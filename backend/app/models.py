import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now() -> datetime: return datetime.now(timezone.utc)
def uid() -> str: return str(uuid.uuid4())

class Status(str, enum.Enum):
    CREATED="CREATED"; PENDING="PENDING"; HELD="HELD"; READY="READY"; AWAITING_APPROVAL="AWAITING_APPROVAL"; PROCESSING="PROCESSING"; SUCCEEDED="SUCCEEDED"; FAILED="FAILED"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"; REFUNDED="REFUNDED"
class ReservationStatus(str, enum.Enum): ACTIVE="ACTIVE"; CONSUMED="CONSUMED"; RELEASED="RELEASED"; EXPIRED="EXPIRED"

class Wallet(Base):
    __tablename__="wallets"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",unique=True); currency: Mapped[str]=mapped_column(String(3),default="INR")
    cached_balance: Mapped[int]=mapped_column(Integer,default=0); ledger_account_id: Mapped[str|None]=mapped_column(ForeignKey("ledger_accounts.id"),nullable=True,unique=True)
class LedgerAccount(Base):
    __tablename__="ledger_accounts"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); name: Mapped[str]=mapped_column(String,unique=True); account_type: Mapped[str]=mapped_column(String); currency: Mapped[str]=mapped_column(String(3),default="INR")
    normal_direction: Mapped[str]=mapped_column(String); wallet_id: Mapped[str|None]=mapped_column(ForeignKey("wallets.id"),nullable=True,unique=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Operation(Base):
    __tablename__="operations"; __table_args__=(UniqueConstraint("idempotency_key",name="uq_operations_idempotency"),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); kind: Mapped[str]=mapped_column(String); amount: Mapped[int]=mapped_column(Integer); status: Mapped[str]=mapped_column(String,default=Status.PENDING.value)
    reference: Mapped[str]=mapped_column(String); idempotency_key: Mapped[str]=mapped_column(String); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class JournalTransaction(Base):
    __tablename__="journal_transactions"; __table_args__=(UniqueConstraint("operation_id",name="uq_journal_operation"),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); operation_id: Mapped[str]=mapped_column(ForeignKey("operations.id")); description: Mapped[str]=mapped_column(String); reference: Mapped[str]=mapped_column(String); status: Mapped[str]=mapped_column(String,default="POSTED"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class LedgerEntry(Base):
    __tablename__="ledger_entries"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); journal_transaction_id: Mapped[str]=mapped_column(ForeignKey("journal_transactions.id"),index=True); ledger_account_id: Mapped[str]=mapped_column(ForeignKey("ledger_accounts.id"),index=True); direction: Mapped[str]=mapped_column(String); amount: Mapped[int]=mapped_column(Integer); currency: Mapped[str]=mapped_column(String(3)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PaymentRequest(Base):
    __tablename__="payment_requests"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); merchant: Mapped[str]=mapped_column(String); category: Mapped[str]=mapped_column(String); description: Mapped[str]=mapped_column(String); amount: Mapped[int]=mapped_column(Integer); currency: Mapped[str]=mapped_column(String(3),default="INR"); expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); verified: Mapped[bool]=mapped_column(Boolean,default=False); provider: Mapped[str]=mapped_column(String,default="DEMO_MERCHANT"); status: Mapped[str]=mapped_column(String,default=Status.PENDING.value); explicit_hold: Mapped[bool]=mapped_column(Boolean,default=False); trace: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PaymentAttempt(Base):
    __tablename__="payment_attempts"; __table_args__=(UniqueConstraint("idempotency_key",name="uq_attempt_idempotency"),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); payment_request_id: Mapped[str]=mapped_column(ForeignKey("payment_requests.id"),index=True); reservation_id: Mapped[str|None]=mapped_column(ForeignKey("payment_reservations.id"),nullable=True); idempotency_key: Mapped[str]=mapped_column(String); provider_reference: Mapped[str|None]=mapped_column(String,nullable=True); status: Mapped[str]=mapped_column(String,default=Status.PROCESSING.value); failure_reason: Mapped[str|None]=mapped_column(String,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PaymentReservation(Base):
    __tablename__="payment_reservations"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); wallet_id: Mapped[str]=mapped_column(ForeignKey("wallets.id"),index=True); payment_request_id: Mapped[str]=mapped_column(ForeignKey("payment_requests.id"),index=True); payment_attempt_id: Mapped[str|None]=mapped_column(ForeignKey("payment_attempts.id"),nullable=True); amount: Mapped[int]=mapped_column(Integer); currency: Mapped[str]=mapped_column(String(3)); status: Mapped[str]=mapped_column(String,default=ReservationStatus.ACTIVE.value); expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class AutoPaySettings(Base):
    __tablename__="autopay_settings"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",unique=True); enabled: Mapped[bool]=mapped_column(Boolean,default=False); time_sensitive_only: Mapped[bool]=mapped_column(Boolean,default=True); per_transaction_limit: Mapped[int]=mapped_column(Integer,default=500000); daily_limit: Mapped[int]=mapped_column(Integer,default=1000000); minimum_balance: Mapped[int]=mapped_column(Integer,default=10000); allow_unknown_merchants: Mapped[bool]=mapped_column(Boolean,default=False)
