"""Record accepted push delivery time for coalescing and bounded escalation."""
from alembic import op
import sqlalchemy as sa
revision='20261113_final_quality'
down_revision='20261112_guardian_v3'
branch_labels=None
depends_on=None
def upgrade():
    if 'delivered_at' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('payment_reminders')}:
        op.add_column('payment_reminders',sa.Column('delivered_at',sa.DateTime(timezone=True),nullable=True))
def downgrade():raise RuntimeError('A downgrade requires an explicit history-preservation plan')
