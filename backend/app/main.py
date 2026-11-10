import asyncio,hmac,json
from datetime import datetime,timedelta,timezone
from fastapi import Depends,FastAPI,File,Header,HTTPException,Request,Response,UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse,JSONResponse
from pydantic import BaseModel,Field
from sqlalchemy import delete,select,text
from sqlalchemy.orm import Session
from .core import settings
from .db import SessionLocal,get_db
from .models import AppEvent,AutoPaySettings,AuthorizationChallenge,Conversation,ConversationMessage,JournalTransaction,LedgerEntry,Operation,PaymentAttempt,PaymentIntent,PaymentRequest,PaymentReservation,Recipient,SpendingMandate,Status
from .providers import DemoPaymentProvider
from .services import FinancialError,balances,batch_preview,emit,finalize,policy,reserve,settings_for,topup_or_withdraw,transition,wallet
from .voice import VoiceError,execute_tool,nemotron_intent,normalize_audio,nvidia_ready,synthesize,transcribe
from .paypal import PayPalError,apply_webhook,browser_client_token,capture_order,configured,create_order,refresh_order,serialise,verify_webhook
from .models import PayPalOrder
from .authorization import AuthorizationError,change_pin,consume_approval,create_challenge,security_for,verify_challenge
from .agentic import add_message,conversation_for,conversation_history,create_draft,mandate_for,serialize_intent,assistant_response,ConversationConflict
from .execution import execute_attempt
from .access import COOKIE,issue_session,valid_session

app=FastAPI(title="AI Wallet")
app.add_middleware(CORSMiddleware,allow_origins=settings().web_allowed_origins.split(","),allow_methods=["*"],allow_headers=["*"])

@app.middleware('http')
async def wallet_access(request:Request,call_next):
    path=request.url.path
    public={'/health','/api/auth/session','/api/auth/login','/api/auth/logout','/api/webhooks/paypal','/api/merchant/checkout'}
    if settings().require_wallet_login and path.startswith('/api/') and path not in public and request.method!='OPTIONS':
        with SessionLocal() as db:
            if not valid_session(db,request.cookies.get(COOKIE)):return JSONResponse({'detail':'Unlock your wallet to continue'},status_code=401)
    response=await call_next(request)
    if path.startswith('/api/'):response.headers['Cache-Control']='no-store'
    return response
class Amount(BaseModel):amount:int=Field(gt=0,le=10_000_000);idempotency_key:str=Field(min_length=8,max_length=255);approval_token:str=Field(min_length=20,max_length=255)
class ChallengeCreate(BaseModel):action:str;amount:int=Field(gt=0,le=10_000_000);resource_id:str|None=None;details:dict=Field(default_factory=dict)
class ChallengeVerify(BaseModel):pin:str=Field(pattern=r"^\d{6}$")
class PinChange(BaseModel):current_pin:str=Field(pattern=r"^\d{6}$");new_pin:str=Field(pattern=r"^\d{6}$")
class RecipientCreate(BaseModel):name:str=Field(min_length=1,max_length=120);handle:str=Field(min_length=3,max_length=160);handle_type:str=Field(default="PHONE",pattern=r"^(PHONE|EMAIL|PAYPAL_ID)$")
class IntentCreate(BaseModel):amount:int=Field(gt=0,le=10_000_000);recipient_id:str|None=None;merchant:str|None=Field(default=None,max_length=120);note:str|None=Field(default=None,max_length=500);source:str=Field(default="AI_WALLET",pattern=r"^(AI_WALLET|PAYPAL_SANDBOX)$")
class IntentExecute(BaseModel):approval_token:str=Field(min_length=20,max_length=255);idempotency_key:str=Field(min_length=8,max_length=255)
class MandateCreate(BaseModel):merchant:str=Field(min_length=1,max_length=120);max_amount:int=Field(gt=0);daily_limit:int=Field(gt=0);expires_at:datetime;approval_token:str=Field(min_length=20,max_length=255)
class MerchantCheckout(BaseModel):merchant:str=Field(min_length=1,max_length=120);order_reference:str=Field(min_length=3,max_length=160);amount:int=Field(gt=0,le=10_000_000);description:str=Field(default="Merchant checkout",max_length=500)
class AutoPatch(BaseModel):enabled:bool|None=None;time_sensitive_only:bool|None=None;per_transaction_limit:int|None=Field(default=None,gt=0);daily_limit:int|None=Field(default=None,gt=0);minimum_balance:int|None=Field(default=None,ge=0);allow_unknown_merchants:bool|None=None
class Merchant(BaseModel):type:str
class Pay(BaseModel):idempotency_key:str|None=None;confirm_unknown_merchant:bool=False
class Batch(BaseModel):
    idempotency_key:str|None=None
    payment_ids:list[str]|None=Field(default=None,max_length=100)
