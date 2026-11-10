"""A bounded worker pass, also callable in tests without starting an infinite loop."""
from datetime import datetime, timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import PaymentAttempt, PaymentRequest, PaymentReservation
from .services import FinancialError, finalize, policy, reserve, transition, emit, utc, wallet
from .execution import execute_attempt


def tick():
    from .reminders import schedule,deliver_one
    with SessionLocal() as reminder_db:
        schedule(reminder_db);reminder_db.commit()
    for _ in range(5):
        if not deliver_one(SessionLocal):break
    with SessionLocal() as db:
        wallet(db, True)
        for reservation in db.scalars(select(PaymentReservation).where(PaymentReservation.status == "ACTIVE")).all():
            if utc(reservation.expires_at) <= datetime.now(timezone.utc):
                finalize(db, reservation.payment_attempt_id, False, "", "RESERVATION_EXPIRED")
                reservation.status = "EXPIRED"
        for payment in db.scalars(select(PaymentRequest).where(PaymentRequest.status.in_(["PENDING", "HELD", "FAILED"]))).all():
            if payment.expires_at and utc(payment.expires_at) <= datetime.now(timezone.utc):
                transition(payment, "EXPIRED")
                emit(db, "payment.expired", {"payment_id": payment.id})
        db.commit()
    # Resume committed simulated attempts after a process interruption.
    with SessionLocal() as db:
        ids = list(db.scalars(select(PaymentAttempt.id).where(PaymentAttempt.status == "PROCESSING", PaymentAttempt.reservation_id.is_not(None)).limit(100)))
    for attempt_id in ids:
        execute_attempt(attempt_id)
    with SessionLocal() as db:
        ids = list(db.scalars(select(PaymentRequest.id).where(PaymentRequest.status == "PENDING", PaymentRequest.explicit_hold.is_(False)).limit(100)))
    for payment_id in ids:
        with SessionLocal() as db:
            try:
                payment = db.get(PaymentRequest, payment_id)
                if policy(db, payment, "auto")["decision"] != "ELIGIBLE":
                    continue
                attempt = reserve(db, payment, f"auto:{payment_id}", "auto")
                db.commit()
                attempt_id = attempt.id
            except FinancialError:
                db.rollback()
                continue
        execute_attempt(attempt_id)
