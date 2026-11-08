"""Server-only PayPal Orders v2 adapter. External Checkout never posts wallet journals."""
import asyncio
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from uuid import uuid4
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core import settings
from .models import PayPalOrder,PayPalWebhookEvent,PaymentAttempt,PaymentRequest
from .services import emit,wallet,utc

class PayPalError(ValueError): pass
_token:tuple[str,datetime]|None=None
_lock=asyncio.Lock()
def configured():
    s=settings();return s.paypal_enabled and s.paypal_mode=="sandbox" and bool(s.paypal_client_id and s.paypal_client_secret)
def currency_amount(amount_minor:int,original_currency:str)->tuple[str,str,str|None]:
    s=settings(); target=s.paypal_checkout_currency.upper(); original=original_currency.upper()
    if target==original:return f"{Decimal(amount_minor)/100:.2f}",target,None
    if original!="INR" or target!="USD":raise PayPalError("Configured PayPal currency conversion is unsupported")
    rate=Decimal(s.paypal_demo_inr_per_usd)
    if rate<=0:raise PayPalError("Invalid Sandbox conversion rate")
    usd=(Decimal(amount_minor)/Decimal(100)/rate).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
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
        except httpx.HTTPStatusError as e:raise PayPalError("PayPal authentication failed") from e
        except httpx.HTTPError as e:raise PayPalError("PayPal is unavailable") from e
        token=body.get("access_token");expires=int(body.get("expires_in",0))
        if not token or expires<=0:raise PayPalError("PayPal returned an invalid token response")
        _token=(token,datetime.now(timezone.utc)+timedelta(seconds=expires));return token
async def browser_client_token():
    """Short-lived browser token required by the current JavaScript SDK v6."""
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
    except httpx.HTTPStatusError as e:raise PayPalError("PayPal rejected the request") from e
    except httpx.HTTPError as e:raise PayPalError("PayPal is unavailable") from e
def serialise(order:PayPalOrder):return {"order_id":order.paypal_order_id,"payment_request_id":order.payment_request_id,"original_amount":order.original_amount,"original_currency":order.original_currency,"provider_amount":order.provider_amount,"provider_currency":order.provider_currency,"demo_conversion_rate":order.conversion_rate,"status":order.provider_status,"capture_id":order.paypal_capture_id,"payment_source":"PAYPAL_SANDBOX"}
async def create_order(db:Session,payment_id:str):
    wallet(db,True)
    p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==payment_id).with_for_update())
    if not p:raise PayPalError("Payment request was not found")
    if p.status=="SUCCEEDED":raise PayPalError("Payment request is already paid")
    if p.explicit_hold:raise PayPalError("Payment request is on hold")
    if p.expires_at and utc(p.expires_at)<=datetime.now(timezone.utc):raise PayPalError("Payment request has expired")
    if p.category=="person_to_person":raise PayPalError("PayPal Checkout cannot transfer money to this recipient")
    existing=db.scalar(select(PayPalOrder).where(PayPalOrder.payment_request_id==p.id,PayPalOrder.provider_status.in_(["CREATED","AWAITING_BUYER_APPROVAL","APPROVED","PENDING"])).order_by(PayPalOrder.created_at.desc()))
    if existing:return serialise(existing)
    active=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==p.id,PaymentAttempt.status.in_(["PROCESSING","SUCCEEDED"])).with_for_update())
    if active and active.idempotency_key!=f"paypal-claim:{p.id}":raise PayPalError("This payment is already being processed")
    amount,currency,rate=currency_amount(p.amount,p.currency);key=f"paypal-create:{p.id}"
    body={"intent":"CAPTURE","purchase_units":[{"reference_id":p.id,"custom_id":p.id,"invoice_id":f"AIW-{p.id[:20]}","description":p.description[:127],"amount":{"currency_code":currency,"value":amount}}]}
    claim=db.scalar(select(PaymentAttempt).where(PaymentAttempt.idempotency_key==f"paypal-claim:{p.id}"))
    if claim:claim.status="PROCESSING";claim.failure_reason=None
    else:claim=PaymentAttempt(payment_request_id=p.id,idempotency_key=f"paypal-claim:{p.id}",status="PROCESSING");db.add(claim)
    p.status="PROCESSING";db.flush();claim_id=claim.id;db.commit()
    try:remote=await request("POST","/v2/checkout/orders",payload=body,request_id=key)
    except PayPalError:
        # A timeout may hide a successful remote order. Retain ownership and
        # retry the same provider idempotency key; never fall back to wallet.
        raise
    order_id=remote.get("id")
    if not order_id:raise PayPalError("PayPal did not return an order ID")
    wallet(db,True)
    existing=db.scalar(select(PayPalOrder).where(PayPalOrder.idempotency_key==key))
    if existing:return serialise(existing)
    p=db.get(PaymentRequest,payment_id)
    order=PayPalOrder(payment_request_id=p.id,payment_attempt_id=claim_id,paypal_order_id=order_id,idempotency_key=key,original_amount=p.amount,original_currency=p.currency,provider_amount=amount,provider_currency=currency,conversion_rate=rate,provider_status=remote.get("status","CREATED"));db.add(order);emit(db,"paypal.order.created",{"payment_id":p.id,"order_id":order_id});db.commit();return serialise(order)
