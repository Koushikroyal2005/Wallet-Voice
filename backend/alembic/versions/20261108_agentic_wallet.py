"""agentic wallet orchestration

Revision ID: 20261108_agentic_wallet
Revises: 20261108_paypal_checkout
"""
from alembic import op
import sqlalchemy as sa

revision="20261108_agentic_wallet"; down_revision="20261108_paypal_checkout"; branch_labels=None; depends_on=None
def upgrade():
    inspector=sa.inspect(op.get_bind());tables=set(inspector.get_table_names())
    if "explicit_hold" not in {column["name"] for column in inspector.get_columns("payment_requests")}:
        op.add_column("payment_requests",sa.Column("explicit_hold",sa.Boolean(),nullable=False,server_default=sa.false()))
    if "wallet_security" in tables:return
    op.create_table("wallet_security",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False,unique=True),sa.Column("pin_salt",sa.String(),nullable=False),sa.Column("pin_hash",sa.String(),nullable=False),sa.Column("failed_attempts",sa.Integer(),nullable=False,server_default="0"),sa.Column("locked_until",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("authorization_challenges",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False,index=True),sa.Column("action",sa.String(),nullable=False),sa.Column("amount",sa.Integer(),nullable=False),sa.Column("resource_id",sa.String()),sa.Column("details",sa.JSON(),nullable=False),sa.Column("status",sa.String(),nullable=False),sa.Column("approval_token",sa.String(),unique=True),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("used_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("conversations",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False,index=True),sa.Column("selected_payment_id",sa.String(),sa.ForeignKey("payment_requests.id")),sa.Column("selected_intent_id",sa.String()),sa.Column("context",sa.JSON(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("conversation_messages",sa.Column("id",sa.String(),primary_key=True),sa.Column("conversation_id",sa.String(),sa.ForeignKey("conversations.id"),nullable=False,index=True),sa.Column("role",sa.String(),nullable=False),sa.Column("content",sa.String(),nullable=False),sa.Column("tool_name",sa.String()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("recipients",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False,index=True),sa.Column("name",sa.String(),nullable=False),sa.Column("handle",sa.String(),nullable=False),sa.Column("handle_type",sa.String(),nullable=False),sa.Column("verified",sa.Boolean(),nullable=False),sa.Column("provider",sa.String(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("user_id","handle",name="uq_recipient_handle"))
    op.create_table("payment_intents",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False,index=True),sa.Column("kind",sa.String(),nullable=False),sa.Column("recipient_id",sa.String(),sa.ForeignKey("recipients.id")),sa.Column("merchant",sa.String()),sa.Column("amount",sa.Integer(),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("note",sa.String()),sa.Column("source",sa.String(),nullable=False),sa.Column("status",sa.String(),nullable=False),sa.Column("version",sa.Integer(),nullable=False),sa.Column("execute_after",sa.DateTime(timezone=True)),sa.Column("expires_at",sa.DateTime(timezone=True)),sa.Column("payment_request_id",sa.String(),sa.ForeignKey("payment_requests.id")),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("spending_mandates",sa.Column("id",sa.String(),primary_key=True),sa.Column("user_id",sa.String(),nullable=False,index=True),sa.Column("merchant",sa.String(),nullable=False,index=True),sa.Column("max_amount",sa.Integer(),nullable=False),sa.Column("daily_limit",sa.Integer(),nullable=False),sa.Column("spent_today",sa.Integer(),nullable=False),sa.Column("status",sa.String(),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
def downgrade():
    for table in ["spending_mandates","payment_intents","recipients","conversation_messages","conversations","authorization_challenges","wallet_security"]:op.drop_table(table)
    op.drop_column("payment_requests","explicit_hold")
