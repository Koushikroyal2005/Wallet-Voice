"""Exercises the real Alembic upgrade against an exact pre-journal PostgreSQL schema."""
import os,subprocess,sys,uuid
import pytest
from sqlalchemy import create_engine,text

URL=os.getenv("TEST_DATABASE_URL")
pytestmark=pytest.mark.skipif(not URL,reason="requires isolated PostgreSQL test database")
@pytest.mark.parametrize('prior_reminders',[False,True])
def test_legacy_schema_migrates_to_balanced_journal(prior_reminders):
    from sqlalchemy.engine import make_url
    target=make_url(URL)
    if target.database!='aiwallet_test' or target.host!='test-db':pytest.fail('Legacy tests require isolated aiwallet_test@test-db')
    database=f"aiwallet_legacy_{uuid.uuid4().hex[:12]}";admin=create_engine(URL.rsplit("/",1)[0]+"/postgres",isolation_level="AUTOCOMMIT")
    with admin.connect() as c:c.execute(text(f'CREATE DATABASE "{database}"'))
    legacy_url=URL.rsplit("/",1)[0]+f"/{database}";engine=create_engine(legacy_url)
    try:
        with engine.begin() as c:
            c.execute(text("CREATE TABLE wallets (id varchar PRIMARY KEY,user_id varchar UNIQUE NOT NULL,currency varchar(3) NOT NULL,cached_balance integer NOT NULL)"))
            c.execute(text("CREATE TABLE operations (id varchar PRIMARY KEY,kind varchar NOT NULL,amount integer NOT NULL,status varchar NOT NULL,reference varchar NOT NULL,idempotency_key varchar UNIQUE NOT NULL,created_at timestamptz NOT NULL)"))
            c.execute(text("CREATE TABLE ledger_entries (id varchar PRIMARY KEY,wallet_id varchar NOT NULL REFERENCES wallets(id),operation_id varchar NOT NULL,debit_account varchar NOT NULL,credit_account varchar NOT NULL,amount integer NOT NULL,currency varchar(3) NOT NULL,created_at timestamptz NOT NULL)"))
            c.execute(text("CREATE TABLE payment_requests (id varchar PRIMARY KEY,merchant varchar NOT NULL,category varchar NOT NULL,description varchar NOT NULL,amount integer NOT NULL,currency varchar(3) NOT NULL,expires_at timestamptz,verified boolean NOT NULL,provider varchar NOT NULL,status varchar NOT NULL,trace json NOT NULL,created_at timestamptz NOT NULL)"))
            c.execute(text("CREATE TABLE autopay_settings (id varchar PRIMARY KEY,user_id varchar UNIQUE NOT NULL,enabled boolean NOT NULL,time_sensitive_only boolean NOT NULL,per_transaction_limit integer NOT NULL,daily_limit integer NOT NULL,minimum_balance integer NOT NULL,allow_unknown_merchants boolean NOT NULL)"))
            c.execute(text("INSERT INTO wallets VALUES ('wallet-1','demo-user','INR',500000)"));c.execute(text("INSERT INTO autopay_settings VALUES ('settings-1','demo-user',true,true,500000,1000000,10000,false)"))
            rows=[('op-topup','TOPUP',200000,'DEMO-TOPUP','demo_bank','wallet'),('op-withdraw','WITHDRAWAL',50000,'DEMO-WITHDRAW','wallet','demo_bank'),('op-payment','PAYMENT',150000,'DEMO-PAY','wallet','demo_merchant')]
            for op,kind,amount,ref,debit,credit in rows:
                c.execute(text("INSERT INTO operations VALUES (:id,:kind,:amount,'SUCCEEDED',:ref,:key,CURRENT_TIMESTAMP)"),{"id":op,"kind":kind,"amount":amount,"ref":ref,"key":op});c.execute(text("INSERT INTO ledger_entries VALUES (:id,'wallet-1',:op,:debit,:credit,:amount,'INR',CURRENT_TIMESTAMP)"),{"id":f"entry-{op}","op":op,"debit":debit,"credit":credit,"amount":amount})
            for ident,status in [('pending','PENDING'),('held','HELD'),('expired','EXPIRED')]:c.execute(text("INSERT INTO payment_requests VALUES (:id,:merchant,'travel','legacy',10000,'INR',CURRENT_TIMESTAMP,false,'DEMO_MERCHANT',:status,'{}',CURRENT_TIMESTAMP)"),{"id":ident,"merchant":ident,"status":status})
            if prior_reminders:
                c.execute(text("CREATE TABLE payment_reminders (id varchar PRIMARY KEY,payment_request_id varchar NOT NULL REFERENCES payment_requests(id),stage varchar NOT NULL,status varchar NOT NULL,attempts integer NOT NULL,deliveries json NOT NULL,next_attempt_at timestamptz NOT NULL,created_at timestamptz NOT NULL,UNIQUE(payment_request_id,stage))"))
                c.execute(text("INSERT INTO payment_reminders VALUES ('old-reminder','pending','UPCOMING','SENT',1,CAST(:deliveries AS json),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"),{'deliveries':'{"device":true}'})
        env={**os.environ,"DATABASE_URL":legacy_url};subprocess.run([sys.executable,"-m","alembic","-c","alembic.ini","upgrade","head"],check=True,env=env);subprocess.run([sys.executable,"-m","alembic","-c","alembic.ini","upgrade","head"],check=True,env=env)
        with engine.connect() as c:
            balance=c.scalar(text("SELECT COALESCE(SUM(CASE WHEN e.direction='CREDIT' THEN e.amount ELSE -e.amount END),0) FROM ledger_entries e JOIN ledger_accounts a ON a.id=e.ledger_account_id WHERE a.wallet_id='wallet-1'"));assert balance==500000
            assert c.scalar(text("SELECT count(*) FROM journal_transactions"))==4
            assert c.scalar(text("SELECT count(*) FROM payment_requests"))==3
            assert c.scalar(text("SELECT count(*) FROM payment_reservations"))==0
            assert c.scalar(text("SELECT count(*) FROM (SELECT journal_transaction_id,SUM(CASE WHEN direction='DEBIT' THEN amount ELSE -amount END) AS balance FROM ledger_entries GROUP BY journal_transaction_id) b WHERE balance<>0"))==0
            assert c.scalar(text("SELECT count(*) FROM operations WHERE reference IN ('DEMO-TOPUP','DEMO-WITHDRAW','DEMO-PAY')"))==3
            if prior_reminders:
                row=c.execute(text("SELECT status,deliveries,delivered_at FROM payment_reminders WHERE id='old-reminder'")).one()
                assert row.status=='SENT' and row.deliveries=={'device':True} and row.delivered_at is None
    finally:
        engine.dispose()
        # Retain the uniquely named disposable DB until the isolated tmpfs stops.
        # Never issue DROP DATABASE, TRUNCATE or reset against an existing DB.
        admin.dispose()
