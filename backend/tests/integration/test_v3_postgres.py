"""V3 financial invariants and identity races on dedicated PostgreSQL schemas."""
import os,threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from test_merchants_v2_postgres import factory,configure,client
from test_merchants_v2 import merchants
from test_v3 import order,grant
from test_v3 import test_payment_memory_independent_of_alerts_and_nonfinancial_controls,test_stable_mandate_rejects_identity_mismatch_revocation_and_rename,test_identity_bound_mandate_and_replayed_approval,test_legacy_name_permission_cannot_authorize_versioned_identity,test_conversation_correction_invalidates_pin_and_supports_readd,test_unknown_outcome_stays_processing_until_reconciled
from app.models import PaymentRequest,SpendingMandate
from app.services import reserve,FinancialError

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')

def test_stable_identity_concurrent_allowance_and_replay(factory,client):
    header=merchants(factory)[0];ids=[order(client,header,'race-'+str(n)) for n in range(2)]
    mandate=grant(client,factory,daily=10000);barrier=threading.Barrier(2)
    def claim(ident):
        with factory() as db:
            p=db.get(PaymentRequest,ident);barrier.wait(timeout=10)
            try:
                a=reserve(db,p,'auto:'+ident,'auto');db.commit()
                assert reserve(db,p,'auto:'+ident,'auto').id==a.id
                return 'reserved'
            except FinancialError:db.rollback();return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,ids))
    assert sorted(results)==['blocked','reserved']
    with factory() as db:assert db.get(SpendingMandate,mandate).spent_today==10000