class AssistantTurn(BaseModel):
    text:str=Field(min_length=1,max_length=2000)
    conversation_id:str|None=Field(default=None,max_length=128)
    request_id:str|None=Field(default=None,min_length=8,max_length=80)
    history:list[dict]=Field(default_factory=list,max_length=12)
class Synthesis(BaseModel):
    text:str=Field(min_length=1,max_length=2000)
    language:str|None=Field(default=None,max_length=32)
    voice:str|None=Field(default=None,max_length=160)
class PayPalCreate(BaseModel):payment_request_id:str

@app.get('/api/auth/session')
def auth_session(request:Request,db:Session=Depends(get_db)):
    return {'required':settings().require_wallet_login,'authenticated':valid_session(db,request.cookies.get(COOKIE)),'mode':'single-owner-demo'}

@app.post('/api/auth/login')
def auth_login(data:ChallengeVerify,response:Response,db:Session=Depends(get_db)):
    if len(settings().wallet_session_secret)<32:raise HTTPException(503,'Set WALLET_SESSION_SECRET to at least 32 random characters before enabling wallet sign-in')
    try:
        challenge=create_challenge(db,'LOGIN',1)
        verify_challenge(db,challenge.id,data.pin)
        challenge.status='CONSUMED';challenge.approval_token=None
        token=issue_session(db);db.commit()
    except AuthorizationError as error:db.commit();raise HTTPException(403,str(error))
    response.set_cookie(COOKIE,token,httponly=True,secure=settings().wallet_cookie_secure,samesite='strict',max_age=settings().wallet_session_minutes*60,path='/')
    return {'authenticated':True}

@app.post('/api/auth/logout')
def auth_logout(request:Request,response:Response,db:Session=Depends(get_db)):
    if request.cookies.get(COOKIE) and valid_session(db,request.cookies.get(COOKIE)):
        security_for(db).updated_at=datetime.now(timezone.utc);db.commit()
    response.delete_cookie(COOKIE,path='/');return {'authenticated':False}
class DemoCheckout(BaseModel):order_reference:str=Field(min_length=8,max_length=160,pattern=r"^DEMO-[a-zA-Z0-9-]+$")

@app.post("/api/demo/checkout")
def demo_checkout(data:DemoCheckout,db:Session=Depends(get_db)):
    if not settings().demo_mode:raise HTTPException(404,"Not found")
    return merchant_checkout(MerchantCheckout(merchant=settings().demo_merchant_name,order_reference=data.order_reference,amount=125000,description="Sample Hyderabad to Bengaluru railway ticket"),settings().demo_merchant_api_key,db)

@app.get("/api/demo/checkout/{payment_id}")
def demo_checkout_status(payment_id:str,db:Session=Depends(get_db)):
    if not settings().demo_mode:raise HTTPException(404,"Not found")
    payment=db.get(PaymentRequest,payment_id)
    if not payment or not payment.provider.startswith("MERCHANT:DEMO-"):raise HTTPException(404,"Order not found")
    return serialize(payment)
def serialize(p:PaymentRequest):return {"id":p.id,"merchant":p.merchant,"category":p.category,"description":p.description,"amount":p.amount,"currency":p.currency,"expires_at":p.expires_at,"verified":p.verified,"provider":p.provider,"status":p.status,"explicit_hold":p.explicit_hold,"trace":p.trace}
def attempt_payload(a:PaymentAttempt|None):return None if not a else {"id":a.id,"status":a.status,"provider_reference":a.provider_reference,"failure_reason":a.failure_reason}
def do_payment(payment_id:str,data:Pay):
    """Commit reservation before provider call; finalize in a fresh transaction."""
    key=data.idempotency_key or f"manual:{payment_id}"
    with SessionLocal() as db:
        p=db.get(PaymentRequest,payment_id)
        if not p:raise HTTPException(404,"Payment request not found")
        try:a=reserve(db,p,key,"manual",data.confirm_unknown_merchant);db.commit();attempt_id=a.id
        except FinancialError as e:db.rollback();raise HTTPException(409,str(e))
    return attempt_payload(execute_attempt(attempt_id))
