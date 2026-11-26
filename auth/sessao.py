"""Sessão persistente ("continuar conectado") — o usuário só volta a ver
a tela de login se clicar em **Sair**.

Como funciona:
- No login, gera um token aleatório. O computador guarda só
  `{nome_usuario, token}` em `sessao.json`, ao lado de `preferencias.json`
  (%APPDATA%\\CadariVizzo). A senha nunca é gravada.
- No banco de usuários (rede) fica apenas o **hash SHA-256** do token, na
  lista `sessoes` da conta — quem ler o banco não consegue reutilizá-lo.
- Ao abrir o app, se o token local bater com um hash válido da conta,
  entra direto.

A sessão deixa de valer quando: o usuário clica em Sair; a senha é
trocada ou resetada pelo administrador; a conta é desativada ou
excluída; a conta precisa trocar a senha; ou passam `DIAS_VALIDADE` dias
sem abrir o app (cada abertura renova o prazo).
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta

from ui import preferencias

DIAS_VALIDADE = 30
MAX_SESSOES_POR_USUARIO = 5  # ex.: notebook + desktop; a mais antiga sai
_FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


# ---------- arquivo local ----------
def _caminho_local():
    return os.path.join(os.path.dirname(preferencias._caminho()), "sessao.json")


def _ler_local():
    try:
        with open(_caminho_local(), encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict) and dados.get("nome_usuario") and dados.get("token"):
            return dados
    except (OSError, ValueError):
        pass
    return None


def _gravar_local(nome_usuario, token):
    try:
        os.makedirs(os.path.dirname(_caminho_local()), exist_ok=True)
        with open(_caminho_local(), "w", encoding="utf-8") as f:
            json.dump({"nome_usuario": nome_usuario, "token": token}, f)
    except OSError:
        pass  # sem sessão salva o app continua funcionando — só pede login de novo


def apagar_local():
    try:
        os.remove(_caminho_local())
    except OSError:
        pass


# ---------- tokens na conta ----------
def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _expirada(sessao, agora):
    try:
        ultimo = datetime.strptime(sessao.get("ultimo_uso", ""), _FORMATO_DATA)
    except ValueError:
        return True
    return agora - ultimo > timedelta(days=DIAS_VALIDADE)


def criar_sessao(usuario, agora=None):
    """Gera o token, registra o hash na conta (mutação in-place — quem
    chama salva o banco de usuários) e grava o token neste computador."""
    agora = agora or datetime.now()
    token = secrets.token_urlsafe(32)
    sessoes = [s for s in usuario.get("sessoes", []) if not _expirada(s, agora)]
    sessoes.append({"hash": _hash(token), "ultimo_uso": agora.strftime(_FORMATO_DATA)})
    usuario["sessoes"] = sessoes[-MAX_SESSOES_POR_USUARIO:]
    _gravar_local(usuario["nome_usuario"], token)
    return token


def restaurar_sessao(usuarios, agora=None):
    """Retorna o usuário da sessão salva neste computador, ou None se não
    houver sessão válida (nesse caso o arquivo local é apagado). Renova o
    prazo da sessão na conta — quem chama salva o banco de usuários."""
    agora = agora or datetime.now()
    local = _ler_local()
    if local is None:
        return None
    nome = local["nome_usuario"].lower()
    usuario = next((u for u in usuarios if u.get("nome_usuario", "").lower() == nome), None)
    if usuario is None or not usuario.get("ativo", True) or usuario.get("deve_trocar_senha"):
        apagar_local()
        return None
    hash_token = _hash(local["token"])
    sessao = next((s for s in usuario.get("sessoes", [])
                   if secrets.compare_digest(s.get("hash", ""), hash_token)), None)
    if sessao is None or _expirada(sessao, agora):
        apagar_local()
        return None
    sessao["ultimo_uso"] = agora.strftime(_FORMATO_DATA)
    return usuario


def encerrar_sessao(usuarios):
    """Logout: remove a sessão deste computador da conta (quem chama
    salva o banco) e apaga o arquivo local."""
    local = _ler_local()
    if local is not None:
        hash_token = _hash(local["token"])
        nome = local["nome_usuario"].lower()
        for u in usuarios:
            if u.get("nome_usuario", "").lower() == nome:
                u["sessoes"] = [s for s in u.get("sessoes", []) if s.get("hash") != hash_token]
    apagar_local()


def revogar_todas(usuario):
    """Derruba as sessões da conta em todos os computadores."""
    usuario["sessoes"] = []
