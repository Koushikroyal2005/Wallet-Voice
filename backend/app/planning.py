"""Owner-scoped planning, catalog and capability queries. No payment execution."""
import calendar
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from .db import get_db
from .models import TrackedBill,PaymentIntakeRecord,ProductPreferences,PaymentRequest,PaymentAttempt,DocumentRecord,PaymentBatch,Recipient
from .services import utc
router=APIRouter(prefix='/api/product')

@router.get('/activity')
def activity(db=Depends(get_db)):
    from .models import PaymentBatchItem,Operation
    from .payment_batches import view
    rows=[];grouped=set()
    for batch in db.scalars(select(PaymentBatch).where(PaymentBatch.user_id=='demo-user').order_by(PaymentBatch.created_at.desc()).limit(100)):
        data=view(db,batch);totals={}
        for item in data['items']:
            totals[item['currency']]=totals.get(item['currency'],0)+item['amount']
            if item['attempt_id']:grouped.add(item['attempt_id'])
        rows.append({'id':batch.id,'kind':'BATCH','title':f"Batch of {len(data['items'])} saved requests",'search_text':' '.join(i['merchant']+' '+i.get('description','') for i in data['items']),
                     'status':data['status'],'created_at':utc(batch.created_at),'totals':totals,'source':'SIMULATED_WALLET','batch_id':batch.id,'reference':batch.id})
    for a,p in db.execute(select(PaymentAttempt,PaymentRequest).join(PaymentRequest,PaymentRequest.id==PaymentAttempt.payment_request_id).order_by(PaymentAttempt.created_at.desc()).limit(200)):
        if a.id in grouped:continue
        from .documents import attempt_record
        try:evidence=attempt_record(db,a.id)
        except HTTPException as error:
            if error.status_code==404:continue
            raise
        rows.append({'id':a.id,'kind':'BILL' if p.category in {'bill','bills','subscription'} else 'SENT','title':p.merchant,'search_text':p.description,'status':a.status,
                     'created_at':utc(a.created_at),'totals':{evidence['currency']:evidence['amount']},'source':'SIMULATED_WALLET' if evidence['funding_source']=='AI_WALLET' else evidence['funding_source'],
                     'payment_id':p.id,'attempt_id':a.id,'download_url':f'/api/product/documents/attempts/{a.id}.pdf','reference':a.provider_reference or a.id})
    for op in db.scalars(select(Operation).where(Operation.kind!='PAYMENT').order_by(Operation.created_at.desc()).limit(100)):
        rows.append({'id':op.id,'kind':'RECEIVED' if op.kind=='TOPUP' else 'SENT','title':'Simulated money added' if op.kind=='TOPUP' else 'Simulated withdrawal',
                     'status':op.status,'created_at':utc(op.created_at),'totals':{'INR':op.amount},'source':'SIMULATED_WALLET','reference':op.reference,'search_text':op.kind})
    rows.sort(key=lambda r:r['created_at'],reverse=True);db.rollback();return rows

class Preferences(BaseModel):
    payment_alerts:bool=True
    ai_alerts:bool=True
    planning_alerts:bool=True
    lock_screen_private:bool=True

def prefs(db):
    row=db.get(ProductPreferences,'demo-user')
    return {k:getattr(row,k) if row else v for k,v in Preferences().model_dump().items()}
@router.get('/preferences')
def preferences(db=Depends(get_db)):return prefs(db)
@router.patch('/preferences')
def change_preferences(data:Preferences,db=Depends(get_db)):
    row=db.get(ProductPreferences,'demo-user')
    if not row:row=ProductPreferences(user_id='demo-user');db.add(row)
    for k,v in data.model_dump().items():setattr(row,k,v)
    db.commit();return prefs(db)

class Reminder(BaseModel):remind_at:datetime
@router.post('/bills/{ident}/reminder')
def remind(ident:str,data:Reminder,db=Depends(get_db)):
    row=db.scalar(select(TrackedBill).where(TrackedBill.id==ident,TrackedBill.user_id=='demo-user').with_for_update())
    if not row:raise HTTPException(404,'Tracked expense not found')
    if not row.active or not data.remind_at.tzinfo or not datetime.now(timezone.utc)<data.remind_at<utc(row.due_at):raise HTTPException(422,'Choose a future in-app reminder before the due date of an active bill')
    row.remind_at=data.remind_at;db.commit();return {'saved':True,'channel':'in-app','moves_money':False}

class Advance(BaseModel):
    expected_due:datetime
    cadence:str=Field(pattern='^(WEEKLY|MONTHLY|YEARLY)$')
@router.post('/bills/{ident}/advance')
def advance(ident:str,data:Advance,db=Depends(get_db)):
    row=db.scalar(select(TrackedBill).where(TrackedBill.id==ident,TrackedBill.user_id=='demo-user').with_for_update())
    if not row:raise HTTPException(404,'Tracked expense not found')
    old=utc(row.due_at)
    if not row.active or not row.recurring or not data.expected_due.tzinfo or utc(data.expected_due)!=old:raise HTTPException(409,'Renewal changed or is not active. Refresh before advancing again.')
    if data.cadence=='WEEKLY':new=old+timedelta(days=7)
    else:
        month=old.month+1 if data.cadence=='MONTHLY' else old.month;year=old.year+(month>12)+(data.cadence=='YEARLY');month=(month-1)%12+1
        new=old.replace(year=year,month=month,day=min(old.day,calendar.monthrange(year,month)[1]))
    row.due_at=new;row.cadence=data.cadence;row.remind_at=None;db.commit()
    return {'due_at':new,'status':'EXPECTED_ONLY','payment_recorded':False,'explanation':'Next tracked renewal updated. No charge or repayment recorded.'}

