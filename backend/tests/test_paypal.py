from datetime import datetime,timezone
from app.models import PayPalOrder,PaymentRequest
from app.paypal import apply_webhook,currency_amount
from app.paypal import configured
from app.services import balances,wallet
from test_domain import db
import asyncio
import copy
import pytest
from sqlalchemy import select,func
from app import paypal
from app.core import settings,Settings
from app.models import PaymentAttempt,PaymentReservation,JournalTransaction,PayPalWebhookEvent


def order_fixture(session):
    payment=PaymentRequest(merchant='Rail',category='travel',description='Ticket',amount=125000,status='PROCESSING')
    session.add(payment);session.flush()
    attempt=PaymentAttempt(payment_request_id=payment.id,idempotency_key=f'paypal-claim:{payment.id}')
    session.add(attempt);session.flush()
    order=PayPalOrder(payment_request_id=payment.id,payment_attempt_id=attempt.id,paypal_order_id='ORDER-TEST',idempotency_key=f'paypal-create:{payment.id}',original_amount=125000,original_currency='INR',provider_amount='14.88',provider_currency='USD')
    session.add(order);session.commit()
    return order


def capture_response(status='COMPLETED',amount='14.88',currency='USD'):
    return {'id':'ORDER-TEST','status':'COMPLETED','purchase_units':[{'payments':{'captures':[{'id':'CAP-TEST','status':status,'amount':{'value':amount,'currency_code':currency}}]}}]}


@pytest.mark.parametrize('status,local',[('COMPLETED','SUCCEEDED'),('PENDING','PROCESSING'),('DENIED','FAILED'),('DECLINED','FAILED'),('FAILED','FAILED')])
def test_capture_states_preserve_wallet_and_idempotent_retry(monkeypatch,status,local):
    s=db();o=order_fixture(s);before=balances(s,wallet(s));s.commit();calls=[]
    async def provider(method,path,**kwargs):
        assert not s.in_transaction(), 'Provider calls must not hold a DB transaction'
        calls.append((method,path,kwargs))
        if '/payments/captures/' in path:return capture_response(status)['purchase_units'][0]['payments']['captures'][0]
        return capture_response(status)
    monkeypatch.setattr(paypal,'request',provider)
    result=asyncio.run(paypal.capture_order(s,o.paypal_order_id))
    assert result['status']==status
    assert s.get(PaymentRequest,o.payment_request_id).status==local
    asyncio.run(paypal.capture_order(s,o.paypal_order_id))
    assert sum(method=='POST' for method,_,_ in calls)==1
    assert calls[0][2]['request_id']==f'paypal-capture:{o.id}'
    assert balances(s,wallet(s))==before
    assert s.scalar(select(func.count(PaymentReservation.id)))==0
    assert s.scalar(select(func.count(JournalTransaction.id)))==0


@pytest.mark.parametrize('mutation',['amount','currency','capture_id','order_id','no_capture','order_only_completed'])
def test_capture_rejects_missing_or_mismatched_evidence(monkeypatch,mutation):
    s=db();o=order_fixture(s);remote=capture_response()
    capture=remote['purchase_units'][0]['payments']['captures'][0]
    if mutation=='amount':capture['amount']['value']='999.00'
    if mutation=='currency':capture['amount']['currency_code']='EUR'
    if mutation=='capture_id':capture.pop('id')
    if mutation=='order_id':remote['id']='OTHER'
    if mutation=='no_capture':remote['purchase_units'][0]['payments']['captures']=[]
    if mutation=='order_only_completed':capture.pop('status')
    async def provider(*args,**kwargs):return remote
    monkeypatch.setattr(paypal,'request',provider)
    with pytest.raises(paypal.PayPalError):asyncio.run(paypal.capture_order(s,o.paypal_order_id))
    s.rollback()
    assert s.get(PaymentRequest,o.payment_request_id).status=='PROCESSING'
    assert s.scalar(select(PayPalOrder)).provider_status=='CREATED'


def test_ambiguous_capture_recovers_by_get_without_another_charge(monkeypatch):
    s=db();o=order_fixture(s);calls=[]
    async def provider(method,path,**kwargs):
        calls.append(method)
        if method=='POST':raise paypal.PayPalError('timeout',retryable=True)
        return capture_response()
    monkeypatch.setattr(paypal,'request',provider)
    assert asyncio.run(paypal.capture_order(s,o.paypal_order_id))['status']=='COMPLETED'
    assert calls==['POST','GET']


def test_ambiguous_capture_stays_unresolved_without_evidence(monkeypatch):
    s=db();o=order_fixture(s)
    async def provider(method,path,**kwargs):
        if method=='POST':raise paypal.PayPalError('timeout',retryable=True)
        return {'id':'ORDER-TEST','status':'APPROVED'}
    monkeypatch.setattr(paypal,'request',provider)
    with pytest.raises(paypal.PayPalError):asyncio.run(paypal.capture_order(s,o.paypal_order_id))
    assert s.get(PaymentRequest,o.payment_request_id).status=='PROCESSING'


