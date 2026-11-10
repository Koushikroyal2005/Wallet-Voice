"""Small authenticated, polling-first simulated merchant contract. No callbacks."""
import hashlib
import hmac
import secrets
from datetime import datetime,timedelta,timezone
from fastapi import APIRouter,Depends,Header,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,func
from .db import get_db
from .models import MerchantIdentity,MerchantOrder,PaymentRequest,Operation,JournalTransaction,PayPalOrder
from .services import wallet,utc,emit,transition,FinancialError

router=APIRouter(prefix='/api/merchant/v1',tags=['Simulated merchant checkout'])

def provision(db,ident,name):
    """Operator-only provisioning: return a generated secret once; persist only hash."""
    if db.get(MerchantIdentity,ident):raise ValueError('Merchant already exists; credentials are not recoverable')
    token=secrets.token_urlsafe(32)
    db.add(MerchantIdentity(id=ident,name=name,secret_hash=hashlib.sha256(token.encode()).hexdigest()))
    db.flush()
    return token

def authenticate(x_merchant_id:str=Header(max_length=120),x_merchant_key:str=Header(max_length=256),db=Depends(get_db)):
    row=db.get(MerchantIdentity,x_merchant_id)
    digest=hashlib.sha256(x_merchant_key.encode()).hexdigest()
    if not hmac.compare_digest(row.secret_hash if row else '0'*64,digest) or not row or not row.active:
        raise HTTPException(401,'Merchant authentication failed')
    return row

class Checkout(BaseModel):
    order_reference:str=Field(min_length=3,max_length=160,pattern=r'^[a-zA-Z0-9_-]+$')
    amount:int=Field(gt=0,le=10_000_000,strict=True)
    currency:str=Field(pattern='^INR$')
    description:str=Field(min_length=1,max_length=500)
    expires_at:datetime
    @field_validator('expires_at')
    @classmethod
    def timezone_required(cls,value):
        if value.tzinfo is None:raise ValueError('Include an explicit timezone')
        return value.astimezone(timezone.utc)

def owned(db,merchant,reference=None,ident=None):
    query=select(MerchantOrder).where(MerchantOrder.merchant_id==merchant.id)
    query=query.where(MerchantOrder.reference==reference) if reference is not None else query.where(MerchantOrder.payment_request_id==ident)
    row=db.scalar(query)
    if not row:raise HTTPException(404,'Order not found')
    return row

def result(db,order):
    p=db.get(PaymentRequest,order.payment_request_id)
    status=p.status
    if status=='SUCCEEDED':
        op=db.scalar(select(Operation).where(Operation.idempotency_key==f'payment:{p.id}',Operation.status=='SUCCEEDED'))
        journal=db.scalar(select(JournalTransaction).where(JournalTransaction.operation_id==op.id)) if op else None
        capture=db.scalar(select(PayPalOrder).where(PayPalOrder.payment_request_id==p.id,PayPalOrder.provider_status=='COMPLETED',PayPalOrder.paypal_capture_id.is_not(None)))
        if not journal and not capture:status='PROCESSING'
    if status in {'PENDING','HELD','FAILED'} and p.expires_at and utc(p.expires_at)<=datetime.now(timezone.utc):status='EXPIRED'
    state='FULFILLED' if order.fulfilled_at else {'SUCCEEDED':'PAYMENT_CONFIRMED','PROCESSING':'PAYMENT_PROCESSING','FAILED':'PAYMENT_FAILED','EXPIRED':'EXPIRED','CANCELLED':'CANCELLED','REFUNDED':'REFUNDED'}.get(status,'PENDING_PAYMENT')
    return {'payment_request_id':p.id,'merchant_id':order.merchant_id,'merchant_order_reference':order.reference,'merchant':p.merchant,'amount':p.amount,'currency':p.currency,'payment_status':status,'order_status':state,'fulfilled_at':utc(order.fulfilled_at) if order.fulfilled_at else None,'expires_at':utc(p.expires_at),'review_url':f'/?review={p.id}','mode':'SIMULATED'}

