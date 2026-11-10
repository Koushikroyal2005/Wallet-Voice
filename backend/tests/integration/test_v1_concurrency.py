"""V1 races: independent real PostgreSQL sessions in fresh schemas."""
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from sqlalchemy import select,func
from test_paypal_lifecycle import isolated
from app.payment_batches import create_batch,authorize,execute_batch
from app.execution import execute_attempt
from app.services import topup_or_withdraw,balances,wallet,FinancialError
from app.models import PaymentAttempt,JournalTransaction,AutoPaySettings
pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')

def test_concurrent_credits_respect_aggregate_ceiling(isolated):
    factory,_=isolated
    barrier=threading.Barrier(2)
    def credit(key):
        with factory() as db:
            barrier.wait(timeout=10)
            try:topup_or_withdraw(db,6_000_000,'TOPUP',key);db.commit();return 'credited'
            except FinancialError:db.rollback();return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(credit,['credit-one','credit-two']))
    assert sorted(results)==['blocked','credited']
    with factory() as db:assert balances(db,wallet(db))['posted_balance']==7_000_000

def test_competing_exact_batches_claim_one_payment(isolated,monkeypatch):
    factory,pid=isolated
    monkeypatch.setattr('app.execution.SessionLocal',factory)
    approvals=[]
    with factory() as db:
        db.add(AutoPaySettings(enabled=False,minimum_balance=0));db.commit()
        for _ in range(2):
            b=create_batch(db,[pid],True);token=authorize(db,b,'123456');db.commit();approvals.append((b.id,token))
    barrier=threading.Barrier(2)
    def pay(approval):
        barrier.wait(timeout=10)
        try:execute_batch(factory,*approval,execute_attempt);return 'submitted'
        except FinancialError:return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(pay,approvals))
    assert sorted(results)==['blocked','submitted']
    with factory() as db:
        assert db.scalar(select(func.count(PaymentAttempt.id)))==1
        assert db.scalar(select(func.count(JournalTransaction.id)))==2
        assert balances(db,wallet(db))['available_balance']==875000
