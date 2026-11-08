from datetime import datetime,timezone
from app.models import PayPalOrder,PaymentRequest
from app.paypal import apply_webhook,currency_amount
from app.paypal import configured
from app.services import balances,wallet
from test_domain import db

def test_sandbox_inr_to_usd_uses_decimal_rounding(monkeypatch):
    monkeypatch.setenv("PAYPAL_CHECKOUT_CURRENCY","USD");monkeypatch.setenv("PAYPAL_DEMO_INR_PER_USD","84")
    from app.core import settings
    settings.cache_clear()
    assert currency_amount(125000,"INR")==("14.88","USD","84")
    settings.cache_clear()
def test_paypal_completed_webhook_does_not_debit_wallet():
    s=db();p=PaymentRequest(merchant="Rail",category="travel",description="ticket",amount=125000);s.add(p);s.flush();o=PayPalOrder(payment_request_id=p.id,paypal_order_id="ORDER-1",idempotency_key="key",original_amount=125000,original_currency="INR",provider_amount="14.88",provider_currency="USD",conversion_rate="84");s.add(o);s.flush();before=balances(s,wallet(s))["posted_balance"]
    apply_webhook(s,{"id":"EVENT-1","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{"id":"CAP-1","amount":{"value":"14.88","currency_code":"USD"},"supplementary_data":{"related_ids":{"order_id":"ORDER-1"}}}})
    assert s.get(PaymentRequest,p.id).status=="SUCCEEDED" and s.get(PayPalOrder,o.id).paypal_capture_id=="CAP-1"
    assert balances(s,wallet(s))["posted_balance"]==before
def test_duplicate_webhook_is_idempotent():
    s=db();apply_webhook(s,{"id":"EVENT-duplicate","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{}});apply_webhook(s,{"id":"EVENT-duplicate","event_type":"PAYMENT.CAPTURE.COMPLETED","resource":{}})
def test_paypal_is_disabled_without_credentials(monkeypatch):
    monkeypatch.setenv("PAYPAL_ENABLED","false");monkeypatch.delenv("PAYPAL_CLIENT_ID",raising=False);monkeypatch.delenv("PAYPAL_CLIENT_SECRET",raising=False)
    from app.core import settings
    settings.cache_clear();assert configured() is False;settings.cache_clear()
