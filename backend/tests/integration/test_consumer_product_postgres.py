"""Same consumer contracts on isolated PostgreSQL, never the development DB."""
import os
import pytest
from test_merchants_v2_postgres import factory,configure,client
from test_consumer_product import (
    test_money_request_idempotency_and_no_financial_mutation,
    test_planning_input_validation,
    test_tracked_bill_not_an_executable_payment,
    test_notification_read_and_dismiss_persist_without_payment_dismissal,
    test_notification_whitelist_and_terminal_attention,
    test_other_owner_records_not_visible,
    test_preview_cannot_download_success_receipt,
    test_actual_wallet_receipt_and_statement,
    test_source_capabilities_do_not_invent_bank_balances,
    test_assistant_readonly_planning_uses_actual_records,
)
pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')
