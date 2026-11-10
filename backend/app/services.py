from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .core import settings
from .models import AppEvent, AutoPaySettings, JournalTransaction, LedgerAccount, LedgerEntry, Operation, PaymentAttempt, PaymentRequest, PaymentReservation, PaymentIntent, SpendingMandate, ReservationStatus, Status, Wallet, uid

def utc(value):return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

class FinancialError(ValueError): pass
class TransitionError(FinancialError): pass
ALLOWED={"PENDING":{"HELD","PROCESSING","EXPIRED","CANCELLED"},"HELD":{"PENDING","PROCESSING","EXPIRED","CANCELLED"},"PROCESSING":{"SUCCEEDED","FAILED"},"FAILED":{"PROCESSING","EXPIRED","CANCELLED"},"SUCCEEDED":{"REFUNDED"}}
def emit(db:Session,event_type:str,payload:dict):
    from .audit import queue
    db.add(AppEvent(event_type=event_type,payload=payload));queue(db,event_type,payload)
def transition(p:PaymentRequest,target:str):
    if p.status==target:return
    if target not in ALLOWED.get(p.status,set()):raise TransitionError(f"Invalid payment transition {p.status} → {target}")
    p.status=target
def account(db:Session,name:str,typ:str,direction:str,wallet_id:str|None=None):
    row=db.scalar(select(LedgerAccount).where(LedgerAccount.name==name))
    if not row:row=LedgerAccount(name=name,account_type=typ,normal_direction=direction,wallet_id=wallet_id);db.add(row);db.flush()
    return row
def wallet(db:Session,lock:bool=False):
    q=select(Wallet).where(Wallet.user_id=="demo-user")
    if lock:q=q.with_for_update()
    w=db.scalar(q)
    if not w:
        try:
            with db.begin_nested():
                w=Wallet();db.add(w);db.flush()
        except IntegrityError:
            q=select(Wallet).where(Wallet.user_id=="demo-user")
            if lock:q=q.with_for_update()
            w=db.scalar(q)
    if not w.ledger_account_id:w.ledger_account_id=account(db,f"wallet:{w.user_id}","LIABILITY","CREDIT",w.id).id
    account(db,"demo_bank_clearing","ASSET","DEBIT");account(db,"demo_merchant_clearing","ASSET","DEBIT")
    return w
def posted_balance(db:Session,w:Wallet):
    credit=db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount),0)).join(JournalTransaction).where(LedgerEntry.ledger_account_id==w.ledger_account_id,LedgerEntry.direction=="CREDIT",JournalTransaction.status=="POSTED")) or 0
    debit=db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount),0)).join(JournalTransaction).where(LedgerEntry.ledger_account_id==w.ledger_account_id,LedgerEntry.direction=="DEBIT",JournalTransaction.status=="POSTED")) or 0
    return int(credit-debit)
def active_reserved(db:Session,w:Wallet): return int(db.scalar(select(func.coalesce(func.sum(PaymentReservation.amount),0)).where(PaymentReservation.wallet_id==w.id,PaymentReservation.status==ReservationStatus.ACTIVE.value,PaymentReservation.expires_at>datetime.now(timezone.utc))) or 0)
def balances(db:Session,w:Wallet):
    posted=posted_balance(db,w);reserved=active_reserved(db,w);return {"posted_balance":posted,"reserved_amount":reserved,"available_balance":posted-reserved}
def settings_for(db:Session):
    s=db.scalar(select(AutoPaySettings).where(AutoPaySettings.user_id=="demo-user"))
    if not s:
        c=settings()
        try:
            with db.begin_nested():
                s=AutoPaySettings(per_transaction_limit=c.default_per_transaction_limit,daily_limit=c.default_daily_spending_limit,minimum_balance=c.default_minimum_balance);db.add(s);db.flush()
        except IntegrityError:s=db.scalar(select(AutoPaySettings).where(AutoPaySettings.user_id=='demo-user'))
    return s
