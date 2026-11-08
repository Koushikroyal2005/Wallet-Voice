from dataclasses import dataclass
from .models import PaymentAttempt, PaymentRequest
@dataclass(frozen=True)
class ProviderResult: success: bool; reference: str; reason: str|None=None
class DemoPaymentProvider:
    """Explicit simulated provider; it never represents an external charge."""
    def execute(self, request:PaymentRequest, attempt:PaymentAttempt)->ProviderResult:
        if "force-fail" in request.description.lower(): return ProviderResult(False,f"DEMO-{attempt.id[:8]}","DEMO_PROVIDER_FAILURE")
        return ProviderResult(True,f"DEMO-{attempt.id[:8]}")
