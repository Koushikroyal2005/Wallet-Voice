"""Mocked NVIDIA contract tests. These are not live-provider evidence."""
import asyncio
import json
import sys
from types import ModuleType,SimpleNamespace
import httpx
import pytest
from app import voice
from app.core import settings


def mock_model(monkeypatch,message):
    monkeypatch.setattr(settings(),'nvidia_enabled',True)
    monkeypatch.setattr(settings(),'nvidia_api_key','synthetic-key-not-a-credential')
    requests=[];original=httpx.AsyncClient
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200,json={'choices':[{'message':message}]})
    monkeypatch.setattr(voice.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    return requests


def call(name,args):return {'tool_calls':[{'function':{'name':name,'arguments':json.dumps(args)}}]}


def test_explicit_preparation_selects_tool_but_model_extracts_amount(monkeypatch):
    requests=mock_model(monkeypatch,call('prepare_topup',{'amount':125050}))
    result=asyncio.run(voice.nemotron_intent('add 1250.50 rupees',[]))
    assert result.provider=='nvidia-nemotron' and result.args=={'amount':125050}
    assert requests[0]['tool_choice']=={'type':'function','function':{'name':'prepare_topup'}}


def test_model_amount_cannot_silently_change_units(monkeypatch):
    mock_model(monkeypatch,call('prepare_topup',{'amount':1250}))
    with pytest.raises(voice.VoiceError,match='amount did not match'):
        asyncio.run(voice.nemotron_intent('add 1250 rupees',[]))


def test_unrequested_autopay_setting_is_removed(monkeypatch):
    mock_model(monkeypatch,call('prepare_autopay_settings_change',{'enabled':False,'time_sensitive_only':False}))
    assert asyncio.run(voice.nemotron_intent('disable autopay',[])).args=={'enabled':False}


def test_opposite_autopay_switch_is_rejected(monkeypatch):
    mock_model(monkeypatch,call('prepare_autopay_settings_change',{'enabled':False}))
    with pytest.raises(voice.VoiceError):asyncio.run(voice.nemotron_intent('enable autopay',[]))


def test_unsolicited_paypal_source_is_rejected(monkeypatch):
    mock_model(monkeypatch,call('prepare_manual_payment',{'merchant':'Rail','payment_source':'PAYPAL_SANDBOX'}))
    with pytest.raises(voice.VoiceError):asyncio.run(voice.nemotron_intent('pay Rail',[]))


def test_model_prose_cannot_fabricate_success(monkeypatch):
    mock_model(monkeypatch,{'content':'I successfully paid your bill.'})
    result=asyncio.run(voice.nemotron_intent('pay the bill',[]))
    assert result.tool=='' and 'successfully paid' not in result.response


@pytest.mark.parametrize('message',[None,{'tool_calls':'invalid'},{'tool_calls':[{}]},call('execute_payment',{}),call('prepare_topup',{'amount':True})])
def test_invalid_model_contract_is_controlled(monkeypatch,message):
    mock_model(monkeypatch,message)
    with pytest.raises(voice.VoiceError):asyncio.run(voice.nemotron_intent('add 500 rupees',[]))


def test_secrets_are_not_sent_and_legacy_secret_history_is_filtered(monkeypatch):
    requests=mock_model(monkeypatch,call('get_wallet_balance',{}))
    with pytest.raises(voice.VoiceError):asyncio.run(voice.nemotron_intent('my pin is 123456',[]))
    assert requests==[]
    asyncio.run(voice.nemotron_intent('wallet balance',[{'role':'user','content':'my OTP is 123456'}]))
    assert len(requests[0]['messages'])==2


@pytest.mark.parametrize('fails',[False,True])
def test_riva_future_timeout_and_thread_contract(monkeypatch,fails):
    monkeypatch.setattr(settings(),'nvidia_enabled',True);monkeypatch.setattr(settings(),'nvidia_api_key','fixture')
    calls=[]
    def result(timeout):
        calls.append(('timeout',timeout))
        if fails:raise TimeoutError('synthetic deadline')
        return SimpleNamespace(results=[SimpleNamespace(alternatives=[SimpleNamespace(transcript='show pending payments')])])
    pending=SimpleNamespace(result=result,done=lambda:not fails,cancel=lambda:calls.append(('cancel',True)))
    class Service:
        def __init__(self,auth):pass
        def offline_recognize(self,audio,config,future=False):
            assert future is True
            return pending
    root=ModuleType('riva');client=ModuleType('riva.client');root.client=client
    client.Auth=lambda **kwargs:object();client.RecognitionConfig=lambda **kwargs:SimpleNamespace();client.ASRService=Service
    monkeypatch.setitem(sys.modules,'riva',root);monkeypatch.setitem(sys.modules,'riva.client',client)
    if fails:
        with pytest.raises(voice.VoiceError):asyncio.run(voice.transcribe(b'synthetic-audio'))
        assert ('cancel',True) in calls
    else:assert asyncio.run(voice.transcribe(b'synthetic-audio'))['transcript']=='show pending payments'
    assert ('timeout',settings().nvidia_whisper_timeout) in calls
