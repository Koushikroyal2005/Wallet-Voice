"""Planning never spends; document evidence and notifications are server-backed."""
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
from test_product_flows import factory,payment
from test_http_contracts import client
from app.models import MoneyRequest,TrackedBill,NotificationReadState,PaymentAttempt,JournalTransaction,PaymentRequest
from app.services import balances,wallet,emit
from app.documents import pdf_document
from test_attempt_documents import pdf_text

def test_money_request_idempotency_and_no_financial_mutation(client,factory):
    body={'payer':'Rahul','amount':12000,'note':'Dinner','request_key':'request-demo-001'}
    a=client.post('/api/product/money-requests',json=body);assert a.status_code==200
    b=client.post('/api/product/money-requests',json=body);assert a.json()['id']==b.json()['id']
    assert a.json()['status']=='REQUESTED' and a.json()['simulated']
    assert client.post('/api/product/money-requests',json={**body,'amount':13000}).status_code==409
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(MoneyRequest))==1
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0
        assert balances(db,wallet(db))['posted_balance']==1000000
    assert client.post('/api/product/money-requests/'+a.json()['id']+'/cancel').json()['status']=='CANCELLED'

def test_planning_input_validation(client):
    for body in [{'payer':' ','amount':10,'request_key':'valid-key-001'},{'payer':'R','amount':0,'request_key':'valid-key-001'}]:
        assert client.post('/api/product/money-requests',json=body).status_code==422
    assert client.post('/api/product/bills',json={'merchant':'Netflix','amount':100,'due_at':'2020-01-01T00:00:00Z'}).status_code==422
    assert client.post('/api/product/bills',json={'merchant':'Netflix','amount':100,'due_at':'2030-01-01T00:00:00'}).status_code==422

def test_tracked_bill_not_an_executable_payment(client,factory):
    body={'merchant':'My subscription','amount':19900,'due_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),'recurring':True}
    result=client.post('/api/product/bills',json=body);assert result.status_code==200
    rows=client.get('/api/product/bills').json();assert len(rows)==1 and rows[0]['recurring']
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentRequest))==0
    assert client.post('/api/product/bills/'+result.json()['id']+'/archive').status_code==200
    assert not client.get('/api/product/bills').json()[0]['active']

def test_notification_read_and_dismiss_persist_without_payment_dismissal(client,factory):
    with factory() as db:
        p=payment(db);p.expires_at=datetime.now(timezone.utc)+timedelta(minutes=8);db.commit();ident=p.id
    first=client.get('/api/product/notifications').json();assert first['unread']==2
    ids=[r['id'] for r in first['items']]
    assert {r['section'] for r in first['items']}=={'Needs Review','AI Updates'}
    assert client.post('/api/product/notifications/state',json={'ids':ids,'action':'READ'}).status_code==200
    assert client.get('/api/product/notifications').json()['unread']==0
    assert client.post('/api/product/notifications/state',json={'ids':ids,'action':'DISMISS'}).status_code==200
    assert client.get('/api/product/notifications').json()['items']==[]
    assert any(r['payment_id']==ident for r in client.get('/api/notifications').json()['items'])
    assert client.get('/api/payments').json()[0]['status']=='PENDING'

def test_notification_whitelist_and_terminal_attention(client,factory):
    with factory() as db:
        p=payment(db);p.status='SUCCEEDED';db.flush()
        emit(db,'payment.completed',{'payment_id':p.id,'private':'never-return-this'})
        emit(db,'private.event',{'secret':'never-return-this'});db.commit()
    response=client.get('/api/product/notifications');assert response.status_code==200
    assert len(response.json()['items'])==1 and 'never-return-this' not in response.text
    assert client.post('/api/product/notifications/state',json={'ids':['made-up'],'action':'READ'}).status_code==404

def test_other_owner_records_not_visible(client,factory):
    with factory() as db:
        db.add(MoneyRequest(user_id='other',payer='Private',amount=100,request_key='other-owner'))
        db.add(TrackedBill(user_id='other',merchant='Private bill',amount=100,due_at=datetime.now(timezone.utc)))
        db.commit()
    assert client.get('/api/product/money-requests').json()==[]
    assert client.get('/api/product/bills').json()==[]

def test_preview_cannot_download_success_receipt(client,factory):
    with factory() as db:p=payment(db);db.commit();ident=p.id
    assert client.get(f'/api/product/documents/payments/{ident}.pdf').status_code==409
    batch=client.post('/api/payment-batches',json={'payment_ids':[ident]}).json()
    doc=client.get(f"/api/product/documents/batches/{batch['id']}.pdf")
    assert doc.status_code==200 and doc.content.startswith(b'%PDF-1.4')
    assert b'Status: REVIEW' in pdf_text(doc.content) and b'Not submitted' in pdf_text(doc.content)
    assert client.get('/api/product/documents/batches/missing.pdf').status_code==404

def test_actual_wallet_receipt_and_statement(client,factory):
    with factory() as db:p=payment(db);db.commit();ident=p.id
    batch=client.post('/api/payment-batches',json={'payment_ids':[ident]}).json()['id']
    token=client.post(f'/api/payment-batches/{batch}/authorize',json={'pin':'123456'}).json()['approval_token']
    result=client.post(f'/api/payment-batches/{batch}/confirm',json={'approval_token':token})
    assert result.json()['status']=='SUCCEEDED'
    doc=client.get(f'/api/product/documents/payments/{ident}.pdf')
    assert doc.headers['content-type']=='application/pdf'
    assert b'SIMULATED WALLET' in pdf_text(doc.content) and b'Actual recorded status: SUCCEEDED' in pdf_text(doc.content)
    assert result.json()['items'][0]['receipt']['journal_id'].encode() in pdf_text(doc.content)
    assert client.get('/api/product/batches').json()[0]['id']==batch

def test_source_capabilities_do_not_invent_bank_balances(client):
    sources=client.get('/api/product/sources').json()
    external=next(r for r in sources if r['id']=='PAYPAL_SANDBOX')
    assert external['balance'] is None and 'batch' not in external['operations']
    assert not next(r for r in sources if r['id']=='BANK_CARD')['configured']

def test_pdf_multiple_pages_and_escaping():
    data=pdf_document(['(Parentheses) \\ private']*120)
    from io import BytesIO
    from pypdf import PdfReader
    reader=PdfReader(BytesIO(data))
    assert len(reader.pages)>=3
    assert sum(page.extract_text().count('(Parentheses) \\ private') for page in reader.pages)==120
    start=int(data.split(b'startxref\n')[1].splitlines()[0]);assert data[start:start+4]==b'xref'

def test_assistant_readonly_planning_uses_actual_records(client,factory):
    client.post('/api/product/money-requests',json={'payer':'Rahul','amount':12000,'request_key':'voice-request-001'})
    client.post('/api/product/bills',json={'merchant':'My renewal','amount':19900,'due_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),'recurring':True})
    for text,expected in [('Show my subscriptions','manually tracked'),('Show money requests','Rahul'),('Find my receipts','No merchant tax invoices')]:
        response=client.post('/api/assistant/turn',json={'text':text})
        assert response.status_code==200 and expected in response.json()['response']
        assert not response.json().get('action_preview')
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0