@app.get("/health")
def health():return {"status":"ok","demo_mode":settings().demo_mode}
@app.get("/api/assistant/status")
def assistant_status():
    s=settings(); configured=nvidia_ready()
    return {"nvidia_enabled":s.nvidia_enabled,"whisper_configured":configured and bool(s.nvidia_whisper_function_id and s.nvidia_whisper_server),"nemotron_configured":configured and bool(s.nvidia_nemotron_model_id),"magpie_configured":configured and bool(s.nvidia_magpie_synthesis_url and s.nvidia_magpie_voice),"whisper_model":"nvidia-riva-whisper-large-v3","nemotron_model":s.nvidia_nemotron_model_id,"magpie_voice":s.nvidia_magpie_voice,"browser_tts_fallback":s.voice_browser_tts_fallback,"demo_mode":not configured,"configuration_is_live_verification":False}
@app.get("/api/paypal/config")
def paypal_config():
    s=settings();ready=configured()
    return {"enabled":ready,"configured":ready,"environment":s.paypal_mode,"client_id":s.paypal_client_id if ready else None,"checkout_currency":s.paypal_checkout_currency,"application_currency":s.paypal_application_currency,"demo_inr_per_usd":s.paypal_demo_inr_per_usd if s.paypal_checkout_currency=="USD" else None}
@app.get("/api/paypal/browser-client-token")
async def paypal_browser_token():
    try:return {"client_token":await browser_client_token()}
    except PayPalError as e:raise HTTPException(503,str(e))
@app.post("/api/paypal/orders")
async def paypal_create(data:PayPalCreate,db:Session=Depends(get_db)):
    try:return await create_order(db,data.payment_request_id)
    except PayPalError as e:raise HTTPException(503 if e.retryable else 409,str(e))
@app.get("/api/paypal/orders/{order_id}")
def paypal_order(order_id:str,db:Session=Depends(get_db)):
    row=db.scalar(select(PayPalOrder).where(PayPalOrder.paypal_order_id==order_id))
    if not row:raise HTTPException(404,"Unknown PayPal order")
    return serialise(row)
@app.post("/api/paypal/orders/{order_id}/capture")
async def paypal_capture(order_id:str,db:Session=Depends(get_db)):
    try:return await capture_order(db,order_id)
    except PayPalError as e:raise HTTPException(503 if e.retryable else 409,str(e))
@app.post('/api/paypal/orders/{order_id}/refresh')
async def paypal_refresh(order_id:str,db:Session=Depends(get_db)):
    try:return await refresh_order(db,order_id)
    except PayPalError as e:raise HTTPException(503 if e.retryable else 409,str(e))
@app.get('/api/paypal/payment-requests/{payment_id}/order')
def paypal_existing_order(payment_id:str,db:Session=Depends(get_db)):
    row=db.scalar(select(PayPalOrder).where(PayPalOrder.payment_request_id==payment_id).order_by(PayPalOrder.created_at.desc()))
    return serialise(row) if row else None
@app.get("/api/paypal/payments")
def paypal_payments(db:Session=Depends(get_db)):return [serialise(x) for x in db.scalars(select(PayPalOrder).order_by(PayPalOrder.created_at.desc())).all()]
@app.post("/api/webhooks/paypal")
async def paypal_webhook(request:Request,db:Session=Depends(get_db)):
    try:
        event=await request.json()
        if not await verify_webhook(request.headers,event):raise HTTPException(401,"Invalid PayPal webhook signature")
        apply_webhook(db,event);return {"status":"accepted"}
    except PayPalError as e:raise HTTPException(503 if e.retryable else 400,str(e))
    except (ValueError,TypeError):raise HTTPException(400,'Invalid webhook JSON')
@app.post("/api/voice/transcribe")
async def voice_transcribe(audio:UploadFile=File(...)):
    try:
        raw=await audio.read()
        wav,duration=await asyncio.to_thread(normalize_audio,raw,audio.content_type)
        answer=await transcribe(wav)
        from .context import contains_authentication_secret
        if contains_authentication_secret(answer['transcript']):raise VoiceError('The recording appears to contain a PIN, password or OTP. It was not sent to the assistant. Use the secure dialog instead.')
        return {**answer,"duration_seconds":duration,"status":"completed"}
    except VoiceError as e:raise HTTPException(422,str(e))
