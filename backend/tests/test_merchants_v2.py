"""Actual HTTP/SQLAlchemy merchant-to-wallet journeys; providers remain simulated."""
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
import pytest
from test_product_flows import factory
from test_http_contracts import client
from app.merchants import provision
from app.models import PaymentRequest,MerchantOrder,JournalTransaction,NotificationPreferences,PaymentReminder,SpendingMandate
from app.services import reserve,FinancialError,balances,wallet
from app.reminders import schedule,preferences
from app import payment_batches as batches
from app.authorization import create_challenge,verify_challenge,consume_approval
from app.execution import execute_attempt

def merchants(factory):
    with factory() as db:
        headers=[]
        for ident,name in [('rail','Demo Railway'),('food','Demo Kitchen')]:
            key=provision(db,ident,name);headers.append({'X-Merchant-Id':ident,'X-Merchant-Key':key,'Idempotency-Key':f'checkout-{ident}-001'})
        db.commit();return headers

def payload(reference='order-001'):
    return {'order_reference':reference,'amount':10000,'currency':'INR','description':'Simulated checkout','expires_at':(datetime.now(timezone.utc)+timedelta(minutes=12)).isoformat()}

def test_two_merchants_voice_pin_settlement_and_fulfillment(client,factory):
    headers=merchants(factory);ids=[]
    for h in headers:
        response=client.post('/api/merchant/v1/checkout-requests',headers=h,json=payload())
        assert response.status_code==200,response.text
        ids.append(response.json()['payment_request_id'])
    # Owner authentication is not a substitute for a merchant's credentials.
    assert client.get(f'/api/merchant/v1/checkout-requests/{ids[0]}',headers=headers[1]).status_code==404
    assert client.get(f'/api/merchant/v1/checkout-requests/{ids[0]}',headers={**headers[0],'X-Merchant-Key':'wrong'}).status_code==401
    assert client.post('/api/merchant/v1/orders/order-001/fulfillment',headers=headers[0]).status_code==409
    with factory() as db:schedule(db);db.commit()
    assert {i['payment_id'] for i in client.get('/api/notifications').json()['items']}==set(ids)
    turn=client.post('/api/assistant/turn',json={'text':'Pay my railway and food requests'}).json()
    ident=turn['action_preview']['batch_id']
    review=client.get(f'/api/payment-batches/{ident}').json()
    assert {i['id'] for i in review['items']}==set(ids)
    token=client.post(f'/api/payment-batches/{ident}/authorize',json={'pin':'123456'}).json()['approval_token']
    for _ in range(2):
        result=client.post(f'/api/payment-batches/{ident}/confirm',json={'approval_token':token})
        assert result.status_code==200 and result.json()['status']=='SUCCEEDED',result.text
    for h in headers:
        order=client.get('/api/merchant/v1/orders/order-001',headers=h).json()
        assert order['order_status']=='PAYMENT_CONFIRMED' and not order['fulfilled_at']
        assert client.post('/api/merchant/v1/orders/order-001/fulfillment',headers=h).json()['order_status']=='FULFILLED'
    with factory() as db:assert balances(db,wallet(db))['posted_balance']==980000

def test_replay_conflict_expiry_and_durable_session(client,factory):
    h=merchants(factory)[0];data=payload()
    first=client.post('/api/merchant/v1/checkout-requests',headers=h,json=data).json()
    assert client.post('/api/merchant/v1/checkout-requests',headers=h,json=data).json()==first
    assert client.post('/api/merchant/v1/checkout-requests',headers=h,json={**data,'amount':20000}).status_code==409
    assert client.post('/api/merchant/v1/checkout-requests',headers={**h,'Idempotency-Key':'different-key'},json=data).status_code==409
    for expiry in ['2020-01-01T00:00:00Z','2099-01-01T00:00:00Z','2026-12-01T00:00:00']:
        assert client.post('/api/merchant/v1/checkout-requests',headers={**h,'Idempotency-Key':'new-order-key'},json={**data,'order_reference':'new-order','expires_at':expiry}).status_code==422
    with factory() as fresh:
        order=fresh.scalar(select(MerchantOrder));assert order.payment_request_id==first['payment_request_id']

