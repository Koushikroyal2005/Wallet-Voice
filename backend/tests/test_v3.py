"""V3 facts, identity authority and exact-review regression tests. No live providers."""
from datetime import datetime,timedelta,timezone
import io,json
import pytest
from sqlalchemy import select,func
from test_product_flows import factory
from test_http_contracts import client
from test_merchants_v2 import merchants,payload
from app.models import PaymentRequest,SpendingMandate,MerchantIdentity,AttentionState,PaymentReminder,AuthorizationChallenge
from app.authorization import create_challenge,verify_challenge
from app.services import reserve,FinancialError,wallet,balances
from app.reminders import schedule
from app import payment_batches as batches
from app.execution import execute_attempt

def order(client,headers,reference='order-001'):
    data=payload(reference)
    r=client.post('/api/merchant/v1/checkout-requests',headers={**headers,'Idempotency-Key':'key-'+reference},json=data)
    assert r.status_code==200,r.text
    return r.json()['payment_request_id']

def grant(client,factory,merchant='rail',name='Demo Railway',daily=20000):
    expiry=datetime.now(timezone.utc)+timedelta(days=1)
    details={'merchant':name,'merchant_id':merchant,'daily_limit':daily,'expires_at':int(expiry.timestamp())}
    with factory() as db:
        c=create_challenge(db,'MANDATE',10000,merchant,details);token=verify_challenge(db,c.id,'123456');db.commit()
    r=client.post('/api/mandates',json={'merchant':name,'merchant_id':merchant,'max_amount':10000,'daily_limit':daily,'expires_at':expiry.isoformat(),'approval_token':token})
    assert r.status_code==200,r.text
    return r.json()['id']

def test_payment_memory_independent_of_alerts_and_nonfinancial_controls(client,factory):
    header=merchants(factory)[0];ident=order(client,header)
    with factory() as db:schedule(db);db.commit();original=db.get(PaymentRequest,ident).expires_at
    assert client.patch('/api/notifications/preferences',json={'enabled':False}).status_code==200
    assert client.get('/api/notifications').json()['items'][0]['payment_id']==ident
    assert client.post(f'/api/notifications/attention/{ident}',json={'action':'SNOOZE'}).status_code==200
    assert client.get('/api/notifications').json()['items'][0]['snoozed_until']
    client.post(f'/api/notifications/attention/{ident}',json={'action':'DISMISS'})
    data=client.get('/api/notifications').json();assert not data['items'] and data['dismissed_items'][0]['payment_id']==ident
    client.post(f'/api/notifications/attention/{ident}',json={'action':'RESTORE'})
    assert client.get('/api/notifications').json()['items'][0]['payment_id']==ident
    with factory() as db:
        p=db.get(PaymentRequest,ident);assert p.expires_at==original and p.status=='PENDING'
        p.status='CANCELLED';db.commit()
    assert client.get('/api/notifications').json()['items']==[]

def test_attention_priorities_expiry_and_reenable_no_duplicate(client,factory):
    h=merchants(factory)[0];ident=order(client,h)
    with factory() as db:
        schedule(db);db.commit();assert db.scalar(select(func.count()).select_from(PaymentReminder))==1
    for enabled in [False,True,False,True]:
        client.patch('/api/notifications/preferences',json={'enabled':enabled})
        with factory() as db:schedule(db);db.commit()
    assert client.get('/api/notifications').json()['items'][0]['stage']=='URGENT'
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PaymentReminder))==1
        p=db.get(PaymentRequest,ident);p.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.get('/api/notifications').json()['items'][0]['stage']=='EXPIRED'
    b=client.post('/api/payment-batches',json={'payment_ids':[ident]}).json();assert not b['can_authorize']

def test_stable_mandate_rejects_identity_mismatch_revocation_and_rename(client,factory):
    h=merchants(factory)[0];ident=order(client,h);grant(client,factory)
    with factory() as db:
        p=db.get(PaymentRequest,ident)
        # Same display name, wrong ID: no automatic authority.
        p.trace={**p.trace,'merchant_id':'different'}
        with pytest.raises(FinancialError,match='MERCHANT_IDENTITY_UNAVAILABLE'):reserve(db,p,'wrong-id','auto')
        p.trace={**p.trace,'merchant_id':'rail'};db.get(MerchantIdentity,'rail').active=False;db.flush()
        with pytest.raises(FinancialError,match='MERCHANT_IDENTITY_UNAVAILABLE'):reserve(db,p,'revoked-id','auto')
        identity=db.get(MerchantIdentity,'rail');identity.active=True;identity.name='Renamed Railway';db.flush()
        with pytest.raises(FinancialError,match='MERCHANT_IDENTITY_UNAVAILABLE'):reserve(db,p,'renamed-id','auto')
        db.add(MerchantIdentity(id='collision',name='Demo Railway',secret_hash='0'*64));p.trace={**p.trace,'merchant_id':'collision'};p.provider='MERCHANT:collision';db.flush()
        with pytest.raises(FinancialError,match='MERCHANT_IDENTITY_UNAVAILABLE'):reserve(db,p,'name-collision','auto')

