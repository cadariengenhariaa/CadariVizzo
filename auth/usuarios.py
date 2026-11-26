"""Armazenamento e autenticação de usuários — login por nome de
usuário/senha, papéis de acesso e política de senha.

Segue o mesmo padrão de persistência JSON em `config.DB_DIR` já usado
pelo resto do projeto (`utils.py`, `clash/armazenamento.py`): caminho
resolvido em tempo de CHAMADA (via `config.DB_DIR`, não um valor
congelado no import), para um teste que sobrescreve `config.DB_DIR`
funcionar mesmo que este módulo já tenha sido importado antes por outro
teste na mesma sessão — a mesma pegadinha (e o mesmo conserto) já
documentados em `clash/armazenamento.py`.

Senhas NUNCA são guardadas em texto puro: PBKDF2-HMAC-SHA256 com salt
próprio por usuário (biblioteca padrão do Python, sem dependência
nova — adequado para um app desktop interno, não um serviço público)."""
import hashlib
import json
import os
import re
import secrets

import banco_json
import config
from utils import agora_str

PAPEL_PROJETISTA = "projetista"
PAPEL_COORDENADOR = "coordenador"
PAPEL_ADMINISTRADOR = "administrador"
PAPEIS_VALIDOS = (PAPEL_PROJETISTA, PAPEL_COORDENADOR, PAPEL_ADMINISTRADOR)

NOMES_PAPEIS = {
    PAPEL_PROJETISTA: "Projetista",
    PAPEL_COORDENADOR: "Coordenador",
    PAPEL_ADMINISTRADOR: "Administrador",
}

_ITERACOES_PBKDF2 = 200_000
_PADRAO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PADRAO_NOME_USUARIO = re.compile(r"^[A-Za-zÀ-ÿ0-9_.]{3,30}$")
_CARACTERES_ESPECIAIS = set("!@#$%^&*()-_=+[]{}|;:'\",.<>/?`~\\")


# ---------- persistência ----------
def _caminho_padrao():
    return os.path.join(config.DB_DIR, "db_usuarios.json")


def carregar_usuarios(caminho=None):
    return banco_json.ler(caminho or _caminho_padrao())


def listar_nomes_ativos():
    """Nomes completos distintos dos usuários ATIVOS cadastrados de
    verdade — usado para popular os combos de 'Criado por'/'Atribuído
    para' no lugar de uma lista fixa, já que o cadastro de usuários
    passou a ser a fonte de verdade de quem existe no sistema."""
    usuarios = carregar_usuarios()
    nomes = {u["nome"].strip() for u in usuarios if u.get("ativo", True) and (u.get("nome") or "").strip()}
    return sorted(nomes)


def salvar_usuarios(usuarios, caminho=None):
    banco_json.gravar(caminho or _caminho_padrao(), usuarios, indent=2)


# ---------- hashing de senha ----------
def _hash_senha(senha, salt=None):
    salt = salt or secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(salt), _ITERACOES_PBKDF2)
    return hash_bytes.hex(), salt


def _verificar_senha(senha, hash_salvo, salt):
    hash_calculado, _ = _hash_senha(senha, salt)
    return secrets.compare_digest(hash_calculado, hash_salvo)


# ---------- validação ----------
def email_valido(email):
    return bool(_PADRAO_EMAIL.match((email or "").strip()))


def nome_usuario_valido(nome_usuario):
    """3 a 30 caracteres, letras/números/_/. — sem espaços (é o login)."""
    return bool(_PADRAO_NOME_USUARIO.match((nome_usuario or "").strip()))


def validar_senha(senha):
    """Política: mínimo 6 caracteres, 1 maiúscula, 1 caractere especial.
    Retorna (True, None) se válida, (False, motivo) caso contrário."""
    if len(senha or "") < 6:
        return False, "A senha precisa ter pelo menos 6 caracteres."
    if not any(c.isupper() for c in senha):
        return False, "A senha precisa ter pelo menos 1 letra maiúscula."
    if not any(c in _CARACTERES_ESPECIAIS for c in senha):
        return False, "A senha precisa ter pelo menos 1 caractere especial (ex.: ! @ # $ %)."
    return True, None


def _gerar_senha_temporaria():
    """Senha aleatória que já atende à política de propósito (nunca por
    sorteio) — usada no reset do administrador e no bootstrap inicial."""
    letras_maiusculas = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # sem I/O, visualmente ambíguos
    letras_minusculas = letras_maiusculas.lower()
    digitos = "23456789"
    especiais = "!@#$%*"
    partes = [
        secrets.choice(letras_maiusculas),
        secrets.choice(letras_minusculas),
        secrets.choice(letras_minusculas),
        secrets.choice(digitos),
        secrets.choice(digitos),
        secrets.choice(especiais),
    ]
    secrets.SystemRandom().shuffle(partes)
    return "".join(partes)


# ---------- CRUD ----------
def buscar_usuario(usuarios, nome_usuario):
    nome_usuario = (nome_usuario or "").strip().lower()
    return next((u for u in usuarios if u["nome_usuario"].lower() == nome_usuario), None)


def buscar_usuario_por_email(usuarios, email):
    email = (email or "").strip().lower()
    return next((u for u in usuarios if u.get("email", "").lower() == email), None)


