"""Current authenticated sender facts, independent of historical verification flags."""
from sqlalchemy import select
from .models import MerchantIdentity,MerchantOrder

def current_identity(db,payment,lock=False):
    order=db.scalar(select(MerchantOrder).where(MerchantOrder.payment_request_id==payment.id))
    declared=(payment.trace or {}).get('merchant_id')
    ident=order.merchant_id if order else declared
    if not ident:
        # A damaged versioned checkout must never fall back to legacy trust.
        if payment.category=='merchant_checkout' and (payment.trace or {}).get('simulation') is True:return {'merchant_id':None,'state':'MISSING','verified':False,'payable':False}
        return {'merchant_id':None,'state':'LEGACY','verified':payment.verified,'payable':True}
    query=select(MerchantIdentity).where(MerchantIdentity.id==ident).execution_options(populate_existing=True)
    merchant=db.scalar(query.with_for_update() if lock else query)
    state='MISSING' if not merchant else 'REVOKED' if not merchant.active else 'MISMATCH' if declared!=ident or payment.provider!=f'MERCHANT:{ident}' or merchant.name!=payment.merchant else 'ACTIVE'
    return {'merchant_id':ident,'state':state,'verified':bool(payment.verified and state=='ACTIVE'),'payable':state=='ACTIVE'}
