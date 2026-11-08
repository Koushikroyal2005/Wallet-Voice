from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine,func,select
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import AutoPaySettings,JournalTransaction,LedgerEntry,PaymentRequest,PaymentReservation
from app.services import (FinancialError,balances,finalize,policy,reserve,topup_or_withdraw,wallet)

def db():
    engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);return sessionmaker(bind=engine)()
def funded(s,amount=300000):return topup_or_withdraw(s,amount,"TOPUP","fund")
def test_every_posted_journal_balances():
    s=db();funded(s);journal=s.scalar(select(JournalTransaction));entries=s.scalars(select(LedgerEntry).where(LedgerEntry.journal_transaction_id==journal.id)).all()
    assert sum(e.amount for e in entries if e.direction=="DEBIT")==sum(e.amount for e in entries if e.direction=="CREDIT")==300000
def test_topup_and_withdrawal_derive_wallet_balance():
    s=db();funded(s);topup_or_withdraw(s,50000,"WITHDRAWAL","withdraw")
    assert balances(s,wallet(s))["posted_balance"]==250000
def test_idempotent_topup_posts_once():
    s=db();a=topup_or_withdraw(s,100000,"TOPUP","same");b=topup_or_withdraw(s,100000,"TOPUP","same")
    assert a.id==b.id and balances(s,wallet(s))["posted_balance"]==100000
def test_active_reservation_reduces_available_balance():
    s=db();funded(s);p=PaymentRequest(merchant="Rail",category="travel",description="x",amount=100000,verified=True,expires_at=datetime.now(timezone.utc)+timedelta(minutes=4));s.add(p);s.flush();s.add(__import__('app.models',fromlist=['AutoPaySettings']).AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));s.flush();reserve(s,p,"pay-00001","auto")
    assert balances(s,wallet(s))["available_balance"]==200000
def test_manual_unknown_requires_confirmation_and_hard_limits_remain():
    s=db();funded(s);p=PaymentRequest(merchant="Unknown",category="x",description="x",amount=100000,verified=False);s.add(p);s.flush()
    assert policy(s,p,"manual")["decision"]=="MANUAL_CONFIRMATION_REQUIRED"
    with __import__('pytest').raises(FinancialError):reserve(s,p,"pay-unknown","manual")
def test_consumed_reservation_is_not_double_counted():
    s=db();funded(s);p=PaymentRequest(merchant="Rail",category="travel",description="x",amount=100000,verified=True,expires_at=datetime.now(timezone.utc)+timedelta(minutes=4));s.add(p);s.add(__import__('app.models',fromlist=['AutoPaySettings']).AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));s.flush();a=reserve(s,p,"pay-00002","auto");finalize(s,a.id,True,"demo")
    assert balances(s,wallet(s))["posted_balance"]==200000 and balances(s,wallet(s))["reserved_amount"]==0
def test_all_autopay_switch_combinations():
    for enabled,time_only,expected in [(False,False,"MANUAL_APPROVAL_REQUIRED"),(False,True,"MANUAL_APPROVAL_REQUIRED"),(True,False,"ELIGIBLE"),(True,True,"HELD_FLEXIBLE")]:
        s=db();funded(s);s.add(AutoPaySettings(enabled=enabled,time_sensitive_only=time_only,minimum_balance=0));p=PaymentRequest(merchant="Rail",category="travel",description="x",amount=100,verified=True);s.add(p);s.flush()
        assert policy(s,p,"auto")["decision"]==expected
def test_daily_limit_blocks_second_payment_reservation():
    s=db();funded(s);s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0,daily_limit=150000));p1=PaymentRequest(merchant="A",category="x",description="x",amount=100000,verified=True);p2=PaymentRequest(merchant="B",category="x",description="x",amount=100000,verified=True);s.add_all([p1,p2]);s.flush();reserve(s,p1,"daily-first","auto")
    assert policy(s,p2,"auto")["decision"]=="HELD_LIMIT_EXCEEDED"
def test_failed_payment_releases_reservation_without_journal_debit():
    s=db();funded(s);s.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0));p=PaymentRequest(merchant="Rail",category="x",description="x",amount=100000,verified=True);s.add(p);s.flush();a=reserve(s,p,"fail-payment","auto");finalize(s,a.id,False,"demo","failure")
    assert balances(s,wallet(s))["posted_balance"]==300000 and balances(s,wallet(s))["reserved_amount"]==0