def day_spend(db:Session,w:Wallet):
    start=datetime.now(ZoneInfo(settings().app_timezone)).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    paid=db.scalar(select(func.coalesce(func.sum(Operation.amount),0)).where(Operation.kind=="PAYMENT",Operation.status=="SUCCEEDED",Operation.created_at>=start)) or 0
    active=db.scalar(select(func.coalesce(func.sum(PaymentReservation.amount),0)).where(PaymentReservation.wallet_id==w.id,PaymentReservation.status=="ACTIVE",PaymentReservation.expires_at>datetime.now(timezone.utc))) or 0
    return int(paid+active)
def policy(db:Session,p:PaymentRequest,mode="auto",merchant_confirmed=False):
    if p.explicit_hold:return {"decision":"EXPLICIT_HOLD","reason_codes":["USER_HELD"],"urgency":"HELD"}
    s=settings_for(db);w=wallet(db);b=balances(db,w);remaining=(utc(p.expires_at)-datetime.now(timezone.utc)).total_seconds() if p.expires_at else None;urgency="FLEXIBLE" if remaining is None or remaining>10800 else "DUE_SOON" if remaining>=900 else "URGENT";codes=[];decision="ELIGIBLE"
    hard=[]
    if p.currency!=w.currency:hard.append("CURRENCY_MISMATCH")
    if p.status=="SUCCEEDED":hard.append("ALREADY_PAID")
    elif p.status not in {"PENDING","HELD","FAILED"}:hard.append("NOT_PAYABLE")
    if p.expires_at and remaining<=0:hard.append("EXPIRED")
    if p.amount>s.per_transaction_limit:hard.append("PER_TRANSACTION_LIMIT")
    if day_spend(db,w)+p.amount>s.daily_limit:hard.append("DAILY_LIMIT")
    if b["available_balance"]-p.amount<s.minimum_balance:hard.append("MINIMUM_BALANCE")
    if hard:
        codes.extend(hard);decision="EXPIRED" if "EXPIRED" in hard else "HELD_INSUFFICIENT_BALANCE" if "MINIMUM_BALANCE" in hard else "HELD_LIMIT_EXCEEDED" if any(x in hard for x in ["PER_TRANSACTION_LIMIT","DAILY_LIMIT"]) else "REJECTED"
    elif not p.verified and not merchant_confirmed and mode=="auto":codes.append("UNKNOWN_MERCHANT");decision="HELD_UNKNOWN_MERCHANT"
    elif not p.verified and not merchant_confirmed and mode=="manual":codes.append("UNKNOWN_MERCHANT_CONFIRMATION_REQUIRED");decision="MANUAL_CONFIRMATION_REQUIRED"
    elif mode=="auto" and not s.enabled:codes.append("AUTOPAY_DISABLED");decision="MANUAL_APPROVAL_REQUIRED"
    elif mode=="auto" and not automatic_mandate(db,p,False):codes.append("MANDATE_REQUIRED");decision="MANUAL_APPROVAL_REQUIRED"
    elif mode=="auto" and s.time_sensitive_only and urgency=="FLEXIBLE":codes.append("TIME_SENSITIVE_ONLY");decision="HELD_FLEXIBLE"
    return {"policy_version":"financial-v2","mode":mode,"decision":decision,"reason_codes":codes,"urgency":urgency,"remaining_seconds":max(0,int(remaining)) if remaining is not None else None,"merchant_verified":p.verified,"transaction_amount":p.amount,"daily_spend":day_spend(db,w),**b,"settings":{"enabled":s.enabled,"time_sensitive_only":s.time_sensitive_only,"minimum_balance":s.minimum_balance,"daily_limit":s.daily_limit}}