@router.post('/checkout-requests')
def create(data:Checkout,merchant=Depends(authenticate),idempotency_key:str=Header(min_length=8,max_length=160),db=Depends(get_db)):
    wallet(db,True) # Single-owner demo lock also serializes reference/idempotency checks.
    old=db.scalar(select(MerchantOrder).where(MerchantOrder.merchant_id==merchant.id,MerchantOrder.idempotency_key==idempotency_key))
    by_reference=db.scalar(select(MerchantOrder).where(MerchantOrder.merchant_id==merchant.id,MerchantOrder.reference==data.order_reference))
    if old or by_reference:
        row=old or by_reference;p=db.get(PaymentRequest,row.payment_request_id)
        if row.reference!=data.order_reference or row.idempotency_key!=idempotency_key or (p.amount,p.currency,p.description,utc(p.expires_at))!=(data.amount,data.currency,data.description,data.expires_at):raise HTTPException(409,'Reference or idempotency key conflicts with the original immutable request')
        return result(db,row)
    now=datetime.now(timezone.utc)
    if not now<data.expires_at<=now+timedelta(days=30):raise HTTPException(422,'Expiry must be in the next 30 days')
    # Durable bounded ingestion avoids an unbounded in-memory rate-limit map.
    count=db.scalar(select(func.count()).select_from(PaymentRequest).where(PaymentRequest.provider==f'MERCHANT:{merchant.id}',PaymentRequest.created_at>now-timedelta(minutes=1)))
    if count>=30:raise HTTPException(429,'Merchant request rate exceeded')
    p=PaymentRequest(merchant=merchant.name,category='merchant_checkout',description=data.description,amount=data.amount,currency=data.currency,expires_at=data.expires_at,verified=True,provider=f'MERCHANT:{merchant.id}',trace={'merchant_id':merchant.id,'order_reference':data.order_reference,'simulation':True})
    db.add(p);db.flush()
    order=MerchantOrder(merchant_id=merchant.id,reference=data.order_reference,idempotency_key=idempotency_key,payment_request_id=p.id)
    db.add(order);db.flush();emit(db,'payment.created',{'payment_id':p.id});db.commit()
    return result(db,order)

@router.get('/checkout-requests/{ident}')
def read(ident:str,merchant=Depends(authenticate),db=Depends(get_db)):return result(db,owned(db,merchant,ident=ident))

@router.get('/orders/{reference}')
def read_order(reference:str,merchant=Depends(authenticate),db=Depends(get_db)):return result(db,owned(db,merchant,reference=reference))

@router.post('/orders/{reference}/fulfillment')
def fulfill(reference:str,merchant=Depends(authenticate),db=Depends(get_db)):
    wallet(db,True)
    order=owned(db,merchant,reference=reference)
    if result(db,order)['payment_status']!='SUCCEEDED':raise HTTPException(409,'Payment must be confirmed before fulfillment')
    if not order.fulfilled_at:
        order.fulfilled_at=datetime.now(timezone.utc);emit(db,'merchant.fulfillment.confirmed',{'merchant_id':merchant.id,'payment_id':order.payment_request_id,'order_id':order.id})
    db.commit();return result(db,order)

@router.post('/orders/{reference}/cancel')
def cancel(reference:str,merchant=Depends(authenticate),db=Depends(get_db)):
    wallet(db,True);order=owned(db,merchant,reference=reference)
    p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==order.payment_request_id).with_for_update())
    if p.status=='CANCELLED':return result(db,order)
    if p.status not in {'PENDING','HELD','FAILED'}:raise HTTPException(409,'Submitted or settled payments cannot be cancelled by the merchant')
    try:transition(p,'CANCELLED')
    except FinancialError as error:raise HTTPException(409,str(error))
    emit(db,'payment.cancelled',{'payment_id':p.id});db.commit();return result(db,order)
