"""V2 HTTP contracts and ingestion races on fresh isolated PostgreSQL schemas."""
import os
import sys
import threading
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from test_postgres_financial import factory,fund
from app.main import app
from app.db import get_db
from app.models import AutoPaySettings,MerchantOrder
from app.voice import demo_intent
from app.merchants import Checkout,create,authenticate
from test_merchants_v2 import merchants,payload
from test_merchants_v2 import test_two_merchants_voice_pin_settlement_and_fulfillment,test_replay_conflict_expiry_and_durable_session,test_global_autopay_needs_pin_mandate_and_rechecks_revocation
from test_merchants_v2 import test_worker_releases_legacy_automatic_reservation_without_authority,test_worker_executes_pin_authorized_mandate_once

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')

@pytest.fixture(autouse=True)
def configure(factory,monkeypatch):
    fund(factory,1_000_000)
    with factory() as db:db.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));db.commit()
    for module in ['app.main','app.execution','app.maintenance']:monkeypatch.setattr(f'{module}.SessionLocal',factory)

@pytest.fixture
def client(factory,monkeypatch):
    def database():
        with factory() as db:yield db
    async def parser(text,history):return demo_intent(text)
    app.dependency_overrides[get_db]=database;monkeypatch.setattr('app.main.nemotron_intent',parser)
    try:
        with TestClient(app) as client:yield client
    finally:app.dependency_overrides.clear()

def test_concurrent_ingestion_is_one_immutable_order(factory):
    header=merchants(factory)[0];data=Checkout(**payload())
    barrier=threading.Barrier(2)
    def submit(_):
        with factory() as db:
            identity=authenticate(header['X-Merchant-Id'],header['X-Merchant-Key'],db)
            barrier.wait(timeout=10)
            return create(data,identity,header['Idempotency-Key'],db)['payment_request_id']
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(submit,range(2)))
    assert len(set(ids))==1
    with factory() as db:assert db.scalar(select(func.count()).select_from(MerchantOrder))==1

def test_concurrent_automatic_mandate_reservations_and_duplicate(factory,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'demo_merchant_name','Demo Railway') # Legacy path only, no V2 identity.
    from app.models import SpendingMandate,PaymentRequest
    from app.authorization import create_challenge,verify_challenge,consume_approval
    from app.services import reserve,FinancialError
    expiry=datetime.now(timezone.utc)+timedelta(days=1)
    details={'merchant':'Demo Railway','daily_limit':150000,'expires_at':int(expiry.timestamp())}
    with factory() as db:
        c=create_challenge(db,'MANDATE',150000,'Demo Railway',details);token=verify_challenge(db,c.id,'123456');db.flush();consume_approval(db,token,'MANDATE',150000,'Demo Railway',details)
        db.add(SpendingMandate(merchant='Demo Railway',max_amount=150000,daily_limit=150000,expires_at=expiry))
        rows=[PaymentRequest(merchant='Demo Railway',category='travel',description='Ticket',amount=125000,verified=True,provider='MERCHANT:rail') for _ in range(2)];db.add_all(rows);db.commit();ids=[p.id for p in rows]
    barrier=threading.Barrier(2)
    def claim(ident):
        with factory() as db:
            p=db.get(PaymentRequest,ident);barrier.wait(timeout=10)
            try:
                a=reserve(db,p,'auto:'+ident,'auto');db.commit()
                assert reserve(db,p,'auto:'+ident,'auto').id==a.id
                return 'reserved'
            except FinancialError:db.rollback();return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(claim,ids))
    assert sorted(outcomes)==['blocked','reserved']
    with factory() as db:assert db.scalar(select(SpendingMandate)).spent_today==125000
