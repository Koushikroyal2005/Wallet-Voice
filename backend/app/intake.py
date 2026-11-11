"""Untrusted intake is saved separately from executable merchant requests. Never fetch a URL."""
import hashlib,ipaddress,json
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator,model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import PaymentIntakeRecord
from .services import utc
router=APIRouter(prefix='/api/product/intakes')

def safe_url(value):
    try:
        p=urlsplit(value.strip());host=p.hostname or '';port=p.port
        if p.scheme!='https' or not host or p.username or p.password or port not in (None,443) or len(value)>2048:raise ValueError()
        if host.lower() in {'localhost','localhost.localdomain'} or '.' not in host or host.endswith(('.local','.internal')):raise ValueError()
        try:address=ipaddress.ip_address(host)
        except ValueError:address=None
        if address and not address.is_global:raise ValueError()
        if address is None and all(c in '0123456789.:' for c in host):raise ValueError()
        if any(ord(c)<33 or c=='\\' for c in value):raise ValueError()
        return urlunsplit(('https',p.netloc.lower(),p.path,p.query,''))
    except (ValueError,TypeError):raise ValueError('Use an HTTPS checkout URL without login details, local addresses or unsafe characters')

class IntakeCreate(BaseModel):
    source_type:str=Field(default='MANUAL',pattern='^(MANUAL|LINK|QR|SHARE)$')
    source_url:str|None=None
    merchant:str=Field(min_length=1,max_length=120)
    description:str=Field(default='',max_length=500)
    amount:int=Field(gt=0,le=10_000_000)
    currency:str=Field(default='INR',pattern='^[A-Z]{3}$')
    deadline:datetime|None=None
    @field_validator('source_url')
    @classmethod
    def url(cls,value):return safe_url(value) if value else None
    @field_validator('merchant')
    @classmethod
    def name(cls,value):
        if not value.strip():raise ValueError('Enter the claimed merchant name')
        return value.strip()
    @field_validator('deadline')
    @classmethod
    def future(cls,value):
        if value and (not value.tzinfo or value<=datetime.now(timezone.utc)):raise ValueError('Choose a future deadline with timezone')
        return value
    @model_validator(mode='after')
    def source(self):
        if self.source_type!='MANUAL' and not self.source_url:raise ValueError('A link or QR import needs a safe HTTPS URL')
        return self

def view(row):
    expired=bool(row.deadline and utc(row.deadline)<=datetime.now(timezone.utc))
    return {'id':row.id,'merchant':row.merchant,'description':row.description,'amount':row.amount,'currency':row.currency,
            'deadline':utc(row.deadline) if row.deadline else None,'remind_at':utc(row.remind_at) if row.remind_at else None,
            'source_type':row.source_type,'source_url':row.source_url,'status':'EXPIRED' if expired else row.status,
            'trust':'IMPORTED_UNVERIFIED','can_pay':False,'created_at':row.created_at,
            'explanation':'Saved details only. Merchant identity, amount and destination have not been verified. Wallet-Voice cannot execute this imported checkout.'}

@router.get('')
def listing(db=Depends(get_db)):
    return [view(r) for r in db.scalars(select(PaymentIntakeRecord).where(PaymentIntakeRecord.user_id=='demo-user').order_by(PaymentIntakeRecord.created_at.desc()))]

@router.post('')
def save(data:IntakeCreate,db=Depends(get_db)):
    values=data.model_dump(mode='json');key=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
    row=db.scalar(select(PaymentIntakeRecord).where(PaymentIntakeRecord.user_id=='demo-user',PaymentIntakeRecord.dedupe_key==key))
    if not row:
        try:
            with db.begin_nested():row=PaymentIntakeRecord(**data.model_dump(),dedupe_key=key);db.add(row);db.flush()
        except IntegrityError:row=db.scalar(select(PaymentIntakeRecord).where(PaymentIntakeRecord.user_id=='demo-user',PaymentIntakeRecord.dedupe_key==key))
    db.commit();return view(row)

class IntakeAction(BaseModel):
    action:str=Field(pattern='^(HOLD|RESTORE|DISMISS|REMIND)$')
    remind_at:datetime|None=None

@router.post('/{ident}/state')
def change(ident:str,data:IntakeAction,db=Depends(get_db)):
    row=db.scalar(select(PaymentIntakeRecord).where(PaymentIntakeRecord.id==ident,PaymentIntakeRecord.user_id=='demo-user').with_for_update())
    if not row:raise HTTPException(404,'Imported checkout not found')
    if data.action=='REMIND':
        if not data.remind_at or not data.remind_at.tzinfo or data.remind_at<=datetime.now(timezone.utc) or row.deadline and data.remind_at>=utc(row.deadline):raise HTTPException(422,'Choose a future reminder before the deadline')
        if row.status!='SAVED':raise HTTPException(409,'Restore this checkout before setting a reminder')
        row.remind_at=data.remind_at
    else:
        row.status={'HOLD':'HELD','RESTORE':'SAVED','DISMISS':'DISMISSED'}[data.action]
        if row.status!='SAVED':row.remind_at=None
    db.commit();return view(row)
