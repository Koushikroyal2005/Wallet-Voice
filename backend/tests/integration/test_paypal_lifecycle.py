"""PayPal races in fresh schemas; no reset, truncate or development DB access."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import uuid
import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app import paypal
from app.models import PaymentRequest, PaymentAttempt, PayPalOrder, PayPalWebhookEvent, PaymentReservation, JournalTransaction
from app.services import balances, wallet, topup_or_withdraw

URL=os.getenv('TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not URL,reason='requires isolated PostgreSQL test database')


@pytest.fixture
def isolated():
    target=make_url(URL)
    if target.database!='aiwallet_test' or target.host!='test-db':pytest.fail('Only aiwallet_test@test-db is permitted')
    schema='paypal_test_'+uuid.uuid4().hex
    admin=create_engine(URL)
    with admin.begin() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    admin.dispose()
    engine=create_engine(URL,connect_args={'options':f'-csearch_path={schema}'})
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
    with factory() as db:
        topup_or_withdraw(db,1000000,'TOPUP','initial')
        p=PaymentRequest(merchant='Rail',category='travel',description='Ticket',amount=125000)
        db.add(p);db.commit();pid=p.id
    yield factory,pid
    engine.dispose()
    # Schema is deliberately retained in the disposable test-db tmpfs. No DROP.


def race(*actions):
    barrier=threading.Barrier(len(actions))
    def invoke(action):barrier.wait(timeout=10);return action()
    with ThreadPoolExecutor(max_workers=len(actions)) as executor:
        futures=[executor.submit(invoke,action) for action in actions]
        return [future.result(timeout=30) for future in futures]


def test_concurrent_create_and_capture_keep_one_external_result(isolated,monkeypatch):
    factory,pid=isolated;calls=[];lock=threading.Lock()
    async def provider(method,path,**kwargs):
        with lock:calls.append((path,kwargs.get('request_id')))
        if path.endswith('/capture'):
            return {'id':'PG-ORDER','purchase_units':[{'payments':{'captures':[{'id':'PG-CAPTURE','status':'COMPLETED','amount':{'value':'14.88','currency_code':'USD'}}]}}]}
        return {'id':'PG-ORDER','status':'CREATED'}
    monkeypatch.setattr(paypal,'request',provider)
    def create():
        with factory() as db:return asyncio.run(paypal.create_order(db,pid))
    assert {result['order_id'] for result in race(create,create)}=={'PG-ORDER'}
    def capture():
        with factory() as db:return asyncio.run(paypal.capture_order(db,'PG-ORDER'))
    assert {result['status'] for result in race(capture,capture)}=={'COMPLETED'}
    assert len({key for path,key in calls if path.endswith('/capture')})==1
    with factory() as db:
        assert db.scalar(select(func.count(PayPalOrder.id)))==1
        assert db.scalar(select(func.count(PaymentAttempt.id)))==1
        assert db.scalar(select(func.count(PaymentReservation.id)))==0
        assert db.scalar(select(func.count(JournalTransaction.id)))==1  # opening funding only
        assert balances(db,wallet(db))=={'posted_balance':1000000,'reserved_amount':0,'available_balance':1000000}


def test_concurrent_duplicate_webhook_is_recorded_once(isolated,monkeypatch):
    factory,pid=isolated
    async def provider(*args,**kwargs):return {'id':'PG-ORDER','status':'CREATED'}
    monkeypatch.setattr(paypal,'request',provider)
    with factory() as db:asyncio.run(paypal.create_order(db,pid))
    event={'id':'PG-EVENT','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{'id':'PG-CAPTURE','amount':{'value':'14.88','currency_code':'USD'},'supplementary_data':{'related_ids':{'order_id':'PG-ORDER'}}}}
    def deliver():
        with factory() as db:paypal.apply_webhook(db,event)
    race(deliver,deliver)
    with factory() as db:
        assert db.scalar(select(func.count(PayPalWebhookEvent.id)))==1
        assert db.get(PaymentRequest,pid).status=='SUCCEEDED'
        assert balances(db,wallet(db))['posted_balance']==1000000
