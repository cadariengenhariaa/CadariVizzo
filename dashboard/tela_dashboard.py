"""Tela do Dashboard — réplica (com gráficos equivalentes, não pixel a
pixel) do relatório Power BI "Verificação de Projeto": KPIs, gráficos
por obra/disciplina/status/tipo/projetista, série mensal e tabela de
issues. Visibilidade por papel: Projetista só vê o próprio (issues
atribuídas a ele); Coordenador/Administrador veem tudo e podem filtrar
por um projetista específico."""
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from certificacao import tom_claro
from config import CORES_STATUS, LISTA_DISCIPLINAS, LISTA_STATUS, TEMA
from ui.componentes import (
    AreaRolavel,
    Botao,
    Cartao,
    ComboArredondado,
    Icone,
    Pilula,
    QuadradoIcone,
    cabecalho_cartao,
    cabecalho_pagina,
    espacar,
    rotulo,
)
from dashboard.dados_dashboard import (
    SEM_VALOR,
    aplicar_filtros,
    calcular_kpis,
    contagem_por_disciplina,
    contagem_por_mes,
    contagem_por_obra,
    contagem_por_projetista,
    contagem_por_status,
    contagem_por_tipo,
    eh_gestor_dashboard,
    filtrar_por_papel,
    listar_nomes_projetistas,
    media_movel_por_mes,
    percentual_por_disciplina,
)

