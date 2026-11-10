from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import PaymentRequest
from app import demo

def test_demo_initializer_is_idempotent_and_uses_services(monkeypatch):
    engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);factory=sessionmaker(bind=engine,expire_on_commit=False);monkeypatch.setattr(demo,"SessionLocal",factory)
    first=demo.initialize_demo();second=demo.initialize_demo()
    with factory() as s:
        rows=s.query(PaymentRequest).filter_by(provider=demo.SEED_PROVIDER).all()
        assert len(rows)==4 and len(first["payment_requests"])==len(second["payment_requests"])==4
