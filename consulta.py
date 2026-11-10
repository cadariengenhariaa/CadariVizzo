"""Tela de consulta e gestão de todos os registros (issues) vindos de PDF
e IFC — no estilo do protótipo Figma: busca, filtros, tabela em cartão
e painel de detalhes com o documento vinculado e o histórico."""
import os
import tkinter as tk
import unicodedata
from tkinter import messagebox, ttk

from auth.usuarios import listar_nomes_ativos
from config import LISTA_STATUS, TEMA
from ui.componentes import (
    Botao,
    Cartao,
    CampoArredondado,
    ComboArredondado,
    cores_status,
    Icone,
    Pilula,
    QuadradoIcone,
    Segmentado,
    cabecalho_pagina,
    espacar,
    fonte,
    imagem_pilula,
    pilula_status,
    rotulo,
)

TODOS = "Todos"
TODAS = "Todas"


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return texto.lower()


def _ultima_data(issue):
    if issue.get("data_modificacao"):
        return issue["data_modificacao"]
    hist = issue.get("historico", [])
    return hist[-1]["data"] if hist else "Sem movimentação"


class ConsultaFrame(tk.Frame):
    def __init__(self, parent, app, busca=None, issue_id=None, atribuido=None, obra=None):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self.issue_atual = None

        pagina = tk.Frame(self, bg=TEMA["pagina"])
        pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(24, 24))
        self.pagina = pagina

        self._montar_cabecalho()
        self._montar_filtros()
        self._montar_corpo()

        if busca:
            self.ent_busca.set(busca)
        if atribuido:
            self.cb_filtro_nome.set(atribuido)
        if obra:
            self.cb_filtro_obra.set(obra)
        self.atualizar_lista()
        if issue_id is not None:
            self.selecionar_issue(issue_id)

    # ---------- construção ----------
    def _montar_cabecalho(self):
        cab, direita = cabecalho_pagina(
            self.pagina, "Gestão de registros", "Consulta de registros",
            "Pesquise, filtre e acompanhe os problemas registrados em pranchas (PDF) e modelos (IFC).",
            migalhas=[("Início", self.app.abrir_tela_home), ("Consulta", None)])
        cab.pack(fill=tk.X, pady=(0, 18))
        botoes = tk.Frame(direita, bg=TEMA["pagina"])
        botoes.pack(anchor="e")
        Botao(botoes, "Atualizar obras", variante="secundario", icone=Icone.PASTA, altura=34, tamanho_fonte=9,
              comando=self.recarregar_obras).pack(side=tk.LEFT, padx=(0, 8))
        Botao(botoes, "Atualizar dados", variante="primario", icone=Icone.ATUALIZAR, altura=34, tamanho_fonte=9,
              comando=self.app.sincronizar_banco).pack(side=tk.LEFT)

    def _montar_filtros(self):
        cartao = Cartao(self.pagina, padding=(16, 14))
        cartao.pack(fill=tk.X, pady=(0, 14))
        c = cartao.corpo
        linha = tk.Frame(c, bg=c["bg"])
        linha.pack(fill=tk.X)

        self.ent_busca = CampoArredondado(linha, placeholder="Buscar por título, descrição, obra, arquivo...",
                                          icone_esquerda=Icone.BUSCA, largura=360, altura=38,
                                          cor=TEMA["campo"], borda=TEMA["campo"])
        self.ent_busca.pack(side=tk.LEFT, padx=(0, 12))
        self.ent_busca.entry.bind("<KeyRelease>", lambda e: self.atualizar_lista())

        def combo(valores, icone_, largura, editavel=False):
            cb = ComboArredondado(linha, valores, icone_esquerda=icone_, largura=largura, altura=38,
                                  editavel=editavel, filtrar=editavel)
            cb.pack(side=tk.LEFT, padx=(0, 10))
            cb.combo.bind("<<ComboboxSelected>>", lambda e: self.atualizar_lista(), add="+")
            return cb

        self.cb_filtro_nome = combo([TODOS] + listar_nomes_ativos(), Icone.PESSOA, 230)
        self.cb_filtro_nome.set(TODOS)
        self.cb_filtro_obra = combo([TODAS] + list(self.app.obras_lista), Icone.PASTA, 180, editavel=True)
        self.cb_filtro_obra.set(TODAS)
        self.cb_filtro_obra.combo.bind("<Return>", lambda e: self.atualizar_lista())
        self.cb_filtro_obra.combo.bind("<FocusOut>", lambda e: self.atualizar_lista(), add="+")
        self.cb_filtro_tipo_doc = combo([TODOS, "PDF", "IFC"], Icone.DOCUMENTO, 130)
        self.cb_filtro_tipo_doc.set(TODOS)

        Botao(linha, "Limpar filtros", variante="link", icone=Icone.FECHAR, altura=30, tamanho_fonte=9,
              comando=self.limpar_filtros).pack(side=tk.LEFT, padx=(6, 0))

        linha2 = tk.Frame(c, bg=c["bg"])
        linha2.pack(fill=tk.X, pady=(12, 0))
        rotulo(linha2, espacar("Status"), 8, "semi", cor=TEMA["eyebrow"]).pack(side=tk.LEFT, padx=(2, 12))
        self.seg_status = Segmentado(linha2, [TODOS] + LISTA_STATUS, valor=TODOS,
                                     comando=lambda v: self.atualizar_lista())
        self.seg_status.pack(side=tk.LEFT)

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
        rotulo(topo, "Registros", 13, "semi").pack(side=tk.LEFT)
        self._contagem = tk.Frame(topo, bg=c["bg"])
        self._contagem.pack(side=tk.RIGHT)

        tabela = tk.Frame(c, bg=c["bg"])
        tabela.pack(fill=tk.BOTH, expand=True)
        colunas = (
            ("ID", "ID", 50, "center"),
            ("Tipo", "Tipo", 55, "center"),
            ("Obra", "Obra", 85, "w"),
            ("Título", "Título", 220, "w"),
            ("Atribuído", "Atribuído a", 160, "w"),
            ("Data", "Movimentação", 140, "w"),
        )
        # a coluna da árvore (#0) mostra a pílula colorida de status — é a
        # única coluna do Treeview que aceita imagem
        self.tree_consulta = ttk.Treeview(tabela, columns=[c_[0] for c_ in colunas], show="tree headings",
                                          style="Cartao.Treeview")
        self.tree_consulta.heading("#0", text=espacar("Status"), anchor="w")
        self.tree_consulta.column("#0", width=118, minwidth=118, stretch=False, anchor="w")
        for col, texto, largura, ancora in colunas:
            self.tree_consulta.heading(col, text=espacar(texto) if col != "ID" else "ID", anchor=ancora)
            self.tree_consulta.column(col, width=largura, anchor=ancora, stretch=col in ("Título", "Atribuído"))
        self._pilulas = {
            status: imagem_pilula(status, cores_status(status), self, tamanho_fonte=12, largura=92)
            for status in LISTA_STATUS
        }
        self.tree_consulta.tag_configure("par", background=TEMA["card"])
        self.tree_consulta.tag_configure("impar", background=TEMA["pagina"])
        scrollbar = ttk.Scrollbar(tabela, orient=tk.VERTICAL, command=self.tree_consulta.yview,
                                  style="Fino.Vertical.TScrollbar")
        self.tree_consulta.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_consulta.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_consulta.bind("<<TreeviewSelect>>", self.mostrar_detalhes)

        detalhes = Cartao(corpo, padding=(20, 18), ajustar_altura=False)
        detalhes.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.painel_detalhes = detalhes.corpo
        self._detalhes_vazio()

    # ---------- lista ----------
    def _passa_filtros(self, issue):
        filtro_nome = self.cb_filtro_nome.get()
        filtro_status = self.seg_status.valor
        filtro_obra = self.cb_filtro_obra.get().strip()
        filtro_tipo_doc = self.cb_filtro_tipo_doc.get()
        busca = _normalizar(self.ent_busca.get().strip())

        atribuido = issue.get("atribuido_para", issue.get("atrib", ""))
        if filtro_nome not in (TODOS, "") and filtro_nome != atribuido:
            return False
        if filtro_status != TODOS and filtro_status != issue.get("status", ""):
            return False
        if filtro_obra not in (TODAS, "") and filtro_obra != issue.get("obra", ""):
            return False
        if filtro_tipo_doc not in (TODOS, "") and filtro_tipo_doc.lower() != issue.get("tipo_doc", "pdf"):
            return False
        if busca:
            campos = (issue.get("id"), issue.get("titulo"), issue.get("desc"), issue.get("obra"),
                      atribuido, issue.get("criado_por"), issue.get("filepath"), issue.get("disciplina"),
                      issue.get("tipo"), issue.get("ifc_nome_elemento"))
            if not any(busca in _normalizar(c) for c in campos):
                return False
        return True

    def atualizar_lista(self, event=None):
        selecionado = self.issue_atual["id"] if self.issue_atual else None
        self.tree_consulta.delete(*self.tree_consulta.get_children())
        n = 0
        for issue in self.app.issues:
            if not self._passa_filtros(issue):
                continue
            status = issue.get("status", "") or "Desconhecido"
            extra = {"image": self._pilulas[status]} if status in self._pilulas else {"text": status}
            self.tree_consulta.insert("", tk.END, iid=str(issue["id"]), tags=("par" if n % 2 == 0 else "impar",),
                                      values=(
                                          issue["id"],
                                          issue.get("tipo_doc", "pdf").upper(),
                                          issue.get("obra") or "—",
                                          issue.get("titulo", "Sem Título"),
                                          issue.get("atribuido_para", issue.get("atrib", "")),
                                          _ultima_data(issue),
                                      ), **extra)
            n += 1
        for w in self._contagem.winfo_children():
            w.destroy()
        Pilula(self._contagem, f"{n} registro{'s' if n != 1 else ''}",
               cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=24).pack()
        if selecionado is not None and self.tree_consulta.exists(str(selecionado)):
            self.tree_consulta.selection_set(str(selecionado))

    def selecionar_issue(self, issue_id):
        iid = str(issue_id)
        if not self.tree_consulta.exists(iid):
            self.limpar_filtros()
        if self.tree_consulta.exists(iid):
            self.tree_consulta.selection_set(iid)
            self.tree_consulta.see(iid)
            self.mostrar_detalhes()

    def limpar_filtros(self):
        self.cb_filtro_nome.set(TODOS)
        self.cb_filtro_obra.set(TODAS)
        self.cb_filtro_tipo_doc.set(TODOS)
        self.ent_busca.set("")
        self.seg_status.selecionar(TODOS, disparar=False)
        self.atualizar_lista()

    def recarregar_obras(self):
        self.app.carregar_obras(silencioso=False)
        self.cb_filtro_obra.valores = [TODAS] + list(self.app.obras_lista)
        self.cb_filtro_obra.combo["values"] = self.cb_filtro_obra.valores

    # ---------- detalhes ----------
    def _limpar_detalhes(self):
        for w in self.painel_detalhes.winfo_children():
            w.destroy()

    def _detalhes_vazio(self):
        self._limpar_detalhes()
        p = self.painel_detalhes
        centro = tk.Frame(p, bg=p["bg"])
        centro.place(relx=0.5, rely=0.42, anchor="center")
        QuadradoIcone(centro, Icone.PRANCHETA, cores=(TEMA["campo"], TEMA["titulo"]), tamanho=48,
                      tamanho_icone=16).pack()
        rotulo(centro, "Selecione um registro", 12, "semi").pack(pady=(12, 2))
        rotulo(centro, "Os detalhes, o documento vinculado e o histórico\naparecem aqui.", 9,
               cor=TEMA["texto_fraco"], justify="center").pack()

    def mostrar_detalhes(self, event=None):
        sel = self.tree_consulta.selection()
        if not sel:
            return
        issue_id = int(sel[0])
        issue = next((i for i in self.app.issues if i["id"] == issue_id), None)
        if not issue:
            return
        self.issue_atual = issue
        self._limpar_detalhes()
        p = self.painel_detalhes
        bg = p["bg"]
        tipo_doc = issue.get("tipo_doc", "pdf")

        topo = tk.Frame(p, bg=bg)
        topo.pack(fill=tk.X)
        Pilula(topo, f"#{issue['id']}", cores=TEMA["pill_azul"], altura=24, tamanho_fonte=9).pack(side=tk.LEFT)
        Pilula(topo, tipo_doc.upper(), cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=24,
               tamanho_fonte=9, icone=Icone.CUBO if tipo_doc == "ifc" else Icone.DOCUMENTO
               ).pack(side=tk.LEFT, padx=(6, 0))
        pilula_status(topo, issue.get("status") or "—", altura=24, tamanho_fonte=9).pack(side=tk.RIGHT)

        rotulo(p, issue.get("titulo") or "Sem título", 14, "semi", wraplength=420, justify="left"
               ).pack(anchor="w", pady=(12, 12))

        meta = tk.Frame(p, bg=bg)
        meta.pack(fill=tk.X)
        meta.columnconfigure(0, weight=1, uniform="meta")
        meta.columnconfigure(1, weight=1, uniform="meta")
        campos = (
            ("Obra", issue.get("obra") or "—"), ("Disciplina", issue.get("disciplina") or "—"),
            ("Tipo", issue.get("tipo") or "—"), ("Atribuído a", issue.get("atribuido_para") or "—"),
            ("Criado por", issue.get("criado_por") or "—"), ("Criado em", issue.get("data_criacao") or "—"),
        )
        for n, (rot, valor) in enumerate(campos):
            f = tk.Frame(meta, bg=bg)
            f.grid(row=n // 2, column=n % 2, sticky="w", pady=(0, 10))
            rotulo(f, espacar(rot), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
            rotulo(f, valor, 10).pack(anchor="w")

        doc = Cartao(p, padding=(14, 12), cor=TEMA["campo"], borda=None, raio=10)
        doc.pack(fill=tk.X, pady=(4, 12))
        d = doc.corpo
        linha_doc = tk.Frame(d, bg=d["bg"])
        linha_doc.pack(fill=tk.X)
        textos = tk.Frame(linha_doc, bg=d["bg"])
        textos.pack(side=tk.LEFT, fill=tk.X, expand=True)
        rotulo(textos, espacar("Documento vinculado"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
        caminho = issue.get("filepath") or ""
        if tipo_doc == "ifc":
            local = (f"Elemento: {issue.get('ifc_nome_elemento', '—')} ({issue.get('ifc_classe', '—')})")
        else:
            pagina = issue.get("page")
            local = f"Página {pagina + 1 if pagina is not None else '—'}"
        rotulo(textos, os.path.basename(caminho) or "Caminho não registrado", 10, "semi",
               wraplength=300, justify="left").pack(anchor="w", pady=(2, 0))
        rotulo(textos, local, 9, cor=TEMA["texto_fraco"]).pack(anchor="w")
        if caminho and os.path.exists(caminho):
            Botao(linha_doc, "Abrir", variante="primario", icone=Icone.SETA_DIREITA, altura=32,
                  tamanho_fonte=9, comando=lambda: self._abrir_documento(issue)).pack(side=tk.RIGHT, padx=(10, 0))

        rotulo(p, espacar("Descrição e histórico"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(4, 6))
        quadro = tk.Frame(p, bg=bg)
        quadro.pack(fill=tk.BOTH, expand=True)
        txt = tk.Text(quadro, wrap=tk.WORD, bg=bg, fg=TEMA["texto"], relief="flat", bd=0,
                      highlightthickness=0, font=fonte(10), padx=0, pady=0, cursor="arrow")
        barra = ttk.Scrollbar(quadro, orient=tk.VERTICAL, command=txt.yview, style="Fino.Vertical.TScrollbar")
        txt.configure(yscrollcommand=barra.set)
        barra.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        txt.tag_configure("titulo", font=fonte(10, "semi"), foreground=TEMA["titulo"], spacing1=4, spacing3=4)
        txt.tag_configure("data", font=fonte(8), foreground=TEMA["texto_fraco"], spacing1=8)
        txt.tag_configure("autor", font=fonte(8, "semi"), foreground=TEMA["titulo"])
        txt.tag_configure("texto", lmargin1=0, lmargin2=0, spacing3=4)
        txt.tag_configure("vazio", foreground=TEMA["texto_fraco"])
        txt.insert(tk.END, (issue.get("desc") or "Nenhuma descrição fornecida.") + "\n", "texto")
        txt.insert(tk.END, "\nHistórico\n", "titulo")
        historico = issue.get("historico", [])
        if not historico:
            txt.insert(tk.END, "Sem comentários para este problema.", "vazio")
        for com in historico:
            txt.insert(tk.END, f"● {com.get('data', '')}", "data")
            if com.get("autor"):
                txt.insert(tk.END, f"  ·  {com['autor']}", "autor")
            txt.insert(tk.END, f"\n{com.get('texto', '')}\n", "texto")
        txt.configure(state=tk.DISABLED)

    def _abrir_documento(self, issue):
        caminho = issue.get("filepath")
        if not caminho or not os.path.exists(caminho):
            messagebox.showwarning("Arquivo indisponível", f"Não foi possível encontrar:\n{caminho}")
            return
        if issue.get("obra"):
            self.app.sessao["obra"] = issue["obra"]
        if issue.get("tipo_doc", "pdf") == "ifc":
            tela = self.app.abrir_tela_visualizador_ifc()
            if hasattr(tela, "_carregar_ifc"):
                tela._carregar_ifc(caminho, limpar_existente=True)
        else:
            tela = self.app.abrir_tela_visualizador_pdf()
            tela.reabrir_arquivo(caminho, issue.get("page") or 0)

    def sincronizar(self):
        self.atualizar_lista()
        if self.issue_atual is not None:
            self.selecionar_issue(self.issue_atual["id"])