@app.post("/api/assistant/turn")
async def assistant_turn(data:AssistantTurn,db:Session=Depends(get_db)):
    from .context import contains_authentication_secret
    if contains_authentication_secret(data.text):
        raise HTTPException(422,"Do not share PINs, passwords or OTPs with the assistant. Use the secure payment dialog instead.")
    try:
        return await assistant_response(db,data.text,data.conversation_id,data.request_id,nemotron_intent)
    except VoiceError as e:db.rollback();raise HTTPException(422,str(e))
    except ConversationConflict as e:db.rollback();raise HTTPException(409,str(e))
@app.get("/api/assistant/conversations/{conversation_id}")
def get_conversation(conversation_id:str,db:Session=Depends(get_db)):
    row=db.get(Conversation,conversation_id)
    if not row or row.user_id!="demo-user":raise HTTPException(404,"Conversation not found")
    return {"id":row.id,"selected_payment_id":row.selected_payment_id,"messages":conversation_history(db,row,50)}
@app.delete("/api/assistant/conversations/{conversation_id}")
def clear_conversation(conversation_id:str,db:Session=Depends(get_db)):
    row=db.get(Conversation,conversation_id)
    if not row or row.user_id!="demo-user":raise HTTPException(404,"Conversation not found")
    db.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id==row.id));db.delete(row);db.commit();return {"status":"CLEARED"}
@app.post("/api/voice/synthesize")
async def voice_synthesize(data:Synthesis):
    try:
        audio,content_type=await synthesize(data.text,data.language or settings().nvidia_magpie_language,data.voice)
        return Response(audio,media_type=content_type,headers={"Cache-Control":"no-store","X-Voice-Provider":"nvidia-magpie"})
    except VoiceError as e:raise HTTPException(422,str(e))
@app.get("/api/wallet")
def get_wallet(db:Session=Depends(get_db)):
    w=wallet(db);data=balances(db,w);w.cached_balance=data["posted_balance"];db.commit();return {"balance":data["posted_balance"],"currency":w.currency,"label":"Demo internal journal balance",**data}
@app.get("/api/wallet/transactions")
def transactions(db:Session=Depends(get_db)):return [{"id":o.id,"kind":o.kind,"amount":o.amount,"status":o.status,"reference":o.reference,"created_at":o.created_at} for o in db.scalars(select(Operation).order_by(Operation.created_at.desc())).all()]
@app.get("/api/wallet/ledger")
def ledger(db:Session=Depends(get_db)):
    rows=db.execute(select(LedgerEntry,JournalTransaction).join(JournalTransaction,LedgerEntry.journal_transaction_id==JournalTransaction.id).order_by(LedgerEntry.created_at)).all()
    return [{"id":e.id,"journal_transaction_id":j.id,"operation_id":j.operation_id,"direction":e.direction,"ledger_account_id":e.ledger_account_id,"amount":e.amount,"currency":e.currency,"created_at":e.created_at} for e,j in rows]
@app.get("/api/wallet/reservations")
def reservations(db:Session=Depends(get_db)):
    rows=db.scalars(select(PaymentReservation).where(PaymentReservation.status=="ACTIVE").order_by(PaymentReservation.created_at.desc())).all()
    return [{"id":r.id,"payment_request_id":r.payment_request_id,"amount":r.amount,"currency":r.currency,"status":r.status,"expires_at":r.expires_at} for r in rows]
@app.get("/api/bank/accounts")
def accounts():return [{"id":"demo-bank-001","bank_name":"Demo National Bank","balance":5000000,"currency":"INR","is_demo":True}]
@app.get("/api/security/pin/status")
def pin_status(db:Session=Depends(get_db)):
    row=security_for(db);db.commit();return {"configured":True,"locked_until":row.locked_until,"mode":"demo_wallet_pin"}
@app.post("/api/security/challenges")
def challenge(data:ChallengeCreate,db:Session=Depends(get_db)):
    try:row=create_challenge(db,data.action.upper(),data.amount,data.resource_id,data.details);db.commit();return {"id":row.id,"action":row.action,"amount":row.amount,"resource_id":row.resource_id,"expires_at":row.expires_at}
    except AuthorizationError as e:db.rollback();raise HTTPException(422,str(e))
@app.post("/api/security/challenges/{challenge_id}/verify")
def approve_challenge(challenge_id:str,data:ChallengeVerify,db:Session=Depends(get_db)):
    try:token=verify_challenge(db,challenge_id,data.pin);db.commit();return {"approval_token":token,"status":"APPROVED"}
    except AuthorizationError as e:db.commit();raise HTTPException(403,str(e))
@app.post("/api/security/pin/change")
def update_pin(data:PinChange,db:Session=Depends(get_db)):
    try:change_pin(db,data.current_pin,data.new_pin);db.commit();return {"status":"UPDATED"}
    except AuthorizationError as e:db.commit();raise HTTPException(403,str(e))
