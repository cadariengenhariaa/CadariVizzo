"""Testes de projeto_vrf.py com uma árvore de pastas sintética (nunca a
rede): pasta da obra, VRF por disciplina (padrão novo e antigo), lista
de documentos, cópias certificadas e nome do arquivo certificado."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from projeto_vrf import (
    contar_pranchas,
    iniciais,
    listar_documentos,
    nome_certificado,
    numero_obra,
    obra_do_caminho,
    pasta_vrf,
    revisao,
    selo_no_nome,
)


def _arvore():
    base = tempfile.mkdtemp(prefix="teste_vrf_")
    novo = os.path.join(base, "CA-1439A", "1439A-VRF", "1439A-PCI")
    antigo = os.path.join(base, "CA-1005", "1005-VRF", "PCI")
    so_obra = os.path.join(base, "CA-0001")
    for pasta in (novo, antigo, so_obra, os.path.join(novo, "1439A-PAST")):
        os.makedirs(pasta)
    for nome in ("1439A-PCI_EX_26_10_14_R00_NPG.pdf", "1439A-PCI_EX_26_10_14_R00_NPG_HAC_APCR.pdf",
                 "Thumbs.db", "modelo.ifc"):
        open(os.path.join(novo, nome), "wb").close()
        time.sleep(0.01)
    open(os.path.join(novo, "1439A-PAST", "velho.pdf"), "wb").close()
    return base, novo, antigo, so_obra


def test_pasta_vrf_padrao_novo_antigo_e_fallbacks():
    base, novo, antigo, so_obra = _arvore()
    assert pasta_vrf("CA-1439A", "PCI", base) == novo
    assert pasta_vrf("CA-1005", "PCI", base) == antigo
    assert pasta_vrf("CA-1439A", "HID", base) == os.path.dirname(novo)  # sem a disciplina: a VRF
    assert pasta_vrf("CA-0001", "PCI", base) == so_obra                  # sem VRF: a obra
    assert pasta_vrf("CA-9999", "PCI", base) is None
    assert numero_obra("CA-1439A") == "1439A"
    assert obra_do_caminho(r"Z:\Projetos\Ativos\CA-1439A\x.pdf") == "CA-1439A"


def test_listar_documentos_e_certificados():
    base, novo, _a, _o = _arvore()
    docs = listar_documentos(novo, "pdf")
    assert [d["nome"] for d in docs] == ["1439A-PCI_EX_26_10_14_R00_NPG_HAC_APCR.pdf",
                                         "1439A-PCI_EX_26_10_14_R00_NPG.pdf"]  # mais recente primeiro
    assert docs[0]["certificado"] == "APCR" and docs[1]["certificado"] is None
    assert docs[1]["revisao"] == "R00"
    assert [d["nome"] for d in listar_documentos(novo, "ifc")] == ["modelo.ifc"]
    assert contar_pranchas("CA-1439A", "pdf", base) == (1, 1, "R00")


def test_nomes_iniciais_selo_e_revisao():
    assert iniciais("Lucas Coutinho Ferreira Gomes") == "LCFG"
    assert iniciais("Ana Elisa da Silva") == "AES"
    assert selo_no_nome("x_GL_CAFJ_APCA.pdf") == "APCA"
    assert selo_no_nome("1002_PCI_PE_010_LMT_MJNR_SLC_APCA0.pdf") == "APCA"
    assert selo_no_nome("1439A-PRE_EX_26_10_16_PHGO.pdf") is None
    assert selo_no_nome("planta_APR.pdf") == "APR"
    assert revisao("1464-VRF-PCI-PE-26.08.26-GL-R00.pdf") == "R00"
    assert nome_certificado(r"Z:\p\prancha_R00.pdf", "HAC", "APCR") == os.path.join(r"Z:\p", "prancha_R00_HAC_APCR.pdf")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE PROJETO/VRF PASSARAM")
