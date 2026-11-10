"""Server-only PayPal Orders v2 adapter. External Checkout never posts wallet journals."""
import asyncio
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP,InvalidOperation
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core import settings
from .models import PayPalOrder,PayPalWebhookEvent,PaymentAttempt,PaymentRequest
from .services import emit,wallet,utc

class PayPalError(ValueError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable
_token:tuple[str,datetime]|None=None
_lock=asyncio.Lock()
def configured():
    s=settings();return s.paypal_enabled and s.paypal_mode=="sandbox" and s.paypal_base_url.rstrip('/')=="https://api-m.sandbox.paypal.com" and bool(s.paypal_client_id and s.paypal_client_secret)
def currency_amount(amount_minor:int,original_currency:str)->tuple[str,str,str|None]:
    s=settings(); target=s.paypal_checkout_currency.upper(); original=original_currency.upper()
    if target==original:return f"{Decimal(amount_minor)/100:.2f}",target,None
    if original!="INR" or target!="USD":raise PayPalError("Configured PayPal currency conversion is unsupported")
    try:rate=Decimal(s.paypal_demo_inr_per_usd)
    except InvalidOperation as e:raise PayPalError("Invalid Sandbox conversion rate") from e
    if not rate.is_finite() or rate<=0:raise PayPalError("Invalid Sandbox conversion rate")
    usd=(Decimal(amount_minor)/Decimal(100)/rate).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    if usd<=0:raise PayPalError("Amount is too small for Sandbox conversion")
    return f"{usd:.2f}","USD",str(rate)
async def access_token():
    global _token
    s=settings()
    if not configured():raise PayPalError("PayPal Sandbox is not configured")
    if _token and _token[1]>datetime.now(timezone.utc)+timedelta(seconds=s.paypal_oauth_refresh_buffer_seconds):return _token[0]
    async with _lock:
        if _token and _token[1]>datetime.now(timezone.utc)+timedelta(seconds=s.paypal_oauth_refresh_buffer_seconds):return _token[0]
        try:
            async with httpx.AsyncClient(timeout=s.paypal_http_timeout_seconds) as client:r=await client.post(f"{s.paypal_base_url.rstrip('/')}/v1/oauth2/token",auth=(s.paypal_client_id,s.paypal_client_secret),data={"grant_type":"client_credentials"},headers={"Accept":"application/json"});r.raise_for_status();body=r.json()
        except httpx.HTTPStatusError as e:raise PayPalError("PayPal authentication failed",retryable=e.response.status_code>=500 or e.response.status_code==429) from e
        except httpx.HTTPError as e:raise PayPalError("PayPal is unavailable",retryable=True) from e
        except ValueError as e:raise PayPalError("PayPal returned an unreadable authentication response",retryable=True) from e
        try:token=body.get("access_token");expires=int(body.get("expires_in",0))
        except (ValueError,TypeError,AttributeError) as e:raise PayPalError("PayPal returned an invalid token response") from e
        if not token or expires<=0:raise PayPalError("PayPal returned an invalid token response")
        _token=(token,datetime.now(timezone.utc)+timedelta(seconds=expires));return token
async def browser_client_token():
    """Legacy browser-safe token endpoint; one-time checkout uses client ID."""
    s=settings()
    if not configured():raise PayPalError("PayPal Sandbox is not configured")
    try:
        async with httpx.AsyncClient(timeout=s.paypal_http_timeout_seconds) as client:r=await client.post(f"{s.paypal_base_url.rstrip('/')}/v1/oauth2/token",auth=(s.paypal_client_id,s.paypal_client_secret),data={"grant_type":"client_credentials","response_type":"client_token"},headers={"Accept":"application/json"});r.raise_for_status();token=r.json().get("access_token")
    except httpx.HTTPError as e:raise PayPalError("PayPal client token request failed") from e
    if not token:raise PayPalError("PayPal did not return a browser token")
    return token
async def request(method:str,path:str,*,payload:dict|None=None,request_id:str|None=None):
    s=settings();token=await access_token();headers={"Authorization":f"Bearer {token}","Content-Type":"application/json","Prefer":"return=representation"}
    if request_id:headers["PayPal-Request-Id"]=request_id
    try:
        async with httpx.AsyncClient(timeout=s.paypal_http_timeout_seconds) as client:r=await client.request(method,f"{s.paypal_base_url.rstrip('/')}{path}",headers=headers,json=payload);r.raise_for_status();return r.json()
    except httpx.HTTPStatusError as e:raise PayPalError("PayPal rejected the request; check the existing order before retrying",retryable=e.response.status_code>=500 or e.response.status_code in {409,429}) from e
    except httpx.HTTPError as e:raise PayPalError("PayPal is unavailable; the payment outcome is not yet known",retryable=True) from e
    except ValueError as e:raise PayPalError("PayPal returned an unreadable response",retryable=True) from e
def serialise(order:PayPalOrder):return {"order_id":order.paypal_order_id,"payment_request_id":order.payment_request_id,"original_amount":order.original_amount,"original_currency":order.original_currency,"provider_amount":order.provider_amount,"provider_currency":order.provider_currency,"demo_conversion_rate":order.conversion_rate,"status":order.provider_status,"capture_id":order.paypal_capture_id,"payment_source":"PAYPAL_SANDBOX"}
async def create_order(db:Session,payment_id:str):
    wallet(db,True)
    p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==payment_id).with_for_update())
    if not p:raise PayPalError("Payment request was not found")
    snapshot=(p.trace or {}).get('paypal_create')
    existing=db.scalar(select(PayPalOrder).where(PayPalOrder.payment_request_id==p.id).order_by(PayPalOrder.created_at.desc()))
    if existing:
        result=serialise(existing);db.rollback();return result
    if p.status=="SUCCEEDED":raise PayPalError("Payment request is already paid")
    if p.explicit_hold:raise PayPalError("Payment request is on hold")
    if not snapshot and p.expires_at and utc(p.expires_at)<=datetime.now(timezone.utc):raise PayPalError("Payment request has expired")
    if p.category=="person_to_person":raise PayPalError("PayPal Checkout cannot transfer money to this recipient")
    active=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==p.id,PaymentAttempt.status.in_(["PROCESSING","SUCCEEDED"])).with_for_update())
    if active and active.idempotency_key!=f"paypal-claim:{p.id}":raise PayPalError("This payment is already being processed")
    key=f"paypal-create:{p.id}"
    claim=db.scalar(select(PaymentAttempt).where(PaymentAttempt.idempotency_key==f"paypal-claim:{p.id}"))
    if claim and not snapshot:
        raise PayPalError("An earlier PayPal attempt needs manual reconciliation before retrying")
    if snapshot:
        # Freeze the original request across ambiguous retries. Stop before the
        # provider's default six-hour idempotency retention can elapse.
        if datetime.now(timezone.utc)-datetime.fromisoformat(snapshot['started_at'])>timedelta(hours=5):
            raise PayPalError("PayPal creation is unresolved; reconcile it before trying another payment")
        body=snapshot['body'];amount=snapshot['amount'];currency=snapshot['currency'];rate=snapshot['rate']
    else:
        amount,currency,rate=currency_amount(p.amount,p.currency)
        body={"intent":"CAPTURE","purchase_units":[{"reference_id":p.id,"custom_id":p.id,"invoice_id":f"AIW-{p.id[:20]}","description":p.description[:127],"amount":{"currency_code":currency,"value":amount}}]}
        p.trace={**(p.trace or {}),'paypal_create':{'body':body,'amount':amount,'currency':currency,'rate':rate,'started_at':datetime.now(timezone.utc).isoformat()}}
    if claim:claim.status="PROCESSING";claim.failure_reason=None
    else:claim=PaymentAttempt(payment_request_id=p.id,idempotency_key=f"paypal-claim:{p.id}",status="PROCESSING");db.add(claim)
    p.status="PROCESSING";db.flush();claim_id=claim.id;db.commit()
    try:remote=await request("POST","/v2/checkout/orders",payload=body,request_id=key)
    except PayPalError:
        # A timeout may hide a successful remote order. Retain ownership and
        # retry the same provider idempotency key; never fall back to wallet.
        raise
    order_id=remote.get("id") if isinstance(remote,dict) else None
    if not order_id:raise PayPalError("PayPal did not return an order ID")
    wallet(db,True)
    existing=db.scalar(select(PayPalOrder).where(PayPalOrder.idempotency_key==key))
    if existing:
        result=serialise(existing);db.rollback();return result
    p=db.get(PaymentRequest,payment_id)
    # A create response alone is never evidence that money was captured.
    order=PayPalOrder(payment_request_id=p.id,payment_attempt_id=claim_id,paypal_order_id=order_id,idempotency_key=key,original_amount=p.amount,original_currency=p.currency,provider_amount=amount,provider_currency=currency,conversion_rate=rate,provider_status="CREATED");db.add(order);db.flush()
    for event in db.scalars(select(PayPalWebhookEvent).where(PayPalWebhookEvent.paypal_order_id==order_id,PayPalWebhookEvent.verified.is_(True)).order_by(PayPalWebhookEvent.created_at)).all():
        apply_order_event(db,order,event.payload)
    emit(db,"paypal.order.created",{"payment_id":p.id,"order_id":order_id});db.commit();return serialise(order)
