"""Diálogos de autenticação: login (obrigatório para abrir o app), troca
de senha (obrigatória após reset, ou voluntária) e a exibição única da
senha temporária gerada no bootstrap do administrador inicial."""
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from auth import visual_login
from ui import preferencias

from auth.usuarios import (
    autenticar,
    bootstrap_admin_inicial,
    carregar_usuarios,
    criar_usuario,
    registrar_login,
    salvar_usuarios,
    trocar_senha,
    PAPEL_ADMINISTRADOR,
    PAPEL_PROJETISTA,
)
from config import (
    LISTA_DISCIPLINAS, LISTA_SETORES, LOGO_CADARI_BRANCO, LOGO_VIZZO_LOGIN,
    NOME_USUARIO_ADMIN_INICIAL, SETOR_BIM, TEMA,
)


class DialogSenhaTemporariaGerada(tk.Toplevel):
    """Mostrada uma única vez, logo após o bootstrap criar a conta
    administradora inicial — a senha não fica guardada em lugar nenhum
    depois disso, então precisa ser anotada agora."""

    def __init__(self, parent, nome_usuario, senha_temporaria):
        super().__init__(parent, bg=TEMA["surface"])
        self.title("Conta de administrador criada")
        self.geometry("440x240")
        self.resizable(False, False)

        tk.Label(self, text="Primeiro uso do Cadari Vizzo", font=("Arial", 11, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"]).pack(pady=(15, 5))
        tk.Label(
            self,
            text=(
                f"Uma conta de administrador foi criada automaticamente:\n\n"
                f"Usuário: {nome_usuario}\n"
                f"Senha temporária: {senha_temporaria}\n\n"
                "Anote essa senha agora — ela só aparece esta vez.\n"
                "Você será obrigado a trocá-la ao entrar."
            ),
            bg=TEMA["surface"], fg=TEMA["texto"], justify="left", wraplength=400,
        ).pack(padx=15, pady=5)

        tk.Button(self, text="✔ Entendi", command=self.destroy, bg=TEMA["acento"],
                  fg=TEMA["acento_texto"], font=("Arial", 9, "bold")).pack(pady=15)

        self.transient(parent)
        self.grab_set()
        self.wait_window(self)


class DialogTrocarSenha(tk.Toplevel):
    """`obrigatoria=True`: logo após login com senha temporária — sem
    botão cancelar e sem fechar pelo X. `obrigatoria=False`: troca
    voluntária, acionável de qualquer tela a qualquer momento."""

    def __init__(self, parent, usuario, obrigatoria=False):
        super().__init__(parent, bg=TEMA["surface"])
        self.usuario = usuario
        self.trocou = False
        self.title("Trocar senha")
        self.geometry("380x280")
        self.resizable(False, False)

        titulo = "Defina uma nova senha para continuar" if obrigatoria else "Trocar senha"
        tk.Label(self, text=titulo, font=("Arial", 11, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"], wraplength=340, justify="center"
                 ).pack(pady=(15, 5))
        tk.Label(self, text="Mínimo 6 caracteres, com 1 maiúscula e 1 caractere especial.",
                 bg=TEMA["surface"], fg=TEMA["texto_fraco"], font=("Arial", 8),
                 wraplength=320, justify="center").pack(pady=(0, 10))

        form = tk.Frame(self, bg=TEMA["surface"])
        form.pack()
        tk.Label(form, text="Nova senha:", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_nova = ttk.Entry(form, width=24, show="•")
        self.ent_nova.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(form, text="Confirmar:", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=1, column=0, padx=5, pady=5, sticky="e")
        self.ent_confirmar = ttk.Entry(form, width=24, show="•")
        self.ent_confirmar.grid(row=1, column=1, padx=5, pady=5)
        self.ent_confirmar.bind("<Return>", lambda e: self._confirmar())

        self.lbl_erro = tk.Label(self, text="", bg=TEMA["surface"], fg=TEMA["critico"],
                                  font=("Arial", 8), wraplength=340, justify="center")
        self.lbl_erro.pack(pady=8)

        botoes = tk.Frame(self, bg=TEMA["surface"])
        botoes.pack(pady=5)
        tk.Button(botoes, text="✔ Confirmar", command=self._confirmar, bg=TEMA["acento"],
                  fg=TEMA["acento_texto"], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        if not obrigatoria:
            tk.Button(botoes, text="Cancelar", command=self.destroy, bg=TEMA["surface_alt"],
                      fg=TEMA["texto"]).pack(side=tk.LEFT, padx=5)
        else:
            self.protocol("WM_DELETE_WINDOW", lambda: None)  # não deixa fechar sem trocar a senha

        self.ent_nova.focus_set()
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def _confirmar(self):
        nova = self.ent_nova.get()
        confirmar = self.ent_confirmar.get()
        if nova != confirmar:
            self.lbl_erro.config(text="As senhas não coincidem.")
            return
        try:
            trocar_senha(self.usuario, nova)
        except ValueError as e:
            self.lbl_erro.config(text=str(e))
            return
        self.trocou = True
        self.destroy()


COR_ERRO_LOGIN = "#ff9e9e"
COR_SUCESSO_LOGIN = "#9be7b0"
_FONTE = "Segoe UI"
_FONTE_SEMI = "Segoe UI Semibold"
_FONTE_ICONE = "Segoe MDL2 Assets"
PLACEHOLDER_SETOR = "Selecione o setor"


class _TextoCanvas:
    """Imita a interface mínima de um tk.Label (`config`/`cget`) para um
    texto desenhado direto no Canvas — no cartão translúcido um Label
    teria fundo opaco. Mantém `lbl_erro.cget("text")` funcionando para
    quem já usava o Label."""

    def __init__(self, canvas):
        self.canvas = canvas
        self.item = None
        self._texto = ""
        self._fg = COR_ERRO_LOGIN

    def config(self, text=None, fg=None, **_):
        if text is not None:
            self._texto = text
        if fg is not None:
            self._fg = fg
        if self.item is not None:
            self.canvas.itemconfig(self.item, text=self._texto, fill=self._fg)

    configure = config

    def cget(self, chave):
        return self._texto if chave == "text" else self._fg


def _entrada_branca(master, **kw):
    return tk.Entry(master, relief="flat", bd=0, bg="white", fg="#1d2b36", font=(_FONTE, 11),
                    insertbackground="#1d2b36", highlightthickness=0, **kw)


class _TelaVidro(tk.Toplevel):
    """Base das telas cheias com fundo da marca e cartão de vidro (login
    e criar usuário). A parte estática (fundo, cartão, logos, molduras
    dos campos) é uma imagem PIL redesenhada quando a janela muda de
    tamanho; textos, campos e botões ficam por cima, no Canvas.

    Subclasses definem `LARGURA_CARTAO`/`ALTURA_CARTAO` e implementam
    `_desenhar_estatico(fundo, x0, y0)` e `_desenhar_dinamico(x0, y0)`."""

    LARGURA_CARTAO = visual_login.CARTAO_LARGURA
    ALTURA_CARTAO = visual_login.CARTAO_ALTURA
    TOM_CARTAO = (150, 185, 200)
    OPACIDADE_CARTAO = 0.16
    RAIO_CARTAO = visual_login.CARTAO_RAIO

    def _iniciar_vidro(self, titulo):
        self.title(titulo)
        largura_tela, altura_tela = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1280, largura_tela)}x{min(800, altura_tela)}")
        self.minsize(self.LARGURA_CARTAO + 40, self.ALTURA_CARTAO + 40)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg="#09263a")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self._imagens = {}
        self._tamanho_renderizado = None
        self._agendado = None
        return largura_tela, altura_tela

    def _ativar_redimensionamento(self, largura_inicial, altura_inicial):
        self._montar_visual(largura_inicial, altura_inicial)
        self.canvas.bind("<Configure>", self._ao_redimensionar)

    def _ao_redimensionar(self, evento):
        if (evento.width, evento.height) == self._tamanho_renderizado:
            return
        if self._agendado is not None:
            self.after_cancel(self._agendado)
        self._agendado = self.after(
            60, lambda: self._montar_visual(evento.width, evento.height))

    def _montar_visual(self, largura, altura):
        self._agendado = None
        self._tamanho_renderizado = (largura, altura)
        largura = max(largura, self.LARGURA_CARTAO + 40)
        altura = max(altura, self.ALTURA_CARTAO + 20)
        self.canvas.delete("all")

        lc, ac = self.LARGURA_CARTAO, self.ALTURA_CARTAO
        x0 = (largura - lc) // 2
        y0 = max(10, (altura - ac) // 2)

        fundo = visual_login.renderizar_fundo(largura, altura)
        visual_login.aplicar_cartao_vidro(fundo, x0, y0, lc, ac, raio=self.RAIO_CARTAO,
                                          tom=self.TOM_CARTAO, opacidade=self.OPACIDADE_CARTAO)
        marca = visual_login.carregar_logo(LOGO_CADARI_BRANCO, 210, 64)
        if marca is not None:
            xm = largura - marca.width - 44
            ym = altura - marca.height - 36
            # só desenha se não ficar por baixo do cartão (janela pequena)
            if xm > x0 + lc or ym > y0 + ac:
                fundo.paste(marca, (xm, ym), marca)
        self._desenhar_estatico(fundo, x0, y0)

        self._imagens["fundo"] = ImageTk.PhotoImage(fundo, master=self)
        self.canvas.create_image(0, 0, image=self._imagens["fundo"], anchor="nw")
        self._desenhar_dinamico(x0, y0)

    def _criar_botao(self, chave, texto, cx, cy, largura, altura, cor, cor_hover,
                     cor_texto, fonte, comando, borda=None):
        normal = ImageTk.PhotoImage(
            visual_login.imagem_botao(largura, altura, 9, cor, borda), master=self)
        hover = ImageTk.PhotoImage(
            visual_login.imagem_botao(largura, altura, 9, cor_hover, borda), master=self)
        self._imagens[chave] = (normal, hover)
        tag = f"btn_{chave}"
        item = self.canvas.create_image(cx, cy, image=normal, tags=(tag,))
        self.canvas.create_text(cx, cy, text=texto, fill=cor_texto, font=fonte, tags=(tag,))

        def _ao_entrar(_):
            self.canvas.itemconfig(item, image=hover)
            self.canvas.config(cursor="hand2")

        def _ao_sair(_):
            self.canvas.itemconfig(item, image=normal)
            self.canvas.config(cursor="")

        self.canvas.tag_bind(tag, "<Enter>", _ao_entrar)
        self.canvas.tag_bind(tag, "<Leave>", _ao_sair)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", lambda e: comando())


class DialogLogin(_TelaVidro):
    """Login modal e bloqueante, mostrado antes de qualquer outra tela
    do app. Se o usuário fechar sem autenticar, `self.usuario` fica
    None — quem chama (app.py) deve encerrar o app nesse caso.

    Visual reproduzindo o protótipo do Figma: tela cheia, fundo azul
    escuro, cartão de vidro centralizado com o logo Vizzo, campos
    brancos arredondados e botões "Entrar"/"Criar Usuário"; marca
    Cadari no canto inferior direito."""

    LARGURA_CARTAO = 430
    ALTURA_CARTAO = 552

    def __init__(self, parent):
        super().__init__(parent, bg="#09263a")
        largura_tela, altura_tela = self._iniciar_vidro("Entrar — Cadari Vizzo")
        self.usuario = None

        self.usuarios = carregar_usuarios()
        # exposto como atributo (não só usado localmente) para quem
        # instanciar o diálogo poder confirmar se o bootstrap rodou,
        # sem depender do momento em que o after() abaixo dispara.
        self.senha_bootstrap = bootstrap_admin_inicial(self.usuarios)
        if self.senha_bootstrap:
            salvar_usuarios(self.usuarios)

        self.ent_usuario = _entrada_branca(self.canvas)
        self.ent_senha = _entrada_branca(self.canvas, show="•")
        self.ent_usuario.bind("<Return>", lambda e: self.ent_senha.focus_set())
        self.ent_senha.bind("<Return>", lambda e: self.entrar())

        self._senha_visivel = False
        self._img_olho = ImageTk.PhotoImage(visual_login.imagem_olho(20), master=self)
        self._img_olho_riscado = ImageTk.PhotoImage(
            visual_login.imagem_olho(20, riscado=True), master=self)
        self.btn_olho = tk.Label(self.canvas, image=self._img_olho, bg="white",
                                 cursor="hand2", bd=0)
        self.btn_olho.bind("<Button-1>", lambda e: self._alternar_senha_visivel())

        self.lbl_erro = _TextoCanvas(self.canvas)
        # "Lembrar usuário": guarda só o nome de usuário neste computador
        # (preferencias.json), nunca a senha
        prefs = preferencias.carregar()
        self.lembrar = tk.BooleanVar(master=self, value=bool(prefs.get("lembrar_usuario", True)))
        self.lembrar.trace_add("write", lambda *_: self._desenhar_lembrar())
        if self.lembrar.get() and prefs.get("ultimo_usuario"):
            self.ent_usuario.insert(0, prefs["ultimo_usuario"])
        self._ativar_redimensionamento(largura_tela, altura_tela)

        (self.ent_senha if self.ent_usuario.get() else self.ent_usuario).focus_set()
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        if self.senha_bootstrap:
            self.after(150, lambda: DialogSenhaTemporariaGerada(
                self, NOME_USUARIO_ADMIN_INICIAL, self.senha_bootstrap))

        # Sem self.transient(parent) de propósito: o parent (janela
        # principal) ainda está withdraw()n neste ponto (login acontece
        # antes de qualquer outra tela), e tornar este diálogo transient
        # a um dono invisível faz o Tk/Windows nunca mapear esta janela
        # na tela — ela existe no processo (grab_set funciona sem erro),
        # mas fica invisível para o usuário.
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window(self)

    # ---------- visual ----------
    _MARGEM = 40
    _ALTURA_CAMPO = 40
    _Y_USUARIO = 200
    _Y_SENHA = 283

    def _desenhar_estatico(self, fundo, x0, y0):
        lc = self.LARGURA_CARTAO
        logo = visual_login.carregar_logo(LOGO_VIZZO_LOGIN, 230, 74)
        if logo is not None:
            fundo.paste(logo, (x0 + (lc - logo.width) // 2, y0 + 30), logo)
        largura_campo = lc - 2 * self._MARGEM
        for y_campo in (self._Y_USUARIO, self._Y_SENHA):
            visual_login.colar_retangulo(fundo, x0 + self._MARGEM, y0 + y_campo, largura_campo,
                                         self._ALTURA_CAMPO, 9, (255, 255, 255))

    def _desenhar_dinamico(self, x0, y0):
        c = self.canvas
        lc = self.LARGURA_CARTAO
        margem, altura_campo = self._MARGEM, self._ALTURA_CAMPO
        largura_campo = lc - 2 * margem
        y_usuario, y_senha = y0 + self._Y_USUARIO, y0 + self._Y_SENHA

        branco = "#ffffff"
        c.create_text(x0 + margem, y0 + 140, text="Login", anchor="w", fill=branco,
                      font=(_FONTE, 20, "bold"))
        c.create_text(x0 + margem, y0 + 186, text="Usuário", anchor="w", fill=branco,
                      font=(_FONTE, 11))
        c.create_text(x0 + margem, y0 + 269, text="Senha", anchor="w", fill=branco,
                      font=(_FONTE, 11))

        c.create_window(x0 + margem + 12, y_usuario + altura_campo // 2,
                        window=self.ent_usuario, anchor="w",
                        width=largura_campo - 24, height=altura_campo - 12)
        c.create_window(x0 + margem + 12, y_senha + altura_campo // 2,
                        window=self.ent_senha, anchor="w",
                        width=largura_campo - 56, height=altura_campo - 12)
        c.create_window(x0 + margem + largura_campo - 12, y_senha + altura_campo // 2,
                        window=self.btn_olho, anchor="e")

        self._pos_lembrar = (x0 + margem, y0 + 344)
        c.create_text(x0 + margem + 24, y0 + 344, text="Lembrar usuário", anchor="w", fill=branco,
                      font=(_FONTE, 10), tags=("lembrar",))
        c.tag_bind("lembrar", "<Button-1>", lambda e: self.lembrar.set(not self.lembrar.get()))
        c.tag_bind("lembrar", "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind("lembrar", "<Leave>", lambda e: c.config(cursor=""))
        self._desenhar_lembrar()

        c.create_text(x0 + lc // 2, y0 + 374,
                      text="Esqueceu a senha? Entre em contato com um administrador.",
                      fill=branco, font=(_FONTE, 9), anchor="center")
        self.lbl_erro.item = c.create_text(
            x0 + lc // 2, y0 + 398, text=self.lbl_erro.cget("text"),
            fill=self.lbl_erro.cget("fg"), font=(_FONTE, 9), anchor="center",
            width=largura_campo, justify="center")

        self._criar_botao("entrar", "Entrar", x0 + lc // 2, y0 + 442, 190, 40,
                          cor=(236, 236, 232, 255), cor_hover=(255, 255, 255, 255),
                          cor_texto="#13303f", fonte=(_FONTE, 11, "bold"),
                          comando=self.entrar)
        self._criar_botao("criar", "Criar Usuário", x0 + lc // 2, y0 + 496, 190, 40,
                          cor=(10, 40, 56, 255), cor_hover=(24, 64, 84, 255),
                          cor_texto="#ffffff", fonte=(_FONTE, 11),
                          comando=self._abrir_criar_usuario, borda=(205, 215, 220, 255))

    def _desenhar_lembrar(self):
        if not hasattr(self, "_pos_lembrar"):
            return
        c = self.canvas
        c.delete("lembrar_caixa")
        x, y = self._pos_lembrar
        c.create_rectangle(x, y - 8, x + 16, y + 8, fill="white", outline="white", tags=("lembrar", "lembrar_caixa"))
        if self.lembrar.get():
            c.create_text(x + 8, y, text="\ue73e", font=(_FONTE_ICONE, 8), fill="#13303f",
                          tags=("lembrar", "lembrar_caixa"))

    def _alternar_senha_visivel(self):
        self._senha_visivel = not self._senha_visivel
        self.ent_senha.config(show="" if self._senha_visivel else "•")
        self.btn_olho.config(
            image=self._img_olho_riscado if self._senha_visivel else self._img_olho)

    def _cancelar(self):
        self.usuario = None
        self.destroy()

    def _abrir_criar_usuario(self):
        dialogo = DialogCriarUsuario(self, self.usuarios)
        if dialogo.usuario_criado is not None:
            salvar_usuarios(self.usuarios)
            self.ent_usuario.delete(0, "end")
            self.ent_usuario.insert(0, dialogo.usuario_criado["nome_usuario"])
            self.ent_senha.delete(0, "end")
            self.ent_senha.focus_set()
            self.lbl_erro.config(fg=COR_SUCESSO_LOGIN, text="Usuário criado! Faça login com a senha que você definiu.")

    def entrar(self):
        nome_usuario = self.ent_usuario.get().strip()
        senha = self.ent_senha.get()
        usuario = autenticar(self.usuarios, nome_usuario, senha)
        if usuario is None:
            self.lbl_erro.config(fg=COR_ERRO_LOGIN, text="Usuário ou senha incorretos, ou conta desativada.")
            return

        if usuario.get("deve_trocar_senha"):
            dialogo_troca = DialogTrocarSenha(self, usuario, obrigatoria=True)
            if not dialogo_troca.trocou:
                self.lbl_erro.config(fg=COR_ERRO_LOGIN, text="É preciso trocar a senha para continuar.")
                return

        registrar_login(usuario)
        salvar_usuarios(self.usuarios)
        preferencias.salvar(lembrar_usuario=self.lembrar.get(),
                            ultimo_usuario=usuario["nome_usuario"] if self.lembrar.get() else "")
        self.usuario = usuario
        self.destroy()


class DialogCriarUsuario(_TelaVidro):
    """Cadastro de conta (protótipo Figma: "ADMINISTRAÇÃO / Criar
    usuário") — tela cheia com o cartão azul de vidro: nome de usuário,
    nome completo, e-mail, disciplina(s) em "chips" marcáveis, setor e
    senha. Aberto pela tela de login (autoatendimento) e pelo painel
    "Gerenciar usuários". Setor BIM entra como Administrador; os demais
    como Projetista (papéis mais altos só via painel do Administrador)."""

    LARGURA_CARTAO = 760
    ALTURA_CARTAO = 664
    TOM_CARTAO = (16, 72, 92)
    OPACIDADE_CARTAO = 0.82
    RAIO_CARTAO = 14

    _M = 28           # margem interna do cartão
    _H = 40           # altura dos campos
    _GAP = 16         # espaço entre colunas
    # topo (y) de cada linha de campos, relativo ao cartão
    _Y = {"linha1": 178, "email": 260, "disciplinas": 342, "setor": 423, "senhas": 505, "botoes": 596}

    def __init__(self, parent, usuarios):
        super().__init__(parent, bg="#09263a")
        largura_tela, altura_tela = self._iniciar_vidro("Criar usuário — Cadari Vizzo")
        self.usuarios = usuarios
        self.usuario_criado = None

        c = self.canvas
        self.ent_usuario = _entrada_branca(c)
        self.ent_nome = _entrada_branca(c)
        self.ent_email = _entrada_branca(c)
        self.ent_senha = _entrada_branca(c, show="•")
        self.ent_confirmar = _entrada_branca(c, show="•")
        self.ent_confirmar.bind("<Return>", lambda e: self._criar())

        estilo = ttk.Style(self)
        estilo.layout("Vidro.TCombobox", [
            ("Combobox.padding", {"expand": "1", "sticky": "nswe", "children": [
                ("Combobox.textarea", {"sticky": "nswe"})]})])
        estilo.configure("Vidro.TCombobox", fieldbackground="white", background="white",
                         foreground="#1d2b36", borderwidth=0, padding=0,
                         selectbackground="white", selectforeground="#1d2b36")
        estilo.map("Vidro.TCombobox", fieldbackground=[("readonly", "white")],
                   selectbackground=[("readonly", "white")], selectforeground=[("readonly", "#1d2b36")])
        self.cb_setor = ttk.Combobox(c, values=LISTA_SETORES, state="readonly", style="Vidro.TCombobox",
                                     font=(_FONTE, 11))
        self.cb_setor.set(PLACEHOLDER_SETOR)

        self._vars_disciplinas = {}
        for disciplina in LISTA_DISCIPLINAS:
            var = tk.BooleanVar(master=self, value=False)
            var.trace_add("write", lambda *_a, d=disciplina: self._desenhar_chip(d))
            self._vars_disciplinas[disciplina] = var

        self.lbl_erro = _TextoCanvas(c)
        self._ativar_redimensionamento(largura_tela, altura_tela)

        self.bind("<Escape>", lambda e: self.destroy())
        self.ent_usuario.focus_set()
        if parent.winfo_viewable():  # transient a janela invisível não aparece (ver DialogLogin)
            self.transient(parent)
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window(self)

    # ---------- geometria ----------
    def _largura_util(self):
        return self.LARGURA_CARTAO - 2 * self._M

    def _largura_coluna(self):
        return (self._largura_util() - self._GAP) // 2

    def _caixas_campos(self, x0, y0):
        """{chave: (x, y, largura)} das molduras brancas dos campos."""
        m, util, col = self._M, self._largura_util(), self._largura_coluna()
        y = self._Y
        return {
            "usuario": (x0 + m, y0 + y["linha1"], col),
            "nome": (x0 + m + col + self._GAP, y0 + y["linha1"], col),
            "email": (x0 + m, y0 + y["email"], util),
            "setor": (x0 + m, y0 + y["setor"], util),
            "senha": (x0 + m, y0 + y["senhas"], col),
            "confirmar": (x0 + m + col + self._GAP, y0 + y["senhas"], col),
        }

    def _caixas_chips(self, x0, y0):
        n = len(LISTA_DISCIPLINAS)
        gap = 8
        largura = (self._largura_util() - gap * (n - 1)) // n
        return {d: (x0 + self._M + k * (largura + gap), y0 + self._Y["disciplinas"], largura)
                for k, d in enumerate(LISTA_DISCIPLINAS)}

    # ---------- desenho ----------
    def _desenhar_estatico(self, fundo, x0, y0):
        logo = visual_login.carregar_logo(LOGO_VIZZO_LOGIN, 150, 60)
        if logo is not None:
            fundo.paste(logo, (x0 + self._M, y0 + 40), logo)
        visual_login.colar_retangulo_rgba(fundo, x0 + self._M, y0 + 132, self._largura_util(), 1, 0,
                                          (255, 255, 255, 50))
        for x, y, largura in self._caixas_campos(x0, y0).values():
            visual_login.colar_retangulo(fundo, x, y, largura, self._H, 8, (255, 255, 255))
        for x, y, largura in self._caixas_chips(x0, y0).values():
            visual_login.colar_retangulo_rgba(fundo, x, y, largura, self._H, 8, (6, 30, 42, 70),
                                              (255, 255, 255, 70))

    def _desenhar_dinamico(self, x0, y0):
        c = self.canvas
        m = self._M
        branco = "#ffffff"
        xt = x0 + m + 174
        c.create_text(xt, y0 + 40, text=" ".join("ADMINISTRAÇÃO"), anchor="nw", fill="#C9B48C",
                      font=(_FONTE_SEMI, 8))
        c.create_text(xt, y0 + 58, text="Criar usuário", anchor="nw", fill=branco, font=(_FONTE_SEMI, 18))
        c.create_text(xt, y0 + 96, text="Cadastre um novo acesso para a equipe técnica.", anchor="nw",
                      fill="#DCE6E9", font=(_FONTE_SEMI, 10))

        caixas = self._caixas_campos(x0, y0)
        rotulos = {"usuario": "Nome de usuário", "nome": "Nome completo", "email": "E-mail",
                   "setor": "Setor", "senha": "Senha", "confirmar": "Confirmar senha"}
        widgets = {"usuario": self.ent_usuario, "nome": self.ent_nome, "email": self.ent_email,
                   "senha": self.ent_senha, "confirmar": self.ent_confirmar}
        for chave, (x, y, largura) in caixas.items():
            c.create_text(x, y - 16, text=rotulos[chave], anchor="w", fill=branco, font=(_FONTE_SEMI, 10))
            if chave == "setor":
                c.create_window(x + 16, y + self._H // 2, window=self.cb_setor, anchor="w",
                                width=largura - 52, height=self._H - 12)
                c.create_text(x + largura - 18, y + self._H // 2, text="", font=(_FONTE_ICONE, 10),
                              fill="#1d2b36", tags=("seta_setor",))
                c.tag_bind("seta_setor", "<Button-1>", lambda e: self._abrir_setor())
                continue
            c.create_window(x + 14, y + self._H // 2, window=widgets[chave], anchor="w",
                            width=largura - 28, height=self._H - 12)
        self.cb_setor.bind("<Button-1>", lambda e: self._abrir_setor() or "break")

        c.create_text(x0 + m, y0 + self._Y["disciplinas"] - 16, text="Disciplina(s)", anchor="w",
                      fill=branco, font=(_FONTE_SEMI, 10))
        self._chips = self._caixas_chips(x0, y0)
        for disciplina, (x, y, largura) in self._chips.items():
            tag = f"chip_{disciplina}"
            c.create_rectangle(x, y, x + largura, y + self._H, fill="", outline="", tags=(tag,))
            c.create_text(x + 42, y + self._H // 2, text=disciplina, anchor="w", fill=branco,
                          font=(_FONTE_SEMI, 10), tags=(tag,))
            c.tag_bind(tag, "<Button-1>", lambda e, d=disciplina: self._alternar_disciplina(d))
            c.tag_bind(tag, "<Enter>", lambda e: c.config(cursor="hand2"))
            c.tag_bind(tag, "<Leave>", lambda e: c.config(cursor=""))
            self._desenhar_chip(disciplina)

        c.create_text(x0 + m, y0 + 565, text="Senha: mínimo 6 caracteres, 1 maiúscula e 1 caractere especial.",
                      anchor="w", fill="#DCE6E9", font=(_FONTE, 9))
        self.lbl_erro.item = c.create_text(
            x0 + m, y0 + self._Y["botoes"] + self._H // 2, text=self.lbl_erro.cget("text"),
            fill=self.lbl_erro.cget("fg"), font=(_FONTE_SEMI, 9), anchor="w", width=400)

        yb = y0 + self._Y["botoes"] + self._H // 2
        xr = x0 + self.LARGURA_CARTAO - m
        self._criar_botao("criar", "✓  Criar usuário", xr - 71, yb, 142, self._H,
                          cor=(240, 240, 236, 255), cor_hover=(255, 255, 255, 255),
                          cor_texto="#13303f", fonte=(_FONTE_SEMI, 10), comando=self._criar)
        self._criar_botao("cancelar", "Cancelar", xr - 142 - 8 - 60, yb, 120, self._H,
                          cor=(10, 40, 56, 255), cor_hover=(24, 64, 84, 255),
                          cor_texto="#ffffff", fonte=(_FONTE_SEMI, 10), comando=self.destroy,
                          borda=(205, 215, 220, 255))

    def _desenhar_chip(self, disciplina):
        caixas = getattr(self, "_chips", None)
        if not caixas or disciplina not in caixas:
            return
        c = self.canvas
        x, y, _ = caixas[disciplina]
        tag = f"caixa_{disciplina}"
        c.delete(tag)
        cy = y + self._H // 2
        c.create_rectangle(x + 16, cy - 7, x + 30, cy + 7, fill="white", outline="white",
                           tags=(tag, f"chip_{disciplina}"))
        if self._vars_disciplinas[disciplina].get():
            c.create_text(x + 23, cy, text="", font=(_FONTE_ICONE, 8), fill="#13303f",
                          tags=(tag, f"chip_{disciplina}"))

    def _alternar_disciplina(self, disciplina):
        var = self._vars_disciplinas[disciplina]
        var.set(not var.get())

    def _abrir_setor(self):
        try:
            self.cb_setor.focus_set()
            self.cb_setor.tk.call("ttk::combobox::Post", self.cb_setor)
        except tk.TclError:
            pass

    # ---------- ação ----------
    def _criar(self):
        nome_usuario = self.ent_usuario.get().strip()
        nome = self.ent_nome.get().strip()
        email = self.ent_email.get().strip()
        disciplinas = [d for d, var in self._vars_disciplinas.items() if var.get()]
        setor = self.cb_setor.get().strip()
        if setor == PLACEHOLDER_SETOR:
            setor = ""
        senha = self.ent_senha.get()
        confirmar = self.ent_confirmar.get()

        if not nome:
            self.lbl_erro.config(text="Informe o nome completo.")
            return
        if not disciplinas:
            self.lbl_erro.config(text="Selecione ao menos uma disciplina.")
            return
        if not setor:
            self.lbl_erro.config(text="Selecione o setor.")
            return
        if senha != confirmar:
            self.lbl_erro.config(text="As senhas não coincidem.")
            return

        # Setor BIM acompanha o trabalho de todos os projetistas e precisa
        # gerenciar contas (excluir/transferir issues de quem sai ou tira
        # férias) — por isso entra direto como Administrador.
        papel = PAPEL_ADMINISTRADOR if setor == SETOR_BIM else PAPEL_PROJETISTA

        try:
            usuario = criar_usuario(
                self.usuarios, nome_usuario, nome, email, senha, papel,
                disciplinas=disciplinas, setor=setor, deve_trocar_senha=False,
            )
        except ValueError as e:
            self.lbl_erro.config(text=str(e))
            return

        self.usuario_criado = usuario
        self.destroy()
