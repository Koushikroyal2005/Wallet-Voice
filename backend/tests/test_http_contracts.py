"""HTTP contracts use an isolated SQLite database; no live providers are called."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.voice import demo_intent
from test_product_flows import factory


@pytest.fixture
def client(factory,monkeypatch):
    def database():
        with factory() as db:yield db
    async def parser(text,history):return demo_intent(text)
    app.dependency_overrides[get_db]=database
    monkeypatch.setattr('app.main.nemotron_intent',parser)
    try:
        with TestClient(app) as client:yield client
    finally:app.dependency_overrides.clear()


def test_http_conversation_reuses_server_history(client):
    first=client.post('/api/assistant/turn',json={'text':'show my balance'})
    assert first.status_code==200
    ident=first.json()['conversation_id']
    second=client.post('/api/assistant/turn',json={'text':'show pending payments','conversation_id':ident})
    assert second.status_code==200 and second.json()['conversation_id']==ident
    history=client.get(f'/api/assistant/conversations/{ident}').json()['messages']
    assert len(history)==4


def test_http_merchant_requires_key_and_recipient_validation(client):
    response=client.post('/api/merchant/checkout',json={'merchant':'Indian Railways','order_reference':'DEMO-test','amount':125000})
    assert response.status_code==401
    assert client.post('/api/recipients',json={'name':'Asha','handle':'invalid','handle_type':'PHONE'}).status_code==422


def test_http_wrong_pins_commit_lockout(client):
    ident=client.post('/api/security/challenges',json={'action':'TOPUP','amount':10000}).json()['id']
    for _ in range(5):assert client.post(f'/api/security/challenges/{ident}/verify',json={'pin':'000000'}).status_code==403
    correct=client.post(f'/api/security/challenges/{ident}/verify',json={'pin':'123456'})
    assert correct.status_code==403 and 'locked' in correct.json()['detail']


def test_http_private_wallet_requires_session_and_logout_revokes_cookie(client,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'require_wallet_login',True)
    monkeypatch.setattr(settings(),'wallet_session_secret','test-only-signing-secret-not-used-outside-tests')
    assert client.get('/api/wallet').status_code==401
    login=client.post('/api/auth/login',json={'pin':'123456'})
    assert login.status_code==200
    cookie=client.cookies.get('aiwallet_session')
    assert 'HttpOnly' in login.headers['set-cookie']
    assert client.get('/api/wallet').status_code==200
    assert client.post('/api/auth/logout').status_code==200
    client.cookies.set('aiwallet_session',cookie)
    assert client.get('/api/wallet').status_code==401


def test_http_pin_change_invalidates_wallet_session(client,monkeypatch):
    from app.core import settings
    monkeypatch.setattr(settings(),'require_wallet_login',True)
    monkeypatch.setattr(settings(),'wallet_session_secret','test-only-signing-secret-not-used-outside-tests')
    client.post('/api/auth/login',json={'pin':'123456'})
    assert client.post('/api/security/pin/change',json={'current_pin':'123456','new_pin':'654321'}).status_code==200
    assert client.get('/api/wallet').status_code==401
    assert client.post('/api/auth/login',json={'pin':'654321'}).status_code==200
    assert client.get('/api/wallet').status_code==200
