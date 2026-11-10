from dataclasses import dataclass
from typing import Protocol,Any
from .models import PaymentAttempt, PaymentRequest
@dataclass(frozen=True)
class ProviderResult: success: bool|None; reference: str; reason: str|None=None
class InternalWalletPaymentProvider(Protocol):
    def execute(self,request:PaymentRequest,attempt:PaymentAttempt)->ProviderResult:...
class NotificationProvider(Protocol):
    def __call__(self,**kwargs:Any)->Any:...
class UnknownProviderOutcome(Exception):pass
class DemoPaymentProvider:
    mode='SIMULATED'
    """Explicit simulated provider; it never represents an external charge."""
    def execute(self, request:PaymentRequest, attempt:PaymentAttempt)->ProviderResult:
        if "force-fail" in request.description.lower(): return ProviderResult(False,f"DEMO-{attempt.id[:8]}","DEMO_PROVIDER_FAILURE")
        return ProviderResult(True,f"DEMO-{attempt.id[:8]}")
