from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import (AutoPaySettings, AuthorizationChallenge, Conversation, JournalTransaction,
    Operation, PaymentAttempt, PaymentRequest, PaymentReservation, SpendingMandate, PayPalOrder)
from app.authorization import create_challenge, verify_challenge, change_pin, consume_approval, AuthorizationError
from app.services import balances, wallet, reserve, finalize, topup_or_withdraw, FinancialError
from app.core import settings
from app.context import contextual_intent
from app.main import (Amount, Batch, IntentCreate, IntentExecute, MerchantCheckout, add_payment_intent,
    authorized_transfer, execute_intent, merchant_checkout, evaluate, confirm, payments)
from app.paypal import apply_webhook, PayPalError


@pytest.fixture
def factory(tmp_path, monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path / 'wallet.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    for module in ['app.main','app.execution','app.maintenance']:
        monkeypatch.setattr(f'{module}.SessionLocal',factory)
    with factory() as db:
        topup_or_withdraw(db,1_000_000,'TOPUP','initial-funding')
        db.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));db.commit()
    yield factory
    engine.dispose()


def payment(db, amount=10000, description='Ticket'):
    row=PaymentRequest(merchant='Indian Railways',category='travel',description=description,amount=amount,verified=True)
    db.add(row);db.flush();return row


def test_pin_change_revokes_old_approvals(factory):
    with factory() as db:
        challenge=create_challenge(db,'TOPUP',10000);token=verify_challenge(db,challenge.id,'123456');db.commit()
        change_pin(db,'123456','654321');db.commit()
        with pytest.raises(AuthorizationError):consume_approval(db,token,'TOPUP',10000)
        new=create_challenge(db,'TOPUP',10000)
        assert verify_challenge(db,new.id,'654321')


def test_failed_pin_attempts_remain_locked_after_commit(factory):
    with factory() as db:
        challenge=create_challenge(db,'TOPUP',10000);db.commit();ident=challenge.id
    for _ in range(settings().pin_max_attempts):
        with factory() as db:
            with pytest.raises(AuthorizationError):verify_challenge(db,ident,'000000')
            db.commit()
    with factory() as db:
        with pytest.raises(AuthorizationError,match='temporarily locked'):verify_challenge(db,ident,'123456')


def test_transfer_retry_uses_same_approval_and_posts_once(factory):
    with factory() as db:
        c=create_challenge(db,'TOPUP',10000);token=verify_challenge(db,c.id,'123456');db.commit()
        data=Amount(amount=10000,idempotency_key='retry-topup',approval_token=token)
        first=authorized_transfer(db,data,'TOPUP');db.commit()
        second=authorized_transfer(db,data,'TOPUP');db.commit()
        assert first.id==second.id
        assert balances(db,wallet(db))['posted_balance']==1_010_000
        with pytest.raises(AuthorizationError):authorized_transfer(db,data.model_copy(update={'amount':20000}),'TOPUP')


def test_idempotency_key_cannot_be_reused_for_other_amount(factory):
    with factory() as db:
        with pytest.raises(FinancialError):topup_or_withdraw(db,100,'WITHDRAWAL','initial-funding')


def test_internal_rail_rejects_paypal_claim(factory):
    with factory() as db:
        p=payment(db);db.add(PaymentAttempt(payment_request_id=p.id,idempotency_key=f'paypal-claim:{p.id}',status='PROCESSING'));db.commit()
        with pytest.raises(FinancialError,match='PayPal'):reserve(db,p,'internal-retry','manual')


def test_expired_attempt_cannot_debit_newly_spent_funds(factory):
    with factory() as db:
        p=payment(db,900000);db.get(AutoPaySettings,db.scalar(select(AutoPaySettings)).id).per_transaction_limit=1_000_000
        a=reserve(db,p,'expired-attempt','manual');db.get(PaymentReservation,a.reservation_id).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
        topup_or_withdraw(db,900000,'WITHDRAWAL','after-expiry');db.commit()
        outcome=finalize(db,a.id,True,'late-provider-result');db.commit()
        assert outcome.status=='FAILED' and outcome.failure_reason=='RESERVATION_EXPIRED'
        assert balances(db,wallet(db))['available_balance']==100000


def test_draft_execution_is_atomic_and_returns_current_status(factory):
    with factory() as db:
        draft=add_payment_intent(IntentCreate(amount=10000,merchant='Asha'),db)
        c=create_challenge(db,'P2P',10000,draft['id'],{'version':draft['version'],'source':'AI_WALLET'})
        token=verify_challenge(db,c.id,'123456');db.commit()
        data=IntentExecute(approval_token=token,idempotency_key='draft-execute')
        result=execute_intent(draft['id'],data,db)
        assert result['intent']['status']=='SUCCEEDED'
        repeat=execute_intent(draft['id'],data,db)
        assert repeat['payment']['id']==result['payment']['id']
        assert balances(db,wallet(db))['posted_balance']==990000


