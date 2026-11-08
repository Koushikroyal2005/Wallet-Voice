"""Deterministic follow-up harness: context can prepare, never execute."""
from types import SimpleNamespace
import pytest
from app.context import contextual_intent, contains_authentication_secret
from app.voice import validate_tool_arguments


def conversation():
    return SimpleNamespace(selected_payment_id='old', context={
        'listed_payment_ids':['railway','movie','electronics'],
        'preview':{'payment_source':'PAYPAL_SANDBOX'}})


@pytest.mark.parametrize('text,tool,payment',[
    ('pay the second one','prepare_manual_payment','movie'),
    ('hold the first payment','prepare_hold','railway'),
    ('pay the last one','prepare_manual_payment','electronics'),
])
def test_ordinal_followup(text,tool,payment):
    row=conversation()
    result=contextual_intent(text,row)
    assert result.tool==tool
    assert result.args['payment_id']==payment
    assert row.selected_payment_id==payment


def test_unknown_ordinal_does_not_guess():
    assert contextual_intent('pay the fourth one',conversation()).tool==''


def test_cancel_forgets_references():
    row=conversation()
    contextual_intent('cancel',row)
    assert row.context=={}
    assert row.selected_payment_id is None
    assert contextual_intent('pay it',row).tool==''


def test_switch_back_to_wallet_only_prepares():
    result=contextual_intent('use wallet instead',conversation())
    assert result.tool=='prepare_manual_payment'
    assert result.args['payment_source']=='AI_WALLET'


@pytest.mark.parametrize('text',['my PIN is 123456','OTP 823450','123456','verification code: 1234'])
def test_obvious_secret_disclosure(text):
    assert contains_authentication_secret(text)


def test_amount_is_not_a_secret():
    assert not contains_authentication_secret('Add 1250 rupees to my wallet')


@pytest.mark.parametrize('tool,args',[
    ('get_wallet_balance',{'amount':100}),
    ('prepare_topup',{'amount':True}),
    ('prepare_topup',{'amount':'100'}),
    ('prepare_topup',{}),
    ('prepare_manual_payment',{'payment_source':'BANK'}),
])
def test_tool_contract_rejects_unsafe_arguments(tool,args):
    with pytest.raises(ValueError):validate_tool_arguments(tool,args)


def test_tool_contract_accepts_minor_units():
    assert validate_tool_arguments('prepare_topup',{'amount':125000})=={'amount':125000}


@pytest.mark.parametrize('tool',['prepare_topup','prepare_withdrawal'])
def test_amount_followup_keeps_task(tool):
    row=conversation()
    row.context['awaiting_amount']=tool
    result=contextual_intent('1250.50 rupees',row)
    assert result.tool==tool
    assert result.args=={'amount':125050}


def test_amount_without_task_does_not_guess():
    assert contextual_intent('1250 rupees',conversation()) is None
