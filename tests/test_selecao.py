"""Testes de clash/selecao.py: seleção A/B (arquivo > nível) estilo
Navisworks — agrupamento a partir de niveis_info, estado marcado/parcial
por arquivo, e a regra de quais pares testar (um elemento em cada lado)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clash.selecao import SelecaoLado, agrupar_por_arquivo, par_deve_ser_testado


def _niveis_info_exemplo():
    return {
        ("arq_a.ifc", "guid-a1"): {"nome": "Térreo", "elevacao": 0.0, "caminho": "arq_a.ifc"},
        ("arq_a.ifc", "guid-a2"): {"nome": "1º Pavimento", "elevacao": 3.0, "caminho": "arq_a.ifc"},
        ("arq_b.ifc", "guid-b1"): {"nome": "Térreo", "elevacao": 0.0, "caminho": "arq_b.ifc"},
    }


class _ElementoFake:
    def __init__(self, arquivo, nivel_guid):
        self.arquivo = arquivo
        self.nivel_guid = nivel_guid


def test_agrupar_por_arquivo_ordena_por_elevacao():
    agrupado = agrupar_por_arquivo(_niveis_info_exemplo())
    assert set(agrupado.keys()) == {"arq_a.ifc", "arq_b.ifc"}
    nomes_a = [nome for _, nome, _ in agrupado["arq_a.ifc"]]
    assert nomes_a == ["Térreo", "1º Pavimento"]  # Térreo (elev 0) antes do 1º Pav (elev 3)
    assert len(agrupado["arq_b.ifc"]) == 1
    print("OK agrupar_por_arquivo agrupa por caminho e ordena níveis por elevação")


def test_selecao_comeca_vazia():
    selecao = SelecaoLado()
    assert selecao.esta_vazia()
    assert not selecao.nivel_marcado("arq_a.ifc", "guid-a1")
    print("OK SelecaoLado começa sem nada marcado")


def test_alternar_nivel_marca_e_desmarca():
    selecao = SelecaoLado()
    selecao.alternar_nivel("arq_a.ifc", "guid-a1")
    assert selecao.nivel_marcado("arq_a.ifc", "guid-a1")
    assert not selecao.esta_vazia()

    selecao.alternar_nivel("arq_a.ifc", "guid-a1")
    assert not selecao.nivel_marcado("arq_a.ifc", "guid-a1")
    assert selecao.esta_vazia()
    print("OK alternar_nivel liga/desliga um nível específico")


def test_definir_arquivo_marca_todos_os_niveis_de_uma_vez():
    agrupado = agrupar_por_arquivo(_niveis_info_exemplo())
    selecao = SelecaoLado()

    selecao.definir_arquivo("arq_a.ifc", agrupado["arq_a.ifc"], True)
    assert selecao.nivel_marcado("arq_a.ifc", "guid-a1")
    assert selecao.nivel_marcado("arq_a.ifc", "guid-a2")
    assert not selecao.nivel_marcado("arq_b.ifc", "guid-b1")  # outro arquivo não é afetado
    assert selecao.arquivo_marcado("arq_a.ifc", agrupado["arq_a.ifc"])

    selecao.definir_arquivo("arq_a.ifc", agrupado["arq_a.ifc"], False)
    assert not selecao.nivel_marcado("arq_a.ifc", "guid-a1")
    assert not selecao.nivel_marcado("arq_a.ifc", "guid-a2")
    print("OK definir_arquivo marca/desmarca todos os níveis daquele arquivo, sem afetar outros")


def test_arquivo_parcial_quando_so_alguns_niveis_marcados():
    agrupado = agrupar_por_arquivo(_niveis_info_exemplo())
    selecao = SelecaoLado()

    assert not selecao.arquivo_parcial("arq_a.ifc", agrupado["arq_a.ifc"])  # nada marcado ainda

    selecao.alternar_nivel("arq_a.ifc", "guid-a1")
    assert selecao.arquivo_parcial("arq_a.ifc", agrupado["arq_a.ifc"])
    assert not selecao.arquivo_marcado("arq_a.ifc", agrupado["arq_a.ifc"])

    selecao.alternar_nivel("arq_a.ifc", "guid-a2")
    assert not selecao.arquivo_parcial("arq_a.ifc", agrupado["arq_a.ifc"])  # os dois marcados: não é mais parcial
    assert selecao.arquivo_marcado("arq_a.ifc", agrupado["arq_a.ifc"])
    print("OK arquivo fica \"parcial\" só quando alguns (não todos nem nenhum) níveis estão marcados")


def test_limitar_aos_arquivos_remove_marcacoes_de_arquivo_removido():
    selecao = SelecaoLado()
    selecao.alternar_nivel("arq_a.ifc", "guid-a1")
    selecao.alternar_nivel("arq_b.ifc", "guid-b1")

    selecao.limitar_aos_arquivos({"arq_a.ifc"})  # arq_b.ifc foi removido do visualizador

    assert selecao.nivel_marcado("arq_a.ifc", "guid-a1")
    assert not selecao.nivel_marcado("arq_b.ifc", "guid-b1")
    print("OK limitar_aos_arquivos tira marcações de arquivos que não existem mais, preserva o resto")


def test_par_deve_ser_testado_um_elemento_em_cada_lado():
    selecao_a = SelecaoLado()
    selecao_b = SelecaoLado()
    selecao_a.alternar_nivel("arq_a.ifc", "guid-a1")
    selecao_b.alternar_nivel("arq_b.ifc", "guid-b1")

    elemento_a = _ElementoFake("arq_a.ifc", "guid-a1")
    elemento_b = _ElementoFake("arq_b.ifc", "guid-b1")

    assert par_deve_ser_testado(elemento_a, elemento_b, selecao_a, selecao_b)
    assert par_deve_ser_testado(elemento_b, elemento_a, selecao_a, selecao_b)  # ordem não importa
    print("OK par_deve_ser_testado aceita um elemento em A e o outro em B, em qualquer ordem")


def test_par_deve_ser_testado_rejeita_quando_ambos_do_mesmo_lado():
    selecao_a = SelecaoLado()
    selecao_b = SelecaoLado()
    selecao_a.alternar_nivel("arq_a.ifc", "guid-a1")
    selecao_a.alternar_nivel("arq_a.ifc", "guid-a2")  # os dois elementos ficam em A, nenhum em B

    elemento_1 = _ElementoFake("arq_a.ifc", "guid-a1")
    elemento_2 = _ElementoFake("arq_a.ifc", "guid-a2")

    assert not par_deve_ser_testado(elemento_1, elemento_2, selecao_a, selecao_b)
    print("OK par_deve_ser_testado rejeita quando os dois elementos estão do mesmo lado (ou de fora)")


def test_par_deve_ser_testado_rejeita_elemento_fora_de_qualquer_selecao():
    selecao_a = SelecaoLado()
    selecao_b = SelecaoLado()
    selecao_a.alternar_nivel("arq_a.ifc", "guid-a1")
    selecao_b.alternar_nivel("arq_b.ifc", "guid-b1")

    elemento_a = _ElementoFake("arq_a.ifc", "guid-a1")
    elemento_fora = _ElementoFake("arq_c.ifc", "guid-c1")  # não marcado em nenhum dos dois lados

    assert not par_deve_ser_testado(elemento_a, elemento_fora, selecao_a, selecao_b)
    print("OK par_deve_ser_testado rejeita quando um elemento não está marcado em nenhum dos dois lados")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE SELEÇÃO A/B PASSARAM")
