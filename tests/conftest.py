"""Configuração comum dos testes: preferências locais (tema, último
usuário, dicionário pessoal) vão para um arquivo temporário — nunca para
o %APPDATA% de quem roda os testes — e cada teste começa sem nenhuma
(senão o "Lembrar usuário" de um teste preencheria o login do próximo)."""
import os
import tempfile

import pytest

os.environ.setdefault("CADARI_VIZZO_PREFS",
                      os.path.join(tempfile.mkdtemp(prefix="teste_cadari_prefs_"), "preferencias.json"))


@pytest.fixture(autouse=True)
def _preferencias_limpas():
    caminho = os.environ["CADARI_VIZZO_PREFS"]
    if os.path.exists(caminho):
        os.remove(caminho)
    yield
