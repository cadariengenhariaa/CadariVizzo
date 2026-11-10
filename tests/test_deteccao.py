"""Testes de ponta a ponta do motor de clash (clash/motor.py) contra os
4 cenários pedidos: hard clash, folga insuficiente, duplicado e o falso
positivo de furo previsto (que deve ser excluído, não reportado)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ifcopenshell.util.element

from clash.motor import rodar_clash
from clash.selecao import SelecaoLado
from tests.fixtures_clash import (
    adicionar_elemento_prisma,
    carregar_regras_teste,
    cenario_duplicado,
    cenario_folga_insuficiente,
    cenario_furo_previsto,
    cenario_hard_clash,
    criar_ifc_base,
)


def _rodar(arquivos_ifc):
    regras = carregar_regras_teste()
    return rodar_clash(arquivos_ifc, regras, persistir=False)


def test_hard_clash_detectado_com_severidade_critica():
    arquivos_ifc, viga, duto = cenario_hard_clash()
    resultado = _rodar(arquivos_ifc)
    clashes = resultado["clashes"]

    assert len(clashes) == 1, clashes
    clash = clashes[0]
    assert clash["tipo"] == "hard"
    assert clash["penetracao_m"] > 0.01
    assert clash["severidade"] == "Critica"  # envolve Estrutura
    assert {clash["disciplina_a"], clash["disciplina_b"]} == {"EST", "CLIM"}
    assert clash["rastreamento"] == "Novo"
    assert clash["status"] == "Novo"
    print("OK hard clash detectado: penetração", clash["penetracao_m"], "severidade", clash["severidade"])


def test_folga_insuficiente_detectada_com_distancia_correta():
    arquivos_ifc, tubo, duto = cenario_folga_insuficiente()
    resultado = _rodar(arquivos_ifc)
    clashes = resultado["clashes"]

    assert len(clashes) == 1, clashes
    clash = clashes[0]
    assert clash["tipo"] == "folga"
    assert abs(clash["distancia_m"] - 0.02) < 1e-6
    assert clash["folga_exigida_m"] == 0.05
    assert {clash["disciplina_a"], clash["disciplina_b"]} == {"HID", "CLIM"}
    print("OK folga insuficiente detectada: distância", clash["distancia_m"], "exigida", clash["folga_exigida_m"])


def test_duplicado_detectado_e_nao_vira_hard_clash():
    arquivos_ifc, parede1, parede2 = cenario_duplicado()
    resultado = _rodar(arquivos_ifc)
    clashes = resultado["clashes"]

    assert len(clashes) == 1, clashes
    clash = clashes[0]
    assert clash["tipo"] == "duplicado"
    assert clash["disciplina_a"] == clash["disciplina_b"] == "ARQ"
    print("OK duplicado detectado (e classificado como duplicado, não hard clash)")


def test_furo_previsto_e_excluido_sem_gerar_clash():
    arquivos_ifc, viga, duto = cenario_furo_previsto()
    resultado = _rodar(arquivos_ifc)
    clashes = resultado["clashes"]

    assert clashes == [], clashes
    print("OK furo previsto corretamente excluído — nenhum falso positivo")


def test_cenarios_nao_interferem_entre_si_quando_combinados():
    """Coloca um par de hard clash e um par de folga insuficiente no
    MESMO arquivo, bem separados espacialmente, e confirma que cada um é
    detectado exatamente uma vez — garante que o broad-phase/agrupamento
    não perde nem conflate candidatos quando há mais de um grupo de
    elementos no modelo."""
    f, body, storey = criar_ifc_base(prefixo_unidade_comprimento=None)

    # grupo 1 (hard clash: EST x CLIM) perto da origem
    adicionar_elemento_prisma(f, body, storey, nome="Viga-Hard", ifc_class="IfcBeam",
                               length=2.0, height=0.5, thickness=0.3)
    adicionar_elemento_prisma(f, body, storey, nome="Duto-Hard", ifc_class="IfcDuctSegment",
                               length=1.0, height=0.3, thickness=0.3, deslocamento=(0.5, 0.0, 0.1))

    # grupo 2 (folga insuficiente: HID x CLIM) bem longe do grupo 1, para
    # não haver nenhuma sobreposição de bounding box entre os grupos
    offset = (100.0, 100.0, 100.0)
    adicionar_elemento_prisma(f, body, storey, nome="Tubo-Folga", ifc_class="IfcPipeSegment",
                               length=1.0, height=0.1, thickness=0.1, deslocamento=offset)
    adicionar_elemento_prisma(f, body, storey, nome="Duto-Folga", ifc_class="IfcDuctSegment",
                               length=1.0, height=0.1, thickness=0.1,
                               deslocamento=(offset[0] + 1.02, offset[1], offset[2]))

    resultado = _rodar({"modelo_coordenacao.ifc": f})
    tipos = sorted(c["tipo"] for c in resultado["clashes"])
    assert tipos == ["folga", "hard"], tipos
    print("OK múltiplos cenários combinados detectados sem interferência entre si")


def test_selecao_ab_restringe_o_motor_a_pares_entre_os_dois_lados():
    """Ponta a ponta com a seleção A/B (estilo Navisworks) no lugar da
    matriz de disciplinas: viga e duto em arquivos/níveis separados,
    fisicamente se cruzando — só deve virar clash quando um está em A e
    o outro em B; com os dois do mesmo lado, nada é testado."""
    f1, body1, storey1 = criar_ifc_base(prefixo_unidade_comprimento=None)
    viga = adicionar_elemento_prisma(f1, body1, storey1, nome="Viga", ifc_class="IfcBeam",
                                      length=2.0, height=0.5, thickness=0.3)
    f2, body2, storey2 = criar_ifc_base(prefixo_unidade_comprimento=None)
    duto = adicionar_elemento_prisma(f2, body2, storey2, nome="Duto", ifc_class="IfcDuctSegment",
                                      length=1.0, height=0.3, thickness=0.3, deslocamento=(0.5, 0.0, 0.1))

    arquivos_ifc = {"viga.ifc": f1, "duto.ifc": f2}
    regras = carregar_regras_teste()
    guid_nivel_viga = ifcopenshell.util.element.get_container(viga).GlobalId
    guid_nivel_duto = ifcopenshell.util.element.get_container(duto).GlobalId

    selecao_a = SelecaoLado()
    selecao_a.alternar_nivel("viga.ifc", guid_nivel_viga)
    selecao_b = SelecaoLado()
    selecao_b.alternar_nivel("duto.ifc", guid_nivel_duto)
    resultado = rodar_clash(arquivos_ifc, regras, persistir=False, selecao_a=selecao_a, selecao_b=selecao_b)
    assert len(resultado["clashes"]) == 1, resultado["clashes"]

    # os dois do mesmo lado (B vazio) -> nenhum par é candidato
    selecao_a_tudo = SelecaoLado()
    selecao_a_tudo.alternar_nivel("viga.ifc", guid_nivel_viga)
    selecao_a_tudo.alternar_nivel("duto.ifc", guid_nivel_duto)
    selecao_b_vazia = SelecaoLado()
    resultado_vazio = rodar_clash(
        arquivos_ifc, regras, persistir=False, selecao_a=selecao_a_tudo, selecao_b=selecao_b_vazia
    )
    assert len(resultado_vazio["clashes"]) == 0
    print("OK seleção A/B restringe o motor a pares com um elemento em cada lado")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE DETECÇÃO PASSARAM")