def excluir_usuario(usuarios, nome_usuario):
    """Remove o usuário da lista (mutação in-place) — quem chama ainda
    precisa salvar. Não mexe nas issues: `atribuido_para`/`criado_por`
    são apenas texto (nome completo), não uma referência à conta, então
    excluir a conta não deixa nada "quebrado" nas issues já existentes —
    use `utils.transferir_atribuicoes` antes de excluir se quiser passar
    o trabalho em aberto para outra pessoa."""
    usuario = buscar_usuario(usuarios, nome_usuario)
    if usuario is None:
        raise ValueError("Usuário não encontrado.")
    usuarios.remove(usuario)


def criar_usuario(usuarios, nome_usuario, nome, email, senha, papel,
                   disciplinas=None, setor=None, deve_trocar_senha=False):
    if not nome_usuario_valido(nome_usuario):
        raise ValueError("Nome de usuário inválido (3 a 30 caracteres, sem espaços).")
    if buscar_usuario(usuarios, nome_usuario) is not None:
        raise ValueError("Já existe um usuário com esse nome de usuário.")
    if not email_valido(email):
        raise ValueError("E-mail inválido.")
    if papel not in PAPEIS_VALIDOS:
        raise ValueError(f"Papel inválido: {papel}")
    ok, motivo = validar_senha(senha)
    if not ok:
        raise ValueError(motivo)

    hash_, salt = _hash_senha(senha)
    usuario = {
        "nome_usuario": nome_usuario.strip(),
        "nome": nome.strip(),
        "email": email.strip().lower(),
        "disciplinas": list(disciplinas or []),
        "setor": setor or "",
        "senha_hash": hash_,
        "senha_salt": salt,
        "papel": papel,
        "ativo": True,
        "deve_trocar_senha": deve_trocar_senha,
        "data_criacao": agora_str(),
        "data_ultimo_login": None,
    }
    usuarios.append(usuario)
    return usuario


def trocar_senha(usuario, senha_nova):
    ok, motivo = validar_senha(senha_nova)
    if not ok:
        raise ValueError(motivo)
    hash_, salt = _hash_senha(senha_nova)
    usuario["senha_hash"] = hash_
    usuario["senha_salt"] = salt
    usuario["deve_trocar_senha"] = False
    usuario["sessoes"] = []  # senha nova derruba as sessões salvas (auth/sessao.py)


def resetar_para_senha_temporaria(usuario):
    """Usado pelo Administrador (tela de gerenciamento de usuários) e
    pelo bootstrap do admin inicial. Retorna a senha em texto puro, só
    para ser mostrada uma única vez — nunca fica guardada."""
    senha_temporaria = _gerar_senha_temporaria()
    hash_, salt = _hash_senha(senha_temporaria)
    usuario["senha_hash"] = hash_
    usuario["senha_salt"] = salt
    usuario["deve_trocar_senha"] = True
    usuario["sessoes"] = []  # reset do admin desconecta a conta em todos os computadores
    return senha_temporaria


def autenticar(usuarios, nome_usuario, senha):
    """Retorna o dict do usuário se as credenciais baterem e a conta
    estiver ativa, ou None — sem diferenciar 'usuário não existe' de
    'senha errada' (quem chama mostra uma mensagem genérica), para não
    revelar quais contas estão cadastradas."""
    usuario = buscar_usuario(usuarios, nome_usuario)
    if usuario is None or not usuario.get("ativo", True):
        return None
    if not _verificar_senha(senha, usuario["senha_hash"], usuario["senha_salt"]):
        return None
    return usuario


def registrar_login(usuario):
    usuario["data_ultimo_login"] = agora_str()


def bootstrap_admin_inicial(usuarios):
    """Se `usuarios` estiver vazio (primeiro uso do app), cria a conta
    administradora inicial (config.NOME_USUARIO_ADMIN_INICIAL) com uma
    senha temporária gerada na hora. Retorna a senha gerada (para
    mostrar uma única vez), ou None se já havia usuários (nada a
    fazer). Muta a lista `usuarios` in-place — quem chama ainda precisa
    salvar."""
    if usuarios:
        return None
    # Proteção (incidente de 26/11/2026): lista vazia pode ser a pasta da
    # rede fora do ar ou o arquivo movido — nesses casos NÃO é 1º uso.
    banco_json.garantir_acesso()
    if banco_json.existe_backup("db_usuarios.json"):
        raise banco_json.BancoIndisponivel(
            "O banco de usuários (db_usuarios.json) não foi encontrado, mas existem "
            f"backups dele em:\n{config.BACKUP_DIR}\n\n"
            "Restaure o backup mais recente em vez de criar um banco novo.")
    senha_temporaria = _gerar_senha_temporaria()
    criar_usuario(
        usuarios, config.NOME_USUARIO_ADMIN_INICIAL, "Administrador",
        config.EMAIL_ADMIN_INICIAL, senha_temporaria, PAPEL_ADMINISTRADOR,
        deve_trocar_senha=True,
    )
    return senha_temporaria


# ---------- papéis ----------
def eh_administrador(usuario):
    return bool(usuario) and usuario.get("papel") == PAPEL_ADMINISTRADOR


def eh_coordenador_ou_administrador(usuario):
    return bool(usuario) and usuario.get("papel") in (PAPEL_COORDENADOR, PAPEL_ADMINISTRADOR)