def post_journal(db:Session,w:Wallet,op:Operation,debit:LedgerAccount,credit:LedgerAccount,description:str):
    # Every incoming journal credit, including future demo rails, shares this cap.
    # Callers serialize on the wallet; acquire it here as a defence in depth.
    wallet(db,True)
    db.flush()  # Include earlier credits posted within this same transaction.
    existing=db.scalar(select(JournalTransaction).where(JournalTransaction.operation_id==op.id))
    if existing:return existing
    if credit.id==w.ledger_account_id and posted_balance(db,w)+op.amount>10_000_000:
        raise FinancialError('Demo wallet maximum is INR 100,000. Withdraw funds before receiving more.')
    j=JournalTransaction(operation_id=op.id,description=description,reference=op.reference);db.add(j);db.flush();db.add_all([LedgerEntry(journal_transaction_id=j.id,ledger_account_id=debit.id,direction="DEBIT",amount=op.amount,currency=w.currency),LedgerEntry(journal_transaction_id=j.id,ledger_account_id=credit.id,direction="CREDIT",amount=op.amount,currency=w.currency)])
    w.cached_balance=posted_balance(db,w)+(op.amount if credit.id==w.ledger_account_id else -op.amount if debit.id==w.ledger_account_id else 0);return j

def batch_preview(db:Session):
    w=wallet(db);b=balances(db,w);s=settings_for(db);remaining=b['available_balance']-s.minimum_balance;daily=s.daily_limit-day_spend(db,w);items=[]
    rows=db.scalars(select(PaymentRequest).where(PaymentRequest.status.in_(['PENDING','HELD']),PaymentRequest.explicit_hold.is_(False)).order_by(PaymentRequest.created_at,PaymentRequest.id)).all()
    for p in rows:
        decision=policy(db,p,'manual')
        if decision['decision']=='ELIGIBLE':
            if p.amount>remaining:decision={**decision,'decision':'HELD_INSUFFICIENT_BALANCE','reason_codes':['BATCH_AVAILABLE_BALANCE']}
            elif p.amount>daily:decision={**decision,'decision':'HELD_LIMIT_EXCEEDED','reason_codes':['BATCH_DAILY_LIMIT']}
            else:remaining-=p.amount;daily-=p.amount
        items.append({'id':p.id,'merchant':p.merchant,'amount':p.amount,'decision':decision['decision'],'reason_codes':decision['reason_codes']})
    eligible=[item for item in items if item['decision']=='ELIGIBLE'];total=sum(item['amount'] for item in eligible)
    return {'total_pending':len(items),'eligible_count':len(eligible),'held_count':len(items)-len(eligible),'total_payable':total,'required_total':total,'available_balance':b['available_balance'],'policy_version':'financial-v3','items':items,'dry_run':True}
def operation(db:Session,amount:int,kind:str,key:str):
    old=db.scalar(select(Operation).where(Operation.idempotency_key==key))
    if old:
        if old.amount!=amount or old.kind!=kind:raise FinancialError("Idempotency key belongs to a different operation")
        return old
    try:
        with db.begin_nested():
            op=Operation(kind=kind,amount=amount,status="SUCCEEDED",reference=f"DEMO-{uid()[:8]}",idempotency_key=key);db.add(op);db.flush()
    except IntegrityError:
        op=db.scalar(select(Operation).where(Operation.idempotency_key==key))
        if op:return op
        raise
    return op
def topup_or_withdraw(db:Session,amount:int,kind:str,key:str):
    if amount<=0 or kind not in {"TOPUP","WITHDRAWAL"}:raise FinancialError("Invalid transfer")
    w=wallet(db,True);op=operation(db,amount,kind,key)
    if db.scalar(select(JournalTransaction).where(JournalTransaction.operation_id==op.id)):return op
    if kind=="WITHDRAWAL" and balances(db,w)["available_balance"]<amount:raise FinancialError("Insufficient available wallet balance")
    bank=account(db,"demo_bank_clearing","ASSET","DEBIT");wa=db.get(LedgerAccount,w.ledger_account_id)
    post_journal(db,w,op,bank,wa,"Demo bank top-up") if kind=="TOPUP" else post_journal(db,w,op,wa,bank,"Demo bank withdrawal");emit(db,"wallet.updated",{"wallet_id":w.id,"operation_id":op.id});return op
def automatic_mandate(db,p,lock=True):
    # Identity is bound to the authenticated ingestion path, never a display name alone.
    if not p.provider.startswith('MERCHANT:'):return None
    from .agentic import mandate_for
    from .mandate_authority import recipient_matches
    row=mandate_for(db,p.merchant,p.amount,lock,(p.trace or {}).get('merchant_id'))
    return row if row and recipient_matches(db,row,p) else None