def test_global_autopay_needs_pin_mandate_and_rechecks_revocation(factory,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'demo_merchant_name','Demo Railway') # Explicit legacy-only fixture.
    with factory() as db:
        p=PaymentRequest(merchant='Demo Railway',category='travel',description='Ticket',amount=10000,verified=True,provider='MERCHANT:rail',expires_at=datetime.now(timezone.utc)+timedelta(minutes=10));db.add(p);db.flush()
        with pytest.raises(FinancialError,match='MANDATE_REQUIRED'):reserve(db,p,'auto-unauthorized','auto')
        expiry=datetime.now(timezone.utc)+timedelta(days=1)
        details={'merchant':p.merchant,'daily_limit':20000,'expires_at':int(expiry.timestamp())}
        c=create_challenge(db,'MANDATE',10000,p.merchant,details);token=verify_challenge(db,c.id,'123456');db.flush();consume_approval(db,token,'MANDATE',10000,p.merchant,details)
        mandate=SpendingMandate(merchant=p.merchant,max_amount=10000,daily_limit=20000,expires_at=expiry);db.add(mandate);db.flush()
        a=reserve(db,p,'auto-authorized','auto');assert reserve(db,p,'auto-authorized','auto').id==a.id
        assert mandate.spent_today==10000
        mandate.status='REVOKED';db.flush()
        q=PaymentRequest(merchant=p.merchant,category='travel',description='Ticket',amount=10000,verified=True,provider=p.provider);db.add(q);db.flush()
        with pytest.raises(FinancialError,match='MANDATE_REQUIRED'):reserve(db,q,'auto-revoked','auto')

def test_reenable_reminders_preserves_delivery_and_stops_paid(factory):
    with factory() as db:
        p=PaymentRequest(merchant='Reminder',category='demo',description='Reminder',amount=100,expires_at=datetime.now(timezone.utc)+timedelta(minutes=10));db.add(p);db.flush()
        schedule(db);prefs=preferences(db);prefs.enabled=False;schedule(db)
        rows=list(db.scalars(select(PaymentReminder)));assert all(r.status=='CANCELLED' for r in rows)
        rows[0].deliveries={'device':True};prefs.enabled=True;schedule(db);schedule(db)
        assert len(list(db.scalars(select(PaymentReminder))))==2
        assert all(r.status=='PENDING' for r in rows) and rows[0].deliveries=={'device':True}
        p.status='SUCCEEDED';schedule(db);assert all(r.status=='CANCELLED' for r in rows)

def test_acknowledgement_replaces_snapshot_without_verification(client,factory):
    with factory() as db:
        p=PaymentRequest(merchant='Unknown',category='demo',description='Unknown',amount=10000,verified=False);db.add(p);db.commit();ident=p.id
    old=client.post('/api/payment-batches',json={'payment_ids':[ident]}).json()
    assert not old['can_authorize']
    new=client.post(f"/api/payment-batches/{old['id']}/acknowledge",json={'payment_id':ident}).json()
    assert new['id']!=old['id'] and new['snapshot_hash']!=old['snapshot_hash'] and new['can_authorize']
    assert not new['items'][0]['verified']
    assert client.post(f"/api/payment-batches/{old['id']}/authorize",json={'pin':'123456'}).status_code==409

@pytest.mark.parametrize('state',['expired','daily','forged'])
def test_automatic_mandate_expiry_allowance_and_missing_pin_evidence(factory,state):
    with factory() as db:
        expiry=datetime.now(timezone.utc)+timedelta(days=-1 if state=='expired' else 1)
        details={'merchant':'Demo Railway','daily_limit':10000,'expires_at':int(expiry.timestamp())}
        if state!='forged':
            c=create_challenge(db,'MANDATE',10000,'Demo Railway',details);token=verify_challenge(db,c.id,'123456');db.flush();consume_approval(db,token,'MANDATE',10000,'Demo Railway',details)
        from zoneinfo import ZoneInfo
        from app.core import settings
        today=datetime.now(ZoneInfo(settings().app_timezone)).date().isoformat()
        db.add(SpendingMandate(merchant='Demo Railway',max_amount=10000,daily_limit=10000,spent_today=10000 if state=='daily' else 0,context={'usage_date':today},expires_at=expiry))
        p=PaymentRequest(merchant='Demo Railway',category='travel',description='Ticket',amount=10000,verified=True,provider='MERCHANT:rail');db.add(p);db.flush()
        with pytest.raises(FinancialError,match='MANDATE_REQUIRED'):reserve(db,p,'invalid-mandate','auto')

