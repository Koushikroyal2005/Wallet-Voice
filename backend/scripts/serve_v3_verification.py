"""Test-only fresh API. Synthetic one-shot uncertainty, actual ledger reconciliation."""
import os,hashlib
from pathlib import Path
from app.core import Settings
Settings.model_config['env_file']=None
target=os.environ.get('DATABASE_URL','')
if not target.startswith('sqlite:///') or not Path(target[10:]).name.startswith('v3-browser-') or Path(target[10:]).exists():raise RuntimeError('Requires a fresh v3-browser- isolated SQLite file')
from app.db import Base,engine,SessionLocal
from app.models import MerchantIdentity,AutoPaySettings
from app.services import topup_or_withdraw
from app.providers import DemoPaymentProvider,ProviderResult
from app.main import app
from app.maintenance import tick
import uvicorn
Base.metadata.create_all(engine)
with SessionLocal() as db:
    topup_or_withdraw(db,1_000_000,'TOPUP','browser-opening')
    db.add(AutoPaySettings(enabled=False,time_sensitive_only=False,minimum_balance=0))
    for ident,name,key in [('demo-railway','Demo Railway',os.environ['V3_RAIL_KEY']),('demo-food','Demo Kitchen',os.environ['V3_FOOD_KEY'])]:db.add(MerchantIdentity(id=ident,name=name,secret_hash=hashlib.sha256(key.encode()).hexdigest()))
    db.commit()
original=DemoPaymentProvider.execute;seen=set()
def uncertain_once(self,request,attempt):
    if 'pending-once' in request.description and attempt.id not in seen:
        seen.add(attempt.id);return ProviderResult(None,'')
    return original(self,request,attempt)
DemoPaymentProvider.execute=uncertain_once
@app.post('/api/test/reconcile')
def reconcile():
    tick();return {'worker_tick':True}
uvicorn.run(app,host='127.0.0.1',port=8198,log_level='error')
