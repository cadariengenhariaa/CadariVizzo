"""Painel de issues do visualizador IFC (layout do protótipo): lista em
tabela — ID, título · disciplina · autor, responsável e status — e, ao
clicar numa linha, o detalhe editável da issue (campos, descrição com
corretor, histórico e novo comentário).

Salvar não abre mais janela de aviso (antes um "OK" aparecia repetido,
com o som de erro do Windows): grava, volta para a lista e mostra
"salva" no rodapé.

O visualizador define, via `definir_filtro`, quais issues pertencem ao
documento aberto, e recebe callbacks para redesenhar seus marcadores
sempre que uma issue é criada, editada ou excluída."""
import tkinter as tk
from tkinter import messagebox

from auth.usuarios import listar_nomes_ativos
from config import LISTA_DISCIPLINAS, LISTA_STATUS, TEMA, TIPO_PADRAO_PDF
from ui.componentes import (
    AreaRolavel,
    Avatar,
    Botao,
    CampoArredondado,
    Cartao,
    ComboArredondado,
    Icone,
    Pilula,
    cores_status,
    espacar,
    fonte,
    rotulo,
    separador,
)
from ui.corretor import ativar_corretor
from utils import agora_str, atualizar_data_modificacao, proximo_id

LIMITE_TITULO = 26


def codigo_issue(issue_id):
    return f"ISS-{int(issue_id):03d}" if str(issue_id).isdigit() else str(issue_id)


def _curto(texto, limite):
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


