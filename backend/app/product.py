"""Consumer planning and evidence views. No payment execution or authorization."""
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import AppEvent,NotificationReadState,MoneyRequest,TrackedBill,PaymentBatch
from .services import emit,utc
from .reminders import attention_data

router=APIRouter(prefix='/api/product')
OWNER='demo-user'  # Existing single-owner prototype, not multi-user authentication.

def notification_feed(db):
    states={r.notification_id:r for r in db.scalars(select(NotificationReadState).where(NotificationReadState.user_id==OWNER))}
    rows=[]
    # Whitelist user-facing events: never expose arbitrary event payloads/secrets.
    titles={'payment.completed':'Payment recorded','payment.failed':'Payment needs attention',
            'payment.batch.updated':'Batch status updated','money.requested':'Money request saved',
            'autopay.changed':'Automatic payment rules changed','security.pin.changed':'Wallet PIN changed'}
    for event in db.scalars(select(AppEvent).where(AppEvent.event_type.in_(titles)).order_by(AppEvent.created_at.desc()).limit(100)):
        payload=event.payload or {};payment_id=payload.get('payment_id');batch_id=payload.get('batch_id')
        rows.append({'id':'event:'+event.id,'title':titles[event.event_type],'message':'Open the recorded details. A notification is not proof of settlement.',
                     'section':'Needs Review' if event.event_type=='payment.failed' else 'All','created_at':utc(event.created_at),
                     'payment_id':payment_id,'batch_id':batch_id,'category':'security' if event.event_type=='security.pin.changed' else 'payment','destination':'settings' if event.event_type=='security.pin.changed' else 'activity'})
    for item in attention_data(db)['items']:
        if item['stage']=='EXPIRED':continue
        rows.append({'id':f"attention:{item['payment_id']}:{item['stage']}",'title':item['merchant'],
                     'message':'Saved payment ready for review. '+item['stage'].replace('_',' ').lower(),
                     'section':'Needs Review','created_at':None,'payment_id':item['payment_id'],'batch_id':None})
        if item['stage']=='URGENT' and not item['explicit_hold']:
            rows.append({'id':'insight:'+item['payment_id'],'title':'A deadline is approaching',
                         'message':f"{item['merchant']} is nearing its saved deadline. Review it before it expires.",
                         'section':'AI Updates','created_at':None,'payment_id':item['payment_id'],'batch_id':None,
                         'mode':'backend-derived insight; no model inference'})
    from .planning import supplemental_notices,prefs
    choices=prefs(db);rows.extend(supplemental_notices(db))
    rows.sort(key=lambda r:r.get('created_at') or datetime.now(timezone.utc),reverse=True)
    result=[]
    for row in rows:
        if row.get('category')=='payment' and not choices['payment_alerts']:continue
        if row['section']=='AI Updates' and not choices['ai_alerts']:continue
        if row.get('category')=='planning' and not choices['planning_alerts']:continue
        state=states.get(row['id'])
        if state and state.dismissed:continue
        result.append({**row,'read':bool(state and state.read)})
    return result

@router.get('/notifications')
def notifications(db=Depends(get_db)):
    rows=notification_feed(db);db.rollback()
    return {'items':rows,'unread':sum(not r['read'] for r in rows),'mode':'single-owner-demo'}

class NoticeAction(BaseModel):
    ids:list[str]=Field(min_length=1,max_length=300)
    action:str=Field(pattern='^(READ|DISMISS)$')

@router.post('/notifications/state')
def notice_state(data:NoticeAction,db=Depends(get_db)):
    known={r['id'] for r in notification_feed(db)}
    if any(ident not in known for ident in data.ids):raise HTTPException(404,'Notification is no longer available; refresh first')
    for ident in set(data.ids):
        row=db.scalar(select(NotificationReadState).where(NotificationReadState.user_id==OWNER,NotificationReadState.notification_id==ident))
        if not row:
            try:
                with db.begin_nested():
                    row=NotificationReadState(notification_id=ident);db.add(row);db.flush()
            except IntegrityError:
                row=db.scalar(select(NotificationReadState).where(NotificationReadState.user_id==OWNER,NotificationReadState.notification_id==ident))
        row.read=True
        if data.action=='DISMISS':row.dismissed=True
    db.commit();return {'updated':len(set(data.ids))}

class RequestCreate(BaseModel):
    payer:str=Field(min_length=1,max_length=120)
    amount:int=Field(gt=0,le=10_000_000)
    note:str=Field(default='',max_length=500)
    request_key:str=Field(min_length=8,max_length=80)
    @field_validator('payer')
    @classmethod
    def name(cls,value):
        if not value.strip():raise ValueError('Enter a payer name')
        return value.strip()

