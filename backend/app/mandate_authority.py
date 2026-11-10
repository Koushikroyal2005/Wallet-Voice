"""Stable authenticated recipient binding; no name-to-identity authority migration."""
from datetime import datetime,timezone
from sqlalchemy import select
from .models import MerchantIdentity,AuthorizationChallenge
from .core import settings

def utc(value):return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def evidence(db,mandate):
    resource=mandate.merchant_id or mandate.merchant
    details={'merchant':mandate.merchant,'daily_limit':mandate.daily_limit,'expires_at':int(utc(mandate.expires_at).timestamp())}
    if mandate.merchant_id:details['merchant_id']=mandate.merchant_id
    return any(c.details==details for c in db.scalars(select(AuthorizationChallenge).where(AuthorizationChallenge.user_id==mandate.user_id,AuthorizationChallenge.action=='MANDATE',AuthorizationChallenge.resource_id==resource,AuthorizationChallenge.amount==mandate.max_amount,AuthorizationChallenge.status=='CONSUMED')))

def recipient_matches(db,mandate,payment):
    ident=(payment.trace or {}).get('merchant_id')
    if ident:
        merchant=db.get(MerchantIdentity,ident)
        return bool(mandate.merchant_id==ident and merchant and merchant.active and merchant.name==mandate.merchant==payment.merchant and payment.provider==f'MERCHANT:{ident}')
    # Legacy authority is confined to the configured single demo merchant path.
    # It never applies to a V2 identity, even if its display name is identical.
    return bool(not mandate.merchant_id and settings().demo_mode and payment.merchant==mandate.merchant==settings().demo_merchant_name and payment.provider.startswith('MERCHANT:'))

def valid_existing(db,mandate,payment):
    return bool(mandate and mandate.user_id=='demo-user' and mandate.status=='ACTIVE' and utc(mandate.expires_at)>datetime.now(timezone.utc) and mandate.max_amount>=payment.amount and recipient_matches(db,mandate,payment) and evidence(db,mandate))
