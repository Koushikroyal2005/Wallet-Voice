"""Only the simulated rail is retryable here; external attempts stay provider-owned."""
from .db import SessionLocal
from .models import PaymentAttempt, PaymentRequest,SpendingMandate,AuthorizationChallenge
from datetime import datetime,timezone
from sqlalchemy import select
from .providers import DemoPaymentProvider,UnknownProviderOutcome,InternalWalletPaymentProvider
from .services import finalize, FinancialError,utc


def execute_attempt(attempt_id):
    with SessionLocal() as db:
        attempt = db.get(PaymentAttempt, attempt_id)
        if not attempt or not attempt.reservation_id:
            raise FinancialError("Not an internal wallet attempt")
        if attempt.status != "PROCESSING":
            db.expunge(attempt)
            return attempt
        payment = db.get(PaymentRequest, attempt.payment_request_id)
        from .merchant_trust import current_identity
        if not current_identity(db,payment)['payable']:
            result=finalize(db,attempt_id,False,'','MERCHANT_IDENTITY_UNAVAILABLE');db.commit();db.refresh(result);db.expunge(result);return result
        if attempt.idempotency_key.startswith('auto:'):
            mandate=db.get(SpendingMandate,(payment.trace or {}).get('mandate_id')) if (payment.trace or {}).get('mandate_id') else None
            from .mandate_authority import valid_existing
            valid=valid_existing(db,mandate,payment)
            if not valid:
                result=finalize(db,attempt_id,False,'','AUTOPAY_AUTHORITY_UNAVAILABLE');db.commit();db.refresh(result);db.expunge(result);return result
        db.expunge_all()
    # No connection or transaction is held during provider execution.
    try:
        provider:InternalWalletPaymentProvider=DemoPaymentProvider()
        result = provider.execute(payment, attempt)
        success, reference, reason = result.success, result.reference, result.reason
    except UnknownProviderOutcome:
        return attempt
    except Exception:
        success, reference, reason = False, "", "DEMO_PROVIDER_UNAVAILABLE"
    if success is None:return attempt
    with SessionLocal() as db:
        result = finalize(db, attempt_id, success, reference, reason)
        db.commit()
        db.refresh(result)
        db.expunge(result)
        return result
