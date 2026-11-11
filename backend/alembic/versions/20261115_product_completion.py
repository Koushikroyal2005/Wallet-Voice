"""Add unverified intake, splits, uploads and reminder planning; preserve financial tables."""
from alembic import op
import sqlalchemy as sa
from app.models import PaymentIntakeRecord,SplitGroup,SplitParticipant,DocumentRecord,ProductPreferences
revision='20261115_product_completion'
down_revision='20261114_consumer_product'
branch_labels=None
depends_on=None
def upgrade():
    for model in (PaymentIntakeRecord,SplitGroup,SplitParticipant,DocumentRecord,ProductPreferences):model.__table__.create(op.get_bind(),checkfirst=True)
    fields={c['name'] for c in sa.inspect(op.get_bind()).get_columns('tracked_bills')}
    if 'cadence' not in fields:op.add_column('tracked_bills',sa.Column('cadence',sa.String(),nullable=False,server_default='MONTHLY'))
    if 'remind_at' not in fields:op.add_column('tracked_bills',sa.Column('remind_at',sa.DateTime(timezone=True),nullable=True))
def downgrade():raise RuntimeError('Preserve financial and imported history; downgrade requires an explicit retention plan')
