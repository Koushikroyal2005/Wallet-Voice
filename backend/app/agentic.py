from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from .core import settings
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Conversation,ConversationMessage,PaymentIntent,PaymentRequest,Recipient,SpendingMandate

def conversation_for(db:Session,conversation_id:str|None)->Conversation:
    row=db.get(Conversation,conversation_id) if conversation_id else None
    if row and row.user_id!="demo-user":raise ValueError("Conversation not found")
    if not row:row=Conversation();db.add(row);db.flush()
    return row
def conversation_history(db:Session,row:Conversation,limit:int=12)->list[dict]:
    messages=db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id==row.id).order_by(ConversationMessage.created_at.desc()).limit(limit)).all()
    return [{"role":message.role,"content":message.content} for message in reversed(messages)]
def add_message(db:Session,row:Conversation,role:str,content:str,tool_name:str|None=None):db.add(ConversationMessage(conversation_id=row.id,role=role,content=content[:2000],tool_name=tool_name))
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
