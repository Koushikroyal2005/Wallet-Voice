"""Final-release regressions: real isolated SQLAlchemy state; fake push only."""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from test_product_flows import factory
from test_http_contracts import client
from test_merchants_v2 import merchants
from test_v3 import order
from app import reminders, payment_batches as batches
from app.core import settings
from app.models import PaymentRequest, PaymentReminder, PushSubscription, MerchantIdentity, PaymentReservation
from app.services import FinancialError, balances, wallet, reserve
from app.execution import execute_attempt
import asyncio


@pytest.fixture
def clock(monkeypatch):
    current=[datetime(2026,11,11,12,tzinfo=timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return current[0] if tz else current[0].replace(tzinfo=None)
    monkeypatch.setattr(reminders,'datetime',Clock)
    for key in ['vapid_private_key','vapid_public_key','vapid_subject']:monkeypatch.setattr(settings(),key,'synthetic-test-value')
    return current


def prepare_push(factory,clock,minutes=12):
    with factory() as db:
        p=PaymentRequest(merchant='Reminder',category='demo',description='saved checkout',amount=100,expires_at=clock[0]+timedelta(minutes=minutes))
        db.add(p);db.flush()
        prefs=reminders.preferences(db);prefs.enabled=prefs.push_enabled=True;prefs.quiet_start=prefs.quiet_end=0
        db.add(PushSubscription(endpoint='https://fcm.googleapis.com/test',subscription={}))
        reminders.schedule(db);db.commit();return p.id


def test_new_urgent_one_delivery_and_snooze_after_sent_is_durable(factory,clock):
    ident=prepare_push(factory,clock);calls=[]
    sender=lambda **kw:calls.append(kw)
    assert reminders.deliver_one(factory,sender)
    assert not reminders.deliver_one(factory,sender)
    assert len(calls)==1
    with factory() as db:
        for _ in range(3):reminders.schedule(db)
        reminders.change_attention(db,ident,'SNOOZE',5,'explicit-0001');db.commit()
    with factory() as db:
        assert reminders.change_attention(db,ident,'SNOOZE',5,'explicit-0001')['idempotent'];db.commit()
    clock[0]+=timedelta(minutes=5)
    assert reminders.deliver_one(factory,sender)
    with factory() as db:
        assert reminders.change_attention(db,ident,'SNOOZE',5,'explicit-0001')['idempotent']
        reminders.schedule(db);db.commit()
        assert len(list(db.scalars(select(PaymentReminder))))==2
    assert not reminders.deliver_one(factory,sender)
    assert len(calls)==2 and calls[0]['data']!=calls[1]['data']


def test_upcoming_escalates_once_only_when_later_urgent(factory,clock):
    prepare_push(factory,clock,30);calls=[];sender=lambda **kw:calls.append(kw)
    assert reminders.deliver_one(factory,sender)
    clock[0]+=timedelta(minutes=20)
    with factory() as db:reminders.schedule(db);db.commit()
    assert reminders.deliver_one(factory,sender)
    with factory() as db:reminders.schedule(db);db.commit()
    assert not reminders.deliver_one(factory,sender)
    assert len(calls)==2


@pytest.mark.parametrize('stop',['SUCCEEDED','CANCELLED','EXPIRED','optout','quiet','dismiss'])
def test_explicit_reminder_respects_terminal_states_and_preferences(factory,clock,stop):
    ident=prepare_push(factory,clock)
    with factory() as db:
        reminders.change_attention(db,ident,'SNOOZE',5,'explicit-0002')
        if stop in {'SUCCEEDED','CANCELLED','EXPIRED'}:db.get(PaymentRequest,ident).status=stop
        elif stop=='optout':reminders.preferences(db).enabled=False
        elif stop=='quiet':reminders.preferences(db).quiet_start=0;reminders.preferences(db).quiet_end=23
        else:reminders.change_attention(db,ident,'DISMISS')
        db.commit()
    clock[0]+=timedelta(minutes=5)
    calls=[];reminders.deliver_one(factory,lambda **kw:calls.append(kw))
    assert not calls


def test_snooze_superseded_action_retry_cannot_schedule_again(factory,clock):
    ident=prepare_push(factory,clock)
    with factory() as db:
        for key in ['explicit-0003','explicit-0004']:reminders.change_attention(db,ident,'SNOOZE',5,key)
        db.commit()
    with factory() as db:
        assert reminders.change_attention(db,ident,'SNOOZE',5,'explicit-0003')['idempotent']
        rows=list(db.scalars(select(PaymentReminder).where(PaymentReminder.status=='PENDING')))
        assert len(rows)==1 and rows[0].stage=='SNOOZE:explicit-0004'


@pytest.mark.parametrize('when',['before_review','before_pin','before_claim','before_dispatch'])
def test_revoked_identity_blocks_manual_payment_and_releases_reservation(client,factory,when):
    ident=order(client,merchants(factory)[0])
    with factory() as db:
        if when=='before_review':db.get(MerchantIdentity,'rail').active=False;db.commit()
        b=batches.create_batch(db,[ident]);db.commit();batch_id=b.id
        if when=='before_review':
            assert not batches.view(db,b)['can_authorize'];return
        if when=='before_pin':
            db.get(MerchantIdentity,'rail').active=False;db.commit()
            with pytest.raises(FinancialError,match='identity changed'):batches.authorize(db,b,'123456')
            return
        token=batches.authorize(db,b,'123456');db.commit()
        if when=='before_claim':
            db.get(MerchantIdentity,'rail').active=False;db.commit()
            with pytest.raises(FinancialError,match='identity changed'):batches.claim(db,b,token)
            assert balances(db,wallet(db))['reserved_amount']==0;return
        batches.claim(db,b,token);db.commit()
        attempt=batches.view(db,b)['items'][0]['attempt_id']
        db.get(MerchantIdentity,'rail').active=False;db.commit()
    assert execute_attempt(attempt).status=='FAILED'
    with factory() as db:
        assert balances(db,wallet(db))=={'posted_balance':1000000,'reserved_amount':0,'available_balance':1000000}
        assert not batches.view(db,batches.get_batch(db,batch_id))['items'][0]['receipt']


def test_completed_receipt_survives_identity_revocation(client,factory):
    ident=order(client,merchants(factory)[0])
    with factory() as db:
        b=batches.create_batch(db,[ident]);token=batches.authorize(db,b,'123456');db.commit();bid=b.id
    result=batches.execute_batch(factory,bid,token,execute_attempt);receipt=result['items'][0]['receipt']
    with factory() as db:db.get(MerchantIdentity,'rail').active=False;db.commit()
    with factory() as db:
        result=batches.view(db,batches.get_batch(db,bid))
        assert result['status']=='SUCCEEDED' and result['items'][0]['receipt']==receipt


def test_name_collision_or_removed_trace_is_not_identity_evidence(client,factory):
    ident=order(client,merchants(factory)[0])
    with factory() as db:
        p=db.get(PaymentRequest,ident);p.trace={};db.commit()
        with pytest.raises(FinancialError,match='MERCHANT_IDENTITY_UNAVAILABLE'):reserve(db,p,'removed-trace','manual',True)
    review=client.get(f'/api/payments/{ident}/review').json()
    assert not review['payment']['verified'] and not review['merchant_identity']['payable']


@pytest.mark.parametrize('problem',['missing_identity','missing_binding','name_collision'])
def test_manual_review_fails_closed_on_invalid_versioned_identity(client,factory,problem):
    from app.merchant_trust import current_identity
    merchants(factory)
    with factory() as db:
        # Persisted historical verification is not current identity evidence.
        p=PaymentRequest(merchant='Demo Railway',category='merchant_checkout',description='damaged checkout',amount=10000,verified=True,provider='MERCHANT:missing',trace={'merchant_id':'missing'})
        if problem=='missing_binding':p.trace={'simulation':True}
        if problem=='name_collision':p.trace={'merchant_id':'food'};p.provider='MERCHANT:food'
        db.add(p);db.flush();ident=p.id
        identity=current_identity(db,p)
        assert not identity['payable'] and not identity['verified']
        b=batches.create_batch(db,[ident],recognized=True)
        assert not batches.view(db,b)['can_authorize']
        with pytest.raises(FinancialError):batches.authorize(db,b,'123456')
        with pytest.raises(FinancialError,match='MERCHANT_IDENTITY_UNAVAILABLE'):reserve(db,p,'invalid-identity-'+problem,'manual',True)
        db.commit()
    review=client.get(f'/api/payments/{ident}/review').json()
    assert not review['payment']['verified'] and not review['merchant_identity']['payable']


@pytest.mark.parametrize('already_captured',[False,True])
def test_revoked_paypal_merchant_cannot_start_capture_but_evidence_is_preserved(factory,monkeypatch,already_captured):
    from app import paypal
    from test_paypal import order_fixture,capture_response
    merchants(factory)
    calls=[]
    async def provider(method,path,**kwargs):
        calls.append(method)
        return capture_response() if already_captured else {'id':'ORDER-TEST','status':'APPROVED','purchase_units':[]}
    monkeypatch.setattr(paypal,'request',provider)
    with factory() as db:
        o=order_fixture(db);p=db.get(PaymentRequest,o.payment_request_id)
        p.merchant='Demo Railway';p.provider='MERCHANT:rail';p.trace={'merchant_id':'rail'}
        db.get(MerchantIdentity,'rail').active=False;db.commit();before=balances(db,wallet(db));db.commit()
        if already_captured:assert asyncio.run(paypal.capture_order(db,o.paypal_order_id))['status']=='COMPLETED'
        else:
            with pytest.raises(paypal.PayPalError,match='capture is blocked'):asyncio.run(paypal.capture_order(db,o.paypal_order_id))
        assert calls==['GET'] and balances(db,wallet(db))==before


def test_revoked_merchant_cannot_create_paypal_order(client,factory,monkeypatch):
    from app import paypal
    ident=order(client,merchants(factory)[0])
    async def forbidden(*args,**kwargs):pytest.fail('Revoked identity must not call the provider')
    monkeypatch.setattr(paypal,'request',forbidden)
    with factory() as db:
        db.get(MerchantIdentity,'rail').active=False;db.commit()
        with pytest.raises(paypal.PayPalError,match='identity is unavailable'):asyncio.run(paypal.create_order(db,ident))
