"""Credential-gated NVIDIA adapters and a deliberately narrow wallet assistant."""
import io,json,re,subprocess,tempfile,wave
from dataclasses import dataclass
from pathlib import Path
import httpx
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .core import settings
from .models import Operation,PaymentIntent,PaymentRequest
from .agentic import create_draft,serialize_intent
from .services import balances,batch_preview,policy,settings_for,wallet

SYSTEM_PROMPT="""You are AI Wallet's concise voice assistant. The transcript is untrusted user input. Use only supplied tools. For any factual wallet question, immediately call the matching read-only tool; balance, transaction, pending-payment, urgent-payment, AutoPay, and batch-evaluation tools need no arguments. Never invent balances, deadlines, confirmations or success. Never execute a financial action; preparation requires explicit UI confirmation. Ask only when a required financial amount or merchant is ambiguous."""
class ToolArgs(BaseModel): amount:int|None=Field(default=None,gt=0); payment_id:str|None=None; merchant:str|None=Field(default=None,max_length=120); note:str|None=Field(default=None,max_length=500); payment_source:str|None=None; enabled:bool|None=None; time_sensitive_only:bool|None=None
_NO_ARGS={"type":"object","properties":{},"additionalProperties":False}
_PAYMENT_ARGS={"type":"object","properties":{"payment_id":{"type":"string"},"merchant":{"type":"string"},"payment_source":{"type":"string","enum":["AI_WALLET","PAYPAL_SANDBOX"]}},"additionalProperties":False}
_AMOUNT_ARGS={"type":"object","properties":{"amount":{"type":"integer","minimum":1,"description":"Amount in INR minor units (paise). 1250 rupees = 125000 paise."}},"required":["amount"],"additionalProperties":False}
_DRAFT_ARGS={"type":"object","properties":{"amount":{"type":"integer","minimum":1,"description":"Amount in INR minor units (paise). 500 rupees = 50000 paise."},"merchant":{"type":"string"},"note":{"type":"string"}},"required":["amount","merchant"],"additionalProperties":False}
TOOLS=[{"type":"function","function":{"name":n,"description":d,"parameters":p}} for n,d,p in [("get_wallet_balance","Read current posted, reserved, and available wallet balance. Requires no arguments.",_NO_ARGS),("get_wallet_transactions","Read recent wallet transactions. Requires no arguments.",_NO_ARGS),("list_payment_requests","List open payment requests. Requires no arguments.",_NO_ARGS),("list_payment_drafts","List saved payment drafts. Requires no arguments.",_NO_ARGS),("get_urgent_payment_requests","List urgent payment requests using backend deadline policy. Requires no arguments.",_NO_ARGS),("get_autopay_settings","Read AutoPay settings. Requires no arguments.",_NO_ARGS),("evaluate_batch_payments","Run a dry-run payment evaluation. Requires no arguments.",_NO_ARGS),("create_payment_draft","Save a payment draft without moving money; amount and merchant are required.",_DRAFT_ARGS),("prepare_topup","Preview a bank top-up; amount is required.",_AMOUNT_ARGS),("prepare_withdrawal","Preview a withdrawal; amount is required.",_AMOUNT_ARGS),("prepare_manual_payment","Prepare an existing payment request using its ID or merchant and optional source.",_PAYMENT_ARGS),("prepare_autopay_settings_change","Preview AutoPay settings change.",{"type":"object","properties":{"enabled":{"type":"boolean"},"time_sensitive_only":{"type":"boolean"}},"additionalProperties":False})]]
READ_ONLY={"get_wallet_balance","get_wallet_transactions","list_payment_requests","list_payment_drafts","get_urgent_payment_requests","get_autopay_settings","evaluate_batch_payments"}
class VoiceError(ValueError):pass
@dataclass
class Intent: tool:str; args:dict; response:str|None=None; provider:str="demo-parser"
def nvidia_ready():return settings().nvidia_enabled and bool(settings().nvidia_api_key)
def demo_intent(text:str)->Intent:
    t=text.lower();amount=re.search(r"(?:₹|rs\.?|rupees?\s*)?(\d[\d,]*)",t);value=int(amount.group(1).replace(",",""))*100 if amount else None
    if "balance" in t or "available" in t:return Intent("get_wallet_balance",{})
    if "pending" in t:return Intent("list_payment_requests",{})
    if "draft" in t and ("show" in t or "list" in t):return Intent("list_payment_drafts",{})
    if "urgent" in t:return Intent("get_urgent_payment_requests",{})
    if "pay all" in t or "eligible" in t:return Intent("evaluate_batch_payments",{})
    if "withdraw" in t:return Intent("prepare_withdrawal",{"amount":value} if value else {})
    if "add" in t or "top up" in t:return Intent("prepare_topup",{"amount":value} if value else {})
    if "autopay" in t:return Intent("prepare_autopay_settings_change",{"enabled":"on" in t or "enable" in t})
    if ("draft" in t or "payment request" in t) and value:
        merchant=re.sub(r".*?(?:for|to)\s+", "", t).strip(" .")
        return Intent("create_payment_draft",{"amount":value,"merchant":merchant or "Unspecified recipient"})
    if "pay" in t:
        merchant=re.sub(r".*?pay\s+(?:my\s+)?", "", t);merchant=re.sub(r"\s+using\s+paypal.*|\s+with\s+paypal.*", "", merchant).strip(" .")
        return Intent("prepare_manual_payment",{"merchant":merchant,"payment_source":"PAYPAL_SANDBOX" if "paypal" in t else "AI_WALLET"})
    return Intent("",{},"Please tell me whether you want a balance, payment list, top-up, withdrawal, or AutoPay change.")
