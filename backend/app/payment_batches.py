"""Exact, immutable internal-wallet reviews. No provider call holds wallet locks."""
import hashlib
import json
from datetime import datetime,timedelta,timezone
from sqlalchemy import select
from .models import PaymentBatch,PaymentBatchItem,PaymentRequest,PaymentAttempt,AuthorizationChallenge,JournalTransaction,Operation
from .services import FinancialError,wallet,balances,policy,reserve,utc,settings_for,day_spend,emit
from .authorization import create_challenge,verify_challenge,consume_approval,AuthorizationError

def request_snapshot(db,p,lock=False):
    from .merchant_trust import current_identity
    identity=current_identity(db,p,lock)
    return {'id':p.id,'merchant':p.merchant,'amount':p.amount,'currency':p.currency,
            'deadline':utc(p.expires_at).isoformat() if p.expires_at else None,
            'verified':identity['verified'],'identity_state':identity['state'],'provider':p.provider,'merchant_id':identity['merchant_id'],'description':p.description}

def digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def create_batch(db,ids,recognized=False,acknowledged_ids=None):
    if not ids or len(ids)>50 or len(set(ids))!=len(ids):raise FinancialError('Choose 1–50 distinct payment requests')
    wallet(db,True)
    rows=[]
    for ident in ids:
        p=db.get(PaymentRequest,ident)
        if not p:raise FinancialError('A selected payment is unavailable')
        rows.append(request_snapshot(db,p))
    snapshot={'items':rows,'source':'AI_WALLET','recognized':recognized,'acknowledged_ids':sorted(acknowledged_ids or [])}
    batch=PaymentBatch(snapshot=snapshot,snapshot_hash=digest(snapshot),total=sum(p['amount'] for p in rows),expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
    db.add(batch);db.flush()
    for ident in ids:db.add(PaymentBatchItem(batch_id=batch.id,payment_request_id=ident))
    db.flush()
    emit(db,'payment.batch.prepared',{'batch_id':batch.id})
    return batch

def get_batch(db,ident,lock=False):
    if lock:wallet(db,True)
    q=select(PaymentBatch).where(PaymentBatch.id==ident,PaymentBatch.user_id=='demo-user')
    if lock:q=q.with_for_update().execution_options(populate_existing=True)
    row=db.scalar(q)
    if not row:raise FinancialError('Batch not found')
    return row

def check_snapshot(db,batch):
    if utc(batch.expires_at)<=datetime.now(timezone.utc):raise FinancialError('Review expired; prepare a fresh review')
    if batch.source!='AI_WALLET' or digest(batch.snapshot)!=batch.snapshot_hash or batch.total!=sum(x['amount'] for x in batch.snapshot['items']):raise FinancialError('Review snapshot changed')
    stored=list(db.scalars(select(PaymentBatchItem.payment_request_id).where(PaymentBatchItem.batch_id==batch.id)))
    if sorted(stored)!=sorted(x['id'] for x in batch.snapshot['items']):raise FinancialError('Review selection changed')
    for saved in batch.snapshot['items']:
        p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==saved['id']).with_for_update().execution_options(populate_existing=True))
        if not p or request_snapshot(db,p,True)!=saved:raise FinancialError('Payment details or merchant identity changed; prepare a fresh review')

def view(db,batch):
    w=wallet(db);balance=balances(db,w);remaining=balance['available_balance'];daily=day_spend(db,w);s=settings_for(db)
    items=[]
    for saved in batch.snapshot['items']:
        p=db.get(PaymentRequest,saved['id']);codes=[]
        acknowledged=saved['id'] in batch.snapshot.get('acknowledged_ids',[])
        d=policy(db,p,'manual',batch.snapshot['recognized'] or acknowledged) if p else {'decision':'REJECTED','reason_codes':['UNAVAILABLE']}
        codes=list(d['reason_codes'])
        current=request_snapshot(db,p) if p else None
        if p and current!=saved:codes.append('DETAILS_CHANGED')
        if d['decision']=='ELIGIBLE':
            if remaining-p.amount<s.minimum_balance:codes.append('BATCH_AVAILABLE_BALANCE')
            if daily+p.amount>s.daily_limit:codes.append('BATCH_DAILY_LIMIT')
            remaining-=p.amount;daily+=p.amount
        item=db.scalar(select(PaymentBatchItem).where(PaymentBatchItem.batch_id==batch.id,PaymentBatchItem.payment_request_id==saved['id']))
        a=db.get(PaymentAttempt,item.attempt_id) if item and item.attempt_id else None
        op=db.scalar(select(Operation).where(Operation.idempotency_key==f"payment:{saved['id']}"))
        j=db.scalar(select(JournalTransaction).where(JournalTransaction.operation_id==op.id)) if op else None
        items.append({**saved,'current_identity':current['identity_state'] if current else 'MISSING','current_verified':current['verified'] if current else False,'acknowledged':acknowledged,'blocked':bool(codes),'reason_codes':codes,'status':a.status if a else p.status if p else 'UNAVAILABLE',
                      'attempt_id':a.id if a else None,'failure_reason':a.failure_reason if a else None,
                      'receipt':{'journal_id':j.id,'operation_id':op.id,'timestamp':utc(j.created_at).isoformat(),'status':a.status,'provider_reference':a.provider_reference} if j and a else None})
    states=[i['status'] for i in items]
    status=batch.status
    if status in {'PROCESSING','SUCCEEDED','PARTIAL','FAILED'}:
        status='PROCESSING' if 'PROCESSING' in states else 'SUCCEEDED' if all(x=='SUCCEEDED' for x in states) else 'PARTIAL' if 'SUCCEEDED' in states else 'FAILED'
    elif utc(batch.expires_at)<=datetime.now(timezone.utc):status='EXPIRED'
    return {'id':batch.id,'snapshot_hash':batch.snapshot_hash,'source':batch.source,'total':batch.total,'currency':w.currency,'status':status,
            'expires_at':batch.expires_at.isoformat(),'items':items,**balance,'remaining_after_payment':balance['available_balance']-batch.total,
            'funding_shortfall':max(0,batch.total+s.minimum_balance-balance['available_balance']),
            'can_authorize':status=='REVIEW' and not any(i['blocked'] for i in items)}

