"""Exportação XLSX: lista completa filtrável, uma linha por
interferência — reaproveita `openpyxl`, já dependência do projeto
(usado em app.py para ler o cadastro de obras)."""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from clash.relatorio.dados_relatorio import montar_resumo_executivo

COLUNAS = [
    ("ID", lambda c: c["id"]),
    ("Status", lambda c: c["status"]),
    ("Rastreamento", lambda c: c.get("rastreamento", "")),
    ("Severidade", lambda c: c["severidade"]),
    ("Tipo", lambda c: c["tipo"]),
    ("Disciplina A", lambda c: c["disciplina_a"]),
    ("Disciplina B", lambda c: c["disciplina_b"]),
    ("Responsável Sugerido", lambda c: c["responsavel_sugerido"]),
    ("Responsável Atribuído", lambda c: c.get("responsavel_atribuido", "")),
    ("Pavimento", lambda c: c.get("nivel", "")),
    ("Elemento A — Classe", lambda c: c["elemento_a"]["ifc_class"]),
    ("Elemento A — Nome", lambda c: c["elemento_a"]["nome"]),
    ("Elemento A — GUID", lambda c: c["elemento_a"]["guid"]),
    ("Elemento A — Arquivo", lambda c: c["elemento_a"]["arquivo"]),
    ("Elemento B — Classe", lambda c: c["elemento_b"]["ifc_class"]),
    ("Elemento B — Nome", lambda c: c["elemento_b"]["nome"]),
    ("Elemento B — GUID", lambda c: c["elemento_b"]["guid"]),
    ("Elemento B — Arquivo", lambda c: c["elemento_b"]["arquivo"]),
    ("Distância (m)", lambda c: c.get("distancia_m")),
    ("Penetração (m)", lambda c: c.get("penetracao_m")),
    ("Folga Exigida (m)", lambda c: c.get("folga_exigida_m")),
    ("Volume Interseção (m³)", lambda c: c.get("volume_intersecao_m3")),
    ("Comentário", lambda c: c.get("comentario", "")),
    ("Prazo", lambda c: c.get("prazo", "")),
]

# mesma paleta de CORES_STATUS/severidade usada no resto do app (config.py)
CORES_SEVERIDADE = {
    "Critica": "F05B5B",
    "Alta": "E8A33D",
    "Media": "5AA9F0",
    "Baixa": "57C08A",
}


def exportar_xlsx(clashes, caminho, resultado_pre_checagens=None, metadados_projeto=None):
    wb = Workbook()
    _montar_aba_interferencias(wb, clashes)
    _montar_aba_resumo(wb, clashes, resultado_pre_checagens, metadados_projeto)
    wb.save(caminho)
    return caminho


def _montar_aba_interferencias(wb, clashes):
    aba = wb.active
    aba.title = "Interferências"
    aba.append([titulo for titulo, _ in COLUNAS])
    for celula in aba[1]:
        celula.font = Font(bold=True)

    coluna_severidade = next(i for i, (titulo, _) in enumerate(COLUNAS, start=1) if titulo == "Severidade")
    for clash in clashes:
        aba.append([extrator(clash) for _, extrator in COLUNAS])
        cor = CORES_SEVERIDADE.get(clash.get("severidade"))
        if cor:
            aba.cell(row=aba.max_row, column=coluna_severidade).fill = PatternFill("solid", fgColor=cor)

    for i, (titulo, _) in enumerate(COLUNAS, start=1):
        aba.column_dimensions[get_column_letter(i)].width = max(12, len(titulo) + 2)


def _montar_aba_resumo(wb, clashes, resultado_pre_checagens, metadados_projeto):
    resumo = montar_resumo_executivo(clashes, resultado_pre_checagens, metadados_projeto)
    aba = wb.create_sheet("Resumo", 0)

    linha = 1
    aba.cell(row=linha, column=1, value="Resumo Executivo — Clash Detection").font = Font(bold=True, size=14)
    linha += 2

    def secao(titulo, pares):
        nonlocal linha
        aba.cell(row=linha, column=1, value=titulo).font = Font(bold=True)
        linha += 1
        for chave, valor in pares:
            aba.cell(row=linha, column=1, value=str(chave))
            aba.cell(row=linha, column=2, value=valor)
            linha += 1
        linha += 1

    aba.cell(row=linha, column=1, value="Total de interferências ativas:")
    aba.cell(row=linha, column=2, value=resumo["totais"]["total_ativo"])
    linha += 1
    aba.cell(row=linha, column=1, value="Total de pendências (sem Aprovado/Aceito):")
    aba.cell(row=linha, column=2, value=resumo["totais"]["total_pendente"])
    linha += 2

    secao("Por severidade:", resumo["totais"]["por_severidade"].items())
    secao("Comparativo com a revisão anterior:", resumo["comparativo_revisao_anterior"].items())
    secao("Matriz disciplina x disciplina:", resumo["matriz_disciplinas"].items())
    secao("Distribuição por pavimento:", resumo["distribuicao_por_pavimento"].items())
    secao("Pendências por disciplina responsável:", resumo["pendencias_por_disciplina"].items())

    aba.column_dimensions["A"].width = 42
    aba.column_dimensions["B"].width = 16
