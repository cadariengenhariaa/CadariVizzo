import sys

import pytest

import instancia_unica


def test_fora_do_windows_nunca_bloqueia(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert instancia_unica.adquirir() is True
    assert instancia_unica.focar_instancia_existente() is False


@pytest.mark.skipif(sys.platform != "win32", reason="mutex nomeado só existe no Windows")
def test_segunda_aquisicao_e_bloqueada():
    nome = "Local\\CadariVizzo_Teste_InstanciaUnica"
    assert instancia_unica.adquirir(nome) is True
    assert instancia_unica.adquirir(nome) is False
