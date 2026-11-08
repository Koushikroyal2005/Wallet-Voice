"""Add external PayPal Checkout persistence without touching wallet journals."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20261108_paypal_checkout"
down_revision="20261107_financial_foundation"
branch_labels=None
depends_on=None

def upgrade():
    # The preceding compatibility migration uses Base.metadata.create_all(), so a
    # fresh install already has these current metadata tables. Existing installs
    # get them here without recreating anything.
    tables=set(inspect(op.get_bind()).get_table_names())
    if "paypal_orders" not in tables:
        op.create_table("paypal_orders",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False),sa.Column("payment_request_id",sa.String(),sa.ForeignKey("payment_requests.id"),nullable=False),sa.Column("payment_attempt_id",sa.String(),sa.ForeignKey("payment_attempts.id"),nullable=True),sa.Column("paypal_order_id",sa.String(),nullable=False),sa.Column("paypal_capture_id",sa.String(),nullable=True),sa.Column("idempotency_key",sa.String(),nullable=False),sa.Column("original_amount",sa.Integer(),nullable=False),sa.Column("original_currency",sa.String(3),nullable=False),sa.Column("provider_amount",sa.String(32),nullable=False),sa.Column("provider_currency",sa.String(3),nullable=False),sa.Column("conversion_rate",sa.String(32),nullable=True),sa.Column("provider_status",sa.String(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("captured_at",sa.DateTime(timezone=True),nullable=True),sa.UniqueConstraint("paypal_order_id",name="uq_paypal_order_id"),sa.UniqueConstraint("paypal_capture_id",name="uq_paypal_capture_id"),sa.UniqueConstraint("idempotency_key",name="uq_paypal_order_key"))
        op.create_index("ix_paypal_orders_payment_request_id","paypal_orders",["payment_request_id"]);op.create_index("ix_paypal_orders_user_id","paypal_orders",["user_id"])
    if "paypal_webhook_events" not in tables:
        op.create_table("paypal_webhook_events",sa.Column("id",sa.String(),primary_key=True),sa.Column("paypal_event_id",sa.String(),nullable=False),sa.Column("event_type",sa.String(),nullable=False),sa.Column("paypal_order_id",sa.String(),nullable=True),sa.Column("verified",sa.Boolean(),nullable=False),sa.Column("payload",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("paypal_event_id",name="uq_paypal_event_id"))
        op.create_index("ix_paypal_webhook_events_paypal_event_id","paypal_webhook_events",["paypal_event_id"]);op.create_index("ix_paypal_webhook_events_paypal_order_id","paypal_webhook_events",["paypal_order_id"])
def downgrade():
    op.drop_table("paypal_webhook_events");op.drop_table("paypal_orders")
