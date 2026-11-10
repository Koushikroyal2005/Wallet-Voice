"""Synthetic evaluation fixtures: no development DB and no payment providers."""
import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import PaymentRequest,PaymentAttempt,PaymentReservation,JournalTransaction,Operation
from app.context import contextual_intent,contains_authentication_secret
from app.voice import Intent,demo_intent,nemotron_intent,execute_tool

CASES=json.loads(Path(__file__).with_name('voice_cases.json').read_text(encoding='utf-8'))


async def evaluate_case(case,model=False):
    expected=case.get('expected_model',case['expected']) if model else case['expected']
    if contains_authentication_secret(case['text']):
        assert expected=={'tool':'BLOCKED_SECRET','args':{}}
        return {'provider':'safety-guard','tool':'BLOCKED_SECRET'}
    state=SimpleNamespace(selected_payment_id=case.get('selected'),context=copy.deepcopy(case.get('context',{})))
    intent=contextual_intent(case['text'],state)
    if intent is None:intent=await nemotron_intent(case['text'],[]) if model else demo_intent(case['text'])
    args={key:value.casefold() if key=='merchant' and isinstance(value,str) else value for key,value in intent.args.items()}
    if intent.tool=='prepare_manual_payment':args.setdefault('payment_source','AI_WALLET')
    assert intent.tool==expected['tool'],f"Expected tool {expected['tool']}, received {intent.tool}"
    assert args==expected['args'],f"Tool arguments differ: expected {expected['args']}, received {args}"
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    try:
        with sessionmaker(bind=engine,autoflush=False)() as db:
            now=datetime.now(timezone.utc)
            db.add_all([
                PaymentRequest(id='rail',merchant='Indian Railways',category='travel',description='Train ticket',amount=125000,verified=True,expires_at=now+timedelta(minutes=4)),
                PaymentRequest(id='movie',merchant='CinemaPass',category='entertainment',description='Movie ticket',amount=60000,verified=True,expires_at=now+timedelta(hours=2)),
                PaymentRequest(id='expired',merchant='Old Rail',category='travel',description='Old train',amount=125000,expires_at=now-timedelta(minutes=1)),
                PaymentRequest(id='paid',merchant='Paid Rail',category='travel',description='Settled ticket',amount=125000,status='SUCCEEDED'),
                PaymentRequest(id='held',merchant='Held Rail',category='travel',description='Held ticket',amount=125000,status='HELD',explicit_hold=True),
            ])
            if case.get('extra_rail'):db.add(PaymentRequest(id='other-rail',merchant='Other Railways',category='travel',description='Train ticket',amount=50000))
            db.flush()
            outcome=execute_tool(db,intent)
            preview=outcome.get('preview') or {}
            if case.get('no_preview'):assert not preview.get('requires_confirmation'),'Unexpected action review'
            if case.get('preview_payment'):assert preview.get('payment_id')==case['preview_payment']
            if case.get('ambiguous'):assert outcome.get('ambiguous') is True
            if preview.get('kind')=='payment':assert preview['payment_source']==args['payment_source']
            for table in [PaymentAttempt,PaymentReservation,JournalTransaction,Operation]:
                assert db.scalar(select(func.count()).select_from(table))==0,'Interpretation must never execute money movement'
            return {'provider':intent.provider,'tool':intent.tool or 'CLARIFY'}
    finally:engine.dispose()
