"""Testes de auth/sessao.py — sessão persistente ("continuar conectado")."""
import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_sessao_")

from auth import sessao
from auth.usuarios import PAPEL_PROJETISTA, criar_usuario, resetar_para_senha_temporaria, trocar_senha


def _usuarios():
    usuarios = []
    criar_usuario(usuarios, "maria", "Maria", "maria@x.com", "Senha!1", PAPEL_PROJETISTA)
    return usuarios


def test_sem_sessao_salva_pede_login():
    assert sessao.restaurar_sessao(_usuarios()) is None


def test_login_salvo_entra_direto_e_nao_grava_senha():
    usuarios = _usuarios()
    token = sessao.criar_sessao(usuarios[0])
    assert sessao.restaurar_sessao(usuarios)["nome_usuario"] == "maria"
    assert token not in str(usuarios)  # na conta só fica o hash
    with open(sessao._caminho_local(), encoding="utf-8") as f:
        assert "Senha!1" not in f.read()


def test_sair_encerra_a_sessao():
    usuarios = _usuarios()
    sessao.criar_sessao(usuarios[0])
    sessao.encerrar_sessao(usuarios)
    assert usuarios[0]["sessoes"] == []
    assert sessao.restaurar_sessao(usuarios) is None


def test_troca_e_reset_de_senha_derrubam_a_sessao():
    usuarios = _usuarios()
    sessao.criar_sessao(usuarios[0])
    trocar_senha(usuarios[0], "Outra!2")
    assert sessao.restaurar_sessao(usuarios) is None

    sessao.criar_sessao(usuarios[0])
    resetar_para_senha_temporaria(usuarios[0])
    assert sessao.restaurar_sessao(usuarios) is None


def test_conta_desativada_nao_restaura():
    usuarios = _usuarios()
    sessao.criar_sessao(usuarios[0])
    usuarios[0]["ativo"] = False
    assert sessao.restaurar_sessao(usuarios) is None


def test_sessao_expira_sem_uso_e_renova_ao_abrir():
    usuarios = _usuarios()
    inicio = datetime(2026, 1, 1)
    sessao.criar_sessao(usuarios[0], agora=inicio)
    # aberto no dia 20: renova o prazo
    assert sessao.restaurar_sessao(usuarios, agora=inicio + timedelta(days=20)) is not None
    assert sessao.restaurar_sessao(usuarios, agora=inicio + timedelta(days=45)) is not None
    # 31 dias sem abrir: expira
    assert sessao.restaurar_sessao(usuarios, agora=inicio + timedelta(days=77)) is None
