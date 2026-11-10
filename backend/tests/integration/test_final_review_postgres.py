"""Run final reminder/trust regressions against independent dedicated PG schemas."""
import os
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from app.models import PaymentReminder
from app import reminders
from test_merchants_v2_postgres import factory,configure,client
from test_final_review import prepare_push
from test_final_review import (
    clock,
    test_new_urgent_one_delivery_and_snooze_after_sent_is_durable,
    test_upcoming_escalates_once_only_when_later_urgent,
    test_explicit_reminder_respects_terminal_states_and_preferences,
    test_snooze_superseded_action_retry_cannot_schedule_again,
    test_revoked_identity_blocks_manual_payment_and_releases_reservation,
    test_completed_receipt_survives_identity_revocation,
    test_name_collision_or_removed_trace_is_not_identity_evidence,
    test_manual_review_fails_closed_on_invalid_versioned_identity,
)

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')


def test_concurrent_explicit_reminder_action_is_one_occurrence(factory,clock):
    ident=prepare_push(factory,clock);barrier=threading.Barrier(2)
    def snooze(_):
        with factory() as db:
            barrier.wait(timeout=10)
            result=reminders.change_attention(db,ident,'SNOOZE',5,'concurrent-reminder-001')
            db.commit();return result
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(snooze,range(2)))
    with factory() as db:
        rows=list(db.scalars(select(PaymentReminder).where(PaymentReminder.stage.like('SNOOZE:%'))))
        assert len(rows)==1 and rows[0].status=='PENDING'
    assert sum(bool(result.get('idempotent')) for result in results)==1
