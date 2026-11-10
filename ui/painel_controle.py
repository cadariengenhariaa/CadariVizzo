"""Dashboard no estilo do protótipo Figma: "Painel de controle" (Visão
geral), "Equipe" e "Conformidade". O relatório detalhado com os
gráficos do Power BI continua em dashboard/tela_dashboard.py (submenu
"Relatório detalhado")."""
import tkinter as tk

from auth.usuarios import carregar_usuarios
from config import TEMA
from dashboard.dados_dashboard import filtrar_por_papel
from dashboard.dados_painel import (
    DIAS_SEMANA,
    SITUACAO_ANALISE,
    SITUACAO_CERTIFICADO,
    SITUACAO_PAUSADO,
    SITUACAO_REVISAO,
    atividade_por_dia_semana,
    desempenho_equipe,
    indice_conformidade,
    kpis_painel,
    pendencias_atrasadas,
    projetos_por_situacao,
    resumo_projetos,
)
from ui.componentes import (
    Anel,
    AreaRolavel,
    Avatar,
    BarraProgresso,
    Cartao,
    Donut,
    GraficoBarras,
    Icone,
    Pilula,
    QuadradoIcone,
    Segmentado,
    cabecalho_cartao,
    cabecalho_pagina,
    espacar,
    fonte,
    icone,
    pilula_status,
    rotulo,
    separador,
)

PERIODOS = {"7 dias": 7, "30 dias": 30, "90 dias": 90}
PRAZO_CONFORMIDADE = 15


def _num(valor, casas=1):
    return f"{valor:.{casas}f}".replace(".", ",")


def _variacao(texto, positivo_e_bom, valor):
    """(texto, cor) para o indicador pequeno ao lado do número do KPI."""
    if valor is None:
        return "sem comparação", TEMA["texto_fraco"]
    bom = (valor >= 0) == positivo_e_bom
    return texto, TEMA["pill_verde"][1] if bom else TEMA["pill_vermelho"][1]


def ponto_legenda(parent, texto, cor):
    f = tk.Frame(parent, bg=parent["bg"])
    tk.Label(f, text="●", fg=cor, bg=parent["bg"], font=fonte(8)).pack(side=tk.LEFT)
    rotulo(f, texto, 9, cor=TEMA["texto"]).pack(side=tk.LEFT, padx=(4, 0))
    return f


def tabela(parent, colunas, linhas, ao_clicar=None):
    """Tabela "de cartão": cabeçalho em caixa alta sobre fundo cinza
    claro e linhas separadas por fios. `colunas`: [(título, peso)];
    `linhas`: [(chave, [célula, ...])] — célula é texto ou função
    `(parent) -> widget`."""
    t = tk.Frame(parent, bg=parent["bg"])
    for col, (_, peso) in enumerate(colunas):
        t.columnconfigure(col, weight=peso, uniform="tab")
    cab = tk.Frame(t, bg=TEMA["campo"])
    cab.grid(row=0, column=0, columnspan=len(colunas), sticky="nsew")
    for col, (titulo, _) in enumerate(colunas):
        tk.Label(t, text=espacar(titulo), bg=TEMA["campo"], fg=TEMA["eyebrow"], font=fonte(8, "semi"),
                 anchor="w").grid(row=0, column=col, sticky="ew", padx=(10, 0), ipady=8)
    for n, (chave, celulas) in enumerate(linhas):
        r = 1 + n * 2
        widgets = []
        for col, celula in enumerate(celulas):
            if callable(celula):
                w = celula(t)
            else:
                w = rotulo(t, str(celula), 10, anchor="w")
            w.grid(row=r, column=col, sticky="w", padx=(10, 0), pady=8)
            widgets.append(w)
        tk.Frame(t, bg=TEMA["linha"], height=1).grid(row=r + 1, column=0, columnspan=len(colunas), sticky="ew")
        if ao_clicar:
            for w in widgets:
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda e, k=chave: ao_clicar(k))
    return t


def celula_pessoa(nome, setor):
    def construir(parent):
        f = tk.Frame(parent, bg=parent["bg"])
        Avatar(f, nome, tamanho=30, cor=TEMA["pill_azul"][0], cor_texto=TEMA["pill_azul"][1],
               tamanho_fonte=7).pack(side=tk.LEFT, padx=(0, 10))
        textos = tk.Frame(f, bg=parent["bg"])
        textos.pack(side=tk.LEFT)
        rotulo(textos, nome, 10, "semi").pack(anchor="w")
        rotulo(textos, setor or "—", 8, cor=TEMA["texto_fraco"]).pack(anchor="w")
        return f
    return construir