class AppEvent(Base):
    __tablename__="app_events"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); event_type: Mapped[str]=mapped_column(String,index=True); payload: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PayPalOrder(Base):
    __tablename__="paypal_orders"; __table_args__=(UniqueConstraint("paypal_order_id",name="uq_paypal_order_id"),UniqueConstraint("idempotency_key",name="uq_paypal_order_key"),UniqueConstraint("paypal_capture_id",name="uq_paypal_capture_id"))
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",index=True); payment_request_id: Mapped[str]=mapped_column(ForeignKey("payment_requests.id"),index=True); payment_attempt_id: Mapped[str|None]=mapped_column(ForeignKey("payment_attempts.id"),nullable=True)
    paypal_order_id: Mapped[str]=mapped_column(String,index=True); paypal_capture_id: Mapped[str|None]=mapped_column(String,nullable=True); idempotency_key: Mapped[str]=mapped_column(String); original_amount: Mapped[int]=mapped_column(Integer); original_currency: Mapped[str]=mapped_column(String(3)); provider_amount: Mapped[str]=mapped_column(String(32)); provider_currency: Mapped[str]=mapped_column(String(3)); conversion_rate: Mapped[str|None]=mapped_column(String(32),nullable=True); provider_status: Mapped[str]=mapped_column(String,default="CREATED"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now); captured_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class PayPalWebhookEvent(Base):
    __tablename__="paypal_webhook_events"; __table_args__=(UniqueConstraint("paypal_event_id",name="uq_paypal_event_id"),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); paypal_event_id: Mapped[str]=mapped_column(String,index=True); event_type: Mapped[str]=mapped_column(String); paypal_order_id: Mapped[str|None]=mapped_column(String,nullable=True,index=True); verified: Mapped[bool]=mapped_column(Boolean,default=False); payload: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class WalletSecurity(Base):
    __tablename__="wallet_security"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",unique=True); pin_salt: Mapped[str]=mapped_column(String); pin_hash: Mapped[str]=mapped_column(String); failed_attempts: Mapped[int]=mapped_column(Integer,default=0); locked_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class AuthorizationChallenge(Base):
    __tablename__="authorization_challenges"; __table_args__=(UniqueConstraint("approval_token",name="uq_authorization_token"),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",index=True); action: Mapped[str]=mapped_column(String); amount: Mapped[int]=mapped_column(Integer); resource_id: Mapped[str|None]=mapped_column(String,nullable=True); details: Mapped[dict]=mapped_column(JSON,default=dict); status: Mapped[str]=mapped_column(String,default="PENDING"); approval_token: Mapped[str|None]=mapped_column(String,nullable=True); expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); used_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Conversation(Base):
    __tablename__="conversations"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",index=True); selected_payment_id: Mapped[str|None]=mapped_column(ForeignKey("payment_requests.id"),nullable=True); selected_intent_id: Mapped[str|None]=mapped_column(String,nullable=True); context: Mapped[dict]=mapped_column(JSON,default=dict); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ConversationMessage(Base):
    __tablename__="conversation_messages"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); conversation_id: Mapped[str]=mapped_column(ForeignKey("conversations.id"),index=True); role: Mapped[str]=mapped_column(String); content: Mapped[str]=mapped_column(String); tool_name: Mapped[str|None]=mapped_column(String,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Recipient(Base):
    __tablename__="recipients"; __table_args__=(UniqueConstraint("user_id","handle",name="uq_recipient_handle"),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",index=True); name: Mapped[str]=mapped_column(String); handle: Mapped[str]=mapped_column(String); handle_type: Mapped[str]=mapped_column(String,default="PHONE"); verified: Mapped[bool]=mapped_column(Boolean,default=False); provider: Mapped[str]=mapped_column(String,default="AI_WALLET_DEMO"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PaymentIntent(Base):
    __tablename__="payment_intents"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",index=True); kind: Mapped[str]=mapped_column(String,default="P2P"); recipient_id: Mapped[str|None]=mapped_column(ForeignKey("recipients.id"),nullable=True); merchant: Mapped[str|None]=mapped_column(String,nullable=True); amount: Mapped[int]=mapped_column(Integer); currency: Mapped[str]=mapped_column(String(3),default="INR"); note: Mapped[str|None]=mapped_column(String,nullable=True); source: Mapped[str]=mapped_column(String,default="AI_WALLET"); status: Mapped[str]=mapped_column(String,default="DRAFT"); version: Mapped[int]=mapped_column(Integer,default=1); execute_after: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); payment_request_id: Mapped[str|None]=mapped_column(ForeignKey("payment_requests.id"),nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class SpendingMandate(Base):
    __tablename__="spending_mandates"
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String,default="demo-user",index=True); merchant: Mapped[str]=mapped_column(String,index=True); max_amount: Mapped[int]=mapped_column(Integer); daily_limit: Mapped[int]=mapped_column(Integer); spent_today: Mapped[int]=mapped_column(Integer,default=0); context: Mapped[dict]=mapped_column(JSON,default=dict); status: Mapped[str]=mapped_column(String,default="ACTIVE"); expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True)); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PaymentBatch(Base):
    __tablename__='payment_batches'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(String,default='demo-user',index=True)
    snapshot: Mapped[dict]=mapped_column(JSON)
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    total: Mapped[int]=mapped_column(Integer)
    source: Mapped[str]=mapped_column(String,default='AI_WALLET')
    status: Mapped[str]=mapped_column(String,default='REVIEW')
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    approval_id: Mapped[str|None]=mapped_column(ForeignKey('authorization_challenges.id'),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PaymentBatchItem(Base):
    __tablename__='payment_batch_items'
    __table_args__=(UniqueConstraint('batch_id','payment_request_id',name='uq_batch_request'),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    batch_id: Mapped[str]=mapped_column(ForeignKey('payment_batches.id'),index=True)
    payment_request_id: Mapped[str]=mapped_column(ForeignKey('payment_requests.id'))
    attempt_id: Mapped[str|None]=mapped_column(ForeignKey('payment_attempts.id'),nullable=True)

class PaymentReminder(Base):
    __tablename__='payment_reminders'
    __table_args__=(UniqueConstraint('payment_request_id','stage',name='uq_payment_reminder_stage'),)
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    payment_request_id: Mapped[str]=mapped_column(ForeignKey('payment_requests.id'),index=True)
    stage: Mapped[str]=mapped_column(String)
    status: Mapped[str]=mapped_column(String,default='PENDING')
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    deliveries: Mapped[dict]=mapped_column(JSON,default=dict)
    next_attempt_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class NotificationPreferences(Base):
    __tablename__='notification_preferences'
    user_id: Mapped[str]=mapped_column(String,primary_key=True,default='demo-user')
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    push_enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    quiet_start: Mapped[int]=mapped_column(Integer,default=22)
    quiet_end: Mapped[int]=mapped_column(Integer,default=8)

class PushSubscription(Base):
    __tablename__='push_subscriptions'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(String,default='demo-user')
    endpoint: Mapped[str]=mapped_column(String,unique=True)
    subscription: Mapped[dict]=mapped_column(JSON)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
