"""Server-backed assistant journeys; deterministic parser, no live providers."""
import asyncio
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
from test_http_contracts import client
from test_product_flows import factory
from app.models import Conversation,ConversationMessage,PaymentRequest,PaymentAttempt,PaymentIntent,PaymentReservation,JournalTransaction
from app.services import balances,wallet
from app.agentic import assistant_response
from app.voice import demo_intent


def seed(factory,extra=False):
    with factory() as db:
        p=PaymentRequest(merchant='Indian Railways',category='travel',description='Train ticket',amount=125000,verified=True,expires_at=datetime.now(timezone.utc)+timedelta(minutes=4));db.add(p)
        db.add(PaymentRequest(merchant='Expired Rail',category='travel',description='Old ticket',amount=10000,expires_at=datetime.now(timezone.utc)-timedelta(minutes=1)))
        if extra:db.add(PaymentRequest(merchant='Other Railways',category='travel',description='Train ticket',amount=50000,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)))
        db.commit();return p.id


def test_urgent_reference_source_change_and_hold_only_prepare(client,factory):
    pid=seed(factory)
    first=client.post('/api/assistant/turn',json={'text':'Which payments are urgent?'}).json()
    assert [item['id'] for item in first['data']]==[pid]
    assert first['provider']=='demo-parser'
    ident=first['conversation_id']
    def ask(text):return client.post('/api/assistant/turn',json={'text':text,'conversation_id':ident}).json()
    assert ask('why that one?')['intent']=='get_payment_details'
    assert ask('pay that one')['action_preview']['payment_id']==pid
    switched=ask('use PayPal instead')
    assert switched['provider']=='context-resolver'
    assert switched['action_preview']['payment_source']=='PAYPAL_SANDBOX'
    ask('what is my wallet balance?')
    assert ask('pay that one')['action_preview']['payment_source']=='PAYPAL_SANDBOX'
    assert ask('hold that one')['action_preview']['kind']=='hold'
    assert ask('cancel')['action_preview'] is None
    assert ask('pay that one')['action_preview'] is None
    with factory() as db:
        assert db.get(PaymentRequest,pid).status=='PENDING'
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0
        assert db.scalar(select(func.count(PaymentReservation.id)))==0
        assert balances(db,wallet(db))['posted_balance']==1000000


def test_multiple_urgent_matches_require_clarification(client,factory):
    seed(factory,True)
    first=client.post('/api/assistant/turn',json={'text':'urgent payments'}).json()
    ident=first['conversation_id']
    result=client.post('/api/assistant/turn',json={'text':'pay that one','conversation_id':ident}).json()
    assert result['action_preview'] is None
    result=client.post('/api/assistant/turn',json={'text':'pay my train ticket','conversation_id':ident}).json()
    assert result['action_preview'] is None and len(result['data'])==2
    result=client.post('/api/assistant/turn',json={'text':'pay the second one','conversation_id':ident}).json()
    assert result['action_preview']['requires_confirmation'] is True


def test_lost_response_retry_does_not_duplicate_draft_even_after_cancel(client,factory):
    ident='test-retry-conversation'
    body={'text':'create a draft of 500 rupees for Asha','conversation_id':ident,'request_id':'draft-request-001'}
    first=client.post('/api/assistant/turn',json=body)
    assert first.status_code==200
    client.post('/api/assistant/turn',json={'text':'cancel','conversation_id':ident,'request_id':'cancel-request-001'})
    retry=client.post('/api/assistant/turn',json=body)
    assert retry.json()==first.json()
    changed=client.post('/api/assistant/turn',json={**body,'text':'create a draft of 600 rupees for Asha'})
    assert changed.status_code==409
    with factory() as db:
        assert db.scalar(select(func.count(PaymentIntent.id)))==1
        assert db.scalar(select(func.count(ConversationMessage.id)))==4


def test_secret_disclosure_never_enters_conversation_or_model(client,factory,monkeypatch):
    calls=[]
    async def provider(*args):calls.append(args);return demo_intent('balance')
    monkeypatch.setattr('app.main.nemotron_intent',provider)
    for text in ['PIN 1 2 3 4 5 6','OTP one two three four five six','my password is test-only']:
        assert client.post('/api/assistant/turn',json={'text':text}).status_code==422
    assert calls==[]
    with factory() as db:assert db.scalar(select(func.count(ConversationMessage.id)))==0


def test_inference_holds_no_database_transaction(factory):
    with factory() as db:
        async def provider(text,history):
            assert not db.in_transaction()
            return demo_intent(text)
        result=asyncio.run(assistant_response(db,'balance',None,'inference-request-001',provider))
        assert result['intent']=='get_wallet_balance'


def test_request_expiry_between_list_and_review_is_checked(client,factory):
    pid=seed(factory)
    first=client.post('/api/assistant/turn',json={'text':'urgent payments'}).json()
    with factory() as db:
        db.get(PaymentRequest,pid).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    result=client.post('/api/assistant/turn',json={'text':'pay that one','conversation_id':first['conversation_id']}).json()
    assert result['action_preview'] is None and 'expired' in result['response']


def test_foreign_wallet_is_not_described_or_funded_as_rupees(client,factory):
    with factory() as db:wallet(db).currency='EUR';db.commit()
    result=client.post('/api/assistant/turn',json={'text':'balance'}).json()
    assert result['data']['currency']=='EUR' and 'EUR' in result['response']
    result=client.post('/api/assistant/turn',json={'text':'add 100 rupees'}).json()
    assert result['action_preview'] is None