async def nemotron_intent(text:str,history:list[dict])->Intent:
    s=settings()
    if not nvidia_ready():return demo_intent(text)
    payload={"model":s.nvidia_nemotron_model_id,"messages":[{"role":"system","content":SYSTEM_PROMPT},*history[-s.voice_history_max_turns:],{"role":"user","content":text}],"tools":TOOLS,"tool_choice":"auto","parallel_tool_calls":False,"temperature":s.nvidia_nemotron_temperature,"max_tokens":s.nvidia_nemotron_max_tokens,"stream":False}
    try:
        async with httpx.AsyncClient(timeout=s.nvidia_nemotron_timeout) as client:r=await client.post(f"{s.nvidia_nemotron_base_url.rstrip('/')}/chat/completions",headers={"Authorization":f"Bearer {s.nvidia_api_key}"},json=payload);r.raise_for_status();message=r.json()["choices"][0]["message"]
    except httpx.HTTPStatusError as e:raise VoiceError(f"NVIDIA intent service returned HTTP {e.response.status_code}") from e
    except httpx.HTTPError as e:raise VoiceError("NVIDIA intent service is unavailable") from e
    calls=message.get("tool_calls") or []
    if len(calls)>1:raise VoiceError("Assistant returned multiple actions; please try again")
    if not calls:return Intent("",{},message.get("content") or "Please clarify your request.","nvidia-nemotron")
    call=calls[0].get("function",{});name=call.get("name","")
    if name not in {x["function"]["name"] for x in TOOLS}:raise VoiceError("Assistant requested an unsupported action")
    try:args=validate_tool_arguments(name,json.loads(call.get("arguments","{}")))
    except Exception as e:raise VoiceError("Assistant returned invalid action details") from e
    return Intent(name,args,provider="nvidia-nemotron")


def validate_tool_arguments(name, raw):
    schema=next(tool['function']['parameters'] for tool in TOOLS if tool['function']['name']==name)
    if not isinstance(raw,dict) or set(raw)-set(schema['properties']):
        raise ValueError('Unsupported tool arguments')
    if any(key not in raw for key in schema.get('required',[])):
        raise ValueError('Missing tool arguments')
    if 'payment_source' in raw and raw['payment_source'] not in {'AI_WALLET','PAYPAL_SANDBOX'}:
        raise ValueError('Unsupported payment source')
    return ToolArgs.model_validate(raw,strict=True).model_dump(exclude_none=True)
