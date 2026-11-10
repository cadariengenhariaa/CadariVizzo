"""Tela Início (protótipo Figma): saudação, issues atribuídas ao
usuário, projetos recentes, resumo da semana e atividade recente."""
import tkinter as tk

from config import TEMA
from dashboard.dados_dashboard import filtrar_por_papel
from dashboard.dados_painel import (
    atividades_recentes,
    issues_pendentes_de,
    resumo_projetos,
    resumo_semana,
    rotulo_dia_hora,
    tempo_relativo,
    ultima_movimentacao,
    ultimo_comentario,
)
from ui.componentes import (
    Anel,
    AreaRolavel,
    BarraProgresso,
    Botao,
    Cartao,
    Icone,
    Pilula,
    QuadradoIcone,
    cabecalho_cartao,
    cabecalho_pagina,
    espacar,
    icone,
    pilula_status,
    rotulo,
    separador,
)

LINHAS_ISSUES = 5
CORES_PASTA = ("pill_azul", "pill_dourado", "pill_verde")


def _truncar(texto, limite):
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


class TelaInicio(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        usuario = app.usuario_atual or {}
        self.nome = usuario.get("nome", "")
        self.issues_visiveis = filtrar_por_papel(app.issues, usuario)

        area = AreaRolavel(self)
        area.pack(fill=tk.BOTH, expand=True)
        pagina = tk.Frame(area.interno, bg=TEMA["pagina"])
        pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(26, 28))
        self.pagina = pagina

        self._cabecalho()
        self._issues_atribuidas()
        meio = tk.Frame(pagina, bg=TEMA["pagina"])
        meio.pack(fill=tk.X, pady=(14, 0))
        meio.columnconfigure(0, weight=5, uniform="meio")
        meio.columnconfigure(1, weight=2, uniform="meio")
        self._projetos_recentes(meio)
        self._resumo_semana(meio)
        self._atividade_recente()

    # ---------- blocos ----------
    def _cabecalho(self):
        primeiro_nome = (self.nome.split() or ["Usuário"])[0]
        cab, direita = cabecalho_pagina(
            self.pagina, "Visão geral", f"Olá, {primeiro_nome}.",
            "Confira suas atividades e acesse rapidamente o que precisa ser revisado hoje.")
        cab.pack(fill=tk.X, pady=(0, 18))
        acoes = tk.Frame(direita, bg=TEMA["pagina"])
        acoes.pack(anchor="e", pady=(0, 14))
        Botao(acoes, "Verificar modelo (IFC)", variante="secundario", icone=Icone.CUBO, altura=36, tamanho_fonte=9,
              comando=lambda: self.app.abrir_tela_verificacao("ifc")).pack(side=tk.LEFT, padx=(0, 8))
        Botao(acoes, "Iniciar verificação (PDF)", variante="primario", icone=Icone.LISTA_CHECK, altura=36,
              tamanho_fonte=9, comando=lambda: self.app.abrir_tela_verificacao("pdf")).pack(side=tk.LEFT)
        bloco = tk.Frame(direita, bg=TEMA["pagina"], cursor="hand2")
        bloco.pack(anchor="e", pady=(0, 4))
        icone(bloco, Icone.RELOGIO, 13, cor=TEMA["acento"]).pack(side=tk.LEFT, padx=(0, 10))
        textos = tk.Frame(bloco, bg=TEMA["pagina"])
        textos.pack(side=tk.LEFT)
        rotulo(textos, espacar("Última atualização"), 8, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
        rotulo(textos, rotulo_dia_hora(self.app.ultima_sincronizacao), 10, "semi").pack(anchor="w")
        for w in (bloco, textos, *textos.winfo_children()):
            w.bind("<Button-1>", lambda e: self.app.sincronizar_banco())

    def _issues_atribuidas(self):
        pendentes = issues_pendentes_de(self.app.issues, self.nome)
        cartao = Cartao(self.pagina, padding=(16, 14))
        cartao.pack(fill=tk.X)
        c = cartao.corpo

        topo = tk.Frame(c, bg=c["bg"])
        topo.pack(fill=tk.X)
        rotulo(topo, "Issues Atribuídas", 13, "semi").pack(side=tk.LEFT)
        Pilula(topo, f"{len(pendentes)} pendência{'s' if len(pendentes) != 1 else ''}",
               cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=24).pack(side=tk.RIGHT)

        tabela = tk.Frame(c, bg=c["bg"])
        tabela.pack(fill=tk.X, pady=(12, 0))
        pesos = (4, 2, 4, 2)
        for col, peso in enumerate(pesos):
            tabela.columnconfigure(col, weight=peso, uniform="iss")
        for col, titulo in enumerate(("Nome do projeto", "Disciplina", "Comentário", "Data e horário")):
            rotulo(tabela, titulo, 10, "semi", anchor="w").grid(row=0, column=col, sticky="w", pady=(0, 8))
        tk.Frame(tabela, bg=TEMA["linha"], height=1).grid(row=1, column=0, columnspan=4, sticky="ew")

        if not pendentes:
            vazio = tk.Frame(c, bg=c["bg"])
            vazio.pack(pady=(18, 10))
            QuadradoIcone(vazio, Icone.MENSAGEM, cores=(TEMA["campo"], TEMA["titulo"]), tamanho=36,
                          tamanho_icone=12).pack(side=tk.LEFT, padx=(0, 12))
            textos = tk.Frame(vazio, bg=c["bg"])
            textos.pack(side=tk.LEFT)
            rotulo(textos, "Nenhuma issue atribuída", 10).pack(anchor="w")
            rotulo(textos, "Novos comentários direcionados a você aparecerão aqui.", 9,
                   cor=TEMA["texto_fraco"]).pack(anchor="w")
            return

        for n, issue in enumerate(pendentes[:LINHAS_ISSUES]):
            linha = 2 + n * 2
            celulas = [
                f"{issue.get('obra') or '—'} · {_truncar(issue.get('titulo'), 34)}",
                issue.get("disciplina") or "—",
                _truncar(ultimo_comentario(issue), 60) or "—",
                rotulo_dia_hora(ultima_movimentacao(issue)),
            ]
            widgets = []
            for col, texto in enumerate(celulas):
                lbl = rotulo(tabela, texto, 10, cor=TEMA["titulo"] if col == 0 else TEMA["texto"],
                             anchor="w", cursor="hand2")
                lbl.grid(row=linha, column=col, sticky="ew", pady=9, padx=(0, 10))
                widgets.append(lbl)
            for w in widgets:
                w.bind("<Button-1>", lambda e, i=issue["id"]: self.app.abrir_tela_consulta(issue_id=i))
                w.bind("<Enter>", lambda e, ws=widgets: [x.config(fg=TEMA["primario"]) for x in ws])
                w.bind("<Leave>", lambda e, ws=widgets: [
                    x.config(fg=TEMA["titulo"] if k == 0 else TEMA["texto"]) for k, x in enumerate(ws)])
            tk.Frame(tabela, bg=TEMA["linha"], height=1).grid(row=linha + 1, column=0, columnspan=4, sticky="ew")
        if len(pendentes) > LINHAS_ISSUES:
            Botao(c, f"Ver todas ({len(pendentes)})", variante="link", icone_direita=Icone.SETA_DIREITA,
                  comando=lambda: self.app.abrir_tela_consulta(atribuido=self.nome),
                  altura=26).pack(anchor="e", pady=(10, 0))

    def _projetos_recentes(self, meio):
        cartao = Cartao(meio, padding=(16, 16), ajustar_altura=False)
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        c = cartao.corpo
        cab, _ = cabecalho_cartao(c, "Acesso rápido", "Projetos recentes", "Ver todos",
                                  self.app.abrir_tela_projetos_pdf)
        cab.pack(fill=tk.X)
        separador(c, pady=(12, 0))
        projetos = resumo_projetos(self.issues_visiveis)[:3]
        if not projetos:
            rotulo(c, "Nenhum projeto com registros ainda.", 10, cor=TEMA["texto_fraco"]).pack(pady=24)
            cartao.configure(height=200)
            return
        for n, p in enumerate(projetos):
            self._linha_projeto(c, p, CORES_PASTA[n % 3])
            if n < len(projetos) - 1:
                separador(c)
        c.update_idletasks()
        cartao.configure(height=c.winfo_reqheight() + 32)

    def _linha_projeto(self, c, p, chave_cor):
        linha = tk.Frame(c, bg=c["bg"], cursor="hand2")
        linha.pack(fill=tk.X, pady=12)
        # colunas de largura idêntica em todas as linhas (cada linha é um
        # grid separado): partes elásticas com o mesmo peso + partes fixas
        linha.columnconfigure(1, weight=1, uniform="elastica")
        linha.columnconfigure(2, weight=1, uniform="elastica")
        linha.columnconfigure(3, minsize=110)
        linha.columnconfigure(4, minsize=46)
        QuadradoIcone(linha, Icone.PASTA, cores=TEMA[chave_cor], tamanho=44).grid(row=0, column=0, padx=(4, 14))
        textos = tk.Frame(linha, bg=c["bg"])
        textos.grid(row=0, column=1, sticky="w")
        rotulo(textos, p["obra"], 11, "semi").pack(anchor="w")
        detalhe = f"{p['total']} registro{'s' if p['total'] != 1 else ''}"
        if p["disciplinas"]:
            detalhe += " · " + ", ".join(p["disciplinas"][:3])
        rotulo(textos, detalhe, 9, cor=TEMA["texto_fraco"]).pack(anchor="w", pady=(2, 0))

        prog = tk.Frame(linha, bg=c["bg"])
        prog.grid(row=0, column=2, sticky="ew", padx=(10, 16))
        topo = tk.Frame(prog, bg=c["bg"])
        topo.pack(fill=tk.X)
        rotulo(topo, espacar("Progresso"), 8, cor=TEMA["texto_fraco"]).pack(side=tk.LEFT)
        rotulo(topo, f"{round(p['progresso'] * 100)}%", 9, "semi").pack(side=tk.RIGHT)
        BarraProgresso(prog, p["progresso"], altura=3).pack(fill=tk.X, pady=(6, 0))

        pilula_status(linha, p["situacao"], altura=26, tamanho_fonte=9).grid(row=0, column=3, padx=(0, 12))
        contagem = tk.Frame(linha, bg=c["bg"])
        contagem.grid(row=0, column=4, padx=(0, 10))
        icone(contagem, Icone.MENSAGEM, 10).pack(side=tk.LEFT)
        rotulo(contagem, str(p["abertos"]), 9, cor=TEMA["texto_fraco"]).pack(side=tk.LEFT, padx=(5, 0))
        seta = icone(linha, Icone.CHEVRON_DIREITA, 10, cor=TEMA["titulo"])
        seta.grid(row=0, column=5, padx=(4, 4))
        tipo = "ifc" if p["tipos_doc"] == ["ifc"] else "pdf"
        for w in (linha, textos, *textos.winfo_children(), seta):
            w.bind("<Button-1>", lambda e, o=p["obra"], t=tipo: self.app.abrir_projeto(o, t))

    def _resumo_semana(self, meio):
        resumo = resumo_semana(self.issues_visiveis)
        cartao = Cartao(meio, padding=(16, 16), ajustar_altura=False)
        cartao.grid(row=0, column=1, sticky="nsew")
        c = cartao.corpo
        cab, direita = cabecalho_cartao(c, "Seu desempenho", "Resumo da semana")
        cab.pack(fill=tk.X)
        if resumo["novas_semana"]:
            Pilula(direita, f"{resumo['novas_semana']} nova{'s' if resumo['novas_semana'] > 1 else ''}",
                   cores=TEMA["pill_verde"], icone=Icone.TENDENCIA, altura=24).pack()

        centro = tk.Frame(c, bg=c["bg"])
        centro.pack(pady=(14, 14))
        Anel(centro, resumo["fracao"], tamanho=88, espessura=6, tamanho_fonte=15).pack(side=tk.LEFT, padx=(0, 18))
        textos = tk.Frame(centro, bg=c["bg"])
        textos.pack(side=tk.LEFT)
        rotulo(textos, f"{resumo['concluidas']} de {resumo['total']}", 24, "semi").pack(anchor="w")
        rotulo(textos, "tarefas concluídas", 9, cor=TEMA["texto_fraco"]).pack(anchor="w")

        separador(c)
        stats = tk.Frame(c, bg=c["bg"])
        stats.pack(fill=tk.X, pady=12)
        itens = (
            (Icone.CHECK, "pill_verde", resumo["revisoes"], "Revisões"),
            (Icone.RELOGIO, "pill_dourado", resumo["pendencias"], "Pendências"),
            (Icone.PESSOAS, "pill_azul", resumo["colaboracoes"], "Colaborações"),
        )
        for n, (glifo, chave, valor, legenda) in enumerate(itens):
            stats.columnconfigure(n * 2, weight=1)
            bloco = tk.Frame(stats, bg=c["bg"])
            bloco.grid(row=0, column=n * 2)
            QuadradoIcone(bloco, glifo, cores=TEMA[chave], tamanho=26, tamanho_icone=9).pack(side=tk.LEFT, padx=(0, 6))
            t = tk.Frame(bloco, bg=c["bg"])
            t.pack(side=tk.LEFT)
            rotulo(t, f"{valor:02d}", 10, "semi").pack(anchor="w")
            rotulo(t, legenda, 8, cor=TEMA["texto_fraco"]).pack(anchor="w")
            if n < 2:
                tk.Frame(stats, bg=TEMA["linha"], width=1).grid(row=0, column=n * 2 + 1, sticky="ns")
        separador(c)
        Botao(c, "Abrir painel completo", variante="primario", icone=Icone.GRADE, altura=40,
              comando=lambda: self.app.abrir_tela_dashboard("visao"), largura=10
              ).pack(fill=tk.X, pady=(14, 0))

    def _atividade_recente(self):
        eventos = atividades_recentes(self.issues_visiveis, limite=1)
        cartao = Cartao(self.pagina, padding=(18, 16))
        cartao.pack(fill=tk.X, pady=(14, 0))
        c = cartao.corpo
        linha = tk.Frame(c, bg=c["bg"])
        linha.pack(fill=tk.X)
        QuadradoIcone(linha, Icone.UPLOAD, cores=TEMA["pill_dourado"], tamanho=36,
                      tamanho_icone=11).pack(side=tk.LEFT, padx=(0, 14))
        titulo = tk.Frame(linha, bg=c["bg"])
        titulo.pack(side=tk.LEFT, padx=(0, 40))
        rotulo(titulo, "Atividade recente", 13, "semi").pack(anchor="w")
        rotulo(titulo, tempo_relativo(eventos[0]["quando"]) if eventos else "—", 9,
               cor=TEMA["texto_fraco"]).pack(anchor="w")

        frase = tk.Frame(linha, bg=c["bg"])
        frase.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if not eventos:
            rotulo(frase, "Nenhuma atividade registrada ainda.", 10, cor=TEMA["texto_fraco"]).pack(side=tk.LEFT)
            return
        e = eventos[0]
        issue = e["issue"]
        if e["tipo"] == "comentou":
            partes = [(e["autor"] or "Alguém", True), (" comentou em ", False),
                      (f"#{issue['id']} {_truncar(issue.get('titulo'), 40)}", True)]
        else:
            partes = [(e["autor"], True), (" registrou ", False),
                      (f"#{issue['id']} {_truncar(issue.get('titulo'), 40)}", True)]
        partes += [(" no projeto ", False), (issue.get("obra") or "—", False)]
        for texto, negrito in partes:
            rotulo(frase, texto, 9, "semi" if negrito else "normal",
                   cor=TEMA["titulo"] if negrito else TEMA["texto"]).pack(side=tk.LEFT)
        Botao(linha, "Visualizar", variante="link", icone_direita=Icone.SETA_DIREITA, altura=26,
              comando=lambda: self.app.abrir_tela_consulta(issue_id=issue["id"])).pack(side=tk.RIGHT)