@app.post("/api/bank/topups")
def topup(data:Amount,db:Session=Depends(get_db)):
    try:op=authorized_transfer(db,data,"TOPUP");db.commit()
    except (FinancialError,AuthorizationError) as e:db.rollback();raise HTTPException(409,str(e))
    return {"operation_id":op.id,"status":op.status,"reference":op.reference,"is_demo":True}
@app.post("/api/bank/withdrawals")
def withdrawal(data:Amount,db:Session=Depends(get_db)):
    try:op=authorized_transfer(db,data,"WITHDRAWAL");db.commit()
    except (FinancialError,AuthorizationError) as e:db.rollback();raise HTTPException(409,str(e))
    return {"operation_id":op.id,"status":op.status,"reference":op.reference,"is_demo":True}

def authorized_transfer(db,data,kind):
    wallet(db,True)
    approval=db.scalar(select(AuthorizationChallenge).where(AuthorizationChallenge.approval_token==data.approval_token))
    old=db.scalar(select(Operation).where(Operation.idempotency_key==data.idempotency_key))
    if old:
        if not approval or approval.status!="CONSUMED" or (approval.details or {}).get("operation_key")!=data.idempotency_key or old.kind!=kind or old.amount!=data.amount:raise AuthorizationError("This retry does not match the approved transfer")
        return old
    approval=consume_approval(db,data.approval_token,kind,data.amount)
    approval.details={**(approval.details or {}),"operation_key":data.idempotency_key}
    return topup_or_withdraw(db,data.amount,kind,data.idempotency_key)
@app.get("/api/recipients")
def recipients(db:Session=Depends(get_db)):
    return [{"id":r.id,"name":r.name,"handle":r.handle,"handle_type":r.handle_type,"verified":r.verified,"provider":r.provider} for r in db.scalars(select(Recipient).order_by(Recipient.created_at.desc())).all()]
@app.post("/api/recipients")
def add_recipient(data:RecipientCreate,db:Session=Depends(get_db)):
    import re
    data.name=data.name.strip();data.handle=data.handle.strip()
    if not data.name:raise HTTPException(422,"Enter a recipient name")
    if data.handle_type=="PHONE":
        data.handle=re.sub(r"[\s()-]","",data.handle)
        if not re.fullmatch(r"\+?[0-9]{8,15}",data.handle):raise HTTPException(422,"Enter a valid phone number with country code")
    if data.handle_type=="EMAIL":
        data.handle=data.handle.lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",data.handle):raise HTTPException(422,"Enter a valid email address")
    existing=db.scalar(select(Recipient).where(Recipient.user_id=="demo-user",Recipient.handle==data.handle))
    if existing:return {"id":existing.id,"name":existing.name,"handle":existing.handle,"handle_type":existing.handle_type,"verified":existing.verified,"provider":existing.provider}
    row=Recipient(name=data.name,handle=data.handle,handle_type=data.handle_type);db.add(row);db.commit();db.refresh(row);return {"id":row.id,"name":row.name,"handle":row.handle,"handle_type":row.handle_type,"verified":row.verified,"provider":row.provider}
@app.get("/api/payment-intents")
def payment_intents(db:Session=Depends(get_db)):return [serialize_intent(row) for row in db.scalars(select(PaymentIntent).order_by(PaymentIntent.created_at.desc())).all()]
@app.post("/api/payment-intents")
def add_payment_intent(data:IntentCreate,db:Session=Depends(get_db)):
    if data.source!="AI_WALLET":raise HTTPException(422,"PayPal recipient payouts are not configured; use the demo wallet")
    recipient=db.get(Recipient,data.recipient_id) if data.recipient_id else None
    if data.recipient_id and not recipient:raise HTTPException(404,"Recipient not found")
    if not recipient and not data.merchant:raise HTTPException(422,"Choose a recipient or merchant")
    row=create_draft(db,data.amount,recipient,data.merchant,data.note);row.source=data.source;db.commit();return serialize_intent(row)
@app.post("/api/payment-intents/{intent_id}/hold")
def hold_intent(intent_id:str,db:Session=Depends(get_db)):
    row=db.get(PaymentIntent,intent_id)
    if not row or row.status not in {"DRAFT","HELD"}:raise HTTPException(409,"Draft cannot be held")
    row.status="HELD";row.version+=1;db.commit();return serialize_intent(row)
