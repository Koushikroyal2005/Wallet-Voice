"""Durable attention queue and bounded, status-checked Web Push delivery."""
import json
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .core import settings
from .db import get_db
from .models import PaymentRequest,PaymentReminder,NotificationPreferences,PushSubscription,AttentionState
from .services import utc,wallet,emit
from .providers import NotificationProvider

router=APIRouter(prefix='/api/notifications')

def preferences(db):
    row=db.get(NotificationPreferences,'demo-user')
    if not row:
        try:
            with db.begin_nested():row=NotificationPreferences(user_id='demo-user');db.add(row);db.flush()
        except IntegrityError:row=db.get(NotificationPreferences,'demo-user')
    return row

def valid(p,now):
    return bool(p and p.status in {'PENDING','HELD'} and not p.explicit_hold and p.expires_at and utc(p.expires_at)>now)

def quiet(prefs,now):
    hour=now.astimezone(ZoneInfo(settings().app_timezone)).hour
    start,end=prefs.quiet_start,prefs.quiet_end
    return False if start==end else start<=hour<end if start<end else hour>=start or hour<end

def schedule(db,now=None):
    now=now or datetime.now(timezone.utc)
    wallet(db,True)  # Serializes schedulers so each request/stage has one record.
    prefs=preferences(db)
    for p in db.scalars(select(PaymentRequest).where(PaymentRequest.expires_at.is_not(None))).all():
        state=db.get(AttentionState,p.id)
        rows=list(db.scalars(select(PaymentReminder).where(PaymentReminder.payment_request_id==p.id)))
        if not valid(p,now) or not prefs.enabled or state and state.dismissed:
            for row in rows:
                if row.status in {'PENDING','RETRY'}:row.status='CANCELLED'
            continue
        left=(utc(p.expires_at)-now).total_seconds()
        for stage,threshold in [('UPCOMING',10800),('URGENT',900)]:
            for old in rows:
                if old.stage==stage and old.status=='CANCELLED' and left<=threshold:
                    old.status='PENDING';old.next_attempt_at=max(now,utc(state.snoozed_until)) if state and state.snoozed_until else now;old.attempts=0
            if left<=threshold and not any(r.stage==stage for r in rows):
                row=PaymentReminder(payment_request_id=p.id,stage=stage,next_attempt_at=max(now,utc(state.snoozed_until)) if state and state.snoozed_until else now);db.add(row)
                emit(db,'payment.reminder',{'payment_id':p.id,'stage':stage})
    db.flush()

def deliver_one(factory,sender:NotificationProvider|None=None):
    s=settings()
    if not (s.vapid_private_key and s.vapid_public_key and s.vapid_subject):return False
    if sender is None:
        from pywebpush import webpush
        sender=webpush
    with factory() as db:
        now=datetime.now(timezone.utc);prefs=preferences(db)
        if not prefs.enabled or not prefs.push_enabled or quiet(prefs,now):return False
        row=db.scalar(select(PaymentReminder).where(PaymentReminder.status.in_(['PENDING','RETRY']),PaymentReminder.next_attempt_at<=now).order_by(PaymentReminder.created_at).with_for_update(skip_locked=True).limit(1))
        if not row:return False
        p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==row.payment_request_id).with_for_update())
        if not valid(p,now):row.status='CANCELLED';db.commit();return True
        state=db.get(AttentionState,p.id)
        if state and state.dismissed:row.status='CANCELLED';db.commit();return True
        if state and state.snoozed_until and utc(state.snoozed_until)>now:
            row.next_attempt_at=utc(state.snoozed_until);db.commit();return True
        subscriptions=list(db.scalars(select(PushSubscription).where(PushSubscription.active.is_(True),PushSubscription.user_id=='demo-user')))
        if not subscriptions:return False
        # Hold request/reminder locks during the bounded send, never wallet locks.
        # This prevents a payment transition between the final check and dispatch.
        failed=False
        delivered=dict(row.deliveries or {})
        for subscription in subscriptions:
            if delivered.get(subscription.id):continue
            try:
                sender(subscription_info=subscription.subscription,data=json.dumps({'title':'A payment needs your attention','body':'Open Wallet-Voice to review it.','payment_id':p.id,'tag':row.id}),vapid_private_key=s.vapid_private_key,vapid_claims={'sub':s.vapid_subject},ttl=min(300,max(1,int((utc(p.expires_at)-now).total_seconds()))),timeout=5)
                delivered[subscription.id]=True
            except Exception as e:
                response=getattr(e,'response',None)
                if response is not None and getattr(response,'status_code',None) in {404,410}:subscription.active=False
                else:failed=True
        row.attempts+=1
        row.deliveries=delivered
        row.status='RETRY' if failed and row.attempts<3 else 'FAILED' if failed else 'SENT'
        row.next_attempt_at=now+timedelta(minutes=2**row.attempts)
        emit(db,'reminder.delivery.result',{'payment_id':p.id,'status':row.status,'stage':row.stage})
        db.commit();return True

class PreferenceUpdate(BaseModel):
    enabled:bool=True
    push_enabled:bool=False
    quiet_start:int=Field(default=22,ge=0,le=23)
    quiet_end:int=Field(default=8,ge=0,le=23)
