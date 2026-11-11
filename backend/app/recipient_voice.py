"""Resolve a real saved recipient and prepare a draft; financial execution stays in existing routes."""
from sqlalchemy import select
from .models import Recipient,PaymentIntent
from .agentic import create_draft,serialize_intent


def prepare_transfer(db,intent):
    if intent.tool=='review_recipient_draft':
        row=db.get(PaymentIntent,intent.args.get('payment_id'))
        if not row or row.user_id!='demo-user' or row.status not in {'DRAFT','HELD'} or row.payment_request_id:
            return {'response':'That draft is no longer awaiting approval. Check its recorded status in Payments.'}
        recipient=db.get(Recipient,row.recipient_id)
        if not recipient or recipient.user_id!='demo-user':return {'response':'The saved recipient is unavailable. Choose another recipient in Payments.'}
    else:
        amount=intent.args.get('amount');name=(intent.args.get('merchant') or '').strip().casefold()
        if type(amount) is not int or not 0<amount<=10_000_000:return {'response':'Please give one positive rupee amount within the supported wallet range.'}
        matches=[r for r in db.scalars(select(Recipient).where(Recipient.user_id=='demo-user')) if name in {r.name.strip().casefold(),r.handle.strip().casefold()}]
        if len(matches)!=1:
            return {'response':'Several saved recipients have that name. Use the full saved phone number or email to choose one.' if matches else 'I could not find that saved recipient. Add their details in Payments first. No transfer was prepared.'}
        recipient=matches[0];row=create_draft(db,amount,recipient=recipient,note=intent.args.get('note'))
    return {'response':f'Review {row.amount/100:.2f} INR to {recipient.name} ({recipient.handle}). This is a saved simulated transfer; your PIN is still required.',
            'data':serialize_intent(row),'preview':{'kind':'recipient_transfer','intent_id':row.id,'amount':row.amount,'recipient_name':recipient.name,'recipient_handle':recipient.handle,'version':row.version,'source':row.source,'requires_confirmation':True}}