@app.post("/api/payment-intents/{intent_id}/execute")
def execute_intent(intent_id:str,data:IntentExecute,db:Session=Depends(get_db)):
    wallet(db,True)
    row=db.scalar(select(PaymentIntent).where(PaymentIntent.id==intent_id).with_for_update())
    if not row or row.user_id!="demo-user":raise HTTPException(404,"Draft not found")
    if row.payment_request_id:
        attempt=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==row.payment_request_id,PaymentAttempt.idempotency_key==data.idempotency_key))
        if attempt:return {"intent":serialize_intent(row),"payment":attempt_payload(attempt)}
        raise HTTPException(409,"This draft has already been submitted. Check its payment status.")
    if row.status not in {"DRAFT","HELD"}:raise HTTPException(409,"Draft is not executable")
    if row.source!="AI_WALLET":raise HTTPException(422,"Recipient transfers use the demo wallet. PayPal Checkout pays the configured merchant, not an arbitrary recipient.")
    try:consume_approval(db,data.approval_token,"P2P",row.amount,row.id,{"version":row.version,"source":row.source})
    except AuthorizationError as e:db.rollback();raise HTTPException(409,str(e))
    recipient=db.get(Recipient,row.recipient_id) if row.recipient_id else None
    label=recipient.name if recipient else row.merchant or "Wallet recipient"
    payment=PaymentRequest(merchant=label,category="person_to_person",description=row.note or "Person-to-person transfer",amount=row.amount,verified=bool(recipient and recipient.verified),provider="AI_WALLET_DEMO")
    db.add(payment);db.flush();row.payment_request_id=payment.id;row.status="PROCESSING";row.version+=1
    try:attempt=reserve(db,payment,data.idempotency_key,"manual",True);db.commit();attempt_id=attempt.id
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))
    db.rollback()
    result=attempt_payload(execute_attempt(attempt_id));db.expire_all();row=db.get(PaymentIntent,intent_id)
    return {"intent":serialize_intent(row),"payment":result}
@app.get("/api/mandates")
def mandates(db:Session=Depends(get_db)):
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo(settings().app_timezone)).date().isoformat()
    return [{"id":m.id,"merchant":m.merchant,"max_amount":m.max_amount,"daily_limit":m.daily_limit,"spent_today":m.spent_today if (m.context or {}).get('usage_date')==today else 0,"status":m.status,"expires_at":m.expires_at} for m in db.scalars(select(SpendingMandate).order_by(SpendingMandate.created_at.desc())).all()]
@app.post("/api/mandates")
def add_mandate(data:MandateCreate,db:Session=Depends(get_db)):
    if data.expires_at.tzinfo is None:raise HTTPException(422,"Include a timezone with the expiry")
    if data.daily_limit<data.max_amount:raise HTTPException(422,"Daily limit must cover the maximum payment")
    details={"merchant":data.merchant,"daily_limit":data.daily_limit,"expires_at":int(data.expires_at.timestamp())}
    try:consume_approval(db,data.approval_token,"MANDATE",data.max_amount,data.merchant,details)
    except AuthorizationError as e:db.rollback();raise HTTPException(409,str(e))
    if data.expires_at<=datetime.now(timezone.utc):raise HTTPException(422,"Mandate expiry must be in the future")
    row=SpendingMandate(merchant=data.merchant,max_amount=data.max_amount,daily_limit=data.daily_limit,expires_at=data.expires_at);db.add(row);db.commit();return {"id":row.id,"status":row.status}
@app.post("/api/mandates/{mandate_id}/revoke")
def revoke_mandate(mandate_id:str,db:Session=Depends(get_db)):
    row=db.get(SpendingMandate,mandate_id)
    if not row:raise HTTPException(404,"Mandate not found")
    row.status="REVOKED";db.commit();return {"id":row.id,"status":row.status}
