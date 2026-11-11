"""Prepared recipient drafts and exact approval on dedicated PostgreSQL schemas."""
import os
import pytest
from test_merchants_v2_postgres import factory,configure,client
from test_premium_conversation import (
    test_saved_recipient_prepares_exact_draft_only,
    test_recipient_resolution_never_guesses,
    test_projection_and_spoken_approval_reuse_immutable_review,
    test_voice_recipient_uses_existing_pin_bound_execution_and_duplicate_reconciliation,
)
pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')
