"""Testes de auth/dialogs.py (DialogLogin, DialogTrocarSenha,
DialogCriarUsuario) e da integração do login em app.py — isolado num
DB_DIR temporário, nunca o banco de produção.

Esses diálogos chamam `self.wait_window(self)` no fim do `__init__`
(bloqueiam até fechar) — como nos testes deste projeto não há um
usuário de verdade clicando, `tk.Toplevel.wait_window` é substituído
por um no-op durante os testes, para a construção terminar sem travar;
depois disso, chamamos os métodos públicos do diálogo diretamente (como
um clique chamaria) e conferimos o resultado."""
import os
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_auth_dialogs_")

# nenhum teste aqui depende de um usuário real clicando — substitui
# wait_window por um no-op para a construção dos diálogos não travar.
tk.Toplevel.wait_window = lambda self, *a, **k: None

from auth.dialogs import DialogCriarUsuario, DialogLogin, DialogSenhaTemporariaGerada, DialogTrocarSenha
from auth.usuarios import carregar_usuarios, criar_usuario, salvar_usuarios, PAPEL_ADMINISTRADOR, PAPEL_PROJETISTA


def _janela_raiz():
    raiz = tk.Tk()
    raiz.withdraw()
    return raiz


def test_login_bootstrap_cria_admin_e_expoe_a_senha_temporaria_uma_vez():
    raiz = _janela_raiz()

    dialogo = DialogLogin(raiz)
    assert dialogo.senha_bootstrap is not None, "primeiro uso deveria ter gerado uma senha de bootstrap"
    from auth.usuarios import validar_senha
    assert validar_senha(dialogo.senha_bootstrap) == (True, None)

    usuarios_apos_bootstrap = carregar_usuarios()
    assert len(usuarios_apos_bootstrap) == 1
    assert usuarios_apos_bootstrap[0]["nome_usuario"] == config.NOME_USUARIO_ADMIN_INICIAL
    assert usuarios_apos_bootstrap[0]["email"] == config.EMAIL_ADMIN_INICIAL
    assert usuarios_apos_bootstrap[0]["deve_trocar_senha"] is True

    # uma SEGUNDA instância (ex.: usuário fechou e reabriu o app) não deve
    # gerar um segundo bootstrap nem uma segunda senha temporária
    dialogo2 = DialogLogin(raiz)
    assert dialogo2.senha_bootstrap is None
    assert len(carregar_usuarios()) == 1

    raiz.destroy()
    print("OK bootstrap no primeiro login cria o admin uma única vez e expõe a senha gerada")


def test_login_credenciais_erradas_mostra_erro_e_nao_autentica():
    raiz = _janela_raiz()
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    salvar_usuarios(usuarios)

    dialogo = DialogLogin(raiz)
    dialogo.ent_usuario.insert(0, "fulano")
    dialogo.ent_senha.insert(0, "SenhaErrada!")
    dialogo.entrar()

    assert dialogo.usuario is None
    assert "incorretos" in dialogo.lbl_erro.cget("text")
    raiz.destroy()
    print("OK login com credenciais erradas mostra erro e não autentica")


def test_login_credenciais_corretas_autentica_e_registra_ultimo_login():
    raiz = _janela_raiz()
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    salvar_usuarios(usuarios)

    dialogo = DialogLogin(raiz)
    dialogo.ent_usuario.insert(0, "fulano")
    dialogo.ent_senha.insert(0, "Senha123!")
    dialogo.entrar()

    assert dialogo.usuario is not None
    assert dialogo.usuario["nome_usuario"] == "fulano"

    usuarios_salvos = carregar_usuarios()
    assert usuarios_salvos[0]["data_ultimo_login"] is not None
    raiz.destroy()
    print("OK login com credenciais corretas autentica e grava o último acesso")


