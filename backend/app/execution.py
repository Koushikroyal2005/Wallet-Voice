"""Only the simulated rail is retryable here; external attempts stay provider-owned."""
from .db import SessionLocal
from .models import PaymentAttempt, PaymentRequest,SpendingMandate,AuthorizationChallenge
from datetime import datetime,timezone
from sqlalchemy import select
from .providers import DemoPaymentProvider
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
        if attempt.idempotency_key.startswith('auto:'):
            mandate=db.get(SpendingMandate,(payment.trace or {}).get('mandate_id')) if (payment.trace or {}).get('mandate_id') else None
            valid=bool(mandate and mandate.user_id=='demo-user' and mandate.status=='ACTIVE' and utc(mandate.expires_at)>datetime.now(timezone.utc) and mandate.merchant==payment.merchant and mandate.max_amount>=payment.amount)
            if valid:
                expected={'merchant':mandate.merchant,'daily_limit':mandate.daily_limit,'expires_at':int(utc(mandate.expires_at).timestamp())}
                valid=any(c.details==expected for c in db.scalars(select(AuthorizationChallenge).where(AuthorizationChallenge.user_id==mandate.user_id,AuthorizationChallenge.action=='MANDATE',AuthorizationChallenge.resource_id==mandate.merchant,AuthorizationChallenge.amount==mandate.max_amount,AuthorizationChallenge.status=='CONSUMED')))
            if not valid:
                result=finalize(db,attempt_id,False,'','AUTOPAY_AUTHORITY_UNAVAILABLE');db.commit();db.refresh(result);db.expunge(result);return result
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
