"""Testes de clash/agrupamento.py: ID estável entre revisões e chave de
agrupamento por pavimento/disciplina."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clash.agrupamento import chave_agrupamento, id_estavel


def test_id_estavel_independe_da_ordem_dos_guids():
    id1 = id_estavel("guid-a", "guid-b", "hard")
    id2 = id_estavel("guid-b", "guid-a", "hard")
    assert id1 == id2
    print("OK id estável não depende de qual GUID veio primeiro")


def test_id_estavel_muda_com_o_tipo():
    id_hard = id_estavel("guid-a", "guid-b", "hard")
    id_folga = id_estavel("guid-a", "guid-b", "folga")
    assert id_hard != id_folga
    print("OK tipos diferentes do mesmo par de elementos geram ids diferentes")


def test_id_estavel_e_deterministico():
    assert id_estavel("x", "y", "hard") == id_estavel("x", "y", "hard")
    print("OK id estável é determinístico (mesma entrada, mesma saída)")


class _ElementoFake:
    def __init__(self, nivel, disciplina):
        self.nivel = nivel
        self.disciplina = disciplina


def test_chave_agrupamento_usa_nivel_e_disciplinas_ordenadas():
    a = _ElementoFake("Pavimento 1", "CLIM")
    b = _ElementoFake("Pavimento 1", "HID")
    nivel, disciplinas = chave_agrupamento(a, b)
    assert nivel == "Pavimento 1"
    assert disciplinas == ("CLIM", "HID")

    # ordem inversa dos elementos não deveria mudar a chave
    nivel2, disciplinas2 = chave_agrupamento(b, a)
    assert (nivel2, disciplinas2) == (nivel, disciplinas)
    print("OK chave de agrupamento é estável independente da ordem dos elementos")


def test_chave_agrupamento_usa_nivel_do_outro_quando_um_esta_sem_nivel():
    a = _ElementoFake(None, "EST")
    b = _ElementoFake("Pavimento 2", "ARQ")
    nivel, _ = chave_agrupamento(a, b)
    assert nivel == "Pavimento 2"
    print("OK usa o nível do elemento que tem, quando o outro está sem nível")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE AGRUPAMENTO PASSARAM")
