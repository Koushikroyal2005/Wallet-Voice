from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.agentic import add_message,conversation_for,conversation_history,create_draft
from app.authorization import AuthorizationError,consume_approval,create_challenge,verify_challenge
from app.db import Base
from app.models import PaymentRequest,Recipient
from app.services import policy

def db():
    engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);return sessionmaker(bind=engine)()

def test_pin_approval_is_transaction_bound_and_single_use():
    session=db();challenge=create_challenge(session,"TOPUP",200000);token=verify_challenge(session,challenge.id,"123456")
    with pytest.raises(AuthorizationError):consume_approval(session,token,"TOPUP",100000)
    consume_approval(session,token,"TOPUP",200000)
    with pytest.raises(AuthorizationError):consume_approval(session,token,"TOPUP",200000)

def test_invalid_pin_never_approves_challenge():
    session=db();challenge=create_challenge(session,"WITHDRAWAL",100000)
    with pytest.raises(AuthorizationError):verify_challenge(session,challenge.id,"000000")
    assert challenge.status=="PENDING" and challenge.approval_token is None

def test_conversation_history_is_owned_by_backend():
    session=db();conversation=conversation_for(session,None);add_message(session,conversation,"user","Show pending payments");add_message(session,conversation,"assistant","You have three.","list_payment_requests");session.flush()
    assert conversation_history(session,conversation)==[{"role":"user","content":"Show pending payments"},{"role":"assistant","content":"You have three."}]

def test_explicit_hold_is_never_policy_eligible():
    session=db();payment=PaymentRequest(merchant="Rail",category="travel",description="ticket",amount=125000,verified=True,explicit_hold=True,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5));session.add(payment);session.flush()
    decision=policy(session,payment,"auto")
    assert decision["decision"]=="EXPLICIT_HOLD" and decision["reason_codes"]==["USER_HELD"]

def test_payment_draft_does_not_move_money():
    session=db();recipient=Recipient(name="Asha",handle="asha@example.com",handle_type="EMAIL");session.add(recipient);session.flush();draft=create_draft(session,25000,recipient,note="Dinner")
    assert draft.status=="DRAFT" and draft.payment_request_id is None and draft.amount==25000

def test_unknown_merchant_confirmation_does_not_bypass_financial_limits():
    from app.models import AutoPaySettings
    from app.services import FinancialError,reserve,topup_or_withdraw
    session=db();topup_or_withdraw(session,100000,"TOPUP","fund-unknown-limit");session.add(AutoPaySettings(enabled=True,time_sensitive_only=False,minimum_balance=0,per_transaction_limit=50000,daily_limit=500000));payment=PaymentRequest(merchant="Unknown",category="x",description="x",amount=75000,verified=False);session.add(payment);session.flush()
    with pytest.raises(FinancialError,match="PER_TRANSACTION_LIMIT"):reserve(session,payment,"unknown-confirmed","manual",confirm_unknown=True)

def test_approval_details_are_immutable():
    session=db();details={"merchant":"Indian Railways","daily_limit":300000,"expires_at":1893456000};challenge=create_challenge(session,"MANDATE",150000,"Indian Railways",details);token=verify_challenge(session,challenge.id,"123456")
    with pytest.raises(AuthorizationError,match="details do not match"):consume_approval(session,token,"MANDATE",150000,"Indian Railways",{**details,"daily_limit":900000})
    consume_approval(session,token,"MANDATE",150000,"Indian Railways",details)