def test_create_retry_freezes_payload_and_reuses_existing_order(monkeypatch):
    s=db();p=PaymentRequest(merchant='Rail',category='travel',description='Ticket',amount=125000);s.add(p);s.commit();pid=p.id;calls=[]
    async def provider(method,path,**kwargs):
        assert not s.in_transaction()
        calls.append(copy.deepcopy(kwargs))
        if len(calls)==1:raise paypal.PayPalError('timeout',retryable=True)
        return {'id':'ORDER-TEST','status':'COMPLETED'}
    monkeypatch.setattr(paypal,'request',provider)
    with pytest.raises(paypal.PayPalError):asyncio.run(paypal.create_order(s,pid))
    monkeypatch.setattr(settings(),'paypal_demo_inr_per_usd','90')
    result=asyncio.run(paypal.create_order(s,pid))
    assert calls[0]==calls[1]
    assert result['status']=='CREATED', 'Create alone cannot prove capture'
    assert asyncio.run(paypal.create_order(s,pid))['order_id']=='ORDER-TEST'
    assert len(calls)==2


def webhook(ident,status='COMPLETED'):
    return {'id':ident,'event_type':f'PAYMENT.CAPTURE.{status}','resource':{'id':'CAP-TEST','amount':{'value':'14.88','currency_code':'USD'},'supplementary_data':{'related_ids':{'order_id':'ORDER-TEST'}}}}


def test_webhook_duplicate_and_out_of_order_do_not_regress():
    s=db();o=order_fixture(s)
    paypal.apply_webhook(s,webhook('pending','PENDING'))
    paypal.apply_webhook(s,{'id':'approved','event_type':'CHECKOUT.ORDER.APPROVED','resource':{'id':'ORDER-TEST'}})
    assert o.provider_status=='PENDING'
    paypal.apply_webhook(s,webhook('complete'))
    paypal.apply_webhook(s,webhook('complete'))
    paypal.apply_webhook(s,webhook('late-pending','PENDING'))
    assert o.provider_status=='COMPLETED'
    assert s.scalar(select(func.count(PayPalWebhookEvent.id)))==4


def test_verified_webhook_arriving_before_local_order_is_replayed(monkeypatch):
    s=db();p=PaymentRequest(merchant='Rail',category='travel',description='Ticket',amount=125000);s.add(p);s.commit();pid=p.id
    paypal.apply_webhook(s,webhook('early'))
    async def provider(*args,**kwargs):return {'id':'ORDER-TEST','status':'CREATED'}
    monkeypatch.setattr(paypal,'request',provider)
    assert asyncio.run(paypal.create_order(s,pid))['status']=='COMPLETED'
    assert s.get(PaymentRequest,pid).status=='SUCCEEDED'


def test_webhook_signature_requires_headers_and_provider_success(monkeypatch):
    monkeypatch.setattr(paypal,'configured',lambda:True)
    monkeypatch.setattr(settings(),'paypal_webhook_id','fixture-webhook')
    calls=[]
    async def provider(method,path,**kwargs):calls.append(kwargs);return {'verification_status':'FAILURE'}
    monkeypatch.setattr(paypal,'request',provider)
    assert not asyncio.run(paypal.verify_webhook({},webhook('x')))
    assert not calls
    headers={key:'fixture' for key in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}
    assert not asyncio.run(paypal.verify_webhook(headers,webhook('x')))
    assert calls[0]['payload']['webhook_id']=='fixture-webhook'


def test_production_base_url_is_never_configured(monkeypatch):
    for key,value in [('paypal_enabled',True),('paypal_mode','sandbox'),('paypal_client_id','fixture'),('paypal_client_secret','fixture'),('paypal_base_url','https://api-m.paypal.com')]:monkeypatch.setattr(settings(),key,value)
    assert not paypal.configured()


@pytest.mark.parametrize('rate',['0','-1','NaN','Infinity','invalid'])
def test_invalid_conversion_is_controlled(monkeypatch,rate):
    monkeypatch.setattr(settings(),'paypal_demo_inr_per_usd',rate)
    with pytest.raises(paypal.PayPalError):paypal.currency_amount(125000,'INR')


def test_login_configuration_requires_private_secret_without_exposing_input():
    with pytest.raises(ValueError) as error:Settings(_env_file=None,require_wallet_login=True,wallet_session_secret='',paypal_client_secret='private-test-value')
    assert 'WALLET_SESSION_SECRET' in str(error.value)
    assert 'private-test-value' not in str(error.value)


def test_example_configuration_has_unique_keys():
    from pathlib import Path
    lines=(Path(__file__).resolve().parents[2]/'.env.example').read_text().splitlines()
    keys=[line.split('=',1)[0] for line in lines if '=' in line and not line.startswith('#')]
    assert len(keys)==len(set(keys))


