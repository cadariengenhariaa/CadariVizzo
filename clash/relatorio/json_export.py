"""Exportação JSON — para integração com outras ferramentas e para
re-importar status/comentários numa rodada futura (o mesmo formato que
`clash.armazenamento` grava/lê, mais o resumo executivo embutido)."""
import json

from clash.relatorio.dados_relatorio import montar_resumo_executivo


def exportar_json(clashes, caminho, resultado_pre_checagens=None, metadados_projeto=None):
    dados = {
        "resumo_executivo": montar_resumo_executivo(clashes, resultado_pre_checagens, metadados_projeto),
        "interferencias": clashes,
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return caminho