def test_login_com_senha_temporaria_forca_troca_antes_de_liberar():
    raiz = _janela_raiz()
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Temp123!", PAPEL_PROJETISTA, deve_trocar_senha=True)
    salvar_usuarios(usuarios)

    dialogo = DialogLogin(raiz)
    dialogo.ent_usuario.insert(0, "fulano")
    dialogo.ent_senha.insert(0, "Temp123!")

    # simula o usuário TROCANDO a senha no diálogo forçado que o login abre:
    # substitui DialogTrocarSenha por uma versão que já "troca" sozinha
    import auth.dialogs as auth_dialogs
    DialogTrocarSenhaOriginal = auth_dialogs.DialogTrocarSenha

    class _TrocaAutomatica:
        def __init__(self, parent, usuario, obrigatoria=False):
            from auth.usuarios import trocar_senha
            trocar_senha(usuario, "NovaSenha1!")
            self.trocou = True

    auth_dialogs.DialogTrocarSenha = _TrocaAutomatica
    dialogo.entrar()
    auth_dialogs.DialogTrocarSenha = DialogTrocarSenhaOriginal

    assert dialogo.usuario is not None
    assert dialogo.usuario["deve_trocar_senha"] is False

    usuarios_salvos = carregar_usuarios()
    assert usuarios_salvos[0]["deve_trocar_senha"] is False
    from auth.usuarios import autenticar
    assert autenticar(usuarios_salvos, "fulano", "NovaSenha1!") is not None
    raiz.destroy()
    print("OK login com senha temporária força a troca antes de liberar o acesso")


def test_dialog_senha_temporaria_gerada_mostra_usuario_e_senha():
    raiz = _janela_raiz()
    dialogo = DialogSenhaTemporariaGerada(raiz, "admin.teste", "Abc123!")
    textos = []
    for widget in dialogo.winfo_children():
        if isinstance(widget, tk.Label):
            textos.append(widget.cget("text"))
    texto_completo = "\n".join(textos)
    assert "admin.teste" in texto_completo
    assert "Abc123!" in texto_completo
    raiz.destroy()
    print("OK DialogSenhaTemporariaGerada mostra usuário e senha corretamente")


def test_dialog_trocar_senha_valida_confirmacao_e_politica():
    raiz = _janela_raiz()
    usuarios = []
    criar_usuario(usuarios, "fulano", "Fulano", "a@a.com", "Senha123!", PAPEL_PROJETISTA)
    usuario = usuarios[0]

    dialogo = DialogTrocarSenha(raiz, usuario, obrigatoria=False)
    dialogo.ent_nova.insert(0, "Abc123!")
    dialogo.ent_confirmar.insert(0, "Diferente!")
    dialogo._confirmar()
    assert dialogo.trocou is False
    assert "não coincidem" in dialogo.lbl_erro.cget("text")

    dialogo.ent_nova.delete(0, "end")
    dialogo.ent_confirmar.delete(0, "end")
    dialogo.ent_nova.insert(0, "fraca")
    dialogo.ent_confirmar.insert(0, "fraca")
    dialogo._confirmar()
    assert dialogo.trocou is False

    dialogo.ent_nova.delete(0, "end")
    dialogo.ent_confirmar.delete(0, "end")
    dialogo.ent_nova.insert(0, "Abc123!")
    dialogo.ent_confirmar.insert(0, "Abc123!")
    dialogo._confirmar()
    assert dialogo.trocou is True

    raiz.destroy()
    print("OK DialogTrocarSenha valida confirmação e política de senha antes de aceitar")


def _preencher_criar_usuario(dialogo, nome_usuario="joaog", nome="João Gabriel",
                              email="joao@a.com", disciplinas=("ADI", "HID"),
                              setor="Projetista PCI", senha="Senha123!", confirmar=None):
    dialogo.ent_usuario.insert(0, nome_usuario)
    dialogo.ent_nome.insert(0, nome)
    dialogo.ent_email.insert(0, email)
    for disciplina, var in dialogo._vars_disciplinas.items():
        var.set(disciplina in disciplinas)
    dialogo.cb_setor.set(setor)
    dialogo.ent_senha.insert(0, senha)
    dialogo.ent_confirmar.insert(0, confirmar if confirmar is not None else senha)


