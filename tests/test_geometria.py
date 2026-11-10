"""Testes de clash/geometria.py: extração de malha por elemento, em
coordenadas do mundo, com metadados (disciplina/nível/guid)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clash.geometria import extrair_elementos
from tests.fixtures_clash import adicionar_elemento_prisma, carregar_regras_teste, criar_ifc_base


def test_extrai_um_elemento_por_malha_com_bbox_correta():
    # fixture em milímetros (padrão) — uma parede "4000" deve virar 4.0 m
    # depois da normalização de unidade feita por extrair_elementos.
    f, body, storey = criar_ifc_base()
    parede = adicionar_elemento_prisma(f, body, storey, nome="ParedeG", ifc_class="IfcWall",
                                        length=4000.0, height=3000.0, thickness=200.0)
    regras = carregar_regras_teste()

    elementos = extrair_elementos(f, "C:/sem_padrao.ifc", regras)

    assert len(elementos) == 1
    el = elementos[0]
    assert el.guid == parede.GlobalId
    assert el.ifc_class == "IfcWall"
    assert el.disciplina == "ARQ"
    assert el.nivel == "Storey"
    assert el.malha.vertices.shape[0] > 0
    assert el.malha.faces.shape[0] > 0

    # bbox já normalizada para METROS (4,0 x 3,0 x 0,2), não os "4000"
    # milímetros brutos usados para desenhar a parede.
    tamanho = el.bbox_max - el.bbox_min
    assert abs(tamanho[0] - 4.0) < 1e-6 or abs(tamanho[1] - 4.0) < 1e-6  # comprimento em X ou Y, a depender do eixo
    print("OK malha extraída com guid/classe/disciplina/nível/bbox corretos (já em metros)")


def test_normaliza_unidade_para_metros_entre_arquivos_diferentes():
    """O mesmo cenário físico (parede de 4m) modelado em dois arquivos com
    unidades de comprimento diferentes (milímetro x metro) deve produzir
    a MESMA bbox em metros depois de `extrair_elementos` — sem essa
    normalização, um modelo de coordenação com arquivos em unidades
    distintas geraria clashes completamente errados (ou nenhum)."""
    regras = carregar_regras_teste()

    f_mm, body_mm, storey_mm = criar_ifc_base(prefixo_unidade_comprimento="MILLI")
    adicionar_elemento_prisma(f_mm, body_mm, storey_mm, ifc_class="IfcWall",
                               length=4000.0, height=3000.0, thickness=200.0)
    elementos_mm = extrair_elementos(f_mm, "arquivo_em_mm.ifc", regras)

    f_m, body_m, storey_m = criar_ifc_base(prefixo_unidade_comprimento=None)
    adicionar_elemento_prisma(f_m, body_m, storey_m, ifc_class="IfcWall",
                               length=4.0, height=3.0, thickness=0.2)
    elementos_m = extrair_elementos(f_m, "arquivo_em_m.ifc", regras)

    tamanho_mm = elementos_mm[0].bbox_max - elementos_mm[0].bbox_min
    tamanho_m = elementos_m[0].bbox_max - elementos_m[0].bbox_min
    assert np.allclose(tamanho_mm, tamanho_m, atol=1e-6), (tamanho_mm, tamanho_m)
    print("OK arquivos em mm e em m produzem a mesma bbox em metros após a normalização")


def test_extrai_varios_elementos_de_disciplinas_diferentes():
    f, body, storey = criar_ifc_base()
    adicionar_elemento_prisma(f, body, storey, nome="Parede", ifc_class="IfcWall")
    adicionar_elemento_prisma(f, body, storey, nome="Tubo", ifc_class="IfcPipeSegment")
    adicionar_elemento_prisma(f, body, storey, nome="Duto", ifc_class="IfcDuctSegment")
    regras = carregar_regras_teste()

    elementos = extrair_elementos(f, "C:/sem_padrao.ifc", regras)
    disciplinas = sorted(e.disciplina for e in elementos)

    assert len(elementos) == 3
    assert disciplinas == ["ARQ", "CLIM", "HID"]
    print("OK extração cobre vários elementos com disciplinas distintas")


def test_ifc_vazio_nao_quebra():
    f, _, _ = criar_ifc_base()
    regras = carregar_regras_teste()
    elementos = extrair_elementos(f, "C:/sem_padrao.ifc", regras)
    assert elementos == []
    print("OK IFC sem elementos de geometria não quebra, devolve lista vazia")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE GEOMETRIA PASSARAM")