async def capture_order(db:Session,order_id:str):
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id))
    if not order:raise PayPalError("Unknown PayPal order")
    if order.provider_status in {"COMPLETED","REFUNDED","DENIED","DECLINED","FAILED"}:
        result=serialise(order);db.rollback();return result
    if order.provider_status=="PENDING":return await refresh_order(db,order_id)
    capture_key=f"paypal-capture:{order.id}";db.rollback()
    try:remote=await request("POST",f"/v2/checkout/orders/{order_id}/capture",payload={},request_id=capture_key)
    except PayPalError as error:
        # A lost response or duplicate approval may mean capture already happened.
        # GET reconciliation cannot create another charge.
        try:result=await refresh_order(db,order_id)
        except PayPalError:raise error
        if result['status'] in {'COMPLETED','PENDING','DENIED','DECLINED','FAILED','REFUNDED'}:return result
        raise error
    return record_order_response(db,order_id,remote)

def validate_amount(order,actual):
    try:
        value=Decimal(actual.get('value',''))
        valid=value.is_finite() and value==Decimal(order.provider_amount)
    except (InvalidOperation,ValueError,TypeError):valid=False
    if not valid or actual.get('currency_code')!=order.provider_currency:
        raise PayPalError('PayPal capture amount does not match the local order')

