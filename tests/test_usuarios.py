"""Testes de auth/usuarios.py: hashing/senha, política de senha, CRUD,
autenticação, bootstrap do admin inicial e papéis — isolado num DB_DIR
temporário, nunca o banco de produção (mesma disciplina já seguida no
resto do projeto)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_usuarios_")

from auth.usuarios import (
    PAPEL_ADMINISTRADOR,
    PAPEL_COORDENADOR,
    PAPEL_PROJETISTA,
    autenticar,
    bootstrap_admin_inicial,
    buscar_usuario,
    carregar_usuarios,
    criar_usuario,
    eh_administrador,
    eh_coordenador_ou_administrador,
    email_valido,
    excluir_usuario,
    nome_usuario_valido,
    registrar_login,
    resetar_para_senha_temporaria,
    salvar_usuarios,
    trocar_senha,
    validar_senha,
)


def test_validar_senha_aplica_as_tres_regras():
    assert validar_senha("Abc1!") == (False, "A senha precisa ter pelo menos 6 caracteres.")
    assert validar_senha("abcdef!")[0] is False  # sem maiúscula
    assert validar_senha("Abcdef1")[0] is False  # sem caractere especial
    assert validar_senha("Abcdef!") == (True, None)
    print("OK política de senha: 6+ caracteres, 1 maiúscula, 1 especial")


def test_email_valido():
    assert email_valido("fulano@empresa.com.br")
    assert not email_valido("fulano@empresa")
    assert not email_valido("não é email")
    print("OK validação simples de e-mail")


def test_nome_usuario_valido():
    assert nome_usuario_valido("JoaoGabriel")
    assert nome_usuario_valido("joao.gabriel")
    assert not nome_usuario_valido("jo")  # curto demais
    assert not nome_usuario_valido("joao gabriel")  # espaço não permitido
    assert not nome_usuario_valido("")
    print("OK validação de nome de usuário (3-30 caracteres, sem espaços)")


def test_hash_de_senha_nunca_fica_em_texto_puro():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    usuario = usuarios[0]
    assert "Senha123!" not in usuario["senha_hash"]
    assert usuario["senha_hash"] != "Senha123!"
    assert usuario["senha_salt"]
    print("OK senha nunca armazenada em texto puro, salt gerado por usuário")


def test_autenticar_aceita_credenciais_corretas_e_rejeita_erradas():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)

    assert autenticar(usuarios, "fulano", "Senha123!") is not None
    assert autenticar(usuarios, "fulano", "SenhaErrada!") is None
    assert autenticar(usuarios, "naoexiste", "Senha123!") is None
    assert autenticar(usuarios, "FULANO", "Senha123!") is not None  # usuário case-insensitive
    print("OK autenticação aceita credenciais corretas e rejeita erradas")


def test_conta_desativada_nao_autentica():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    usuarios[0]["ativo"] = False
    assert autenticar(usuarios, "fulano", "Senha123!") is None
    print("OK conta desativada não autentica mesmo com senha certa")


def test_criar_usuario_rejeita_usuario_duplicado_email_invalido_ou_senha_fraca():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)

    try:
        criar_usuario(usuarios, "fulano", "Outro", "b@b.com", "Senha123!", PAPEL_PROJETISTA)
        assert False, "deveria ter rejeitado nome de usuário duplicado"
    except ValueError:
        pass

    try:
        criar_usuario(usuarios, "outro", "X", "invalido", "Senha123!", PAPEL_PROJETISTA)
        assert False, "deveria ter rejeitado e-mail inválido"
    except ValueError:
        pass

    try:
        criar_usuario(usuarios, "outro2", "X", "b@b.com", "fraca", PAPEL_PROJETISTA)
        assert False, "deveria ter rejeitado senha fora da política"
    except ValueError:
        pass

    assert len(usuarios) == 1
    print("OK criar_usuario rejeita usuário duplicado, e-mail inválido e senha fora da política")


def test_criar_usuario_aceita_disciplinas_e_setor():
    usuarios = []
    criar_usuario(
        usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA,
        disciplinas=["ADI", "HID"], setor="Setor BIM",
    )
    usuario = usuarios[0]
    assert usuario["disciplinas"] == ["ADI", "HID"]
    assert usuario["setor"] == "Setor BIM"
    print("OK criar_usuario grava disciplinas (lista) e setor")


def test_trocar_senha_funciona_e_desliga_a_flag_de_troca_obrigatoria():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA, deve_trocar_senha=True)
    usuario = usuarios[0]
    assert usuario["deve_trocar_senha"] is True

    trocar_senha(usuario, "NovaSenha1!")
    assert usuario["deve_trocar_senha"] is False
    assert autenticar(usuarios, "fulano", "NovaSenha1!") is not None
    assert autenticar(usuarios, "fulano", "Senha123!") is None
    print("OK trocar_senha atualiza o hash e desliga deve_trocar_senha")


def test_resetar_para_senha_temporaria_liga_flag_e_senha_atende_a_politica():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    usuario = usuarios[0]

    senha_temp = resetar_para_senha_temporaria(usuario)
    assert usuario["deve_trocar_senha"] is True
    assert validar_senha(senha_temp) == (True, None)
    assert autenticar(usuarios, "fulano", senha_temp) is not None
    assert autenticar(usuarios, "fulano", "Senha123!") is None
    print("OK reset gera senha temporária válida e liga a flag de troca obrigatória")


def test_bootstrap_admin_inicial_so_roda_uma_vez():
    usuarios = []
    senha = bootstrap_admin_inicial(usuarios)
    assert senha is not None
    assert len(usuarios) == 1
    assert usuarios[0]["papel"] == PAPEL_ADMINISTRADOR
    assert usuarios[0]["nome_usuario"] == config.NOME_USUARIO_ADMIN_INICIAL
    assert usuarios[0]["email"] == config.EMAIL_ADMIN_INICIAL
    assert usuarios[0]["deve_trocar_senha"] is True
    assert eh_administrador(usuarios[0])

    # banco já tem usuário -> bootstrap não faz nada de novo
    resultado2 = bootstrap_admin_inicial(usuarios)
    assert resultado2 is None
    assert len(usuarios) == 1
    print("OK bootstrap cria o admin inicial uma única vez")


def test_papeis_coordenador_e_administrador():
    usuarios = []
    criar_usuario(usuarios, "projetista", "Projetista", "p@a.com", "Senha123!", PAPEL_PROJETISTA)
    criar_usuario(usuarios, "coordenador", "Coordenador", "c@a.com", "Senha123!", PAPEL_COORDENADOR)
    criar_usuario(usuarios, "admin", "Admin", "adm@a.com", "Senha123!", PAPEL_ADMINISTRADOR)

    projetista = buscar_usuario(usuarios, "projetista")
    coordenador = buscar_usuario(usuarios, "coordenador")
    administrador = buscar_usuario(usuarios, "admin")

    assert not eh_administrador(projetista) and not eh_coordenador_ou_administrador(projetista)
    assert not eh_administrador(coordenador) and eh_coordenador_ou_administrador(coordenador)
    assert eh_administrador(administrador) and eh_coordenador_ou_administrador(administrador)
    print("OK checagem de papéis (projetista/coordenador/administrador)")


def test_registrar_login_atualiza_data_ultimo_login():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    usuario = usuarios[0]
    assert usuario["data_ultimo_login"] is None
    registrar_login(usuario)
    assert usuario["data_ultimo_login"] is not None
    print("OK registrar_login grava a data/hora do último acesso")


def test_persistencia_salvar_e_carregar_usuarios_isolada_do_banco_real():
    # proteção: checa a propriedade (dentro do temp do sistema), não um
    # prefixo deste arquivo — vários arquivos de teste reatribuem
    # config.DB_DIR no nível de módulo e o pytest os importa todos antes
    # de rodar qualquer teste, então outro arquivo pode "vencer" essa
    # reatribuição para o resto da sessão (ver mesma nota em
    # test_rastreamento.py e test_app_login_integration.py).
    assert config.DB_DIR.startswith(tempfile.gettempdir()), "proteção: este teste não pode rodar contra o DB_DIR real"

    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    salvar_usuarios(usuarios)

    recarregados = carregar_usuarios()
    assert len(recarregados) == 1
    assert recarregados[0]["nome_usuario"] == "fulano"
    assert autenticar(recarregados, "fulano", "Senha123!") is not None
    print("OK salvar/carregar usuários do disco, isolado do banco de produção")


def test_excluir_usuario_remove_da_lista():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    criar_usuario(usuarios, "ciclano", "Ciclano", "b@b.com", "Senha123!", PAPEL_PROJETISTA)
    assert len(usuarios) == 2

    excluir_usuario(usuarios, "fulano")
    assert len(usuarios) == 1
    assert buscar_usuario(usuarios, "fulano") is None
    assert buscar_usuario(usuarios, "ciclano") is not None
    print("OK excluir_usuario remove só o usuário indicado")


def test_excluir_usuario_inexistente_da_erro():
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    try:
        excluir_usuario(usuarios, "naoexiste")
        assert False, "deveria ter levantado ValueError"
    except ValueError:
        pass
    assert len(usuarios) == 1
    print("OK excluir_usuario de quem não existe levanta ValueError sem mexer na lista")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE USUÁRIOS PASSARAM")