def celula_pilula(texto, cores):
    return lambda parent: Pilula(parent, texto, cores=cores, altura=22)


def celula_desempenho(fracao):
    def construir(parent):
        f = tk.Frame(parent, bg=parent["bg"])
        BarraProgresso(f, fracao, altura=3, width=70).pack(side=tk.LEFT, pady=(2, 0))
        rotulo(f, f"{round(fracao * 100)}%", 9, "semi").pack(side=tk.LEFT, padx=(10, 0))
        return f
    return construir


class _TelaBase(tk.Frame):
    """Rolagem + margens + cabeçalho padrão."""

    def __init__(self, parent, app, sobre, titulo, subtitulo, migalha):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        area = AreaRolavel(self)
        area.pack(fill=tk.BOTH, expand=True)
        self.pagina = tk.Frame(area.interno, bg=TEMA["pagina"])
        self.pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(24, 28))
        cab, self.direita_cabecalho = cabecalho_pagina(
            self.pagina, sobre, titulo, subtitulo, migalhas=[("Início", app.abrir_tela_home), (migalha, None)])
        cab.pack(fill=tk.X, pady=(0, 20))
        self.corpo = tk.Frame(self.pagina, bg=TEMA["pagina"])
        self.corpo.pack(fill=tk.BOTH, expand=True)

    def issues_visiveis(self):
        return filtrar_por_papel(self.app.issues, self.app.usuario_atual)

    def sincronizar(self):
        for w in self.corpo.winfo_children():
            w.destroy()
        self.montar()