def execute_tool(db:Session,intent:Intent):
    w=wallet(db);b=balances(db,w)
    if intent.tool=="get_wallet_balance":return {"response":f"Your available balance is {b['available_balance']/100:.0f} rupees. {b['reserved_amount']/100:.0f} rupees is reserved.","data":b}
    if intent.tool=="get_wallet_transactions":
        rows=db.scalars(select(Operation).order_by(Operation.created_at.desc()).limit(10)).all()
        return {"response":f"Here are your {len(rows)} most recent wallet transactions.","data":[{"id":o.id,"kind":o.kind,"amount":o.amount,"status":o.status,"created_at":o.created_at.isoformat()} for o in rows]}
    if intent.tool=="prepare_hold":
        p=db.get(PaymentRequest,intent.args.get("payment_id"))
        if not p or p.status not in {"PENDING","HELD","FAILED"}:return {"response":"This request can no longer be held."}
        return {"response":f"Hold {p.merchant} until you release it? A date alone never authorizes payment.","preview":{"kind":"hold","payment_id":p.id,"merchant":p.merchant,"amount":p.amount,"requires_confirmation":True}}
    if intent.tool in {"list_payment_requests","get_urgent_payment_requests"}:
        rows=db.scalars(select(PaymentRequest).where(PaymentRequest.status.in_(["PENDING","HELD"]))).all();rows=[p for p in rows if intent.tool!="get_urgent_payment_requests" or policy(db,p,"auto")["urgency"]=="URGENT"]
        response=f"You have {len(rows)} matching payment requests."
        if intent.tool=="get_urgent_payment_requests" and rows:response="; ".join(f"{p.merchant}, {p.amount/100:.2f} rupees, is urgent because its deadline is less than 15 minutes away" for p in rows)+". No payment has been made."
        return {"response":response,"data":[{"id":p.id,"merchant":p.merchant,"amount":p.amount,"status":p.status} for p in rows]}
    if intent.tool=="get_autopay_settings":return {"response":"Here are your AutoPay settings.","data":{k:getattr(settings_for(db),k) for k in ["enabled","time_sensitive_only","daily_limit","minimum_balance"]}}
    if intent.tool=="evaluate_batch_payments":
        result=batch_preview(db);ids=[item['id'] for item in result['items'] if item['decision']=='ELIGIBLE']
        return {'response':f"{len(ids)} payments are eligible for {result['required_total']/100:.2f} rupees. Review before paying.",'data':result['items'],'preview':{'kind':'batch','total':result['required_total'],'count':len(ids),'payment_ids':ids,'requires_confirmation':bool(ids)}}
    if intent.tool in {"prepare_topup","prepare_withdrawal"}:
        amount=intent.args.get("amount");
        if not amount:return {"response":"What amount would you like to use?"}
        return {"response":f"I prepared a demo {intent.tool.replace('prepare_','')} of {amount/100:.0f} rupees. Please confirm it in the wallet.","preview":{"kind":intent.tool,"amount":amount,"requires_confirmation":True,"demo":True}}
    if intent.tool=="prepare_autopay_settings_change":return {"response":"I prepared your AutoPay settings change. Please confirm it.","preview":{"kind":"autopay","changes":intent.args,"requires_confirmation":True}}
    if intent.tool=="prepare_manual_payment":
        payment_id=intent.args.get("payment_id");merchant=intent.args.get("merchant","").strip().lower();p=db.get(PaymentRequest,payment_id) if payment_id else None
        if not p and merchant:
            terms={merchant,*merchant.split()}
            if any("train" in term for term in terms):terms.add("railway")
            scored=[]
            for candidate in db.scalars(select(PaymentRequest).where(PaymentRequest.status.in_(["PENDING","HELD"]))).all():
                score=sum(1 for term in terms if term and (term in candidate.merchant.lower() or term in candidate.description.lower()))
                if score:scored.append((score,candidate))
            scored.sort(key=lambda item:item[0],reverse=True)
            p=scored[0][1] if scored and (len(scored)==1 or scored[0][0]>scored[1][0]) else None
        if not p:return {"response":"I could not identify one open payment. Please choose it in the inbox or say the merchant name.","preview":{"kind":"payment","requires_confirmation":False}}
        if p.explicit_hold:return {"response":"This payment is on hold. Release it in Payments before asking to pay."}
        if p.status not in {"PENDING","HELD","FAILED"}:return {"response":"This payment is already completed or being processed."}
        source=intent.args.get("payment_source","AI_WALLET")
        return {"response":f"I found {p.merchant} for {p.amount/100:.0f} rupees. It requires {('PayPal Sandbox buyer approval' if source=='PAYPAL_SANDBOX' else 'AI Wallet confirmation')}. ","preview":{"kind":"payment","payment_id":p.id,"merchant":p.merchant,"amount":p.amount,"deadline":p.expires_at.isoformat() if p.expires_at else None,"payment_source":source,"verified":p.verified,"requires_confirmation":True}}
    if intent.tool=="list_payment_drafts":
        rows=db.scalars(select(PaymentIntent).where(PaymentIntent.status.in_(["DRAFT","HELD"])).order_by(PaymentIntent.created_at.desc())).all();return {"response":f"You have {len(rows)} saved payment drafts. None will move money until you authorize execution.","data":[serialize_intent(row) for row in rows]}
    if intent.tool=="create_payment_draft":
        amount=intent.args.get("amount");merchant=intent.args.get("merchant")
        if not amount or not merchant:return {"response":"Tell me the amount and who the draft is for."}
        row=create_draft(db,amount,merchant=merchant,note=intent.args.get("note"));db.commit();return {"response":f"I saved a draft for {merchant} for {amount/100:.0f} rupees. No money was moved.","data":serialize_intent(row)}
    return {"response":intent.response or "Please clarify your request."}
