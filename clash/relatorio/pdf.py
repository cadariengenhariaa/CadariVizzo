"""Exportação PDF — relatório de emissão para reunião de
compatibilização. Usa `reportlab` (já estava instalado neste ambiente;
formalizado em requirements.txt nesta etapa)."""
import os
import tempfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from clash.relatorio.dados_relatorio import clashes_ativos, montar_resumo_executivo
from clash.relatorio.snapshot_3d import capturar_snapshot_do_clash

CORES_SEVERIDADE = {
    "Critica": colors.HexColor("#F05B5B"),
    "Alta": colors.HexColor("#E8A33D"),
    "Media": colors.HexColor("#5AA9F0"),
    "Baixa": colors.HexColor("#57C08A"),
}


def _estilos():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle("TituloRelatorio", parent=base["Title"], fontSize=20, spaceAfter=6))
    base.add(ParagraphStyle("Secao", parent=base["Heading2"], spaceBefore=14, spaceAfter=6))
    base.add(ParagraphStyle("TextoNormal", parent=base["Normal"], fontSize=9, leading=12))
    base.add(ParagraphStyle("Alerta", parent=base["Normal"], textColor=colors.HexColor("#C4362D"),
                             fontSize=10, leading=13, spaceAfter=4))
    return base


def _tabela_simples(dados, larguras=None):
    tabela = Table(dados, colWidths=larguras)
    tabela.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14171C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
    ]))
    return tabela


def _secao_resumo(story, estilos, resumo):
    story.append(Paragraph("Resumo Executivo", estilos["Secao"]))

    meta = resumo["metadados_projeto"]
    if meta:
        story.append(Paragraph("<br/>".join(f"<b>{k}:</b> {v}" for k, v in meta.items()), estilos["TextoNormal"]))
        story.append(Spacer(1, 8))

    pre = resumo["pre_checagens"]
    if pre.get("tem_alertas_bloqueantes"):
        story.append(Paragraph(
            "⚠ Atenção: foram encontrados problemas de qualidade que podem gerar interferências "
            "enganosas nesta rodada (detalhes abaixo). Revise antes de confiar cegamente nos resultados.",
            estilos["Alerta"],
        ))
    if pre.get("unidades_inconsistentes"):
        story.append(Paragraph(
            f"• Unidades inconsistentes entre arquivos: {pre.get('escala_por_arquivo')}", estilos["TextoNormal"]
        ))
    if pre.get("alerta_desalinhamento"):
        story.append(Paragraph(
            f"• Possível desalinhamento entre modelos — distância entre centros: "
            f"{pre.get('distancia_entre_centros_m'):.1f} m", estilos["TextoNormal"]
        ))
    if pre.get("guids_duplicados"):
        story.append(Paragraph(f"• {len(pre['guids_duplicados'])} GUID(s) duplicado(s)", estilos["TextoNormal"]))
    if pre.get("elementos_sem_geometria"):
        story.append(Paragraph(f"• {len(pre['elementos_sem_geometria'])} elemento(s) sem geometria",
                                estilos["TextoNormal"]))
    if pre.get("elementos_sem_nivel"):
        story.append(Paragraph(f"• {len(pre['elementos_sem_nivel'])} elemento(s) sem pavimento associado",
                                estilos["TextoNormal"]))
    if pre.get("geometria_invalida"):
        story.append(Paragraph(f"• {len(pre['geometria_invalida'])} elemento(s) com geometria inválida",
                                estilos["TextoNormal"]))
    if pre.get("niveis_sem_correspondencia"):
        story.append(Paragraph("• Nomenclatura de pavimento sem correspondência entre arquivos",
                                estilos["TextoNormal"]))
    story.append(Spacer(1, 10))

    totais = resumo["totais"]
    story.append(Paragraph(
        f"<b>{totais['total_ativo']}</b> interferência(s) ativa(s), das quais "
        f"<b>{totais['total_pendente']}</b> ainda pendente(s) de ação.", estilos["TextoNormal"]
    ))
    story.append(Spacer(1, 6))

    if totais["por_severidade"]:
        story.append(_tabela_simples(
            [["Severidade", "Quantidade"]] + list(totais["por_severidade"].items()), larguras=[8 * cm, 4 * cm]
        ))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Comparativo com a revisão anterior", estilos["Heading3"]))
    story.append(_tabela_simples(
        [["Rastreamento", "Quantidade"]] + list(resumo["comparativo_revisao_anterior"].items()),
        larguras=[8 * cm, 4 * cm],
    ))
    story.append(Spacer(1, 10))

    if resumo["matriz_disciplinas"]:
        story.append(Paragraph("Matriz disciplina x disciplina", estilos["Heading3"]))
        story.append(_tabela_simples(
            [["Par de disciplinas", "Quantidade"]] + list(resumo["matriz_disciplinas"].items()),
            larguras=[8 * cm, 4 * cm],
        ))
        story.append(Spacer(1, 10))

    if resumo["distribuicao_por_pavimento"]:
        story.append(Paragraph("Distribuição por pavimento", estilos["Heading3"]))
        story.append(_tabela_simples(
            [["Pavimento", "Quantidade"]] + list(resumo["distribuicao_por_pavimento"].items()),
            larguras=[8 * cm, 4 * cm],
        ))
        story.append(Spacer(1, 10))

    if resumo["top_elementos"]:
        story.append(Paragraph("Elementos com mais interferências", estilos["Heading3"]))
        story.append(_tabela_simples(
            [["Elemento", "Quantidade"]] + [[t["nome"], t["quantidade"]] for t in resumo["top_elementos"]],
            larguras=[10 * cm, 3 * cm],
        ))
        story.append(Spacer(1, 10))

    if resumo["pendencias_por_disciplina"]:
        story.append(Paragraph("Pendências por disciplina responsável", estilos["Heading3"]))
        story.append(_tabela_simples(
            [["Disciplina", "Pendências"]] + list(resumo["pendencias_por_disciplina"].items()),
            larguras=[8 * cm, 4 * cm],
        ))