class PainelControle(_TelaBase):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Inteligência de projetos", "Painel de controle",
                         "Acompanhe o desempenho dos projetos, revisões e responsáveis em um só lugar.",
                         "Painel de controle")
        self.periodo = "30 dias"
        Segmentado(self.direita_cabecalho, list(PERIODOS), valor=self.periodo, agrupado=True,
                   comando=self._trocar_periodo).pack(anchor="e")
        self.montar()

    def _trocar_periodo(self, valor):
        self.periodo = valor
        self.sincronizar()

    def montar(self):
        dias = PERIODOS[self.periodo]
        issues = self.issues_visiveis()
        self._kpis(issues, dias)
        linha = tk.Frame(self.corpo, bg=TEMA["pagina"])
        linha.pack(fill=tk.X, pady=(16, 0))
        linha.columnconfigure(0, weight=5, uniform="l1")
        linha.columnconfigure(1, weight=3, uniform="l1")
        self._atividade(linha, issues, dias)
        self._portfolio(linha, issues)
        linha2 = tk.Frame(self.corpo, bg=TEMA["pagina"])
        linha2.pack(fill=tk.X, pady=(16, 0))
        linha2.columnconfigure(0, weight=5, uniform="l2")
        linha2.columnconfigure(1, weight=3, uniform="l2")
        self._equipe(linha2, issues)
        self._conformidade(linha2, issues)

    # ---------- KPIs ----------
    def _kpis(self, issues, dias):
        k = kpis_painel(issues, dias)
        linha = tk.Frame(self.corpo, bg=TEMA["pagina"])
        linha.pack(fill=tk.X)
        saldo = k["revisoes_saldo_semana"]
        taxa = k["taxa_conclusao"]
        tempo = k["tempo_medio_dias"]
        cartoes = [
            (Icone.PASTA, "pill_azul", "Projetos ativos", str(k["projetos_ativos"]), "",
             _variacao(f"{'↗' if (k['projetos_ativos_variacao'] or 0) >= 0 else '↘'} "
                       f"{_num(abs(k['projetos_ativos_variacao'] or 0))}%", True, k["projetos_ativos_variacao"])),
            (Icone.MENSAGEM, "pill_dourado", "Revisões abertas", str(k["revisoes_abertas"]), "",
             _variacao(f"{'+' if saldo > 0 else '−' if saldo < 0 else ''}{abs(saldo)} esta semana", False, saldo)),
            (Icone.CHECK, "pill_verde", "Taxa de conclusão", "—" if taxa is None else str(round(taxa)), "%",
             _variacao(f"{'+' if (k['taxa_conclusao_variacao'] or 0) >= 0 else '−'}"
                       f"{_num(abs(k['taxa_conclusao_variacao'] or 0))}% no período", True,
                       k["taxa_conclusao_variacao"])),
            (Icone.RELOGIO, "pill_vermelho", "Tempo médio", "—" if tempo is None else _num(tempo), "d",
             _variacao(f"{'+' if (k['tempo_medio_variacao'] or 0) >= 0 else '−'}"
                       f"{_num(abs(k['tempo_medio_variacao'] or 0))} dia", False, k["tempo_medio_variacao"])),
        ]
        for col, (glifo, chave, titulo, valor, unidade, (variacao, cor_var)) in enumerate(cartoes):
            linha.columnconfigure(col, weight=1, uniform="kpi")
            cartao = Cartao(linha, padding=(20, 22))
            cartao.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0 if col == 3 else 8))
            c = cartao.corpo
            QuadradoIcone(c, glifo, cores=TEMA[chave], tamanho=40
                          ).pack(side=tk.LEFT, padx=(0, 16), anchor="n", pady=(4, 0))
            textos = tk.Frame(c, bg=c["bg"])
            textos.pack(side=tk.LEFT, fill=tk.X)
            rotulo(textos, espacar(titulo), 8, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
            valores = tk.Frame(textos, bg=c["bg"])
            valores.pack(anchor="w")
            rotulo(valores, valor, 22, "semi").pack(side=tk.LEFT)
            if unidade:
                rotulo(valores, unidade, 11, cor=TEMA["texto_fraco"]).pack(side=tk.LEFT, anchor="s", pady=(0, 6))
            rotulo(valores, variacao, 9, cor=cor_var).pack(side=tk.LEFT, anchor="s", padx=(10, 0), pady=(0, 7))

    # ---------- gráficos ----------
    def _atividade(self, linha, issues, dias):
        cartao = Cartao(linha, padding=(20, 20), ajustar_altura=False, height=330)
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c = cartao.corpo
        cab, direita = cabecalho_cartao(c, "Fluxo de trabalho", "Atividade de revisões")
        cab.pack(fill=tk.X)
        cores = TEMA["grafico"]
        legenda = tk.Frame(direita, bg=c["bg"])
        legenda.pack()
        ponto_legenda(legenda, "Revisões", cores[0]).pack(side=tk.LEFT, padx=(0, 12))
        ponto_legenda(legenda, "Comentários", cores[1]).pack(side=tk.LEFT)
        separador(c, pady=(14, 0))
        revisoes, comentarios = atividade_por_dia_semana(issues, dias)
        GraficoBarras(c, list(DIAS_SEMANA), [revisoes, comentarios], cores[:2], altura=220
                      ).pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    def _portfolio(self, linha, issues):
        cartao = Cartao(linha, padding=(20, 20), ajustar_altura=False, height=330)
        cartao.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        c = cartao.corpo
        cab, direita = cabecalho_cartao(c, "Portfólio", "Projetos por status")
        cab.pack(fill=tk.X)
        mais = icone(direita, Icone.RETICENCIAS, 12, cor=TEMA["texto"], cursor="hand2")
        mais.pack()
        mais.bind("<Button-1>", lambda e: self.app.abrir_tela_projetos_pdf())
        resumos = resumo_projetos(issues)
        contagem = projetos_por_situacao(resumos)
        cores = TEMA["grafico"]
        itens = [
            ("Em andamento", contagem[SITUACAO_ANALISE], cores[0]),
            ("Em revisão", contagem[SITUACAO_REVISAO], cores[1]),
            ("Certificados", contagem[SITUACAO_CERTIFICADO], cores[2]),
            ("Pausados", contagem[SITUACAO_PAUSADO], cores[3]),
        ]
        corpo = tk.Frame(c, bg=c["bg"])
        corpo.pack(expand=True)
        Donut(corpo, [(v, cor) for _, v, cor in itens], tamanho=136, espessura=17,
              texto=str(len(resumos)), legenda="Projetos").pack(side=tk.LEFT, padx=(0, 26))
        lista = tk.Frame(corpo, bg=c["bg"])
        lista.pack(side=tk.LEFT)
        for texto, valor, cor in itens:
            l = tk.Frame(lista, bg=c["bg"])
            l.pack(fill=tk.X, pady=(6, 0))
            ponto_legenda(l, texto, cor).pack(side=tk.LEFT)
            rotulo(l, f"{valor:02d}", 10, "semi").pack(side=tk.RIGHT, padx=(26, 0))
            tk.Frame(lista, bg=TEMA["linha"], height=1).pack(fill=tk.X, pady=(8, 0))

    def _equipe(self, linha, issues):
        cartao = Cartao(linha, padding=(20, 20))
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c = cartao.corpo
        cab, _ = cabecalho_cartao(c, "Eficiência", "Desempenho da equipe", "Ver equipe",
                                  lambda: self.app.abrir_tela_dashboard("equipe"))
        cab.pack(fill=tk.X, pady=(0, 14))
        equipe = desempenho_equipe(issues, carregar_usuarios())[:6]
        if not equipe:
            rotulo(c, "Nenhum problema atribuído ainda.", 10, cor=TEMA["texto_fraco"]).pack(pady=20)
            return
        linhas = [
            (m["nome"], [celula_pessoa(m["nome"], m["setor"]), str(m["revisoes"]),
                         celula_pilula(str(m["pendencias"]), TEMA["pill_dourado"]),
                         celula_desempenho(m["desempenho"])])
            for m in equipe
        ]
        tabela(c, [("Responsável", 4), ("Revisões", 2), ("Pendências", 2), ("Desempenho", 3)], linhas,
               ao_clicar=lambda nome: self.app.abrir_tela_consulta(atribuido=nome)).pack(fill=tk.X)

    def _conformidade(self, linha, issues):
        cartao = Cartao(linha, padding=(20, 20), ajustar_altura=False)
        cartao.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        c = cartao.corpo
        cab, _ = cabecalho_cartao(c, "Qualidade", "Índice de conformidade")
        cab.pack(fill=tk.X)
        bloco_conformidade(c, issues).pack(fill=tk.X, pady=(24, 0))


def bloco_conformidade(parent, issues):
    fracao, conformes, total = indice_conformidade(issues, prazo_dias=PRAZO_CONFORMIDADE)
    f = tk.Frame(parent, bg=parent["bg"])
    Anel(f, fracao, tamanho=118, espessura=9, cor=TEMA["acento"], tamanho_fonte=22,
         legenda="Geral").pack(side=tk.LEFT, padx=(0, 20))
    textos = tk.Frame(f, bg=parent["bg"])
    textos.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if total == 0:
        titulo, texto = "Sem dados", "Nenhum projeto com registros ainda."
    else:
        titulo = ("Excelente desempenho" if fracao >= 0.85 else "Bom desempenho" if fracao >= 0.7
                  else "Atenção às pendências")
        texto = (f"{conformes} dos {total} projetos estão dentro dos padrões definidos "
                 f"(nenhuma pendência aberta há mais de {PRAZO_CONFORMIDADE} dias).")
    rotulo(textos, titulo, 13, "semi").pack(anchor="w")
    rotulo(textos, texto, 9, cor=TEMA["texto"], wraplength=240, justify="left").pack(anchor="w", pady=(4, 0))
    return f


class TelaEquipe(_TelaBase):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Eficiência", "Equipe",
                         "Revisões atribuídas, pendências e desempenho de cada responsável.", "Equipe")
        self.montar()

    def montar(self):
        equipe = desempenho_equipe(self.issues_visiveis(), carregar_usuarios())
        cartao = Cartao(self.corpo, padding=(20, 20))
        cartao.pack(fill=tk.X)
        c = cartao.corpo
        cab, direita = cabecalho_cartao(c, "Responsáveis", "Desempenho da equipe")
        cab.pack(fill=tk.X, pady=(0, 14))
        Pilula(direita, f"{len(equipe)} pessoa{'s' if len(equipe) != 1 else ''}",
               cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=24).pack()
        if not equipe:
            rotulo(c, "Nenhum problema atribuído ainda.", 10, cor=TEMA["texto_fraco"]).pack(pady=20)
            return
        linhas = [
            (m["nome"], [celula_pessoa(m["nome"], m["setor"]), str(m["revisoes"]), str(m["fechadas"]),
                         celula_pilula(str(m["pendencias"]), TEMA["pill_dourado"]),
                         celula_desempenho(m["desempenho"])])
            for m in equipe
        ]
        tabela(c, [("Responsável", 4), ("Revisões", 2), ("Concluídas", 2), ("Pendências", 2),
                   ("Desempenho", 3)], linhas,
               ao_clicar=lambda nome: self.app.abrir_tela_consulta(atribuido=nome)).pack(fill=tk.X)
        rotulo(self.corpo, "Clique em uma pessoa para ver os registros atribuídos a ela.", 9,
               cor=TEMA["texto_fraco"]).pack(anchor="w", pady=(10, 0))