def test_expired_ambiguous_create_does_not_issue_another_order(monkeypatch):
    from datetime import timedelta
    s=db();p=PaymentRequest(merchant='Rail',category='travel',description='Ticket',amount=125000);s.add(p);s.commit();pid=p.id
    calls=[]
    async def provider(*args,**kwargs):calls.append(kwargs);raise paypal.PayPalError('timeout',retryable=True)
    monkeypatch.setattr(paypal,'request',provider)
    with pytest.raises(paypal.PayPalError):asyncio.run(paypal.create_order(s,pid))
    snapshot=dict(p.trace['paypal_create']);snapshot['started_at']=(datetime.now(timezone.utc)-timedelta(hours=6)).isoformat()
    p.trace={**p.trace,'paypal_create':snapshot};s.commit()
    with pytest.raises(paypal.PayPalError,match='reconcile'):asyncio.run(paypal.create_order(s,pid))
    assert len(calls)==1


def test_pending_refresh_completes_without_posting_capture_again(monkeypatch):
    s=db();o=order_fixture(s);paypal.apply_webhook(s,webhook('pending','PENDING'));calls=[]
    async def provider(method,path,**kwargs):
        assert not s.in_transaction()
        calls.append((method,path));return capture_response()['purchase_units'][0]['payments']['captures'][0]
    monkeypatch.setattr(paypal,'request',provider)
    assert asyncio.run(paypal.refresh_order(s,o.paypal_order_id))['status']=='COMPLETED'
    assert calls==[('GET','/v2/payments/captures/CAP-TEST')]


def test_wrong_capture_identity_cannot_replace_recorded_capture():
    s=db();o=order_fixture(s);paypal.apply_webhook(s,webhook('pending','PENDING'))
    event=webhook('wrong');event['resource']['id']='OTHER-CAPTURE'
    with pytest.raises(paypal.PayPalError):paypal.apply_webhook(s,event)
    assert o.provider_status=='PENDING'


def test_full_refund_cannot_be_regressed_by_late_completion():
    s=db();o=order_fixture(s);paypal.apply_webhook(s,webhook('complete'))
    event=webhook('refund','REFUNDED');event['resource']['id']='REFUND-ID'
    paypal.apply_webhook(s,event)
    paypal.apply_webhook(s,webhook('late-complete'))
    assert o.provider_status=='REFUNDED'
    assert s.get(PaymentRequest,o.payment_request_id).status=='REFUNDED'


def test_signature_success_preserves_event_for_provider_verification(monkeypatch):
    monkeypatch.setattr(paypal,'configured',lambda:True)
    monkeypatch.setattr(settings(),'paypal_webhook_id','fixture-webhook')
    event=webhook('signed');calls=[]
    async def provider(method,path,**kwargs):calls.append((path,kwargs));return {'verification_status':'SUCCESS'}
    monkeypatch.setattr(paypal,'request',provider)
    headers={key:'fixture' for key in ['paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time']}
    assert asyncio.run(paypal.verify_webhook(headers,event))
    assert calls[0][0]=='/v1/notifications/verify-webhook-signature'
    assert calls[0][1]['payload']['webhook_event']==event

def test_sandbox_inr_to_usd_uses_decimal_rounding(monkeypatch):
    monkeypatch.setenv("PAYPAL_CHECKOUT_CURRENCY","USD");monkeypatch.setenv("PAYPAL_DEMO_INR_PER_USD","84")
    from app.core import settings
    settings.cache_clear()
    assert currency_amount(125000,"INR")==("14.88","USD","84")
    settings.cache_clear()
def test_paypal_completed_webhook_does_not_debit_wallet():
    s=db();p=PaymentRequest(merchant="Rail",category="travel",description="ticket",amount=125000);s.add(p);s.flush();o=PayPalOrder(payment_request_id=p.id,paypal_order_id="ORDER-1",idempotency_key="key",original_amount=125000,original_currency="INR",provider_amount="14.88",provider_currency="USD",conversion_rate="84");s.add(o);s.flush();before=balances(s,wallet(s))["posted_balance"]
    apply_webhook(s,{"id":"EVENT-1","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{"id":"CAP-1","amount":{"value":"14.88","currency_code":"USD"},"supplementary_data":{"related_ids":{"order_id":"ORDER-1"}}}})
    assert s.get(PaymentRequest,p.id).status=="SUCCEEDED" and s.get(PayPalOrder,o.id).paypal_capture_id=="CAP-1"
    assert balances(s,wallet(s))["posted_balance"]==before
def test_duplicate_webhook_is_idempotent():
    s=db();apply_webhook(s,{"id":"EVENT-duplicate","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{}});apply_webhook(s,{"id":"EVENT-duplicate","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{}})
def test_paypal_is_disabled_without_credentials(monkeypatch):
    monkeypatch.setenv("PAYPAL_ENABLED","false");monkeypatch.delenv("PAYPAL_CLIENT_ID",raising=False);monkeypatch.delenv("PAYPAL_CLIENT_SECRET",raising=False)
    from app.core import settings
    settings.cache_clear();assert configured() is False;settings.cache_clear()
