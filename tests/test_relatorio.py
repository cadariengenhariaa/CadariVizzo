"""Testes dos formatos de relatório (XLSX, JSON, BCF, PDF) e da
estrutura de dados comum (resumo executivo) — gerados a partir dos
cenários sintéticos de clash já usados em test_deteccao.py."""
import os
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from clash.geometria import configuracoes_padrao
from clash.motor import rodar_clash
from clash.relatorio import bcf, json_export, pdf, xlsx
from clash.relatorio.dados_relatorio import (
    aplicar_filtros,
    clashes_ativos,
    matriz_disciplina_x_disciplina,
    montar_resumo_executivo,
    pendencias,
    pendencias_por_disciplina,
    top_elementos,
)
from tests.fixtures_clash import cenario_duplicado, cenario_folga_insuficiente, cenario_hard_clash
from tests.fixtures_clash import carregar_regras_teste as carregar_regras


def _resultado_combinado():
    """Roda hard clash + folga insuficiente + duplicado juntos (3
    arquivos separados, cada um com seu próprio cenário) e devolve o
    resultado completo do motor — a base de dados para todos os testes
    de relatório abaixo."""
    arquivos_ifc = {}
    f_hard, _, _ = cenario_hard_clash(offset=(0.0, 0.0, 0.0))
    f_folga, _, _ = cenario_folga_insuficiente(offset=(100.0, 0.0, 0.0))
    f_dup, _, _ = cenario_duplicado(offset=(200.0, 0.0, 0.0))
    arquivos_ifc["hard.ifc"] = list(f_hard.values())[0]
    arquivos_ifc["folga.ifc"] = list(f_folga.values())[0]
    arquivos_ifc["duplicado.ifc"] = list(f_dup.values())[0]

    regras = carregar_regras()
    resultado = rodar_clash(arquivos_ifc, regras, persistir=False)
    return resultado, arquivos_ifc


# ---------- dados_relatorio.py (funções puras) ----------
def test_montar_resumo_executivo_cobre_os_tres_tipos():
    resultado, _ = _resultado_combinado()
    clashes = resultado["clashes"]
    resumo = montar_resumo_executivo(clashes, resultado["pre_checagens"], {"Projeto": "Teste"})

    assert resumo["totais"]["total_ativo"] == 3
    assert set(resumo["totais"]["por_tipo"]) == {"hard", "folga", "duplicado"}
    assert resumo["comparativo_revisao_anterior"] == {"Novo": 3}
    assert resumo["metadados_projeto"] == {"Projeto": "Teste"}
    print("OK resumo executivo cobre hard/folga/duplicado corretamente")


def test_matriz_disciplinas_conta_pares_corretamente():
    resultado, _ = _resultado_combinado()
    matriz = matriz_disciplina_x_disciplina(resultado["clashes"])
    assert matriz[("CLIM", "EST")] == 1  # hard clash
    assert matriz[("CLIM", "HID")] == 1  # folga
    assert matriz[("ARQ", "ARQ")] == 1  # duplicado (mesma disciplina)
    print("OK matriz disciplina x disciplina conta os pares certos")


def test_pendencias_exclui_aprovado_e_aceito():
    resultado, _ = _resultado_combinado()
    clashes = resultado["clashes"]
    assert len(pendencias(clashes)) == 3

    clashes[0]["status"] = "Aceito"
    assert len(pendencias(clashes)) == 2
    assert len(clashes_ativos(clashes)) == 3  # ainda ativo, só não é mais "pendência"
    print("OK pendências exclui itens já Aceito/Aprovado, mas eles continuam em 'ativos'")


def test_pendencias_por_disciplina_usa_responsavel_sugerido():
    resultado, _ = _resultado_combinado()
    por_disciplina = pendencias_por_disciplina(resultado["clashes"])
    # EST nunca é responsável sugerido (é a disciplina mais rígida nas regras padrão)
    assert "EST" not in por_disciplina
    print("OK pendências agrupadas por responsável sugerido, nunca Estrutura")


def test_top_elementos_aponta_os_guids_mais_frequentes():
    resultado, _ = _resultado_combinado()
    top = top_elementos(resultado["clashes"])
    assert len(top) > 0
    assert all(item["quantidade"] >= 1 for item in top)
    print("OK top_elementos devolve os elementos mais frequentes nas interferências")


def test_aplicar_filtros_por_disciplina_e_severidade():
    resultado, _ = _resultado_combinado()
    clashes = resultado["clashes"]

    so_est = aplicar_filtros(clashes, disciplina="EST")
    assert len(so_est) == 1 and so_est[0]["tipo"] == "hard"

    so_criticas = aplicar_filtros(clashes, severidade="Critica")
    assert len(so_criticas) == 1 and so_criticas[0]["disciplina_a"] in ("EST", "CLIM")

    nenhum = aplicar_filtros(clashes, disciplina="GAS")
    assert nenhum == []
    print("OK filtros de exportação (disciplina/severidade) funcionam")