def test_identity_bound_mandate_and_replayed_approval(client,factory):
    h=merchants(factory)[0];ident=order(client,h);mandate=grant(client,factory)
    with factory() as db:
        p=db.get(PaymentRequest,ident);a=reserve(db,p,'auto:'+ident,'auto');db.commit();attempt=a.id
    assert execute_attempt(attempt).status=='SUCCEEDED'
    with factory() as db:
        assert db.get(SpendingMandate,mandate).merchant_id=='rail'
        assert db.get(SpendingMandate,mandate).spent_today==10000
        assert balances(db,wallet(db))['posted_balance']==990000
    assert client.post('/api/mandates',json={'merchant':'Demo Railway','max_amount':10000,'daily_limit':20000,'expires_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'approval_token':'synthetic-not-valid-token'}).status_code==422

def test_legacy_name_permission_cannot_authorize_versioned_identity(client,factory,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'demo_merchant_name','Demo Railway')
    h=merchants(factory)[0];ident=order(client,h)
    expiry=datetime.now(timezone.utc)+timedelta(days=1)
    with factory() as db:
        c=create_challenge(db,'MANDATE',10000,'Demo Railway',{'merchant':'Demo Railway','daily_limit':20000,'expires_at':int(expiry.timestamp())})
        token=verify_challenge(db,c.id,'123456');db.commit()
    r=client.post('/api/mandates',json={'merchant':'Demo Railway','legacy_demo':True,'max_amount':10000,'daily_limit':20000,'expires_at':expiry.isoformat(),'approval_token':token});assert r.status_code==200
    with factory() as db:
        with pytest.raises(FinancialError,match='MANDATE_REQUIRED'):reserve(db,db.get(PaymentRequest,ident),'legacy-collision','auto')

def test_conversation_correction_invalidates_pin_and_supports_readd(client,factory):
    headers=merchants(factory);ids=[order(client,h) for h in headers]
    def say(text,conversation=None):
        r=client.post('/api/assistant/turn',json={'text':text,**({'conversation_id':conversation} if conversation else {})});assert r.status_code==200,r.text;return r.json()
    first=say('Pay my railway and food orders');conversation=first['conversation_id'];old=first['action_preview']['batch_id']
    token=client.post(f'/api/payment-batches/{old}/authorize',json={'pin':'123456'}).json()['approval_token']
    only=say('Actually, just the railway.',conversation);new=only['action_preview']['batch_id'];assert new!=old
    assert client.post(f'/api/payment-batches/{old}/confirm',json={'approval_token':token}).status_code==409
    added=say('Add the food order',conversation)['action_preview']['batch_id'];assert len(client.get(f'/api/payment-batches/{added}').json()['items'])==2
    removed=say('Remove the second payment',conversation)['action_preview']['batch_id'];assert len(client.get(f'/api/payment-batches/{removed}').json()['items'])==1
    assert not say('Cancel this review',conversation)['action_preview']
    assert client.get(f'/api/payment-batches/{removed}').json()['status']=='CANCELLED'

def test_unknown_outcome_stays_processing_until_reconciled(factory,monkeypatch):
    from app.providers import DemoPaymentProvider,ProviderResult
    original=DemoPaymentProvider.execute
    with factory() as db:
        p=PaymentRequest(merchant='Simulated',category='demo',description='test',amount=10000,verified=True);db.add(p);db.flush()
        b=batches.create_batch(db,[p.id]);token=batches.authorize(db,b,'123456');db.commit();ident=b.id
    monkeypatch.setattr(DemoPaymentProvider,'execute',lambda *args:ProviderResult(None,''))
    uncertain=batches.execute_batch(factory,ident,token,execute_attempt);assert uncertain['status']=='PROCESSING' and not uncertain['items'][0]['receipt']
    monkeypatch.setattr(DemoPaymentProvider,'execute',original)
    settled=batches.execute_batch(factory,ident,token,execute_attempt);assert settled['status']=='SUCCEEDED'
    assert settled['items'][0]['receipt']['journal_id']

def test_lifecycle_logs_are_committed_and_allowlisted(factory,monkeypatch):
    import logging
    from app.audit import logger
    from app.services import emit
    output=io.StringIO();handler=logging.StreamHandler(output);monkeypatch.setattr(logger,'handlers',[handler])
    with factory() as db:
        emit(db,'test.lifecycle',{'payment_id':'request-1','pin':'private-pin','approval_token':'private-token','speech':'private speech'});db.commit()
        emit(db,'test.rollback',{'payment_id':'rolled-back'});db.rollback()
    value=output.getvalue();assert 'request-1' in value and 'private' not in value and 'rolled-back' not in value

def test_ticket_deadline_question_excludes_earlier_food_checkout(client,factory):
    headers=merchants(factory)
    ids=[order(client,h) for h in headers]
    with factory() as db:db.get(PaymentRequest,ids[0]).description='train ticket';db.get(PaymentRequest,ids[1]).expires_at=datetime.now(timezone.utc)+timedelta(minutes=1);db.commit()
    answer=client.post('/api/assistant/turn',json={'text':'Which ticket expires first?'}).json()
    assert answer['data'][0]['id']==ids[0] and not answer['action_preview']

def test_batch_snapshot_binds_merchant_identity(client,factory):
    h=merchants(factory)[0];ident=order(client,h)
    b=client.post('/api/payment-batches',json={'payment_ids':[ident]}).json()
    assert b['items'][0]['merchant_id']=='rail'
    with factory() as db:
        p=db.get(PaymentRequest,ident);p.trace={**p.trace,'merchant_id':'different'};db.commit()
    assert client.post(f"/api/payment-batches/{b['id']}/authorize",json={'pin':'123456'}).status_code==409
