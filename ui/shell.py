"""Moldura fixa do app depois do login (protótipo Figma): barra lateral
à esquerda (logo, usuário, navegação) e barra superior (busca, modo
noite, notificações). As telas trocam só na área de conteúdo
(`app.main_container`)."""
import os
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk

from auth.usuarios import NOMES_PAPEIS, eh_administrador
from config import CHAMADOS_EXE, ICONE_VIZZO_PNG, TEMA
from dashboard.dados_painel import issues_pendentes_de
from ui.componentes import (
    FONTE_ICONE,
    Avatar,
    Botao,
    Cartao,
    CampoArredondado,
    Icone,
    espacar,
    fonte,
    nome_curto,
    retangulo_arredondado,
)

LARGURA_LATERAL = 236
LARGURA_LATERAL_RECOLHIDA = 72


def imagem_marca(tamanho, master, cor_fundo=None, cor_logo="#FFFFFF"):
    """Quadrado arredondado com o "V" do Vizzo: azul com V branco (barra
    lateral) ou, com `cor_fundo="#FFFFFF"`, branco com V azul (cabeçalho
    do visualizador)."""
    s = 4
    t = tamanho * s
    fundo = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    ImageDraw.Draw(fundo).rounded_rectangle(
        (0, 0, t - 1, t - 1), radius=int(t * 0.24),
        fill=cor_fundo or (TEMA["primario"] if not TEMA.esta_escuro() else "#14495D"))
    if os.path.exists(ICONE_VIZZO_PNG):
        icone = Image.open(ICONE_VIZZO_PNG).convert("RGBA")
        branco = Image.new("RGBA", icone.size, cor_logo)
        branco.putalpha(icone.getchannel("A"))
        branco.thumbnail((int(t * 0.62), int(t * 0.62)), Image.LANCZOS)
        fundo.alpha_composite(branco, ((t - branco.width) // 2, (t - branco.height) // 2 + s))
    return ImageTk.PhotoImage(fundo.resize((tamanho, tamanho), Image.LANCZOS), master=master)


class ItemNavegacao(tk.Canvas):
    """Linha da navegação lateral: ícone + texto (quebra em 2 linhas),
    fundo arredondado quando selecionado ou com o mouse em cima."""

    def __init__(self, parent, texto, glifo, comando, selecionado=False, recolhido=False,
                 sub=False, largura=210):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.texto, self.glifo, self.comando = texto, glifo, comando
        self.selecionado, self.recolhido, self.sub = selecionado, recolhido, sub
        self.largura = 48 if recolhido else largura
        self._hover = False
        # mede a altura do texto quebrado para dimensionar a linha
        if recolhido:
            self.altura = 44
        else:
            item = self.create_text(0, 0, text=texto, width=self.largura - (40 if sub else 58),
                                    font=fonte(10, "semi" if selecionado else "normal"), anchor="nw")
            x0, y0, x1, y1 = self.bbox(item)
            self.delete(item)
            self.altura = max(36 if sub else 44, (y1 - y0) + 18)
        self.configure(width=self.largura, height=self.altura)
        self._desenhar()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", lambda e: self.comando())

    def _set_hover(self, valor):
        self._hover = valor
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        if self.selecionado:
            retangulo_arredondado(self, 0, 0, self.largura, self.altura, 9, TEMA["sidebar_sel"],
                                  None if self.sub else TEMA["sidebar_sel_borda"])
        elif self._hover:
            retangulo_arredondado(self, 0, 0, self.largura, self.altura, 9, TEMA["sidebar_sel"])
        cor = TEMA["titulo"] if self.selecionado else TEMA["texto"]
        if self.recolhido:
            self.create_text(self.largura / 2, self.altura / 2, text=self.glifo,
                             font=(FONTE_ICONE, 12), fill=cor)
            return
        x = 14
        if self.glifo and not self.sub:
            self.create_text(x + 8, self.altura / 2, text=self.glifo, font=(FONTE_ICONE, 11), fill=cor)
            x = 44
        self.create_text(x, self.altura / 2, text=self.texto, anchor="w", fill=cor,
                         width=self.largura - x - 8,
                         font=fonte(10, "semi" if self.selecionado else "normal"))


class BarraLateral(Cartao):
    def __init__(self, parent, app, recolhida=False):
        largura = LARGURA_LATERAL_RECOLHIDA if recolhida else LARGURA_LATERAL
        super().__init__(parent, raio=14, padding=(12, 14), ajustar_altura=False, width=largura)
        self.app = app
        self.recolhida = recolhida
        self.largura = largura
        self._montar()

    def _ajustar(self, _evento=None):
        pass  # largura fixa: não segue o conteúdo

    def _montar(self):
        c = self.corpo
        bg = self.cor
        app = self.app
        usuario = app.usuario_atual or {}

        topo = tk.Frame(c, bg=bg)
        topo.pack(fill=tk.X, pady=(4, 12))
        self._img_marca = imagem_marca(38, self)
        marca = tk.Label(topo, image=self._img_marca, bg=bg, cursor="hand2")
        marca.pack(side=tk.LEFT)
        marca.bind("<Button-1>", lambda e: app.abrir_tela_home())
        if not self.recolhida:
            textos = tk.Frame(topo, bg=bg)
            textos.pack(side=tk.LEFT, padx=(10, 0))
            tk.Label(textos, text=espacar("Cadari"), bg=bg, fg=TEMA["primario"] if not TEMA.esta_escuro()
                     else TEMA["acento"], font=fonte(8, "bold")).pack(anchor="w")
            tk.Label(textos, text="Vizzo", bg=bg, fg=TEMA["titulo"], font=fonte(16, "semi")
                     ).pack(anchor="w", pady=(0, 0))
        Botao(topo if not self.recolhida else c,
              "", comando=app.alternar_barra_lateral, variante="secundario",
              icone=Icone.CHEVRON_DIREITA if self.recolhida else Icone.CHEVRON_ESQUERDA,
              largura=24, altura=24, raio=12, tamanho_fonte=8
              ).pack(side=tk.RIGHT if not self.recolhida else tk.TOP, pady=(0, 6))

        tk.Frame(c, bg=TEMA["linha"], height=1).pack(fill=tk.X)

        bloco = tk.Frame(c, bg=bg, cursor="hand2")
        bloco.pack(fill=tk.X, pady=14)
        avatar = Avatar(bloco, usuario.get("nome", "?"), tamanho=42, online=True)
        avatar.pack(side=tk.LEFT)
        widgets_clicaveis = [bloco, avatar]
        if not self.recolhida:
            textos = tk.Frame(bloco, bg=bg)
            textos.pack(side=tk.LEFT, padx=(10, 0), fill=tk.X, expand=True)
            setor = usuario.get("setor") or NOMES_PAPEIS.get(usuario.get("papel"), "")
            l1 = tk.Label(textos, text=espacar(setor or "Usuário"), bg=bg, fg=TEMA["eyebrow"],
                          font=fonte(7, "semi"), anchor="w", wraplength=150, justify="left")
            l1.pack(anchor="w", fill=tk.X)
            l2 = tk.Label(textos, text=nome_curto(usuario.get("nome", "")), bg=bg, fg=TEMA["titulo"],
                          font=fonte(10, "semi"), anchor="w")
            l2.pack(anchor="w")
            widgets_clicaveis += [textos, l1, l2]
        for w in widgets_clicaveis:
            w.bind("<Button-1>", self._menu_usuario)

        tk.Frame(c, bg=TEMA["linha"], height=1).pack(fill=tk.X)

        if not self.recolhida:
            tk.Label(c, text=espacar("Navegação"), bg=bg, fg=TEMA["eyebrow"],
                     font=fonte(7, "semi")).pack(anchor="w", padx=14, pady=(16, 8))
        else:
            tk.Frame(c, bg=bg, height=12).pack()

        ativo = app.navegacao_ativa
        itens = [
            ("inicio", "Início", Icone.INICIO, app.abrir_tela_home),
            ("vrf", "Verificações (VRF)", Icone.LISTA_CHECK, app.abrir_tela_verificacao),
            ("pdf", "Validação Pranchas (PDF)", Icone.DOCUMENTO, app.abrir_tela_projetos_pdf),
            ("ifc", "Validação Modelo (IFC)", Icone.CUBO, app.abrir_tela_projetos_ifc),
            ("consulta", "Consulta - Gerenciar Registros", Icone.PRANCHETA, app.abrir_tela_consulta),
            ("dashboard", "Dashboard Gráficos e KPIs", Icone.GRAFICO, app.abrir_tela_dashboard),
        ]
        if eh_administrador(usuario):
            itens.append(("usuarios", "Gerenciar Usuários", Icone.PESSOAS, app.abrir_tela_usuarios))
        largura_item = self.largura - 24
        for chave, texto, glifo, comando in itens:
            ItemNavegacao(c, texto, glifo, comando, selecionado=ativo[0] == chave,
                          recolhido=self.recolhida, largura=largura_item).pack(anchor="w", pady=2)
            if chave == "dashboard" and ativo[0] == "dashboard" and not self.recolhida:
                self._submenu_dashboard(c, ativo[1], largura_item)

        rodape = tk.Frame(c, bg=bg)
        rodape.pack(side=tk.BOTTOM, fill=tk.X)
        ItemNavegacao(rodape, "Ajuda e suporte", Icone.AJUDA, self._ajuda,
                      recolhido=self.recolhida, largura=largura_item).pack(anchor="w")

    def _submenu_dashboard(self, c, sub_ativo, largura):
        sub = tk.Frame(c, bg=self.cor)
        sub.pack(fill=tk.X, pady=(2, 4))
        tk.Frame(sub, bg=TEMA["linha"], width=1).pack(side=tk.LEFT, fill=tk.Y, padx=(24, 10))
        lista = tk.Frame(sub, bg=self.cor)
        lista.pack(side=tk.LEFT, fill=tk.X)
        for chave, texto in (("visao", "Visão geral"), ("equipe", "Equipe"),
                             ("conformidade", "Conformidade"), ("relatorio", "Relatório detalhado")):
            ItemNavegacao(lista, texto, None, lambda k=chave: self.app.abrir_tela_dashboard(k),
                          selecionado=sub_ativo == chave, sub=True, largura=largura - 35
                          ).pack(anchor="w", pady=1)

    def _menu_usuario(self, evento):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        menu.add_command(label="Obra / disciplina da sessão…", command=self.app.abrir_dialogo_sessao)
        menu.add_command(label="Trocar senha…", command=self.app.trocar_minha_senha)
        menu.add_separator()
        menu.add_command(label="Sair (trocar de usuário)", command=self.app.sair)
        menu.tk_popup(evento.x_root, evento.y_root)

    def _ajuda(self):
        """Abre o formulário de abertura de chamados da Cadari (executável
        na rede). Sem acesso a ele (rede fora / arquivo movido), mostra o
        resumo de ajuda e o caminho esperado."""
        if os.path.exists(CHAMADOS_EXE):
            # confirmação: evita abrir o formulário por um clique acidental
            if not messagebox.askyesno(
                    "Abrir chamado",
                    "Você será direcionado ao formulário de Abertura de Chamados "
                    "da TI Cadari, para relatar um problema ou pedir suporte.\n\n"
                    "Tem certeza de que deseja abrir um chamado?",
                    icon="warning", default="no"):
                return
            try:
                os.startfile(CHAMADOS_EXE)
                return
            except OSError as erro:
                messagebox.showerror("Ajuda e suporte",
                                     f"Não foi possível abrir o formulário de chamados:\n{CHAMADOS_EXE}\n\n{erro}")
                return
        messagebox.showinfo(
            "Ajuda e suporte",
            f"Formulário de abertura de chamados não encontrado em:\n{CHAMADOS_EXE}\n"
            "Verifique a conexão com a rede (unidade Z:).\n\n"
            "Cadari Vizzo — Visualizador de Projetos\n\n"
            "• Validação Pranchas (PDF): marque problemas direto nas pranchas.\n"
            "• Validação Modelo (IFC): visualize o modelo 3D, marque problemas e rode o clash detection.\n"
            "• Consulta: pesquise e gerencie todos os registros.\n"
            "• Dashboard: indicadores e gráficos por projeto e equipe.\n\n"
            "Dúvidas ou problemas: fale com o Setor BIM.",
        )


class BotaoRedondo(tk.Canvas):
    def __init__(self, parent, glifo, comando, tamanho=38, ponto=False):
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0,
                         width=tamanho, height=tamanho, cursor="hand2")
        self.glifo, self.comando, self.tamanho, self.ponto = glifo, comando, tamanho, ponto
        self._hover = False
        self._desenhar()
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<ButtonRelease-1>", lambda e: self.comando(e))

    def _set(self, v):
        self._hover = v
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        t = self.tamanho
        retangulo_arredondado(self, 0, 0, t, t, t // 2,
                              TEMA["sidebar_sel"] if self._hover else TEMA["card"], TEMA["card_borda"])
        self.create_text(t / 2, t / 2, text=self.glifo, font=(FONTE_ICONE, 12), fill=TEMA["titulo"])
        if self.ponto:
            self.create_oval(t - 13, 7, t - 7, 13, fill="#D9534F", outline=TEMA["card"], width=1)


class BarraTopo(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        linha = tk.Frame(self, bg=TEMA["pagina"])
        linha.pack(fill=tk.X, padx=(24, 20), pady=10)

        self.busca = CampoArredondado(linha, placeholder="Buscar projetos, arquivos ou responsáveis...",
                                      icone_esquerda=Icone.BUSCA, largura=470, altura=40,
                                      cor=TEMA["campo"], borda=TEMA["campo"], extra_direita=48)
        self.busca.pack(side=tk.LEFT)
        self.busca.bind("<Configure>", self._desenhar_atalho, add="+")
        self.busca.entry.bind("<Return>", self._buscar)
        self.busca.entry.bind("<Escape>", lambda e: (self.busca.set(""), self.focus_set()))

        direita = tk.Frame(linha, bg=TEMA["pagina"])
        direita.pack(side=tk.RIGHT)
        pendentes = issues_pendentes_de(app.issues, (app.usuario_atual or {}).get("nome"))
        BotaoRedondo(direita, Icone.SOL if TEMA.esta_escuro() else Icone.OLHO if TEMA.eh_daltonico()
                     else Icone.LUA, app.abrir_menu_tema).pack(side=tk.LEFT, padx=6)
        BotaoRedondo(direita, Icone.SINO, self._notificacoes, ponto=bool(pendentes)).pack(side=tk.LEFT)

        tk.Frame(self, bg=TEMA["card_borda"], height=1).pack(fill=tk.X, side=tk.BOTTOM)

    def _desenhar_atalho(self, evento):
        c = self.busca
        c.delete("atalho")
        x1 = evento.width - 10
        retangulo_arredondado(c, x1 - 40, 9, x1, evento.height - 9, 5, TEMA["card"], TEMA["card_borda"],
                              tag="atalho")
        c.create_text(x1 - 20, evento.height / 2, text="Ctrl K", font=fonte(7), fill=TEMA["texto_fraco"],
                      tags=("atalho",))

    def focar_busca(self):
        self.busca.entry.focus_set()
        self.busca.entry.select_range(0, tk.END)

    def _buscar(self, _evento=None):
        texto = self.busca.get().strip()
        self.app.abrir_tela_consulta(busca=texto)

    def _notificacoes(self, evento):
        app = self.app
        pendentes = issues_pendentes_de(app.issues, (app.usuario_atual or {}).get("nome"))
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        if not pendentes:
            menu.add_command(label="Nenhuma pendência atribuída a você", state="disabled")
        for issue in pendentes[:10]:
            rotulo = f"#{issue['id']} · {issue.get('obra') or '—'} · {(issue.get('titulo') or '')[:40]} ({issue.get('status')})"
            menu.add_command(label=rotulo, command=lambda i=issue["id"]: app.abrir_tela_consulta(issue_id=i))
        if len(pendentes) > 10:
            menu.add_separator()
            menu.add_command(label=f"Ver todas ({len(pendentes)})…",
                             command=lambda: app.abrir_tela_consulta(atribuido=app.usuario_atual.get("nome")))
        menu.tk_popup(evento.x_root - 260, evento.y_root + 16)
