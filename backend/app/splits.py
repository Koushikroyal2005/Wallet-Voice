"""Exact split previews create requests only after explicit confirmation, never debits."""
import hashlib,json
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import Recipient,SplitGroup,SplitParticipant,MoneyRequest
from .services import emit
router=APIRouter(prefix='/api/product/splits')
class SplitInput(BaseModel):
    amount:int=Field(gt=0,le=10_000_000)
    participants:list[str]=Field(min_length=2,max_length=20)
    note:str=Field(default='',max_length=500)
class ConfirmSplit(SplitInput):
    snapshot_hash:str=Field(min_length=64,max_length=64)
    request_key:str=Field(min_length=8,max_length=80)
    confirmed:bool

def preview(db,data):
    names=[n.strip() for n in data.participants]
    if names.count('me')!=1 or len(set(n.casefold() for n in names))!=len(names) or data.amount<len(names):raise HTTPException(422,'Include me once and distinct saved recipients; each share must be at least one paisa')
    recipients=list(db.scalars(select(Recipient).where(Recipient.user_id=='demo-user')))
    base,remainder=divmod(data.amount,len(names));rows=[]
    for pos,name in enumerate(names):
        matches=[r for r in recipients if name.casefold() in {r.name.casefold(),r.handle.casefold()}]
        if name!='me' and len(matches)!=1:raise HTTPException(409,'A split participant is unknown or ambiguous. Use an exact saved name or handle.')
        rows.append({'position':pos,'name':'You' if name=='me' else matches[0].name,'recipient_id':None if name=='me' else matches[0].id,'amount':base+(pos<remainder)})
    digest=hashlib.sha256(json.dumps({'amount':data.amount,'note':data.note,'participants':rows},sort_keys=True).encode()).hexdigest()
    return {'amount':data.amount,'currency':'INR','participants':rows,'rounding_paise':remainder,'snapshot_hash':digest,'requires_confirmation':True,'moves_money':False}

def group_view(db,row):
    parts=[]
    for p in db.scalars(select(SplitParticipant).where(SplitParticipant.group_id==row.id).order_by(SplitParticipant.position)):
        request=db.get(MoneyRequest,p.request_id) if p.request_id else None
        parts.append({'name':p.name,'amount':p.amount,'request_id':p.request_id,'status':request.status if request else 'YOUR_SHARE'})
    return {'id':row.id,'amount':row.amount,'currency':'INR','note':row.note,'participants':parts,'received_amount':0,
            'outstanding_amount':sum(p['amount'] for p in parts if p['status']=='REQUESTED'),'simulated':True,
            'explanation':'Requests created, not transfers. No repayments have been provider-confirmed.'}

@router.post('/preview')
def prepare(data:SplitInput,db=Depends(get_db)):return preview(db,data)
@router.get('')
def listing(db=Depends(get_db)):
    return [group_view(db,r) for r in db.scalars(select(SplitGroup).where(SplitGroup.user_id=='demo-user').order_by(SplitGroup.created_at.desc()))]
@router.post('')
def confirm(data:ConfirmSplit,db=Depends(get_db)):
    if not data.confirmed:raise HTTPException(403,'Review the exact split and confirm creating requests')
    old=db.scalar(select(SplitGroup).where(SplitGroup.user_id=='demo-user',SplitGroup.request_key==data.request_key))
    if old:
        if old.snapshot_hash!=data.snapshot_hash:raise HTTPException(409,'Request key belongs to another split')
        return group_view(db,old)
    result=preview(db,data)
    if result['snapshot_hash']!=data.snapshot_hash:raise HTTPException(409,'Participants or details changed; prepare a new split preview')
    created=False
    try:
        with db.begin_nested():
            row=SplitGroup(request_key=data.request_key,snapshot_hash=data.snapshot_hash,amount=data.amount,note=data.note);db.add(row);db.flush()
            for item in result['participants']:
                request=None
                if item['recipient_id']:
                    request=MoneyRequest(payer=item['name'],amount=item['amount'],note=data.note,request_key=f'split:{row.id}:{item["position"]}');db.add(request);db.flush()
                db.add(SplitParticipant(group_id=row.id,position=item['position'],name=item['name'],amount=item['amount'],request_id=request.id if request else None))
            db.flush()
            created=True
    except IntegrityError:
        row=db.scalar(select(SplitGroup).where(SplitGroup.user_id=='demo-user',SplitGroup.request_key==data.request_key))
        if not row or row.snapshot_hash!=data.snapshot_hash:raise HTTPException(409,'Split confirmation conflicted; refresh before retrying')
    if created:emit(db,'money.split.created',{'split_id':row.id})
    db.commit();return group_view(db,row)
