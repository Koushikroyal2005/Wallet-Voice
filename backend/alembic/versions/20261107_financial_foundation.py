"""financial foundation journal, reservations, and outbox

The prior demo ledger used debit/credit names on a single row. Existing rows are
renamed to legacy_ledger_entries before the new append-only journal table is
created, preserving history for audit and manual reconciliation.
"""
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy import inspect
from app.db import Base
import app.models
revision="20261107_financial_foundation"
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    bind=op.get_bind();tables=set(inspect(bind).get_table_names())
    legacy=False
    if "ledger_entries" in tables:
        columns={c["name"] for c in inspect(bind).get_columns("ledger_entries")}
        if "journal_transaction_id" not in columns:
            op.rename_table("ledger_entries","legacy_ledger_entries");legacy=True
    Base.metadata.create_all(bind=bind,checkfirst=True)
    wallet_columns={c["name"] for c in inspect(bind).get_columns("wallets")} if "wallets" in tables else set()
    if "wallets" in tables and "ledger_account_id" not in wallet_columns:
        op.add_column("wallets",sa.Column("ledger_account_id",sa.String(),nullable=True))
    # Preserve and translate the old debit/credit-name rows into balanced journals.
    if legacy:
        rows=bind.execute(sa.text("SELECT id,wallet_id,operation_id,debit_account,credit_account,amount,currency,created_at FROM legacy_ledger_entries")).mappings().all()
        for row in rows:
            wallet_account=bind.execute(sa.text("SELECT ledger_account_id FROM wallets WHERE id=:id"),{"id":row["wallet_id"]}).scalar()
            if not wallet_account:
                wallet_account=str(uuid.uuid4());bind.execute(sa.text("INSERT INTO ledger_accounts (id,name,account_type,currency,normal_direction,wallet_id,created_at) VALUES (:id,:name,'LIABILITY',:currency,'CREDIT',:wallet,:created)"),{"id":wallet_account,"name":f"wallet:legacy:{row['wallet_id']}","currency":row["currency"],"wallet":row["wallet_id"],"created":row["created_at"]});bind.execute(sa.text("UPDATE wallets SET ledger_account_id=:account WHERE id=:wallet"),{"account":wallet_account,"wallet":row["wallet_id"]})
            clearing_name="demo_bank_clearing" if row["debit_account"]=="demo_bank" or row["credit_account"]=="demo_bank" else "demo_merchant_clearing"
            clearing=bind.execute(sa.text("SELECT id FROM ledger_accounts WHERE name=:name"),{"name":clearing_name}).scalar()
            if not clearing:
                clearing=str(uuid.uuid4());bind.execute(sa.text("INSERT INTO ledger_accounts (id,name,account_type,currency,normal_direction,created_at) VALUES (:id,:name,'ASSET',:currency,'DEBIT',:created)"),{"id":clearing,"name":clearing_name,"currency":row["currency"],"created":row["created_at"]})
            journal=str(uuid.uuid4());bind.execute(sa.text("INSERT INTO journal_transactions (id,operation_id,description,reference,status,created_at) VALUES (:id,:operation,'Migrated legacy ledger entry',:reference,'POSTED',:created)"),{"id":journal,"operation":row["operation_id"],"reference":f"legacy:{row['id']}","created":row["created_at"]})
            wallet_direction="CREDIT" if row["credit_account"]=="wallet" else "DEBIT"
            clearing_direction="DEBIT" if wallet_direction=="CREDIT" else "CREDIT"
            for account_id,direction in [(wallet_account,wallet_direction),(clearing,clearing_direction)]:bind.execute(sa.text("INSERT INTO ledger_entries (id,journal_transaction_id,ledger_account_id,direction,amount,currency,created_at) VALUES (:id,:journal,:account,:direction,:amount,:currency,:created)"),{"id":str(uuid.uuid4()),"journal":journal,"account":account_id,"direction":direction,"amount":row["amount"],"currency":row["currency"],"created":row["created_at"]})
        # A legacy cached balance can include an opening balance predating the
        # available ledger history. Preserve that difference transparently.
        for legacy_wallet in bind.execute(sa.text("SELECT id,currency,cached_balance FROM wallets")).mappings().all():
            wallet_account=bind.execute(sa.text("SELECT ledger_account_id FROM wallets WHERE id=:id"),{"id":legacy_wallet["id"]}).scalar()
            posted=bind.execute(sa.text("SELECT COALESCE(SUM(CASE WHEN e.direction='CREDIT' THEN e.amount ELSE -e.amount END),0) FROM ledger_entries e JOIN journal_transactions j ON j.id=e.journal_transaction_id WHERE e.ledger_account_id=:account AND j.status='POSTED'"),{"account":wallet_account}).scalar() or 0
            difference=int(legacy_wallet["cached_balance"])-int(posted)
            if difference:
                clearing=bind.execute(sa.text("SELECT id FROM ledger_accounts WHERE name='demo_bank_clearing'")).scalar();operation=str(uuid.uuid4());journal=str(uuid.uuid4());direction="CREDIT" if difference>0 else "DEBIT";opposite="DEBIT" if direction=="CREDIT" else "CREDIT";amount=abs(difference)
                bind.execute(sa.text("INSERT INTO operations (id,kind,amount,status,reference,idempotency_key,created_at) VALUES (:id,'MIGRATION_OPENING_BALANCE',:amount,'SUCCEEDED',:reference,:key,CURRENT_TIMESTAMP)"),{"id":operation,"amount":amount,"reference":f"MIGRATION-OPENING-{legacy_wallet['id']}","key":f"migration-opening:{legacy_wallet['id']}"})
                bind.execute(sa.text("INSERT INTO journal_transactions (id,operation_id,description,reference,status,created_at) VALUES (:id,:operation,'Migrated opening balance',:reference,'POSTED',CURRENT_TIMESTAMP)"),{"id":journal,"operation":operation,"reference":f"MIGRATION-OPENING-{legacy_wallet['id']}"})
                for account_id,entry_direction in [(wallet_account,direction),(clearing,opposite)]:bind.execute(sa.text("INSERT INTO ledger_entries (id,journal_transaction_id,ledger_account_id,direction,amount,currency,created_at) VALUES (:id,:journal,:account,:direction,:amount,:currency,CURRENT_TIMESTAMP)"),{"id":str(uuid.uuid4()),"journal":journal,"account":account_id,"direction":entry_direction,"amount":amount,"currency":legacy_wallet["currency"]})
def downgrade():
    # Financial journals remain append-only. Downgrade only removes new empty-schema objects.
    bind=op.get_bind()
    for name in ["app_events","payment_reservations","payment_attempts","ledger_entries","journal_transactions","ledger_accounts"]:
        if name in inspect(bind).get_table_names():op.drop_table(name)
    if "legacy_ledger_entries" in inspect(bind).get_table_names():op.rename_table("legacy_ledger_entries","ledger_entries")
