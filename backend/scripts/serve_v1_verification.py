"""Local browser verification only. Requires an explicitly named fresh SQLite file."""
import os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from app.core import Settings

Settings.model_config['env_file']=None  # Never load private credentials for fixtures.
target=os.environ.get('DATABASE_URL','')
if not target.startswith('sqlite:///') or not Path(target[10:]).name.startswith('v1-browser-'):
    raise RuntimeError('This verification server requires a fresh v1-browser- SQLite file')
if Path(target[10:]).exists():raise RuntimeError('Refusing to reuse any existing database')
from app.db import Base,engine,SessionLocal
from app.models import PaymentRequest,AutoPaySettings
from app.services import topup_or_withdraw
from app.reminders import schedule
from app.main import app
import uvicorn

Base.metadata.create_all(engine)
with SessionLocal() as db:
    topup_or_withdraw(db,1_000_000,'TOPUP','browser-opening')
    db.add(AutoPaySettings(enabled=False,time_sensitive_only=False,minimum_balance=10000))
    for merchant,description,category,amount in [('Indian Railways','train ticket','travel',125000),('CinemaPass','movie ticket','entertainment',60000),('Demo Kitchen','food order','food',40000)]:
        db.add(PaymentRequest(merchant=merchant,description=description,category=category,amount=amount,verified=True,expires_at=datetime.now(timezone.utc)+timedelta(minutes=12)))
    db.commit();schedule(db);db.commit()
uvicorn.run(app,host='127.0.0.1',port=8194,log_level='error')