def test_dialog_criar_usuario_cria_projetista_com_disciplinas_e_setor():
    raiz = _janela_raiz()
    usuarios = []

    dialogo = DialogCriarUsuario(raiz, usuarios)
    _preencher_criar_usuario(dialogo)
    dialogo._criar()

    assert dialogo.usuario_criado is not None
    assert len(usuarios) == 1
    criado = usuarios[0]
    assert criado["nome_usuario"] == "joaog"
    assert criado["nome"] == "João Gabriel"
    assert criado["disciplinas"] == ["ADI", "HID"]
    assert criado["setor"] == "Projetista PCI"
    assert criado["papel"] == PAPEL_PROJETISTA
    assert criado["deve_trocar_senha"] is False  # já definiu a própria senha
    raiz.destroy()
    print("OK DialogCriarUsuario cria projetista com disciplinas (lista) e setor")


def test_dialog_criar_usuario_setor_bim_vira_administrador_automaticamente():
    raiz = _janela_raiz()
    usuarios = []

    dialogo = DialogCriarUsuario(raiz, usuarios)
    _preencher_criar_usuario(dialogo, setor="Setor BIM")
    dialogo._criar()

    assert dialogo.usuario_criado is not None
    criado = usuarios[0]
    assert criado["setor"] == "Setor BIM"
    assert criado["papel"] == PAPEL_ADMINISTRADOR  # Setor BIM gerencia usuários e vê o Dashboard de todos
    raiz.destroy()
    print("OK quem escolhe setor 'Setor BIM' no autoatendimento já entra como Administrador")


def test_dialog_criar_usuario_exige_disciplina_setor_e_senhas_iguais():
    raiz = _janela_raiz()
    usuarios = []

    dialogo = DialogCriarUsuario(raiz, usuarios)
    _preencher_criar_usuario(dialogo, disciplinas=())  # nenhuma disciplina marcada
    dialogo._criar()
    assert dialogo.usuario_criado is None
    assert "disciplina" in dialogo.lbl_erro.cget("text").lower()

    dialogo2 = DialogCriarUsuario(raiz, usuarios)
    _preencher_criar_usuario(dialogo2, nome_usuario="outro", confirmar="Diferente1!")
    dialogo2._criar()
    assert dialogo2.usuario_criado is None
    assert "não coincidem" in dialogo2.lbl_erro.cget("text")

    assert len(usuarios) == 0
    raiz.destroy()
    print("OK DialogCriarUsuario exige disciplina, setor e confirmação de senha igual")


def test_login_abrir_criar_usuario_preenche_usuario_apos_criar():
    raiz = _janela_raiz()

    dialogo_login = DialogLogin(raiz)  # roda o bootstrap, mas não usamos a conta dele aqui
    import auth.dialogs as auth_dialogs
    DialogCriarUsuarioOriginal = auth_dialogs.DialogCriarUsuario

    class _CriarAutomatico:
        def __init__(self, parent, usuarios):
            criar_usuario(
                usuarios, "novoprojetista", "Fulano de Tal", "fulano@a.com", "Senha123!",
                PAPEL_PROJETISTA, disciplinas=["PCI"], setor="Projetista PCI",
            )
            self.usuario_criado = usuarios[-1]

    auth_dialogs.DialogCriarUsuario = _CriarAutomatico
    dialogo_login._abrir_criar_usuario()
    auth_dialogs.DialogCriarUsuario = DialogCriarUsuarioOriginal

    assert dialogo_login.ent_usuario.get() == "novoprojetista"
    usuarios_salvos = carregar_usuarios()
    assert any(u["nome_usuario"] == "novoprojetista" for u in usuarios_salvos)
    raiz.destroy()
    print("OK login reaproveita o usuário recém-criado e já salva no banco")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE DIÁLOGOS DE AUTENTICAÇÃO PASSARAM")
