"""Small allowlisted structured lifecycle logs emitted only after DB commit."""
import json,logging
from sqlalchemy import event
from sqlalchemy.orm import Session

logger=logging.getLogger('wallet.lifecycle')
if not logger.handlers:
    handler=logging.StreamHandler();handler.setFormatter(logging.Formatter('%(message)s'));logger.addHandler(handler)
logger.setLevel(logging.INFO);logger.propagate=False
SAFE={'payment_id','batch_id','operation_id','wallet_id','attempt_id','merchant_id','order_id','authorization_id','reservation_id','status','stage','action'}

def queue(db,name,payload):
    db.info.setdefault('lifecycle',[]).append({'event':name,**{k:str(v)[:120] for k,v in payload.items() if k in SAFE}})

@event.listens_for(Session,'after_commit')
def committed(db):
    if not db.in_nested_transaction():
        for item in db.info.pop('lifecycle',[]):logger.info(json.dumps(item,separators=(',',':')))

@event.listens_for(Session,'after_rollback')
def rolled_back(db):db.info.pop('lifecycle',None)