class SubscriptionInput(BaseModel):
    endpoint:str=Field(max_length=2048)
    keys:dict[str,str]

def attention_data(db):
    now=datetime.now(timezone.utc)
    prefs=preferences(db)
    data=[];dismissed=[]
    for p in db.scalars(select(PaymentRequest).where(PaymentRequest.status.in_(['PENDING','HELD','FAILED','EXPIRED'])).order_by(PaymentRequest.created_at.desc()).limit(100)):
        state=db.get(AttentionState,p.id)
        left=(utc(p.expires_at)-now).total_seconds() if p.expires_at else None
        priority='EXPIRED' if p.status=='EXPIRED' or left is not None and left<=0 else 'URGENT' if left is not None and left<900 else 'DUE_SOON' if left is not None and left<=10800 else 'SAVED_CHECKOUT' if p.category=='merchant_checkout' else 'NORMAL'
        item={'id':'attention:'+p.id,'payment_id':p.id,'merchant':p.merchant,'amount':p.amount,'currency':p.currency,'deadline':utc(p.expires_at) if p.expires_at else None,'stage':priority,'status':'EXPIRED' if priority=='EXPIRED' else p.status,'snoozed_until':utc(state.snoozed_until) if state and state.snoozed_until and utc(state.snoozed_until)>now else None,'explicit_hold':p.explicit_hold}
        (dismissed if state and state.dismissed else data).append(item)
    rank={'URGENT':0,'DUE_SOON':1,'SAVED_CHECKOUT':2,'NORMAL':3,'EXPIRED':4}
    data.sort(key=lambda p:(rank[p['stage']],p['deadline'] or datetime.max.replace(tzinfo=timezone.utc),p['payment_id']))
    return {'items':data,'dismissed_items':dismissed,'preferences':{'enabled':prefs.enabled,'push_enabled':prefs.push_enabled,'quiet_start':prefs.quiet_start,'quiet_end':prefs.quiet_end},'push_configured':bool(settings().vapid_public_key and settings().vapid_private_key and settings().vapid_subject),'public_key':settings().vapid_public_key or None}

@router.get('')
def attention(db=Depends(get_db)):
    result=attention_data(db);db.commit();return result

class AttentionAction(BaseModel):
    action:str=Field(pattern='^(SNOOZE|DISMISS|RESTORE)$')
    minutes:int=Field(default=5,ge=1,le=60)

def change_attention(db,payment_id,action,minutes=5):
    wallet(db,True)
    p=db.get(PaymentRequest,payment_id)
    if not p:raise HTTPException(404,'Payment request not found')
    state=db.get(AttentionState,p.id)
    if not state:state=AttentionState(payment_request_id=p.id);db.add(state)
    now=datetime.now(timezone.utc)
    if action=='SNOOZE':
        if not valid(p,now):raise HTTPException(409,'This payment cannot receive a deadline reminder')
        state.snoozed_until=min(now+timedelta(minutes=minutes),utc(p.expires_at));state.dismissed=False
    else:state.dismissed=action=='DISMISS';state.snoozed_until=None
    db.flush()
    for reminder in db.scalars(select(PaymentReminder).where(PaymentReminder.payment_request_id==p.id,PaymentReminder.status.in_(['PENDING','RETRY']))):
        if state.dismissed:reminder.status='CANCELLED'
        elif state.snoozed_until:reminder.next_attempt_at=state.snoozed_until
    return {'payment_id':p.id,'dismissed':state.dismissed,'snoozed_until':state.snoozed_until,'payment_unchanged':True}

@router.post('/attention/{payment_id}')
def update_attention(payment_id:str,data:AttentionAction,db=Depends(get_db)):
    result=change_attention(db,payment_id,data.action,data.minutes);db.commit();return result

@router.patch('/preferences')
def update(data:PreferenceUpdate,db=Depends(get_db)):
    prefs=preferences(db)
    for key,value in data.model_dump().items():setattr(prefs,key,value)
    db.commit();return {'saved':True}

@router.post('/subscriptions')
def subscribe(data:SubscriptionInput,db=Depends(get_db)):
    # Fixed known push-provider domains prevent arbitrary server-side requests.
    try:
        parsed=urlparse(data.endpoint)
        port=parsed.port
    except ValueError:raise HTTPException(422,'Invalid browser push endpoint')
    allowed=('fcm.googleapis.com','updates.push.services.mozilla.com','push.services.mozilla.com','web.push.apple.com','notify.windows.com')
    if parsed.scheme!='https' or parsed.username or parsed.password or port not in (None,443) or not any(parsed.hostname==h or parsed.hostname and parsed.hostname.endswith('.'+h) for h in allowed):raise HTTPException(422,'Unsupported browser push endpoint')
    if set(data.keys)!={'auth','p256dh'} or any(not 8<=len(v)<=256 for v in data.keys.values()):raise HTTPException(422,'Invalid browser subscription keys')
    row=db.scalar(select(PushSubscription).where(PushSubscription.endpoint==data.endpoint))
    if not row:row=PushSubscription(endpoint=data.endpoint,subscription=data.model_dump());db.add(row)
    else:row.subscription=data.model_dump();row.active=True
    db.commit();return {'saved':True}
