"""Testes de clash/indice_espacial.py: geração de pares candidatos pelo
broad-phase (R-tree) respeitando a matriz disciplina x disciplina."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clash.indice_espacial import pares_candidatos
from clash.selecao import SelecaoLado
from tests.fixtures_clash import carregar_regras_teste as carregar_regras


class _ElementoFake:
    def __init__(self, disciplina, bbox_min, bbox_max, arquivo="a.ifc", nivel_guid=None):
        self.disciplina = disciplina
        self.bbox_min = np.array(bbox_min, dtype=float)
        self.bbox_max = np.array(bbox_max, dtype=float)
        self.arquivo = arquivo
        self.nivel_guid = nivel_guid


def test_pares_proximos_viram_candidatos():
    elementos = [
        _ElementoFake("EST", (0, 0, 0), (1, 1, 1)),
        _ElementoFake("CLIM", (0.5, 0.5, 0.5), (1.5, 1.5, 1.5)),
    ]
    regras = carregar_regras()
    pares = pares_candidatos(elementos, regras)
    assert pares == [(0, 1)]
    print("OK bounding boxes sobrepostos viram par candidato")


def test_pares_muito_distantes_nao_viram_candidatos():
    elementos = [
        _ElementoFake("EST", (0, 0, 0), (1, 1, 1)),
        _ElementoFake("CLIM", (1000, 1000, 1000), (1001, 1001, 1001)),
    ]
    regras = carregar_regras()
    assert pares_candidatos(elementos, regras) == []
    print("OK elementos muito distantes não geram candidato (broad-phase funciona)")


def test_par_marcado_testar_false_e_descartado():
    elementos = [
        _ElementoFake("ARQ", (0, 0, 0), (1, 1, 1)),
        _ElementoFake("ARQ", (0.1, 0.1, 0.1), (1.1, 1.1, 1.1)),
    ]
    regras = carregar_regras()
    regras.matriz_disciplinas["ARQ|ARQ"] = {"testar": False}
    assert pares_candidatos(elementos, regras) == []
    print("OK par explicitamente marcado testar:false é descartado no broad-phase")


def test_folga_configurada_expande_a_busca_alem_do_bbox_estrito():
    # dois elementos cujos bounding boxes NÃO se tocam, mas a folga
    # mínima configurada para o par é maior que o vão entre eles — o
    # broad-phase precisa trazer esse par como candidato mesmo assim,
    # para a fase fina medir a distância exata.
    elementos = [
        _ElementoFake("HID", (0, 0, 0), (1, 1, 1)),
        _ElementoFake("CLIM", (1.03, 0, 0), (2.03, 1, 1)),  # vão de 0.03 m
    ]
    regras = carregar_regras()
    assert regras.folga_minima("HID", "CLIM") == 0.05  # maior que o vão de 0.03
    assert pares_candidatos(elementos, regras) == [(0, 1)]
    print("OK folga configurada expande a consulta espacial além do bbox estrito")


def test_selecao_ab_substitui_a_matriz_quando_os_dois_lados_sao_passados():
    elementos = [
        _ElementoFake("ARQ", (0, 0, 0), (1, 1, 1), arquivo="a.ifc", nivel_guid="nivel-a"),
        _ElementoFake("ARQ", (0.1, 0.1, 0.1), (1.1, 1.1, 1.1), arquivo="b.ifc", nivel_guid="nivel-b"),
    ]
    regras = carregar_regras()
    regras.matriz_disciplinas["ARQ|ARQ"] = {"testar": False}  # matriz diria "não", mas não é mais quem decide

    selecao_a = SelecaoLado()
    selecao_a.alternar_nivel("a.ifc", "nivel-a")
    selecao_b = SelecaoLado()
    selecao_b.alternar_nivel("b.ifc", "nivel-b")

    pares = pares_candidatos(elementos, regras, selecao_a=selecao_a, selecao_b=selecao_b)
    assert pares == [(0, 1)]
    print("OK com seleção A/B passada, ela decide os pares (ignora o testar:false da matriz)")


def test_selecao_ab_rejeita_par_do_mesmo_lado_mesmo_com_bbox_sobreposto():
    elementos = [
        _ElementoFake("ARQ", (0, 0, 0), (1, 1, 1), arquivo="a.ifc", nivel_guid="nivel-a1"),
        _ElementoFake("ARQ", (0.1, 0.1, 0.1), (1.1, 1.1, 1.1), arquivo="a.ifc", nivel_guid="nivel-a1"),
    ]
    regras = carregar_regras()
    selecao_a = SelecaoLado()
    selecao_a.alternar_nivel("a.ifc", "nivel-a1")  # os dois elementos ficam em A; B fica vazio
    selecao_b = SelecaoLado()

    assert pares_candidatos(elementos, regras, selecao_a=selecao_a, selecao_b=selecao_b) == []
    print("OK seleção A/B rejeita par com os dois elementos do mesmo lado, mesmo com bbox sobreposto")


def test_sem_selecao_ab_continua_usando_a_matriz_como_antes():
    # garante que passar só um dos dois (ou nenhum) mantém o comportamento
    # antigo — importante para o CLI e os demais testes não quebrarem.
    elementos = [
        _ElementoFake("ARQ", (0, 0, 0), (1, 1, 1)),
        _ElementoFake("ARQ", (0.1, 0.1, 0.1), (1.1, 1.1, 1.1)),
    ]
    regras = carregar_regras()
    regras.matriz_disciplinas["ARQ|ARQ"] = {"testar": False}
    assert pares_candidatos(elementos, regras, selecao_a=SelecaoLado()) == []
    assert pares_candidatos(elementos, regras) == []
    print("OK sem os dois lados da seleção, continua valendo a matriz de disciplinas (modo CLI)")


def test_lista_vazia_ou_com_um_elemento_nao_quebra():
    regras = carregar_regras()
    assert pares_candidatos([], regras) == []
    assert pares_candidatos([_ElementoFake("ARQ", (0, 0, 0), (1, 1, 1))], regras) == []
    print("OK lista vazia ou com um único elemento não quebra")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE ÍNDICE ESPACIAL PASSARAM")
