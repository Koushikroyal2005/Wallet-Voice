"""V1 financial and conversation assertions against real isolated SQLAlchemy DBs."""
import asyncio
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,func
from test_product_flows import factory
from test_http_contracts import client
from app.models import PaymentRequest,PaymentBatch,PaymentBatchItem,PaymentAttempt,PaymentReservation,JournalTransaction,AutoPaySettings,PaymentReminder,NotificationPreferences,PayPalOrder
from app.models import PushSubscription
from app.core import settings
from app import payment_batches as batches
from app.authorization import AuthorizationError
from app.services import FinancialError,balances,wallet,topup_or_withdraw
from app.execution import execute_attempt
from app.reminders import schedule,attention,quiet,deliver_one
from app.agentic import assistant_response
from app.voice import demo_intent,validate_tool_arguments

def requests(factory):
    with factory() as db:
        rows=[PaymentRequest(merchant=m,description=d,category=c,amount=a,verified=True,expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)) for m,d,c,a in [('Indian Railways','train ticket','travel',125000),('CinemaPass','movie tickets','entertainment',60000),('Demo Kitchen','food order','food',40000)]]
        db.add_all(rows);db.commit();return [p.id for p in rows]

def approve(factory,ids):
    with factory() as db:
        b=batches.create_batch(db,ids);token=batches.authorize(db,b,'123456');db.commit();return b.id,token

def test_exact_batch_partial_success_and_duplicate(factory):
    ids=requests(factory)
    with factory() as db:db.get(PaymentRequest,ids[1]).description='force-fail';db.commit()
    ident,token=approve(factory,ids[:2])
    result=batches.execute_batch(factory,ident,token,execute_attempt)
    assert result['status']=='PARTIAL'
    assert [p['status'] for p in result['items']]==['SUCCEEDED','FAILED']
    assert result['items'][0]['receipt']['journal_id']
    batches.execute_batch(factory,ident,token,execute_attempt)
    with factory() as db:
        assert balances(db,wallet(db))=={'posted_balance':875000,'reserved_amount':0,'available_balance':875000}
        assert db.get(PaymentRequest,ids[2]).status=='PENDING'

@pytest.mark.parametrize('change',['amount','merchant','currency','deadline','verified','source','total','items','expired','paid','held'])
def test_changed_or_expired_approval_never_reserves(factory,change):
    ids=requests(factory);ident,token=approve(factory,ids[:2])
    with factory() as db:
        p=db.get(PaymentRequest,ids[0]);b=db.get(PaymentBatch,ident)
        if change=='amount':p.amount+=1
        elif change=='merchant':p.merchant='Different recipient'
        elif change=='currency':p.currency='USD'
        elif change=='deadline':p.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        elif change=='verified':p.verified=False
        elif change=='source':b.source='PAYPAL_SANDBOX'
        elif change=='total':b.total+=1
        elif change=='items':b.snapshot={**b.snapshot,'items':b.snapshot['items'][:1]}
        elif change=='expired':b.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        elif change=='paid':p.status='SUCCEEDED'
        elif change=='held':p.explicit_hold=True
        db.commit()
    with pytest.raises((FinancialError,AuthorizationError)):batches.execute_batch(factory,ident,token,execute_attempt)
    with factory() as db:assert db.scalar(select(func.count(PaymentReservation.id)))==0

def test_approval_cannot_authorize_another_batch(factory):
    ids=requests(factory);ident,token=approve(factory,ids[:1]);other,_=approve(factory,ids[1:2])
    with pytest.raises(AuthorizationError):batches.execute_batch(factory,other,token,execute_attempt)

def test_correction_invalidates_previously_approved_snapshot(factory):
    from app.batch_voice import prepare
    ids=requests(factory);ident,token=approve(factory,ids[:2])
    with factory() as db:
        outcome=prepare(db,{'existing':ident,'remove':'movie'}, {'batch_id':ident});db.commit()
        assert outcome['preview']['batch_id']!=ident
    with pytest.raises(AuthorizationError,match='cancelled'):batches.execute_batch(factory,ident,token,execute_attempt)

