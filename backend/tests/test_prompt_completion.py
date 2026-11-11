"""Regression evidence for the requirements omitted by the first consumer pass."""
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,func
from test_product_flows import factory,payment
from test_http_contracts import client
from app.models import PaymentRequest,PaymentAttempt,Recipient,MoneyRequest,TrackedBill,ProductPreferences,PaymentIntakeRecord,DocumentRecord
from app.documents import pdf_document
from app.services import balances,wallet,emit

@pytest.mark.parametrize('url',['http://example.com','javascript:alert(1)','https://user:pass@example.com/pay','https://127.0.0.1/pay','https://[::1]/pay','https://localhost/pay','https://private.local/pay','https://example.com:8443/pay','https://example.com/\npay','file:///etc/passwd'])
def test_intake_rejects_unsafe_links(client,url):
    assert client.post('/api/product/intakes',json={'source_type':'LINK','source_url':url,'merchant':'Claim','amount':100}).status_code==422

def test_intake_dedupes_and_never_becomes_executable(client,factory):
    body={'source_type':'LINK','source_url':'https://example.com/checkout','merchant':'Untrusted store','amount':15000,'description':'User supplied','deadline':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}
    a=client.post('/api/product/intakes',json=body);assert a.status_code==200,a.text
    ident=a.json()['id'];assert client.post('/api/product/intakes',json=body).json()['id']==ident
    assert a.json()['trust']=='IMPORTED_UNVERIFIED' and not a.json()['can_pay']
    assert client.post(f'/api/payments/{ident}/pay').status_code in {403,404}
    assert client.post(f'/api/product/intakes/{ident}/state',json={'action':'REMIND','remind_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}).status_code==200
    assert client.post(f'/api/product/intakes/{ident}/state',json={'action':'HOLD'}).json()['status']=='HELD'
    assert client.post(f'/api/product/intakes/{ident}/state',json={'action':'RESTORE'}).json()['status']=='SAVED'
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PaymentRequest))==0
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0
        assert balances(db,wallet(db))['posted_balance']==1000000

def test_split_exact_rounding_confirmation_and_replay(client,factory):
    for name,handle in [('Rahul','+919111111111'),('Priya','+919222222222')]:client.post('/api/recipients',json={'name':name,'handle':handle})
    data={'amount':10001,'participants':['me','Rahul','Priya'],'note':'Dinner'}
    preview=client.post('/api/product/splits/preview',json=data).json()
    assert [p['amount'] for p in preview['participants']]==[3334,3334,3333]
    with factory() as db:assert db.scalar(select(func.count()).select_from(MoneyRequest))==0
    body={**data,'snapshot_hash':preview['snapshot_hash'],'request_key':'split-demo-001','confirmed':False}
    assert client.post('/api/product/splits',json=body).status_code==403
    body['confirmed']=True;first=client.post('/api/product/splits',json=body);assert first.status_code==200,first.text
    assert client.post('/api/product/splits',json=body).json()['id']==first.json()['id']
    assert first.json()['received_amount']==0 and first.json()['outstanding_amount']==6667
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(MoneyRequest))==2
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0
        assert balances(db,wallet(db))['posted_balance']==1000000

def test_split_unknown_ambiguous_and_changed_recipient(client,factory):
    data={'amount':200,'participants':['me','Rahul']}
    assert client.post('/api/product/splits/preview',json=data).status_code==409
    with factory() as db:db.add(Recipient(name='Rahul',handle='+919111111111'));db.commit()
    preview=client.post('/api/product/splits/preview',json=data).json()
    with factory() as db:db.add(Recipient(name='Rahul',handle='+919222222222'));db.commit()
    assert client.post('/api/product/splits',json={**data,'confirmed':True,'snapshot_hash':preview['snapshot_hash'],'request_key':'changed-split'}).status_code==409

def test_bill_reminder_and_calendar_rollover_are_not_payment(client,factory):
    with factory() as db:
        row=TrackedBill(merchant='Subscription',amount=100,due_at=datetime(2028,1,31,tzinfo=timezone.utc),recurring=True);db.add(row);db.commit();ident=row.id
    assert client.post(f'/api/product/bills/{ident}/reminder',json={'remind_at':'2028-01-30T00:00:00Z'}).status_code==200
    data={'expected_due':'2028-01-31T00:00:00Z','cadence':'MONTHLY'}
    result=client.post(f'/api/product/bills/{ident}/advance',json=data)
    assert result.status_code==200 and result.json()['due_at'].startswith('2028-02-29')
    assert not result.json()['payment_recorded']
    assert client.post(f'/api/product/bills/{ident}/advance',json=data).status_code==409
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0

