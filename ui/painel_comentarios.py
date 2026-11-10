"""Painel à direita do visualizador de PDF (protótipo Figma), com duas
abas:

- **Comentários**: os problemas (issues) desta prancha como cartões de
  comentário — quem registrou, quando, página, disciplina, status,
  respostas (histórico) e as ações (responder, mudar status, editar,
  excluir). O campo do topo cria um problema novo no local marcado na
  prancha com a ferramenta "Comentar"; "@nome" no texto sugere o
  responsável.
- **Certificação**: o selo carimbado define o status da prancha (ver
  certificacao.py) — status atual, selos disponíveis para aplicar e o
  histórico de selos do documento."""
import os
import tkinter as tk
import unicodedata
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from auth.usuarios import carregar_usuarios
from certificacao import (
    ATIVO,
    REMOVIDO,
    SUBSTITUIDO,
    estado_selo,
    info_selo,
    listar_selos,
    selos_do_documento,
    status_certificacao,
    tom_claro,
)
from config import LISTA_STATUS, LISTA_TIPOS_PDF, TEMA, TIPO_PADRAO_PDF
from dashboard.dados_dashboard import _parse_data
from dashboard.dados_painel import rotulo_dia_hora, ultima_movimentacao
from dialogs import DialogEditarIssue
from ui.corretor import ativar_corretor
from ui.componentes import (
    FONTE_ICONE,
    AreaRolavel,
    Avatar,
    Botao,
    CampoArredondado,
    Cartao,
    ComboArredondado,
    Icone,
    Pilula,
    espacar,
    fonte,
    icone,
    pilula_status,
    rotulo,
    separador,
)
from utils import agora_str, atualizar_data_modificacao

LARGURA_PAINEL = 400
MANTER_STATUS = "Manter status"
ESCOPOS = {"documento": "Todos os comentários", "pagina": "Só desta página",
           "abertos": "Em aberto", "fechados": "Fechados", "meus": "Atribuídos a mim"}
ORDENS = {"recentes": "Mais recentes", "antigos": "Mais antigos", "numero": "Por número"}
_CACHE_MINIATURAS = {}


