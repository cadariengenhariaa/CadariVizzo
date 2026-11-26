"""Testes de banco_json.py — proteções do banco na rede."""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import banco_json
from auth.usuarios import bootstrap_admin_inicial


@pytest.fixture
def banco(monkeypatch):
    pasta = tempfile.mkdtemp(prefix="teste_cadari_banco_")
    monkeypatch.setattr(config, "DB_DIR", pasta)
    monkeypatch.setattr(config, "BACKUP_DIR", os.path.join(pasta, "backups"))
    return pasta


def test_pasta_inacessivel_nao_cria_banco_novo(monkeypatch, tmp_path):
    sumida = str(tmp_path / "rede_fora")
    monkeypatch.setattr(config, "DB_DIR", sumida)
    with pytest.raises(banco_json.BancoIndisponivel):
        banco_json.gravar(os.path.join(sumida, "db_usuarios.json"), [])
    assert not os.path.exists(sumida)
    with pytest.raises(banco_json.BancoIndisponivel):
        bootstrap_admin_inicial([])


def test_gravacao_atomica_e_backup(banco):
    caminho = os.path.join(banco, "db_issues.json")
    banco_json.gravar(caminho, [1])
    banco_json.gravar(caminho, [1, 2])
    assert banco_json.ler(caminho) == [1, 2]
    assert not os.path.exists(caminho + ".tmp")
    backups = os.listdir(config.BACKUP_DIR)
    assert len(backups) == 1  # o 2º save copiou a versão [1]
    with open(os.path.join(config.BACKUP_DIR, backups[0]), encoding="utf-8") as f:
        assert json.load(f) == [1]


def test_backup_respeita_intervalo(banco):
    caminho = os.path.join(banco, "db_issues.json")
    banco_json.gravar(caminho, [1])
    agora = datetime.now()
    assert banco_json.fazer_backup(caminho, agora) is not None
    assert banco_json.fazer_backup(caminho, agora + timedelta(minutes=1)) is None
    assert banco_json.fazer_backup(caminho, agora + timedelta(minutes=11)) is not None


def test_banco_de_usuarios_sumido_com_backup_nao_recria(banco):
    caminho = os.path.join(banco, "db_usuarios.json")
    banco_json.gravar(caminho, [{"nome_usuario": "bruno"}])
    banco_json.fazer_backup(caminho)
    os.remove(caminho)
    with pytest.raises(banco_json.BancoIndisponivel):
        bootstrap_admin_inicial([])


def test_primeiro_uso_de_verdade_cria_admin(banco):
    usuarios = []
    assert bootstrap_admin_inicial(usuarios)
    assert usuarios[0]["nome_usuario"] == config.NOME_USUARIO_ADMIN_INICIAL == "Bruno"
