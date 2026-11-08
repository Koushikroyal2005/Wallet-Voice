"""Only the simulated rail is retryable here; external attempts stay provider-owned."""
from .db import SessionLocal
from .models import PaymentAttempt, PaymentRequest
from .providers import DemoPaymentProvider
from .services import finalize, FinancialError


def execute_attempt(attempt_id):
    with SessionLocal() as db:
        attempt = db.get(PaymentAttempt, attempt_id)
        if not attempt or not attempt.reservation_id:
            raise FinancialError("Not an internal wallet attempt")
        if attempt.status != "PROCESSING":
            db.expunge(attempt)
            return attempt
        payment = db.get(PaymentRequest, attempt.payment_request_id)
        db.expunge_all()
    # No connection or transaction is held during provider execution.
    try:
        result = DemoPaymentProvider().execute(payment, attempt)
        success, reference, reason = result.success, result.reference, result.reason
    except Exception:
        success, reference, reason = False, "", "DEMO_PROVIDER_UNAVAILABLE"
    with SessionLocal() as db:
        result = finalize(db, attempt_id, success, reference, reason)
        db.commit()
        db.refresh(result)
        db.expunge(result)
        return result
