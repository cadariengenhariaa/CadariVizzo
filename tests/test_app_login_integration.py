"""Teste de integração: login obrigatório em app.py (AppCDE) — nunca
toca no banco de produção.

`utils.py` resolve `DB_DIR`/`DB_FILE` uma vez no IMPORT (`from config
import DB_DIR, DB_FILE`), não a cada chamada — se outro módulo de teste
já tiver importado `utils` antes deste arquivo rodar (pytest importa
todos os módulos de teste na coleta, em alguma ordem), a reatribuição de
`config.DB_DIR` sozinha não bastaria. Por segurança, sobrescrevemos
`utils.DB_DIR`/`utils.DB_FILE` diretamente também — o mesmo cuidado já
usado nos primeiros testes deste projeto (ver histórico de
pdf_viewer.py) antes de `clash/armazenamento.py` passar a resolver o
caminho em tempo de chamada."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_app_login_")
config.DB_FILE = os.path.join(config.DB_DIR, "db_issues.json")

import utils

utils.DB_DIR = config.DB_DIR
utils.DB_FILE = config.DB_FILE

import app as app_module
from app import AppCDE

AppCDE.carregar_obras = lambda self: None


class _FakeDialogLoginSucesso:
    def __init__(self, parent):
        self.usuario = {"nome_usuario": "fulano", "email": "fulano@a.com", "nome": "Fulano", "papel": "projetista"}


class _FakeDialogLoginCancelado:
    def __init__(self, parent):
        self.usuario = None


def test_login_bem_sucedido_abre_a_home_com_sessao_preenchida():
    # proteção: nunca o DB_DIR real — ver nota equivalente em
    # test_rastreamento.py sobre por que isto checa uma propriedade
    # (dentro do temp do sistema) em vez de um prefixo específico deste
    # arquivo.
    assert config.DB_DIR.startswith(tempfile.gettempdir())
    app_module.DialogLogin = _FakeDialogLoginSucesso

    a = AppCDE()
    assert a.usuario_atual is not None
    assert a.usuario_atual["nome"] == "Fulano"
    assert a.sessao["nome"] == "Fulano"
    assert a.sessao["obra"] == ""
    assert a.sessao["disciplina"] == ""
    assert a.tela_atual is None  # abrir_tela_home() não passa por _abrir_modulo()
    a.destroy()
    print("OK login bem-sucedido monta usuario_atual/sessao (nome vem do login) e segue para a Home")


def test_login_cancelado_nao_monta_estado_nem_abre_home():
    app_module.DialogLogin = _FakeDialogLoginCancelado

    a = AppCDE()
    assert a.usuario_atual is None
    assert not hasattr(a, "sessao")  # __init__ retornou antes de montar o resto do estado
    a.destroy()
    print("OK login cancelado não monta sessão nem abre a Home — main.py não chamaria mainloop()")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE INTEGRAÇÃO DE LOGIN PASSARAM")
