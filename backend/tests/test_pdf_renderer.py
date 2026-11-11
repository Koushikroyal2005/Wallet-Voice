from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from pypdf import PdfReader
from app.documents import pdf_document, download

def text(data):return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)

def test_unicode_rupee_hindi_and_safe_markup():
    data=pdf_document(['Payment record','Amount: ₹1,250.00','Merchant: भारतीय रेल','<script>& customer (copy)'])
    content=text(data)
    assert '₹1,250.00' in content and 'भारतीय रेल' in content
    assert '<script>& customer (copy)' in content
    assert b'/FontFile2' in data and b'/ToUnicode' in data

def test_identifiers_are_not_rewritten_as_ligatures():
    ident='3e73ccff-769d-43a4-a391-7a351996039d'
    assert ident in text(pdf_document(['Payment record',f'Journal: {ident}']))

def test_telugu_original_text_is_available_as_actual_text():
    original='తెలుగు పేరు'
    data=pdf_document(['Payment record',original])
    assert ('\ufeff'+original).encode('utf-16-be').hex().upper().encode() in data

def test_long_reference_and_unknown_glyph_are_not_silently_lost():
    data=pdf_document(['Reference: '+'abc123'*200,'Unknown: 漢'])
    content=text(data)
    assert '[U+6F22]' in content
    assert content.replace('\n','').count('abc123')==200

def test_concurrent_documents_keep_their_own_text():
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda i:pdf_document([f'Attempt-{i}','Merchant: भारतीय रेल']),range(8)))
    for i,result in enumerate(results):assert f'Attempt-{i}' in text(result)

def test_attachment_filename_is_sanitized():
    response=download(['Payment record'],'../record"\r\nInjected: header')
    header=response.headers['content-disposition']
    assert '\r' not in header and '\n' not in header and '..' not in header
    assert response.headers['cache-control']=='no-store'
    assert response.headers['x-content-type-options']=='nosniff'