def record_capture(db,order,capture):
    validate_amount(order,capture.get('amount') or {})
    capture_id=capture.get('id');status=capture.get('status')
    if not capture_id or status not in {'COMPLETED','PENDING','DENIED','DECLINED','FAILED','REFUNDED'}:
        raise PayPalError('PayPal did not provide a supported capture result')
    if order.paypal_capture_id and order.paypal_capture_id!=capture_id:
        raise PayPalError('PayPal capture reference does not match the local order')
    if order.provider_status=='REFUNDED' or (order.provider_status=='COMPLETED' and status!='REFUNDED'):return
    if order.provider_status in {'DENIED','DECLINED','FAILED'} and status=='PENDING':return
    changed=order.provider_status!=status
    order.provider_status=status;order.paypal_capture_id=capture_id
    payment=db.get(PaymentRequest,order.payment_request_id)
    attempt=db.get(PaymentAttempt,order.payment_attempt_id) if order.payment_attempt_id else None
    if status=='COMPLETED':
        order.captured_at=order.captured_at or datetime.now(timezone.utc);payment.status='SUCCEEDED'
        if attempt:attempt.status='SUCCEEDED';attempt.provider_reference=capture_id;attempt.failure_reason=None
    elif status in {'DENIED','DECLINED','FAILED'}:
        payment.status='FAILED'
        if attempt:attempt.status='FAILED';attempt.failure_reason=f'PAYPAL_{status}'
    elif status=='REFUNDED':
        payment.status='REFUNDED'
        if attempt:attempt.status='REFUNDED';attempt.failure_reason=None
    if changed:emit(db,'paypal.payment.updated',{'payment_id':payment.id,'order_id':order.paypal_order_id,'status':status})

def record_order_response(db,order_id,remote):
    if not isinstance(remote,dict) or remote.get('id')!=order_id:
        raise PayPalError('PayPal order reference does not match the local order')
    units=remote.get('purchase_units') or []
    if len(units)!=1:raise PayPalError('PayPal returned an unexpected purchase-unit count')
    captures=(units[0].get('payments') or {}).get('captures') or []
    if len(captures)!=1:raise PayPalError('PayPal did not confirm a single payment capture')
    wallet(db,True)
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id).with_for_update().execution_options(populate_existing=True))
    record_capture(db,order,captures[0])
    db.commit();return serialise(order)

