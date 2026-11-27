"""Render the exact report payload returned by the preview endpoint."""
from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape
from datetime import date


def xlsx(report):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb=Workbook(); summary=wb.active;summary.title='Summary'
    def cell_value(value):
        return float(value) if isinstance(value,Decimal) else value
    def append(ws, values):
        ws.append([cell_value(v) for v in values])
        for c in ws[ws.max_row]:
            # Treat all user-controlled text as text, never formulas.
            if isinstance(c.value,str): c.data_type='s'
            if isinstance(c.value,(float,int)):c.number_format='#,##0.##'
            if isinstance(c.value,date):c.number_format='dd-mmm-yyyy'
    def header(ws, row):
        for c in ws[row]:c.fill=PatternFill('solid',fgColor='273B56');c.font=Font(color='FFFFFF',bold=True);c.alignment=Alignment(wrap_text=True,vertical='center')
        ws.row_dimensions[row].height=30
    append(summary,['DA SVARN | '+report['title']]);summary['A1'].font=Font(bold=True,size=15,color='273B56')
    for label,value in [('From',report['date_from']),('To',report['date_to']),('Generated (UTC)',report['generated_at']),*report['filters'].items()]:append(summary,[label,value])
    append(summary,['Metric','Quantity']);header(summary,summary.max_row)
    for m in report['metrics']:append(summary,[m['label'],m['value']])
    for n in report['notes']:append(summary,['Note',n]);summary.cell(summary.max_row,2).alignment=Alignment(wrap_text=True);summary.row_dimensions[summary.max_row].height=42
    summary.column_dimensions['A'].width=46;summary.column_dimensions['B'].width=78
    for idx,s in enumerate(report['sections'],1):
        ws=wb.create_sheet(f'{idx:02d} {s["title"][:27]}');append(ws,s['columns']);header(ws,1)
        for r in s['rows']:append(ws,r)
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        for i,col in enumerate(ws.columns,1):
            ws.column_dimensions[get_column_letter(i)].width=min(48,max(13,max(len(str(c.value or '')) for c in col)+2))
    buf=BytesIO();wb.save(buf);return buf.getvalue()


def pdf(report):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, KeepTogether
    from reportlab.graphics.shapes import Drawing, Rect, String
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=30,rightMargin=30,topMargin=36,bottomMargin=35)
    styles=getSampleStyleSheet(); body=ParagraphStyle('cell',parent=styles['Normal'],fontSize=7.7,leading=10,wordWrap='CJK');head=ParagraphStyle('head',parent=body,textColor=colors.white,fontName='Helvetica-Bold')
    def fmt(v):
        if v is None:return '-'
        if isinstance(v,Decimal):return f'{v:,.2f}'.rstrip('0').rstrip('.')
        if isinstance(v,date):return v.isoformat()
        return str(v)
    def para(v,style=body):return Paragraph(escape(fmt(v)),style)
    story=[Paragraph('DA SVARN',styles['Title']),Paragraph(escape(report['title']),styles['Heading1']),para(f"Period: {report['date_from']} to {report['date_to']} | Generated (UTC): {report['generated_at']}"),para(' | '.join(f'{k}: {v}' for k,v in report['filters'].items())),Spacer(1,10)]
    def table(columns,rows):
        data=[[para(c,head) for c in columns]]+[[para(v) for v in r] for r in rows]
        t=LongTable(data,colWidths=[doc.width/len(columns)]*len(columns),repeatRows=1,splitByRow=1,splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#273B56')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F1F5F9')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.grey),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        return t
    def bars(title, pairs):
        if not pairs: return
        height = 35 + 22*len(pairs)
        drawing = Drawing(doc.width, height)
        drawing.add(String(0, height-12, title, fontName='Helvetica-Bold', fontSize=10, fillColor=colors.HexColor('#273B56')))
        maximum = max((float(value) for _, value in pairs), default=0) or 1
        for i,(label,value) in enumerate(pairs):
            y=height-34-i*22
            drawing.add(String(0,y+3,label,fontSize=8,fillColor=colors.HexColor('#334155')))
            drawing.add(Rect(185,y,doc.width-265,11,fillColor=colors.HexColor('#E2E8F0'),strokeColor=None))
            if value > 0: drawing.add(Rect(185,y,(doc.width-265)*float(value)/maximum,11,fillColor=colors.HexColor('#486581'),strokeColor=None))
            drawing.add(String(doc.width-72,y+2,fmt(value),fontSize=8,fillColor=colors.HexColor('#334155')))
        story.extend([drawing, Spacer(1,8)])
    metric_map={m['label']:m['value'] for m in report['metrics']}
    if 'Gross sales' in metric_map:
        bars('Sales reconciliation (invoice period)',[(label,metric_map[label]) for label in ('Gross sales','Linked rejected quantity','Net sales')])
    if 'Purchase planned' in metric_map:
        bars('Selected purchase plans: quantities reconciled to date',[(label,metric_map[label]) for label in ('Purchase planned','Received on selected plans','Cancelled on selected plans','Outstanding purchase')])
    if report['metrics']:story.extend([table(['Metric','Quantity'],[[m['label'],m['value']] for m in report['metrics']]),Spacer(1,8)])
    for n in report['notes']:story.extend([para(n),Spacer(1,4)])
    for s in report['sections']:
        story.extend([Spacer(1,10),Paragraph(escape(s['title']),styles['Heading2'])])
        story.append(table(s['columns'],s['rows']) if s['rows'] else para('No matching records.'))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.drawString(30,18,'DA SVARN | Inventory Management System');canvas.drawRightString(doc.pagesize[0]-30,18,f'Page {doc.page}')
    doc.build(story,onFirstPage=footer,onLaterPages=footer);return buf.getvalue()