def test_provider_called_with_no_database_transaction(factory, monkeypatch):
    from app.providers import DemoPaymentProvider,ProviderResult
    def execute(self,p,a):
        assert p._sa_instance_state.session is None
        assert a._sa_instance_state.session is None
        return ProviderResult(True,'test-provider')
    monkeypatch.setattr(DemoPaymentProvider,'execute',execute)
    with factory() as db:
        p=payment(db);a=reserve(db,p,'detached-provider','manual');db.commit();ident=a.id
    from app.execution import execute_attempt
    assert execute_attempt(ident).status=='SUCCEEDED'


def test_merchant_failure_releases_daily_allowance(factory):
    day=datetime.now(ZoneInfo(settings().app_timezone)).date().isoformat()
    with factory() as db:
        expiry=datetime.now(timezone.utc)+timedelta(days=1)
        details={'merchant':settings().demo_merchant_name,'daily_limit':300000,'expires_at':int(expiry.timestamp())}
        challenge=create_challenge(db,'MANDATE',200000,settings().demo_merchant_name,details)
        token=verify_challenge(db,challenge.id,'123456');db.flush();consume_approval(db,token,'MANDATE',200000,settings().demo_merchant_name,details)
        m=SpendingMandate(merchant=settings().demo_merchant_name,max_amount=200000,daily_limit=300000,expires_at=expiry,context={'usage_date':day});db.add(m);db.commit()
        result=merchant_checkout(MerchantCheckout(merchant=settings().demo_merchant_name,order_reference='DEMO-failure',amount=125000,description='force-fail'),settings().demo_merchant_api_key,db)
        assert result['status']=='FAILED'
        db.expire_all();assert db.get(SpendingMandate,m.id).spent_today==0


def test_get_payments_keeps_mandate_accounting_metadata(factory):
    with factory() as db:
        p=payment(db);p.trace={'mandate_id':'example','mandate_day':'2026-11-08'};db.commit()
        payments(db);db.commit();db.expire_all()
        assert db.get(PaymentRequest,p.id).trace['mandate_id']=='example'


def test_batch_failure_does_not_corrupt_other_payment(factory):
    with factory() as db:
        good=payment(db);bad=payment(db,description='force-fail');db.commit()
        before=db.scalar(select(func.count(Operation.id)))
        preview=evaluate(db)
        assert db.scalar(select(func.count(Operation.id)))==before
        from app.payment_batches import create_batch,authorize,execute_batch
        from app.execution import execute_attempt
        b=create_batch(db,[good.id,bad.id]);token=authorize(db,b,'123456');db.commit()
        result=execute_batch(factory,b.id,token,execute_attempt)
        db.expire_all()
        assert sorted(x['status'] for x in result['items'])==['FAILED','SUCCEEDED']
        assert balances(db,wallet(db))['posted_balance']==990000
        assert balances(db,wallet(db))['reserved_amount']==0
        db.rollback();execute_batch(factory,b.id,token,execute_attempt)
        assert balances(db,wallet(db))['posted_balance']==990000


def test_followup_source_switch_and_cancel_never_execute(factory):
    conversation=Conversation(selected_payment_id='ticket',context={'preview':{'payment_source':'AI_WALLET'}})
    intent=contextual_intent('use PayPal instead',conversation)
    assert intent.tool=='prepare_manual_payment' and intent.args['payment_source']=='PAYPAL_SANDBOX'
    changed=contextual_intent('change it to 800',conversation)
    assert changed.tool==''
    contextual_intent('cancel',conversation)
    assert conversation.selected_payment_id is None


def test_worker_global_autopay_cannot_authorize_and_leaves_explicit_hold(factory):
    from app.maintenance import tick
    with factory() as db:
        eligible=payment(db);held=payment(db);held.explicit_hold=True;held.status='HELD';db.commit();a,b=eligible.id,held.id
    tick()
    with factory() as db:
        assert db.get(PaymentRequest,a).status=='PENDING'
        assert db.get(PaymentRequest,b).status=='HELD'


def test_webhook_rejects_wrong_amount_and_cannot_regress_completed_order(factory):
    with factory() as db:
        p=payment(db);o=PayPalOrder(payment_request_id=p.id,paypal_order_id='TEST',idempotency_key='TEST',original_amount=10000,original_currency='INR',provider_amount='1.19',provider_currency='USD');db.add(o);db.commit()
        resource={'id':'CAPTURE','amount':{'value':'999.00','currency_code':'USD'},'supplementary_data':{'related_ids':{'order_id':'TEST'}}}
        with pytest.raises(PayPalError):apply_webhook(db,{'id':'wrong','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':resource})
        resource['amount']['value']='1.19'
        apply_webhook(db,{'id':'correct','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':resource})
        apply_webhook(db,{'id':'old-approved','event_type':'CHECKOUT.ORDER.APPROVED','resource':{'id':'TEST'}})
        assert db.get(PayPalOrder,o.id).provider_status=='COMPLETED'
