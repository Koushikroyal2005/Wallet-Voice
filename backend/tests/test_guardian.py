"""Guardian review uses actual execution records; no external providers."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from test_http_contracts import client
from test_product_flows import factory
from app.models import PaymentRequest, PaymentAttempt, PaymentReservation, JournalTransaction, PayPalOrder
from app.services import balances, wallet

def seed(factory, **values):
    with factory() as db:
        p=PaymentRequest(merchant='Rail',category='travel',description='Ticket',amount=125000,verified=True,**values)
        db.add(p);db.commit();return p.id

def approval(client,pid):
    review=client.post('/api/payment-batches',json={'payment_ids':[pid]}).json()
    auth=client.post(f"/api/payment-batches/{review['id']}/authorize",json={'pin':'123456'}).json()
    return {'batch_id':review['id'],'approval_token':auth['approval_token']}

def test_wallet_success_and_duplicate_confirmation(client,factory):
    pid=seed(factory)
    review=client.get(f'/api/payments/{pid}/review').json()
    assert review['wallet_policy']['decision']=='ELIGIBLE' and review['receipt'] is None
    body={'idempotency_key':'guardian-confirm-key',**approval(client,pid)}
    first=client.post(f'/api/payments/{pid}/pay',json=body)
    second=client.post(f'/api/payments/{pid}/pay',json=body)
    assert first.json()==second.json() and first.json()['status']=='SUCCEEDED'
    receipt=client.get(f'/api/payments/{pid}/review').json()['receipt']
    assert receipt['status']=='SUCCEEDED' and receipt['journal_id'] and receipt['timestamp']
    assert receipt['funding_source']=='AI_WALLET' and receipt['capture_id'] is None
    with factory() as db:
        assert db.scalar(select(func.count(PaymentAttempt.id)))==1
        assert balances(db,wallet(db))['posted_balance']==875000

def test_failed_payment_has_no_success_journal(client,factory):
    pid=seed(factory)
    with factory() as db:db.get(PaymentRequest,pid).description='force-fail';db.commit()
    assert client.post(f'/api/payments/{pid}/pay',json={'idempotency_key':'guardian-failed-key',**approval(client,pid)}).json()['status']=='FAILED'
    result=client.get(f'/api/payments/{pid}/review').json()
    assert result['receipt']['status']=='FAILED' and result['receipt']['journal_id'] is None
    assert result['attempt']['failure_reason']=='DEMO_PROVIDER_FAILURE'

def test_unknown_insufficient_expired_and_hold(client,factory):
    pid=seed(factory)
    with factory() as db:db.get(PaymentRequest,pid).verified=False;db.commit()
    result=client.get(f'/api/payments/{pid}/review').json()
    assert result['wallet_policy']['decision']=='MANUAL_CONFIRMATION_REQUIRED'
    assert result['wallet_policy_after_merchant_confirmation']['decision']=='ELIGIBLE'
    with factory() as db:db.get(PaymentRequest,pid).amount=2000000;db.commit()
    assert 'MINIMUM_BALANCE' in client.get(f'/api/payments/{pid}/review').json()['wallet_policy']['reason_codes']
    with factory() as db:db.get(PaymentRequest,pid).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    assert client.get(f'/api/payments/{pid}/review').json()['wallet_policy']['decision']=='EXPIRED'
    held=seed(factory)
    assert client.post(f'/api/payments/{held}/hold').status_code==200
    assert client.get(f'/api/payments/{held}/review').json()['wallet_policy']['decision']=='EXPLICIT_HOLD'
    with factory() as db:
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0
        assert db.scalar(select(func.count(PaymentReservation.id)))==0

def test_paypal_pending_and_completed_records_keep_wallet_separate(client,factory):
    pid=seed(factory)
    with factory() as db:
        a=PaymentAttempt(payment_request_id=pid,idempotency_key='external-review-key',status='PROCESSING');db.add(a);db.flush()
        order=PayPalOrder(payment_request_id=pid,payment_attempt_id=a.id,paypal_order_id='TEST-ORDER',idempotency_key='test-order',original_amount=125000,original_currency='INR',provider_amount='14.88',provider_currency='USD',provider_status='PENDING',paypal_capture_id='TEST-CAPTURE')
        db.add(order);db.get(PaymentRequest,pid).status='PROCESSING';db.commit()
    result=client.get(f'/api/payments/{pid}/review').json()
    assert result['paypal']['status']=='PENDING' and result['receipt']['status']=='PROCESSING'
    assert result['receipt']['funding_source']=='PAYPAL_SANDBOX' and result['receipt']['journal_id'] is None
    with factory() as db:
        order=db.scalar(select(PayPalOrder));order.provider_status='COMPLETED';order.captured_at=datetime.now(timezone.utc)
        db.scalar(select(PaymentAttempt)).status='SUCCEEDED';db.get(PaymentRequest,pid).status='SUCCEEDED';db.commit()
    result=client.get(f'/api/payments/{pid}/review').json()
    assert result['paypal']['status']=='COMPLETED' and result['receipt']['capture_id']=='TEST-CAPTURE'
    assert result['receipt']['timestamp_label']=='Capture recorded'
    with factory() as db:
        assert balances(db,wallet(db))['posted_balance']==1000000
        assert db.scalar(select(func.count(PaymentReservation.id)))==0
        assert db.scalar(select(func.count(JournalTransaction.id)))==1

def test_review_missing_request(client):
    assert client.get('/api/payments/missing/review').status_code==404

def test_wallet_rejects_foreign_currency_without_financial_mutation(client,factory):
    pid=seed(factory,currency='USD')
    response=client.post(f'/api/payments/{pid}/pay',json={'idempotency_key':'foreign-currency-key'})
    assert response.status_code==403  # Direct execution also requires exact PIN approval.
    assert 'CURRENCY_MISMATCH' in client.get(f'/api/payments/{pid}/review').json()['wallet_policy']['reason_codes']
    with factory() as db:
        assert balances(db,wallet(db))['posted_balance']==1000000
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0
        assert db.scalar(select(func.count(PaymentReservation.id)))==0
