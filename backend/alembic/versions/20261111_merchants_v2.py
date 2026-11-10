"""Add authenticated merchants and durable order relationships."""
from alembic import op
from app.models import MerchantIdentity,MerchantOrder
revision='20261111_merchants_v2'
down_revision='20261110_wallet_voice_v1'
branch_labels=None
depends_on=None
def upgrade():
    for model in (MerchantIdentity,MerchantOrder):model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    raise RuntimeError('Preserve merchant order history; downgrade requires a preservation plan')
