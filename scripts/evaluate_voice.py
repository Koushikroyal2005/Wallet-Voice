"""Run synthetic intent evaluations; never executes a real payment or logs keys."""
import argparse
import asyncio
from collections import Counter
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import copy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'backend'/'tests'))
from app.voice import nvidia_ready,VoiceError
from voice_eval_support import CASES,evaluate_case
from app.context import contextual_intent,contains_authentication_secret


async def run(mode):
    if mode=='model' and not nvidia_ready():
        print('SKIPPED: NVIDIA Nemotron evaluation requires NVIDIA_ENABLED=true and an API key. No model calls were performed.')
        return 0
    passed=0;providers=Counter();durations=[];model_attempts=0
    for case in CASES:
        start=time.monotonic()
        if mode=='model' and not contains_authentication_secret(case['text']):
            state=SimpleNamespace(selected_payment_id=case.get('selected'),context=copy.deepcopy(case.get('context',{})))
            model_attempts+=contextual_intent(case['text'],state) is None
        try:
            result=await evaluate_case(case,model=mode=='model')
            passed+=1;providers[result['provider']]+=1
            print(f"PASS | {mode} | {case['id']} | {result['provider']} | {result['tool']}",flush=True)
        except AssertionError as error:
            print(f"FAIL | {mode} | {case['id']} | {error}",flush=True)
        except VoiceError as error:
            print(f"ERROR | {mode} | {case['id']} | {error}",flush=True)
        durations.append((time.monotonic()-start)*1000)
    print(f'RESULT | mode={mode} | passed={passed} | failed={len(CASES)-passed} | total={len(CASES)} | model_attempts={model_attempts} | mean_case_ms={sum(durations)/len(durations):.0f} | passed_case_providers={dict(providers)}')
    print('Synthetic request/argument checks only. This does not verify microphone quality, Whisper transcription, TTS playback or live payments.')
    return 0 if passed==len(CASES) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['deterministic','model'],required=True)
    raise SystemExit(asyncio.run(run(parser.parse_args().mode)))
