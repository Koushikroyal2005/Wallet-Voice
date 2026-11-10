"""Additional races run only against the existing isolated PostgreSQL test URL."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import threading
import pytest
from sqlalchemy import select, func, text
from test_postgres_financial import factory, fund
from app.models import (AutoPaySettings, AuthorizationChallenge, JournalTransaction, Operation,
    PaymentAttempt, PaymentRequest, SpendingMandate, WalletSecurity)
from app.services import FinancialError, balances, reserve, topup_or_withdraw, wallet
from app.authorization import create_challenge, verify_challenge, consume_approval, AuthorizationError, security_for
from app.core import settings
from app.main import Batch, MerchantCheckout, confirm, merchant_checkout
from app.paypal import create_order, PayPalError

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')


@pytest.fixture(autouse=True)
def isolated_executors(factory,monkeypatch):
    for module in ['app.main','app.execution','app.maintenance']:monkeypatch.setattr(f'{module}.SessionLocal',factory)


def parallel(*actions):
    barrier=threading.Barrier(len(actions))
    def invoke(action):barrier.wait(timeout=10);return action()
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures=[pool.submit(invoke,action) for action in actions]
        return [future.result(timeout=30) for future in futures]


def setup_payment(factory,amount=100000):
    fund(factory,400000)
    with factory() as db:
        db.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0,daily_limit=500000))
        p=PaymentRequest(merchant='Indian Railways',category='travel',description='Ticket',amount=amount,verified=True);db.add(p);db.commit();return p.id


def test_duplicate_batch_confirmation_executes_one_journal(factory):
    pid=setup_payment(factory)
    from app.payment_batches import create_batch,authorize,execute_batch
    from app.execution import execute_attempt
    with factory() as db:
        batch=create_batch(db,[pid]);token=authorize(db,batch,'123456');db.commit();ident=batch.id
    def run():
        return execute_batch(factory,ident,token,execute_attempt)
    parallel(run,run)
    with factory() as db:
        assert db.scalar(select(func.count(Operation.id)).where(Operation.kind=='PAYMENT'))==1
        assert balances(db,wallet(db))['available_balance']==300000


def test_duplicate_pin_verification_and_consumption_are_single_use(factory):
    fund(factory)
    with factory() as db:
        security_for(db);c=create_challenge(db,'TOPUP',10000);db.commit();ident=c.id
    def approve():
        with factory() as db:
            try:token=verify_challenge(db,ident,'123456');db.commit();return token
            except AuthorizationError:db.rollback();return None
    tokens=parallel(approve,approve)
    assert sum(bool(token) for token in tokens)==1
    token=next(token for token in tokens if token)
    def consume():
        with factory() as db:
            try:consume_approval(db,token,'TOPUP',10000);db.commit();return True
            except AuthorizationError:db.rollback();return False
    assert sorted(parallel(consume,consume))==[False,True]


def test_concurrent_merchant_permissions_respect_daily_allowance(factory):
    fund(factory,1_000_000)
    with factory() as db:
        db.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0))
        db.add(SpendingMandate(merchant=settings().demo_merchant_name,max_amount=150000,daily_limit=150000,expires_at=datetime.now(timezone.utc)+timedelta(days=1)));db.commit()
    def checkout(ref):
        with factory() as db:return merchant_checkout(MerchantCheckout(merchant=settings().demo_merchant_name,order_reference=ref,amount=125000),settings().demo_merchant_api_key,db)
    outcomes=parallel(lambda:checkout('DEMO-one'),lambda:checkout('DEMO-two'))
    assert sorted(item['status'] for item in outcomes)==['AWAITING_USER_APPROVAL','SUCCEEDED']
    with factory() as db:
        assert db.scalar(select(SpendingMandate)).spent_today==125000
        assert balances(db,wallet(db))['posted_balance']==875000


def test_paypal_claim_and_internal_reservation_cannot_both_win(factory,monkeypatch):
    pid=setup_payment(factory)
    async def provider(*args,**kwargs):return {'id':'MOCK-ORDER','status':'CREATED'}
    monkeypatch.setattr('app.paypal.request',provider)
    def internal():
        with factory() as db:
            try:reserve(db,db.get(PaymentRequest,pid),'internal-race','manual');db.commit();return True
            except FinancialError:db.rollback();return False
    def external():
        with factory() as db:
            try:asyncio.run(create_order(db,pid));return True
            except PayPalError:db.rollback();return False
    assert sorted(parallel(internal,external))==[False,True]
    with factory() as db:assert db.scalar(select(func.count(PaymentAttempt.id)))==1


def test_mixed_operations_keep_available_balance_nonnegative(factory):
    pid=setup_payment(factory,300000)
    def withdraw(key):
        with factory() as db:
            try:topup_or_withdraw(db,250000,'WITHDRAWAL',key);db.commit();return True
            except FinancialError:db.rollback();return False
    def pay():
        with factory() as db:
            try:reserve(db,db.get(PaymentRequest,pid),'mixed-payment','manual');db.commit();return True
            except FinancialError:db.rollback();return False
    results=parallel(lambda:withdraw('mixed-one'),lambda:withdraw('mixed-two'),pay)
    assert sum(results)==1
    with factory() as db:assert balances(db,wallet(db))['available_balance']>=0
