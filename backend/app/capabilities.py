"""Capability descriptions do not authorize payment or invoke providers."""
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from .db import get_db
from .models import PaymentRequest
from .services import utc
router=APIRouter(prefix='/api/product/sources')
@router.get('/{payment_id}/eligibility')
def eligibility(payment_id:str,db=Depends(get_db)):
    from .main import payment_review
    from .paypal import configured,currency_amount,PayPalError
    p=db.get(PaymentRequest,payment_id)
    if not p:raise HTTPException(404,'Payment not found')
    facts={'category':p.category,'currency':p.currency,'amount':p.amount,'status':p.status,'hold':p.explicit_hold,'expired':bool(p.expires_at and utc(p.expires_at)<=datetime.now(timezone.utc))}
    review=payment_review(payment_id,db);reasons=[]
    if not configured():reasons.append('PayPal Sandbox is not configured')
    if facts['category']=='person_to_person':reasons.append('Checkout does not support recipient transfers')
    if not (review.get('merchant_identity') or {}).get('payable',True):reasons.append('Merchant identity is no longer valid')
    if facts['status']!='PENDING' or facts['hold'] or facts['expired']:reasons.append('Request is not open for a new checkout')
    quote=None
    try:
        value,currency,rate=currency_amount(facts['amount'],facts['currency']);quote={'provider_amount':value,'provider_currency':currency,'configured_demo_rate':rate,'live_fx_quote':False}
    except PayPalError as e:reasons.append(str(e))
    return {'wallet':{'decision':review['wallet_policy'],'requires':'Exact transaction-bound PIN','source':'SIMULATED'},
            'paypal':{'can_prepare':not reasons,'reasons':reasons,'approval_steps':1,'requires':'Separate PayPal buyer approval and provider-confirmed capture','internal_limits_apply':False,'quote':quote},
            'bank_card':{'can_prepare':False,'reasons':['No hosted bank/card provider is connected']}}