class _PopupSelecaoMultipla(tk.Toplevel):
    """Popup de checkboxes para os filtros "Mês", "Status" e "Obra" —
    deixa marcar mais de um valor ao mesmo tempo (ex.: Problema +
    Reaberto). Só aplica ao clicar "✔ Aplicar", para não refazer os 9
    gráficos a cada clique de checkbox. `pesquisavel=True` (usado em
    "Obra", que pode ter dezenas de itens) acrescenta uma caixa de texto
    que filtra quais checkboxes aparecem — digitar NÃO desmarca nada que
    já estava marcado, só esconde da vista por enquanto."""

    def __init__(self, parent, titulo, valores, selecionados, pesquisavel=False):
        super().__init__(parent, bg=TEMA["card"])
        self.title(titulo)
        self.geometry("260x480")  # altura fixa — com muitos itens (ex.: obras),
        self.minsize(220, 320)    # a lista rola, em vez da janela crescer até
        self.resizable(False, True)  # sumir o botão "Aplicar" fora da tela.
        self.resultado = None

        tk.Label(self, text=titulo, font=("Segoe UI Semibold", 12), bg=TEMA["card"], fg=TEMA["titulo"]
                 ).pack(padx=14, pady=(14, 8), anchor="w")

        if pesquisavel:
            self.ent_busca = ttk.Entry(self, width=28)
            self.ent_busca.pack(padx=12, pady=(0, 6), fill=tk.X)
            self.ent_busca.insert(0, "")
            self.ent_busca.bind("<KeyRelease>", self._ao_digitar_busca)
            self.ent_busca.focus_set()
        else:
            self.ent_busca = None

        topo = tk.Frame(self, bg=TEMA["card"])
        topo.pack(fill=tk.X, padx=12)
        Botao(topo, "Marcar todos", variante="link", altura=24, tamanho_fonte=9,
              comando=lambda: self._marcar(True)).pack(side=tk.LEFT, padx=(0, 12))
        Botao(topo, "Desmarcar todos", variante="link", altura=24, tamanho_fonte=9,
              comando=lambda: self._marcar(False)).pack(side=tk.LEFT)

        # "✔ Aplicar" empacotado ANTES da lista rolável, no mesmo pai (`self`)
        # e sem expand — assim ele sempre fica reservado/visível na parte de
        # baixo da janela, não importa quantos itens a lista tenha.
        Botao(self, "Aplicar", variante="primario", icone=Icone.CHECK, altura=36, largura=200,
              comando=self._confirmar).pack(side=tk.BOTTOM, pady=12)

        self._montar_lista_rolavel(valores, selecionados)

        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def _montar_lista_rolavel(self, valores, selecionados):
        moldura = tk.Frame(self, bg=TEMA["card"])
        moldura.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        canvas = tk.Canvas(moldura, bg=TEMA["card"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(moldura, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        corpo = tk.Frame(canvas, bg=TEMA["card"])
        janela_id = canvas.create_window((0, 0), window=corpo, anchor="nw")

        def _ajustar_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _ajustar_largura(event):
            canvas.itemconfig(janela_id, width=event.width)

        corpo.bind("<Configure>", _ajustar_scrollregion)
        canvas.bind("<Configure>", _ajustar_largura)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # bind_all() prende na aplicação inteira, não só neste popup — sem
        # desfazer, rolar o mouse depois de fechar chamaria isto com o
        # canvas já destruído (mesma pegadinha corrigida no Dashboard).
        def _ao_destruir(event):
            canvas.unbind_all("<MouseWheel>")
        self.bind("<Destroy>", _ao_destruir)

        self._vars = {}
        self._linhas = {}  # valor -> Checkbutton — pra esconder/mostrar sem perder a ordem
        for i, valor in enumerate(valores):
            var = tk.BooleanVar(value=(valor in selecionados))
            chk = tk.Checkbutton(
                corpo, text=valor, variable=var, bg=TEMA["card"], fg=TEMA["titulo"],
                selectcolor=TEMA["card"], activebackground=TEMA["card"],
                activeforeground=TEMA["titulo"], anchor="w", font=("Segoe UI", 10),
            )
            chk.grid(row=i, column=0, sticky="w")
            self._vars[valor] = var
            self._linhas[valor] = chk

    def _ao_digitar_busca(self, event=None):
        texto = self.ent_busca.get().strip().lower()
        for valor, chk in self._linhas.items():
            bate = (not texto) or (texto in str(valor).lower())
            if bate:
                chk.grid()  # volta a aparecer na mesma linha/posição de antes
            else:
                chk.grid_remove()  # esconde sem perder o estado marcado/desmarcado

    def _marcar(self, valor):
        """Marca/desmarca só o que está visível no momento (respeita a
        busca) — "Marcar todos" depois de pesquisar "CA-14" marca só as
        obras que batem com "CA-14", sem mexer no resto."""
        for nome_valor, var in self._vars.items():
            if self._linhas[nome_valor].grid_info():  # dict vazio == escondido por grid_remove()
                var.set(valor)

    def _confirmar(self):
        self.resultado = {v for v, var in self._vars.items() if var.get()}
        self.destroy()


def _paleta():
    """Cores das categorias nos gráficos: a do tema (Dia/Noturno/Daltônico)
    primeiro, depois complementares — no daltônico, só Okabe-Ito."""
    if TEMA.modo == "daltonico_vv":
        extras = ["#F0E442", "#D55E00", "#999999", "#CC79A7"]
    elif TEMA.modo == "daltonico_aa":
        extras = ["#9E9E9E", "#F48FB1", "#80CBC4", "#000000"]
    else:
        extras = ["#5AA9C9", "#D98C5F", "#8E7CC3", "#4FB6A8", "#C9A227", "#B07D62", "#8DA3C9"]
    return list(TEMA["grafico"]) + extras


# rótulo pequeno acima do título de cada gráfico (como nos cartões do Painel)
SOBRETITULOS = {
    "Problemas por Obra": "Portfólio",
    "Ajustes por Projetista": "Equipe",
    "Status dos Problemas": "Em aberto",
    "Causas por Disciplina": "Disciplinas",
    "Porcentagem por Disciplina": "Disciplinas",
    "Problemas por Mês": "Evolução",
    "Média Ponderada por Mês": "Evolução",
    "Radar de Desenvolvimento": "Tipos",
    "Tipos de Problemas": "Tipos",
}


class TelaDashboard(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self._canvases = []  # FigureCanvasTkAgg abertos, para fechar as figuras ao trocar de tela

        self.area = AreaRolavel(self)
        self.area.pack(fill=tk.BOTH, expand=True)
        self.pagina = tk.Frame(self.area.interno, bg=TEMA["pagina"])
        self.pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(24, 28))

        self._montar_toolbar()
        self._montar_filtros()
        self._montar_corpo()
        self.atualizar()

    # ---------- estrutura ----------
    def _montar_toolbar(self):
        """Cabeçalho no padrão das outras telas (migalhas, título e
        "Atualizar"); o tema fica só no seletor da barra superior."""
        cab, direita = cabecalho_pagina(
            self.pagina, "Relatório", "Relatório detalhado",
            "Gráficos por obra, projetista, disciplina, status e tipo — com filtros combináveis.",
            migalhas=[("Início", self.app.abrir_tela_home), ("Relatório detalhado", None)])
        cab.pack(fill=tk.X, pady=(0, 18))
        Botao(direita, "Atualizar dados", variante="primario", icone=Icone.ATUALIZAR, altura=34, tamanho_fonte=9,
              comando=self.app.sincronizar_banco).pack(anchor="e")

    def _montar_filtros(self):
        usuario = self.app.usuario_atual or {}
        eh_gestor = eh_gestor_dashboard(usuario)
        issues_visiveis = filtrar_por_papel(self.app.issues, usuario)

        cartao = Cartao(self.pagina, padding=(18, 14))
        cartao.pack(fill=tk.X, pady=(0, 16))
        self.filtro_frame = tk.Frame(cartao.corpo, bg=TEMA["card"])
        self.filtro_frame.pack(fill=tk.X)

        def _campo(rotulo_texto, coluna):
            caixa = tk.Frame(self.filtro_frame, bg=TEMA["card"])
            caixa.grid(row=0, column=coluna, padx=(0, 12), sticky="w")
            rotulo(caixa, espacar(rotulo_texto), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(0, 4))
            return caixa

        def _combo(rotulo_texto, coluna, valores, largura=150):
            caixa = _campo(rotulo_texto, coluna)
            cb = ComboArredondado(caixa, valores, largura=largura, altura=36)
            cb.pack()
            cb.combo.current(0)
            cb.combo.bind("<<ComboboxSelected>>", lambda e: self.atualizar(), add="+")
            return cb.combo  # mesma interface do ttk.Combobox (get/set/current/["values"])

        tipos = sorted({i.get("tipo", "").strip() for i in issues_visiveis if (i.get("tipo") or "").strip()})
        self.meses_disponiveis = list(contagem_por_mes(issues_visiveis).keys())
        self.meses_selecionados = set(self.meses_disponiveis)  # começa com "todos"
        self.status_selecionados = set(LISTA_STATUS)  # começa com "todos"
        self.obras_disponiveis = list(self.app.obras_lista)
        self.obras_selecionadas = set(self.obras_disponiveis)  # começa com "todas"

        self.btn_obra = self._criar_botao_selecao_multipla(_campo("Obra", 0), lambda: self._abrir_popup_multiplo(
            "Obra", self.obras_disponiveis, self.obras_selecionadas, self._ao_confirmar_obra, pesquisavel=True))
        self._atualizar_texto_botao(self.btn_obra, self.obras_selecionadas, self.obras_disponiveis)

        self.cb_disciplina = _combo("Disciplina", 1, ["Todas"] + LISTA_DISCIPLINAS, largura=120)
        self.cb_tipo = _combo("Tipo", 2, ["Todos"] + tipos)

        self.btn_status = self._criar_botao_selecao_multipla(_campo("Status", 3), lambda: self._abrir_popup_multiplo(
            "Status", LISTA_STATUS, self.status_selecionados, self._ao_confirmar_status))
        self.btn_mes = self._criar_botao_selecao_multipla(_campo("Mês", 4), lambda: self._abrir_popup_multiplo(
            "Mês", self.meses_disponiveis, self.meses_selecionados, self._ao_confirmar_mes))
        self._atualizar_texto_botao(self.btn_status, self.status_selecionados, LISTA_STATUS)
        self._atualizar_texto_botao(self.btn_mes, self.meses_selecionados, self.meses_disponiveis)

        self.cb_projetista = None
        if eh_gestor:
            nomes = listar_nomes_projetistas(issues_visiveis)
            self.cb_projetista = _combo("Projetista", 5, ["Todos"] + nomes, largura=200)

        limpar = tk.Frame(self.filtro_frame, bg=TEMA["card"])
        limpar.grid(row=0, column=20, sticky="sw", pady=(18, 0))
        Botao(limpar, "Limpar filtros", variante="link", icone=Icone.FECHAR, altura=30, tamanho_fonte=9,
              comando=self._limpar_filtros).pack()

    # ---------- filtros de seleção múltipla (Obra/Mês/Status) ----------
    def _criar_botao_selecao_multipla(self, caixa, comando):
        btn = Botao(caixa, "Todos", comando=comando, variante="secundario", icone_direita=Icone.CHEVRON_BAIXO,
                    largura=150, altura=36, tamanho_fonte=9, negrito=False)
        btn.pack()
        return btn

    @staticmethod
    def _atualizar_texto_botao(botao, selecionados, disponiveis):
        if not disponiveis or set(selecionados) == set(disponiveis):
            texto = "Todos"
        elif not selecionados:
            texto = "Nenhum"
        elif len(selecionados) <= 2:
            texto = ", ".join(sorted(selecionados))
        else:
            texto = f"{len(selecionados)} selecionados"
        if hasattr(botao, "config_texto"):
            botao.config_texto(texto if len(texto) <= 18 else texto[:17] + "…")
        else:
            botao.config(text=texto)

    def _abrir_popup_multiplo(self, titulo, valores, selecionados_atuais, ao_confirmar, pesquisavel=False):
        popup = _PopupSelecaoMultipla(self, titulo, valores, selecionados_atuais, pesquisavel=pesquisavel)
        if popup.resultado is not None:
            ao_confirmar(popup.resultado)

    def _ao_confirmar_obra(self, novo_conjunto):
        self.obras_selecionadas = novo_conjunto
        self._atualizar_texto_botao(self.btn_obra, self.obras_selecionadas, self.obras_disponiveis)
        self.atualizar()

    def _ao_confirmar_status(self, novo_conjunto):
        self.status_selecionados = novo_conjunto
        self._atualizar_texto_botao(self.btn_status, self.status_selecionados, LISTA_STATUS)
        self.atualizar()

    def _ao_confirmar_mes(self, novo_conjunto):
        self.meses_selecionados = novo_conjunto
        self._atualizar_texto_botao(self.btn_mes, self.meses_selecionados, self.meses_disponiveis)
        self.atualizar()

    def _limpar_filtros(self):
        for cb in (self.cb_disciplina, self.cb_tipo, self.cb_projetista):
            if cb is not None:
                cb.current(0)
        self.obras_selecionadas = set(self.obras_disponiveis)
        self.status_selecionados = set(LISTA_STATUS)
        self.meses_selecionados = set(self.meses_disponiveis)
        self._atualizar_texto_botao(self.btn_obra, self.obras_selecionadas, self.obras_disponiveis)
        self._atualizar_texto_botao(self.btn_status, self.status_selecionados, LISTA_STATUS)
        self._atualizar_texto_botao(self.btn_mes, self.meses_selecionados, self.meses_disponiveis)
        self.atualizar()

    def sincronizar(self):
        """Chamado por app.sincronizar_banco() (botão "🔄 Atualizar") depois
        de recarregar self.app.issues do disco — issues novas podem trazer
        obras/tipos/meses que ainda não existiam nas opções dos filtros."""
        usuario = self.app.usuario_atual or {}
        issues_visiveis = filtrar_por_papel(self.app.issues, usuario)

        tinha_todas_obras_marcadas = self.obras_selecionadas == set(self.obras_disponiveis)
        self.obras_disponiveis = list(self.app.obras_lista)
        self.obras_selecionadas = (
            set(self.obras_disponiveis) if tinha_todas_obras_marcadas
            else self.obras_selecionadas & set(self.obras_disponiveis)
        )
        self._atualizar_texto_botao(self.btn_obra, self.obras_selecionadas, self.obras_disponiveis)

        tipos_atuais = ["Todos"] + sorted(
            {i.get("tipo", "").strip() for i in issues_visiveis if (i.get("tipo") or "").strip()}
        )
        self.cb_tipo["values"] = tipos_atuais
        if self.cb_tipo.get() not in tipos_atuais:
            self.cb_tipo.set("Todos")

        tinha_tudo_marcado = self.meses_selecionados == set(self.meses_disponiveis)
        self.meses_disponiveis = list(contagem_por_mes(issues_visiveis).keys())
        self.meses_selecionados = (
            set(self.meses_disponiveis) if tinha_tudo_marcado
            else self.meses_selecionados & set(self.meses_disponiveis)
        )
        self._atualizar_texto_botao(self.btn_mes, self.meses_selecionados, self.meses_disponiveis)

        if self.cb_projetista is not None:
            nomes_atuais = ["Todos"] + listar_nomes_projetistas(issues_visiveis)
            self.cb_projetista["values"] = nomes_atuais
            if self.cb_projetista.get() not in nomes_atuais:
                self.cb_projetista.set("Todos")

        self.atualizar()

    def _montar_corpo(self):
        """KPIs, grade de gráficos e tabela — a rolagem é da AreaRolavel
        (só captura a roda do mouse com o ponteiro em cima da tela)."""
        self.frame_kpis = tk.Frame(self.pagina, bg=TEMA["pagina"])
        self.frame_kpis.pack(fill=tk.X, pady=(0, 16))

        self.frame_graficos = tk.Frame(self.pagina, bg=TEMA["pagina"])
        self.frame_graficos.pack(fill=tk.X)

        self.frame_tabela = tk.Frame(self.pagina, bg=TEMA["pagina"])
        self.frame_tabela.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    # ---------- dados filtrados ----------
    def _issues_filtradas(self):
        usuario = self.app.usuario_atual or {}
        projetista_filtro = None
        if self.cb_projetista is not None and self.cb_projetista.get() != "Todos":
            projetista_filtro = self.cb_projetista.get()

        issues = filtrar_por_papel(self.app.issues, usuario, projetista_filtro=projetista_filtro)
        # Com TUDO marcado (estado padrão), equivale a "sem filtro" — inclui
        # até issues antigas sem o campo status/data preenchido. Só vira um
        # filtro de fato quando o usuário desmarca algo no popup.
        obra_filtro = None if self.obras_selecionadas == set(self.obras_disponiveis) else self.obras_selecionadas
        status_filtro = None if self.status_selecionados == set(LISTA_STATUS) else self.status_selecionados
        mes_filtro = None if self.meses_selecionados == set(self.meses_disponiveis) else self.meses_selecionados
        issues = aplicar_filtros(
            issues,
            obra=obra_filtro,
            disciplina=None if self.cb_disciplina.get() == "Todas" else self.cb_disciplina.get(),
            tipo=None if self.cb_tipo.get() == "Todos" else self.cb_tipo.get(),
            status=status_filtro,
            ano_mes=mes_filtro,
        )
        return issues

    # ---------- atualização geral ----------
    def atualizar(self):
        issues = self._issues_filtradas()
        self._fechar_graficos_antigos()
        self._montar_kpis(issues)
        self._montar_graficos(issues)
        self._montar_tabela(issues)

    def _fechar_graficos_antigos(self):
        for canvas in self._canvases:
            try:
                import matplotlib.pyplot as plt
                plt.close(canvas.figure)
                canvas.get_tk_widget().destroy()
            except Exception:
                pass
        self._canvases = []
        for widget in self.frame_graficos.winfo_children():
            widget.destroy()

    # ---------- KPIs ----------
    def _montar_kpis(self, issues):
        for widget in self.frame_kpis.winfo_children():
            widget.destroy()

        kpis = calcular_kpis(issues)
        cartoes = (
            ("Total", kpis["total"], TEMA["primario"] if not TEMA.esta_escuro() else TEMA["acento"], Icone.PRANCHETA),
            ("Novo", kpis["problema"], CORES_STATUS["Novo"], Icone.ALERTA),
            ("Respondido", kpis["respondido"], CORES_STATUS["Respondido"], Icone.MENSAGEM),
            ("Reaberto", kpis["reaberto"], CORES_STATUS["Reaberto"], Icone.ATUALIZAR),
            ("Fechado", kpis["fechado"], CORES_STATUS["Fechado"], Icone.CHECK),
        )
        for col, (titulo, valor, cor, glifo) in enumerate(cartoes):
            self.frame_kpis.grid_columnconfigure(col, weight=1, uniform="kpi")
            cartao = Cartao(self.frame_kpis, padding=(18, 16))
            cartao.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0 if col == 4 else 6))
            c = cartao.corpo
            fundo = cor if TEMA.esta_escuro() else tom_claro(cor, 0.85)
            QuadradoIcone(c, glifo, cores=(fundo, "#FFFFFF" if TEMA.esta_escuro() else cor), tamanho=40
                          ).pack(side=tk.LEFT, padx=(0, 14))
            textos = tk.Frame(c, bg=c["bg"])
            textos.pack(side=tk.LEFT)
            rotulo(textos, espacar(titulo), 8, "semi", cor=TEMA["eyebrow"]).pack(anchor="w")
            rotulo(textos, str(valor), 20, "semi").pack(anchor="w")

    # ---------- gráficos ----------
    def _nova_figura(self, parent, titulo, figsize=(4.0, 2.7), projection=None, left=None, right=None, top=None):
        """Figura "de cartão": fundo do cartão, sem moldura pesada, fonte
        Segoe UI e eixos discretos. O título fica fora (no cartão, em Tk)."""
        fig = Figure(figsize=figsize, dpi=90)
        fig.patch.set_facecolor(TEMA["card"])
        ax = fig.add_subplot(111, projection=projection) if projection else fig.add_subplot(111)
        ax.set_facecolor(TEMA["card"])
        fig.subplots_adjust(left=0.18 if left is None else left, right=0.95 if right is None else right,
                            top=0.95 if top is None else top, bottom=0.14)
        if projection is None:
            for lado in ("top", "right"):
                ax.spines[lado].set_visible(False)
            for lado in ("left", "bottom"):
                ax.spines[lado].set_color(TEMA["card_borda"])
            ax.tick_params(colors=TEMA["texto_fraco"], labelsize=7, length=0)
            ax.grid(axis="x", color=TEMA["linha"], linewidth=0.8)
            ax.set_axisbelow(True)
        for texto in ax.get_xticklabels() + ax.get_yticklabels():
            texto.set_fontfamily("Segoe UI")

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().configure(bg=TEMA["card"], highlightthickness=0)
        self._canvases.append(canvas)
        return fig, ax, canvas

    def _sem_dados(self, ax):
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", color=TEMA["texto_fraco"], transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])

    @staticmethod
    def _rotulo_compacto(nome, max_chars=16):
        """Nome completo (ex.: "Lucas Coutinho Ferreira Gomes") ocupava
        espaço demais no eixo — mantém só primeiro e último nome (ainda
        identifica a pessoa) e, se mesmo assim passar de `max_chars`,
        corta com "…"."""
        texto = str(nome)
        partes = texto.split()
        if len(partes) > 2:
            texto = f"{partes[0]} {partes[-1]}"
        if len(texto) > max_chars:
            texto = texto[:max_chars - 1].rstrip() + "…"
        return texto

    def _grafico_barra_horizontal(self, parent, titulo, contagem, limite=8):
        itens = list(contagem.items())[:limite]
        rotulos_compactos = [self._rotulo_compacto(k) for k, _ in itens]
        maior_rotulo = max((len(r) for r in rotulos_compactos), default=0)
        margem_esquerda = min(0.4, 0.16 + max(0, maior_rotulo - 8) * 0.011)
        fig, ax, canvas = self._nova_figura(parent, titulo, left=margem_esquerda)
        if not itens:
            self._sem_dados(ax)
        else:
            rotulos = rotulos_compactos[::-1]
            valores = [v for _, v in itens][::-1]
            paleta = _paleta()
            cores = [paleta[0]] + [paleta[1]] * (len(itens) - 1)  # destaque no maior, resto na 2ª cor
            ax.barh(rotulos, valores, color=cores[::-1], height=0.62)
            for y, v in enumerate(valores):
                ax.text(v, y, f" {v}", va="center", fontsize=7, color=TEMA["texto"], fontfamily="Segoe UI")
            ax.set_xlim(0, max(valores) * 1.15)
        return canvas

    @staticmethod
    def _margem_direita_legenda(rotulos):
        """Reserva espaço à direita dos eixos para a legenda — sem isso,
        o texto de rótulos longos (ex.: "Incompatibilidade") cai fora da
        área visível do canvas."""
        maior = max((len(str(r)) for r in rotulos), default=0)
        return max(0.42, 0.92 - maior * 0.018)

    def _grafico_donut(self, parent, titulo, contagem, cores_fixas=None):
        rotulos = list(contagem.keys())
        fig, ax, canvas = self._nova_figura(parent, titulo, right=self._margem_direita_legenda(rotulos))
        if not contagem:
            self._sem_dados(ax)
        else:
            valores = list(contagem.values())
            paleta = _paleta()
            if cores_fixas:
                cores = [cores_fixas.get(r, TEMA["texto_fraco"]) for r in rotulos]
            else:
                cores = [paleta[i % len(paleta)] for i in range(len(rotulos))]
            wedges, _ = ax.pie(valores, colors=cores, startangle=90, counterclock=False,
                               wedgeprops=dict(width=0.32, edgecolor=TEMA["card"], linewidth=2))
            total = sum(valores)
            ax.text(0, 0.06, f"{round(total) if isinstance(total, float) else total}", ha="center", va="center",
                    fontsize=15, color=TEMA["titulo"], fontfamily="Segoe UI", fontweight="bold")
            ax.text(0, -0.2, "%" if all(isinstance(v, float) for v in valores) else "itens", ha="center",
                    va="center", fontsize=7, color=TEMA["texto_fraco"], fontfamily="Segoe UI")
            ax.legend(wedges, [f"{r}  {v}" for r, v in zip(rotulos, valores)], loc="center left",
                      bbox_to_anchor=(1.0, 0.5), fontsize=8, labelcolor=TEMA["texto"], frameon=False,
                      prop={"family": "Segoe UI", "size": 8}, handlelength=0.8, handleheight=0.8)
        return canvas

    def _grafico_linha(self, parent, titulo, serie, cor):
        fig, ax, canvas = self._nova_figura(parent, titulo, left=0.12)
        if not serie:
            self._sem_dados(ax)
        else:
            meses = list(serie.keys())
            valores = list(serie.values())
            ax.plot(meses, valores, marker="o", color=cor, linewidth=2, markersize=5,
                    markerfacecolor=TEMA["card"], markeredgewidth=2)
            ax.fill_between(range(len(meses)), valores, color=cor, alpha=0.12)
            ax.grid(axis="x", visible=False)
            ax.grid(axis="y", color=TEMA["linha"], linewidth=0.8)
            ax.tick_params(axis="x", labelsize=7, rotation=0)
        return canvas

    def _grafico_radar(self, parent, titulo, contagem):
        fig, ax, canvas = self._nova_figura(parent, titulo, figsize=(4.0, 2.9), projection="polar",
                                            top=0.86, left=0.1, right=0.9)
        if not contagem:
            self._sem_dados(ax)
        else:
            categorias = list(contagem.keys())
            valores = list(contagem.values())
            n = len(categorias)
            angulos = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
            valores_fechado = valores + valores[:1]
            angulos_fechado = angulos + angulos[:1]
            cor = _paleta()[0]
            ax.plot(angulos_fechado, valores_fechado, color=cor, linewidth=2)
            ax.fill(angulos_fechado, valores_fechado, color=cor, alpha=0.2)
            ax.set_xticks(angulos)
            ax.set_xticklabels(categorias, color=TEMA["texto"], fontsize=7, fontfamily="Segoe UI")
            ax.tick_params(axis="x", pad=10)
            ax.spines["polar"].set_color(TEMA["card_borda"])
            ax.grid(color=TEMA["linha"])
            maximo = max(valores) if valores else 0
            if maximo > 0:
                ax.set_ylim(0, maximo * 1.15)
                ax.set_rgrids([round(maximo * f, 1) for f in (0.25, 0.5, 0.75, 1.0)],
                              fontsize=6, color=TEMA["texto_fraco"])
            if n:
                ax.set_rlabel_position(180 / n)
        return canvas

    def _grafico_barra_100(self, parent, titulo, contagem):
        fig, ax, canvas = self._nova_figura(parent, titulo, top=0.62, left=0.05)
        total = sum(contagem.values())
        if not total:
            self._sem_dados(ax)
        else:
            esquerda = 0
            paleta = _paleta()
            for i, (rotulo_tipo, valor) in enumerate(contagem.items()):
                largura = valor / total * 100
                ax.barh([""], [largura], left=esquerda, color=paleta[i % len(paleta)], label=rotulo_tipo,
                        height=0.5, edgecolor=TEMA["card"], linewidth=1.5)
                if largura >= 8:
                    ax.text(esquerda + largura / 2, 0, f"{round(largura)}%", ha="center", va="center",
                            fontsize=7, color="#FFFFFF", fontfamily="Segoe UI", fontweight="bold")
                esquerda += largura
            ax.set_xlim(0, 100)
            ax.set_yticks([])
            ax.spines["left"].set_visible(False)
            ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=False, handlelength=0.8,
                      handleheight=0.8, columnspacing=1.0, labelcolor=TEMA["texto"],
                      prop={"family": "Segoe UI", "size": 7})
        return canvas

    def _montar_graficos(self, issues):
        # "Status dos Problemas" só mostra o que ainda está em aberto/em
        # andamento (Novo, Respondido, Reaberto) — Fechado não entra
        # nesse gráfico, por pedido explícito (ele já é visível no KPI).
        status_em_aberto = {
            k: v for k, v in contagem_por_status(issues).items() if k != "Fechado"
        }
        linhas_colunas = [
            (contagem_por_obra(issues), "Problemas por Obra", "barra"),
            (contagem_por_projetista(issues), "Ajustes por Projetista", "barra"),
            (status_em_aberto, "Status dos Problemas", "donut_status"),
            (contagem_por_disciplina(issues), "Causas por Disciplina", "barra"),
            (percentual_por_disciplina(issues), "Porcentagem por Disciplina", "donut"),
            (None, "Problemas por Mês", "linha"),
            (None, "Média Ponderada por Mês", "linha_media"),
            (contagem_por_tipo(issues), "Radar de Desenvolvimento", "radar"),
            (contagem_por_tipo(issues), "Tipos de Problemas", "barra100"),
        ]

        for col in range(3):
            self.frame_graficos.grid_columnconfigure(col, weight=1, uniform="graf")

        paleta = _paleta()
        for indice, (dados, titulo, tipo) in enumerate(linhas_colunas):
            col = indice % 3
            cartao = Cartao(self.frame_graficos, padding=(16, 14))
            cartao.grid(row=indice // 3, column=col, sticky="nsew",
                        padx=(0 if col == 0 else 6, 0 if col == 2 else 6), pady=(0, 12))
            celula = cartao.corpo
            cab, _ = cabecalho_cartao(celula, SOBRETITULOS.get(titulo, ""), titulo)
            cab.pack(fill=tk.X, pady=(0, 6))

            if tipo == "barra":
                canvas = self._grafico_barra_horizontal(celula, titulo, dados)
            elif tipo == "donut_status":
                canvas = self._grafico_donut(celula, titulo, dados, cores_fixas=CORES_STATUS)
            elif tipo == "donut":
                canvas = self._grafico_donut(celula, titulo, dados)
            elif tipo == "linha":
                canvas = self._grafico_linha(celula, titulo, contagem_por_mes(issues), paleta[0])
            elif tipo == "linha_media":
                canvas = self._grafico_linha(celula, titulo, media_movel_por_mes(issues), paleta[1])
            elif tipo == "radar":
                canvas = self._grafico_radar(celula, titulo, dados)
            else:  # barra100
                canvas = self._grafico_barra_100(celula, titulo, dados)

            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------- tabela ----------
    def _montar_tabela(self, issues):
        for widget in self.frame_tabela.winfo_children():
            widget.destroy()

        cartao = Cartao(self.frame_tabela, padding=(16, 14))
        cartao.pack(fill=tk.BOTH, expand=True)
        c = cartao.corpo
        cab, direita = cabecalho_cartao(c, "Registros filtrados", "Descrição dos Problemas")
        cab.pack(fill=tk.X, pady=(0, 10))
        Pilula(direita, f"{len(issues)} registro{'s' if len(issues) != 1 else ''}",
               cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=24).pack()

        colunas = ("titulo", "obra", "disciplina", "tipo", "status", "atribuido_para", "data_criacao")
        rotulos = ("Título", "Obra", "Disciplina", "Tipo", "Status", "Atribuído para", "Criado em")

        tree_frame = tk.Frame(c, bg=TEMA["card"])
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(tree_frame, columns=colunas, show="headings", height=10, style="Cartao.Treeview")
        for col, rot in zip(colunas, rotulos):
            tree.heading(col, text=espacar(rot), anchor="w")
            tree.column(col, width=260 if col == "titulo" else 120, anchor="w", stretch=col == "titulo")
        tree.tag_configure("impar", background=TEMA["pagina"])

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview, style="Fino.Vertical.TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for n, issue in enumerate(issues):
            tree.insert("", tk.END, values=tuple(issue.get(col, "") or SEM_VALOR for col in colunas),
                        tags=("impar",) if n % 2 else ())
        tree.bind("<Double-1>", lambda e: self._abrir_na_consulta(tree, issues))

    def _abrir_na_consulta(self, tree, issues):
        selecao = tree.selection()
        if selecao:
            issue = issues[tree.index(selecao[0])]
            self.app.abrir_tela_consulta(issue_id=issue["id"])
