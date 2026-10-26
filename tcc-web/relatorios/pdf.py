from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import CondPageBreak, LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


def gerar_pdf(relatorio):
    # Fontes distribuídas com o ReportLab, incorporadas ao PDF para manter
    # acentos e medidas consistentes no Windows e nos leitores de PDF.
    pasta_fontes = Path(reportlab.__file__).parent / "fonts"
    if "RelatoriosSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("RelatoriosSans", str(pasta_fontes / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("RelatoriosSans-Bold", str(pasta_fontes / "VeraBd.ttf")))
        pdfmetrics.registerFontFamily("RelatoriosSans", normal="RelatoriosSans", bold="RelatoriosSans-Bold")
    saida = BytesIO()
    largura, altura = landscape(A4)
    doc = SimpleDocTemplate(saida, pagesize=(largura, altura),
                            leftMargin=34, rightMargin=34, topMargin=46, bottomMargin=38,
                            title="UNICAP - Relatórios de transporte", author="UNICAP")
    estilos = getSampleStyleSheet()
    estilos.add(ParagraphStyle("Celula", fontName="RelatoriosSans", fontSize=7.5, leading=10, spaceAfter=0))
    estilos.add(ParagraphStyle("CabecalhoTabela", parent=estilos["Celula"], textColor=colors.white))
    estilos.add(ParagraphStyle("Nota", fontName="RelatoriosSans", fontSize=8, leading=11, spaceAfter=8, textColor=colors.HexColor("#526176")))
    estilos["Heading1"].fontName = "RelatoriosSans-Bold"
    estilos["Heading2"].fontName = "RelatoriosSans-Bold"
    estilos["Heading1"].textColor = colors.HexColor("#142c4d")
    estilos["Heading2"].fontSize = 12
    estilos["Heading2"].spaceBefore = 10
    estilos["Heading2"].keepWithNext = True
    elementos = []

    def par(valor, estilo="Celula"):
        texto = str(valor if valor is not None else "-")
        return Paragraph(escape(texto).replace("\n", "<br/>"), estilos[estilo])

    def tabela(cabecalho, linhas, pesos):
        dados = [[par(c, "CabecalhoTabela") for c in cabecalho]]
        for linha in linhas:
            dados.append([par(c) for c in linha])
        if len(dados) == 1:
            elementos.append(par("Nenhum registro encontrado.", "Nota"))
            return
        total = sum(pesos)
        t = LongTable(dados, colWidths=[doc.width*p/total for p in pesos], repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#142c4d")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f4f8")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#ad4700")),
        ]))
        elementos.extend([t, Spacer(1, 8)])

    def data(valor):
        return timezone.localtime(valor, relatorio.fuso).strftime("%d/%m/%Y %H:%M")

    gerado = data(timezone.now())

    def pagina(canvas, document):
        canvas.saveState()
        canvas.setFont("RelatoriosSans-Bold", 9)
        canvas.setFillColor(colors.HexColor("#142c4d"))
        canvas.drawString(34, altura-27, "UNICAP | Transporte universitário")
        canvas.setFont("RelatoriosSans", 8)
        canvas.drawRightString(largura-34, 21, f"Página {document.page}")
        canvas.drawString(34, 21, f"Gerado em {gerado} | {relatorio.fuso.key}")
        canvas.restoreState()

    elementos.append(par("Relatório de utilização do transporte", "Heading1"))
    for filtro in relatorio.filtros_legiveis:
        elementos.append(par(filtro, "Nota"))
    r = relatorio.resumo
    tabela(["Embarques", "Associados distintos", "Viagens com embarque", "Ônibus utilizados"],
           [[r["embarques"], r["associados"], r["viagens_com_embarque"], r["onibus_utilizados"]]], [1, 1, 1, 1])

    elementos.extend([CondPageBreak(100), par("Frequência por associado", "Heading2")])
    elementos.append(par("Nome e RUA do último embarque no período. Dias de uso contam cada data uma única vez. Ausência de registro não determina falta.", "Nota"))
    tabela(["Associado", "RUA", "Embarques", "Dias de uso", "Primeira presença", "Última presença"],
           ([f["nome"] + "\n" + (f["instituicao"] or "Instituição não informada"), f["rua"], f["embarques"], f["dias"], data(f["primeira_presenca"]), data(f["ultima_presenca"])] for f in relatorio.frequencia),
           [3, 1.3, 1, 1, 1.8, 1.8])

    elementos.extend([CondPageBreak(100), par("Ocupação e vagas por viagem", "Heading2")])
    elementos.append(par("Viagens iniciadas no período ou com embarques no período. A ocupação usa todos os passageiros da viagem, inclusive ao filtrar associado ou ponto. Capacidade histórica ausente não é estimada.", "Nota"))
    tabela(["Viagem / início", "Rota / ônibus", "Sentido / status", "Presentes", "Capacidade", "Vagas", "Ocupação"],
           ([f"#{v['id']}\n{data(v['inicio'])}", f"{v['rota']}\n{v['onibus']} / {v['placa']}", f"{v['sentido']}\n{v['status']}",
             v["presentes"], v["capacidade"] or "Não registrada", v["vagas"],
             f"{v['ocupacao']:.1f}%" if v["ocupacao"] is not None else "-"] for v in relatorio.preparar_viagens(relatorio.viagens)),
           [1.7, 3.2, 1.5, .9, 1.2, .8, 1])

    elementos.extend([CondPageBreak(100), par("Embarques por dia", "Heading2")])
    tabela(["Data", "Embarques"], ([p["dia"].strftime("%d/%m/%Y"), p["total"]] for p in relatorio.por_dia), [1, 1])

    elementos.extend([CondPageBreak(100), par("Registros de embarque", "Heading2")])
    tabela(["Data / hora", "Associado / RUA", "Ônibus / placa", "Viagem / rota", "Sentido", "Ponto informado"],
           ([data(c.ocorrido_em), f"{c.nome_associado}\n{c.rua_associado}", f"{c.codigo_onibus}\n{c.placa_onibus}",
             f"#{c.viagem_id}\n{c.viagem.nome_rota_historico}", c.get_sentido_display(), c.ponto_informado] for c in relatorio.registros),
           [1.4, 2.5, 1.4, 2, 1, 1.8])
    doc.build(elementos, onFirstPage=pagina, onLaterPages=pagina)
    return saida.getvalue()