def supplemental_notices(db):
    now=datetime.now(timezone.utc);result=[]
    for row in db.scalars(select(TrackedBill).where(TrackedBill.user_id=='demo-user',TrackedBill.active.is_(True))):
        if row.remind_at and utc(row.remind_at)<=now and utc(row.due_at)>now:
            result.append({'id':f'bill:{row.id}:{utc(row.due_at).isoformat()}','title':f'{row.merchant} reminder','message':'Your manually tracked expected expense is approaching. This is not a confirmed charge.','section':'Needs Review','created_at':utc(row.remind_at),'destination':'bills','category':'planning'})
    for row in db.scalars(select(PaymentIntakeRecord).where(PaymentIntakeRecord.user_id=='demo-user',PaymentIntakeRecord.status=='SAVED')):
        if row.remind_at and utc(row.remind_at)<=now and (not row.deadline or utc(row.deadline)>now):
            result.append({'id':'intake:'+row.id,'title':row.merchant,'message':'Review saved imported checkout details. Merchant and amount are unverified; no payment has been made.','section':'Needs Review','created_at':utc(row.remind_at),'destination':'payments','category':'planning'})
    return result

@router.get('/insights')
def insights(db=Depends(get_db)):
    from .reminders import attention_data
    from .services import balances,wallet
    attention=attention_data(db)['items'];urgent=[r for r in attention if r['stage']=='URGENT' and not r['explicit_hold']]
    bill_totals={};now=datetime.now(timezone.utc)
    for row in db.scalars(select(TrackedBill).where(TrackedBill.user_id=='demo-user',TrackedBill.active.is_(True))):
        if now<=utc(row.due_at)<=now+timedelta(days=30):bill_totals[row.currency]=bill_totals.get(row.currency,0)+row.amount
    w=wallet(db);available=balances(db,w)['available_balance'];totals={}
    for r in attention:
        if r['stage']!='EXPIRED' and not r['explicit_hold']:totals[r['currency']]=totals.get(r['currency'],0)+r['amount']
    seen={};duplicates=[]
    for p in db.scalars(select(PaymentRequest).where(PaymentRequest.status=='PENDING')):
        k=(p.merchant.casefold(),p.description.casefold(),p.amount,p.currency)
        if k in seen:duplicates.append([seen[k],p.id])
        else:seen[k]=p.id
    db.rollback();return {'mode':'backend-derived, no model inference','urgent_ids':[r['payment_id'] for r in urgent],
                         'expected_30_day_bills_by_currency':bill_totals,'pending_by_currency':totals,
                         'wallet_shortfall':max(0,totals.get(w.currency,0)-available),'wallet_currency':w.currency,
                         'possible_duplicate_ids':duplicates,'duplicates_are_not_confirmed':True}

@router.get('/documents')
def catalog(q:str='',kind:str='ALL',db=Depends(get_db)):
    if len(q)>120 or kind not in {'ALL','PAYMENT','BATCH','UPLOAD','REFUND'}:raise HTTPException(422,'Invalid document search')
    rows=[]
    if kind in {'ALL','PAYMENT','REFUND'}:
        for a,p in db.execute(select(PaymentAttempt,PaymentRequest).join(PaymentRequest,PaymentRequest.id==PaymentAttempt.payment_request_id).order_by(PaymentAttempt.created_at.desc()).limit(100)):
            if kind=='REFUND' and a.status!='REFUNDED':continue
            from .documents import attempt_record
            try:evidence=attempt_record(db,a.id)
            except HTTPException as error:
                if error.status_code==404:continue
                raise
            rows.append({**evidence,'id':a.id,'kind':'REFUND' if a.status=='REFUNDED' else 'PAYMENT','title':p.merchant+' · '+p.description,'created_at':utc(a.created_at),'reference':a.provider_reference or a.id,'download_url':f'/api/product/documents/attempts/{a.id}.pdf','trust':'RECORDED_ATTEMPT_NOT_NECESSARILY_SETTLED'})
    if kind in {'ALL','BATCH'}:
        for b in db.scalars(select(PaymentBatch).where(PaymentBatch.user_id=='demo-user').order_by(PaymentBatch.created_at.desc()).limit(100)):
            rows.append({'id':b.id,'kind':'BATCH','title':'Batch statement '+', '.join(i['merchant'] for i in b.snapshot['items']),'status':b.status,'created_at':utc(b.created_at),'reference':b.id,'download_url':f'/api/product/documents/batches/{b.id}.pdf','trust':'SIMULATED_WALLET'})
    if kind in {'ALL','UPLOAD'}:
        for d in db.scalars(select(DocumentRecord).where(DocumentRecord.user_id=='demo-user')):
            rows.append({'id':d.id,'kind':'UPLOAD','title':d.title,'status':'UNVERIFIED','created_at':utc(d.created_at),'reference':d.digest,'payment_id':d.payment_request_id,'download_url':f'/api/product/uploads/{d.id}/download','trust':'USER_UPLOADED_NOT_PAYMENT_PROOF'})
    needles={q.casefold()}
    if q.casefold() in {'train','rail','train ticket'}:needles={'train','rail'}
    rows=[r for r in rows if any(needle in f"{r['title']} {r['reference']} {r['created_at']}".casefold() for needle in needles)]
    rows.sort(key=lambda r:r['created_at'],reverse=True);return rows

@router.get('/saved-recipients')
def saved_recipients(q:str='',db=Depends(get_db)):
    return [{'id':r.id,'name':r.name,'handle':r.handle,'verified':r.verified} for r in db.scalars(select(Recipient).where(Recipient.user_id=='demo-user')) if q.casefold() in f'{r.name} {r.handle}'.casefold()]
