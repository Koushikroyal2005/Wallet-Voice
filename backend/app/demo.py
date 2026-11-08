"""Explicit, repeatable demo data setup. Never runs during normal application startup."""
import argparse
from datetime import datetime,timedelta,timezone
from sqlalchemy import delete,select
from .db import SessionLocal
from .models import PaymentRequest
from .services import emit,policy,settings_for,topup_or_withdraw,wallet

SEED_PROVIDER="DEMO_SEED_V1"
SEED_REQUESTS=[
    ("Indian Railways","travel","Tatkal train ticket",125000,4,True),
    ("CinemaPass","entertainment","Movie ticket",60000,120,True),
    ("ElectroHub","shopping","Flexible electronics request",450000,None,False),
]
def initialize_demo(*,reset:bool=False,autopay_enabled:bool=False):
    """Seed only labelled demo requests and a deterministic 10,000 INR wallet top-up."""
    with SessionLocal() as db:
        if reset:
            # Explicit reset is deliberately narrow: never deletes wallet, journals,
            # attempts, reservations, provider orders, or any non-seed request.
            db.execute(delete(PaymentRequest).where(PaymentRequest.provider==SEED_PROVIDER,PaymentRequest.status.in_(["PENDING","HELD","EXPIRED"])))
        topup_or_withdraw(db,1_000_000,"TOPUP","demo-seed-v1:wallet-opening")
        settings=settings_for(db);settings.enabled=autopay_enabled;settings.time_sensitive_only=True;settings.minimum_balance=10_000
        created=[]
        for merchant,category,description,amount,minutes,verified in SEED_REQUESTS:
            existing=db.scalar(select(PaymentRequest).where(PaymentRequest.provider==SEED_PROVIDER,PaymentRequest.merchant==merchant,PaymentRequest.status.in_(["PENDING","HELD"])))
            if existing:created.append(existing);continue
            p=PaymentRequest(merchant=merchant,category=category,description=description,amount=amount,verified=verified,provider=SEED_PROVIDER,expires_at=datetime.now(timezone.utc)+timedelta(minutes=minutes) if minutes else None);db.add(p);db.flush();p.trace=policy(db,p,"auto");created.append(p);emit(db,"payment.created",{"payment_id":p.id,"source":"demo_initializer"})
        emit(db,"demo.initialized",{"payment_count":len(created),"autopay_enabled":autopay_enabled});db.commit()
        data={"wallet":wallet(db).id,"payment_requests":[{"id":p.id,"merchant":p.merchant,"amount":p.amount,"urgency":p.trace.get("urgency")} for p in created]};db.commit();return data
def main():
    parser=argparse.ArgumentParser(description="Seed repeatable AI Wallet demo data")
    parser.add_argument("--reset",action="store_true",help="remove only pending/held/expired labelled seed requests before reseeding")
    parser.add_argument("--autopay-enabled",action="store_true",help="enable AutoPay for the seeded demonstration")
    args=parser.parse_args();result=initialize_demo(reset=args.reset,autopay_enabled=args.autopay_enabled)
    print(f"Demo ready: {len(result['payment_requests'])} payment requests seeded.")
if __name__=="__main__":main()
