"""Utilitário manual (não é um teste pytest) para gerar exemplos reais
de relatório (PDF, XLSX, BCF, JSON) a partir dos cenários sintéticos de
teste — entregável pedido: "Exemplo de relatório gerado a partir dos
modelos de teste". Rode com `python tests/gerar_exemplos.py` a partir da
raiz do projeto. A saída vai para `exemplos_relatorio/` (gitignored —
são exemplos gerados, não arquivos versionados)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clash.geometria import configuracoes_padrao
from clash.motor import rodar_clash
from clash.relatorio import bcf, json_export, pdf, xlsx
from tests.fixtures_clash import cenario_duplicado, cenario_folga_insuficiente, cenario_furo_previsto, cenario_hard_clash
from tests.fixtures_clash import carregar_regras_teste as carregar_regras

PASTA_SAIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exemplos_relatorio")


def main():
    os.makedirs(PASTA_SAIDA, exist_ok=True)

    arquivos_ifc = {}
    f_hard, _, _ = cenario_hard_clash(offset=(0.0, 0.0, 0.0))
    f_folga, _, _ = cenario_folga_insuficiente(offset=(100.0, 0.0, 0.0))
    f_dup, _, _ = cenario_duplicado(offset=(200.0, 0.0, 0.0))
    f_furo, _, _ = cenario_furo_previsto(offset=(300.0, 0.0, 0.0))
    arquivos_ifc["hard.ifc"] = list(f_hard.values())[0]
    arquivos_ifc["folga.ifc"] = list(f_folga.values())[0]
    arquivos_ifc["duplicado.ifc"] = list(f_dup.values())[0]
    arquivos_ifc["furo_previsto.ifc"] = list(f_furo.values())[0]

    regras = carregar_regras()
    resultado = rodar_clash(arquivos_ifc, regras, persistir=False)
    clashes = resultado["clashes"]
    escala_por_arquivo = resultado["pre_checagens"].escala_por_arquivo
    metadados = {
        "Projeto": "Exemplo — modelos sintéticos de teste",
        "Arquivos analisados": ", ".join(arquivos_ifc.keys()),
        "Regras": "clash/regras_clash.yaml (padrão)",
    }

    print(f"{resultado['n_elementos']} elementos, {resultado['n_pares_candidatos']} pares candidatos, "
          f"{len(clashes)} interferência(s) (inclui o furo previsto corretamente excluído = nenhum extra)")

    caminho_xlsx = os.path.join(PASTA_SAIDA, "exemplo_relatorio.xlsx")
    xlsx.exportar_xlsx(clashes, caminho_xlsx, resultado["pre_checagens"], metadados)
    print("XLSX:", caminho_xlsx)

    caminho_json = os.path.join(PASTA_SAIDA, "exemplo_relatorio.json")
    json_export.exportar_json(clashes, caminho_json, resultado["pre_checagens"], metadados)
    print("JSON:", caminho_json)

    caminho_bcf = os.path.join(PASTA_SAIDA, "exemplo_relatorio.bcfzip")
    bcf.exportar_bcf(clashes, caminho_bcf, arquivos_ifc=arquivos_ifc, escala_por_arquivo=escala_por_arquivo,
                      settings=configuracoes_padrao())
    print("BCF:", caminho_bcf)

    caminho_pdf = os.path.join(PASTA_SAIDA, "exemplo_relatorio.pdf")
    pdf.exportar_pdf(clashes, caminho_pdf, resultado["pre_checagens"], metadados,
                      arquivos_ifc=arquivos_ifc, escala_por_arquivo=escala_por_arquivo)
    print("PDF:", caminho_pdf)


if __name__ == "__main__":
    main()
