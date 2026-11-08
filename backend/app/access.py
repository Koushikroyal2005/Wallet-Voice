"""Single-owner wallet sessions. This is not a multi-tenant account system."""
import hashlib
import hmac
import secrets
import time
from .core import settings
from .authorization import security_for
from .services import utc

COOKIE='aiwallet_session'

def issue_session(db):
    security=security_for(db)
    db.flush()
    payload=f"{int(time.time())+settings().wallet_session_minutes*60}.{secrets.token_hex(16)}"
    signature=hmac.new(settings().wallet_session_secret.encode(),f'{payload}:{security.pin_hash}:{utc(security.updated_at).isoformat()}'.encode(),hashlib.sha256).hexdigest()
    return f'{payload}.{signature}'

def valid_session(db,token):
    if not settings().require_wallet_login:return True
    if not token or not settings().wallet_session_secret:return False
    try:
        expiry,nonce,signature=token.split('.')
        if int(expiry)<=time.time() or len(nonce)!=32:return False
        security=security_for(db)
        expected=hmac.new(settings().wallet_session_secret.encode(),f'{expiry}.{nonce}:{security.pin_hash}:{utc(security.updated_at).isoformat()}'.encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected,signature)
    except (ValueError,TypeError):return False
