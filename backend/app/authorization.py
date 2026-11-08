"""Transaction-bound wallet PIN authorization. Provider passwords never enter this service."""
import hashlib,hmac,json,secrets
from datetime import datetime,timedelta,timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .core import settings
from .models import AuthorizationChallenge,WalletSecurity,uid

class AuthorizationError(ValueError):pass
def _utc(value:datetime)->datetime:return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
def _digest(pin:str,salt:str)->str:return hashlib.scrypt(pin.encode(),salt=bytes.fromhex(salt),n=2**14,r=8,p=1).hex()
def security_for(db:Session)->WalletSecurity:
    row=db.scalar(select(WalletSecurity).where(WalletSecurity.user_id=="demo-user"))
    if row:return row
    salt=secrets.token_hex(16)
    try:
        with db.begin_nested():
            row=WalletSecurity(user_id="demo-user",pin_salt=salt,pin_hash=_digest(settings().demo_wallet_pin,salt));db.add(row);db.flush()
    except IntegrityError:row=db.scalar(select(WalletSecurity).where(WalletSecurity.user_id=='demo-user').with_for_update())
    return row
def _canonical(value:dict|None)->str:return json.dumps(value or {},sort_keys=True,separators=(",",":"),default=str)
def create_challenge(db:Session,action:str,amount:int,resource_id:str|None=None,details:dict|None=None)->AuthorizationChallenge:
    if action not in {"TOPUP","WITHDRAWAL","PAYMENT","P2P","MANDATE","LOGIN"}:raise AuthorizationError("Unsupported authorization action")
    if amount<=0:raise AuthorizationError("Amount must be positive")
    row=AuthorizationChallenge(action=action,amount=amount,resource_id=resource_id,details=details or {},expires_at=datetime.now(timezone.utc)+timedelta(seconds=settings().authorization_ttl_seconds));db.add(row);db.flush();return row
def verify_challenge(db:Session,challenge_id:str,pin:str)->str:
    security=db.scalar(select(WalletSecurity).where(WalletSecurity.user_id=="demo-user").with_for_update()) or security_for(db)
    row=db.scalar(select(AuthorizationChallenge).where(AuthorizationChallenge.id==challenge_id).with_for_update());now=datetime.now(timezone.utc)
    if not row or row.status!="PENDING" or _utc(row.expires_at)<=now:raise AuthorizationError("Authorization challenge expired or unavailable")
    if security.locked_until and _utc(security.locked_until)>now:raise AuthorizationError("Wallet PIN is temporarily locked")
    if not (len(pin)==6 and pin.isdigit() and hmac.compare_digest(_digest(pin,security.pin_salt),security.pin_hash)):
        security.failed_attempts+=1
        if security.failed_attempts>=settings().pin_max_attempts:security.failed_attempts=0;security.locked_until=now+timedelta(minutes=settings().pin_lockout_minutes)
        raise AuthorizationError("Invalid wallet PIN")
    security.failed_attempts=0;security.locked_until=None;row.status="APPROVED";row.approval_token=secrets.token_urlsafe(32);return row.approval_token
def consume_approval(db:Session,token:str,action:str,amount:int,resource_id:str|None=None,details:dict|None=None)->AuthorizationChallenge:
    db.scalar(select(WalletSecurity).where(WalletSecurity.user_id=="demo-user").with_for_update())
    row=db.scalar(select(AuthorizationChallenge).where(AuthorizationChallenge.approval_token==token).with_for_update());now=datetime.now(timezone.utc)
    if not row or row.status!="APPROVED" or row.used_at or _utc(row.expires_at)<=now:raise AuthorizationError("Approval is invalid, expired, or already used")
    if row.action!=action or row.amount!=amount or row.resource_id!=resource_id:raise AuthorizationError("Approval does not match this transaction")
    if details is not None and not hmac.compare_digest(_canonical(row.details),_canonical(details)):raise AuthorizationError("Approval details do not match this transaction")
    row.status="CONSUMED";row.used_at=now;return row
def change_pin(db:Session,current_pin:str,new_pin:str)->None:
    if not (len(new_pin)==6 and new_pin.isdigit()):raise AuthorizationError("New wallet PIN must contain six digits")
    row=db.scalar(select(WalletSecurity).where(WalletSecurity.user_id=="demo-user").with_for_update()) or security_for(db);now=datetime.now(timezone.utc)
    if row.locked_until and _utc(row.locked_until)>now:raise AuthorizationError("Wallet PIN is temporarily locked")
    if not hmac.compare_digest(_digest(current_pin,row.pin_salt),row.pin_hash):
        row.failed_attempts+=1
        if row.failed_attempts>=settings().pin_max_attempts:row.failed_attempts=0;row.locked_until=now+timedelta(minutes=settings().pin_lockout_minutes)
        raise AuthorizationError("Current wallet PIN is incorrect")
    salt=secrets.token_hex(16);row.pin_salt=salt;row.pin_hash=_digest(new_pin,salt);row.failed_attempts=0;row.locked_until=None
    db.execute(update(AuthorizationChallenge).where(AuthorizationChallenge.user_id==row.user_id,AuthorizationChallenge.status.in_(["PENDING","APPROVED"])).values(status="REVOKED",approval_token=None))