def authorize(db,batch,pin):
    check_snapshot(db,batch)
    if not view(db,batch)['can_authorize']:raise FinancialError('Every selected item must be eligible; revise and review the selection')
    challenge=create_challenge(db,'PAYMENT',batch.total,batch.id,{'snapshot_hash':batch.snapshot_hash,'source':batch.source})
    token=verify_challenge(db,challenge.id,pin)
    batch.approval_id=challenge.id
    return token

def claim(db,batch,token):
    if batch.status!='REVIEW':
        if batch.status=='CANCELLED':raise AuthorizationError('Review was cancelled; prepare a new review')
        approval=db.get(AuthorizationChallenge,batch.approval_id) if batch.approval_id else None
        if not approval or approval.approval_token!=token or approval.status!='CONSUMED':raise AuthorizationError('Retry must use this batch approval')
        return
    check_snapshot(db,batch)
    if not view(db,batch)['can_authorize']:raise FinancialError('Payment state or spending rules changed; review again')
    approval=consume_approval(db,token,'PAYMENT',batch.total,batch.id,{'snapshot_hash':batch.snapshot_hash,'source':batch.source})
    if approval.id!=batch.approval_id:raise AuthorizationError('Use the latest approval for this batch')
    # All reservations succeed in one transaction or the entire claim rolls back.
    for item in db.scalars(select(PaymentBatchItem).where(PaymentBatchItem.batch_id==batch.id).order_by(PaymentBatchItem.payment_request_id)).all():
        p=db.get(PaymentRequest,item.payment_request_id)
        existing=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==p.id,PaymentAttempt.status.in_(['PROCESSING','SUCCEEDED'])))
        if existing:raise FinancialError('A selected payment was claimed elsewhere; review again')
        item.attempt_id=reserve(db,p,f'batch-v1:{batch.id}:{p.id}','manual',batch.snapshot['recognized'] or p.id in batch.snapshot.get('acknowledged_ids',[])).id
    batch.status='PROCESSING';emit(db,'payment.batch.updated',{'batch_id':batch.id})

def execute_batch(factory,ident,token,executor):
    with factory() as db:
        batch=get_batch(db,ident,True)
        claim(db,batch,token);db.commit()
        ids=list(db.scalars(select(PaymentBatchItem.attempt_id).where(PaymentBatchItem.batch_id==ident)))
    for attempt_id in ids:
        try:executor(attempt_id)
        except Exception:pass  # Uncertain execution remains PROCESSING for worker reconciliation.
    with factory() as db:return view(db,get_batch(db,ident))

def reconcile_for_attempt(db,attempt_id):
    """Persist aggregate outcome when either the request thread or worker settles."""
    for ident in db.scalars(select(PaymentBatchItem.batch_id).where(PaymentBatchItem.attempt_id==attempt_id)):
        batch=db.scalar(select(PaymentBatch).where(PaymentBatch.id==ident).with_for_update())
        states=list(db.scalars(select(PaymentAttempt.status).join(PaymentBatchItem,PaymentBatchItem.attempt_id==PaymentAttempt.id).where(PaymentBatchItem.batch_id==ident)))
        status='PROCESSING' if 'PROCESSING' in states else 'SUCCEEDED' if states and all(s=='SUCCEEDED' for s in states) else 'PARTIAL' if 'SUCCEEDED' in states else 'FAILED'
        if batch.status!=status:batch.status=status;emit(db,'payment.batch.updated',{'batch_id':ident,'status':status})