def request_view(row):
    return {'id':row.id,'payer':row.payer,'amount':row.amount,'currency':row.currency,'note':row.note,
            'status':row.status,'created_at':row.created_at,'simulated':True,'share_text':f'Wallet-Voice demo request: INR {row.amount/100:.2f} from {row.payer}. {row.note} Not a payment or bank transfer.'}

@router.get('/money-requests')
def requests(db=Depends(get_db)):
    return [request_view(r) for r in db.scalars(select(MoneyRequest).where(MoneyRequest.user_id==OWNER).order_by(MoneyRequest.created_at.desc()))]

@router.post('/money-requests')
def create_request(data:RequestCreate,db=Depends(get_db)):
    row=db.scalar(select(MoneyRequest).where(MoneyRequest.user_id==OWNER,MoneyRequest.request_key==data.request_key))
    if not row:
        try:
            with db.begin_nested():
                row=MoneyRequest(**data.model_dump());db.add(row);db.flush()
            emit(db,'money.requested',{'request_id':row.id})
        except IntegrityError:
            row=db.scalar(select(MoneyRequest).where(MoneyRequest.user_id==OWNER,MoneyRequest.request_key==data.request_key))
    if (row.payer,row.amount,row.note)!=(data.payer,data.amount,data.note):raise HTTPException(409,'Request key belongs to different details')
    db.commit();return request_view(row)

@router.post('/money-requests/{ident}/cancel')
def cancel_request(ident:str,db=Depends(get_db)):
    row=db.scalar(select(MoneyRequest).where(MoneyRequest.id==ident,MoneyRequest.user_id==OWNER).with_for_update())
    if not row:raise HTTPException(404,'Request not found')
    if row.status not in {'REQUESTED','CANCELLED'}:raise HTTPException(409,'Request is already recorded')
    row.status='CANCELLED';db.commit();return request_view(row)

class BillCreate(BaseModel):
    merchant:str=Field(min_length=1,max_length=120)
    amount:int=Field(gt=0,le=10_000_000)
    due_at:datetime
    recurring:bool=False
    @field_validator('merchant')
    @classmethod
    def name(cls,value):
        if not value.strip():raise ValueError('Enter a biller name')
        return value.strip()
    @field_validator('due_at')
    @classmethod
    def future(cls,value):
        if value.tzinfo is None or value<=datetime.now(timezone.utc):raise ValueError('Choose a future time with timezone')
        return value

@router.get('/bills')
def bills(db=Depends(get_db)):
    return [{'id':r.id,'merchant':r.merchant,'amount':r.amount,'currency':r.currency,'due_at':utc(r.due_at),
             'recurring':r.recurring,'cadence':r.cadence,'remind_at':utc(r.remind_at) if r.remind_at else None,'active':r.active,'mode':'Manually tracked estimate; not a live biller or automatic charge'}
            for r in db.scalars(select(TrackedBill).where(TrackedBill.user_id==OWNER).order_by(TrackedBill.due_at))]

@router.post('/bills')
def create_bill(data:BillCreate,db=Depends(get_db)):
    row=TrackedBill(**data.model_dump());db.add(row);db.commit();return {'id':row.id,'mode':'manual-tracking'}

@router.post('/bills/{ident}/archive')
def archive_bill(ident:str,db=Depends(get_db)):
    row=db.scalar(select(TrackedBill).where(TrackedBill.id==ident,TrackedBill.user_id==OWNER))
    if not row:raise HTTPException(404,'Bill not found')
    row.active=False;db.commit();return {'archived':True}

@router.get('/batches')
def history(db=Depends(get_db)):
    from .payment_batches import view
    return [{**view(db,b),'created_at':utc(b.created_at)} for b in db.scalars(select(PaymentBatch).where(PaymentBatch.user_id==OWNER).order_by(PaymentBatch.created_at.desc()).limit(100))]

@router.get('/sources')
def sources():
    from .paypal import configured
    return [{'id':'AI_WALLET','label':'Wallet-Voice simulated balance','currency':'INR','simulated':True,'configured':True,'operations':['single','batch'],'approval':'Transaction-bound wallet PIN'},
            {'id':'PAYPAL_SANDBOX','label':'PayPal Sandbox','simulated':False,'sandbox':True,'configured':configured(),'operations':['single'],'approval':'Separate PayPal buyer approval','balance':None},
            {'id':'BANK_CARD','label':'Banks & cards','configured':False,'operations':[],'balance':None,'approval':'No hosted bank/card integration connected'}]
