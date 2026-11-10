from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from .db import get_db,SessionLocal
from .execution import execute_attempt
from .services import FinancialError
from .authorization import AuthorizationError
from . import payment_batches as batches

router=APIRouter(prefix='/api/payment-batches')
class Selection(BaseModel):
    payment_ids:list[str]=Field(min_length=1,max_length=50)
    recognize_merchants:bool=False
class Pin(BaseModel):pin:str=Field(pattern=r'^\d{6}$')
class Approval(BaseModel):approval_token:str=Field(min_length=20,max_length=255)
class Acknowledgement(BaseModel):payment_id:str=Field(max_length=120)

@router.post('/{ident}/acknowledge')
def acknowledge(ident:str,data:Acknowledgement,db:Session=Depends(get_db)):
    try:
        old=batches.get_batch(db,ident,True)
        if old.status!='REVIEW':raise FinancialError('Prepare a new review first')
        batches.check_snapshot(db,old)
        ids=[p['id'] for p in old.snapshot['items']]
        if data.payment_id not in ids:raise FinancialError('Choose a merchant in this review')
        acknowledged=set(old.snapshot.get('acknowledged_ids',[]));acknowledged.add(data.payment_id)
        row=batches.create_batch(db,ids,old.snapshot['recognized'],acknowledged)
        old.status='CANCELLED';db.commit();return batches.view(db,row)
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))

@router.post('')
def preview(data:Selection,db:Session=Depends(get_db)):
    try:
        row=batches.create_batch(db,data.payment_ids,data.recognize_merchants);db.commit()
        return batches.view(db,row)
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))

@router.get('/{ident}')
def read(ident:str,db:Session=Depends(get_db)):
    try:return batches.view(db,batches.get_batch(db,ident))
    except FinancialError as e:raise HTTPException(404,str(e))

@router.post('/{ident}/authorize')
def authorize(ident:str,data:Pin,db:Session=Depends(get_db)):
    try:
        token=batches.authorize(db,batches.get_batch(db,ident,True),data.pin);db.commit()
        return {'approval_token':token}
    except AuthorizationError as e:db.commit();raise HTTPException(403,str(e))
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))

@router.post('/{ident}/confirm')
def confirm(ident:str,data:Approval):
    from . import main
    try:return batches.execute_batch(main.SessionLocal,ident,data.approval_token,execute_attempt)
    except (FinancialError,AuthorizationError) as e:raise HTTPException(409,str(e))

@router.post('/{ident}/cancel')
def cancel(ident:str,db:Session=Depends(get_db)):
    try:
        row=batches.get_batch(db,ident,True)
        if row.status!='REVIEW':raise FinancialError('Already submitted; check the recorded outcome')
        row.status='CANCELLED';db.commit();return batches.view(db,row)
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))
