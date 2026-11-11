"""Small text-PDF renderer: no browser, remote fetch, or payment mutation."""
import textwrap
from fastapi import APIRouter,Depends,HTTPException,Response
from .db import get_db
from .services import FinancialError

router=APIRouter(prefix='/api/product/documents')

def pdf_document(lines):
    # Built-in Helvetica is WinAnsi. Currency codes, not unsupported symbols.
    wrapped=[part for line in lines for part in (textwrap.wrap(str(line),88) or [''])]
    pages=[wrapped[i:i+46] for i in range(0,len(wrapped),46)] or [[]]
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>']
    ids=[]
    for page in pages:
        page_id=len(objects)+1;stream_id=page_id+1;ids.append(page_id)
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>'.encode())
        content='BT /F1 11 Tf 48 790 Td 16 TL\n'
        for line in page:
            escaped=line.replace('\\','\\\\').replace('(','\\(').replace(')','\\)').replace('\r',' ').replace('\n',' ')
            content+=f'({escaped}) Tj T*\n'
        raw=(content+'ET').encode('cp1252',errors='replace')
        objects.append(f'<< /Length {len(raw)} >>\nstream\n'.encode()+raw+b'\nendstream')
    objects[1]=f"<< /Type /Pages /Count {len(ids)} /Kids [{' '.join(f'{i} 0 R' for i in ids)}] >>".encode()
    result=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(result));result.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start=len(result);result.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:result.extend(f'{offset:010d} 00000 n \n'.encode())
    result.extend(f'trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode())
    return bytes(result)

def download(lines,name):
    return Response(pdf_document(lines),media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{name}.pdf"','Cache-Control':'no-store'})

@router.get('/payments/{ident}.pdf')
def receipt(ident:str,db=Depends(get_db)):
    from .main import payment_review
    data=payment_review(ident,db);r=data['receipt']
    if not r:raise HTTPException(409,'No recorded payment attempt; a preview is not a receipt')
    return download(['Wallet-Voice | Payment record (not a merchant tax invoice)',
        'SIMULATED WALLET' if r['funding_source']=='AI_WALLET' else 'PAYPAL SANDBOX',
        f"Payment: {r['payment_id']}",f"Merchant/recipient: {r['merchant']}",
        f"Amount: {r['currency']} {r['amount']/100:.2f}",f"Actual recorded status: {r['status']}",
        f"Source: {r['funding_source']}",f"{r['timestamp_label']}: {r['timestamp']}",
        f"Attempt: {r['attempt_id']}",f"Journal: {r['journal_id'] or 'Not posted'}",
        f"PayPal order: {r['order_id'] or 'Not applicable'}",f"PayPal capture: {r['capture_id'] or 'Not recorded'}",
        f"Provider reference: {r['provider_reference'] or 'Not recorded'}",
        'Pending/failed records are not proof of successful payment.'], 'wallet-voice-payment')

@router.get('/batches/{ident}.pdf')
def statement(ident:str,db=Depends(get_db)):
    from .payment_batches import get_batch,view
    try:
        row=get_batch(db,ident);data=view(db,row)
    except FinancialError as e:raise HTTPException(404,str(e))
    lines=['Wallet-Voice | Batch statement | SIMULATED WALLET',f"Batch: {data['id']}",f"Created: {row.created_at}",f"Status: {data['status']}",f"Items: {len(data['items'])}"]
    totals={}
    for item in data['items']:
        key=(item['currency'],item['status']);totals[key]=totals.get(key,0)+item['amount']
        lines.extend(['',f"{item['merchant']} | {item['currency']} {item['amount']/100:.2f} | {item['status']}",f"Request: {item['id']}",f"Attempt: {item['attempt_id'] or 'Not submitted'}",f"Journal: {(item['receipt'] or {}).get('journal_id','Not posted')}"])
    lines.extend(['','Currency-aware recorded totals:']+[f'{currency} {amount/100:.2f} | {state}' for (currency,state),amount in totals.items()])
    lines.append('Review, pending, failed and cancelled items are not settled payments. Not a merchant invoice.')
    db.rollback();return download(lines,'wallet-voice-batch')