def test_expiry_between_pin_and_confirmation_releases_no_money(factory):
    ids=requests(factory);ident,token=approve(factory,ids[:1])
    with factory() as db:
        db.get(PaymentRequest,ids[0]).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    with pytest.raises(FinancialError):batches.execute_batch(factory,ident,token,execute_attempt)
    with factory() as db:assert balances(db,wallet(db))['available_balance']==1000000

@pytest.mark.parametrize('limit',['balance','daily','per_payment','unknown'])
def test_no_silent_subset_for_blocked_item(factory,limit):
    ids=requests(factory)
    with factory() as db:
        settings=db.scalar(select(AutoPaySettings))
        if limit=='balance':topup_or_withdraw(db,900000,'WITHDRAWAL','spend-before-review')
        elif limit=='daily':settings.daily_limit=150000
        elif limit=='per_payment':settings.per_transaction_limit=100000
        else:db.get(PaymentRequest,ids[1]).verified=False
        db.commit();b=batches.create_batch(db,ids[:2]);assert not batches.view(db,b)['can_authorize']
        with pytest.raises(FinancialError):batches.authorize(db,b,'123456')
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0

def test_wallet_cap_and_idempotent_credit(factory):
    with factory() as db:
        topup_or_withdraw(db,9_000_000,'TOPUP','up-to-cap');db.commit()
        topup_or_withdraw(db,9_000_000,'TOPUP','up-to-cap');db.commit()
        assert balances(db,wallet(db))['posted_balance']==10_000_000
        with pytest.raises(FinancialError,match='maximum'):topup_or_withdraw(db,1,'TOPUP','over-cap')
        db.rollback();assert balances(db,wallet(db))['posted_balance']==10_000_000

def test_voice_selection_exclusion_correction_and_ordinals(factory):
    ids=requests(factory)
    async def turn(text,ident=None):
        async def parser(text,history):return demo_intent(text)
        with factory() as db:return await assistant_response(db,text,ident,None,parser)
    initial=asyncio.run(turn('Pay my train ticket and movie tickets, but leave the food order.'))
    cid=initial['conversation_id'];batch_id=initial['action_preview']['batch_id']
    with factory() as db:
        b=batches.get_batch(db,batch_id);assert [p['id'] for p in b.snapshot['items']]==ids[:2]
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0
    corrected=asyncio.run(turn('Remove the movie ticket.',cid))
    with factory() as db:assert [p['id'] for p in batches.get_batch(db,corrected['action_preview']['batch_id']).snapshot['items']]==ids[:1]
    cancel=asyncio.run(turn('cancel',cid));assert not cancel['action_preview']
    listing=asyncio.run(turn('show pending payments'))
    listed=[p['id'] for p in listing['data']]
    ordinal=asyncio.run(turn('Pay the first and third requests.',listing['conversation_id']))
    with factory() as db:assert [p['id'] for p in batches.get_batch(db,ordinal['action_preview']['batch_id']).snapshot['items']]==[listed[0],listed[2]]

def test_voice_multiple_matches_asks_instead_of_guessing(factory):
    ids=requests(factory)
    with factory() as db:
        db.add(PaymentRequest(merchant='Other Railways',description='train ticket',category='travel',amount=10000,verified=True));db.commit()
    async def run():
        with factory() as db:return await assistant_response(db,'Pay train and movie tickets',None,None,None)
    outcome=asyncio.run(run());assert not outcome['action_preview'] and 'matches' in outcome['response']

def test_batch_tool_rejects_injected_ids_and_amounts():
    with pytest.raises(ValueError):validate_tool_arguments('prepare_payment_batch',{'include':['train'],'amount':1,'payment_ids':['invented']})

