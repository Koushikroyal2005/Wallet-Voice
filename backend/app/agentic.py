from datetime import datetime,timezone
import copy
import hashlib
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from .core import settings
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .models import Conversation,ConversationMessage,PaymentIntent,PaymentRequest,Recipient,SpendingMandate

def conversation_for(db:Session,conversation_id:str|None)->Conversation:
    row=db.get(Conversation,conversation_id) if conversation_id else None
    if row and row.user_id!="demo-user":raise ValueError("Conversation not found")
    if not row:
        try:
            with db.begin_nested():
                row=Conversation(**({'id':conversation_id} if conversation_id else {}));db.add(row);db.flush()
        except IntegrityError:row=db.get(Conversation,conversation_id)
    return row
def conversation_history(db:Session,row:Conversation,limit:int=12)->list[dict]:
    messages=db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==row.id).order_by(ConversationMessage.created_at.desc()).limit(limit)).all()
    return [{"role":message.role,"content":message.content} for message in reversed(messages)]
def add_message(db:Session,row:Conversation,role:str,content:str,tool_name:str|None=None):db.add(ConversationMessage(conversation_id=row.id,role=role,content=content[:2000],tool_name=tool_name))

class ConversationConflict(ValueError):pass

async def assistant_response(db,text,conversation_id,request_id,intent_provider):
    """Inference holds no DB transaction; recheck context before applying a turn.

    Replay keys deduplicate the latest 32 turns, including draft creation.
    This authorizes no payments and never calls payment execution services.
    """
    from .context import contextual_intent
    from .voice import execute_tool,nvidia_ready
    from .services import utc
    conversation=conversation_for(db,conversation_id)
    fingerprint=hashlib.sha256(text.encode()).hexdigest()
    def replay(row):
        previous=((row.context or {}).get('turn_receipts') or {}).get(request_id) or (row.context or {}).get('last_turn') or {}
        if request_id and previous.get('request_id')==request_id:
            if previous['fingerprint']!=fingerprint:raise ConversationConflict('This request ID was already used for different text.')
            return previous['response']
    cached=replay(conversation)
    if cached:db.rollback();return cached
    history=conversation_history(db,conversation,settings().voice_history_max_turns)
    ident=conversation.id;version=conversation.updated_at
    state=SimpleNamespace(selected_payment_id=conversation.selected_payment_id,context=copy.deepcopy(conversation.context or {}))
    db.commit()
    intent=contextual_intent(text,state)
    if intent is None:
        intent=await intent_provider(text,history)
    row=db.scalar(select(Conversation).where(Conversation.id==ident).with_for_update().execution_options(populate_existing=True))
    if not row:raise ConversationConflict('This conversation was closed. Start a new chat.')
    cached=replay(row)
    if cached:db.rollback();return cached
    if utc(row.updated_at)!=utc(version):raise ConversationConflict('This conversation changed in another turn. Review the latest messages and retry.')
    receipts=dict((row.context or {}).get('turn_receipts') or {})
    row.selected_payment_id=state.selected_payment_id
    row.context=state.context
    outcome=execute_tool(db,intent)
    preview=outcome.get('preview');response=outcome.get('response') or 'Please clarify your request.'
    context=dict(row.context or {})
    if outcome.get('clear_selection'):
        row.selected_payment_id=None;context.pop('selected_source',None)
        if not outcome.get('ambiguous'):context.pop('listed_payment_ids',None)
    if preview and preview.get('payment_id'):
        row.selected_payment_id=preview['payment_id']
        if preview.get('payment_source'):context['selected_source']=preview['payment_source']
    if intent.tool in {'list_payment_requests','get_urgent_payment_requests'} or outcome.get('ambiguous'):
        context['listed_payment_ids']=[item['id'] for item in outcome.get('data',[])]
        row.selected_payment_id=context['listed_payment_ids'][0] if len(context['listed_payment_ids'])==1 else None
    context['preview']=preview
    context['awaiting_amount']=intent.tool if intent.tool in {'prepare_topup','prepare_withdrawal'} and not intent.args.get('amount') else None
    result={'conversation_id':ident,'response':response,'intent':intent.tool or None,'tool_name':intent.tool or None,'data':outcome.get('data'),'action_preview':preview,'requires_confirmation':bool(preview and preview.get('requires_confirmation')),'voice_response_available':nvidia_ready(),'provider':intent.provider}
    context.pop('last_turn',None)
    if request_id:
        receipts[request_id]={'request_id':request_id,'fingerprint':fingerprint,'response':result}
        receipts=dict(list(receipts.items())[-32:])
    context['turn_receipts']=receipts
    row.context=context;row.updated_at=datetime.now(timezone.utc)
    add_message(db,row,'user',text);add_message(db,row,'assistant',response,intent.tool or None)
    db.commit()
    return result
def create_draft(db:Session,amount:int,recipient:Recipient|None=None,merchant:str|None=None,note:str|None=None)->PaymentIntent:
    row=PaymentIntent(amount=amount,recipient_id=recipient.id if recipient else None,merchant=merchant,note=note,status="DRAFT");db.add(row);db.flush();return row
def mandate_for(db:Session,merchant:str,amount:int)->SpendingMandate|None:
    now=datetime.now(timezone.utc);today=now.astimezone(ZoneInfo(settings().app_timezone)).date().isoformat();row=db.scalar(select(SpendingMandate).where(SpendingMandate.merchant==merchant,SpendingMandate.status=="ACTIVE",SpendingMandate.expires_at>now,SpendingMandate.max_amount>=amount).order_by(SpendingMandate.created_at.desc()).with_for_update())
    if not row:return None
    context=row.context or {}
    spent=row.spent_today if context.get("usage_date")==today else 0
    if spent+amount>row.daily_limit:return None
    if context.get("usage_date")!=today:row.spent_today=0;row.context={**context,"usage_date":today}
    return row
def serialize_intent(row:PaymentIntent):return {"id":row.id,"kind":row.kind,"recipient_id":row.recipient_id,"merchant":row.merchant,"amount":row.amount,"currency":row.currency,"note":row.note,"source":row.source,"status":row.status,"version":row.version,"execute_after":row.execute_after,"expires_at":row.expires_at,"payment_request_id":row.payment_request_id}