async def capture_order(db:Session,order_id:str):
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id))
    if not order:raise PayPalError("Unknown PayPal order")
    if order.provider_status=="COMPLETED":return serialise(order)
    capture_key=f"paypal-capture:{order.id}";db.rollback()
    remote=await request("POST",f"/v2/checkout/orders/{order_id}/capture",payload={},request_id=capture_key)
    wallet(db,True)
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id).with_for_update().execution_options(populate_existing=True))
    if order.provider_status in {"COMPLETED","REFUNDED"}:return serialise(order)
    unit=(remote.get("purchase_units") or [{}])[0]; capture=((unit.get("payments") or {}).get("captures") or [{}])[0]; actual=capture.get("amount") or {}
    if actual.get("value")!=order.provider_amount or actual.get("currency_code")!=order.provider_currency:raise PayPalError("PayPal capture amount does not match the local order")
    status=capture.get("status") or remote.get("status","");order.provider_status=status;order.paypal_capture_id=capture.get("id")
    p=db.get(PaymentRequest,order.payment_request_id)
    if status=="COMPLETED":
        order.captured_at=datetime.now(timezone.utc);p.status="SUCCEEDED"
        if order.payment_attempt_id:
            attempt=db.get(PaymentAttempt,order.payment_attempt_id);attempt.status="SUCCEEDED";attempt.provider_reference=order.paypal_capture_id
        emit(db,"paypal.payment.completed",{"payment_id":p.id,"order_id":order_id,"capture_id":order.paypal_capture_id})
    elif status in {"PENDING","DENIED"}:
        if status=='DENIED':
            p.status='FAILED'
            if order.payment_attempt_id:
                attempt=db.get(PaymentAttempt,order.payment_attempt_id);attempt.status='FAILED';attempt.failure_reason='PAYPAL_DENIED'
        emit(db,"paypal.payment.updated",{"payment_id":p.id,"order_id":order_id,"status":status})
    else:raise PayPalError("PayPal did not confirm payment capture")
    db.commit();return serialise(order)
async def verify_webhook(headers,body:dict):
    s=settings()
    if not configured() or not s.paypal_webhook_id:raise PayPalError("PayPal webhooks are not configured")
    payload={"auth_algo":headers.get("paypal-auth-algo"),"cert_url":headers.get("paypal-cert-url"),"transmission_id":headers.get("paypal-transmission-id"),"transmission_sig":headers.get("paypal-transmission-sig"),"transmission_time":headers.get("paypal-transmission-time"),"webhook_id":s.paypal_webhook_id,"webhook_event":body}
    answer=await request("POST","/v1/notifications/verify-webhook-signature",payload=payload)
    return answer.get("verification_status")=="SUCCESS"
def apply_webhook(db:Session,event:dict):
    wallet(db,True)
    event_id=event.get("id");event_type=event.get("event_type","");resource=event.get("resource") or {};order_id=resource.get("supplementary_data",{}).get("related_ids",{}).get("order_id") or resource.get("id") if event_type.startswith("CHECKOUT.ORDER") else resource.get("supplementary_data",{}).get("related_ids",{}).get("order_id")
    if not event_id:raise PayPalError("Webhook event ID is missing")
    if db.scalar(select(PayPalWebhookEvent).where(PayPalWebhookEvent.paypal_event_id==event_id)):return
    db.add(PayPalWebhookEvent(paypal_event_id=event_id,event_type=event_type,paypal_order_id=order_id,verified=True,payload=event));order=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id)) if order_id else None
    if order:
        if order.provider_status in {"COMPLETED","REFUNDED"} and event_type in {"CHECKOUT.ORDER.APPROVED","PAYMENT.CAPTURE.PENDING","PAYMENT.CAPTURE.DENIED"}:
            db.commit();return
        if event_type=="PAYMENT.CAPTURE.COMPLETED":
            actual=resource.get("amount") or {}
            if actual.get("currency_code")!=order.provider_currency or actual.get("value")!=order.provider_amount:
                db.rollback();raise PayPalError("Webhook amount does not match the local order")
        if event_type=="CHECKOUT.ORDER.APPROVED":order.provider_status="APPROVED"
        elif event_type=="PAYMENT.CAPTURE.PENDING":order.provider_status="PENDING"
        elif event_type=="PAYMENT.CAPTURE.COMPLETED":
            order.provider_status="COMPLETED";order.paypal_capture_id=resource.get("id");order.captured_at=datetime.now(timezone.utc);db.get(PaymentRequest,order.payment_request_id).status="SUCCEEDED"
            if order.payment_attempt_id:
                attempt=db.get(PaymentAttempt,order.payment_attempt_id);attempt.status="SUCCEEDED";attempt.provider_reference=order.paypal_capture_id
        elif event_type in {"PAYMENT.CAPTURE.DENIED","PAYMENT.CAPTURE.REFUNDED"}:
            order.provider_status=event_type.rsplit(".",1)[-1]
            if event_type=='PAYMENT.CAPTURE.DENIED':
                db.get(PaymentRequest,order.payment_request_id).status='FAILED'
                if order.payment_attempt_id:
                    attempt=db.get(PaymentAttempt,order.payment_attempt_id);attempt.status='FAILED';attempt.failure_reason='PAYPAL_DENIED'
        emit(db,"paypal.webhook",{"order_id":order.paypal_order_id,"event_type":event_type})
    db.commit()
