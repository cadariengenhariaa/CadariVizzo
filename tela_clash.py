"""Painel "⚠ Clash Detection", embutido como aba dentro do visualizador
de IFC (`ifc_viewer.IFCViewerFrame`) — fica ao lado das abas Issues/
Elemento/Modelos/Níveis de propósito para que, durante a análise de
interferências, o usuário continue podendo clicar num elemento e criar
uma issue normalmente, sem trocar de tela.

Roda o motor de detecção sobre os arquivos já carregados no
visualizador (`viewer.arquivos_ifc` — não existe um carregador de IFC
próprio aqui), lista/filtra os resultados, permite editar as regras
(matriz de disciplinas, tolerâncias, folgas, exclusões) e exportar o
relatório (PDF/XLSX/BCF/JSON)."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from clash import armazenamento
from clash.config_regras import carregar_regras, salvar_regras
from clash.motor import rodar_clash
from clash.selecao import SelecaoLado, agrupar_por_arquivo
from clash.relatorio import bcf as bcf_export
from clash.relatorio import json_export, pdf as pdf_export, xlsx as xlsx_export
from clash.relatorio.dados_relatorio import aplicar_filtros, montar_resumo_executivo
from auth.usuarios import listar_nomes_ativos
from config import TEMA

STATUS_CLASH = ["Novo", "Em análise", "Atribuído", "Reaberto", "Resolvido", "Aprovado", "Aceito"]
SEVERIDADES = ["Critica", "Alta", "Media", "Baixa"]
COR_CLASH_A01 = (0.94, 0.35, 0.35)
COR_CLASH_B01 = (0.33, 0.55, 0.95)

TODOS = "— Todos —"


class PainelClash(tk.Frame):
    def __init__(self, parent, viewer):
        super().__init__(parent, bg=TEMA["bg"])
        self.viewer = viewer

        self.regras = carregar_regras()
        self.resultado_atual = None
        self.clash_atual_id = None
        self.selecao_a = SelecaoLado()
        self.selecao_b = SelecaoLado()

        self._montar_toolbar()
        self._montar_corpo()
        self.atualizar_arvore_selecao()

    @property
    def arquivos_ifc(self):
        """Mesmos arquivos já carregados no visualizador 3D — este
        painel não tem (nem precisa de) um carregador de IFC próprio."""
        return self.viewer.arquivos_ifc

    # ---------- construção da UI ----------
    def _montar_toolbar(self):
        toolbar = tk.Frame(self, bd=1, relief=tk.RAISED, bg=TEMA["surface"])
        toolbar.pack(side=tk.TOP, fill=tk.X)

        tk.Button(toolbar, text="▶ Rodar Clash", command=self.rodar_clash,
                  bg=TEMA["sucesso"], fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5, pady=5)

        self.lbl_progresso = tk.Label(toolbar, text="", bg=TEMA["surface"], fg=TEMA["texto_fraco"],
                                       wraplength=180, justify="left")
        self.lbl_progresso.pack(side=tk.LEFT, padx=10)

        tk.Button(toolbar, text="💾 Exportar", command=self.abrir_exportar,
                  bg=TEMA["atencao"], fg=TEMA["acento_texto"], font=("Arial", 9, "bold")
                  ).pack(side=tk.LEFT, padx=10, pady=5)

    def _montar_corpo(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._montar_tab_selecao()
        self._montar_tab_resultados()
        self._montar_tab_regras()
        self._montar_tab_resumo()

    # ---------- aba Seleção (A/B, estilo Navisworks) ----------
    def _montar_tab_selecao(self):
        self.tab_selecao = tk.Frame(self.notebook, bg=TEMA["bg"])
        self.notebook.add(self.tab_selecao, text="Seleção")

        tk.Label(
            self.tab_selecao,
            text="Marque os arquivos/níveis de cada lado — o clash testa tudo que está em A "
                 "contra tudo que está em B. Marcar o arquivo marca todos os níveis dele de uma vez.",
            bg=TEMA["bg"], fg=TEMA["texto_fraco"], font=("Arial", 8), wraplength=600, justify="left",
        ).pack(fill=tk.X, padx=5, pady=(5, 8), anchor="w")

        corpo = tk.Frame(self.tab_selecao, bg=TEMA["bg"])
        corpo.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        corpo.columnconfigure(0, weight=1)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)

        self.tree_selecao_a = self._montar_arvore_selecao(corpo, "Seleção A", coluna=0, lado="A")
        self.tree_selecao_b = self._montar_arvore_selecao(corpo, "Seleção B", coluna=1, lado="B")

    def _montar_arvore_selecao(self, pai, titulo, coluna, lado):
        moldura = tk.Frame(pai, bg=TEMA["surface"], highlightbackground=TEMA["borda"], highlightthickness=1)
        moldura.grid(row=0, column=coluna, sticky="nsew", padx=3)

        tk.Label(moldura, text=titulo, bg=TEMA["surface"], fg=TEMA["texto"],
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=5, pady=5)

        tree = ttk.Treeview(moldura, columns=("marcar",), show="tree headings", height=14)
        tree.heading("#0", text="Arquivo / Nível")
        tree.heading("marcar", text="Marcar")
        tree.column("#0", width=220)
        tree.column("marcar", width=60, anchor="center")
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        tree.bind("<Button-1>", lambda e, l=lado: self._clique_selecao(e, l))
        return tree

    def _selecao_do_lado(self, lado):
        return self.selecao_a if lado == "A" else self.selecao_b

    def _arvore_do_lado(self, lado):
        return self.tree_selecao_a if lado == "A" else self.tree_selecao_b

    @staticmethod
    def _iid_arquivo(caminho):
        return f"arquivo::{caminho}"

    @staticmethod
    def _iid_nivel(caminho, nivel_guid):
        return f"nivel::{caminho}::{nivel_guid or '—sem-nivel—'}"

    def atualizar_arvore_selecao(self):
        """Reconstrói as duas árvores a partir dos arquivos/níveis
        carregados no visualizador — chamado ao abrir o painel e sempre
        que um modelo é adicionado/removido (ver ifc_viewer.py)."""
        caminhos_validos = set(self.arquivos_ifc.keys())
        self.selecao_a.limitar_aos_arquivos(caminhos_validos)
        self.selecao_b.limitar_aos_arquivos(caminhos_validos)

        agrupado = agrupar_por_arquivo(self.viewer.niveis_info)
        # só mostra arquivos que de fato têm modelo carregado (niveis_info
        # pode, em teoria, ficar momentaneamente desatualizado)
        agrupado = {c: niveis for c, niveis in agrupado.items() if c in caminhos_validos}

        for lado in ("A", "B"):
            self._redesenhar_arvore(lado, agrupado)

    def _redesenhar_arvore(self, lado, agrupado):
        tree = self._arvore_do_lado(lado)
        selecao = self._selecao_do_lado(lado)
        tree.delete(*tree.get_children())

        if not agrupado:
            tree.insert("", tk.END, text="Nenhum modelo carregado.", values=("",))
            return

        for caminho, niveis in sorted(agrupado.items()):
            nome_arquivo = os.path.basename(caminho)
            if selecao.arquivo_marcado(caminho, niveis):
                marca = "✔"
            elif selecao.arquivo_parcial(caminho, niveis):
                marca = "◐"
            else:
                marca = "☐"
            tree.insert("", tk.END, iid=self._iid_arquivo(caminho), text=nome_arquivo,
                        values=(marca,), open=True)
            for nivel_guid, nome_nivel, _elevacao in niveis:
                marca_nivel = "✔" if selecao.nivel_marcado(caminho, nivel_guid) else "☐"
                tree.insert(
                    self._iid_arquivo(caminho), tk.END, iid=self._iid_nivel(caminho, nivel_guid),
                    text=nome_nivel, values=(marca_nivel,),
                )

    def _clique_selecao(self, event, lado):
        tree = self._arvore_do_lado(lado)
        if tree.identify_region(event.x, event.y) != "cell":
            return
        linha = tree.identify_row(event.y)
        coluna = tree.identify_column(event.x)
        if not linha or coluna != "#1":  # "#1" = coluna "Marcar"
            return

        selecao = self._selecao_do_lado(lado)
        agrupado = agrupar_por_arquivo(self.viewer.niveis_info)

        if linha.startswith("arquivo::"):
            caminho = linha[len("arquivo::"):]
            niveis = agrupado.get(caminho, [])
            selecao.definir_arquivo(caminho, niveis, not selecao.arquivo_marcado(caminho, niveis))
        elif linha.startswith("nivel::"):
            caminho = linha.split("::", 2)[1]
            niveis = agrupado.get(caminho, [])
            nivel_guid = next(
                (ng for ng, _, _ in niveis if self._iid_nivel(caminho, ng) == linha), None
            )
            selecao.alternar_nivel(caminho, nivel_guid)
        else:
            return

        self._redesenhar_arvore(lado, agrupado)
        return "break"  # evita que o clique também dispare a seleção normal da linha

    # ---------- aba Resultados ----------
    def _montar_tab_resultados(self):
        self.tab_resultados = tk.Frame(self.notebook, bg=TEMA["bg"])
        self.notebook.add(self.tab_resultados, text="Resultados")

        filtros = tk.Frame(self.tab_resultados, bg=TEMA["surface"])
        filtros.pack(fill=tk.X, padx=5, pady=5)

        def combo_filtro(texto, valores, linha):
            tk.Label(filtros, text=texto, bg=TEMA["surface"], fg=TEMA["texto"]).grid(
                row=linha, column=0, padx=5, pady=3, sticky="w")
            cb = ttk.Combobox(filtros, values=[TODOS] + valores, state="readonly", width=20)
            cb.set(TODOS)
            cb.grid(row=linha, column=1, padx=5, pady=3, sticky="w")
            cb.bind("<<ComboboxSelected>>", lambda e: self.atualizar_lista())
            return cb

        self.cb_filtro_disciplina = combo_filtro("Disciplina:", list(self.regras.disciplinas), 0)
        self.cb_filtro_severidade = combo_filtro("Severidade:", SEVERIDADES, 1)
        self.cb_filtro_status = combo_filtro("Status:", STATUS_CLASH, 2)
        self.cb_filtro_pavimento = combo_filtro("Pavimento:", [], 3)
        self.cb_filtro_responsavel = combo_filtro("Responsável:", list(self.regras.disciplinas), 4)

        colunas = ("ID", "Severidade", "Tipo", "Disciplinas", "Pavimento", "Status", "Rastr.")
        self.tree = ttk.Treeview(self.tab_resultados, columns=colunas, show="headings", height=8)
        for col, largura in zip(colunas, (55, 60, 55, 95, 75, 85, 55)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=largura)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar_na_lista)

        self._montar_detalhe(self.tab_resultados)

    def _montar_detalhe(self, pai):
        self.lbl_detalhe_titulo = tk.Label(pai, text="Selecione uma interferência", font=("Arial", 10, "bold"),
                                            bg=TEMA["bg"], fg=TEMA["texto"], wraplength=300, justify="left")
        self.lbl_detalhe_titulo.pack(pady=(5, 3), padx=5, anchor="w")

        self.lbl_detalhe_info = tk.Label(pai, text="", bg=TEMA["bg"], fg=TEMA["texto_fraco"],
                                          wraplength=300, justify="left", font=("Arial", 8))
        self.lbl_detalhe_info.pack(pady=(0, 8), padx=5, anchor="w")

        form = tk.Frame(pai, bg=TEMA["bg"])
        form.pack(fill=tk.X, padx=5)

        tk.Label(form, text="Status:", bg=TEMA["bg"], fg=TEMA["texto"]).grid(row=0, column=0, sticky="w", pady=2)
        self.cb_status = ttk.Combobox(form, values=STATUS_CLASH, state="readonly", width=18)
        self.cb_status.grid(row=0, column=1, pady=2, sticky="w")

        tk.Label(form, text="Responsável:", bg=TEMA["bg"], fg=TEMA["texto"]).grid(row=1, column=0, sticky="w", pady=2)
        self.cb_responsavel_atrib = ttk.Combobox(form, values=listar_nomes_ativos(), width=18)
        self.cb_responsavel_atrib.grid(row=1, column=1, pady=2, sticky="w")

        tk.Label(form, text="Prazo:", bg=TEMA["bg"], fg=TEMA["texto"]).grid(row=2, column=0, sticky="w", pady=2)
        self.ent_prazo = ttk.Entry(form, width=20)
        self.ent_prazo.grid(row=2, column=1, pady=2, sticky="w")

        tk.Label(form, text="Comentário:", bg=TEMA["bg"], fg=TEMA["texto"]).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 2))
        self.txt_comentario = tk.Text(pai, height=3, font=("Arial", 8),
                                       bg=TEMA["surface_alt"], fg=TEMA["texto"], insertbackground=TEMA["texto"])
        self.txt_comentario.pack(padx=5, fill=tk.X)

        botoes = tk.Frame(pai, bg=TEMA["bg"])
        botoes.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(botoes, text="💾 Salvar", command=self.salvar_detalhe,
                  bg=TEMA["sucesso"], fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, fill=tk.X,
                                                                                   expand=True, padx=(0, 5))
        tk.Button(botoes, text="🎯 Focar no 3D", command=self.focar_no_3d,
                  bg=TEMA["info"], fg="white", font=("Arial", 9, "bold")).pack(side=tk.LEFT, fill=tk.X,
                                                                                 expand=True, padx=(5, 0))

        tk.Label(pai, text="Histórico de status:", bg=TEMA["bg"], fg=TEMA["texto"],
                 font=("Arial", 8, "bold")).pack(anchor="w", padx=5, pady=(8, 2))
        self.txt_historico = tk.Text(pai, height=4, font=("Arial", 8), state=tk.DISABLED,
                                      bg=TEMA["surface_alt"], fg=TEMA["texto_fraco"])
        self.txt_historico.pack(padx=5, pady=(0, 5), fill=tk.X)

    # ---------- aba Regras ----------
    def _montar_tab_regras(self):
        self.tab_regras = tk.Frame(self.notebook, bg=TEMA["bg"])
        self.notebook.add(self.tab_regras, text="Regras")

        topo = tk.Frame(self.tab_regras, bg=TEMA["surface"])
        topo.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(topo, text="Tolerância hard clash (m):", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=0, column=0, padx=5, pady=5, sticky="e")
        self.ent_tolerancia = ttk.Entry(topo, width=8)
        self.ent_tolerancia.insert(0, str(self.regras.tolerancia_hard_clash_m))
        self.ent_tolerancia.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(topo, text="Folga padrão (m):", bg=TEMA["surface"], fg=TEMA["texto"]).grid(
            row=1, column=0, padx=5, pady=5, sticky="e")
        self.ent_folga_padrao = ttk.Entry(topo, width=8)
        self.ent_folga_padrao.insert(0, str(self.regras.folga_padrao_m))
        self.ent_folga_padrao.grid(row=1, column=1, padx=5, pady=5)

        exclusoes_frame = tk.Frame(self.tab_regras, bg=TEMA["surface"])
        exclusoes_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(exclusoes_frame, text="Exclusões automáticas:", bg=TEMA["surface"], fg=TEMA["texto"],
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=5, pady=(5, 2))

        self.var_furo_previsto = tk.BooleanVar(value=self.regras.exclusoes.get("ignorar_furos_previstos", True))
        self.var_mesmo_sistema = tk.BooleanVar(value=self.regras.exclusoes.get("ignorar_mesmo_sistema_conectado", True))
        self.var_isolamento = tk.BooleanVar(value=self.regras.exclusoes.get("ignorar_isolamento_proprio_duto", True))
        for texto, var in (
            ("Ignorar furos/passagens já previstas", self.var_furo_previsto),
            ("Ignorar elementos do mesmo sistema", self.var_mesmo_sistema),
            ("Ignorar isolamento sobre o próprio tubo/duto", self.var_isolamento),
        ):
            tk.Checkbutton(exclusoes_frame, text=texto, variable=var, bg=TEMA["surface"], fg=TEMA["texto"],
                            selectcolor=TEMA["surface_alt"], activebackground=TEMA["surface"]
                            ).pack(anchor="w", padx=15, pady=1)

        tk.Label(self.tab_regras,
                 text="Folga mínima por par de disciplinas — clique duas vezes numa linha para editar. "
                      "Quem decide QUAIS pares são testados agora é a aba \"Seleção\" (A/B).",
                 bg=TEMA["bg"], fg=TEMA["texto_fraco"], font=("Arial", 8), wraplength=320, justify="left"
                 ).pack(fill=tk.X, padx=5, pady=(10, 2), anchor="w")

        add_frame = tk.Frame(self.tab_regras, bg=TEMA["bg"])
        add_frame.pack(fill=tk.X, padx=5, pady=5)
        self.cb_add_disc_a = ttk.Combobox(add_frame, values=list(self.regras.disciplinas), state="readonly", width=8)
        self.cb_add_disc_a.pack(side=tk.LEFT, padx=2)
        tk.Label(add_frame, text="x", bg=TEMA["bg"], fg=TEMA["texto"]).pack(side=tk.LEFT, padx=2)
        self.cb_add_disc_b = ttk.Combobox(add_frame, values=list(self.regras.disciplinas), state="readonly", width=8)
        self.cb_add_disc_b.pack(side=tk.LEFT, padx=2)
        tk.Button(add_frame, text="➕", command=self.adicionar_par_matriz,
                  bg=TEMA["acento"], fg=TEMA["acento_texto"], width=3).pack(side=tk.LEFT, padx=5)
        tk.Button(add_frame, text="🗑 Remover selecionado", command=self.remover_par_matriz,
                  bg=TEMA["critico"], fg="white").pack(side=tk.LEFT, padx=5)

        self.tree_matriz = ttk.Treeview(self.tab_regras, columns=("Par", "Folga (m)"), show="headings", height=10)
        for col, largura in (("Par", 150), ("Folga (m)", 90)):
            self.tree_matriz.heading(col, text=col)
            self.tree_matriz.column(col, width=largura, anchor="center" if col != "Par" else "w")
        self.tree_matriz.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree_matriz.bind("<Double-1>", self._editar_par_matriz)
        self._atualizar_tree_matriz()

        tk.Button(self.tab_regras, text="💾 Salvar Regras", command=self.salvar_regras_tela,
                  bg=TEMA["sucesso"], fg="white", font=("Arial", 9, "bold")).pack(pady=10)

    def _atualizar_tree_matriz(self, manter_selecao=None):
        self.tree_matriz.delete(*self.tree_matriz.get_children())
        for chave, config in sorted(self.regras.matriz_disciplinas.items()):
            self.tree_matriz.insert("", tk.END, iid=chave, values=(
                chave.replace("|", " x "), config.get("folga_m", self.regras.folga_padrao_m),
            ))
        if manter_selecao and self.tree_matriz.exists(manter_selecao):
            self.tree_matriz.selection_set(manter_selecao)

    def adicionar_par_matriz(self):
        disc_a, disc_b = self.cb_add_disc_a.get(), self.cb_add_disc_b.get()
        if not disc_a or not disc_b:
            messagebox.showwarning("Aviso", "Selecione as duas disciplinas.", parent=self)
            return
        chave = self.regras.chave_par(disc_a, disc_b)
        self.regras.matriz_disciplinas[chave] = self.regras.matriz_disciplinas.get(
            chave, {"folga_m": self.regras.folga_padrao_m}
        )
        self._atualizar_tree_matriz()

    def remover_par_matriz(self):
        selecao = self.tree_matriz.selection()
        if not selecao:
            return
        for chave in selecao:
            self.regras.matriz_disciplinas.pop(chave, None)
        self._atualizar_tree_matriz()

    def _editar_par_matriz(self, event=None):
        if self.tree_matriz.identify_region(event.x, event.y) != "cell":
            return
        linha = self.tree_matriz.identify_row(event.y)
        if not linha:
            return
        chave = linha
        config = self.regras.matriz_disciplinas.get(chave, {})

        dialogo = tk.Toplevel(self)
        dialogo.title(f"Editar {chave.replace('|', ' x ')}")
        dialogo.configure(bg=TEMA["surface"])
        dialogo.geometry("300x130")
        dialogo.transient(self.winfo_toplevel())
        dialogo.grab_set()

        tk.Label(dialogo, text="Folga mínima (m):", bg=TEMA["surface"], fg=TEMA["texto"]).pack(
            anchor="w", padx=15, pady=(15, 0))
        ent_folga = ttk.Entry(dialogo, width=10)
        ent_folga.insert(0, str(config.get("folga_m", self.regras.folga_padrao_m)))
        ent_folga.pack(anchor="w", padx=15, pady=5)

        def confirmar():
            try:
                folga = float(ent_folga.get())
            except ValueError:
                messagebox.showwarning("Aviso", "Folga precisa ser um número.", parent=dialogo)
                return
            self.regras.matriz_disciplinas[chave] = {"folga_m": folga}
            self._atualizar_tree_matriz()
            dialogo.destroy()

        tk.Button(dialogo, text="✔ Confirmar", command=confirmar, bg=TEMA["acento"], fg=TEMA["acento_texto"]
                  ).pack(pady=10)

    def salvar_regras_tela(self):
        try:
            self.regras.tolerancia_hard_clash_m = float(self.ent_tolerancia.get())
            self.regras.folga_padrao_m = float(self.ent_folga_padrao.get())
        except ValueError:
            messagebox.showwarning("Aviso", "Tolerância e folga padrão precisam ser números.", parent=self)
            return

        self.regras.exclusoes["ignorar_furos_previstos"] = self.var_furo_previsto.get()
        self.regras.exclusoes["ignorar_mesmo_sistema_conectado"] = self.var_mesmo_sistema.get()
        self.regras.exclusoes["ignorar_isolamento_proprio_duto"] = self.var_isolamento.get()

        dados = self.regras._dados_brutos
        dados["tolerancia_hard_clash_m"] = self.regras.tolerancia_hard_clash_m
        dados["folga_padrao_m"] = self.regras.folga_padrao_m
        dados["exclusoes"] = self.regras.exclusoes
        dados["matriz_disciplinas"] = self.regras.matriz_disciplinas

        salvar_regras(self.regras)
        messagebox.showinfo("OK", "Regras salvas em clash/regras_clash.yaml.", parent=self)

    # ---------- aba Resumo ----------
    def _montar_tab_resumo(self):
        self.tab_resumo = tk.Frame(self.notebook, bg=TEMA["bg"])
        self.notebook.add(self.tab_resumo, text="Resumo")

        self.txt_resumo = tk.Text(self.tab_resumo, font=("Consolas", 9), bg=TEMA["surface_alt"],
                                   fg=TEMA["texto"], state=tk.DISABLED, wrap="word")
        self.txt_resumo.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _atualizar_resumo(self):
        if not self.resultado_atual:
            return
        resumo = montar_resumo_executivo(
            self.resultado_atual["clashes"], self.resultado_atual["pre_checagens"]
        )
        linhas = [
            f"{resumo['totais']['total_ativo']} interferência(s) ativa(s), "
            f"{resumo['totais']['total_pendente']} pendente(s) de ação.",
            "",
            "Por severidade: " + ", ".join(f"{k}={v}" for k, v in resumo["totais"]["por_severidade"].items()),
            "Comparativo com a revisão anterior: " + ", ".join(
                f"{k}={v}" for k, v in resumo["comparativo_revisao_anterior"].items()
            ),
            "",
            "Matriz disciplina x disciplina:",
        ]
        for par, qtd in resumo["matriz_disciplinas"].items():
            linhas.append(f"  {par}: {qtd}")
        linhas.append("")
        linhas.append("Distribuição por pavimento:")
        for pav, qtd in resumo["distribuicao_por_pavimento"].items():
            linhas.append(f"  {pav}: {qtd}")
        linhas.append("")
        linhas.append("Pendências por disciplina responsável:")
        for disc, qtd in resumo["pendencias_por_disciplina"].items():
            linhas.append(f"  {disc}: {qtd}")

        pre = resumo["pre_checagens"]
        if pre.get("tem_alertas_bloqueantes"):
            linhas.insert(0, "⚠ ATENÇÃO: há alertas de qualidade que podem gerar interferências enganosas "
                             "(unidades/desalinhamento). Veja a aba Resultados após rodar novamente.")
            linhas.insert(1, "")

        self.txt_resumo.config(state=tk.NORMAL)
        self.txt_resumo.delete("1.0", tk.END)
        self.txt_resumo.insert(tk.END, "\n".join(linhas))
        self.txt_resumo.config(state=tk.DISABLED)

    # ---------- ações ----------
    def rodar_clash(self):
        if not self.arquivos_ifc:
            messagebox.showwarning(
                "Aviso", "Carregue ao menos um modelo IFC (aba 📚 Modelos) antes de rodar o clash.", parent=self
            )
            return
        if self.selecao_a.esta_vazia() or self.selecao_b.esta_vazia():
            messagebox.showwarning(
                "Aviso",
                "Marque pelo menos um arquivo/nível na Seleção A e outro na Seleção B "
                "(aba \"Seleção\") antes de rodar o clash.",
                parent=self,
            )
            return

        def progresso(total):
            self.lbl_progresso.config(text=f"Processando... {total} elementos")
            self.update_idletasks()

        self.lbl_progresso.config(text="Rodando clash...")
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            self.resultado_atual = rodar_clash(
                self.arquivos_ifc, self.regras, callback_progresso=progresso,
                selecao_a=self.selecao_a, selecao_b=self.selecao_b,
            )
        except Exception as e:
            messagebox.showerror("Erro ao rodar clash", f"Falha ao processar os modelos:\n{e}", parent=self)
            self.resultado_atual = None
            return
        finally:
            self.config(cursor="")

        n = len(self.resultado_atual["clashes"])
        t = self.resultado_atual["tempo_execucao_s"]
        self.lbl_progresso.config(text=f"{n} interferência(s) em {t:.1f}s")

        pavimentos = sorted({c.get("nivel") for c in self.resultado_atual["clashes"] if c.get("nivel")})
        self.cb_filtro_pavimento["values"] = [TODOS] + pavimentos

        self.atualizar_lista()
        self._atualizar_resumo()
        self._avisar_pre_checagens()

    def _avisar_pre_checagens(self):
        pre = self.resultado_atual["pre_checagens"]
        if not pre.tem_alertas_bloqueantes():
            return
        msgs = []
        if pre.unidades_inconsistentes:
            msgs.append(f"• Unidades de comprimento diferentes entre arquivos: {pre.escala_por_arquivo}")
        if pre.alerta_desalinhamento:
            msgs.append(f"• Possível desalinhamento entre modelos (distância entre centros: "
                        f"{pre.distancia_entre_centros_m:.1f} m)")
        messagebox.showwarning(
            "Atenção — qualidade dos modelos",
            "Foram encontrados problemas que podem gerar interferências enganosas:\n\n" + "\n".join(msgs) +
            "\n\nRevise os modelos antes de confiar cegamente nos resultados.",
            parent=self,
        )

    def _clashes_filtrados(self):
        if not self.resultado_atual:
            return []

        def valor_ou_none(combo):
            v = combo.get()
            return None if (not v or v == TODOS) else v

        return aplicar_filtros(
            self.resultado_atual["clashes"],
            disciplina=valor_ou_none(self.cb_filtro_disciplina),
            pavimento=valor_ou_none(self.cb_filtro_pavimento),
            severidade=valor_ou_none(self.cb_filtro_severidade),
            status=valor_ou_none(self.cb_filtro_status),
            responsavel=valor_ou_none(self.cb_filtro_responsavel),
        )

    def atualizar_lista(self):
        self.tree.delete(*self.tree.get_children())
        for clash in self._clashes_filtrados():
            self.tree.insert("", tk.END, iid=clash["id"], values=(
                clash["id"][:8], clash["severidade"], clash["tipo"],
                f"{clash['disciplina_a']} x {clash['disciplina_b']}",
                clash.get("nivel") or "—", clash["status"], clash.get("rastreamento", ""),
            ))

    def _ao_selecionar_na_lista(self, event=None):
        selecao = self.tree.selection()
        if not selecao:
            return
        clash_id = selecao[0]
        clash = self._encontrar_clash(clash_id)
        if not clash:
            return
        self.clash_atual_id = clash_id
        self._carregar_detalhe(clash)

    def _encontrar_clash(self, clash_id):
        if not self.resultado_atual:
            return None
        return next((c for c in self.resultado_atual["clashes"] if c["id"] == clash_id), None)

    def _carregar_detalhe(self, clash):
        self.lbl_detalhe_titulo.config(
            text=f"#{clash['id'][:8]} — {clash['severidade']} — {clash['tipo'].upper()} — "
                 f"{clash['disciplina_a']} x {clash['disciplina_b']}"
        )
        info = (
            f"Pavimento: {clash.get('nivel') or '—'}\n"
            f"Responsável sugerido: {clash['responsavel_sugerido']}\n"
            f"Elemento A: {clash['elemento_a']['ifc_class']} \"{clash['elemento_a']['nome']}\"\n"
            f"Elemento B: {clash['elemento_b']['ifc_class']} \"{clash['elemento_b']['nome']}\"\n"
        )
        if clash.get("penetracao_m") is not None:
            info += f"Penetração: {clash['penetracao_m']:.3f} m\n"
        if clash.get("volume_intersecao_m3") is not None:
            info += f"Volume de interseção: {clash['volume_intersecao_m3']:.4f} m³\n"
        if clash.get("distancia_m") is not None and clash.get("folga_exigida_m") is not None:
            info += f"Distância x folga exigida: {clash['distancia_m']:.3f} m x {clash['folga_exigida_m']:.3f} m\n"
        self.lbl_detalhe_info.config(text=info)

        self.cb_status.set(clash.get("status", "Novo"))
        self.cb_responsavel_atrib.set(clash.get("responsavel_atribuido", ""))
        self.ent_prazo.delete(0, tk.END)
        self.ent_prazo.insert(0, clash.get("prazo", ""))
        self.txt_comentario.delete("1.0", tk.END)
        self.txt_comentario.insert(tk.END, clash.get("comentario", ""))

        self.txt_historico.config(state=tk.NORMAL)
        self.txt_historico.delete("1.0", tk.END)
        for evento in clash.get("historico_status", []):
            self.txt_historico.insert(
                tk.END, f"[{evento.get('data', '')}] {evento.get('de') or '—'} → {evento.get('para')}\n"
            )
        self.txt_historico.config(state=tk.DISABLED)

    def salvar_detalhe(self):
        if not self.clash_atual_id or not self.resultado_atual:
            return
        clash = self._encontrar_clash(self.clash_atual_id)
        if not clash:
            return

        status_novo = self.cb_status.get()
        if status_novo != clash.get("status"):
            from utils import agora_str
            clash.setdefault("historico_status", []).append({
                "data": agora_str(), "de": clash.get("status"), "para": status_novo, "por": "usuário",
            })
        clash["status"] = status_novo
        clash["responsavel_atribuido"] = self.cb_responsavel_atrib.get()
        clash["prazo"] = self.ent_prazo.get()
        clash["comentario"] = self.txt_comentario.get("1.0", tk.END).strip()

        armazenamento.salvar_clashes(self.resultado_atual["clashes"])
        self.atualizar_lista()
        self._carregar_detalhe(clash)
        messagebox.showinfo("OK", "Alterações salvas.", parent=self)

    def focar_no_3d(self):
        """Destaca os dois elementos da interferência selecionada
        (vermelho/azul) e enquadra a câmera neles — já estamos dentro do
        visualizador IFC, então isso só atualiza a cena 3D ao lado, sem
        trocar de aba/tela."""
        if not self.clash_atual_id or not self.resultado_atual:
            messagebox.showwarning("Aviso", "Selecione uma interferência na lista primeiro.", parent=self)
            return
        clash = self._encontrar_clash(self.clash_atual_id)
        if not clash:
            return

        self.viewer.destacar_e_focar_elementos([
            (clash["elemento_a"], COR_CLASH_A01),
            (clash["elemento_b"], COR_CLASH_B01),
        ])

    def abrir_exportar(self):
        if not self.resultado_atual:
            messagebox.showwarning("Aviso", "Rode o clash antes de exportar.", parent=self)
            return
        self.dialogo_exportar = _DialogExportar(self.winfo_toplevel(), self)


class _DialogExportar(tk.Toplevel):
    FORMATOS = {
        "PDF": (".pdf", [("PDF", "*.pdf")]),
        "XLSX": (".xlsx", [("Excel", "*.xlsx")]),
        "BCF": (".bcfzip", [("BCF", "*.bcfzip")]),
        "JSON": (".json", [("JSON", "*.json")]),
    }

    def __init__(self, parent, painel):
        super().__init__(parent, bg=TEMA["surface"])
        self.painel = painel
        self.title("Exportar Relatório")
        self.geometry("360x340")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        tk.Label(self, text="Formato:", bg=TEMA["surface"], fg=TEMA["texto"]).pack(anchor="w", padx=15, pady=(15, 2))
        self.cb_formato = ttk.Combobox(self, values=list(self.FORMATOS), state="readonly", width=20)
        self.cb_formato.set("PDF")
        self.cb_formato.pack(anchor="w", padx=15)

        tk.Label(self, text="Filtros (opcionais):", bg=TEMA["surface"], fg=TEMA["texto"],
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        def combo(texto, valores):
            tk.Label(self, text=texto, bg=TEMA["surface"], fg=TEMA["texto"]).pack(anchor="w", padx=15)
            cb = ttk.Combobox(self, values=[TODOS] + valores, state="readonly", width=24)
            cb.set(TODOS)
            cb.pack(anchor="w", padx=15, pady=(0, 5))
            return cb

        self.cb_disciplina = combo("Disciplina:", list(painel.regras.disciplinas))
        self.cb_severidade = combo("Severidade:", SEVERIDADES)
        self.cb_status = combo("Status:", STATUS_CLASH)

        tk.Button(self, text="✔ Exportar", command=self.exportar, bg=TEMA["acento"], fg=TEMA["acento_texto"],
                  font=("Arial", 9, "bold")).pack(pady=15)

    def exportar(self):
        formato = self.cb_formato.get()
        extensao, tipos = self.FORMATOS[formato]

        def valor_ou_none(combo):
            v = combo.get()
            return None if (not v or v == TODOS) else v

        clashes = aplicar_filtros(
            self.painel.resultado_atual["clashes"],
            disciplina=valor_ou_none(self.cb_disciplina),
            severidade=valor_ou_none(self.cb_severidade),
            status=valor_ou_none(self.cb_status),
        )
        if not clashes:
            messagebox.showwarning("Aviso", "Nenhuma interferência corresponde a esses filtros.", parent=self)
            return

        caminho = filedialog.asksaveasfilename(defaultextension=extensao, filetypes=tipos, parent=self)
        if not caminho:
            return

        pre = self.painel.resultado_atual["pre_checagens"]
        escala_por_arquivo = pre.escala_por_arquivo
        arquivos_ifc = self.painel.arquivos_ifc

        try:
            if formato == "PDF":
                pdf_export.exportar_pdf(clashes, caminho, pre, arquivos_ifc=arquivos_ifc,
                                         escala_por_arquivo=escala_por_arquivo)
            elif formato == "XLSX":
                xlsx_export.exportar_xlsx(clashes, caminho, pre)
            elif formato == "BCF":
                bcf_export.exportar_bcf(clashes, caminho, arquivos_ifc=arquivos_ifc,
                                         escala_por_arquivo=escala_por_arquivo)
            elif formato == "JSON":
                json_export.exportar_json(clashes, caminho, pre)
        except Exception as e:
            messagebox.showerror("Erro ao exportar", f"Falha ao gerar o relatório:\n{e}", parent=self)
            return

        messagebox.showinfo("OK", f"Relatório exportado para:\n{caminho}", parent=self)
        self.destroy()
