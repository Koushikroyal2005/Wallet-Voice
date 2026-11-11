"""Historical document links must never resolve to a different attempt."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from test_product_flows import factory, payment
from test_http_contracts import client
from app.models import PaymentAttempt, JournalTransaction, PayPalOrder, PayPalWebhookEvent
from app.services import reserve, finalize, wallet, balances
from app.payment_batches import create_batch, view
from app.models import PaymentBatchItem
from io import BytesIO
from pypdf import PdfReader

def pdf_text(data):return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages).encode('utf-8')

def test_failed_batch_receipt_cannot_inherit_later_retry_journal(client, factory):
    with factory() as db:
        p=payment(db)
        batch=create_batch(db,[p.id]);db.flush()
        first=reserve(db,p,'wallet-failed-attempt','manual');db.flush()
        item=db.scalar(select(PaymentBatchItem).where(PaymentBatchItem.batch_id==batch.id))
        item.attempt_id=first.id;batch.status='PROCESSING'
        finalize(db,first.id,False,'not-settled','Demo decline');db.commit()
        failed_id=first.id;batch_id=batch.id;before=balances(db,wallet(db))['posted_balance']
        retry=reserve(db,p,'wallet-retried-attempt','manual');db.flush()
        finalize(db,retry.id,True,'retry-settled-reference');db.commit()
        success_id=retry.id
        assert balances(db,wallet(db))['posted_balance']==before-p.amount
        old=view(db,batch)
        assert old['items'][0]['status']=='FAILED' and old['items'][0]['receipt'] is None
    failed=pdf_text(client.get(f'/api/product/documents/attempts/{failed_id}.pdf').content)
    succeeded=pdf_text(client.get(f'/api/product/documents/attempts/{success_id}.pdf').content)
    assert b'Journal: Not recorded' in failed and b'Actual recorded status: FAILED' in failed
    assert b'retry-settled-reference' in succeeded and b'Actual recorded status: SUCCEEDED' in succeeded
    statement=pdf_text(client.get(f'/api/product/documents/batches/{batch_id}.pdf').content)
    assert b'Journal: Not posted' in statement and b'Status: FAILED' in statement

def test_failed_and_later_success_documents_are_distinct(client, factory):
    with factory() as db:
        p=payment(db)
        a=PaymentAttempt(payment_request_id=p.id,idempotency_key='failed-record',status='FAILED',provider_reference='failed-reference',created_at=datetime.now(timezone.utc)-timedelta(minutes=1))
        b=PaymentAttempt(payment_request_id=p.id,idempotency_key='success-record',status='SUCCEEDED',provider_reference='success-reference')
        db.add_all([a,b]);db.flush()
        db.add(PayPalOrder(payment_request_id=p.id,payment_attempt_id=b.id,paypal_order_id='sandbox-order',paypal_capture_id='sandbox-capture',idempotency_key='sandbox-record',original_amount=p.amount,original_currency='INR',provider_amount='1.19',provider_currency='USD',provider_status='COMPLETED'))
        db.commit(); failed_id=a.id;success_id=b.id;pid=p.id
        before=db.scalar(select(func.count()).select_from(JournalTransaction))
    records=client.get('/api/product/documents').json()
    by_id={r['attempt_id']:r for r in records if r['kind']=='PAYMENT'}
    assert by_id[failed_id]['download_url']!=by_id[success_id]['download_url']
    failed=client.get(by_id[failed_id]['download_url'])
    succeeded=client.get(by_id[success_id]['download_url'])
    assert b'Actual recorded status: FAILED' in pdf_text(failed.content)
    assert b'failed-reference' in pdf_text(failed.content) and b'sandbox-capture' not in pdf_text(failed.content)
    assert b'Actual recorded status: SUCCEEDED' in pdf_text(succeeded.content)
    assert b'sandbox-capture' in pdf_text(succeeded.content) and b'sandbox-order' in pdf_text(succeeded.content)
    assert failed.headers['cache-control']=='no-store'
    assert success_id in succeeded.headers['content-disposition']
    assert pdf_text(client.get(f'/api/product/documents/payments/{pid}.pdf').content)==pdf_text(succeeded.content)
    assert client.get('/api/product/documents/attempts/missing.pdf').status_code==404
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(JournalTransaction))==before

def test_refund_record_preserves_original_capture(client,factory):
    with factory() as db:
        p=payment(db);a=PaymentAttempt(payment_request_id=p.id,idempotency_key='refunded-attempt',status='REFUNDED')
        db.add(a);db.flush()
        db.add(PayPalOrder(payment_request_id=p.id,payment_attempt_id=a.id,paypal_order_id='refunded-order',paypal_capture_id='original-capture',idempotency_key='refunded-order-key',original_amount=p.amount,original_currency='INR',provider_amount='1.19',provider_currency='USD',provider_status='REFUNDED',captured_at=datetime.now(timezone.utc)))
        db.add(PayPalWebhookEvent(paypal_event_id='refund-event',event_type='PAYMENT.CAPTURE.REFUNDED',paypal_order_id='refunded-order',verified=True,payload={'resource':{'id':'refund-reference','amount':{'value':'1.19','currency_code':'USD'}}}))
        db.commit();ident=a.id
    record=client.get(f'/api/product/documents/attempts/{ident}').json()
    assert record['capture_id']=='original-capture' and record['status']=='REFUNDED'
    assert record['refunds'][0]['reference']=='refund-reference'
    pdf=pdf_text(client.get(f'/api/product/documents/attempts/{ident}.pdf').content)
    assert b'original-capture' in pdf and b'refund-reference' in pdf and b'Provider refund amount: USD 1.19' in pdf

def test_attention_read_state_survives_stage_change(client,monkeypatch):
    item={'payment_id':'saved-id','merchant':'Saved merchant','stage':'UPCOMING','explicit_hold':False}
    monkeypatch.setattr('app.product.attention_data',lambda db:{'items':[item]})
    first=client.get('/api/product/notifications').json()['items']
    ident=next(n['id'] for n in first if n['section']=='Needs Review')
    assert client.post('/api/product/notifications/state',json={'ids':[ident],'action':'READ'}).status_code==200
    item['stage']='URGENT'
    notices=client.get('/api/product/notifications').json()['items']
    attention=next(n for n in notices if n['section']=='Needs Review')
    assert attention['id']==ident and attention['read']

def test_activity_does_not_invent_paypal_source_without_order(client,factory):
    with factory() as db:
        p=payment(db)
        attempt=PaymentAttempt(payment_request_id=p.id,idempotency_key='unresolved-source',status='FAILED')
        db.add(attempt);db.commit();ident=attempt.id
    row=next(r for r in client.get('/api/product/activity').json() if r['id']==ident)
    assert row['source']=='UNRESOLVED'
    assert row['download_url']==f'/api/product/documents/attempts/{ident}.pdf'
