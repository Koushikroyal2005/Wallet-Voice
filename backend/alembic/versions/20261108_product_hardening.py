"""product hardening

Revision ID: 20261108_product_hardening
Revises: 20261108_agentic_wallet
"""
from alembic import op
import sqlalchemy as sa

revision="20261108_product_hardening";down_revision="20261108_agentic_wallet";branch_labels=None;depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("spending_mandates")}
    if "context" not in columns:op.add_column("spending_mandates",sa.Column("context",sa.JSON(),nullable=False,server_default=sa.text("'{}'")))

def downgrade():
    op.drop_column("spending_mandates","context")
