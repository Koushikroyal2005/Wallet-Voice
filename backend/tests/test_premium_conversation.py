"""Conversational preparation uses saved destinations and never executes money movement."""
import pytest
from sqlalchemy import select,func
from test_product_flows import factory
from test_http_contracts import client
from app.models import Recipient,PaymentIntent,PaymentAttempt
from app.services import balances,wallet
from app.voice import demo_intent,execute_tool,Intent
from test_v1 import requests


@pytest.mark.parametrize('spoken',['Send ₹500 to Rahul','Send 500 rupees to rahul','Please send 500 to +919876543210'])
def test_saved_recipient_prepares_exact_draft_only(client,factory,spoken):
    with factory() as db:
        r=Recipient(name='Rahul',handle='+919876543210');db.add(r);db.commit();rid=r.id
    first=client.post('/api/assistant/turn',json={'text':spoken,'request_id':'recipient-turn-001'}).json()
    p=first['action_preview'];assert p['kind']=='recipient_transfer' and p['amount']==50000
    assert p['recipient_handle']=='+919876543210'
    again=client.post('/api/assistant/turn',json={'text':'Okay, pay it.','conversation_id':first['conversation_id']}).json()
    assert again['action_preview']['intent_id']==p['intent_id']
    with factory() as db:
        row=db.get(PaymentIntent,p['intent_id']);assert row.recipient_id==rid and row.amount==50000
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0
        assert balances(db,wallet(db))['posted_balance']==1000000


@pytest.mark.parametrize('problem',['unknown','ambiguous','other_owner'])
def test_recipient_resolution_never_guesses(factory,problem):
    with factory() as db:
        if problem=='ambiguous':db.add_all([Recipient(name='Rahul',handle='+919111111111'),Recipient(name='Rahul',handle='+919222222222')])
        if problem=='other_owner':db.add(Recipient(name='Rahul',handle='+919111111111',user_id='someone-else'))
        db.flush();result=execute_tool(db,demo_intent('Send 500 to Rahul'))
        assert not result.get('preview') and db.scalar(select(func.count()).select_from(PaymentIntent))==0


def test_projection_and_spoken_approval_reuse_immutable_review(client,factory):
    requests(factory)
    first=client.post('/api/assistant/turn',json={'text':'Pay the train and movie tickets, not the food order.'}).json()
    original=first['action_preview']['batch_id'];cid=first['conversation_id']
    for text in ['How much money will I have left?','Okay pay it']:
        result=client.post('/api/assistant/turn',json={'text':text,'conversation_id':cid}).json()
        assert result['action_preview']['batch_id']==original
    with factory() as db:assert db.scalar(select(func.count()).select_from(PaymentAttempt))==0


def test_voice_recipient_uses_existing_pin_bound_execution_and_duplicate_reconciliation(client,factory):
    client.post('/api/recipients',json={'name':'Rahul','handle':'+919876543210','handle_type':'PHONE'})
    preview=client.post('/api/assistant/turn',json={'text':'Send 500 to Rahul'}).json()['action_preview']
    path=f"/api/payment-intents/{preview['intent_id']}/execute";key='approved-recipient-test'
    assert client.post(path,json={'approval_token':'not-a-valid-approved-token','idempotency_key':key}).status_code==409
    challenge=client.post('/api/security/challenges',json={'action':'P2P','amount':50000,'resource_id':preview['intent_id'],'details':{'version':preview['version'],'source':preview['source']}}).json()['id']
    token=client.post(f'/api/security/challenges/{challenge}/verify',json={'pin':'123456'}).json()['approval_token']
    for _ in range(2):
        result=client.post(path,json={'approval_token':token,'idempotency_key':key})
        assert result.status_code==200 and result.json()['payment']['status']=='SUCCEEDED',result.text
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PaymentAttempt))==1
        assert balances(db,wallet(db))['posted_balance']==950000
