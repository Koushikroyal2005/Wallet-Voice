"""Fresh isolated PostgreSQL schema; no resets or real provider calls."""
import os
import pytest
from concurrent.futures import ThreadPoolExecutor
from test_paypal_lifecycle import isolated
from app.main import payment_review, do_payment, Pay
from app.payment_batches import create_batch,authorize
from app.models import PaymentRequest, PaymentAttempt, PaymentReservation
from app.services import FinancialError, reserve, balances, wallet
from sqlalchemy import select, func

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')

def test_currency_mismatch_never_reserves_postgres_funds(isolated):
    factory,pid=isolated
    with factory() as db:
        payment=db.get(PaymentRequest,pid)
        payment.currency='USD'
        db.commit()
        with pytest.raises(FinancialError):
            reserve(db,payment,'currency-mismatch','manual',True)
        db.rollback()
        assert balances(db,wallet(db))['available_balance']==1000000
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0
        assert db.scalar(select(func.count(PaymentReservation.id)))==0

def test_guardian_read_only_and_duplicate_wallet_confirmation(isolated,monkeypatch):
    factory,pid=isolated
    for module in ['app.main','app.execution']:monkeypatch.setattr(f'{module}.SessionLocal',factory)
    with factory() as db:
        first=payment_review(pid,db)
        assert first['wallet_policy']['decision']=='MANUAL_CONFIRMATION_REQUIRED' and first['receipt'] is None
        b=create_batch(db,[pid],True);token=authorize(db,b,'123456');db.commit();ident=b.id
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:do_payment(pid,Pay(batch_id=ident,approval_token=token,idempotency_key='guardian-pg-duplicate',confirm_unknown_merchant=True)),range(2)))
    assert results[0]['id']==results[1]['id'] and results[0]['status']=='SUCCEEDED'
    with factory() as db:
        result=payment_review(pid,db)
        assert result['receipt']['journal_id'] and result['receipt']['status']=='SUCCEEDED'
