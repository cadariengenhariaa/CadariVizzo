"""Testes de clash/disciplinas.py: ordem de prioridade da inferência de
disciplina (arquivo > pset > sistema > classe IFC > OUTRO)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clash.disciplinas import DISCIPLINA_DESCONHECIDA, disciplina_por_caminho, inferir_disciplina
from tests.fixtures_clash import (
    adicionar_elemento_prisma,
    adicionar_pset_disciplina,
    adicionar_sistema,
    carregar_regras_teste,
    criar_ifc_base,
)


def _regras():
    return carregar_regras_teste()


def test_padroes_de_caminho_cobrem_estrutura_real_de_pastas():
    regras = _regras()
    casos = {
        r"Z:/Projetos/Ativos/CA-1386/1386-DADOS/1386-ARQ/1386-2026.08.19-TORRE C/PDF/plantabaixa.ifc": "ARQ",
        r"Z:\Projetos\Ativos\CA-1386\1386-DADOS\1386-HID\modelo.ifc": "HID",
        r"...\1386-ELE\quadros.ifc": "ELE",
        r"...\1386-CLIM\dutos.ifc": "CLIM",
        r"...\1386-PCI\sprinklers.ifc": "PCI",
        r"...\1386-GAS\rede.ifc": "GAS",
        r"...\1386-TEL\racks.ifc": "TEL",
        r"...\1386-SPDA\paras-raios.ifc": "SPDA",
        r"...\1386-EST\vigas.ifc": "EST",
    }
    for caminho, esperado in casos.items():
        assert disciplina_por_caminho(caminho, regras) == esperado, caminho
    print("OK padrões de caminho cobrem a estrutura real de pastas por disciplina")


def test_caminho_sem_padrao_nao_bate():
    regras = _regras()
    assert disciplina_por_caminho(r"Z:\qualquer\coisa\sem_padrao.ifc", regras) is None
    print("OK caminho sem padrão conhecido não gera falso positivo")


def test_fallback_por_classe_ifc():
    f, body, storey = criar_ifc_base()
    parede = adicionar_elemento_prisma(f, body, storey, nome="Parede1", ifc_class="IfcWall")
    tubo = adicionar_elemento_prisma(f, body, storey, nome="Tubo1", ifc_class="IfcPipeSegment")
    duto = adicionar_elemento_prisma(f, body, storey, nome="Duto1", ifc_class="IfcDuctSegment")
    cabo = adicionar_elemento_prisma(f, body, storey, nome="Cabo1", ifc_class="IfcCableCarrierSegment")
    desconhecido = adicionar_elemento_prisma(f, body, storey, nome="X1", ifc_class="IfcBuildingElementProxy")

    regras = _regras()
    caminho_neutro = "C:/sem_padrao_nenhum.ifc"
    assert inferir_disciplina(parede, caminho_neutro, regras) == "ARQ"
    assert inferir_disciplina(tubo, caminho_neutro, regras) == "HID"
    assert inferir_disciplina(duto, caminho_neutro, regras) == "CLIM"
    assert inferir_disciplina(cabo, caminho_neutro, regras) == "ELE"
    assert inferir_disciplina(desconhecido, caminho_neutro, regras) == DISCIPLINA_DESCONHECIDA
    print("OK fallback por classe IFC (e OUTRO para classe não mapeada) funciona")


def test_prioridade_arquivo_vence_classe():
    f, body, storey = criar_ifc_base()
    # elemento é uma parede (classe -> ARQ), mas o arquivo está na pasta
    # de Hidrossanitário — a origem deve vencer, pois reflete a
    # organização real do escritório (um "duto de passagem" desenhado
    # junto com a prancha de HID, por exemplo).
    parede = adicionar_elemento_prisma(f, body, storey, nome="Parede2", ifc_class="IfcWall")
    regras = _regras()
    caminho_hid = r"Z:\Projetos\Ativos\CA-1386\1386-DADOS\1386-HID\modelo.ifc"
    assert inferir_disciplina(parede, caminho_hid, regras) == "HID"
    print("OK padrão do caminho do arquivo tem prioridade sobre a classe IFC")


def test_prioridade_pset_vence_classe_mas_perde_para_arquivo():
    f, body, storey = criar_ifc_base()
    elemento = adicionar_elemento_prisma(f, body, storey, nome="Proxy1", ifc_class="IfcBuildingElementProxy")
    adicionar_pset_disciplina(f, elemento, "PCI")
    regras = _regras()

    assert inferir_disciplina(elemento, "C:/sem_padrao_nenhum.ifc", regras) == "PCI"

    caminho_arq = r"Z:\Projetos\Ativos\CA-1386\1386-DADOS\1386-ARQ\modelo.ifc"
    assert inferir_disciplina(elemento, caminho_arq, regras) == "ARQ"
    print("OK propriedade explícita de disciplina vence a classe, mas perde para o caminho do arquivo")


def test_prioridade_sistema_vence_classe_mas_perde_para_pset():
    f, body, storey = criar_ifc_base()
    # IfcFlowTerminal: elemento de distribuição genérico, sem entrada em
    # `classe_ifc` — assim, se a inferência por sistema falhar, o teste
    # cai para OUTRO em vez de mascarar o bug caindo noutra disciplina.
    elemento = adicionar_elemento_prisma(f, body, storey, nome="Terminal1", ifc_class="IfcFlowTerminal")
    adicionar_sistema(f, [elemento], predefined_type="FIREPROTECTION")
    regras = _regras()

    assert inferir_disciplina(elemento, "C:/sem_padrao_nenhum.ifc", regras) == "PCI"

    adicionar_pset_disciplina(f, elemento, "ELE")
    assert inferir_disciplina(elemento, "C:/sem_padrao_nenhum.ifc", regras) == "ELE"
    print("OK PredefinedType do sistema vence a classe, mas perde para uma propriedade explícita")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE DISCIPLINAS PASSARAM")
