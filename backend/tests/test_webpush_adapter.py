"""Offline Web Push encryption/signing; never calls a real push endpoint."""
import base64
import os
from types import SimpleNamespace
import pytest

def test_webpush_encrypts_and_signs_without_network():
    pywebpush=pytest.importorskip('pywebpush',reason='optional Web Push dependency not installed in this interpreter')
    from py_vapid import Vapid
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    vapid=Vapid();vapid.generate_keys()
    receiver=ec.generate_private_key(ec.SECP256R1())
    key=receiver.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    encode=lambda value:base64.urlsafe_b64encode(value).decode().rstrip('=')
    sent=[]
    class Session:
        def post(self,url,**kwargs):
            sent.append((url,kwargs));return SimpleNamespace(status_code=201,text='accepted',headers={})
    pywebpush.webpush(subscription_info={'endpoint':'https://fcm.googleapis.com/synthetic-test','keys':{'p256dh':encode(key),'auth':encode(os.urandom(16))}},data='{"title":"Review payment"}',vapid_private_key=vapid,vapid_claims={'sub':'mailto:test@example.invalid'},ttl=60,timeout=5,requests_session=Session())
    assert len(sent)==1
    _,request=sent[0]
    assert request['headers']['authorization'].startswith('vapid ')
    assert request['headers']['content-encoding']=='aes128gcm'
    assert b'Review payment' not in request['data']