def reserve(db:Session,p:PaymentRequest,key:str,mode:str,confirm_unknown=False):
    db.flush()
    w=wallet(db,True)
    p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==p.id).with_for_update().execution_options(populate_existing=True))
    old=db.scalar(select(PaymentAttempt).where(PaymentAttempt.idempotency_key==key))
    if old:
        if old.payment_request_id!=p.id or not old.reservation_id:raise FinancialError("Idempotency key belongs to another payment or funding source")
        return old
    settled=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==p.id,PaymentAttempt.status.in_(["PROCESSING","SUCCEEDED"])).with_for_update())
    if settled:
        if not settled.reservation_id:raise FinancialError("Payment is owned by PayPal checkout")
        return settled
    d=policy(db,p,mode,confirm_unknown)
    if d["decision"]!="ELIGIBLE":raise FinancialError(", ".join(d["reason_codes"]) or d["decision"])
    if db.scalar(select(PaymentReservation).where(PaymentReservation.payment_request_id==p.id,PaymentReservation.status=="ACTIVE").with_for_update()):raise FinancialError("Payment already reserved")
    if mode=='auto':
        mandate=automatic_mandate(db,p)
        if not mandate:raise FinancialError('MANDATE_REQUIRED')
        mandate.spent_today+=p.amount
        p.trace={**(p.trace or {}),'mandate_id':mandate.id,'mandate_day':mandate.context['usage_date']}
    transition(p,"PROCESSING");a=PaymentAttempt(payment_request_id=p.id,idempotency_key=key);db.add(a);db.flush();r=PaymentReservation(wallet_id=w.id,payment_request_id=p.id,payment_attempt_id=a.id,amount=p.amount,currency=p.currency,expires_at=datetime.now(timezone.utc)+timedelta(minutes=10));db.add(r);db.flush();a.reservation_id=r.id;emit(db,"payment.reserved",{"payment_id":p.id,"reservation_id":r.id});return a
def finalize(db:Session,attempt_id:str,success:bool,reference:str,reason:str|None=None):
    w=wallet(db,True)
    a=db.scalar(select(PaymentAttempt).where(PaymentAttempt.id==attempt_id).with_for_update().execution_options(populate_existing=True))
    if not a or a.status!="PROCESSING":return a
    if not a.reservation_id:raise FinancialError("External payment cannot be settled by wallet")
    p=db.get(PaymentRequest,a.payment_request_id);r=db.get(PaymentReservation,a.reservation_id)
    if r.status!="ACTIVE" or utc(r.expires_at)<=datetime.now(timezone.utc):success=False;reason="RESERVATION_EXPIRED"
    if success:
        op=operation(db,p.amount,"PAYMENT",f"payment:{p.id}");post_journal(db,w,op,db.get(LedgerAccount,w.ledger_account_id),account(db,"demo_merchant_clearing","ASSET","DEBIT"),f"Demo merchant payment: {p.merchant}");r.status="CONSUMED";a.status="SUCCEEDED";a.provider_reference=reference;transition(p,"SUCCEEDED");emit(db,"payment.completed",{"payment_id":p.id,"attempt_id":a.id,"operation_id":op.id})
    else:r.status="RELEASED";a.status="FAILED";a.failure_reason=reason;transition(p,"FAILED");emit(db,"payment.failed",{"payment_id":p.id,"attempt_id":a.id,"reason":reason})
    for intent in db.scalars(select(PaymentIntent).where(PaymentIntent.payment_request_id==p.id)).all():intent.status=a.status
    trace=dict(p.trace or {})
    if not success and trace.get("mandate_id") and not trace.get("allowance_released"):
        mandate=db.scalar(select(SpendingMandate).where(SpendingMandate.id==trace["mandate_id"]).with_for_update())
        if mandate and (mandate.context or {}).get("usage_date")==trace.get("mandate_day"):mandate.spent_today=max(0,mandate.spent_today-p.amount)
        trace["allowance_released"]=True;p.trace=trace
    db.flush()
    from .payment_batches import reconcile_for_attempt
    reconcile_for_attempt(db,a.id)
    return a
