from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape
from django.db.models import Sum
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, CondPageBreak

def gerar_despesas_pdf(despesas,filtros):
    out = BytesIO();styles = getSampleStyleSheet()
    def p(text): return Paragraph(escape(str(text)),styles['BodyText'])
    def tabela(rows,widths):
        t=Table([[p(v) for v in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0f7')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),9),
            ('TOPPADDING',(0,0),(-1,-1),9),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dce3ed'))]))
        return t
    total = despesas.filter(cancelada=False).aggregate(s=Sum('valor'))['s'] or Decimal('0.00')
    story=[Paragraph('UNICAP — Despesas',styles['Title']),
        p(f"Período: {filtros['inicio']:%d/%m/%Y} a {filtros['fim']:%d/%m/%Y}"),
        p(f"Total de despesas válidas: R$ {total:,.2f}"),
        p('Os valores cancelados não compõem o total.'),Spacer(1,16)]
    rows=[['Data / ônibus','Categoria / descrição','Valor (R$)','Situação']]
    for d in despesas:
        rows.append([f'{d.data:%d/%m/%Y} / {d.onibus.codigo}',f'{d.get_categoria_display()} — {d.descricao}',
            f'{d.valor:.2f}',f'Cancelada: {d.motivo_cancelamento}' if d.cancelada else 'Válida'])
    if len(rows)==1: rows.append(['Sem despesas no período.','','',''])
    story += [tabela(rows,[100,210,70,130])]
    def rodape(c,doc):
        c.setFont('Helvetica',8);c.drawString(42,24,'UNICAP — Uso administrativo');c.drawRightString(553,24,f'Página {doc.page}')
    SimpleDocTemplate(out,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=42).build(story,onFirstPage=rodape,onLaterPages=rodape)
    return out.getvalue()
