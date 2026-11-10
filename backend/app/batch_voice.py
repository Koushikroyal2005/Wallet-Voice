"""Server resolution for explicit multi-request selection and corrections."""
import re
from sqlalchemy import select
from .models import PaymentRequest,PaymentBatch
from .payment_batches import create_batch,view,get_batch

ALIASES={'train':{'train','railway','railways','rail','irctc'},'movie':{'movie','movies','cinema','cinemapass'},'food':{'food','meal','restaurant','kitchen'}}
STOP={'pay','my','the','a','an','ticket','tickets','request','requests','order','orders','please','and','for','me'}

def matching(rows,phrase):
    words=set(re.findall(r'[a-z0-9]+',phrase.lower()))-STOP
    expanded=set(words)
    for terms in ALIASES.values():
        if terms & words:expanded|=terms
    return [p for p in rows if expanded & set(re.findall(r'[a-z0-9]+',(p.merchant+' '+p.description+' '+p.category).lower()))]

def status_intent(db,text,state):
    from .voice import Intent
    value=text.lower().strip().rstrip('.!?')
    if not (value.startswith('did ') and 'payment' in value or value.startswith('what happened to ') or value in {'who sent this request','is this merchant recognized'}):return None
    selected=state.selected_payment_id
    if value in {'what happened to my order','who sent this request','is this merchant recognized'}:
        return Intent('get_payment_details',{'payment_id':selected},provider='context-resolver') if selected else Intent('',{},'Which request? Name the merchant or choose one from Payments.',provider='context-resolver')
    phrase=re.sub(r'\b(did|what|happened|to|my|payment|succeed|succeeded|order|orders)\b',' ',value)
    matches=matching(list(db.scalars(select(PaymentRequest))),phrase)
    if len(matches)!=1:return Intent('',{},f'I found {len(matches)} matching requests. Choose the exact request in Payments.',provider='context-resolver')
    return Intent('get_payment_details',{'payment_id':matches[0].id},provider='context-resolver')

def resolve(db,args,listed=()):
    rows=list(db.scalars(select(PaymentRequest).where(PaymentRequest.status.in_(['PENDING','HELD','FAILED']))))
    chosen=[]
    for phrase in args.get('include',[]):
        found=matching(rows,phrase)
        if len(found)!=1:return None,f'Please choose one request for “{phrase}”; I found {len(found)} matches.'
        chosen.append(found[0].id)
    for position in args.get('positions',[]):
        if position<1 or position>len(listed):return None,'Ask for your payment list first, then choose positions from that list.'
        chosen.append(listed[position-1])
    excluded={p.id for phrase in args.get('exclude',[]) for p in matching(rows,phrase)}
    chosen=list(dict.fromkeys(i for i in chosen if i not in excluded))
    return (chosen,None) if chosen else (None,'No requests remain selected. Which payments should I review?')

def interpret(text,context):
    value=text.lower().strip().rstrip('.!?')
    previous=context.get('batch_id')
    if previous and 'paypal' in value:return {'unsupported_source':True}
    if previous and value in {'how much will i have left if i pay these','how much will i have left','use my wallet','use wallet','use wallet instead','use my wallet instead'}:return {'existing':previous}
    if previous and value in {'how much will remain','how much will remain?'}:return {'existing':previous}
    if previous and value.startswith("don't pay "):return {'existing':previous,'remove':value[10:]}
    if previous and value.startswith('remove '):return {'existing':previous,'remove':value[7:]}
    if not re.match(r'^(?:please )?pay\b',value) or ' and ' not in value:return None
    if 'paypal' in value:return {'unsupported_source':True}
    include,*excluded=re.split(r'\b(?:but leave|but not|not|except|leave out)\b',value,maxsplit=1)
    positions=[]
    ordinals={'first':1,'second':2,'third':3,'fourth':4,'fifth':5}
    ordinal_words=re.findall(r'\b(first|second|third|fourth|fifth)\b',include)
    if ordinal_words:positions=[ordinals[x] for x in ordinal_words];phrases=[]
    else:phrases=[x.strip(' ,') for x in re.split(r'\band\b|,',include) if x.strip(' ,')]
    return {'include':phrases,'exclude':excluded,'positions':positions}

def prepare(db,args,context):
    if args.get('unsupported_source'):
        retire(db,context.get('batch_id'))
        return {'response':'PayPal needs separate buyer approval for each order. Select one request in Payments to review PayPal Sandbox checkout. No batch was submitted.','clear_selection':True}
    if args.get('existing'):
        old=get_batch(db,args['existing'],True)
        if not old or old.user_id!='demo-user':return {'response':'The previous review is unavailable. Choose your requests again.'}
        ids=[x['id'] for x in old.snapshot['items']]
        if args.get('remove'):
            if old.status!='REVIEW':return {'response':'That review was already submitted or closed. Check its recorded outcomes before making a new selection.'}
            rows=[db.get(PaymentRequest,i) for i in ids]
            matches=matching([p for p in rows if p],args['remove'])
            if len(matches)!=1:return {'response':'Which one should I remove? Please name exactly one selected business.'}
            ids=[i for i in ids if i!=matches[0].id]
        elif old.status=='REVIEW':return outcome(db,old)
    else:
        ids,error=resolve(db,args,context.get('listed_payment_ids',[]))
        if error:return {'response':error,'clear_selection':True}
    if not ids:return {'response':'No requests selected. No payment was submitted.','clear_selection':True}
    retire(db,context.get('batch_id'))
    return outcome(db,create_batch(db,ids))

def retire(db,ident):
    if ident:
        old=get_batch(db,ident,True)
        if old.status=='REVIEW':old.status='CANCELLED'

def outcome(db,batch):
    result=view(db,batch)
    return {'response':f"Review these {len(result['items'])} exact requests. Total {result['total']/100:.2f} INR; projected available balance {result['remaining_after_payment']/100:.2f} INR. Enter your PIN only in the secure review. No payment has been made.",
            'preview':{'kind':'payment_batch','batch_id':batch.id,'requires_confirmation':True,'total':batch.total},'data':result['items']}
