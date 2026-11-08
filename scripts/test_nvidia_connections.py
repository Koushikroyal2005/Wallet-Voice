"""Credential-gated live smoke checks; never prints the NVIDIA API key."""
import asyncio
import os
import sys

sys.path.insert(0,os.path.join(os.path.dirname(__file__),"..","backend"))
from app.core import settings
from app.voice import nvidia_ready,synthesize

async def live_check():
    audio,content_type=await synthesize("AI Wallet NVIDIA smoke test.",settings().nvidia_magpie_language)
    if not audio or not content_type.startswith("audio/"): raise RuntimeError("Magpie returned unusable audio")
    print(f"PASSED: Magpie synthesis ({content_type}, {len(audio)} bytes)")
    print("Whisper requires a deliberate recorded fixture and is not invoked by this no-audio smoke check.")
    return 0
def main():
    if not nvidia_ready():
        print("SKIPPED: set NVIDIA_ENABLED=true and NVIDIA_API_KEY to run live NVIDIA smoke checks",flush=True)
        return 0
    return asyncio.run(live_check())
if __name__=="__main__":raise SystemExit(main())