class PainelIssue(tk.Frame):
    def __init__(self, parent, app, tipos_disponiveis, on_issue_alterada=None, on_issue_selecionada=None):
        super().__init__(parent, bg=TEMA["card"])
        self.app = app
        self.tipos_disponiveis = tipos_disponiveis
        self.on_issue_alterada = on_issue_alterada or (lambda: None)
        self.on_issue_selecionada = on_issue_selecionada or (lambda issue: None)
        self.current_editing_id = None
        self._filtro_atual = lambda issues: []
        self._linhas = {}

        self.vista_lista = tk.Frame(self, bg=TEMA["card"])
        self.vista_detalhe = tk.Frame(self, bg=TEMA["card"])
        self._montar_lista()
        self.lbl_info_extra = None  # criado no detalhe
        self.mostrar_lista()

    # ---------- lista ----------
    def _montar_lista(self):
        v = self.vista_lista
        cab = tk.Frame(v, bg=TEMA["card"])
        cab.pack(fill=tk.X, padx=16, pady=(10, 6))
        for texto, largura in (("ID", 70), ("Título · Disciplina", 0), ("Atrib.", 50), ("Status", 96)):
            l = rotulo(cab, espacar(texto), 7, "semi", cor=TEMA["eyebrow"], anchor="w")
            if largura:
                l.configure(width=largura // 7)
            l.pack(side=tk.LEFT, fill=tk.X, expand=not largura)
        separador(v)
        self.area = AreaRolavel(v, cor=TEMA["card"])
        self.area.pack(fill=tk.BOTH, expand=True)
        self.lista = self.area.interno
        separador(v)
        self.rodape = tk.Frame(v, bg=TEMA["card"])
        self.rodape.pack(fill=tk.X, padx=16, pady=8)
        self.lbl_contagem = rotulo(self.rodape, "", 8, cor=TEMA["texto_fraco"])
        self.lbl_contagem.pack(side=tk.LEFT)
        self.lbl_aviso = rotulo(self.rodape, "", 8, "semi", cor=TEMA["pill_verde"][1])
        self.lbl_aviso.pack(side=tk.RIGHT)

    def mostrar_lista(self):
        self.vista_detalhe.pack_forget()
        self.vista_lista.pack(fill=tk.BOTH, expand=True)

    def _avisar(self, texto):
        self.lbl_aviso.config(text=texto)
        self.after(3500, lambda: self.lbl_aviso.winfo_exists() and self.lbl_aviso.config(text=""))

    def atualizar_lista(self):
        for w in self.lista.winfo_children():
            w.destroy()
        self._linhas = {}
        issues = sorted(self.issues_atuais(), key=lambda i: i.get("id", 0))
        if not issues:
            vazio = tk.Frame(self.lista, bg=TEMA["card"])
            vazio.pack(fill=tk.X, pady=28)
            rotulo(vazio, "Nenhuma issue neste modelo", 10, "semi").pack()
            rotulo(vazio, "Use a ferramenta Marcar issue (M) e clique num elemento.", 9,
                   cor=TEMA["texto_fraco"]).pack(pady=(4, 0))
        for issue in issues:
            self._linha(issue)
        n = len(issues)
        self.lbl_contagem.config(text=f"{n} issue{'s' if n != 1 else ''} neste modelo")
        if self.current_editing_id in self._linhas:
            self._destacar(self.current_editing_id)

    def _linha(self, issue):
        bg = TEMA["card"]
        linha = tk.Frame(self.lista, bg=bg, cursor="hand2")
        linha.pack(fill=tk.X)
        marcador = tk.Frame(linha, bg=bg, width=3)
        marcador.pack(side=tk.LEFT, fill=tk.Y)
        conteudo = tk.Frame(linha, bg=bg)
        conteudo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(13, 12), pady=9)
        lbl_id = tk.Label(conteudo, text=codigo_issue(issue["id"]), bg=bg, fg=TEMA["primario"]
                          if not TEMA.esta_escuro() else TEMA["acento"], font=fonte(9, "semi"), width=8, anchor="w")
        lbl_id.pack(side=tk.LEFT)
        textos = tk.Frame(conteudo, bg=bg)
        textos.pack(side=tk.LEFT, fill=tk.X, expand=True)
        l1 = rotulo(textos, _curto(issue.get("titulo"), LIMITE_TITULO), 9, "semi", anchor="w")
        l1.pack(anchor="w")
        detalhe = " · ".join(p for p in (issue.get("disciplina"), f"por {issue.get('criado_por')}"
                                          if issue.get("criado_por") else "") if p)
        l2 = rotulo(textos, _curto(detalhe, 34), 8, cor=TEMA["texto_fraco"], anchor="w")
        l2.pack(anchor="w")
        bg_av, fg_av = TEMA["pill_azul"]
        av = Avatar(conteudo, issue.get("atribuido_para") or "?", tamanho=26, cor=bg_av, cor_texto=fg_av,
                    tamanho_fonte=7)
        av.pack(side=tk.LEFT, padx=(6, 12))
        status = issue.get("status") or "—"
        caixa_status = tk.Frame(conteudo, bg=bg, width=96)
        caixa_status.pack(side=tk.LEFT)
        ponto = tk.Label(caixa_status, text="●", bg=bg, fg=cores_status(status)[1], font=fonte(8))
        ponto.pack(side=tk.LEFT)
        lbl_status = rotulo(caixa_status, status, 9)
        lbl_status.pack(side=tk.LEFT, padx=(3, 0))
        widgets = [linha, conteudo, lbl_id, textos, l1, l2, av, caixa_status, ponto, lbl_status]
        for w in widgets:
            w.bind("<Button-1>", lambda e, i=issue["id"]: self.selecionar_issue(i))
            w.bind("<Enter>", lambda e, ws=widgets: self._pintar(ws, TEMA["sidebar_sel"]), add="+")
            w.bind("<Leave>", lambda e, ws=widgets, i=issue["id"]: self._pintar(
                ws, TEMA["sidebar_sel"] if i == self.current_editing_id else TEMA["card"]), add="+")
        separador(self.lista)
        self._linhas[issue["id"]] = (marcador, widgets)

    @staticmethod
    def _pintar(widgets, cor):
        for w in widgets:
            try:
                w.configure(bg=cor)
            except tk.TclError:
                pass

    def _destacar(self, issue_id):
        for k, (marcador, widgets) in self._linhas.items():
            ativo = k == issue_id
            marcador.configure(bg=TEMA["primario"] if ativo else TEMA["card"])
            self._pintar(widgets, TEMA["sidebar_sel"] if ativo else TEMA["card"])

    # ---------- integração com o visualizador ----------
    def definir_filtro(self, filtro_fn):
        """filtro_fn(issues) -> lista de issues do documento atual."""
        self._filtro_atual = filtro_fn

    def atualizar_obras(self):
        if hasattr(self, "cb_obra") and self.cb_obra.winfo_exists():
            self.cb_obra.valores = list(self.app.obras_lista)
            self.cb_obra.combo["values"] = self.cb_obra.valores

    def issues_atuais(self):
        return self._filtro_atual(self.app.issues)

    def criar_issue(self, obra, criado_por, atribuido_para, campos_extra, titulo=None, tipo=None,
                    disciplina=""):
        agora = agora_str()
        novo_id = proximo_id(self.app.issues)
        issue = {
            "id": novo_id,
            "titulo": titulo or f"Problema {novo_id}",
            "status": "Novo",
            "tipo": tipo or (TIPO_PADRAO_PDF if TIPO_PADRAO_PDF in self.tipos_disponiveis
                             else self.tipos_disponiveis[0] if self.tipos_disponiveis else ""),
            "obra": obra,
            "disciplina": disciplina,
            "criado_por": criado_por,
            "atribuido_para": atribuido_para,
            "desc": "",
            "historico": [],
            "data_criacao": agora,
            "data_modificacao": agora,
        }
        issue.update(campos_extra)
        self.app.issues.append(issue)
        self.app.salvar_banco_dados()
        self.atualizar_lista()
        self.load_issue_to_form(issue["id"])
        self.on_issue_alterada()
        return issue["id"]

    def selecionar_issue(self, issue_id):
        """Mostra os detalhes de uma issue (clique na lista ou num pino 3D)."""
        issue = self._find(issue_id)
        if not issue:
            return
        self.load_issue_to_form(issue_id)
        self.on_issue_selecionada(issue)

    def _find(self, issue_id):
        return next((i for i in self.app.issues if i["id"] == issue_id), None)

    # ---------- detalhe ----------
    def load_issue_to_form(self, issue_id):
        issue = self._find(issue_id)
        if not issue:
            return
        self.current_editing_id = issue_id
        for w in self.vista_detalhe.winfo_children():
            w.destroy()
        v = self.vista_detalhe
        bg = TEMA["card"]

        topo = tk.Frame(v, bg=bg)
        topo.pack(fill=tk.X, padx=16, pady=(10, 6))
        Botao(topo, "Issues", variante="link", icone=Icone.CHEVRON_ESQUERDA, altura=26, tamanho_fonte=9,
              comando=self._voltar).pack(side=tk.LEFT)
        rotulo(topo, codigo_issue(issue_id), 10, "semi").pack(side=tk.LEFT, padx=(10, 0))
        status = issue.get("status") or "—"
        Pilula(topo, status, cores=cores_status(status), altura=22, tamanho_fonte=8).pack(side=tk.RIGHT)
        separador(v)

        # botões fixos no rodapé (empacotados antes da área rolável)
        botoes = tk.Frame(v, bg=bg)
        botoes.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=10)
        Botao(botoes, "Excluir", variante="perigo", icone=Icone.EXCLUIR, altura=34, tamanho_fonte=9,
              comando=self.delete_issue).pack(side=tk.LEFT)
        Botao(botoes, "Salvar", variante="primario", icone=Icone.CHECK, altura=34, tamanho_fonte=9,
              comando=self.save_issue).pack(side=tk.RIGHT)
        tk.Frame(v, bg=TEMA["linha"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        area = AreaRolavel(v, cor=bg)
        area.pack(fill=tk.BOTH, expand=True)
        f = tk.Frame(area.interno, bg=bg)
        f.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        def campo(rotulo_texto, linha, coluna, colspan=1):
            caixa = tk.Frame(f, bg=bg)
            caixa.grid(row=linha, column=coluna, columnspan=colspan, sticky="new",
                       padx=(0, 8 if coluna == 0 and colspan == 1 else 0), pady=(0, 10))
            rotulo(caixa, espacar(rotulo_texto), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(0, 3))
            return caixa

        f.columnconfigure(0, weight=1, uniform="d")
        f.columnconfigure(1, weight=1, uniform="d")
        nomes = listar_nomes_ativos()

        self.ent_titulo = CampoArredondado(campo("Título", 0, 0, 2), largura=10, altura=36)
        self.ent_titulo.pack(fill=tk.X)
        self.ent_titulo.set(issue.get("titulo", ""))
        self.cb_status = ComboArredondado(campo("Status", 1, 0), LISTA_STATUS, largura=10, altura=34)
        self.cb_status.pack(fill=tk.X)
        self.cb_status.set(issue.get("status", ""))
        self.cb_tipo = ComboArredondado(campo("Tipo", 1, 1), self.tipos_disponiveis, largura=10, altura=34)
        self.cb_tipo.pack(fill=tk.X)
        self.cb_tipo.set(issue.get("tipo", ""))
        self.cb_disciplina = ComboArredondado(campo("Disciplina", 2, 0), LISTA_DISCIPLINAS, largura=10, altura=34)
        self.cb_disciplina.pack(fill=tk.X)
        self.cb_disciplina.set(issue.get("disciplina", ""))
        self.cb_obra = ComboArredondado(campo("Obra", 2, 1), self.app.obras_lista, largura=10, altura=34,
                                        editavel=True, filtrar=True)
        self.cb_obra.pack(fill=tk.X)
        self.cb_obra.set(issue.get("obra", ""))
        self.ent_criado_por = ComboArredondado(campo("Criado por", 3, 0), nomes, largura=10, altura=34,
                                               editavel=True, filtrar=True)
        self.ent_criado_por.pack(fill=tk.X)
        self.ent_criado_por.set(issue.get("criado_por", ""))
        self.cb_atrib = ComboArredondado(campo("Atribuído para", 3, 1), nomes, largura=10, altura=34,
                                         editavel=True, filtrar=True)
        self.cb_atrib.pack(fill=tk.X)
        self.cb_atrib.set(issue.get("atribuido_para", issue.get("atrib", "")))

        moldura = Cartao(campo("Descrição", 4, 0, 2), padding=(10, 8), raio=8, tamanho_fixo=True, width=10,
                         height=90)
        moldura.pack(fill=tk.X)
        self.txt_desc = tk.Text(moldura.corpo, wrap="word", relief="flat", bd=0, highlightthickness=0, width=1,
                                height=1, bg=bg, fg=TEMA["titulo"], insertbackground=TEMA["titulo"], font=fonte(10))
        self.txt_desc.pack(fill=tk.BOTH, expand=True)
        self.txt_desc.insert("1.0", issue.get("desc", ""))
        ativar_corretor(self.txt_desc)

        info = ""
        if issue.get("tipo_doc") == "ifc":
            info = (f"Elemento IFC: {issue.get('ifc_nome_elemento', '—')} ({issue.get('ifc_classe', '—')})\n"
                    f"GlobalId: {issue.get('ifc_global_id', '—')}")
        self.lbl_info_extra = rotulo(f, info, 8, cor=TEMA["texto_fraco"], justify="left", wraplength=360)
        self.lbl_info_extra.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 10))
        rotulo(f, f"Criado em {issue.get('data_criacao', '—')}  ·  Modificado em {issue.get('data_modificacao', '—')}",
               8, cor=TEMA["texto_fraco"]).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 10))

        historico = tk.Frame(f, bg=bg)
        historico.grid(row=7, column=0, columnspan=2, sticky="ew")
        rotulo(historico, espacar("Histórico"), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(0, 6))
        if not issue.get("historico"):
            rotulo(historico, "Sem comentários ainda.", 9, cor=TEMA["texto_fraco"]).pack(anchor="w")
        for com in issue.get("historico", []):
            item = tk.Frame(historico, bg=bg)
            item.pack(fill=tk.X, pady=(0, 8))
            tk.Frame(item, bg=TEMA["linha"], width=2).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
            t = tk.Frame(item, bg=bg)
            t.pack(side=tk.LEFT, fill=tk.X)
            rotulo(t, " · ".join(p for p in (com.get("autor"), com.get("data")) if p), 8, "semi").pack(anchor="w")
            rotulo(t, com.get("texto", ""), 9, cor=TEMA["texto"], wraplength=330, justify="left").pack(anchor="w")

        novo = Cartao(f, padding=(0, 0), raio=8)
        novo.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.txt_novo_comentario = tk.Text(novo.corpo, height=2, width=1, wrap="word", relief="flat", bd=0,
                                           highlightthickness=0, bg=bg, fg=TEMA["titulo"],
                                           insertbackground=TEMA["titulo"], font=fonte(9), padx=10, pady=8)
        self.txt_novo_comentario.pack(fill=tk.X)
        ativar_corretor(self.txt_novo_comentario)
        Botao(novo.corpo, "Comentar", variante="secundario", altura=28, tamanho_fonte=9,
              comando=self.adicionar_comentario).pack(anchor="e", padx=8, pady=(0, 8))

        self.vista_lista.pack_forget()
        self.vista_detalhe.pack(fill=tk.BOTH, expand=True)
        self._destacar(issue_id)

    def _voltar(self):
        self.mostrar_lista()
        self.atualizar_lista()

    def save_issue(self):
        if not self.current_editing_id:
            return
        issue = self._find(self.current_editing_id)
        if not issue:
            return
        novo_status = self.cb_status.get()
        if novo_status and novo_status != issue.get("status"):
            issue.setdefault("historico", []).append({
                "data": agora_str()[:16], "autor": self.app.sessao.get("nome", ""),
                "texto": f"Status alterado de {issue.get('status')} para {novo_status}."})
        issue["titulo"] = self.ent_titulo.get().strip() or f"Problema {issue['id']}"
        issue["status"] = novo_status or issue.get("status")
        issue["tipo"] = self.cb_tipo.get()
        issue["criado_por"] = self.ent_criado_por.get()
        issue["atribuido_para"] = self.cb_atrib.get()
        issue["obra"] = self.cb_obra.get()
        issue["disciplina"] = self.cb_disciplina.get()
        issue["desc"] = self.txt_desc.get("1.0", tk.END).strip()
        if not issue.get("data_criacao"):
            issue["data_criacao"] = agora_str()
        atualizar_data_modificacao(issue)

        self.app.salvar_banco_dados()
        self.on_issue_alterada()
        self._voltar()
        self._avisar(f"✓ {codigo_issue(issue['id'])} salva")

    def delete_issue(self):
        if not self.current_editing_id:
            return
        if not messagebox.askyesno("Confirmar exclusão",
                                   f"Excluir a issue {codigo_issue(self.current_editing_id)}?",
                                   parent=self.winfo_toplevel()):
            return
        excluida = self.current_editing_id
        self.app.issues = [i for i in self.app.issues if i["id"] != excluida]
        self.current_editing_id = None
        self.app.salvar_banco_dados()
        self.on_issue_alterada()
        self._voltar()
        self._avisar(f"{codigo_issue(excluida)} excluída")

    def adicionar_comentario(self):
        if not self.current_editing_id:
            return
        novo_texto = self.txt_novo_comentario.get("1.0", tk.END).strip()
        if not novo_texto:
            return
        issue = self._find(self.current_editing_id)
        if not issue:
            return
        issue.setdefault("historico", []).append({
            "data": agora_str()[:16],
            "texto": novo_texto,
            "autor": self.app.sessao.get("nome", ""),
        })
        atualizar_data_modificacao(issue)
        self.app.salvar_banco_dados()
        self.on_issue_alterada()
        self.load_issue_to_form(issue["id"])
