"""Gerenciamento de usuários — exclusivo do Administrador (o que inclui
quem é do Setor BIM, que entra como Administrador automaticamente, ver
auth/dialogs.py): listar, excluir conta e transferir os problemas
("atribuido_para") de um usuário para outro, para o caso de alguém sair
da empresa ou entrar de férias."""
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from auth.dialogs import DialogCriarUsuario, DialogSenhaTemporariaGerada
from auth.usuarios import (
    NOMES_PAPEIS,
    PAPEL_ADMINISTRADOR,
    carregar_usuarios,
    excluir_usuario,
    resetar_para_senha_temporaria,
    salvar_usuarios,
)
from config import LISTA_STATUS, TEMA
from ui.componentes import (
    Avatar,
    Botao,
    CampoArredondado,
    Cartao,
    Icone,
    Pilula,
    QuadradoIcone,
    cabecalho_pagina,
    espacar,
    iniciais,
    rotulo,
    separador,
)
from utils import transferir_issues_por_id

TODOS = "— Todos —"


class PainelUsuarios(tk.Frame):
    """Tela "Gerenciar usuários" no estilo do protótipo Figma: números
    gerais, lista de contas (com busca) e painel do usuário selecionado
    com as ações (transferir problemas, resetar senha, ativar/desativar,
    excluir)."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self.usuarios = carregar_usuarios()
        self._avatares = {}

        self.pagina = tk.Frame(self, bg=TEMA["pagina"])
        self.pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(24, 24))
        self._montar_cabecalho()
        self.frame_numeros = tk.Frame(self.pagina, bg=TEMA["pagina"])
        self.frame_numeros.pack(fill=tk.X, pady=(0, 16))
        self._montar_corpo()
        self._atualizar_lista()

    # ---------- construção ----------
    def _montar_cabecalho(self):
        cab, direita = cabecalho_pagina(
            self.pagina, "Administração", "Gerenciar usuários",
            "Contas de acesso, papéis e transferência de problemas entre a equipe.",
            migalhas=[("Início", self.app.abrir_tela_home), ("Gerenciar usuários", None)])
        cab.pack(fill=tk.X, pady=(0, 18))
        botoes = tk.Frame(direita, bg=TEMA["pagina"])
        botoes.pack(anchor="e")
        Botao(botoes, "Transferir problemas", variante="secundario", icone=Icone.TROCAR, altura=34,
              tamanho_fonte=9, comando=self._abrir_transferir).pack(side=tk.LEFT, padx=(0, 8))
        Botao(botoes, "Novo usuário", variante="primario", icone=Icone.ADICIONAR_PESSOA, altura=34,
              tamanho_fonte=9, comando=self._novo_usuario).pack(side=tk.LEFT)

    def _montar_numeros(self):
        for w in self.frame_numeros.winfo_children():
            w.destroy()
        ativos = [u for u in self.usuarios if u.get("ativo", True)]
        admins = [u for u in self.usuarios if u.get("papel") == PAPEL_ADMINISTRADOR]
        abertos = sum(1 for i in self.app.issues if i.get("status") != "Fechado" and i.get("atribuido_para"))
        cartoes = (
            (Icone.PESSOAS, "pill_azul", "Usuários cadastrados", len(self.usuarios)),
            (Icone.CHAVE, "pill_dourado", "Administradores", len(admins)),
            (Icone.CHECK, "pill_verde", "Contas ativas", len(ativos)),
            (Icone.RELOGIO, "pill_vermelho", "Problemas em aberto", abertos),
        )
        for col, (glifo, chave, titulo, valor) in enumerate(cartoes):
            self.frame_numeros.columnconfigure(col, weight=1, uniform="num")
            cartao = Cartao(self.frame_numeros, padding=(18, 16))
            cartao.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0 if col == 3 else 8))
            c = cartao.corpo
            QuadradoIcone(c, glifo, cores=TEMA[chave], tamanho=40).pack(side=tk.LEFT, padx=(0, 14))
            t = tk.Frame(c, bg=c["bg"])
            t.pack(side=tk.LEFT)
            rotulo(t, espacar(titulo), 8, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
            rotulo(t, str(valor), 20, "semi").pack(anchor="w")

    def _montar_corpo(self):
        corpo = tk.Frame(self.pagina, bg=TEMA["pagina"])
        corpo.pack(fill=tk.BOTH, expand=True)
        corpo.columnconfigure(0, weight=3, uniform="corpo")
        corpo.columnconfigure(1, weight=2, uniform="corpo")
        corpo.rowconfigure(0, weight=1)

        lista = Cartao(corpo, padding=(16, 14), ajustar_altura=False)
        lista.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c = lista.corpo
        topo = tk.Frame(c, bg=c["bg"])
        topo.pack(fill=tk.X, pady=(0, 10))
        rotulo(topo, "Contas", 13, "semi").pack(side=tk.LEFT)
        self._contagem = tk.Frame(topo, bg=c["bg"])
        self._contagem.pack(side=tk.RIGHT)
        self.ent_busca = CampoArredondado(topo, placeholder="Buscar por nome, usuário, e-mail ou setor...",
                                          icone_esquerda=Icone.BUSCA, largura=320, altura=34,
                                          cor=TEMA["campo"], borda=TEMA["campo"])
        self.ent_busca.pack(side=tk.RIGHT, padx=(0, 12))
        self.ent_busca.entry.bind("<KeyRelease>", lambda e: self._preencher_lista())

        colunas = ("nome_usuario", "papel", "setor", "ativo", "problemas_atribuidos")
        rotulos = ("Usuário", "Papel", "Setor", "Situação", "Problemas")
        larguras = (120, 110, 170, 90, 90)
        tabela = tk.Frame(c, bg=c["bg"])
        tabela.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tabela, columns=colunas, show="tree headings", style="Cartao.Treeview")
        self.tree.heading("#0", text=espacar("Nome"), anchor="w")
        self.tree.column("#0", width=260, anchor="w")
        for col, rot, largura in zip(colunas, rotulos, larguras):
            self.tree.heading(col, text=espacar(rot), anchor="w")
            self.tree.column(col, width=largura, anchor="w", stretch=col == "setor")
        self.tree.tag_configure("inativo", foreground=TEMA["texto_fraco"])
        scrollbar = ttk.Scrollbar(tabela, orient=tk.VERTICAL, command=self.tree.yview,
                                  style="Fino.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._mostrar_detalhes())

        detalhes = Cartao(corpo, padding=(22, 20), ajustar_altura=False)
        detalhes.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.painel_detalhes = detalhes.corpo
        self._detalhes_vazio()

    # ---------- dados ----------
    def _contar_problemas_atribuidos(self, nome):
        return sum(1 for i in self.app.issues if i.get("atribuido_para") == nome)

    def _contar_problemas_abertos(self, nome):
        return sum(1 for i in self.app.issues if i.get("atribuido_para") == nome and i.get("status") != "Fechado")

    def _imagem_avatar(self, nome):
        if nome not in self._avatares:
            s, t = 4, 26
            img = Image.new("RGBA", (t * s, t * s), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            bg, fg = TEMA["pill_azul"]
            d.ellipse((0, 0, t * s - 1, t * s - 1), fill=bg)
            try:
                f = ImageFont.truetype("seguisb.ttf", 9 * s)
            except OSError:
                f = ImageFont.load_default()
            d.text((t * s / 2, t * s / 2), iniciais(nome), font=f, fill=fg, anchor="mm")
            self._avatares[nome] = ImageTk.PhotoImage(img.resize((t, t), Image.LANCZOS), master=self)
        return self._avatares[nome]

    def _atualizar_lista(self):
        self.usuarios = carregar_usuarios()
        self._montar_numeros()
        self._preencher_lista()

    def _preencher_lista(self):
        selecionado = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        busca = self.ent_busca.get().strip().lower()
        n = 0
        for u in self.usuarios:
            campos = (u["nome_usuario"], u["nome"], u.get("email", ""), u.get("setor", ""))
            if busca and not any(busca in (c or "").lower() for c in campos):
                continue
            ativo = u.get("ativo", True)
            self.tree.insert("", tk.END, iid=u["nome_usuario"], text="  " + u["nome"],
                             image=self._imagem_avatar(u["nome"]),
                             tags=() if ativo else ("inativo",), values=(
                                 u["nome_usuario"], NOMES_PAPEIS.get(u.get("papel"), u.get("papel", "")),
                                 u.get("setor", "") or "—", "Ativo" if ativo else "Inativo",
                                 self._contar_problemas_atribuidos(u["nome"]),
                             ))
            n += 1
        for w in self._contagem.winfo_children():
            w.destroy()
        Pilula(self._contagem, f"{n} conta{'s' if n != 1 else ''}", cores=(TEMA["campo"], TEMA["texto_fraco"]),
               altura=24).pack()
        for iid in selecionado:
            if self.tree.exists(iid):
                self.tree.selection_set(iid)

    def _usuario_selecionado(self):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showwarning("Nenhum usuário selecionado", "Selecione um usuário na lista primeiro.")
            return None
        return selecionado[0]  # iid == nome_usuario

    # ---------- detalhes ----------
    def _detalhes_vazio(self):
        for w in self.painel_detalhes.winfo_children():
            w.destroy()
        p = self.painel_detalhes
        centro = tk.Frame(p, bg=p["bg"])
        centro.place(relx=0.5, rely=0.42, anchor="center")
        QuadradoIcone(centro, Icone.PESSOA, cores=(TEMA["campo"], TEMA["titulo"]), tamanho=48,
                      tamanho_icone=16).pack()
        rotulo(centro, "Selecione um usuário", 12, "semi").pack(pady=(12, 2))
        rotulo(centro, "Os dados da conta e as ações aparecem aqui.", 9, cor=TEMA["texto_fraco"]).pack()

    def _mostrar_detalhes(self):
        selecionado = self.tree.selection()
        if not selecionado:
            self._detalhes_vazio()
            return
        u = next((x for x in self.usuarios if x["nome_usuario"] == selecionado[0]), None)
        if u is None:
            return
        for w in self.painel_detalhes.winfo_children():
            w.destroy()
        p = self.painel_detalhes
        bg = p["bg"]
        ativo = u.get("ativo", True)

        topo = tk.Frame(p, bg=bg)
        topo.pack(fill=tk.X)
        Avatar(topo, u["nome"], tamanho=56, online=ativo).pack(side=tk.LEFT, padx=(0, 14))
        t = tk.Frame(topo, bg=bg)
        t.pack(side=tk.LEFT, fill=tk.X, expand=True)
        rotulo(t, u["nome"], 14, "semi", wraplength=280, justify="left").pack(anchor="w")
        rotulo(t, f"@{u['nome_usuario']} · {u.get('email', '')}", 9, cor=TEMA["texto_fraco"]).pack(anchor="w")
        pilulas = tk.Frame(t, bg=bg)
        pilulas.pack(anchor="w", pady=(6, 0))
        Pilula(pilulas, NOMES_PAPEIS.get(u.get("papel"), u.get("papel", "")), cores=TEMA["pill_azul"],
               altura=22).pack(side=tk.LEFT, padx=(0, 6))
        Pilula(pilulas, "Ativo" if ativo else "Inativo",
               cores=TEMA["pill_verde"] if ativo else TEMA["pill_cinza"], altura=22).pack(side=tk.LEFT)

        separador(p, pady=16)
        meta = tk.Frame(p, bg=bg)
        meta.pack(fill=tk.X)
        meta.columnconfigure(0, weight=1, uniform="m")
        meta.columnconfigure(1, weight=1, uniform="m")
        campos = (
            ("Setor", u.get("setor") or "—"),
            ("Disciplinas", ", ".join(u.get("disciplinas") or []) or "—"),
            ("Problemas em aberto", str(self._contar_problemas_abertos(u["nome"]))),
            ("Problemas atribuídos", str(self._contar_problemas_atribuidos(u["nome"]))),
            ("Último acesso", u.get("data_ultimo_login") or "Nunca"),
            ("Conta criada em", u.get("data_criacao") or "—"),
        )
        for n, (rot, valor) in enumerate(campos):
            f = tk.Frame(meta, bg=bg)
            f.grid(row=n // 2, column=n % 2, sticky="w", pady=(0, 12))
            rotulo(f, espacar(rot), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
            rotulo(f, valor, 10).pack(anchor="w")

        separador(p, pady=(4, 16))
        rotulo(p, espacar("Ações"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(0, 8))
        acoes = (
            ("Transferir problemas deste usuário", Icone.TROCAR, "secundario", lambda: self._abrir_transferir(u["nome"])),
            ("Resetar para senha temporária", Icone.CHAVE, "secundario", lambda: self._resetar_senha(u)),
            ("Desativar conta" if ativo else "Reativar conta", Icone.CADEADO, "secundario",
             lambda: self._alternar_ativo(u)),
            ("Excluir usuário", Icone.EXCLUIR, "perigo", self._excluir_selecionado),
        )
        for texto, glifo, variante, comando in acoes:
            Botao(p, texto, variante=variante, icone=glifo, altura=36, tamanho_fonte=9, largura=10,
                  comando=comando).pack(fill=tk.X, pady=(0, 8))

    # ---------- ações ----------
    def _novo_usuario(self):
        dialogo = DialogCriarUsuario(self.winfo_toplevel(), self.usuarios)
        if dialogo.usuario_criado is not None:
            salvar_usuarios(self.usuarios)
            self._atualizar_lista()
            self.tree.selection_set(dialogo.usuario_criado["nome_usuario"])
            messagebox.showinfo("OK", f"Usuário \"{dialogo.usuario_criado['nome']}\" criado.")

    def _resetar_senha(self, usuario):
        if self.app.usuario_atual and self.app.usuario_atual.get("nome_usuario") == usuario["nome_usuario"]:
            messagebox.showinfo("Sua conta", "Para trocar a sua própria senha, use \"Trocar senha\" no menu do "
                                             "seu nome (barra lateral).")
            return
        if not messagebox.askyesno("Resetar senha", f"Gerar uma senha temporária para \"{usuario['nome']}\"? "
                                                    "A pessoa será obrigada a trocá-la no próximo login."):
            return
        senha = resetar_para_senha_temporaria(usuario)
        salvar_usuarios(self.usuarios)
        DialogSenhaTemporariaGerada(self.winfo_toplevel(), usuario["nome_usuario"], senha)

    def _alternar_ativo(self, usuario):
        if self.app.usuario_atual and self.app.usuario_atual.get("nome_usuario") == usuario["nome_usuario"]:
            messagebox.showerror("Não é possível", "Você não pode desativar a conta com a qual está logado.")
            return
        usuario["ativo"] = not usuario.get("ativo", True)
        salvar_usuarios(self.usuarios)
        self._atualizar_lista()
        self._mostrar_detalhes()

    def _excluir_selecionado(self):
        nome_usuario = self._usuario_selecionado()
        if nome_usuario is None:
            return

        if self.app.usuario_atual and self.app.usuario_atual.get("nome_usuario") == nome_usuario:
            messagebox.showerror("Não é possível excluir", "Você não pode excluir a conta com a qual está logado.")
            return

        usuario = next(u for u in self.usuarios if u["nome_usuario"] == nome_usuario)
        qtd_problemas = self._contar_problemas_atribuidos(usuario["nome"])
        aviso_problemas = (
            f"\n\nATENÇÃO: {qtd_problemas} problema(s) estão atribuídos a esse usuário "
            "e continuarão no histórico com o nome dele. Use \"Transferir problemas\" "
            "antes de excluir se quiser passá-los para outra pessoa."
            if qtd_problemas else ""
        )
        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Excluir o usuário \"{usuario['nome']}\" ({nome_usuario})? Essa ação não pode ser desfeita."
            + aviso_problemas,
        ):
            return

        excluir_usuario(self.usuarios, nome_usuario)
        salvar_usuarios(self.usuarios)
        self._atualizar_lista()
        self._detalhes_vazio()
        messagebox.showinfo("OK", "Usuário excluído.")

    def _abrir_transferir(self, origem=None):
        if len(self.usuarios) < 2:
            messagebox.showwarning("Usuários insuficientes", "É preciso pelo menos 2 usuários cadastrados para transferir problemas.")
            return
        dialogo = _DialogTransferirProblemas(self, self.usuarios, self.app.issues, origem=origem)
        if dialogo.confirmado:
            qtd = transferir_issues_por_id(self.app.issues, dialogo.ids_selecionados, dialogo.destino)
            self.app.salvar_banco_dados()
            self._atualizar_lista()
            self._mostrar_detalhes()
            messagebox.showinfo("OK", f"{qtd} problema(s) transferido(s) para \"{dialogo.destino}\".")

    def sincronizar(self):
        self._atualizar_lista()
        self._mostrar_detalhes()


class _DialogTransferirProblemas(tk.Toplevel):
    """Escolhe "De"/"Para" e, a partir dos problemas atribuídos a "De",
    filtra por projeto/tipo/status/id e deixa marcar manualmente (um a
    um ou "selecionar todos os filtrados") quais serão transferidos —
    mostrando a descrição do item em foco para conferência antes de
    confirmar."""

    def __init__(self, parent, usuarios, issues, origem=None):
        super().__init__(parent, bg=TEMA["surface"])
        self.issues = issues
        self.confirmado = False
        self.destino = None
        self.ids_selecionados = []
        self.title("Transferir problemas")
        self.geometry("760x560")
        self.minsize(640, 460)

        self.nomes = sorted({u["nome"] for u in usuarios if u.get("nome")})

        tk.Label(self, text="Transferir problemas de um usuário para outro", font=("Arial", 11, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"]).pack(pady=(12, 8))

        self._montar_selecao_usuarios()
        self._montar_filtros()
        self._montar_lista()
        self._montar_descricao()
        self._montar_rodape()

        if origem in self.nomes:
            self.cb_origem.set(origem)
            self._ao_trocar_origem()

        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    # ---------- construção ----------
    def _montar_selecao_usuarios(self):
        form = tk.Frame(self, bg=TEMA["surface"])
        form.pack(fill=tk.X, padx=15)

        tk.Label(form, text="De (sai/tira férias):", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=0, column=0, padx=5, pady=5, sticky="e")
        self.cb_origem = ttk.Combobox(form, values=self.nomes, state="readonly", width=22)
        self.cb_origem.grid(row=0, column=1, padx=5, pady=5)
        self.cb_origem.bind("<<ComboboxSelected>>", self._ao_trocar_origem)

        tk.Label(form, text="Para (recebe os problemas):", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=0, column=2, padx=(15, 5), pady=5, sticky="e")
        self.cb_destino = ttk.Combobox(form, values=self.nomes, state="readonly", width=22)
        self.cb_destino.grid(row=0, column=3, padx=5, pady=5)

    def _montar_filtros(self):
        filtros = tk.Frame(self, bg=TEMA["surface"])
        filtros.pack(fill=tk.X, padx=15, pady=(5, 0))

        def combo(texto, coluna, largura=16):
            tk.Label(filtros, text=texto, bg=TEMA["surface"], fg=TEMA["texto"]).grid(
                row=0, column=coluna * 2, padx=(0, 4), pady=5, sticky="e")
            cb = ttk.Combobox(filtros, values=[TODOS], state="readonly", width=largura)
            cb.set(TODOS)
            cb.grid(row=0, column=coluna * 2 + 1, padx=(0, 10), pady=5)
            cb.bind("<<ComboboxSelected>>", lambda e: self._atualizar_lista())
            return cb

        self.cb_filtro_obra = combo("Projeto:", 0)
        self.cb_filtro_tipo = combo("Tipo:", 1)
        self.cb_filtro_status = combo("Status:", 2, largura=14)
        self.cb_filtro_status["values"] = [TODOS] + LISTA_STATUS

        tk.Label(filtros, text="ID:", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=0, column=6, padx=(0, 4), pady=5, sticky="e")
        self.ent_filtro_id = ttk.Entry(filtros, width=8)
        self.ent_filtro_id.grid(row=0, column=7, pady=5)
        self.ent_filtro_id.bind("<KeyRelease>", lambda e: self._atualizar_lista())

    def _montar_lista(self):
        corpo = tk.Frame(self, bg=TEMA["surface"])
        corpo.pack(fill=tk.BOTH, expand=True, padx=15, pady=(8, 0))

        colunas = ("id", "titulo", "obra", "tipo", "status")
        rotulos = ("ID", "Título", "Projeto", "Tipo", "Status")
        self.tree = ttk.Treeview(corpo, columns=colunas, show="headings", selectmode="extended", height=10)
        for col, rot, largura in zip(colunas, rotulos, (50, 260, 90, 110, 90)):
            self.tree.heading(col, text=rot)
            self.tree.column(col, width=largura, anchor="w" if col in ("titulo",) else "center")
        scrollbar = ttk.Scrollbar(corpo, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar_na_lista)

        botoes_sel = tk.Frame(self, bg=TEMA["surface"])
        botoes_sel.pack(fill=tk.X, padx=15, pady=(4, 0))
        tk.Button(botoes_sel, text="☑ Selecionar todos (filtrados)", command=self._selecionar_todos,
                  bg=TEMA["surface_alt"], fg=TEMA["texto"], font=("Arial", 8)).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(botoes_sel, text="☐ Limpar seleção", command=self._limpar_selecao,
                  bg=TEMA["surface_alt"], fg=TEMA["texto"], font=("Arial", 8)).pack(side=tk.LEFT)
        self.lbl_contagem = tk.Label(botoes_sel, text="0 selecionado(s)", bg=TEMA["surface"],
                                      fg=TEMA["texto_fraco"], font=("Arial", 8))
        self.lbl_contagem.pack(side=tk.RIGHT)

    def _montar_descricao(self):
        tk.Label(self, text="Descrição do item em foco:", bg=TEMA["surface"], fg=TEMA["texto"],
                 font=("Arial", 8, "bold")).pack(anchor="w", padx=15, pady=(8, 2))
        self.txt_descricao = tk.Text(self, height=3, font=("Arial", 9), bg=TEMA["surface_alt"],
                                      fg=TEMA["texto"], state=tk.DISABLED, wrap="word")
        self.txt_descricao.pack(fill=tk.X, padx=15)

    def _montar_rodape(self):
        self.lbl_erro = tk.Label(self, text="", bg=TEMA["surface"], fg=TEMA["critico"],
                                  font=("Arial", 8), wraplength=600, justify="center")
        self.lbl_erro.pack(pady=(6, 0))

        botoes = tk.Frame(self, bg=TEMA["surface"])
        botoes.pack(pady=10)
        tk.Button(botoes, text="✔ Transferir selecionados", command=self._confirmar, bg=TEMA["acento"],
                  fg=TEMA["acento_texto"], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(botoes, text="Cancelar", command=self.destroy, bg=TEMA["surface_alt"],
                  fg=TEMA["texto"]).pack(side=tk.LEFT, padx=5)

    # ---------- dados ----------
    def _issues_do_usuario_origem(self):
        nome = self.cb_origem.get()
        if not nome:
            return []
        return [i for i in self.issues if i.get("atribuido_para") == nome]

    def _issues_filtradas(self):
        base = self._issues_do_usuario_origem()

        obra = self.cb_filtro_obra.get()
        if obra and obra != TODOS:
            base = [i for i in base if (i.get("obra") or "") == obra]

        tipo = self.cb_filtro_tipo.get()
        if tipo and tipo != TODOS:
            base = [i for i in base if (i.get("tipo") or "") == tipo]

        status = self.cb_filtro_status.get()
        if status and status != TODOS:
            base = [i for i in base if (i.get("status") or "") == status]

        id_busca = self.ent_filtro_id.get().strip()
        if id_busca:
            base = [i for i in base if id_busca in str(i.get("id", ""))]

        return base

    def _ao_trocar_origem(self, event=None):
        issues_origem = self._issues_do_usuario_origem()
        obras = sorted({i.get("obra") for i in issues_origem if i.get("obra")})
        tipos = sorted({i.get("tipo") for i in issues_origem if i.get("tipo")})
        self.cb_filtro_obra["values"] = [TODOS] + obras
        self.cb_filtro_obra.set(TODOS)
        self.cb_filtro_tipo["values"] = [TODOS] + tipos
        self.cb_filtro_tipo.set(TODOS)
        self.cb_filtro_status.set(TODOS)
        self.ent_filtro_id.delete(0, tk.END)
        self._atualizar_lista()

    def _atualizar_lista(self):
        self.tree.delete(*self.tree.get_children())
        for issue in self._issues_filtradas():
            self.tree.insert("", tk.END, iid=str(issue["id"]), values=(
                issue["id"], issue.get("titulo") or "(sem título)", issue.get("obra") or "—",
                issue.get("tipo") or "—", issue.get("status") or "—",
            ))
        self._atualizar_contagem()

    def _ao_selecionar_na_lista(self, event=None):
        self._atualizar_contagem()
        selecao = self.tree.selection()
        self.txt_descricao.config(state=tk.NORMAL)
        self.txt_descricao.delete("1.0", tk.END)
        if selecao:
            issue_id = int(selecao[-1])
            issue = next((i for i in self.issues if i.get("id") == issue_id), None)
            if issue:
                self.txt_descricao.insert(tk.END, issue.get("desc") or "(sem descrição)")
        self.txt_descricao.config(state=tk.DISABLED)

    def _atualizar_contagem(self):
        self.lbl_contagem.config(text=f"{len(self.tree.selection())} selecionado(s)")

    def _selecionar_todos(self):
        self.tree.selection_set(self.tree.get_children())

    def _limpar_selecao(self):
        self.tree.selection_remove(*self.tree.selection())

    # ---------- confirmação ----------
    def _confirmar(self):
        origem = self.cb_origem.get()
        destino = self.cb_destino.get()
        selecao = self.tree.selection()

        if not origem or not destino:
            self.lbl_erro.config(text="Selecione os dois usuários.")
            return
        if origem == destino:
            self.lbl_erro.config(text="Selecione usuários diferentes.")
            return
        if not selecao:
            self.lbl_erro.config(text="Selecione ao menos um problema na lista para transferir.")
            return

        self.destino = destino
        self.ids_selecionados = [int(iid) for iid in selecao]
        self.confirmado = True
        self.destroy()
