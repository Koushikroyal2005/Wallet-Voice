"""Owner-only untrusted PDF uploads, served as attachments, never payment evidence."""
import hashlib
from fastapi import APIRouter,Depends,UploadFile,File,Form,HTTPException,Response
from sqlalchemy import select
from .db import get_db
from .models import DocumentRecord,PaymentRequest
router=APIRouter(prefix='/api/product/uploads')
MAX_BYTES=2*1024*1024

def view(r):
    return {'id':r.id,'title':r.title,'payment_request_id':r.payment_request_id,'created_at':r.created_at,
            'size':len(r.content),'digest':r.digest,'trust':'USER_UPLOADED_UNVERIFIED','payment_proof':False,
            'download_url':f'/api/product/uploads/{r.id}/download'}

@router.get('')
def listing(q:str='',db=Depends(get_db)):
    if len(q)>120:raise HTTPException(422,'Search is too long')
    rows=db.scalars(select(DocumentRecord).where(DocumentRecord.user_id=='demo-user').order_by(DocumentRecord.created_at.desc()))
    return [view(r) for r in rows if q.casefold() in r.title.casefold()]

@router.post('')
async def upload(file:UploadFile=File(...),title:str=Form(...,min_length=1,max_length=120),payment_request_id:str|None=Form(None),db=Depends(get_db)):
    try:content=await file.read(MAX_BYTES+1)
    finally:await file.close()
    if len(content)>MAX_BYTES:raise HTTPException(413,'Choose a PDF no larger than 2 MiB')
    if file.content_type!='application/pdf' or not content.startswith(b'%PDF-') or b'%%EOF' not in content[-1024:]:raise HTTPException(422,'Only a PDF with a valid header and end marker is accepted')
    if not title.strip():raise HTTPException(422,'Enter a document title')
    if payment_request_id and not db.get(PaymentRequest,payment_request_id):raise HTTPException(404,'Payment not found')
    digest=hashlib.sha256(content).hexdigest()
    old=db.scalar(select(DocumentRecord).where(DocumentRecord.user_id=='demo-user',DocumentRecord.digest==digest,DocumentRecord.title==title.strip(),DocumentRecord.payment_request_id==payment_request_id))
    if old:return view(old)
    row=DocumentRecord(title=title.strip(),payment_request_id=payment_request_id,content=content,digest=digest);db.add(row);db.commit();return view(row)

@router.get('/{ident}/download')
def download(ident:str,db=Depends(get_db)):
    row=db.scalar(select(DocumentRecord).where(DocumentRecord.id==ident,DocumentRecord.user_id=='demo-user'))
    if not row:raise HTTPException(404,'Document not found')
    return Response(row.content,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="unverified-upload.pdf"','Content-Security-Policy':"sandbox; default-src 'none'",'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