def test_expired_cancelled_and_unpaid_orders_cannot_be_fulfilled(client,factory):
    h=merchants(factory)[0]
    created=client.post('/api/merchant/v1/checkout-requests',headers=h,json=payload()).json()
    cancelled=client.post('/api/merchant/v1/orders/order-001/cancel',headers=h)
    assert cancelled.status_code==200 and cancelled.json()['payment_status']=='CANCELLED'
    assert client.post('/api/merchant/v1/orders/order-001/fulfillment',headers=h).status_code==409
    with factory() as db:
        p=db.get(PaymentRequest,created['payment_request_id']);p.status='PENDING';p.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.get('/api/merchant/v1/orders/order-001',headers=h).json()['order_status']=='EXPIRED'
    batch=client.post('/api/payment-batches',json={'payment_ids':[created['payment_request_id']]}).json()
    assert not batch['can_authorize'] and 'EXPIRED' in batch['items'][0]['reason_codes']

def test_order_questions_and_remind_later_use_backend_facts(client,factory):
    h=merchants(factory)[0]
    created=client.post('/api/merchant/v1/checkout-requests',headers=h,json=payload()).json()
    answer=client.post('/api/assistant/turn',json={'text':'Did my railway payment succeed?'}).json()
    assert answer['provider']=='context-resolver' and not answer['action_preview']
    assert 'PENDING_PAYMENT' in answer['response'] and 'fulfillment' in answer['response']
    ident=answer['conversation_id']
    sender=client.post('/api/assistant/turn',json={'text':'Who sent this request?','conversation_id':ident}).json()
    assert 'Demo Railway' in sender['response']
    snoozed=client.post('/api/assistant/turn',json={'text':'Remind me later','conversation_id':ident}).json()
    assert not snoozed['action_preview'] and 'no payment was authorized' in snoozed['response']
    with factory() as db:
        assert db.get(PaymentRequest,created['payment_request_id']).status=='PENDING'
        assert db.scalar(select(func.count()).select_from(PaymentReminder))==2

def test_public_legacy_placeholder_cannot_impersonate_merchant(client,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'demo_merchant_api_key','change-this-demo-merchant-key')
    response=client.post('/api/merchant/checkout',headers={'X-Merchant-Key':'change-this-demo-merchant-key'},json={'merchant':settings().demo_merchant_name,'order_reference':'public-spoof','amount':10000})
    assert response.status_code==401

def test_worker_releases_legacy_automatic_reservation_without_authority(factory):
    from app.maintenance import tick
    from app.models import PaymentAttempt
    with factory() as db:
        p=PaymentRequest(merchant='Legacy Rail',category='travel',description='Ticket',amount=10000,verified=True);db.add(p);db.flush()
        # Reproduce a pre-V2 global-switch claim, without granting a mandate.
        a=reserve(db,p,'auto:'+p.id,'manual');db.commit();ident=a.id
    tick()
    with factory() as db:
        assert db.get(PaymentAttempt,ident).failure_reason=='AUTOPAY_AUTHORITY_UNAVAILABLE'
        assert balances(db,wallet(db))['posted_balance']==1_000_000
        assert balances(db,wallet(db))['reserved_amount']==0

def test_worker_executes_pin_authorized_mandate_once(factory,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'demo_merchant_name','Demo Railway') # Explicit legacy-only fixture.
    from app.maintenance import tick
    expiry=datetime.now(timezone.utc)+timedelta(days=1)
    details={'merchant':'Demo Railway','daily_limit':20000,'expires_at':int(expiry.timestamp())}
    with factory() as db:
        c=create_challenge(db,'MANDATE',10000,'Demo Railway',details);token=verify_challenge(db,c.id,'123456');db.flush();consume_approval(db,token,'MANDATE',10000,'Demo Railway',details)
        db.add(SpendingMandate(merchant='Demo Railway',max_amount=10000,daily_limit=20000,expires_at=expiry))
        p=PaymentRequest(merchant='Demo Railway',category='travel',description='Ticket',amount=10000,verified=True,provider='MERCHANT:rail');db.add(p);db.commit();ident=p.id
    tick();tick()
    with factory() as db:
        assert db.get(PaymentRequest,ident).status=='SUCCEEDED'
        assert db.scalar(select(SpendingMandate)).spent_today==10000
        assert balances(db,wallet(db))['posted_balance']==990000
