"""Add consumer planning and read-state tables without touching financial records."""
from alembic import op
from app.models import NotificationReadState,MoneyRequest,TrackedBill

revision='20261114_consumer_product'
down_revision='20261113_final_quality'
branch_labels=None
depends_on=None

def upgrade():
    for model in (NotificationReadState,MoneyRequest,TrackedBill):
        model.__table__.create(op.get_bind(),checkfirst=True)

def downgrade():
    raise RuntimeError('Preserve request and notification history; downgrade needs an explicit retention plan')
