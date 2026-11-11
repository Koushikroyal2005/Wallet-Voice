"""Offline Unicode records with embedded OFL fonts and measured wrapping."""
from io import BytesIO
from pathlib import Path
from threading import RLock
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

FONT_DIR = Path(__file__).parent / 'assets' / 'fonts'
FONTS = {'WalletSans':'NotoSans-Regular.ttf', 'WalletHindi':'NotoSansDevanagari-Regular.ttf', 'WalletTelugu':'NotoSansTelugu-Regular.ttf'}
RENDER_LOCK = RLock()

class RecordedParagraph(Paragraph):
    """Keep original Unicode available to PDF accessibility/text consumers."""
    def draw(self):
        value=self.getPlainText()
        actual=('\ufeff'+value).encode('utf-16-be').hex().upper()
        self.canv.addLiteral(f'/Span << /ActualText <{actual}> >> BDC')
        try:super().draw()
        finally:self.canv.addLiteral('EMC')

def unicode_markup(text):
    fragments=[]; current=None; run=''
    for char in str(text):
        code=ord(char)
        preferred='WalletHindi' if 0x900<=code<=0x97f else 'WalletTelugu' if 0xc00<=code<=0xc7f else 'WalletSans'
        name=next((n for n in [preferred,*FONTS] if code in pdfmetrics.getFont(n).face.charWidths),None)
        # Unsupported scripts remain explicit rather than silently becoming '?'.
        if name is None:char=f'[U+{code:04X}]';name='WalletSans'
        if char.isspace() and current:name=current
        if current and name!=current:
            fragments.append(f'<font name="{current}">{escape(run)}</font>');run=''
        current=name;run+=char
    if run:fragments.append(f'<font name="{current}">{escape(run)}</font>')
    return ''.join(fragments)

def render_pdf(lines, table=None):
    # ReportLab's registered subset fonts are shared; serialize document creation.
    with RENDER_LOCK:
        for name,file in FONTS.items():
            if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(FONT_DIR/file),shapable=name!='WalletSans'))
        output=BytesIO()
        body=ParagraphStyle('Record',fontName='WalletSans',fontSize=10,leading=16,textColor=colors.HexColor('#202945'),spaceAfter=8,splitLongWords=True,shaping=True)
        title=ParagraphStyle('Title',parent=body,fontSize=18,leading=24,spaceAfter=18)
        amount=ParagraphStyle('Amount',parent=body,fontSize=22,leading=30,spaceBefore=8,spaceAfter=16)
        def frame(canvas,doc):
            canvas.saveState();canvas.setFillColor(colors.HexColor('#192038'));canvas.rect(0,774,595.28,68,fill=1,stroke=0)
            canvas.setFillColor(colors.white);canvas.setFont('WalletSans',16);canvas.drawString(44,802,'Wallet-Voice')
            canvas.setStrokeColor(colors.HexColor('#E5E8F1'));canvas.line(44,64,551,64)
            canvas.setFillColor(colors.HexColor('#66718B'));canvas.setFont('WalletSans',8)
            canvas.drawString(44,48,'Recorded evidence - not a merchant tax invoice');canvas.drawRightString(551,48,f'Page {doc.page}');canvas.restoreState()
        document=SimpleDocTemplate(output,pagesize=(595.28,841.89),leftMargin=44,rightMargin=44,topMargin=88,bottomMargin=86,pageCompression=0,title='Wallet-Voice payment record',author='Wallet-Voice')
        story=[]
        for index,line in enumerate(lines):
            text=str(line).replace('\r',' ').replace('\n',' ')
            if not text:story.append(Spacer(1,8));continue
            story.append(RecordedParagraph(unicode_markup(text),title if index==0 else amount if text.startswith('Amount: ') else body))
        if table:
            cell=ParagraphStyle('Cell',parent=body,fontSize=8,leading=12,spaceAfter=0)
            rows=[[RecordedParagraph(unicode_markup(value),cell) for value in row] for row in table]
            grid=LongTable(rows,colWidths=[110,65,60,75,195],repeatRows=1,splitInRow=1,hAlign='LEFT')
            grid.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EEF0FF')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),10),('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#E5E8F1'))]))
            story.extend([Spacer(1,12),grid])
        document.build(story or [Paragraph('No recorded details.',body)],onFirstPage=frame,onLaterPages=frame)
        return output.getvalue()
