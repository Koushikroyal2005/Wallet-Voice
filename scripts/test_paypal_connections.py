"""Credential-gated PayPal Sandbox connectivity smoke check; never captures an order."""
import asyncio,os,sys,time
sys.path.insert(0,os.path.join(os.path.dirname(__file__),"..","backend"))
from app.paypal import PayPalError,access_token,configured,request
async def live_check(started):
    try:
        await access_token();print(f"OAuth | PASSED | 200 | {(time.monotonic()-started):.2f}s")
        print("Orders | SKIPPED | - | No order is created or captured by this safe connectivity check")
        return 0
    except PayPalError as e:print(f"OAuth | FAILED | - | {e}");return 1
def main():
    if not configured():print("OAuth | SKIPPED | - | Set PAYPAL_ENABLED=true with Sandbox credentials",flush=True);return 0
    return asyncio.run(live_check(time.monotonic()))
if __name__=="__main__":raise SystemExit(main())
