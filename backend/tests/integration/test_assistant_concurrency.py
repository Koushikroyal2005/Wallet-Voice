"""Assistant replay safety on fresh isolated PostgreSQL schemas, no resets."""
import asyncio
import threading
import os
import pytest
from sqlalchemy import select,func
from test_paypal_lifecycle import isolated,race
from app.agentic import assistant_response,conversation_for
from app.models import ConversationMessage,PaymentIntent,PaymentAttempt,JournalTransaction
from app.voice import demo_intent

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='requires isolated PostgreSQL test database')


def test_duplicate_assistant_turn_creates_one_draft(isolated):
    factory,_=isolated
    with factory() as db:conversation_for(db,'shared-conversation');db.commit()
    barrier=threading.Barrier(2)
    async def provider(text,history):
        barrier.wait(timeout=10)
        return demo_intent(text)
    def submit():
        with factory() as db:
            return asyncio.run(assistant_response(db,'create a draft of 500 rupees for Asha','shared-conversation','same-request-id',provider))
    results=race(submit,submit)
    assert results[0]==results[1]
    with factory() as db:
        assert db.scalar(select(func.count(PaymentIntent.id)))==1
        assert db.scalar(select(func.count(ConversationMessage.id)))==2
        assert db.scalar(select(func.count(PaymentAttempt.id)))==0
        assert db.scalar(select(func.count(JournalTransaction.id)))==1  # original test funding only