def _secao_interferencia(story, estilos, clash, caminho_png):
    cor = CORES_SEVERIDADE.get(clash["severidade"], colors.grey)
    titulo = (f"#{clash['id'][:8]} — {clash['severidade']} — {clash['tipo'].upper()} — "
              f"{clash['disciplina_a']} x {clash['disciplina_b']}")
    estilo_titulo = ParagraphStyle("TituloClash", parent=estilos["Heading3"], textColor=cor)
    story.append(Paragraph(titulo, estilo_titulo))

    if caminho_png and os.path.exists(caminho_png):
        story.append(Image(caminho_png, width=9 * cm, height=6.75 * cm))
        story.append(Spacer(1, 4))

    linhas = [
        ["Status", clash["status"]],
        ["Pavimento", clash.get("nivel") or "—"],
        ["Responsável sugerido", clash["responsavel_sugerido"]],
        ["Elemento A", f"{clash['elemento_a']['ifc_class']} \"{clash['elemento_a']['nome']}\" "
                       f"({clash['elemento_a']['guid']})"],
        ["Elemento B", f"{clash['elemento_b']['ifc_class']} \"{clash['elemento_b']['nome']}\" "
                       f"({clash['elemento_b']['guid']})"],
    ]
    if clash.get("penetracao_m") is not None:
        linhas.append(["Penetração", f"{clash['penetracao_m']:.3f} m"])
    if clash.get("volume_intersecao_m3") is not None:
        linhas.append(["Volume de interseção", f"{clash['volume_intersecao_m3']:.4f} m³"])
    if clash.get("distancia_m") is not None and clash.get("folga_exigida_m") is not None:
        linhas.append(["Distância x folga exigida",
                        f"{clash['distancia_m']:.3f} m x {clash['folga_exigida_m']:.3f} m"])
    if clash.get("comentario"):
        linhas.append(["Comentário", clash["comentario"]])
    if clash.get("prazo"):
        linhas.append(["Prazo", clash["prazo"]])

    story.append(_tabela_simples(linhas, larguras=[4 * cm, 12 * cm]))
    story.append(Paragraph(
        "<i>Sugestão automática — avaliar com a equipe, não é uma decisão de projeto.</i>", estilos["TextoNormal"]
    ))
    story.append(Spacer(1, 16))


def exportar_pdf(clashes, caminho_pdf, resultado_pre_checagens=None, metadados_projeto=None,
                  arquivos_ifc=None, escala_por_arquivo=None, settings=None, incluir_snapshots=True):
    estilos = _estilos()
    resumo = montar_resumo_executivo(clashes, resultado_pre_checagens, metadados_projeto)

    doc = SimpleDocTemplate(caminho_pdf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    story = [Paragraph("Relatório de Interferências (Clash Detection)", estilos["TituloRelatorio"])]

    _secao_resumo(story, estilos, resumo)
    story.append(PageBreak())

    ativos = clashes_ativos(clashes)
    with tempfile.TemporaryDirectory() as tmp:
        for i, clash in enumerate(ativos):
            caminho_png = None
            if incluir_snapshots and arquivos_ifc and escala_por_arquivo:
                candidato = os.path.join(tmp, f"snap_{i}.png")
                if capturar_snapshot_do_clash(clash, arquivos_ifc, escala_por_arquivo, candidato,
                                               settings=settings):
                    caminho_png = candidato
            _secao_interferencia(story, estilos, clash, caminho_png)

        doc.build(story)

    return caminho_pdf
