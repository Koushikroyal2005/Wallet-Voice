"""Fresh SQLite API fixture with credentials supplied only by its test parent."""
import os,hashlib
from pathlib import Path
from app.core import Settings
Settings.model_config['env_file']=None
target=os.environ.get('DATABASE_URL','')
if not target.startswith('sqlite:///') or not Path(target[10:]).name.startswith('v2-browser-'):raise RuntimeError('Requires an isolated v2-browser- SQLite file')
existing=Path(target[10:]).exists()
if existing and os.environ.get('V2_REOPEN_VERIFY')!='true':raise RuntimeError('Refusing to reuse an existing database without the explicit test restart flag')
from app.db import Base,engine,SessionLocal
from app.models import MerchantIdentity,AutoPaySettings
from app.services import topup_or_withdraw
from app.main import app
import uvicorn
Base.metadata.create_all(engine)
if not existing:
    with SessionLocal() as db:
        topup_or_withdraw(db,1_000_000,'TOPUP','browser-opening')
        db.add(AutoPaySettings(enabled=False,time_sensitive_only=False,minimum_balance=0))
        for ident,name,key in [('demo-railway','Demo Railway',os.environ['V2_RAIL_KEY']),('demo-food','Demo Kitchen',os.environ['V2_FOOD_KEY'])]:db.add(MerchantIdentity(id=ident,name=name,secret_hash=hashlib.sha256(key.encode()).hexdigest()))
        db.commit()
uvicorn.run(app,host='127.0.0.1',port=8195,log_level='error')