# ---------- xlsx ----------
def test_exportar_xlsx_gera_arquivo_com_as_duas_abas():
    resultado, _ = _resultado_combinado()
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "relatorio.xlsx")
        xlsx.exportar_xlsx(resultado["clashes"], caminho, resultado["pre_checagens"], {"Projeto": "Teste"})

        assert os.path.exists(caminho)
        wb = openpyxl.load_workbook(caminho)
        assert wb.sheetnames == ["Resumo", "Interferências"]

        aba = wb["Interferências"]
        assert aba.cell(row=1, column=1).value == "ID"
        assert aba.max_row == 4  # cabeçalho + 3 interferências
        print("OK XLSX gerado com abas Resumo e Interferências, uma linha por item")


# ---------- json ----------
def test_exportar_json_gera_estrutura_esperada():
    import json as json_mod
    resultado, _ = _resultado_combinado()
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "relatorio.json")
        json_export.exportar_json(resultado["clashes"], caminho, resultado["pre_checagens"])

        with open(caminho, encoding="utf-8") as f:
            dados = json_mod.load(f)

        assert "resumo_executivo" in dados and "interferencias" in dados
        assert len(dados["interferencias"]) == 3
        assert dados["resumo_executivo"]["totais"]["total_ativo"] == 3
        print("OK JSON gerado com resumo_executivo + interferencias")


# ---------- bcf ----------
def test_exportar_bcf_gera_um_topico_por_interferencia_com_componentes_selecionados():
    resultado, arquivos_ifc = _resultado_combinado()
    clashes = resultado["clashes"]

    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "relatorio.bcfzip")
        bcf.exportar_bcf(clashes, caminho, arquivos_ifc=arquivos_ifc,
                          escala_por_arquivo=resultado["pre_checagens"].escala_por_arquivo,
                          settings=configuracoes_padrao())

        assert os.path.exists(caminho)
        with zipfile.ZipFile(caminho) as z:
            nomes = z.namelist()
            assert "bcf.version" in nomes

            pastas = {n.split("/")[0] for n in nomes if "/" in n}
            assert len(pastas) == len(clashes)

            pasta_exemplo = sorted(pastas)[0]
            assert f"{pasta_exemplo}/markup.bcf" in nomes
            assert f"{pasta_exemplo}/viewpoint.bcfv" in nomes

            markup = ET.fromstring(z.read(f"{pasta_exemplo}/markup.bcf"))
            assert markup.find("Topic") is not None
            assert markup.find("Topic").get("TopicStatus") == "Open"

            viewpoint = ET.fromstring(z.read(f"{pasta_exemplo}/viewpoint.bcfv"))
            componentes = viewpoint.findall(".//Component")
            assert len(componentes) == 2
            guids_no_viewpoint = {c.get("IfcGuid") for c in componentes}
            assert guids_no_viewpoint  # não vazio — tem os 2 GUIDs selecionados
        print("OK BCF gerado: um tópico por interferência, com os 2 componentes selecionados no viewpoint")


def test_exportar_bcf_sem_arquivos_ifc_ainda_funciona_sem_snapshot():
    """Mesmo sem conseguir gerar o snapshot (ex.: sem acesso aos IFCs de
    origem), o BCF deve sair válido, só sem a imagem."""
    resultado, _ = _resultado_combinado()
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "sem_snapshot.bcfzip")
        bcf.exportar_bcf(resultado["clashes"], caminho, arquivos_ifc=None, escala_por_arquivo=None)

        with zipfile.ZipFile(caminho) as z:
            pastas = {n.split("/")[0] for n in z.namelist() if "/" in n}
            for pasta in pastas:
                assert f"{pasta}/snapshot.png" not in z.namelist()
                assert f"{pasta}/markup.bcf" in z.namelist()
        print("OK BCF sem acesso aos IFCs de origem ainda gera tópicos válidos (sem snapshot)")


# ---------- pdf ----------
def test_exportar_pdf_gera_arquivo_valido_com_e_sem_snapshot():
    resultado, arquivos_ifc = _resultado_combinado()
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "relatorio.pdf")
        pdf.exportar_pdf(resultado["clashes"], caminho, resultado["pre_checagens"], {"Projeto": "Teste"},
                          arquivos_ifc=arquivos_ifc, escala_por_arquivo=resultado["pre_checagens"].escala_por_arquivo)

        assert os.path.exists(caminho)
        with open(caminho, "rb") as f:
            cabecalho = f.read(5)
        assert cabecalho == b"%PDF-"
        assert os.path.getsize(caminho) > 1000
        print("OK PDF gerado (com snapshots), cabeçalho %PDF- válido, tamanho razoável")


def test_exportar_pdf_sem_snapshots_tambem_funciona():
    resultado, _ = _resultado_combinado()
    with tempfile.TemporaryDirectory() as tmp:
        caminho = os.path.join(tmp, "sem_snapshot.pdf")
        pdf.exportar_pdf(resultado["clashes"], caminho, resultado["pre_checagens"], incluir_snapshots=False)
        assert os.path.exists(caminho) and os.path.getsize(caminho) > 500
        print("OK PDF sem snapshots também gera um arquivo válido")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE RELATÓRIO PASSARAM")