class TelaConformidade(_TelaBase):
    def __init__(self, parent, app):
        super().__init__(parent, app, "Qualidade", "Conformidade",
                         f"Projetos com pendências abertas há mais de {PRAZO_CONFORMIDADE} dias "
                         "saem do padrão definido.", "Conformidade")
        self.montar()

    def montar(self):
        issues = self.issues_visiveis()
        linha = tk.Frame(self.corpo, bg=TEMA["pagina"])
        linha.pack(fill=tk.X)
        linha.columnconfigure(0, weight=2, uniform="c")
        linha.columnconfigure(1, weight=3, uniform="c")

        geral = Cartao(linha, padding=(20, 20), ajustar_altura=False)
        geral.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        cab, _ = cabecalho_cartao(geral.corpo, "Qualidade", "Índice de conformidade")
        cab.pack(fill=tk.X)
        bloco_conformidade(geral.corpo, issues).pack(fill=tk.X, pady=(24, 0))

        projetos = Cartao(linha, padding=(20, 20))
        projetos.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        c = projetos.corpo
        cab, _ = cabecalho_cartao(c, "Portfólio", "Situação por projeto")
        cab.pack(fill=tk.X, pady=(0, 14))
        atrasadas = pendencias_atrasadas(issues, prazo_dias=PRAZO_CONFORMIDADE)
        obras_atrasadas = {}
        for issue, _dias in atrasadas:
            obras_atrasadas[issue.get("obra")] = obras_atrasadas.get(issue.get("obra"), 0) + 1
        linhas = []
        for r in resumo_projetos(issues):
            n = obras_atrasadas.get(r["obra"], 0)
            linhas.append((r["obra"], [
                r["obra"], lambda p, s=r["situacao"]: pilula_status(p, s, altura=22),
                celula_desempenho(r["progresso"]),
                celula_pilula(f"{n} atrasada{'s' if n != 1 else ''}" if n else "Conforme",
                              TEMA["pill_vermelho"] if n else TEMA["pill_verde"]),
            ]))
        if linhas:
            tabela(c, [("Projeto", 2), ("Situação", 2), ("Progresso", 3), ("Conformidade", 2)], linhas,
                   ao_clicar=lambda obra: self.app.abrir_tela_consulta(obra=obra)).pack(fill=tk.X)
        else:
            rotulo(c, "Nenhum projeto com registros ainda.", 10, cor=TEMA["texto_fraco"]).pack(pady=20)

        lista = Cartao(self.corpo, padding=(20, 20))
        lista.pack(fill=tk.X, pady=(16, 0))
        c = lista.corpo
        cab, direita = cabecalho_cartao(c, "Atenção", "Pendências fora do prazo")
        cab.pack(fill=tk.X, pady=(0, 14))
        Pilula(direita, str(len(atrasadas)), cores=TEMA["pill_vermelho"], altura=24).pack()
        if not atrasadas:
            rotulo(c, "Tudo em dia — nenhuma pendência fora do prazo.", 10, cor=TEMA["texto_fraco"]).pack(pady=14)
            return
        linhas = [
            (issue["id"], [f"#{issue['id']}", issue.get("obra") or "—", (issue.get("titulo") or "")[:50],
                           issue.get("atribuido_para") or "—",
                           lambda p, s=issue.get("status"): pilula_status(p, s, altura=22),
                           celula_pilula(f"{dias} dias", TEMA["pill_vermelho"])])
            for issue, dias in atrasadas[:30]
        ]
        tabela(c, [("ID", 1), ("Projeto", 2), ("Título", 5), ("Responsável", 3), ("Status", 2), ("Em aberto", 2)],
               linhas, ao_clicar=lambda i: self.app.abrir_tela_consulta(issue_id=i)).pack(fill=tk.X)
