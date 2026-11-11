"""Small text-PDF renderer: no browser, remote fetch, or payment mutation."""
from .pdf_renderer import render_pdf
import re
from fastapi import APIRouter,Depends,HTTPException,Response
from .db import get_db
from .services import FinancialError
from sqlalchemy import select
from .models import PaymentAttempt, PaymentRequest, PaymentReservation, PayPalOrder, Operation, JournalTransaction, Wallet, PayPalWebhookEvent

router=APIRouter(prefix='/api/product/documents')

def pdf_document(lines,table=None):
    return render_pdf(lines,table)

def download(lines,name,table=None):
    safe_name=re.sub(r'[^A-Za-z0-9_-]','_',str(name))[:120] or 'wallet-voice-record'
    return Response(pdf_document(lines,table),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{safe_name}.pdf"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

def attempt_record(db, ident):
    """Resolve evidence by attempt, never by the request's latest attempt."""
    a=db.get(PaymentAttempt,ident)
    if not a:raise HTTPException(404,'Payment attempt not found')
    p=db.get(PaymentRequest,a.payment_request_id)
    if not p:raise HTTPException(404,'Payment request not found')
    order=db.scalar(select(PayPalOrder).where(PayPalOrder.payment_attempt_id==a.id))
    if order and order.user_id!='demo-user':raise HTTPException(404,'Payment attempt not found')
    reservation=db.get(PaymentReservation,a.reservation_id) if a.reservation_id else None
    owner=db.get(Wallet,reservation.wallet_id) if reservation else None
    if owner and owner.user_id!='demo-user':raise HTTPException(404,'Payment attempt not found')
    # A request-level journal belongs only to its consumed, successful reservation.
    op=db.scalar(select(Operation).where(Operation.idempotency_key==f'payment:{p.id}')) if reservation and reservation.status=='CONSUMED' and a.status=='SUCCEEDED' else None
    journal=db.scalar(select(JournalTransaction).where(JournalTransaction.operation_id==op.id)) if op else None
    refunds=[]
    if order and order.provider_status=='REFUNDED':
        for event in db.scalars(select(PayPalWebhookEvent).where(PayPalWebhookEvent.verified.is_(True),PayPalWebhookEvent.event_type=='PAYMENT.CAPTURE.REFUNDED')):
            resource=(event.payload or {}).get('resource') or {}
            related=resource.get('supplementary_data',{}).get('related_ids',{})
            if event.paypal_order_id==order.paypal_order_id or (order.paypal_capture_id and related.get('capture_id')==order.paypal_capture_id):
                refunds.append({'reference':resource.get('id'),'recorded_at':event.created_at,'provider_timestamp':resource.get('create_time'),'amount':(resource.get('amount') or {}).get('value'),'currency':(resource.get('amount') or {}).get('currency_code')})
    return {'attempt_id':a.id,'payment_id':p.id,'merchant':p.merchant,'refunds':refunds,
        'amount':order.original_amount if order else reservation.amount if reservation else p.amount,
        'currency':order.original_currency if order else reservation.currency if reservation else p.currency,
        'status':a.status,'created_at':a.created_at,'funding_source':'PAYPAL_SANDBOX' if order else 'AI_WALLET' if reservation else 'UNRESOLVED',
        'provider_reference':a.provider_reference,'journal_id':journal.id if journal else None,
        'reservation_id':reservation.id if reservation else None,'order_id':order.paypal_order_id if order else None,
        'capture_id':order.paypal_capture_id if order else None,'provider_status':order.provider_status if order else None,
        'captured_at':order.captured_at if order else None}

@router.get('/attempts/{ident}.pdf')
def attempt_receipt(ident:str,db=Depends(get_db)):
    r=attempt_record(db,ident)
    lines=['Wallet-Voice | Payment Record',f"Actual recorded status: {r['status']}",
        'SIMULATED WALLET' if r['funding_source']=='AI_WALLET' else 'PAYPAL SANDBOX' if r['funding_source']=='PAYPAL_SANDBOX' else 'Funding evidence unavailable',
        f"Amount: {r['currency']} {r['amount']/100:.2f}",f"Merchant/recipient: {r['merchant']}",
        f"Payment: {r['payment_id']}",f"Attempt: {r['attempt_id']}",f"Recorded: {r['created_at']}",
        f"Source: {r['funding_source']}"]
    lines += [f"{label}: {r[key] or 'Not recorded'}" for label,key in [('Reservation','reservation_id'),('Journal','journal_id'),('Provider reference','provider_reference'),('PayPal order','order_id'),('PayPal capture','capture_id'),('Current provider state','provider_status'),('Capture recorded','captured_at')]]
    lines += ['Pending/failed records are not proof of successful payment.',
        'Current refund state does not erase the original capture evidence.',
        'This record reflects recorded transaction status. It is not a merchant tax invoice.']
    for refund in r['refunds']:
        lines += [f"Refund reference: {refund['reference'] or 'Not recorded'}",f"Refund recorded: {refund['recorded_at']}",f"Provider refund amount: {refund['currency'] or ''} {refund['amount'] or 'Not recorded'}"]
    return download(lines,f'wallet-voice-payment-{r["attempt_id"]}')

@router.get('/payments/{ident}.pdf')
def receipt(ident:str,db=Depends(get_db)):
    """Compatibility view: explicitly resolves the latest recorded attempt."""
    latest=db.scalar(select(PaymentAttempt).where(PaymentAttempt.payment_request_id==ident).order_by(PaymentAttempt.created_at.desc(),PaymentAttempt.id.desc()))
    if not latest:raise HTTPException(409,'No recorded payment attempt; a preview is not a receipt')
    return attempt_receipt(latest.id,db)

@router.get('/attempts/{ident}')
def attempt_details(ident:str,db=Depends(get_db)):
    return attempt_record(db,ident)

@router.get('/batches/{ident}.pdf')
def statement(ident:str,db=Depends(get_db)):
    from .payment_batches import get_batch,view
    try:
        row=get_batch(db,ident);data=view(db,row)
    except FinancialError as e:raise HTTPException(404,str(e))
    lines=['Wallet-Voice | Batch statement | SIMULATED WALLET',f"Batch: {data['id']}",f"Created: {row.created_at}",f"Status: {data['status']}",f"Items: {len(data['items'])}"]
    totals={};table=[['Merchant','Amount','Currency','Status','Recorded references']]
    for item in data['items']:
        key=(item['currency'],item['status']);totals[key]=totals.get(key,0)+item['amount']
        table.append([item['merchant'],f"{item['amount']/100:.2f}",item['currency'],item['status'],f"Request: {item['id']} | Attempt: {item['attempt_id'] or 'Not submitted'} | Journal: {(item['receipt'] or {}).get('journal_id','Not posted')}"])
    lines.extend(['','Currency-aware recorded totals:']+[f'{currency} {amount/100:.2f} | {state}' for (currency,state),amount in totals.items()])
    lines.append('Review, pending, failed and cancelled items are not settled payments. Not a merchant invoice.')
    db.rollback();return download(lines,f'wallet-voice-batch-{row.id}',table)
