"""Resolve narrow follow-ups from server-owned context; never execute a payment."""
import re
from decimal import Decimal
from .voice import Intent


def contains_authentication_secret(text):
    """Reject obvious authentication disclosures before storage or provider calls.

    This is a narrow guard, not a general-purpose secret detector.
    """
    return bool(re.search(r'\b(?:pin|otp|password|passcode|verification code)\b.{0,24}\b\d{4,8}\b',text,re.I)
                or re.fullmatch(r'\s*\d{4,8}\s*',text))


def contextual_intent(text, conversation):
    value=text.strip().lower().rstrip('.!?')
    preview=(conversation.context or {}).get('preview') or {}
    listed=(conversation.context or {}).get('listed_payment_ids') or []
    awaiting=(conversation.context or {}).get('awaiting_amount')
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
        return Intent('prepare_hold' if value.startswith('hold ') else 'prepare_manual_payment',{'payment_id':listed[index],'payment_source':'AI_WALLET'})
    if value in {'use wallet instead','use my wallet','wallet instead'}:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment would you like to use your wallet for?')
        return Intent('prepare_manual_payment',{'payment_id':conversation.selected_payment_id,'payment_source':'AI_WALLET'})
    if value in {'cancel','never mind','nevermind','forget it'}:
        conversation.selected_payment_id=None
        conversation.context={}
        return Intent('',{},'Cancelled the preview. No payment was made.')
    if re.search(r'\b(?:change|make|instead)\b',value) and re.search(r'\d',value):
        return Intent('',{},'I cleared the old preview. Merchant request amounts cannot be changed; create a new draft for a different amount.')
    if value in {'pay it','pay that','pay that one','pay this','pay the one','yes pay it'} or ('paypal' in value and any(term in value for term in ['instead','use ','with '])):
        if not conversation.selected_payment_id:return Intent('',{},'Which payment do you mean? Choose a merchant or ask for your pending payments.')
        return Intent('prepare_manual_payment',{'payment_id':conversation.selected_payment_id,'payment_source':'PAYPAL_SANDBOX' if 'paypal' in value else preview.get('payment_source','AI_WALLET')})
    if value in {'hold it','hold that','hold that one','hold until friday','hold for later'}:
        if not conversation.selected_payment_id:return Intent('',{},'Which payment would you like to hold?')
        return Intent('prepare_hold',{'payment_id':conversation.selected_payment_id})
    return None
