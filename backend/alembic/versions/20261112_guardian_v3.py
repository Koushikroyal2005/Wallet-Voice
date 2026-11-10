"""Identity-bound mandates and non-financial attention preferences. No authority backfill."""
from alembic import op
import sqlalchemy as sa
from app.models import AttentionState
revision='20261112_guardian_v3'
down_revision='20261111_merchants_v2'
branch_labels=None
depends_on=None
def upgrade():
    if 'merchant_id' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('spending_mandates')}:
        op.add_column('spending_mandates',sa.Column('merchant_id',sa.String(),nullable=True))
    AttentionState.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():raise RuntimeError('A downgrade requires an explicit history-preservation plan')