def test_reminders_deduplicate_and_stop_after_payment(factory):
    ids=requests(factory)
    with factory() as db:
        schedule(db);db.commit();schedule(db);db.commit()
        assert db.scalar(select(func.count(PaymentReminder.id)))==3
        db.get(PaymentRequest,ids[0]).status='SUCCEEDED';db.commit();schedule(db);db.commit()
        assert all(p['payment_id']!=ids[0] for p in attention(db)['items'])
        assert all(r.status=='CANCELLED' for r in db.scalars(select(PaymentReminder).where(PaymentReminder.payment_request_id==ids[0])))

def test_quiet_hours_wrap_midnight():
    prefs=NotificationPreferences(quiet_start=22,quiet_end=8)
    assert quiet(prefs,datetime(2026,11,10,18,tzinfo=timezone.utc))
    assert not quiet(prefs,datetime(2026,11,10,10,tzinfo=timezone.utc))

def test_http_pin_required_and_real_backend_batch(client,factory):
    ids=requests(factory)
    assert client.post(f'/api/payments/{ids[0]}/pay',json={}).status_code==403
    b=client.post('/api/payment-batches',json={'payment_ids':ids[:2]}).json()
    bad=client.post(f"/api/payment-batches/{b['id']}/authorize",json={'pin':'000000'});assert bad.status_code==403
    auth=client.post(f"/api/payment-batches/{b['id']}/authorize",json={'pin':'123456'}).json()
    result=client.post(f"/api/payment-batches/{b['id']}/confirm",json=auth)
    assert result.status_code==200 and result.json()['status']=='SUCCEEDED'
    assert client.post(f"/api/payment-batches/{b['id']}/confirm",json=auth).json()['status']=='SUCCEEDED'

def test_push_retry_does_not_redeliver_to_successful_subscription(factory,monkeypatch):
    requests(factory)
    s=settings()
    for k,v in [('vapid_private_key','synthetic-test-key'),('vapid_public_key','synthetic-public-key'),('vapid_subject','mailto:test@example.invalid')]:monkeypatch.setattr(s,k,v)
    with factory() as db:
        schedule(db);prefs=db.get(NotificationPreferences,'demo-user');prefs.push_enabled=True;prefs.quiet_start=0;prefs.quiet_end=0
        db.add_all([PushSubscription(endpoint=f'https://fcm.googleapis.com/{n}',subscription={'endpoint':f'https://fcm.googleapis.com/{n}'}) for n in [1,2]])
        db.commit()
    calls=[]
    def sender(**kwargs):
        endpoint=kwargs['subscription_info']['endpoint'];calls.append(endpoint)
        if endpoint.endswith('/2') and calls.count(endpoint)==1:raise RuntimeError('synthetic network failure')
    assert deliver_one(factory,sender)
    with factory() as db:
        row=db.scalar(select(PaymentReminder).where(PaymentReminder.status=='RETRY'));assert row
        row.next_attempt_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        # Keep only this reminder dispatchable to test its exact retry.
        for other in db.scalars(select(PaymentReminder).where(PaymentReminder.id!=row.id)):other.status='CANCELLED'
        db.commit()
    assert deliver_one(factory,sender)
    assert calls.count('https://fcm.googleapis.com/1')==1
    assert calls.count('https://fcm.googleapis.com/2')==2

def test_no_push_after_payment_and_unsupported_endpoint_rejected(client,factory,monkeypatch):
    ids=requests(factory)
    s=settings()
    for k in ['vapid_private_key','vapid_public_key','vapid_subject']:monkeypatch.setattr(s,k,'synthetic-value')
    with factory() as db:
        schedule(db);prefs=db.get(NotificationPreferences,'demo-user');prefs.push_enabled=True;prefs.quiet_start=prefs.quiet_end=0
        db.add(PushSubscription(endpoint='https://fcm.googleapis.com/test',subscription={}))
        for ident in ids:db.get(PaymentRequest,ident).status='SUCCEEDED'
        db.commit()
    calls=[]
    for _ in range(6):deliver_one(factory,lambda **kwargs:calls.append(kwargs))
    assert not calls
    assert client.post('/api/notifications/subscriptions',json={'endpoint':'http://127.0.0.1/private','keys':{'auth':'x'*20,'p256dh':'y'*88}}).status_code==422