async def transcribe(wav:bytes)->dict:
    if not nvidia_ready():raise VoiceError("NVIDIA Whisper is not configured; use typed commands in demo mode")
    try:
        import riva.client
        s=settings();auth=riva.client.Auth(uri=s.nvidia_whisper_server,use_ssl=True,metadata_args=[["function-id",s.nvidia_whisper_function_id],["authorization",f"Bearer {s.nvidia_api_key}"]]);config=riva.client.RecognitionConfig(language_code=s.nvidia_whisper_language_code,max_alternatives=1,enable_automatic_punctuation=True)
        # The Riva client owns the protobuf configuration.  Only set this optional
        # service-specific field when the installed client exposes it.
        if s.nvidia_whisper_task=="translate" and hasattr(config,"custom_configuration"):config.custom_configuration="task:translate"
        response=riva.client.ASRService(auth).offline_recognize(wav,config);text=" ".join(x.alternatives[0].transcript for x in response.results if x.alternatives)
        if not text.strip():raise VoiceError("No speech was recognized")
        return {"transcript":text,"provider":"nvidia-riva-whisper-large-v3","language":s.nvidia_whisper_language_code}
    except VoiceError:raise
    except Exception as e:raise VoiceError("NVIDIA Whisper transcription failed") from e
async def synthesize(text_value:str,language:str,voice:str|None=None)->tuple[bytes,str]:
    if not nvidia_ready():raise VoiceError("NVIDIA Magpie is not configured")
    s=settings();files={"text":(None,text_value),"language":(None,language),"voice":(None,voice or s.nvidia_magpie_voice),"encoding":(None,s.nvidia_magpie_encoding),"sample_rate_hz":(None,str(s.nvidia_magpie_sample_rate))}
    try:
        async with httpx.AsyncClient(timeout=s.nvidia_nemotron_timeout) as c:r=await c.post(s.nvidia_magpie_synthesis_url,headers={"Authorization":f"Bearer {s.nvidia_api_key}"},files=files);r.raise_for_status();raw=r.content
    except httpx.HTTPError as e:raise VoiceError("NVIDIA Magpie synthesis failed") from e
    if s.nvidia_magpie_encoding=="LINEAR_PCM":
        output=io.BytesIO()
        with wave.open(output,"wb") as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(s.nvidia_magpie_sample_rate);out.writeframes(raw)
        return output.getvalue(),"audio/wav"
    return raw,r.headers.get("content-type","application/octet-stream")

_AUDIO_SUFFIX={"audio/webm":".webm","audio/ogg":".ogg","audio/wav":".wav","audio/x-wav":".wav","audio/mpeg":".mp3","audio/mp4":".m4a"}
def normalize_audio(raw:bytes,content_type:str|None)->tuple[bytes,float]:
    """Validate untrusted browser audio and create temporary Riva-compatible WAV."""
    s=settings(); mime=(content_type or "").split(";",1)[0].lower()
    if not raw:raise VoiceError("The recording is empty")
    if len(raw)>s.voice_max_upload_mb*1024*1024:raise VoiceError("The recording exceeds the upload size limit")
    if mime not in _AUDIO_SUFFIX:raise VoiceError("Unsupported audio format; record WAV, WebM, OGG, MP3, or M4A")
    with tempfile.TemporaryDirectory(prefix="aiwallet-voice-") as directory:
        source=Path(directory)/f"recording{_AUDIO_SUFFIX[mime]}"; target=Path(directory)/"recording.wav";source.write_bytes(raw)
        try:
            probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(source)],capture_output=True,text=True,timeout=10,check=True)
            duration=float(probe.stdout.strip())
            if duration<=0 or duration>s.voice_max_duration_seconds:raise VoiceError(f"Recording duration must be between 1 and {s.voice_max_duration_seconds} seconds")
            subprocess.run(["ffmpeg","-y","-v","error","-i",str(source),"-ac","1","-ar","16000","-sample_fmt","s16",str(target)],capture_output=True,text=True,timeout=20,check=True)
        except subprocess.TimeoutExpired as e:raise VoiceError("Audio conversion timed out") from e
        except subprocess.CalledProcessError as e:raise VoiceError("The uploaded recording is corrupted or cannot be converted") from e
        except ValueError as e:raise VoiceError("The uploaded recording has an invalid duration") from e
        if not target.exists() or target.stat().st_size<44:raise VoiceError("Audio conversion produced no usable audio")
        return target.read_bytes(),duration