@app.post("/api/merchant/checkout")
def merchant_checkout(data:MerchantCheckout,x_merchant_key:str|None=Header(default=None),db:Session=Depends(get_db)):
    configured=settings()
    if data.merchant!=configured.demo_merchant_name or not x_merchant_key or not hmac.compare_digest(x_merchant_key,configured.demo_merchant_api_key):raise HTTPException(401,"Merchant authentication failed")
    wallet(db,True)
    existing=db.scalar(select(PaymentRequest).where(PaymentRequest.provider==f"MERCHANT:{data.order_reference}"))
    if existing:
        if existing.amount!=data.amount or existing.merchant!=data.merchant or existing.description!=data.description:raise HTTPException(409,"Order reference was already used with different details")
        return {"payment_request":serialize(existing),"status":existing.status,"idempotent":True}
    permission=mandate_for(db,data.merchant,data.amount)
    payment=PaymentRequest(merchant=data.merchant,category="merchant_checkout",description=data.description,amount=data.amount,verified=permission is not None,provider=f"MERCHANT:{data.order_reference}")
    db.add(payment);db.flush()
    if not permission:
        payment.explicit_hold=True;payment.status="HELD";emit(db,"payment.created",{"payment_id":payment.id});db.commit()
        return {"payment_request":serialize(payment),"status":"AWAITING_USER_APPROVAL","idempotent":False}
    try:
        attempt=reserve(db,payment,f"merchant:{data.order_reference}","manual")
        permission.spent_today+=data.amount
        payment.trace={**(payment.trace or {}),"mandate_id":permission.id,"mandate_day":permission.context["usage_date"]}
        db.commit();attempt_id=attempt.id;payment_id=payment.id;db.rollback()
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))
    result=attempt_payload(execute_attempt(attempt_id));db.expire_all();payment=db.get(PaymentRequest,payment_id)
    return {"payment_request":serialize(payment),"status":result["status"],"payment":result,"idempotent":False}
@app.get("/api/autopay/settings")
def get_settings(db:Session=Depends(get_db)):
    s=settings_for(db);db.commit();return {k:getattr(s,k) for k in ["enabled","time_sensitive_only","per_transaction_limit","daily_limit","minimum_balance","allow_unknown_merchants"]}
@app.patch("/api/autopay/settings")
def update_settings(data:AutoPatch,db:Session=Depends(get_db)):
    s=settings_for(db)
    for k,v in data.model_dump(exclude_none=True).items():setattr(s,k,v)
    emit(db,"autopay.changed",{"user_id":s.user_id});db.commit();return get_settings(db)
@app.post("/api/merchant/payment-requests")
def merchant(data:Merchant,db:Session=Depends(get_db)):
    templates={"railway":("Indian Railways","travel","Tatkal ticket",125000,4,True),"movie":("CinemaPass","entertainment","Movie ticket",60000,120,True),"electronics":("ElectroHub","shopping","Unverified electronics store",450000,None,False)}
    if data.type not in templates:raise HTTPException(422,"Unknown demo merchant type")
    n,c,d,a,m,v=templates[data.type];p=PaymentRequest(merchant=n,category=c,description=d,amount=a,verified=v,expires_at=datetime.now(timezone.utc)+timedelta(minutes=m) if m else None);db.add(p);db.flush();p.trace=policy(db,p,"auto");emit(db,"payment.created",{"payment_id":p.id});db.commit();return serialize(p)
@app.get("/api/payments")
@app.get("/api/payment-requests")
def payments(db:Session=Depends(get_db)):
    rows=db.scalars(select(PaymentRequest).order_by(PaymentRequest.created_at.desc())).all()
    external=set(db.scalars(select(PaymentAttempt.payment_request_id).where(PaymentAttempt.reservation_id.is_(None),PaymentAttempt.status.in_(["PROCESSING","SUCCEEDED"]))).all())
    return [{**serialize(p),"trace":policy(db,p,"auto"),"payment_source":"PAYPAL_SANDBOX" if p.id in external else "AI_WALLET"} for p in rows]
@app.post("/api/payments/{payment_id}/pay")
def pay(payment_id:str,data:Pay=Pay()):return do_payment(payment_id,data)
@app.get('/api/payments/{payment_id}/review')
def payment_review(payment_id:str,db:Session=Depends(get_db)):
    """Read-only review: reuse execution policy and recorded settlement evidence."""
    p=db.get(PaymentRequest,payment_id)
    if not p:raise HTTPException(404,'Payment request not found')
    decision=policy(db,p,'manual')
    confirmed=policy(db,p,'manual',True)
    a=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==p.id).order_by(PaymentAttempt.created_at.desc()))
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.payment_request_id==p.id).order_by(PayPalOrder.created_at.desc()))
    op=db.scalar(select(Operation).where(Operation.idempotency_key==f'payment:{p.id}'))
    journal=db.scalar(select(JournalTransaction).where(JournalTransaction.operation_id==op.id)) if op else None
    result={'payment':serialize(p),'wallet_policy':decision,'wallet_policy_after_merchant_confirmation':confirmed,'wallet_per_transaction_limit':settings_for(db).per_transaction_limit,
        'wallet_currency':wallet(db).currency,'paypal':{**serialise(order),'updated_at':order.updated_at,'captured_at':order.captured_at} if order else None,
        'attempt':attempt_payload(a),'receipt':None}
    if a:
        external=not a.reservation_id
        result['receipt']={'payment_id':p.id,'attempt_id':a.id,'merchant':p.merchant,'amount':p.amount,'currency':p.currency,
            'funding_source':'PAYPAL_SANDBOX' if external else 'AI_WALLET','status':a.status,
            'timestamp':order.captured_at or order.updated_at if external and order else journal.created_at if journal else a.created_at,
            'timestamp_label':'Capture recorded' if external and order and order.captured_at else 'Journal posted' if journal else 'Record timestamp',
            'provider_reference':a.provider_reference,'journal_id':journal.id if journal else None,
            'order_id':order.paypal_order_id if external and order else None,'capture_id':order.paypal_capture_id if external and order else None}
    db.rollback()
    return result
