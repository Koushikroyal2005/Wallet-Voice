"""Synthetic visual QA only. Requires the existing local PyMuPDF renderer."""
from pathlib import Path
import pymupdf as fitz
from app.documents import pdf_document

def main():
    output=Path(__file__).resolve().parents[2]/'artifacts'/'final-completion'/'pdf'
    output.mkdir(parents=True,exist_ok=True)
    samples={
        'unicode-payment':pdf_document(['Payment Record','Actual recorded status: SUCCEEDED','SIMULATED WALLET','Amount: ₹1,250.00','Merchant: भारतीय रेल','Recipient: తెలుగు పేరు','Attempt: sample-only-123','Journal: sample-journal-456','This is synthetic layout evidence, not a real payment.']),
        'batch-statement':pdf_document(['Batch Payment Statement','Status: PARTIAL','Successfully recorded: INR 1250.00','Pending: INR 600.00','Failed: USD 20.00','Currencies are not combined. Synthetic layout example, not real settlement.'],[['Merchant','Amount','Currency','Status','Recorded references']]+[[f'भारतीय रेल / తెలుగు పేరు {i}', '1250.00','INR',['SUCCEEDED','PROCESSING','FAILED'][i%3],f'Attempt: sample-{i} | Journal: '+('example-journal' if i%3==0 else 'Not posted')] for i in range(30)])
    }
    for name,data in samples.items():
        (output/f'{name}.pdf').write_bytes(data)
        document=fitz.open(stream=data,filetype='pdf')
        for index,page in enumerate(document):
            page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(output/f'{name}-{index+1}.png')
            for word in page.get_text('words'):
                assert 30<=word[0]<=565 and 0<=word[1]<=820 and word[2]<=566 and word[3]<=830,(name,index,word)
        print(f'{name}: {len(document)} pages, rendered with bounds checks')
if __name__=='__main__':main()
