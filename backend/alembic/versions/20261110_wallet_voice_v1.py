"""Add V1 exact batches and reminders; preserve existing tables and ledger rows."""
from alembic import op
import sqlalchemy as sa
from app.models import PaymentBatch, PaymentBatchItem, PaymentReminder, NotificationPreferences, PushSubscription

revision='20261110_wallet_voice_v1'
down_revision='20261108_product_hardening'
branch_labels=None
depends_on=None

def upgrade():
    for model in (PaymentBatch,PaymentBatchItem,PaymentReminder,NotificationPreferences,PushSubscription):
        model.__table__.create(op.get_bind(),checkfirst=True)
    op.get_bind().execute(sa.text("UPDATE payment_attempts SET status='REFUNDED',failure_reason=NULL WHERE id IN (SELECT payment_attempt_id FROM paypal_orders WHERE provider_status='REFUNDED')"))

def downgrade():
    raise RuntimeError('V1 downgrade requires an explicit data-preservation plan')