@app.post("/api/payments/{payment_id}/hold")
def hold(payment_id:str,db:Session=Depends(get_db)):
    wallet(db,True);p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==payment_id).with_for_update())
    if not p:raise HTTPException(404,"Payment request not found")
    try:transition(p,"HELD");p.explicit_hold=True
    except FinancialError as e:raise HTTPException(409,str(e))
    emit(db,"payment.held",{"payment_id":p.id});db.commit();return serialize(p)
@app.post("/api/payments/{payment_id}/release")
def release_hold(payment_id:str,db:Session=Depends(get_db)):
    wallet(db,True);p=db.scalar(select(PaymentRequest).where(PaymentRequest.id==payment_id).with_for_update())
    if not p:raise HTTPException(404,"Payment request not found")
    if not p.explicit_hold:raise HTTPException(409,"Payment is not explicitly held")
    p.explicit_hold=False
    if p.status=="HELD":transition(p,"PENDING")
    emit(db,"payment.released",{"payment_id":p.id});db.commit();return serialize(p)
@app.post("/api/payments/batch/evaluate")
def evaluate(db:Session=Depends(get_db)):
    result=batch_preview(db);db.rollback();return result
@app.post("/api/payments/batch/confirm")
def confirm(data:Batch=Batch(),db:Session=Depends(get_db)):
    wallet(db,True)
    # A stable per-request key makes a duplicate confirmation non-debiting.
    query=select(PaymentRequest).where(PaymentRequest.status.in_(["PENDING","HELD"]),PaymentRequest.explicit_hold.is_(False))
    if data.payment_ids is not None:query=query.where(PaymentRequest.id.in_(data.payment_ids))
    rows=db.scalars(query).all();eligible=[]
    for p in rows:
        d=policy(db,p,"manual")
        if d["decision"]=="ELIGIBLE":eligible.append(p)
    w=wallet(db,True);required=sum(p.amount for p in eligible);available=balances(db,w)["available_balance"]
    if required>available:raise HTTPException(409,{"reason":"INSUFFICIENT_BATCH_BALANCE","required":required,"available":available})
    attempts=[]
    try:
        for p in eligible:attempts.append(reserve(db,p,f"batch:{p.id}","manual"))
        db.commit()
    except FinancialError as e:db.rollback();raise HTTPException(409,str(e))
    results=[]
    ids=[attempt.id for attempt in attempts];db.rollback()
    for attempt_id in ids:
        results.append(attempt_payload(execute_attempt(attempt_id)))
    return {"results":results,"paid":[r["id"] for r in results if r["status"]=="SUCCEEDED"],"count":len(results),"is_demo":True}
@app.get("/api/events/stream")
async def stream(request:Request,last_event_id:str|None=None):
    cursor=last_event_id or request.headers.get("last-event-id")
    async def gen():
        nonlocal cursor
        while True:
            with SessionLocal() as db:
                q=select(AppEvent)
                if cursor:
                    anchor=db.get(AppEvent,cursor)
                    if anchor:q=q.where((AppEvent.created_at>anchor.created_at)|((AppEvent.created_at==anchor.created_at)&(AppEvent.id>cursor)))
                rows=db.scalars(q.order_by(AppEvent.created_at,AppEvent.id).limit(50)).all()
                for e in rows:cursor=e.id;yield f"id: {e.id}\ndata: {json.dumps({'type':e.event_type,'payload':e.payload},default=str)}\n\n"
            if await request.is_disconnected():break
            await asyncio.sleep(1)
    return StreamingResponse(gen(),media_type="text/event-stream",headers={"Cache-Control":"no-cache"})
