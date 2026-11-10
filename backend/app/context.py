"""Resolve narrow follow-ups from server-owned context; never execute a payment."""
import re
from decimal import Decimal
from .voice import Intent


def contains_authentication_secret(text):
    """Reject obvious authentication disclosures before storage or provider calls.

    This is a narrow guard, not a general-purpose secret detector.
    """
    return bool(re.search(r'\b(?:pin|otp|password|passcode|verification code)\b.{0,24}\b(?:\d[\s,-]*){4,8}\b',text,re.I)
                or re.search(r'\b(?:pin|otp|password|passcode|verification code)\s*(?:is|:|=)\s*\S+',text,re.I)
                or re.search(r'\b(?:pin|otp|passcode|verification code)\b.{0,16}\b(?:(?:zero|one|two|three|four|five|six|seven|eight|nine)[\s,-]+){3,7}(?:zero|one|two|three|four|five|six|seven|eight|nine)\b',text,re.I)
                or re.fullmatch(r'\s*\d{4,8}\s*',text))


def contextual_intent(text, conversation):
    result=_resolve_context(text,conversation)
    if result:result.provider='context-resolver'
    return result


def _resolve_context(text, conversation):
    value=text.strip().lower().rstrip('.!?')
    preview=(conversation.context or {}).get('preview') or {}
    listed=(conversation.context or {}).get('listed_payment_ids') or []
    awaiting=(conversation.context or {}).get('awaiting_amount')
    if re.search(r'[$€£]|\b(?:usd|dollars?|eur|euros?|gbp|pounds?)\b',value):
        conversation.selected_payment_id=None
        conversation.context={}
        return Intent('',{},'Wallet amounts are in INR. Please state the amount in rupees; I will not assume a currency conversion. PayPal shows its separate Sandbox conversion at review.')
    if re.search(r'-\s*\d|\d+\.\d{3,}|\d.*\b(?:or|and)\b.*\d',value):
        return Intent('',{},'Please give one positive rupee amount with at most two decimal places.')
    if re.search(r'\b(?:bypass|ignore|skip)\b.{0,30}\b(?:approval|confirmation|pin|rules)\b',value):
        return Intent('',{},'Financial actions always require your approval in the secure review.')
    if value in {'stop','stop talking','no','not that one','actually not that one'}:
        conversation.selected_payment_id=None
        conversation.context={}
        return Intent('',{},'Stopped. No new payment was made. Which payment would you like to look at?')
    if value in {'why','why that one','why is it urgent','explain','show details','who sent this request','is this merchant recognized','what happened to my order'}:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment should I explain? Ask for the list or name the business.')
        return Intent('get_payment_details',{'payment_id':conversation.selected_payment_id})
    source=({'paypal':'PAYPAL_SANDBOX','use paypal':'PAYPAL_SANDBOX','use paypal instead':'PAYPAL_SANDBOX',
             'wallet':'AI_WALLET','my wallet':'AI_WALLET','use wallet':'AI_WALLET'}).get(value)
    if source:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment would you like to use that payment method for?')
        return Intent('prepare_manual_payment',{'payment_id':conversation.selected_payment_id,'payment_source':source})
    if awaiting in {'prepare_topup','prepare_withdrawal'}:
        amount=re.fullmatch(r'(?:₹\s*|rs\.?\s*|rupees\s*)?(\d+(?:\.\d{1,2})?)\s*(?:rupees|rs)?',value)
        if amount:
            minor=int(Decimal(amount.group(1))*100)
            if minor>0:return Intent(awaiting,{'amount':minor})
    ordinal=re.fullmatch(r'(?:pay |hold |show )?(?:the )?(first|second|third|fourth|last)(?: one| payment)?',value)
    if ordinal:
        index={'first':0,'second':1,'third':2,'fourth':3,'last':-1}[ordinal.group(1)]
        if not listed or index>=len(listed):
            return Intent('',{},'Please ask for your pending payments first, then choose one from that list.')
        conversation.selected_payment_id=listed[index]
        tool='prepare_hold' if value.startswith('hold ') else 'get_payment_details' if value.startswith('show ') else 'prepare_manual_payment'
        args={'payment_id':listed[index]}
        if tool=='prepare_manual_payment':args['payment_source']='AI_WALLET'
        return Intent(tool,args)
    if value in {'use wallet instead','use my wallet','wallet instead'}:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment would you like to use your wallet for?')
        return Intent('prepare_manual_payment',{'payment_id':conversation.selected_payment_id,'payment_source':'AI_WALLET'})
    if value in {'cancel','cancel it','cancel that one',"don't pay",'do not pay','never mind','nevermind','forget it'}:
        conversation.selected_payment_id=None
        conversation.context={}
        return Intent('',{},'Cancelled this preview. This command did not submit a payment. Check Payments for any earlier submitted action.')
    if re.search(r'\b(?:change|make|instead)\b',value) and re.search(r'\d',value):
        conversation.selected_payment_id=None
        conversation.context={}
        return Intent('',{},'I cleared the old preview. Merchant request amounts cannot be changed; create a new draft for a different amount.')
    if value in {'pay it','pay that','pay that one','pay this','pay the one','yes pay it','pay it again','pay that one again'}:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment do you mean? Choose a merchant or ask for your pending payments.')
        return Intent('prepare_manual_payment',{'payment_id':conversation.selected_payment_id,'payment_source':preview.get('payment_source') or (conversation.context or {}).get('selected_source','AI_WALLET')})
    if value=='remind me later':
        if not conversation.selected_payment_id:return Intent('',{},'Which payment should I remind you about? Choose a request first.')
        return Intent('snooze_payment',{'payment_id':conversation.selected_payment_id})
    if value in {'hold it','hold that','hold that one','hold until friday','hold for later'}:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment would you like to hold?')
        return Intent('prepare_hold',{'payment_id':conversation.selected_payment_id})
    return None
