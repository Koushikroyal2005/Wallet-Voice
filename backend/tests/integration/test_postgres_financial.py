"""Runs only in the isolated docker-compose.test.yml database."""
import os,threading
import pytest
from sqlalchemy import create_engine,select,func,text
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import AutoPaySettings,JournalTransaction,LedgerEntry,Operation,PaymentAttempt,PaymentRequest,PaymentReservation
from app.services import FinancialError,active_reserved,balances,emit,finalize,reserve,topup_or_withdraw,wallet

URL=os.getenv("TEST_DATABASE_URL")
pytestmark=pytest.mark.skipif(not URL,reason="requires isolated PostgreSQL test database")
@pytest.fixture()
def factory():
    from sqlalchemy.engine import make_url
    target=make_url(URL)
    if target.database!='aiwallet_test' or target.host!='test-db':pytest.fail('Refusing to reset any database except aiwallet_test@test-db')
    engine=create_engine(URL,isolation_level="READ COMMITTED")
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE app_events, payment_reservations, payment_attempts, payment_requests, ledger_entries, journal_transactions, operations, ledger_accounts, autopay_settings, wallets RESTART IDENTITY CASCADE"))
    return sessionmaker(bind=engine,expire_on_commit=False)
def fund(factory,amount=200000):
    with factory() as s:topup_or_withdraw(s,amount,"TOPUP","integration-fund");s.commit()
def test_concurrent_withdrawals_cannot_overspend(factory):
    fund(factory);results=[];barrier=threading.Barrier(2)
    def run(key):
        try:
            with factory() as s:barrier.wait();topup_or_withdraw(s,150000,"WITHDRAWAL",key);s.commit();results.append("ok")
        except FinancialError:results.append("blocked")
    threads=[threading.Thread(target=run,args=(f"withdraw-{n}",)) for n in range(2)]
    [t.start() for t in threads];[t.join() for t in threads]
    with factory() as s:assert results.count("ok")==1 and balances(s,wallet(s))["posted_balance"]==50000
def test_duplicate_key_creates_one_operation_and_journal(factory):
    results=[];barrier=threading.Barrier(2)
    def run():
        with factory() as s:barrier.wait();op=topup_or_withdraw(s,100000,"TOPUP","same-key");s.commit();results.append(op.id)
    ts=[threading.Thread(target=run) for _ in range(2)];[t.start() for t in ts];[t.join() for t in ts]
    with factory() as s:assert len(set(results))==1 and s.scalar(select(func.count(Operation.id)))==1 and s.scalar(select(func.count(JournalTransaction.id)))==1
def test_reconciliation_and_reservation(factory):
    fund(factory)
    with factory() as s:
        s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));p=PaymentRequest(merchant="Rail",category="travel",description="x",amount=125000,verified=True);s.add(p);s.flush();reserve(s,p,"reserve-key","auto");s.commit()
    with factory() as s:
        for journal in s.scalars(select(JournalTransaction)).all():
            rows=s.scalars(select(LedgerEntry).where(LedgerEntry.journal_transaction_id==journal.id)).all();assert sum(x.amount for x in rows if x.direction=="DEBIT")==sum(x.amount for x in rows if x.direction=="CREDIT")
        b=balances(s,wallet(s));assert b["posted_balance"]==200000 and b["available_balance"]==75000
def test_concurrent_merchant_reservations_cannot_overspend(factory):
    fund(factory);ids=[]
    with factory() as s:
        s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0,daily_limit=500000));s.add_all([PaymentRequest(merchant="A",category="x",description="x",amount=150000,verified=True),PaymentRequest(merchant="B",category="x",description="x",amount=150000,verified=True)]);s.commit();ids=[x.id for x in s.scalars(select(PaymentRequest)).all()]
    barrier=threading.Barrier(2);out=[]
    def run(pid):
        try:
            with factory() as s:barrier.wait();reserve(s,s.get(PaymentRequest,pid),f"merchant-{pid}","auto");s.commit();out.append("reserved")
        except FinancialError:out.append("blocked")
    ts=[threading.Thread(target=run,args=(pid,)) for pid in ids];[t.start() for t in ts];[t.join() for t in ts]
    with factory() as s:assert out.count("reserved")==1 and balances(s,wallet(s))["available_balance"]==50000
def test_concurrent_daily_limit_reservations_cannot_exceed_limit(factory):
    fund(factory,400000);ids=[]
    with factory() as s:
        s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0,daily_limit=200000));s.add_all([PaymentRequest(merchant="A",category="x",description="x",amount=150000,verified=True),PaymentRequest(merchant="B",category="x",description="x",amount=150000,verified=True)]);s.commit();ids=[x.id for x in s.scalars(select(PaymentRequest)).all()]
    barrier=threading.Barrier(2);out=[]
    def run(pid):
        try:
            with factory() as s:barrier.wait();reserve(s,s.get(PaymentRequest,pid),f"daily-{pid}","auto");s.commit();out.append("ok")
        except FinancialError:out.append("blocked")
    ts=[threading.Thread(target=run,args=(pid,)) for pid in ids];[t.start() for t in ts];[t.join() for t in ts]
    with factory() as s:assert out.count("ok")==1 and active_reserved(s,wallet(s))==150000
def test_duplicate_payment_attempt_and_reservation_are_singleton(factory):
    fund(factory)
    with factory() as s:
        s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));p=PaymentRequest(merchant="A",category="x",description="x",amount=100000,verified=True);s.add(p);s.commit();pid=p.id
    barrier=threading.Barrier(2)
    def run(key):
        with factory() as s:barrier.wait();reserve(s,s.get(PaymentRequest,pid),key,"auto");s.commit()
    ts=[threading.Thread(target=run,args=(f"batch-{x}",)) for x in range(2)];[t.start() for t in ts];[t.join() for t in ts]
    with factory() as s:assert s.scalar(select(func.count(PaymentAttempt.id)))==1 and s.scalar(select(func.count(PaymentReservation.id)))==1
def test_expired_reservation_does_not_reduce_available_balance(factory):
    fund(factory)
    with factory() as s:
        s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));p=PaymentRequest(merchant="A",category="x",description="x",amount=100000,verified=True);s.add(p);s.flush();a=reserve(s,p,"expiry","auto");r=s.get(PaymentReservation,a.reservation_id);r.expires_at=r.created_at.replace(year=r.created_at.year-1);emit(s,"payment.reservation_expired",{"reservation_id":r.id});s.commit()
    with factory() as s:assert balances(s,wallet(s))["available_balance"]==200000