def test_upload_validation_catalog_and_private_attachment(client,factory):
    assert client.post('/api/product/uploads',data={'title':'Bad'},files={'file':('bad.pdf',b'not-pdf','application/pdf')}).status_code==422
    assert client.post('/api/product/uploads',data={'title':'Big'},files={'file':('big.pdf',b'%PDF-'+b'a'*(2*1024*1024),'application/pdf')}).status_code==413
    data=pdf_document(['Example user bill - not payment proof'])
    response=client.post('/api/product/uploads',data={'title':'My train invoice'},files={'file':('bill.pdf',data,'application/pdf')});assert response.status_code==200,response.text
    record=response.json();assert not record['payment_proof']
    download=client.get(record['download_url']);assert download.content==data and 'attachment' in download.headers['content-disposition']
    assert 'sandbox' in download.headers['content-security-policy']
    docs=client.get('/api/product/documents?q=train&kind=UPLOAD').json();assert docs[0]['status']=='UNVERIFIED'
    result=client.post('/api/assistant/turn',json={'text':'Find my train invoice'}).json()
    # Train alias searches rail; generic invoice lookup never invents authenticated issuer evidence.
    assert 'No merchant tax invoices' in result['response'] and not result.get('action_preview')
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0

def test_notification_categories_keep_security_and_bill_consent(client,factory):
    now=datetime.now(timezone.utc)
    with factory() as db:
        db.add(TrackedBill(merchant='Reminder',amount=100,due_at=now+timedelta(days=1),remind_at=now-timedelta(minutes=1)))
        emit(db,'security.pin.changed',{});emit(db,'payment.completed',{'payment_id':'recorded-event'});db.commit()
    rows=client.get('/api/product/notifications').json()['items'];assert any(r.get('category')=='planning' for r in rows)
    assert client.patch('/api/product/preferences',json={'payment_alerts':False,'ai_alerts':False,'planning_alerts':False,'lock_screen_private':True}).status_code==200
    rows=client.get('/api/product/notifications').json()['items'];assert len(rows)==1 and rows[0]['category']=='security'

@pytest.mark.parametrize('text,name,note',[('Send ₹500 to Rahul for dinner','Rahul','dinner'),('Pay Priya ₹250','Priya',None)])
def test_voice_exact_recipient_with_notes(client,factory,text,name,note):
    client.post('/api/recipients',json={'name':name,'handle':'+919111111111'})
    result=client.post('/api/assistant/turn',json={'text':text}).json()
    assert result['action_preview']['kind']=='recipient_transfer' and result['action_preview']['recipient_name']==name
    if note:assert result['data']['note']==note
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0

def test_source_eligibility_is_readonly_and_explicit(client,factory):
    with factory() as db:p=payment(db);db.commit();ident=p.id
    data=client.get(f'/api/product/sources/{ident}/eligibility').json()
    assert not data['paypal']['can_prepare'] and not data['bank_card']['can_prepare']
    assert data['wallet']['decision']['decision']=='ELIGIBLE'
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0

def test_voice_split_and_bill_reminder_only_prepare_reviews(client,factory):
    for name,handle in [('Rahul','+919111111111'),('Priya','+919222222222')]:client.post('/api/recipients',json={'name':name,'handle':handle})
    response=client.post('/api/assistant/turn',json={'text':'Split ₹1200 between me, Rahul and Priya'}).json()
    assert response['action_preview']['kind']=='split_requests'
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(MoneyRequest))==0
        row=TrackedBill(merchant='Netflix',amount=19900,due_at=datetime.now(timezone.utc)+timedelta(days=5),recurring=True);db.add(row);db.commit();ident=row.id
    response=client.post('/api/assistant/turn',json={'text':'Remind me before Netflix renews'}).json()
    assert response['action_preview']['kind']=='bill_reminder' and response['action_preview']['resource_id']==ident
    with factory() as db:
        assert db.get(TrackedBill,ident).remind_at is None
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0

def test_voice_subscription_period_is_actually_filtered(client,factory):
    now=datetime.now(timezone.utc);start=now.replace(day=1,hour=12);future=start.replace(year=start.year+(start.month==12),month=start.month%12+1)
    with factory() as db:
        db.add_all([TrackedBill(merchant='This month',amount=100,due_at=start,recurring=True),TrackedBill(merchant='Next month',amount=200,due_at=future,recurring=True),TrackedBill(merchant='One-off',amount=300,due_at=start,recurring=False)]);db.commit()
    response=client.post('/api/assistant/turn',json={'text':'What subscriptions are due this month?'}).json()
    rows=response['data']['tracked_bills'];assert len(rows)==1 and rows[0]['merchant']=='This month'

def test_voice_money_request_prepares_without_saving_or_spending(client,factory):
    response=client.post('/api/assistant/turn',json={'text':'Request ₹500 from Rahul for dinner'}).json()
    p=response['action_preview'];assert p['kind']=='money_request' and p['amount']==50000 and p['recipient_name']=='Rahul'
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(MoneyRequest))==0
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0

def test_activity_groups_batches_and_does_not_treat_requests_as_received(client,factory):
    client.post('/api/product/money-requests',json={'payer':'Someone','amount':100,'request_key':'not-received-01'})
    with factory() as db:p=payment(db);db.commit();ident=p.id
    batch=client.post('/api/payment-batches',json={'payment_ids':[ident]}).json()
    rows=client.get('/api/product/activity').json()
    assert any(r.get('batch_id')==batch['id'] and r['status']=='REVIEW' for r in rows)
    received=[r for r in rows if r['kind']=='RECEIVED'];assert len(received)==1 and received[0]['totals']['INR']==1000000
    assert all(r['source']=='SIMULATED_WALLET' for r in rows)