def _normalizar(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def resolver_mencao(texto, usuarios):
    """Primeiro "@fulano" do texto que corresponda a um usuário ativo
    (pelo nome de usuário, pelo primeiro nome ou pelo nome completo sem
    espaços) -> nome completo; ou None."""
    for palavra in (texto or "").split():
        if not palavra.startswith("@") or len(palavra) < 3:
            continue
        alvo = _normalizar(palavra[1:].strip(".,;:!?"))
        for u in usuarios:
            if not u.get("ativo", True):
                continue
            nome = u.get("nome") or ""
            candidatos = {_normalizar(u.get("nome_usuario")), _normalizar(nome.replace(" ", "")),
                          _normalizar((nome.split() or [""])[0])}
            if alvo in candidatos:
                return nome
    return None


def titulo_do_texto(texto, limite=60):
    primeira = (texto or "").strip().splitlines()[0].strip() if (texto or "").strip() else ""
    if not primeira:
        return "Nova Revisão"
    return primeira if len(primeira) <= limite else primeira[: limite - 1] + "…"


def miniatura_selo(caminho, tamanho, master):
    chave = (caminho, tamanho)
    if chave not in _CACHE_MINIATURAS:
        try:
            img = Image.open(caminho).convert("RGBA")
            img.thumbnail((tamanho, tamanho), Image.LANCZOS)
        except Exception:
            img = Image.new("RGBA", (tamanho, tamanho), (200, 200, 200, 255))
        _CACHE_MINIATURAS[chave] = img
    return ImageTk.PhotoImage(_CACHE_MINIATURAS[chave], master=master)


class PainelComentarios(tk.Frame):
    def __init__(self, parent, viewer):
        super().__init__(parent, bg=TEMA["card"], width=LARGURA_PAINEL)
        self.viewer = viewer
        self.app = viewer.app
        self.aba = "comentarios"
        self.escopo = "documento"
        self.ordem = "recentes"
        self._cartoes = {}
        self._fotos = []
        self.selo_escolhido = None
        self._selos = listar_selos()
        if self._selos:
            self.selo_escolhido = self._selos[0]["caminho"]

        self._montar_abas()
        self.corpo_comentarios = tk.Frame(self, bg=TEMA["card"])
        self.corpo_certificacao = tk.Frame(self, bg=TEMA["card"])
        self._montar_comentarios()
        self._montar_certificacao_base()
        self.mostrar_aba("comentarios")

    # ---------- abas ----------
    def _montar_abas(self):
        self.barra_abas = tk.Frame(self, bg=TEMA["card"])
        self.barra_abas.pack(fill=tk.X, padx=20, pady=(14, 0))
        self._abas = {}
        for chave, texto in (("comentarios", "Comentários"), ("certificacao", "Certificação")):
            f = tk.Frame(self.barra_abas, bg=TEMA["card"], cursor="hand2")
            f.pack(side=tk.LEFT, padx=(0, 22))
            linha = tk.Frame(f, bg=TEMA["card"])
            linha.pack()
            lbl = tk.Label(linha, text=texto, bg=TEMA["card"], font=fonte(10, "semi"), cursor="hand2")
            lbl.pack(side=tk.LEFT)
            contagem = tk.Frame(linha, bg=TEMA["card"])
            contagem.pack(side=tk.LEFT, padx=(6, 0))
            sublinhado = tk.Frame(f, height=2, bg=TEMA["card"])
            sublinhado.pack(fill=tk.X, pady=(10, 0))
            for w in (f, linha, lbl):
                w.bind("<Button-1>", lambda e, k=chave: self.mostrar_aba(k))
            self._abas[chave] = (lbl, sublinhado, contagem)
        fechar = icone(self.barra_abas, Icone.FECHAR, 10, cor=TEMA["titulo"], cursor="hand2")
        fechar.pack(side=tk.RIGHT, anchor="n", pady=(2, 0))
        fechar.bind("<Button-1>", lambda e: self.viewer.ocultar_painel())
        tk.Frame(self, bg=TEMA["linha"], height=1).pack(fill=tk.X)

    def mostrar_aba(self, chave):
        self.aba = chave
        for k, (lbl, sublinhado, _c) in self._abas.items():
            ativo = k == chave
            lbl.config(fg=TEMA["titulo"] if ativo else TEMA["texto_fraco"])
            sublinhado.config(bg=TEMA["acento"] if ativo else TEMA["card"])
        self.corpo_comentarios.pack_forget()
        self.corpo_certificacao.pack_forget()
        if chave == "comentarios":
            self.corpo_comentarios.pack(fill=tk.BOTH, expand=True)
        else:
            self.corpo_certificacao.pack(fill=tk.BOTH, expand=True)
            self.atualizar_certificacao()

    def _contagem_aba(self, chave, n):
        caixa = self._abas[chave][2]
        for w in caixa.winfo_children():
            w.destroy()
        if n:
            Pilula(caixa, str(n), cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=18, tamanho_fonte=7).pack()

    # ---------- comentários ----------
    def _montar_comentarios(self):
        c = self.corpo_comentarios
        compositor = Cartao(c, padding=(0, 0), raio=10)
        compositor.pack(fill=tk.X, padx=20, pady=(18, 0))
        cc = compositor.corpo
        # título já preenchido com um nome genérico aceitável ("Problema 102"):
        # muitas issues são curtas e o título já descreve a tarefa
        self.ent_titulo = CampoArredondado(cc, largura=10, altura=36, cor=TEMA["card"], borda=None,
                                           tamanho_fonte=10)
        self.ent_titulo.entry.config(font=fonte(10, "semi"))
        self.ent_titulo.pack(fill=tk.X, padx=2, pady=(4, 0))
        self._sugerir_titulo()
        tk.Frame(cc, bg=TEMA["linha"], height=1).pack(fill=tk.X, padx=14)
        self.txt_novo = tk.Text(cc, height=2, width=1, wrap="word", relief="flat", bd=0, highlightthickness=0,
                                bg=TEMA["card"], fg=TEMA["titulo"], insertbackground=TEMA["titulo"],
                                font=fonte(10), padx=14, pady=12)
        self.txt_novo.pack(fill=tk.X)
        self._placeholder = "Descrição (opcional) — mencione alguém com @ para atribuir..."
        self._ph = False
        self.txt_novo.bind("<FocusIn>", lambda e: self._tirar_placeholder())
        self.txt_novo.bind("<FocusOut>", lambda e: self._por_placeholder())
        self.txt_novo.bind("<Control-Return>", lambda e: (self._comentar(), "break")[1])
        self._por_placeholder()
        ativar_corretor(self.txt_novo)
        tk.Frame(cc, bg=TEMA["card_borda"], height=1).pack(fill=tk.X)
        campos = tk.Frame(cc, bg=TEMA["card"])
        campos.pack(fill=tk.X, padx=12, pady=(8, 0))
        campos.columnconfigure(0, weight=1, uniform="comp")
        campos.columnconfigure(1, weight=1, uniform="comp")
        self.cb_tipo = ComboArredondado(campos, LISTA_TIPOS_PDF, largura=10, altura=32)
        self.cb_tipo.set(TIPO_PADRAO_PDF)
        self.cb_tipo.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.cb_para = ComboArredondado(campos, [], icone_esquerda=Icone.PESSOA, largura=10, altura=32,
                                        editavel=True, filtrar=True, placeholder="Para quem?")
        self.cb_para.grid(row=0, column=1, sticky="ew")
        self.atualizar_responsaveis()
        rodape = tk.Frame(cc, bg=TEMA["card"])
        rodape.pack(fill=tk.X, padx=12, pady=8)
        self.lbl_pagina = rotulo(rodape, "Página —", 9, cor=TEMA["texto"])
        self.lbl_pagina.pack(side=tk.LEFT)
        Botao(rodape, "Atribuição", variante="link", icone=Icone.EDITAR, altura=26, tamanho_fonte=8,
              comando=self.editar_atribuicao).pack(side=tk.LEFT, padx=(10, 0))
        Botao(rodape, "Comentar", variante="primario", altura=34, tamanho_fonte=10,
              comando=self._comentar).pack(side=tk.RIGHT)

        self.lbl_dica = rotulo(c, "", 8, cor=TEMA["texto_fraco"], wraplength=350, justify="left")
        self.lbl_dica.pack(anchor="w", padx=22, pady=(6, 0))

        filtros = tk.Frame(c, bg=TEMA["card"])
        filtros.pack(fill=tk.X, padx=20, pady=(10, 4))
        self.btn_escopo = Botao(filtros, ESCOPOS[self.escopo], variante="link", icone_direita=Icone.CHEVRON_BAIXO,
                                altura=24, tamanho_fonte=9, negrito=False, comando=self._menu_escopo)
        self.btn_escopo.pack(side=tk.LEFT)
        self.btn_ordem = Botao(filtros, ORDENS[self.ordem], variante="link", icone_direita=Icone.CHEVRON_BAIXO,
                               altura=24, tamanho_fonte=9, negrito=False, comando=self._menu_ordem)
        self.btn_ordem.pack(side=tk.RIGHT)

        self.area = AreaRolavel(c, cor=TEMA["card"])
        self.area.pack(fill=tk.BOTH, expand=True, padx=(20, 6))
        self.lista = self.area.interno
        self._atualizar_dica()

    def _tirar_placeholder(self):
        if self._ph:
            self._ph = False
            self.txt_novo.delete("1.0", tk.END)
            self.txt_novo.config(fg=TEMA["titulo"])

    def _por_placeholder(self):
        if not self.txt_novo.get("1.0", tk.END).strip():
            self._ph = True
            self.txt_novo.delete("1.0", tk.END)
            self.txt_novo.insert("1.0", self._placeholder)
            self.txt_novo.config(fg=TEMA["texto_fraco"])

    def texto_novo(self):
        return "" if self._ph else self.txt_novo.get("1.0", tk.END).strip()

    def _atualizar_dica(self, erro=None):
        if erro:
            self.lbl_dica.config(text=erro, fg=TEMA["pill_vermelho"][1])
            return
        if self.viewer.local_pendente:
            pagina = self.viewer.local_pendente[0] + 1
            texto = f"Local marcado na página {pagina:02d}. Escreva o comentário e clique em Comentar."
        else:
            texto = "Use a ferramenta Comentar e clique na prancha para marcar o local do problema."
        self.lbl_dica.config(text=texto, fg=TEMA["texto_fraco"])

    def marcar_local_pendente(self):
        self.mostrar_aba("comentarios")
        self._atualizar_dica()
        if not self.ent_titulo.get().strip():
            self._sugerir_titulo()
        self.ent_titulo.entry.focus_set()
        self.ent_titulo.entry.select_range(0, tk.END)

    def _comentar(self):
        if not self.viewer.pdf_document:
            self._atualizar_dica("Abra uma prancha (PDF) primeiro.")
            return
        if not self.viewer.local_pendente:
            self._atualizar_dica("Primeiro marque o local: ferramenta Comentar e um clique na prancha.")
            self.viewer.set_tool("pin")
            return
        texto = self.texto_novo()
        responsavel = resolver_mencao(texto, carregar_usuarios()) or self.cb_para.get().strip() or None
        titulo = self.ent_titulo.get().strip() or None
        novo_id = self.viewer.criar_issue_no_local(texto, self.cb_tipo.get() or TIPO_PADRAO_PDF, responsavel,
                                                    titulo=titulo)
        if novo_id is None:
            return
        self.txt_novo.delete("1.0", tk.END)
        self._por_placeholder()
        self._sugerir_titulo()
        self._atualizar_dica()

    def _sugerir_titulo(self):
        from utils import proximo_id
        self.ent_titulo.set(f"Problema {proximo_id(self.app.issues)}")

    def atualizar_responsaveis(self):
        """Valores do "Para": padrão e coautores da verificação primeiro,
        depois os demais usuários ativos."""
        from auth.usuarios import listar_nomes_ativos
        sessao = self.app.sessao
        primeiros = [n for n in [sessao.get("atribuido_para")] + list(sessao.get("projetistas") or []) if n]
        resto = [n for n in listar_nomes_ativos() if n not in primeiros]
        self.cb_para.valores = primeiros + resto
        self.cb_para.combo["values"] = self.cb_para.valores
        self.cb_para.set(sessao.get("atribuido_para") or "")

    def editar_atribuicao(self):
        from dialogs import DialogAtribuicao
        dialogo = DialogAtribuicao(self.winfo_toplevel(), self.app.sessao)
        if dialogo.padrao:
            self.app.sessao["atribuido_para"] = dialogo.padrao
            self.app.sessao["projetistas"] = dialogo.outros
            self.atualizar_responsaveis()
            self.viewer._atualizar_cabecalho()

    def _menu_escopo(self):
        self._menu(ESCOPOS, "escopo", self.btn_escopo)

    def _menu_ordem(self):
        self._menu(ORDENS, "ordem", self.btn_ordem)

    def _menu(self, opcoes, atributo, botao):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        for chave, texto in opcoes.items():
            menu.add_command(label=("✓  " if getattr(self, atributo) == chave else "     ") + texto,
                             command=lambda k=chave: self._definir_filtro(atributo, k, opcoes, botao))
        menu.tk_popup(botao.winfo_rootx(), botao.winfo_rooty() + botao.winfo_height())

    def _definir_filtro(self, atributo, chave, opcoes, botao):
        setattr(self, atributo, chave)
        botao.config_texto(opcoes[chave])
        self.atualizar_lista()

    # ---------- dados ----------
    def issues_do_documento(self):
        caminho = self.viewer.current_pdf_path
        if not caminho:
            return []
        return [i for i in self.app.issues
                if i.get("tipo_doc", "pdf") == "pdf" and i.get("filepath") == caminho]

    def _issues_filtradas(self):
        issues = self.issues_do_documento()
        nome = (self.app.usuario_atual or {}).get("nome")
        if self.escopo == "pagina":
            issues = [i for i in issues if i.get("page") == self.viewer.current_page]
        elif self.escopo == "abertos":
            issues = [i for i in issues if i.get("status") != "Fechado"]
        elif self.escopo == "fechados":
            issues = [i for i in issues if i.get("status") == "Fechado"]
        elif self.escopo == "meus":
            issues = [i for i in issues if i.get("atribuido_para") == nome]
        if self.ordem == "numero":
            return sorted(issues, key=lambda i: i.get("id", 0))
        chave = lambda i: (ultima_movimentacao(i) or _parse_data("01/01/1900"), i.get("id", 0))  # noqa: E731
        return sorted(issues, key=chave, reverse=self.ordem == "recentes")

    def _buscar(self, issue_id):
        return next((i for i in self.app.issues if i.get("id") == issue_id), None)

    # ---------- lista de cartões ----------
    def atualizar_lista(self):
        pagina = self.viewer.current_page + 1 if self.viewer.pdf_document else None
        self.lbl_pagina.config(text=f"Página {pagina:02d}" if pagina else "Página —")
        self._contagem_aba("comentarios", len(self.issues_do_documento()))
        for w in self.lista.winfo_children():
            w.destroy()
        self._cartoes = {}
        self._fotos = []
        issues = self._issues_filtradas()
        if not issues:
            vazio = tk.Frame(self.lista, bg=TEMA["card"])
            vazio.pack(fill=tk.X, pady=30)
            icone(vazio, Icone.MENSAGEM, 18, cor=TEMA["texto_fraco"]).pack()
            rotulo(vazio, "Nenhum comentário por aqui", 10, "semi").pack(pady=(8, 2))
            rotulo(vazio, "Marque um ponto na prancha com a ferramenta Comentar.", 9,
                   cor=TEMA["texto_fraco"]).pack()
        for issue in issues:
            self._cartao(issue)
        self._atualizar_dica()
        if self.viewer.issue_selecionada_id in self._cartoes:
            self._destacar(self.viewer.issue_selecionada_id)

    def _cartao(self, issue):
        bg = TEMA["card"]
        caixa = tk.Frame(self.lista, bg=bg)
        caixa.pack(fill=tk.X)
        marcador = tk.Frame(caixa, bg=bg, width=3)
        marcador.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10), pady=12)
        corpo = tk.Frame(caixa, bg=bg)
        corpo.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(16, 14), padx=(0, 8))
        self._cartoes[issue["id"]] = marcador

        topo = tk.Frame(corpo, bg=bg)
        topo.pack(fill=tk.X)
        bg_av, fg_av = TEMA["pill_azul"]
        Avatar(topo, issue.get("criado_por") or "?", tamanho=34, cor=bg_av, cor_texto=fg_av,
               tamanho_fonte=8).pack(side=tk.LEFT, anchor="n", padx=(0, 10))
        textos = tk.Frame(topo, bg=bg)
        textos.pack(side=tk.LEFT, fill=tk.X, expand=True)
        rotulo(textos, issue.get("criado_por") or "—", 10, "semi").pack(anchor="w")
        meta = f"{rotulo_dia_hora(_parse_data(issue.get('data_criacao')))}  ·  Pág. {issue.get('page', 0) + 1:02d}" \
               f"  ·  #{issue['id']}"
        rotulo(textos, meta, 8, cor=TEMA["texto_fraco"]).pack(anchor="w", pady=(2, 0))
        mais = tk.Label(topo, text=Icone.RETICENCIAS, bg=bg, fg=TEMA["titulo"], font=(FONTE_ICONE, 12),
                        cursor="hand2")
        mais.pack(side=tk.RIGHT, anchor="n")
        mais.bind("<Button-1>", lambda e, i=issue: self._menu_issue(e, i))

        titulo = issue.get("titulo") or ""
        desc = issue.get("desc") or ""
        clicaveis = [caixa, corpo, textos]
        if titulo and titulo != desc[: len(titulo)]:
            lbl = rotulo(corpo, titulo, 10, "semi", wraplength=320, justify="left", cursor="hand2")
            lbl.pack(anchor="w", pady=(12, 0))
            clicaveis.append(lbl)
        if desc:
            lbl = rotulo(corpo, desc, 10, cor=TEMA["texto"], wraplength=320, justify="left", cursor="hand2")
            lbl.pack(anchor="w", pady=(6 if titulo else 12, 0))
            clicaveis.append(lbl)
        if issue.get("atribuido_para"):
            rotulo(corpo, f"Responsável: {issue['atribuido_para']}", 8, cor=TEMA["texto_fraco"]
                   ).pack(anchor="w", pady=(6, 0))

        etiquetas = tk.Frame(corpo, bg=bg)
        etiquetas.pack(fill=tk.X, pady=(12, 0))
        if issue.get("disciplina"):
            Pilula(etiquetas, issue["disciplina"], cores=TEMA["pill_dourado"], altura=24,
                   tamanho_fonte=8).pack(side=tk.LEFT, padx=(0, 6))
        pilula_status(etiquetas, issue.get("status") or "—", altura=24, tamanho_fonte=8).pack(side=tk.LEFT)
        Botao(etiquetas, "Responder", variante="link", altura=24, tamanho_fonte=9,
              comando=lambda i=issue, f=corpo: self._abrir_resposta(i, f)).pack(side=tk.RIGHT)

        for com in issue.get("historico") or []:
            self._resposta(corpo, com)

        for w in clicaveis:
            w.bind("<Button-1>", lambda e, i=issue: self.viewer.ir_para_issue(i))
        separador(self.lista)

    def _resposta(self, parent, com):
        bg = TEMA["card"]
        r = tk.Frame(parent, bg=bg)
        r.pack(fill=tk.X, pady=(10, 0), padx=(14, 0))
        tk.Frame(r, bg=TEMA["linha"], width=2).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        conteudo = tk.Frame(r, bg=bg)
        conteudo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        linha = tk.Frame(conteudo, bg=bg)
        linha.pack(anchor="w")
        rotulo(linha, com.get("autor") or "Comentário", 9, "semi").pack(side=tk.LEFT)
        rotulo(linha, f"  {rotulo_dia_hora(_parse_data(com.get('data')))}", 8, cor=TEMA["texto_fraco"]
               ).pack(side=tk.LEFT)
        rotulo(conteudo, com.get("texto", ""), 9, cor=TEMA["texto"], wraplength=290, justify="left"
               ).pack(anchor="w", pady=(2, 0))

    def _abrir_resposta(self, issue, corpo):
        if getattr(corpo, "_resposta_aberta", False):
            return
        corpo._resposta_aberta = True
        bg = TEMA["card"]
        caixa = Cartao(corpo, padding=(0, 0), raio=8)
        caixa.pack(fill=tk.X, pady=(10, 0))
        txt = tk.Text(caixa.corpo, height=2, width=1, wrap="word", relief="flat", bd=0, highlightthickness=0,
                      bg=bg, fg=TEMA["titulo"], insertbackground=TEMA["titulo"], font=fonte(9), padx=10, pady=8)
        txt.pack(fill=tk.X)
        ativar_corretor(txt)
        rodape = tk.Frame(caixa.corpo, bg=bg)
        rodape.pack(fill=tk.X, padx=8, pady=(0, 8))
        cb = ComboArredondado(rodape, [MANTER_STATUS] + LISTA_STATUS, largura=130, altura=30)
        cb.set(MANTER_STATUS)
        cb.pack(side=tk.LEFT)

        def fechar():
            corpo._resposta_aberta = False
            caixa.destroy()

        def enviar():
            texto = txt.get("1.0", tk.END).strip()
            novo_status = cb.get()
            if not texto and novo_status == MANTER_STATUS:
                return
            self.responder(issue, texto, None if novo_status == MANTER_STATUS else novo_status)

        Botao(rodape, "Enviar", variante="primario", altura=30, tamanho_fonte=9, comando=enviar).pack(side=tk.RIGHT)
        Botao(rodape, "Cancelar", variante="fantasma", altura=30, tamanho_fonte=9, comando=fechar
              ).pack(side=tk.RIGHT, padx=(0, 6))
        txt.focus_set()

    def _destacar(self, issue_id):
        for k, marcador in self._cartoes.items():
            marcador.config(bg=TEMA["acento"] if k == issue_id else TEMA["card"])

    def selecionar_issue(self, issue_id):
        self.mostrar_aba("comentarios")
        if issue_id not in self._cartoes:
            self.escopo = "documento"
            self.btn_escopo.config_texto(ESCOPOS[self.escopo])
            self.atualizar_lista()
        self._destacar(issue_id)
        marcador = self._cartoes.get(issue_id)
        if marcador is not None:
            self.update_idletasks()
            total = max(1, self.lista.winfo_height())
            self.area.canvas.yview_moveto(max(0.0, (marcador.master.winfo_y() - 10) / total))

    # ---------- ações sobre um problema ----------
    def _registrar(self, issue, texto):
        issue.setdefault("historico", []).append({
            "data": agora_str()[:16], "texto": texto, "autor": self.app.sessao.get("nome", ""),
        })

    def _salvar(self, issue):
        atualizar_data_modificacao(issue)
        self.app.salvar_banco_dados()
        self.viewer.draw_pins()
        self.atualizar_lista()

    def responder(self, issue, texto, novo_status=None):
        if texto:
            self._registrar(issue, texto)
        if novo_status and novo_status != issue.get("status"):
            self._registrar(issue, f"Status alterado de {issue.get('status')} para {novo_status}.")
            issue["status"] = novo_status
        self._salvar(issue)

    def alterar_status(self, issue, novo_status):
        self.responder(issue, "", novo_status)

    def _menu_issue(self, evento, issue):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        menu.add_command(label="Ir para o local na prancha", command=lambda: self.viewer.ir_para_issue(issue))
        status = tk.Menu(menu, tearoff=0, font=fonte(10))
        for s in LISTA_STATUS:
            status.add_command(label=("✓  " if issue.get("status") == s else "     ") + s,
                               command=lambda s=s: self.alterar_status(issue, s))
        menu.add_cascade(label="Alterar status", menu=status)
        menu.add_command(label="Editar…", command=lambda: self._editar(issue))
        menu.add_command(label="Copiar para outros locais…", command=lambda: self.viewer.iniciar_copia(issue))
        menu.add_separator()
        menu.add_command(label="Excluir", command=lambda: self._excluir(issue))
        menu.tk_popup(evento.x_root - 160, evento.y_root + 10)

    def _editar(self, issue):
        dialogo = DialogEditarIssue(self.winfo_toplevel(), issue, LISTA_TIPOS_PDF)
        if not dialogo.valores:
            return
        mudou = [k for k, v in dialogo.valores.items() if (issue.get(k) or "") != v]
        if not mudou:
            return
        if "status" in mudou:
            self._registrar(issue, f"Status alterado de {issue.get('status')} para {dialogo.valores['status']}.")
        outros = [k for k in mudou if k != "status"]
        if outros:
            self._registrar(issue, "Problema editado (" + ", ".join(outros) + ").")
        issue.update(dialogo.valores)
        self._salvar(issue)

    def _excluir(self, issue):
        if not messagebox.askyesno("Excluir", f"Excluir o problema #{issue['id']}? Essa ação não pode ser desfeita.",
                                   parent=self.winfo_toplevel()):
            return
        self.app.issues = [i for i in self.app.issues if i.get("id") != issue["id"]]
        if self.viewer.issue_selecionada_id == issue["id"]:
            self.viewer.issue_selecionada_id = None
        self.app.salvar_banco_dados()
        self.viewer.draw_pins()
        self.atualizar_lista()

    # ---------- certificação ----------
    def _montar_certificacao_base(self):
        self.area_cert = AreaRolavel(self.corpo_certificacao, cor=TEMA["card"])
        self.area_cert.pack(fill=tk.BOTH, expand=True, padx=(20, 6), pady=(14, 0))

    def atualizar_certificacao(self):
        viewer = self.viewer
        selos_doc = selos_do_documento(viewer.anotacoes, viewer.current_pdf_path) if viewer.current_pdf_path else []
        self._contagem_aba("certificacao", len(selos_doc))
        if self.aba != "certificacao":
            return
        p = self.area_cert.interno
        for w in p.winfo_children():
            w.destroy()
        self._fotos_cert = []
        bg = TEMA["card"]

        status = status_certificacao(viewer.anotacoes, viewer.current_pdf_path) if viewer.current_pdf_path else None
        cartao = Cartao(p, padding=(16, 14), raio=10,
                        cor=tom_claro(status["cor"], 0.88) if status and not TEMA.esta_escuro() else TEMA["campo"],
                        borda=None)
        cartao.pack(fill=tk.X, padx=(0, 10))
        cc = cartao.corpo
        rotulo(cc, espacar("Status da prancha"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
        linha = tk.Frame(cc, bg=cc["bg"])
        linha.pack(anchor="w", pady=(8, 0))
        if status:
            foto = miniatura_selo(status["caminho"], 44, self)
            self._fotos_cert.append(foto)
            tk.Label(linha, image=foto, bg=cc["bg"]).pack(side=tk.LEFT, padx=(0, 12))
            textos = tk.Frame(linha, bg=cc["bg"])
            textos.pack(side=tk.LEFT)
            rotulo(textos, f"{status['codigo']} · {status['descricao']}", 13, "semi",
                   cor=status["cor"] if not TEMA.esta_escuro() else TEMA["titulo"]).pack(anchor="w")
            detalhe = " · ".join(x for x in (status["autor"], status["data"][:16], f"Pág. {status['pagina'] + 1:02d}")
                                 if x)
            rotulo(textos, f"Certificado por {detalhe}", 8, cor=TEMA["texto"], wraplength=250,
                   justify="left").pack(anchor="w", pady=(2, 0))
        else:
            rotulo(linha, "Aguardando certificação", 13, "semi").pack(anchor="w")
            rotulo(cc, "Aplique um selo abaixo para definir o status desta prancha.", 8,
                   cor=TEMA["texto"]).pack(anchor="w", pady=(2, 0))

        rotulo(p, espacar("Selos disponíveis"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(18, 8))
        grade = tk.Frame(p, bg=bg)
        grade.pack(fill=tk.X, padx=(0, 10))
        grade.columnconfigure(0, weight=1, uniform="selo")
        grade.columnconfigure(1, weight=1, uniform="selo")
        if not self._selos:
            rotulo(grade, "Pasta de selos indisponível na rede.", 9, cor=TEMA["texto_fraco"]).grid(row=0, column=0)
        for n, selo in enumerate(self._selos):
            escolhido = selo["caminho"] == self.selo_escolhido
            tile = Cartao(grade, padding=(10, 10), raio=10,
                          borda=TEMA["primario"] if escolhido else "padrao",
                          cor=TEMA["sidebar_sel"] if escolhido else TEMA["card"])
            tile.grid(row=n // 2, column=n % 2, sticky="nsew", padx=(0 if n % 2 == 0 else 5, 5 if n % 2 == 0 else 0),
                      pady=(0, 10))
            t = tile.corpo
            foto = miniatura_selo(selo["caminho"], 40, self)
            self._fotos_cert.append(foto)
            img = tk.Label(t, image=foto, bg=t["bg"], cursor="hand2")
            img.pack(side=tk.LEFT, padx=(0, 8))
            textos = tk.Frame(t, bg=t["bg"], cursor="hand2")
            textos.pack(side=tk.LEFT, fill=tk.X)
            l1 = rotulo(textos, selo["codigo"], 10, "semi", cursor="hand2")
            l1.pack(anchor="w")
            l2 = rotulo(textos, selo["descricao"], 8, cor=TEMA["texto_fraco"], wraplength=100, justify="left",
                        cursor="hand2")
            l2.pack(anchor="w")
            for w in (tile, t, img, textos, l1, l2):
                w.bind("<Button-1>", lambda e, c=selo["caminho"]: self._escolher_selo(c))

        tamanho = tk.Frame(p, bg=bg)
        tamanho.pack(fill=tk.X, padx=(0, 10), pady=(4, 0))
        rotulo(tamanho, "Tamanho do selo", 9, cor=TEMA["texto"]).pack(side=tk.LEFT)
        self.lbl_tamanho = rotulo(tamanho, f"{int(viewer.tamanho_selo_atual)} pt", 9, "semi")
        self.lbl_tamanho.pack(side=tk.RIGHT)
        escala = ttk.Scale(p, from_=40, to=400, orient=tk.HORIZONTAL, command=self._ao_mudar_tamanho)
        escala.set(viewer.tamanho_selo_atual)
        escala.pack(fill=tk.X, padx=(0, 10), pady=(6, 12))

        Botao(p, "Aplicar selo na prancha", variante="primario", icone=Icone.SELO, altura=40, largura=10,
              comando=self._aplicar_selo).pack(fill=tk.X, padx=(0, 10))
        rotulo(p, "Depois de clicar, escolha o ponto da prancha onde o selo vai ficar. A prancha tem um selo só: "
                  "aplicar outro substitui o atual (o anterior fica no histórico). Para mudar o selo de lugar, "
                  "arraste-o com a ferramenta Selecionar.", 8,
               cor=TEMA["texto_fraco"], wraplength=340, justify="left").pack(anchor="w", pady=(6, 0))

        rotulo(p, espacar("Histórico de certificação"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(20, 8))
        if not selos_doc:
            rotulo(p, "Nenhum selo aplicado nesta prancha ainda.", 9, cor=TEMA["texto_fraco"]).pack(anchor="w")
        for a in reversed(selos_doc):
            info = info_selo(a.get("arquivo_selo"))
            linha = tk.Frame(p, bg=bg)
            linha.pack(fill=tk.X, padx=(0, 10), pady=(0, 10))
            foto = miniatura_selo(a.get("arquivo_selo"), 28, self)
            self._fotos_cert.append(foto)
            tk.Label(linha, image=foto, bg=bg).pack(side=tk.LEFT, padx=(0, 10))
            textos = tk.Frame(linha, bg=bg)
            textos.pack(side=tk.LEFT, fill=tk.X, expand=True)
            estado = estado_selo(a, viewer.anotacoes)
            rotulo(textos, f"{info['codigo']} · {info['descricao']}", 9, "semi").pack(anchor="w")
            rotulo(textos, " · ".join(x for x in (f"Pág. {a.get('page', 0) + 1:02d}", (a.get("data") or "")[:16],
                                                  a.get("autor") or "") if x),
                   8, cor=TEMA["texto_fraco"]).pack(anchor="w")
            if estado == SUBSTITUIDO:
                detalhe = "Substituído" + (f" em {a['substituido_em'][:16]}" if a.get("substituido_em") else "")
            elif estado == REMOVIDO:
                detalhe = "Removido" + (f" em {a['removido_em'][:16]}" if a.get("removido_em") else "") + \
                          (f" por {a['removido_por']}" if a.get("removido_por") else "")
            else:
                detalhe = "Na prancha" + (f" · movido em {a['movido_em'][:16]}" if a.get("movido_em") else "")
            rotulo(textos, detalhe, 8, "semi" if estado == ATIVO else "normal",
                   cor=info["cor"] if estado == ATIVO else TEMA["texto_fraco"]).pack(anchor="w")
            if estado == ATIVO:
                Botao(linha, "Remover", variante="link", altura=22, tamanho_fonte=8,
                      comando=lambda i=a["id"]: self._remover_selo(i)).pack(side=tk.RIGHT)

    def _escolher_selo(self, caminho):
        self.selo_escolhido = caminho
        self.atualizar_certificacao()

    def _ao_mudar_tamanho(self, valor):
        self.viewer.tamanho_selo_atual = max(20, float(valor))
        self.lbl_tamanho.config(text=f"{int(self.viewer.tamanho_selo_atual)} pt")

    def _aplicar_selo(self):
        if not self.viewer.pdf_document:
            messagebox.showinfo("Certificação", "Abra uma prancha (PDF) primeiro.", parent=self.winfo_toplevel())
            return
        if not self.selo_escolhido or not os.path.exists(self.selo_escolhido):
            messagebox.showwarning("Certificação", "Escolha um selo disponível.", parent=self.winfo_toplevel())
            return
        self.viewer.iniciar_colocacao_selo(self.selo_escolhido)

    def _remover_selo(self, anotacao_id):
        if messagebox.askyesno("Remover selo", "Remover o selo da prancha? Ele continua no histórico de "
                                               "certificação e a prancha volta a \"aguardando certificação\".",
                               parent=self.winfo_toplevel()):
            self.viewer.remover_anotacao(anotacao_id)

    # ---------- compatibilidade com PDFViewerFrame.sincronizar ----------
    def atualizar_obras(self):
        pass