async def refresh_order(db:Session,order_id:str):
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id))
    if not order:raise PayPalError('Unknown PayPal order')
    if order.provider_status in {'COMPLETED','REFUNDED','DENIED','DECLINED','FAILED'}:
        result=serialise(order);db.rollback();return result
    capture_id=order.paypal_capture_id;db.rollback()
    if capture_id:
        capture=await request('GET',f'/v2/payments/captures/{capture_id}')
        wallet(db,True)
        order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id).with_for_update().execution_options(populate_existing=True))
        record_capture(db,order,capture);db.commit();return serialise(order)
    remote=await request('GET',f'/v2/checkout/orders/{order_id}')
    if not isinstance(remote,dict) or remote.get('id')!=order_id:raise PayPalError('PayPal order reference does not match the local order')
    if any((unit.get('payments') or {}).get('captures') for unit in remote.get('purchase_units',[])):
        return record_order_response(db,order_id,remote)
    if remote.get('status')=='COMPLETED':raise PayPalError('PayPal order has no verifiable capture')
    wallet(db,True)
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id).with_for_update().execution_options(populate_existing=True))
    if order.provider_status in {'CREATED','AWAITING_BUYER_APPROVAL'} and remote.get('status')=='APPROVED':order.provider_status='APPROVED'
    db.commit();return serialise(order)
async def verify_webhook(headers,body:dict):
    s=settings()
    if not configured() or not s.paypal_webhook_id:raise PayPalError("PayPal webhooks are not configured")
    if not isinstance(body,dict) or not all(headers.get(name) for name in ('paypal-auth-algo','paypal-cert-url','paypal-transmission-id','paypal-transmission-sig','paypal-transmission-time')):return False
    payload={"auth_algo":headers.get("paypal-auth-algo"),"cert_url":headers.get("paypal-cert-url"),"transmission_id":headers.get("paypal-transmission-id"),"transmission_sig":headers.get("paypal-transmission-sig"),"transmission_time":headers.get("paypal-transmission-time"),"webhook_id":s.paypal_webhook_id,"webhook_event":body}
    answer=await request("POST","/v1/notifications/verify-webhook-signature",payload=payload)
    return answer.get("verification_status")=="SUCCESS"
def apply_order_event(db,order,event):
    event_type=event['event_type'];resource=event.get('resource') or {}
    if event_type=='CHECKOUT.ORDER.APPROVED':
        if order.provider_status in {'CREATED','AWAITING_BUYER_APPROVAL'}:order.provider_status='APPROVED'
    elif event_type in {'PAYMENT.CAPTURE.COMPLETED','PAYMENT.CAPTURE.PENDING','PAYMENT.CAPTURE.DENIED'}:
        record_capture(db,order,{**resource,'status':event_type.rsplit('.',1)[-1]})
    elif event_type=='PAYMENT.CAPTURE.REFUNDED':
        # Refund resources have their own ID. Only a full matching refund is
        # represented here; partial refunds require capture reconciliation.
        validate_amount(order,resource.get('amount') or {})
        order.provider_status='REFUNDED';db.get(PaymentRequest,order.payment_request_id).status='REFUNDED'
        attempt=db.get(PaymentAttempt,order.payment_attempt_id) if order.payment_attempt_id else None
        if attempt:attempt.status='REFUNDED';attempt.failure_reason=None
        emit(db,'paypal.payment.updated',{'payment_id':order.payment_request_id,'order_id':order.paypal_order_id,'status':'REFUNDED'})

def apply_webhook(db:Session,event:dict):
    wallet(db,True)
    event_id=event.get("id");event_type=event.get("event_type","");resource=event.get("resource") or {};order_id=resource.get("supplementary_data",{}).get("related_ids",{}).get("order_id") or resource.get("id") if event_type.startswith("CHECKOUT.ORDER") else resource.get("supplementary_data",{}).get("related_ids",{}).get("order_id")
    if not event_id or not event_type:raise PayPalError("Webhook event ID or type is missing")
    if db.scalar(select(PayPalWebhookEvent).where(PayPalWebhookEvent.paypal_event_id==event_id)):
        db.rollback();return
    db.add(PayPalWebhookEvent(paypal_event_id=event_id,event_type=event_type,paypal_order_id=order_id,verified=True,payload=event));order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id)) if order_id else None
    if not order and event_type=='PAYMENT.CAPTURE.REFUNDED':
        capture_id=resource.get('supplementary_data',{}).get('related_ids',{}).get('capture_id')
        if capture_id:order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_capture_id==capture_id))
    if order:
        try:apply_order_event(db,order,event)
        except PayPalError:db.rollback();raise
        emit(db,"paypal.webhook",{"order_id":order.paypal_order_id,"event_type":event_type})
    db.commit()
