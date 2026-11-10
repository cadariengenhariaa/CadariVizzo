"""Visualizador 3D de modelos IFC (ifcopenshell + VTK), com:
  - criação de issues vinculadas a elementos do modelo (clicar para marcar);
  - inspeção de propriedades e hierarquia espacial de um elemento;
  - modelo de coordenação (vários arquivos IFC federados na mesma cena);
  - caixa de corte (section box) por sliders, com contorno visível;
  - órbita travada ao eixo vertical do mundo (sem "tombamento" livre);
  - navegação em primeira pessoa (W/A/S/D + olhar com o mouse);
  - ferramentas de medição (régua, ângulo, laser) com ajuste ('snap') ao
    vértice de malha mais próximo do clique.

Notas de desempenho: em vez de criar um vtkActor/vtkPolyDataMapper por
elemento do IFC (o que gera milhares de chamadas de desenho e deixa a
navegação travada em modelos grandes), os elementos são agrupados por
(arquivo, cor de material) em um único vtkPolyData por grupo (via
vtkAppendPolyData). A seleção de um elemento individual e o destaque por
status são feitos através de um array de cor por célula, com um índice de
faixas (início/fim de células por elemento) para mapear o clique de volta ao
elemento certo — e ao arquivo certo, no caso de um modelo de coordenação.
"""
import bisect
import math
import multiprocessing
import os
import tkinter as tk
from collections import defaultdict
from tkinter import filedialog, messagebox, ttk

import numpy as np

from config import CORES_STATUS, LISTA_TIPOS_IFC, TEMA
from ui.atalhos import Dica, instalar_atalhos
from ui.componentes import Avatar, Botao, Cartao, Icone, Segmentado, espacar, fonte
from dialogs import DialogNovaIssue
from painel_issue import PainelIssue
from tela_clash import PainelClash
from utils import hex_to_rgb01

try:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element
    import ifcopenshell.util.unit
    IFCOPENSHELL_OK = True
except ImportError:
    IFCOPENSHELL_OK = False

try:
    import vtk
    try:
        from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy
    except ImportError:
        from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy
    VTK_OK = True
    # Por padrão, qualquer aviso interno do VTK (ex.: "Resetting view-up
    # since view plane normal is parallel", que aparece ao olhar quase
    # exatamente para cima/baixo) abre uma janela nativa "vtkOutputWindow"
    # separada, atrapalhando o app. Isso é só um aviso informativo — o VTK
    # já se autocorrige — então a exibição de avisos é desligada aqui.
    vtk.vtkObject.GlobalWarningDisplayOff()
except ImportError:
    VTK_OK = False

IFC_VIEWER_OK = IFCOPENSHELL_OK and VTK_OK

COR_PADRAO_ELEMENTO = (0.75, 0.75, 0.75)
EIXO_VERTICAL_MUNDO = (0.0, 0.0, 1.0)  # convenção Z-up do IFC

# Fundo do viewport 3D por modo dia/noite (ver _VTKTkCanvas/self.renderer).
COR_FUNDO_VIEWPORT_ESCURO = (0.063, 0.075, 0.094)  # quase preto, #101318
COR_FUNDO_VIEWPORT_CLARO = (0.80, 0.88, 0.95)  # azul claro, combina com a paleta clara da marca
COR_SELECAO = tuple(int(round(c * 255)) for c in hex_to_rgb01(TEMA["acento"]))  # destaque do elemento clicado

# Cores do destaque "Ver em 3D" de uma interferência (tela de Clash
# Detection) — mesmo tom de vermelho/azul usado no snapshot do relatório
# (clash/relatorio/snapshot_3d.py), só que em 0-255 (convenção de
# cor_base_por_id/COR_SELECAO) em vez de 0-1.
COR_CLASH_A = (240, 89, 89)
COR_CLASH_B = (84, 140, 242)


class _VTKTkCanvas(tk.Frame):
    """Embute uma vtkRenderWindow diretamente na janela nativa (HWND) de um
    Frame Tkinter via SetWindowInfo, em vez de usar o widget
    vtkTkRenderWindowInteractor (que carrega 'vtkRenderingTk.dll' por meio de
    uma extensão Tcl e costuma falhar com o wheel pip do VTK em instalações
    padrão do Python no Windows — o Tcl/Tk embutido no VTK não bate com o
    Tcl/Tk usado pelo tkinter). Os eventos de mouse são capturados pelo
    próprio Tkinter e repassados manualmente ao interactor do VTK.

    Eventos de arraste (botão pressionado + movimento) e a roda do mouse
    disparam um Render imediatamente. O simples "passar o mouse por cima"
    (sem nenhum botão pressionado) também é repassado ao interactor — é
    necessário para a pré-visualização ao vivo das ferramentas de medição —
    mas SEM forçar um Render a cada pixel: quem decide se algo realmente
    mudou (e portanto precisa redesenhar) é o estilo/viewer."""

    def __init__(self, parent, width=800, height=600):
        super().__init__(parent, width=width, height=height, bg="black")
        self.pack_propagate(False)
        self.update_idletasks()

        self.render_window = vtk.vtkRenderWindow()
        self.render_window.SetSize(width, height)
        self.render_window.SetWindowInfo(str(self.winfo_id()))

        self.interactor = vtk.vtkGenericRenderWindowInteractor()
        self.render_window.SetInteractor(self.interactor)
        self.interactor.Initialize()

        self.on_resize_extra = None  # callback opcional do viewer (ex.: re-sincronizar a caixa de corte)
        self.bind("<Configure>", self._on_resize)
        self.bind("<Motion>", self._despachar_hover)
        self.bind("<ButtonPress-1>", lambda e: self._despachar(e, "LeftButtonPressEvent"))
        self.bind("<ButtonRelease-1>", lambda e: self._despachar(e, "LeftButtonReleaseEvent"))
        self.bind("<B1-Motion>", lambda e: self._despachar(e, "MouseMoveEvent"))
        self.bind("<ButtonPress-2>", lambda e: self._despachar(e, "MiddleButtonPressEvent"))
        self.bind("<ButtonRelease-2>", lambda e: self._despachar(e, "MiddleButtonReleaseEvent"))
        self.bind("<B2-Motion>", lambda e: self._despachar(e, "MouseMoveEvent"))
        self.bind("<ButtonPress-3>", lambda e: self._despachar(e, "RightButtonPressEvent"))
        self.bind("<ButtonRelease-3>", lambda e: self._despachar(e, "RightButtonReleaseEvent"))
        self.bind("<B3-Motion>", lambda e: self._despachar(e, "MouseMoveEvent"))
        self.bind("<MouseWheel>", self._on_mouse_wheel)

    def _despachar(self, event, nome_evento):
        self.focus_set()
        self.interactor.SetEventInformationFlipY(event.x, event.y, 0, 0, chr(0), 0, None)
        getattr(self.interactor, nome_evento)()
        self.render_window.Render()

    def _despachar_hover(self, event):
        self.interactor.SetEventInformationFlipY(event.x, event.y, 0, 0, chr(0), 0, None)
        self.interactor.MouseMoveEvent()

    def _on_mouse_wheel(self, event):
        self.interactor.SetEventInformationFlipY(event.x, event.y, 0, 0, chr(0), 0, None)
        if event.delta > 0:
            self.interactor.MouseWheelForwardEvent()
        else:
            self.interactor.MouseWheelBackwardEvent()
        self.render_window.Render()

    def _on_resize(self, event):
        if event.width <= 1 or event.height <= 1:
            return
        self.render_window.SetSize(event.width, event.height)
        self.interactor.SetSize(event.width, event.height)
        self.interactor.ConfigureEvent()
        self.render_window.Render()
        if self.on_resize_extra:
            self.on_resize_extra()


def _girar_vetor(vetor, eixo, angulo_graus):
    transform = vtk.vtkTransform()
    transform.RotateWXYZ(angulo_graus, *eixo)
    return transform.TransformVector(vetor)


class _EstiloNavegacaoIFC(vtk.vtkInteractorStyleTrackballCamera if VTK_OK else object):
    """Estilo de interação com vários modos, trocados pelo viewer via
    `ferramenta_atual`:
      - 'orbit'        : órbita travada ao eixo vertical do mundo (gira
        lateralmente/frontalmente, sem tombar a câmera de lado).
      - 'pin'          : o clique esquerdo seleciona um elemento e dispara a
        criação de uma issue; os demais botões continuam orbitando/zoom.
      - 'inspecionar'  : o clique esquerdo seleciona um elemento e mostra
        propriedades/hierarquia na aba "Elemento", sem criar issue.
      - 'fps'          : arrastar com o botão esquerdo olha ao redor (like a
        fly-through); W/A/S/D/Q/E é tratado à parte, via bind de teclado.
      - 'medir_regua', 'medir_angulo', 'medir_laser': clicar marca pontos de
        medição (com ajuste ao vértice mais próximo); mover o mouse sem
        clicar mostra uma pré-visualização ao vivo.

    Registrar um observer para um evento de botão/mouse num
    vtkInteractorStyle substitui o comportamento padrão daquele evento (ele
    só volta a rodar se o próprio observer chamar `self.OnLeftButtonDown()`
    etc.), o que permite alternar entre os modos sem que a órbita padrão e a
    seleção/medição disparem ao mesmo tempo. O botão direito (zoom) e o
    botão do meio (pan) nunca são interceptados, então continuam funcionando
    normalmente em qualquer modo."""

    FERRAMENTAS_DE_CLIQUE = ("pin", "inspecionar", "medir_regua", "medir_angulo", "medir_laser")
    FERRAMENTAS_DE_ARRASTE = ("orbit", "fps")

    def __init__(self, viewer):
        super().__init__()
        self.viewer = viewer
        self._arrastando = False
        self._ultimo_xy = (0, 0)
        self.AddObserver("LeftButtonPressEvent", self._on_left_down)
        self.AddObserver("LeftButtonReleaseEvent", self._on_left_up)
        self.AddObserver("MouseMoveEvent", self._on_mouse_move)

    def _on_left_down(self, obj, event):
        x, y = self.GetInteractor().GetEventPosition()
        if self.viewer.caixa_corte_ativa and self.viewer.iniciar_arraste_handle(x, y):
            return

        modo = self.viewer.ferramenta_atual
        if modo in self.FERRAMENTAS_DE_CLIQUE:
            self._processar_clique(modo, x, y)
            return
        if modo in self.FERRAMENTAS_DE_ARRASTE:
            self._arrastando = True
            self._ultimo_xy = self.GetInteractor().GetEventPosition()
            self._pos_inicial_clique = self._ultimo_xy
            return
        self.OnLeftButtonDown()

    def _on_left_up(self, obj, event):
        if self.viewer._arrastando_handle is not None:
            self.viewer.finalizar_arraste_handle()
            return
        if self.viewer.ferramenta_atual in self.FERRAMENTAS_DE_ARRASTE:
            self._arrastando = False
            # Orbitar/FPS são ferramentas de arraste, mas um clique (sem
            # arrastar o mouse) sobre um pino de issue deve mostrá-la — sem
            # isso, só dá pra ver a issue trocando pra ferramenta 📍/🔍 antes.
            x, y = self.GetInteractor().GetEventPosition()
            xi, yi = getattr(self, "_pos_inicial_clique", (x, y))
            if abs(x - xi) <= 3 and abs(y - yi) <= 3:
                self._verificar_clique_em_pin(x, y)
            return
        self.OnLeftButtonUp()

    def _verificar_clique_em_pin(self, x, y):
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        picker.Pick(x, y, 0, self.viewer.renderer)
        actor = picker.GetActor()
        if actor is None:
            return
        issue_id = self.viewer.issue_id_por_pin_actor.get(actor)
        if issue_id is not None:
            self.viewer.on_pin_issue_clicado(issue_id)

    def _on_mouse_move(self, obj, event):
        if self.viewer._arrastando_handle is not None:
            x, y = self.GetInteractor().GetEventPosition()
            self.viewer.continuar_arraste_handle(x, y)
            return

        modo = self.viewer.ferramenta_atual
        if modo in self.FERRAMENTAS_DE_ARRASTE and self._arrastando:
            x, y = self.GetInteractor().GetEventPosition()
            ux, uy = self._ultimo_xy
            self._ultimo_xy = (x, y)
            if modo == "fps":
                self.viewer.olhar_ao_redor(x - ux, y - uy)
            else:
                self.viewer.orbitar_travado(x - ux, y - uy)
            return
        if modo in ("medir_regua", "medir_angulo", "medir_laser"):
            x, y = self.GetInteractor().GetEventPosition()
            self.viewer.atualizar_previa_medicao(x, y)
        self.OnMouseMove()

    def _processar_clique(self, modo, x, y):
        if modo == "pin":
            self._selecionar_elemento(x, y, self.viewer.on_elemento_selecionado)
        elif modo == "inspecionar":
            self._selecionar_elemento(x, y, self.viewer.on_elemento_inspecionado)
        else:
            self.viewer.on_clique_medicao(x, y)

    def _selecionar_elemento(self, x, y, callback):
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        picker.Pick(x, y, 0, self.viewer.renderer)
        actor = picker.GetActor()
        if actor is None:
            return
        issue_id = self.viewer.issue_id_por_pin_actor.get(actor)
        if issue_id is not None:
            self.viewer.on_pin_issue_clicado(issue_id)
            return
        callback(actor, picker.GetCellId(), picker.GetPickPosition())


class _PainelPropriedadesIFC(tk.Frame):
    """Mostra as propriedades (Property Sets) e a hierarquia espacial em
    cascata (Projeto > Obra > Edificação > Pavimento > ... > Elemento) do
    elemento selecionado com a ferramenta 'Inspecionar'."""

    def __init__(self, parent):
        super().__init__(parent, bg=TEMA["surface"])

        self.lbl_titulo = tk.Label(
            self, text="Selecione um elemento com a ferramenta 🔍 Inspecionar.",
            font=("Arial", 11, "bold"), bg=TEMA["surface"], fg=TEMA["texto"], wraplength=380, justify="left"
        )
        self.lbl_titulo.pack(anchor="w", padx=10, pady=(10, 5))

        tk.Label(self, text="Hierarquia (cascata):", font=("Arial", 10, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"]).pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        self.txt_cascata = tk.Text(self, height=7, font=("Consolas", 9), state=tk.DISABLED,
                                    bg=TEMA["surface_alt"], fg=TEMA["texto"], wrap=tk.NONE)
        self.txt_cascata.pack(fill=tk.X, padx=10, pady=2)

        tk.Label(self, text="Propriedades (Property Sets):", font=("Arial", 10, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"]).pack(
            anchor="w", padx=10, pady=(10, 2)
        )
        cont = tk.Frame(self, bg=TEMA["surface"])
        cont.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tree_props = ttk.Treeview(cont, columns=("valor",), show="tree headings")
        self.tree_props.heading("#0", text="Propriedade")
        self.tree_props.heading("valor", text="Valor")
        self.tree_props.column("#0", width=190)
        self.tree_props.column("valor", width=150)
        self.tree_props.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(cont, orient=tk.VERTICAL, command=self.tree_props.yview)
        self.tree_props.configure(yscroll=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def mostrar(self, elemento, cadeia):
        nome = getattr(elemento, "Name", None) or "Sem nome"
        global_id = getattr(elemento, "GlobalId", "—")
        self.lbl_titulo.config(text=f"{elemento.is_a()} — {nome}\nGlobalId: {global_id}")

        self.txt_cascata.config(state=tk.NORMAL)
        self.txt_cascata.delete("1.0", tk.END)
        for nivel, (classe, nome_item) in enumerate(cadeia):
            recuo = "  " * nivel
            marcador = "└─ " if nivel > 0 else ""
            self.txt_cascata.insert(tk.END, f"{recuo}{marcador}{classe}: {nome_item or '(sem nome)'}\n")
        self.txt_cascata.config(state=tk.DISABLED)

        for i in self.tree_props.get_children():
            self.tree_props.delete(i)

        try:
            psets = ifcopenshell.util.element.get_psets(elemento)
        except Exception:
            psets = {}

        if not psets:
            self.tree_props.insert("", tk.END, text="(sem property sets)", values=("",))
        for nome_pset, propriedades in psets.items():
            no_pset = self.tree_props.insert("", tk.END, text=nome_pset, values=("",), open=True)
            for chave, valor in propriedades.items():
                if chave == "id":
                    continue
                self.tree_props.insert(no_pset, tk.END, text=str(chave), values=(str(valor),))

    def limpar(self):
        self.lbl_titulo.config(text="Selecione um elemento com a ferramenta 🔍 Inspecionar.")
        self.txt_cascata.config(state=tk.NORMAL)
        self.txt_cascata.delete("1.0", tk.END)
        self.txt_cascata.config(state=tk.DISABLED)
        for i in self.tree_props.get_children():
            self.tree_props.delete(i)


class _PainelModelos(tk.Frame):
    """Lista os arquivos IFC carregados no modelo de coordenação, com
    visibilidade individual e opção de remover cada um."""

    def __init__(self, parent, viewer):
        super().__init__(parent, bg=TEMA["surface"])
        self.viewer = viewer

        tk.Label(self, text="Modelo de coordenação:", font=("Arial", 10, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"]).pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        self.lista_frame = tk.Frame(self, bg=TEMA["surface"])
        self.lista_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def atualizar(self):
        for w in self.lista_frame.winfo_children():
            w.destroy()

        if not self.viewer.info_arquivos:
            tk.Label(self.lista_frame, text="Nenhum modelo carregado.",
                     bg=TEMA["surface"], fg=TEMA["texto_fraco"]).pack(
                anchor="w", pady=10
            )
            return

        for caminho, info in self.viewer.info_arquivos.items():
            linha = tk.Frame(self.lista_frame, bg=TEMA["surface_alt"],
                              highlightbackground=TEMA["borda"], highlightthickness=1)
            linha.pack(fill=tk.X, pady=3)

            var = tk.BooleanVar(value=info["visivel"])
            tk.Checkbutton(
                linha, variable=var, bg=TEMA["surface_alt"], activebackground=TEMA["surface_alt"],
                command=lambda c=caminho, v=var: self.viewer.alternar_visibilidade_modelo(c, v.get())
            ).pack(side=tk.LEFT, padx=5)

            tk.Label(
                linha, text=f"{info['nome_exibicao']}\n{info['n_elementos']} elemento(s)",
                bg=TEMA["surface_alt"], fg=TEMA["texto"], justify="left", font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

            tk.Button(
                linha, text="✕", command=lambda c=caminho: self.viewer.remover_modelo(c),
                bg=TEMA["critico"], fg="white", width=3
            ).pack(side=tk.RIGHT, padx=5)


class _PainelNiveis(tk.Frame):
    """Lista os níveis (pavimentos/IfcBuildingStorey) encontrados nos
    modelos carregados, com uma caixa de seleção para mostrar/ocultar cada
    um — permite criar vistas rápidas por pavimento."""

    def __init__(self, parent, viewer):
        super().__init__(parent, bg=TEMA["surface"])
        self.viewer = viewer

        topo = tk.Frame(self, bg=TEMA["surface"])
        topo.pack(fill=tk.X, padx=10, pady=(10, 5))
        tk.Label(topo, text="Níveis / Pavimentos:", font=("Arial", 10, "bold"),
                 bg=TEMA["surface"], fg=TEMA["texto"]).pack(side=tk.LEFT)
        tk.Button(topo, text="Todos", command=lambda: self.viewer.definir_visibilidade_todos_niveis(True),
                  bg=TEMA["surface_alt"], fg=TEMA["texto"], font=("Arial", 8)).pack(side=tk.RIGHT, padx=2)
        tk.Button(topo, text="Nenhum", command=lambda: self.viewer.definir_visibilidade_todos_niveis(False),
                  bg=TEMA["surface_alt"], fg=TEMA["texto"], font=("Arial", 8)).pack(side=tk.RIGHT, padx=2)

        self.lista_frame = tk.Frame(self, bg=TEMA["surface"])
        self.lista_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    def atualizar(self):
        for w in self.lista_frame.winfo_children():
            w.destroy()

        if not self.viewer.niveis_info:
            tk.Label(self.lista_frame, text="Nenhum nível encontrado.",
                     bg=TEMA["surface"], fg=TEMA["texto_fraco"]).pack(
                anchor="w", pady=10
            )
            return

        niveis_ordenados = sorted(
            self.viewer.niveis_info.items(),
            key=lambda kv: (kv[1]["caminho"], kv[1]["elevacao"])
        )
        for nivel_key, info in niveis_ordenados:
            linha = tk.Frame(self.lista_frame, bg=TEMA["surface_alt"],
                              highlightbackground=TEMA["borda"], highlightthickness=1)
            linha.pack(fill=tk.X, pady=2)

            var = tk.BooleanVar(value=info["visivel"])
            tk.Checkbutton(
                linha, variable=var, bg=TEMA["surface_alt"], activebackground=TEMA["surface_alt"],
                command=lambda k=nivel_key, v=var: self.viewer.alternar_visibilidade_nivel(k, v.get())
            ).pack(side=tk.LEFT, padx=5)

            tk.Label(
                linha, text=f"{info['nome']}  (elev. {info['elevacao']:.2f})",
                bg=TEMA["surface_alt"], fg=TEMA["texto"], justify="left", font=("Arial", 9)
            ).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)


class _EventoPosicao:
    """Posição de tela de um widget no formato de um evento (x_root/y_root),
    para abrir menus ancorados nele."""

    def __init__(self, widget):
        self.x_root = widget.winfo_rootx() + widget.winfo_width()
        self.y_root = widget.winfo_rooty() + widget.winfo_height() // 2


class _SeletorAbas:
    """Compatibilidade com o antigo ttk.Notebook do painel lateral."""

    def __init__(self, viewer):
        self.viewer = viewer

    def select(self, frame):
        self.viewer.mostrar_aba(frame)


class IFCViewerFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self.painel = None
        self.painel_propriedades = None
        self.painel_modelos = None
        self.painel_niveis = None
        self.painel_clash = None

        self.ferramenta_atual = "orbit"
        self.elemento_selecionado_id = None
        self.elementos_destacados_clash = {}  # elem_index -> cor RGB (0-255) — ver destacar_e_focar_elementos
        self.pins_por_issue_id = {}  # issue_id -> vtkActor (alfinete/esfera colorido por status)
        self.issue_id_por_pin_actor = {}  # vtkActor -> issue_id (mapa inverso, usado ao clicar no pino)

        # Configurações ajustáveis na aba de engrenagem (⚙ Configurações).
        self.sensibilidade_mouse = 0.3
        self.velocidade_deslocamento = 1.0
        self.inverter_eixo_y = False  # "orientação da movimentação": olhar para cima/baixo invertido
        self._janela_controles = None
        self.caixa_corte_ativa = False
        self.corte_pct = {"x0": 0.0, "x1": 0.0, "y0": 0.0, "y1": 0.0, "z0": 0.0, "z1": 0.0}
        self._janela_config = None
        self.escalas_corte = {}
        self._bounds_originais = None

        # Manípulos (setas) arrastáveis da caixa de corte.
        self._handles_por_actor = {}
        self._arrastando_handle = None

        # Modelo de coordenação: vários arquivos IFC federados na mesma cena.
        self.arquivos_ifc = {}          # caminho -> ifcopenshell.file
        self.info_arquivos = {}         # caminho -> {"nome_exibicao", "visivel", "n_elementos"}
        self.escala_por_arquivo = {}    # caminho -> fator de conversão para metros
        self.niveis_info = {}           # (caminho, storey_guid|None) -> {"nome","visivel","elevacao","caminho"}

        # Estruturas de dados dos grupos de geometria. Um grupo é a chave
        # (caminho_do_arquivo, nivel_key, cor_do_material) — agrupar também
        # por arquivo e por nível (e não só por cor) permite mostrar/ocultar
        # ou remover um modelo inteiro, ou um pavimento inteiro, sem precisar
        # separar geometria misturada que por acaso compartilha a mesma cor.
        self.guid_por_id = []            # índice global do elemento -> GlobalId
        self.arquivo_por_id = []         # índice global do elemento -> caminho do arquivo de origem
        self.cor_base_por_id = []        # índice global do elemento -> cor RGB (0-255)
        self.grupo_por_actor = {}        # ator -> chave de grupo (caminho, nivel_key, cor_key)
        self.actor_por_grupo = {}        # chave de grupo -> ator
        self.mapper_por_grupo = {}       # chave de grupo -> vtkPolyDataMapper
        self.array_cor_por_grupo = {}    # chave de grupo -> numpy view (n_celulas, 3) editável
        self.faixas_por_grupo = {}       # chave de grupo -> ([inícios...], [índices de elemento...])

        # Ferramentas de medição.
        self._medicao_pontos = []
        self._medicao_escala_atual = 1.0
        self._marcadores_atuais = []
        self._preview_actors = []
        self._medicoes_finalizadas = []

        if not IFC_VIEWER_OK:
            self._montar_aviso_dependencias()
            return

        self._montar_toolbar()
        self._montar_canvas_3d()
        # atalhos de navegação (W/A/S/D/Q/E e setas ficam com a 1ª pessoa)
        instalar_atalhos(self, {
            "o": lambda: self.set_ferramenta("orbit"), "i": lambda: self.set_ferramenta("inspecionar"),
            "m": lambda: self.set_ferramenta("pin"), "f": lambda: self.set_ferramenta("fps"),
            "r": lambda: self.set_ferramenta("medir_regua"), "Escape": lambda: self.set_ferramenta("orbit"),
        })

    # ---------- UI quando dependências estão ausentes ----------
    def _montar_aviso_dependencias(self):
        toolbar = tk.Frame(self, bd=1, relief=tk.RAISED, bg=TEMA["surface"])
        toolbar.pack(side=tk.TOP, fill=tk.X)
        tk.Button(toolbar, text="⬅ Meus modelos", command=self.app.abrir_tela_projetos_ifc,
                  bg=TEMA["surface_alt"], fg=TEMA["texto"]).pack(side=tk.LEFT, padx=5, pady=5)

        faltando = []
        if not IFCOPENSHELL_OK:
            faltando.append("ifcopenshell")
        if not VTK_OK:
            faltando.append("vtk")
        tk.Label(
            self,
            text=(
                "Visualizador IFC indisponível.\n\n"
                f"Instale as dependências faltantes com:\n\npip install {' '.join(faltando)}"
            ),
            font=("Arial", 12), justify="center", fg="#B00020"
        ).pack(expand=True)

    # ---------- construção da UI (layout do protótipo) ----------
    # (chave, rótulo, ícone, atalho) — barra vertical de ferramentas à esquerda
    FERRAMENTAS_TRILHO = (
        ("orbit", "Orbitar", "", "O"),
        ("pin", "Marcar issue", "", "M"),
        ("inspecionar", "Inspecionar", "", "I"),
        ("fps", "1ª pessoa", "", "F"),
        None,
        ("medir_regua", "Régua", "", "R"),
        ("medir_angulo", "Ângulo", "", ""),
        ("medir_laser", "Laser", "", ""),
    )

    def _montar_toolbar(self):
        """Cabeçalho branco (marca, modelo, chip do projeto, Arquivo,
        Sincronizar, tema e usuário) + corpo com o trilho de ferramentas."""
        from ui.shell import imagem_marca

        bg = TEMA["card"]
        cab = tk.Frame(self, bg=bg, height=60)
        cab.pack(side=tk.TOP, fill=tk.X)
        cab.pack_propagate(False)
        tk.Frame(self, bg=TEMA["card_borda"], height=1).pack(side=tk.TOP, fill=tk.X)

        esquerda = tk.Frame(cab, bg=bg)
        esquerda.pack(side=tk.LEFT, fill=tk.Y, padx=(12, 0))
        Botao(esquerda, "", variante="fantasma", icone=Icone.VOLTAR, largura=32, altura=32,
              comando=self.app.abrir_tela_projetos_ifc).pack(side=tk.LEFT, pady=14)
        self._img_marca = imagem_marca(30, self)
        marca = tk.Label(esquerda, image=self._img_marca, bg=bg, cursor="hand2")
        marca.pack(side=tk.LEFT, padx=(8, 8))
        marca.bind("<Button-1>", lambda e: self.app.abrir_tela_projetos_ifc())
        tk.Label(esquerda, text="Cadari", bg=bg, fg=TEMA["titulo"], font=fonte(11, "semi")).pack(side=tk.LEFT)
        tk.Label(esquerda, text=" Vizzo", bg=bg, fg=TEMA["primario"] if not TEMA.esta_escuro() else TEMA["acento"],
                 font=fonte(11, "semi")).pack(side=tk.LEFT)
        tk.Frame(esquerda, bg=TEMA["card_borda"], width=1).pack(side=tk.LEFT, fill=tk.Y, padx=16, pady=14)
        textos = tk.Frame(esquerda, bg=bg)
        textos.pack(side=tk.LEFT, pady=10)
        linha = tk.Frame(textos, bg=bg)
        linha.pack(anchor="w")
        self.lbl_titulo_modelo = tk.Label(linha, text="Validação de modelo (IFC)", bg=bg, fg=TEMA["titulo"],
                                          font=fonte(10, "semi"))
        self.lbl_titulo_modelo.pack(side=tk.LEFT)
        self.lbl_ponto_salvo = tk.Label(linha, text="", bg=bg, fg=CORES_STATUS["Fechado"], font=fonte(8))
        self.lbl_ponto_salvo.pack(side=tk.LEFT, padx=(6, 0))
        self.lbl_modelo = tk.Label(textos, text="Nenhum modelo aberto", bg=bg, fg=TEMA["texto_fraco"],
                                   font=fonte(8))
        self.lbl_modelo.pack(anchor="w")
        self.btn_projeto = Botao(esquerda, self._texto_chip_projeto(), variante="fantasma",
                                 icone_direita=Icone.CHEVRON_BAIXO, altura=30, tamanho_fonte=9, negrito=False,
                                 comando=self._editar_sessao)
        self.btn_projeto.pack(side=tk.LEFT, padx=(16, 0))

        direita = tk.Frame(cab, bg=bg)
        direita.pack(side=tk.RIGHT, padx=(0, 14))
        nome = (self.app.usuario_atual or {}).get("nome", "")
        Avatar(direita, nome, tamanho=34, tamanho_fonte=8).pack(side=tk.RIGHT, padx=(10, 0))
        Botao(direita, "Sincronizar", variante="primario", icone=Icone.ATUALIZAR, altura=34, tamanho_fonte=9,
              comando=self.app.sincronizar_banco).pack(side=tk.RIGHT, padx=(8, 0))
        self.btn_arquivo = Botao(direita, "Arquivo", variante="secundario", icone=Icone.PASTA,
                                 icone_direita=Icone.CHEVRON_BAIXO, altura=34, tamanho_fonte=9, negrito=False,
                                 comando=self._menu_arquivo)
        self.btn_arquivo.pack(side=tk.RIGHT, padx=(8, 0))
        glifo = Icone.SOL if TEMA.esta_escuro() else Icone.OLHO if TEMA.eh_daltonico() else Icone.LUA
        tema = Botao(direita, "", variante="fantasma", icone=glifo, largura=34, altura=34)
        tema.comando = lambda: self.app.abrir_menu_tema(_EventoPosicao(tema))
        tema.pack(side=tk.RIGHT)

        # corpo: trilho de ferramentas | trilho de modelos/níveis | viewport | painel lateral
        self.corpo_ifc = tk.Frame(self, bg=TEMA["pagina"])
        self.corpo_ifc.pack(fill=tk.BOTH, expand=True)
        trilho = tk.Frame(self.corpo_ifc, bg=bg, width=56)
        trilho.pack(side=tk.LEFT, fill=tk.Y)
        tk.Frame(self.corpo_ifc, bg=TEMA["card_borda"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        self.botoes_ferramenta = {}
        tk.Frame(trilho, bg=bg, height=8).pack()
        for item in self.FERRAMENTAS_TRILHO:
            if item is None:
                tk.Frame(trilho, bg=TEMA["linha"], height=1, width=30).pack(pady=8)
                continue
            chave, texto, glifo, tecla = item
            b = Botao(trilho, "", variante="fantasma", icone=glifo, largura=40, altura=40, raio=10,
                      tamanho_fonte=13, comando=lambda k=chave: self.set_ferramenta(k))
            b.pack(pady=3, padx=8)
            Dica(b, f"{texto}  ·  atalho {tecla}" if tecla else texto)
            self.botoes_ferramenta[chave] = b
        tk.Frame(trilho, bg=TEMA["linha"], height=1, width=30).pack(pady=8)
        limpar = Botao(trilho, "", variante="fantasma", icone=Icone.LIXEIRA, largura=40, altura=40, raio=10,
                       tamanho_fonte=12, comando=self.limpar_medicoes)
        limpar.pack(pady=3)
        Dica(limpar, "Limpar medições")
        config = Botao(trilho, "", variante="fantasma", icone="", largura=40, altura=40, raio=10,
                       tamanho_fonte=12, comando=self._abrir_configuracoes)
        config.pack(side=tk.BOTTOM, pady=10)
        Dica(config, "Configurações do visualizador")
        self.botoes_ferramenta["orbit"].definir_variante("ativo")

    def _texto_chip_projeto(self):
        sessao = self.app.sessao
        partes = [p for p in (sessao.get("obra"), sessao.get("disciplina")) if p]
        return " · ".join(partes) if partes else "Definir projeto"

    def _editar_sessao(self):
        self.app.abrir_dialogo_sessao()
        self.ao_mudar_sessao()

    def ao_mudar_sessao(self):
        if hasattr(self, "btn_projeto"):
            self.btn_projeto.config_texto(self._texto_chip_projeto())

    def _menu_arquivo(self):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        menu.add_command(label="Abrir modelo IFC…", command=self.abrir_ifc)
        menu.add_command(label="Adicionar modelo (coordenação)…", command=self.adicionar_ifc)
        menu.add_separator()
        menu.add_command(label="Configurações do visualizador…", command=self._abrir_configuracoes)
        menu.add_command(label="Projeto / disciplina da verificação…", command=self._editar_sessao)
        menu.add_separator()
        menu.add_command(label="Voltar para Meus modelos", command=self.app.abrir_tela_projetos_ifc)
        b = self.btn_arquivo
        menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 4)

    def _montar_trilho_modelos(self):
        """Trilho estreito "MODELOS · NÍVEIS" (como "PÁGINAS" no protótipo):
        » abre o painel com as duas listas, « recolhe."""
        bg = TEMA["card"]
        self.trilho_modelos = tk.Frame(self.corpo_ifc, bg=bg, width=34)
        self.trilho_modelos.pack(side=tk.LEFT, fill=tk.Y)
        self.trilho_modelos.pack_propagate(False)
        abrir = Botao(self.trilho_modelos, "", variante="fantasma", icone=Icone.CHEVRON_DIREITA, largura=26,
                      altura=26, tamanho_fonte=8, comando=self._alternar_painel_modelos)
        abrir.pack(pady=(10, 6))
        rotulo_vertical = tk.Canvas(self.trilho_modelos, width=20, height=150, bg=bg, highlightthickness=0)
        rotulo_vertical.create_text(10, 75, text=espacar("Modelos · Níveis"), angle=90, fill=TEMA["eyebrow"],
                                    font=fonte(7, "semi"))
        rotulo_vertical.pack()
        rotulo_vertical.bind("<Button-1>", lambda e: self._alternar_painel_modelos())
        self.lbl_qtd_modelos = tk.Label(self.trilho_modelos, text="0", bg=bg, fg=TEMA["primario"],
                                        font=fonte(8, "semi"))
        self.lbl_qtd_modelos.pack(pady=(6, 0))
        tk.Frame(self.corpo_ifc, bg=TEMA["card_borda"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        self.painel_esquerdo = tk.Frame(self.corpo_ifc, bg=bg, width=300)
        self.painel_esquerdo.pack_propagate(False)
        topo = tk.Frame(self.painel_esquerdo, bg=bg)
        topo.pack(fill=tk.X, padx=10, pady=8)
        self._abas_esquerda = Segmentado(topo, ["Modelos", "Níveis"], valor="Modelos", agrupado=True,
                                         comando=self._trocar_aba_esquerda)
        self._abas_esquerda.pack(side=tk.LEFT)
        Botao(topo, "", variante="fantasma", icone=Icone.CHEVRON_ESQUERDA, largura=26, altura=26, tamanho_fonte=8,
              comando=self._alternar_painel_modelos).pack(side=tk.RIGHT)
        self.frame_modelos = tk.Frame(self.painel_esquerdo, bg=bg)
        self.frame_niveis = tk.Frame(self.painel_esquerdo, bg=bg)
        self.frame_modelos.pack(fill=tk.BOTH, expand=True)
        self._painel_modelos_aberto = False

    def _trocar_aba_esquerda(self, aba):
        self.frame_modelos.pack_forget()
        self.frame_niveis.pack_forget()
        (self.frame_modelos if aba == "Modelos" else self.frame_niveis).pack(fill=tk.BOTH, expand=True)

    def _alternar_painel_modelos(self):
        self._painel_modelos_aberto = not self._painel_modelos_aberto
        if self._painel_modelos_aberto:
            self.painel_esquerdo.pack(side=tk.LEFT, fill=tk.Y, after=self.trilho_modelos)
        else:
            self.painel_esquerdo.pack_forget()

    def _montar_barra_vistas(self, centro):
        """Barra inferior centralizada (como a de páginas/zoom do protótipo):
        vistas predefinidas, ajustar, projeção e caixa de corte."""
        faixa = tk.Frame(centro, bg=TEMA["pagina"])
        faixa.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_dica = tk.Label(faixa, text="Arraste para girar • Roda do mouse para zoom", bg=TEMA["pagina"],
                                 fg=TEMA["texto_fraco"], font=fonte(8))
        self.lbl_dica.pack(side=tk.LEFT, padx=16)
        cartao = Cartao(faixa, padding=(8, 6), raio=12)
        cartao.pack(pady=10)
        c = cartao.corpo
        for texto, nome in (("Superior", "superior"), ("Frontal", "frontal"), ("Lateral", "lateral"),
                            ("Isométrica", "isometrica")):
            Botao(c, texto, variante="fantasma", altura=30, tamanho_fonte=9, negrito=False,
                  comando=lambda n=nome: self._vista_predefinida(n)).pack(side=tk.LEFT, padx=1)
        tk.Frame(c, bg=TEMA["card_borda"], width=1, height=20).pack(side=tk.LEFT, padx=6)
        ajustar = Botao(c, "", variante="fantasma", icone="", largura=30, altura=30,
                        comando=self._resetar_camera)
        ajustar.pack(side=tk.LEFT, padx=1)
        Dica(ajustar, "Ajustar à tela")
        self.btn_projecao = Botao(c, "Perspectiva", variante="fantasma", icone="", altura=30, tamanho_fonte=9,
                                  negrito=False, largura=120, comando=self._alternar_projecao)
        self.btn_projecao.pack(side=tk.LEFT, padx=1)
        self.btn_caixa_corte = Botao(c, "Caixa de corte", variante="fantasma", icone="", altura=30,
                                     tamanho_fonte=9, negrito=False, comando=self._alternar_caixa_corte)
        self.btn_caixa_corte.pack(side=tk.LEFT, padx=1)

    def _montar_painel_lateral(self):
        """Painel direito: abas Issues · Elemento · Clash (pílulas no topo,
        como "Issues | Marcações" no protótipo), + nova issue e recolher."""
        bg = TEMA["card"]
        self.painel_direito = tk.Frame(self.corpo_ifc, bg=bg, width=430)
        self.painel_direito.pack(side=tk.RIGHT, fill=tk.Y)
        self.painel_direito.pack_propagate(False)
        tk.Frame(self.corpo_ifc, bg=TEMA["card_borda"], width=1).pack(side=tk.RIGHT, fill=tk.Y)

        topo = tk.Frame(self.painel_direito, bg=bg)
        topo.pack(fill=tk.X, padx=12, pady=10)
        self._aba_direita = Segmentado(topo, ["Issues", "Elemento", "Clash"], valor="Issues", agrupado=True,
                                       comando=self._trocar_aba_direita)
        self._aba_direita.pack(side=tk.LEFT)
        nova = Botao(topo, "", variante="fantasma", icone=Icone.MAIS, largura=30, altura=30,
                     comando=lambda: self.set_ferramenta("pin"))
        nova.pack(side=tk.RIGHT)
        Dica(nova, "Nova issue: clique num elemento do modelo")
        tk.Frame(self.painel_direito, bg=TEMA["linha"], height=1).pack(fill=tk.X)

        self.tab_issues = tk.Frame(self.painel_direito, bg=bg)
        self.tab_propriedades = tk.Frame(self.painel_direito, bg=bg)
        self.tab_clash = tk.Frame(self.painel_direito, bg=bg)
        self._abas_direita = {"Issues": self.tab_issues, "Elemento": self.tab_propriedades, "Clash": self.tab_clash}
        self.tab_issues.pack(fill=tk.BOTH, expand=True)
        self.notebook_lateral = _SeletorAbas(self)

    def _trocar_aba_direita(self, aba):
        for nome, frame in self._abas_direita.items():
            frame.pack_forget()
        self._abas_direita[aba].pack(fill=tk.BOTH, expand=True)

    def mostrar_aba(self, frame):
        for nome, f in self._abas_direita.items():
            if f is frame:
                self._aba_direita.selecionar(nome, disparar=False)
                self._trocar_aba_direita(nome)

    def _montar_canvas_3d(self):
        self._montar_painel_lateral()
        self._montar_trilho_modelos()
        canvas_container = tk.Frame(self.corpo_ifc, bg=TEMA["pagina"])
        canvas_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._montar_barra_vistas(canvas_container)

        self.vtk_canvas = _VTKTkCanvas(canvas_container, width=800, height=600)
        self.vtk_canvas.pack(fill=tk.BOTH, expand=True)
        self.vtk_canvas.on_resize_extra = self._ao_redimensionar_viewport

        self.renderer = vtk.vtkRenderer()
        # Fundo do viewport 3D acompanha o modo dia/noite: azul claro de
        # dia (combina com a paleta clara da marca), preto à noite — não
        # é recalculado em tempo real porque a tela inteira é reconstruída
        # ao trocar de tema (ver AppCDE._reabrir_tela_atual).
        cor_fundo = COR_FUNDO_VIEWPORT_CLARO if not TEMA.esta_escuro() else COR_FUNDO_VIEWPORT_ESCURO
        self.renderer.SetBackground(*cor_fundo)
        self.vtk_canvas.render_window.AddRenderer(self.renderer)

        self.interactor = self.vtk_canvas.interactor
        self.estilo = _EstiloNavegacaoIFC(self)
        self.interactor.SetInteractorStyle(self.estilo)

        # Contorno visível da caixa de corte (some quando ela está desativada).
        self.outline_source = vtk.vtkOutlineSource()
        outline_mapper = vtk.vtkPolyDataMapper()
        outline_mapper.SetInputConnection(self.outline_source.GetOutputPort())
        self.actor_caixa_corte = vtk.vtkActor()
        self.actor_caixa_corte.SetMapper(outline_mapper)
        self.actor_caixa_corte.GetProperty().SetColor(1.0, 0.6, 0.0)
        self.actor_caixa_corte.GetProperty().SetLineWidth(2)
        self.actor_caixa_corte.VisibilityOff()
        self.actor_caixa_corte.PickableOff()
        self.renderer.AddActor(self.actor_caixa_corte)

        # Manípulos (setas) arrastáveis em cada face da caixa de corte —
        # aparecem só quando ela está ativa, para "empurrar" cada lado.
        especificacao_handles = (
            ("x0", (1.0, 0.0, 0.0)), ("x1", (-1.0, 0.0, 0.0)),
            ("y0", (0.0, 1.0, 0.0)), ("y1", (0.0, -1.0, 0.0)),
            ("z0", (0.0, 0.0, 1.0)), ("z1", (0.0, 0.0, -1.0)),
        )
        self.handles_caixa_corte = {}
        self._direcao_por_handle = {}
        for chave, direcao_para_dentro in especificacao_handles:
            cone = vtk.vtkConeSource()
            cone.SetDirection(*direcao_para_dentro)
            cone.SetResolution(16)
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(cone.GetOutputPort())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetColor(0.0, 0.9, 1.0)
            actor.GetProperty().SetLighting(False)  # cor solida e visivel mesmo "dentro" de sombra
            actor.VisibilityOff()
            self.renderer.AddActor(actor)
            self.handles_caixa_corte[chave] = (cone, actor)
            self._handles_por_actor[actor] = (chave, direcao_para_dentro)
            self._direcao_por_handle[chave] = direcao_para_dentro

        # Reajusta o tamanho dos manípulos a cada render (barato: só 6 cones,
        # sem tocar em geometria do modelo) para que fiquem sempre com um
        # tamanho aparente parecido na tela, mesmo dando zoom depois de
        # ativar a caixa de corte — sem isso, o manípulo (calculado só uma
        # vez, na ativação) ficava enorme ao aproximar a câmera depois.
        self.vtk_canvas.render_window.AddObserver("StartEvent", self._sincronizar_handles_com_camera)

        # Movimento em primeira pessoa (só tem efeito quando ferramenta_atual == "fps").
        # W/A/S/D e as setas do teclado fazem a mesma coisa — o usuário pode
        # usar o que preferir, sem precisar escolher um esquema.
        for tecla, direcao in (
            ("w", (1, 0, 0)), ("s", (-1, 0, 0)),
            ("a", (0, -1, 0)), ("d", (0, 1, 0)),
            ("e", (0, 0, 1)), ("q", (0, 0, -1)),
            ("Up", (1, 0, 0)), ("Down", (-1, 0, 0)),
            ("Left", (0, -1, 0)), ("Right", (0, 1, 0)),
        ):
            self.vtk_canvas.bind(f"<KeyPress-{tecla}>", lambda ev, d=direcao: self._mover_fps(*d))

        self.painel = PainelIssue(
            self.tab_issues, self.app, tipos_disponiveis=LISTA_TIPOS_IFC,
            on_issue_alterada=self.atualizar_visual_issues,
            on_issue_selecionada=self._ao_selecionar_issue,
        )
        self.painel.pack(fill=tk.BOTH, expand=True)
        self.painel.definir_filtro(
            lambda issues: [
                i for i in issues
                if i.get("tipo_doc") == "ifc" and i.get("filepath") in self.arquivos_ifc
            ]
        )

        self.painel_propriedades = _PainelPropriedadesIFC(self.tab_propriedades)
        self.painel_propriedades.pack(fill=tk.BOTH, expand=True)

        self.painel_modelos = _PainelModelos(self.frame_modelos, self)
        self.painel_modelos.pack(fill=tk.BOTH, expand=True)
        self.painel_modelos.atualizar()

        self.painel_niveis = _PainelNiveis(self.frame_niveis, self)
        self.painel_niveis.pack(fill=tk.BOTH, expand=True)
        self.painel_niveis.atualizar()

        self.painel_clash = PainelClash(self.tab_clash, self)
        self.painel_clash.pack(fill=tk.BOTH, expand=True)

    def _atualizar_titulo_modelo(self, titulo, quantidade):
        self.lbl_titulo_modelo.config(text=titulo or "Validação de modelo (IFC)")
        self.lbl_ponto_salvo.config(text="●" if titulo else "")
        if hasattr(self, "lbl_qtd_modelos"):
            self.lbl_qtd_modelos.config(text=str(quantidade))

    # ---------- ferramentas ----------
    def set_ferramenta(self, nome):
        if self.ferramenta_atual in ("medir_regua", "medir_angulo", "medir_laser") and nome != self.ferramenta_atual:
            self._cancelar_medicao_em_andamento()

        self.ferramenta_atual = nome
        for chave, b in self.botoes_ferramenta.items():
            b.definir_variante("ativo" if chave == nome else "fantasma")

        dicas = {
            "orbit": "Arraste para girar (eixo travado) • Roda do mouse para zoom",
            "pin": "Clique num elemento do modelo para criar uma issue nele",
            "inspecionar": "Clique num elemento para ver propriedades e hierarquia na aba 'Elemento'",
            "fps": "W/A/S/D anda • Q/E desce/sobe • Arraste com o botão esquerdo para olhar ao redor",
            "medir_regua": "Clique em 2 pontos para medir a distância entre eles",
            "medir_angulo": "Clique em 3 pontos (ponta, vértice, ponta) para medir o ângulo",
            "medir_laser": "Clique para fixar a referência e mova o mouse para ler a distância ao vivo",
        }
        self.lbl_dica.config(text=dicas.get(nome, ""))
        if nome == "fps":
            self.vtk_canvas.focus_set()

    # ---------- carregamento do modelo (coordenação de múltiplos IFC) ----------
    def abrir_ifc(self, initialdir=None):
        filepath = filedialog.askopenfilename(filetypes=[("Modelos IFC", "*.ifc"), ("Todos os arquivos", "*.*")],
                                              initialdir=initialdir)
        if not filepath:
            return
        self._carregar_ifc(filepath, limpar_existente=True)

    def adicionar_ifc(self):
        filepath = filedialog.askopenfilename(filetypes=[("Modelos IFC", "*.ifc"), ("Todos os arquivos", "*.*")])
        if not filepath:
            return
        self._carregar_ifc(filepath, limpar_existente=False)

    def _carregar_ifc(self, filepath, limpar_existente):
        self.config(cursor="watch")
        self.lbl_modelo.config(text="Carregando modelo, aguarde...")
        self.update_idletasks()
        try:
            self._carregar_ifc_impl(filepath, limpar_existente)
        except Exception as e:
            messagebox.showerror("Erro ao abrir IFC", f"Falha ao carregar o modelo:\n{e}")
        finally:
            self.config(cursor="")

    def _carregar_ifc_impl(self, filepath, limpar_existente):
        if filepath in self.arquivos_ifc:
            self.remover_modelo(filepath)

        estava_com_corte_ativo = self.caixa_corte_ativa

        if limpar_existente:
            for caminho in list(self.arquivos_ifc.keys()):
                self.remover_modelo(caminho, redesenhar=False)
            self.limpar_medicoes()
            self.elemento_selecionado_id = None
            if self.painel_propriedades:
                self.painel_propriedades.limpar()

        ifc_file = ifcopenshell.open(filepath)
        try:
            escala = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
        except Exception:
            escala = 1.0

        self.arquivos_ifc[filepath] = ifc_file
        self.escala_por_arquivo[filepath] = escala
        self.info_arquivos[filepath] = {
            "nome_exibicao": filepath.replace("/", "\\").split("\\")[-1],
            "visivel": True,
            "n_elementos": 0,
        }

        dados_por_grupo = {}
        contagem_celulas = defaultdict(int)
        faixas_tmp = defaultdict(list)

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        n_threads = max(1, multiprocessing.cpu_count() - 1)
        iterator = ifcopenshell.geom.iterator(settings, ifc_file, n_threads)
        total = 0
        if iterator.initialize():
            while True:
                shape = iterator.get()
                self._processar_shape(shape, filepath, ifc_file, dados_por_grupo, contagem_celulas, faixas_tmp)
                total += 1
                if total % 200 == 0:
                    self.lbl_modelo.config(text=f"Carregando geometria... {total} elementos processados")
                    self.update_idletasks()
                if not iterator.next():
                    break

        self.lbl_modelo.config(text=f"Montando {len(dados_por_grupo)} grupo(s) de geometria...")
        self.update_idletasks()

        for grupo_key, dados in dados_por_grupo.items():
            self._finalizar_grupo(grupo_key, dados, faixas_tmp[grupo_key])

        self.info_arquivos[filepath]["n_elementos"] = total

        self.renderer.ResetCamera()
        self.atualizar_destaques()
        self.atualizar_pins_issues()
        if estava_com_corte_ativo:
            self._capturar_bounds_originais()
            self._aplicar_caixa_corte()
        self.vtk_canvas.render_window.Render()

        self._atualizar_label_modelos()
        if self.painel:
            self.painel.atualizar_lista()
        if self.painel_modelos:
            self.painel_modelos.atualizar()
        if self.painel_niveis:
            self.painel_niveis.atualizar()
        if self.painel_clash:
            self.painel_clash.atualizar_arvore_selecao()

    def _atualizar_label_modelos(self):
        n_arquivos = len(self.info_arquivos)
        n_elementos = sum(info["n_elementos"] for info in self.info_arquivos.values())
        if n_arquivos == 0:
            self.lbl_modelo.config(text="Nenhum modelo aberto")
            self._atualizar_titulo_modelo(None, 0)
        elif n_arquivos == 1:
            nome = next(iter(self.info_arquivos.values()))["nome_exibicao"]
            self.lbl_modelo.config(text=f"{n_elementos} elementos · salvo automaticamente na rede")
            self._atualizar_titulo_modelo(nome, 1)
        else:
            self.lbl_modelo.config(text=f"{n_arquivos} modelos coordenados · {n_elementos} elementos")
            self._atualizar_titulo_modelo(f"{n_arquivos} modelos coordenados", n_arquivos)

    def remover_modelo(self, caminho, redesenhar=True):
        if caminho not in self.arquivos_ifc:
            return
        grupos_do_arquivo = [g for g in list(self.mapper_por_grupo.keys()) if g[0] == caminho]
        for grupo_key in grupos_do_arquivo:
            actor = self.actor_por_grupo.pop(grupo_key, None)
            if actor is not None:
                self.renderer.RemoveActor(actor)
                self.grupo_por_actor.pop(actor, None)
            self.mapper_por_grupo.pop(grupo_key, None)
            self.array_cor_por_grupo.pop(grupo_key, None)
            self.faixas_por_grupo.pop(grupo_key, None)

        self.arquivos_ifc.pop(caminho, None)
        self.escala_por_arquivo.pop(caminho, None)
        self.info_arquivos.pop(caminho, None)
        for chave in [k for k in self.niveis_info if k[0] == caminho]:
            self.niveis_info.pop(chave, None)

        if redesenhar:
            self.atualizar_destaques()
            self.atualizar_pins_issues()
            self._atualizar_label_modelos()
            if self.painel:
                self.painel.atualizar_lista()
            if self.painel_modelos:
                self.painel_modelos.atualizar()
            if self.painel_niveis:
                self.painel_niveis.atualizar()
            if self.painel_clash:
                self.painel_clash.atualizar_arvore_selecao()
            self.vtk_canvas.render_window.Render()

    def alternar_visibilidade_modelo(self, caminho, visivel):
        if caminho not in self.info_arquivos:
            return
        self.info_arquivos[caminho]["visivel"] = visivel
        self._atualizar_visibilidade_atores()

    def alternar_visibilidade_nivel(self, nivel_key, visivel):
        if nivel_key not in self.niveis_info:
            return
        self.niveis_info[nivel_key]["visivel"] = visivel
        self._atualizar_visibilidade_atores()

    def definir_visibilidade_todos_niveis(self, visivel):
        for info in self.niveis_info.values():
            info["visivel"] = visivel
        self._atualizar_visibilidade_atores()
        if self.painel_niveis:
            self.painel_niveis.atualizar()

    def _atualizar_visibilidade_atores(self):
        for grupo_key, actor in self.actor_por_grupo.items():
            caminho, nivel_key, _ = grupo_key
            visivel_arquivo = self.info_arquivos.get(caminho, {}).get("visivel", True)
            visivel_nivel = self.niveis_info.get(nivel_key, {}).get("visivel", True)
            actor.SetVisibility(visivel_arquivo and visivel_nivel)
        self.vtk_canvas.render_window.Render()

    def _nivel_do_elemento(self, elemento, caminho):
        """Determina o nível (IfcBuildingStorey) do elemento via
        ifcopenshell.util.element.get_container, e registra suas
        informações em self.niveis_info na primeira vez que aparece."""
        try:
            container = ifcopenshell.util.element.get_container(elemento)
        except Exception:
            container = None

        if container is not None and container.is_a("IfcBuildingStorey"):
            nivel_key = (caminho, container.GlobalId)
            nome = container.Name or container.GlobalId
            try:
                elevacao = float(container.Elevation) if container.Elevation is not None else 0.0
            except Exception:
                elevacao = 0.0
        else:
            nivel_key = (caminho, None)
            nome = "Sem nível"
            elevacao = 0.0

        if nivel_key not in self.niveis_info:
            self.niveis_info[nivel_key] = {
                "nome": nome, "visivel": True, "elevacao": elevacao, "caminho": caminho,
            }
        return nivel_key

    def _processar_shape(self, shape, caminho, ifc_file, dados_por_grupo, contagem_celulas, faixas_tmp):
        """Acumula os vértices/faces do elemento em arrays numpy por grupo,
        em vez de montar um vtkPolyData (vtkPoints + vtkCellArray) por
        ELEMENTO e uni-los com vtkAppendPolyData. Criar objetos VTK um a um
        tem um custo fixo por chamada que, multiplicado por milhares de
        elementos, dominava o tempo de abertura de modelos grandes — medido
        e confirmado com profiling antes desta mudança. Só é criado UM
        vtkPolyData por grupo (arquivo, nível, cor), em `_finalizar_grupo`,
        a partir dos arrays já concatenados."""
        geometry = shape.geometry
        verts = np.asarray(geometry.verts, dtype=np.float64)
        faces = np.asarray(geometry.faces, dtype=np.int64)
        n_tri = faces.size // 3
        if n_tri == 0 or verts.size == 0:
            return

        elemento = ifc_file.by_guid(shape.guid)
        nivel_key = self._nivel_do_elemento(elemento, caminho)

        cor = self._cor_por_material(shape)
        cor_key = tuple(round(c, 2) for c in cor)
        grupo_key = (caminho, nivel_key, cor_key)

        elem_index = len(self.guid_por_id)
        self.guid_por_id.append(shape.guid)
        self.arquivo_por_id.append(caminho)
        self.cor_base_por_id.append(tuple(int(round(c * 255)) for c in cor))

        inicio = contagem_celulas[grupo_key]
        faixas_tmp[grupo_key].append((inicio, elem_index))
        contagem_celulas[grupo_key] += n_tri

        if grupo_key not in dados_por_grupo:
            dados_por_grupo[grupo_key] = {"verts": [], "faces": [], "offset": 0}
        dados = dados_por_grupo[grupo_key]

        dados["verts"].append(verts)
        dados["faces"].append(faces.reshape(-1, 3) + dados["offset"])
        dados["offset"] += verts.size // 3

    def _finalizar_grupo(self, grupo_key, dados, faixas):
        verts_concat = np.concatenate(dados["verts"]).reshape(-1, 3)
        faces_concat = np.concatenate(dados["faces"])
        n_tri = faces_concat.shape[0]

        points = vtk.vtkPoints()
        points.SetData(numpy_to_vtk(verts_concat, deep=True))

        conectividade = np.hstack([np.full((n_tri, 1), 3, dtype=np.int64), faces_concat]).ravel()
        id_array = numpy_to_vtkIdTypeArray(conectividade, deep=True)
        cells = vtk.vtkCellArray()
        cells.ImportLegacyFormat(id_array)

        polydata_bruto = vtk.vtkPolyData()
        polydata_bruto.SetPoints(points)
        polydata_bruto.SetPolys(cells)

        normais = vtk.vtkPolyDataNormals()
        normais.SetInputData(polydata_bruto)
        normais.ComputeCellNormalsOn()
        normais.ComputePointNormalsOff()
        normais.SplittingOff()
        normais.Update()
        polydata = normais.GetOutput()

        _, _, cor_key = grupo_key
        n_cel = polydata.GetNumberOfCells()
        cor_rgb = tuple(int(round(c * 255)) for c in cor_key)
        cores = vtk.vtkUnsignedCharArray()
        cores.SetNumberOfComponents(3)
        cores.SetName("Cores")
        cores.SetNumberOfTuples(n_cel)
        cores_np = vtk_to_numpy(cores)
        cores_np[:, :] = cor_rgb
        polydata.GetCellData().SetScalars(cores)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.SetScalarModeToUseCellData()
        mapper.ScalarVisibilityOn()

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        self.renderer.AddActor(actor)

        self.mapper_por_grupo[grupo_key] = mapper
        self.array_cor_por_grupo[grupo_key] = cores_np
        self.grupo_por_actor[actor] = grupo_key
        self.actor_por_grupo[grupo_key] = actor

        faixas_ordenadas = sorted(faixas, key=lambda t: t[0])
        self.faixas_por_grupo[grupo_key] = (
            [f[0] for f in faixas_ordenadas],
            [f[1] for f in faixas_ordenadas],
        )

    @staticmethod
    def _cor_por_material(shape):
        """Extrai a cor difusa do primeiro material do elemento.

        shape.geometry.materials[i].diffuse NÃO é uma tupla indexável — é um
        objeto ifcopenshell_wrapper.colour com métodos .r()/.g()/.b()
        (confirmado em teste direto contra uma parede real; indexar com
        diffuse[0] levanta TypeError e cairia sempre no 'except', mostrando
        tudo cinza)."""
        try:
            materiais = shape.geometry.materials
            if materiais:
                diffuse = materiais[0].diffuse
                return diffuse.r(), diffuse.g(), diffuse.b()
        except Exception:
            pass
        return COR_PADRAO_ELEMENTO

    # ---------- seleção e criação de issues ----------
    def _elemento_do_clique(self, actor, cell_id):
        grupo_key = self.grupo_por_actor.get(actor)
        if grupo_key is None:
            return None
        inicios, indices = self.faixas_por_grupo.get(grupo_key, ([], []))
        if not inicios:
            return None
        pos = bisect.bisect_right(inicios, cell_id) - 1
        if pos < 0:
            return None
        return indices[pos]

    def on_elemento_selecionado(self, actor, cell_id, ponto_clique):
        elem_index = self._elemento_do_clique(actor, cell_id)
        if elem_index is None or not self.painel:
            return
        caminho = self.arquivo_por_id[elem_index]
        guid = self.guid_por_id[elem_index]
        elemento = self.arquivos_ifc[caminho].by_guid(guid)
        nome = getattr(elemento, "Name", None) or "Sem nome"
        classe = elemento.is_a()

        sessao = self.app.sessao
        if DialogNovaIssue.sessao_completa(sessao):
            # verificação iniciada com obra/disciplina/projetista: cria direto
            obra, criado_por, atribuido, disciplina = (sessao["obra"], sessao["nome"], sessao["atribuido_para"],
                                                       sessao["disciplina"])
        else:
            dialog = DialogNovaIssue(self.winfo_toplevel(), lista_obras=self.app.obras_lista, sessao=sessao)
            if not dialog.criado_por or not dialog.atribuido_para or not dialog.obra:
                return
            obra, criado_por, atribuido, disciplina = (dialog.obra, dialog.criado_por, dialog.atribuido_para,
                                                       dialog.disciplina)

        camera = self.renderer.GetActiveCamera()
        campos_extra = {
            "tipo_doc": "ifc",
            "filepath": caminho,
            "page": None,
            "pdf_x": None,
            "pdf_y": None,
            "ifc_global_id": guid,
            "ifc_nome_elemento": nome,
            "ifc_classe": classe,
            "posicao_3d": list(ponto_clique),
            "camera": {
                "position": list(camera.GetPosition()),
                "focal_point": list(camera.GetFocalPoint()),
                "view_up": list(camera.GetViewUp()),
            },
        }
        self.selecionar_elemento(elem_index)
        self.painel.criar_issue(
            obra, criado_por, atribuido, campos_extra,
            titulo=f"{classe} — {nome}", disciplina=disciplina,
        )

    def on_pin_issue_clicado(self, issue_id):
        """Clique num pino (alfinete/esfera) de issue: mostra os detalhes
        dela no painel em vez de criar uma issue nova ou selecionar o
        elemento do modelo por trás do pino."""
        if self.painel:
            self.painel.selecionar_issue(issue_id)

    def on_elemento_inspecionado(self, actor, cell_id, ponto_clique):
        elem_index = self._elemento_do_clique(actor, cell_id)
        if elem_index is None or not self.painel_propriedades:
            return
        caminho = self.arquivo_por_id[elem_index]
        guid = self.guid_por_id[elem_index]
        elemento = self.arquivos_ifc[caminho].by_guid(guid)
        cadeia = self._cadeia_hierarquia(elemento)
        self.painel_propriedades.mostrar(elemento, cadeia)
        self.mostrar_aba(self.tab_propriedades)
        self.selecionar_elemento(elem_index)

    def selecionar_elemento(self, elem_index):
        """Destaca visualmente (em laranja) o elemento clicado no modelo 3D,
        dando o retorno visual de 'isto está selecionado agora'."""
        self.elemento_selecionado_id = elem_index
        self.atualizar_destaques()

    @staticmethod
    def _cadeia_hierarquia(elemento):
        """Monta a cascata Projeto > ... > Elemento subindo pela hierarquia
        espacial via ifcopenshell.util.element.get_parent."""
        cadeia = []
        atual = elemento
        vistos = set()
        while atual is not None and atual.id() not in vistos:
            vistos.add(atual.id())
            cadeia.append((atual.is_a(), getattr(atual, "Name", None)))
            atual = ifcopenshell.util.element.get_parent(atual)
        cadeia.reverse()
        return cadeia

    def _ao_selecionar_issue(self, issue):
        if issue.get("tipo_doc") != "ifc":
            return
        self.restaurar_camera(issue.get("camera"))
        self.vtk_canvas.render_window.Render()

    def restaurar_camera(self, camera_info):
        if not camera_info:
            return
        cam = self.renderer.GetActiveCamera()
        cam.SetPosition(*camera_info.get("position", cam.GetPosition()))
        cam.SetFocalPoint(*camera_info.get("focal_point", cam.GetFocalPoint()))
        cam.SetViewUp(*camera_info.get("view_up", cam.GetViewUp()))
        self.renderer.ResetCameraClippingRange()

    # ---------- integração com a tela de Clash Detection ----------
    def destacar_e_focar_elementos(self, elementos_info):
        """Método aditivo usado pela tela "⚠ Clash Detection" (botão
        "👁 Ver em 3D"): `elementos_info` é uma lista de (info, cor01)
        onde `info` é {"guid","arquivo","ifc_class","nome"} — o mesmo
        formato salvo em db_clashes.json — e `cor01` uma cor (r,g,b) em
        [0,1]. Carrega os arquivos que ainda não estiverem abertos,
        destaca os elementos dados e enquadra a câmera nos dois. Não
        mexe em `elemento_selecionado_id` (o destaque de seleção usado
        por 📍 Marcar Issue/🔍 Inspecionar continua funcionando à parte —
        ver `atualizar_destaques`)."""
        import numpy as np
        import ifcopenshell.util.unit

        from clash.geometria import malha_por_guid

        self.elementos_destacados_clash = {}
        bbox_min_total, bbox_max_total = None, None

        for info, cor01 in elementos_info:
            caminho = info["arquivo"]
            if caminho not in self.arquivos_ifc:
                if not os.path.exists(caminho):
                    messagebox.showwarning(
                        "Arquivo não encontrado",
                        f"Não foi possível localizar o arquivo de origem para destacar o elemento:\n{caminho}",
                    )
                    continue
                self._carregar_ifc(caminho, limpar_existente=False)

            ifc_file = self.arquivos_ifc.get(caminho)
            if ifc_file is None:
                continue

            cor_rgb_255 = tuple(int(round(c * 255)) for c in cor01)
            try:
                elem_index = self.guid_por_id.index(info["guid"])
                self.elementos_destacados_clash[elem_index] = cor_rgb_255
            except ValueError:
                pass  # elemento sem geometria renderizável — segue sem destacá-lo visualmente

            try:
                escala = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
                malha = malha_por_guid(ifc_file, info["guid"], escala)
                if bbox_min_total is None:
                    bbox_min_total, bbox_max_total = malha.bounds[0].copy(), malha.bounds[1].copy()
                else:
                    bbox_min_total = np.minimum(bbox_min_total, malha.bounds[0])
                    bbox_max_total = np.maximum(bbox_max_total, malha.bounds[1])
            except Exception:
                pass

        self.atualizar_destaques()

        if bbox_min_total is not None:
            bounds = (bbox_min_total[0], bbox_max_total[0], bbox_min_total[1], bbox_max_total[1],
                      bbox_min_total[2], bbox_max_total[2])
            self.renderer.ResetCamera(bounds)
            self.renderer.GetActiveCamera().Zoom(0.8)
            self.renderer.ResetCameraClippingRange()

        self.vtk_canvas.render_window.Render()

    # ---------- destaque de status (array de cor por célula) ----------
    def atualizar_destaques(self):
        """Recolore as células do modelo apenas para o destaque de SELEÇÃO
        (elemento clicado com 🔍 Inspecionar/📍 Marcar Issue) — o
        acompanhamento de status das issues não pinta mais o elemento
        inteiro, e sim um alfinete (esfera) próprio, ver `atualizar_pins_issues`."""
        if not IFC_VIEWER_OK:
            return
        for grupo_key, (inicios, indices) in self.faixas_por_grupo.items():
            array_np = self.array_cor_por_grupo[grupo_key]
            n_total = array_np.shape[0]
            for pos, elem_index in enumerate(indices):
                inicio = inicios[pos]
                fim = inicios[pos + 1] if pos + 1 < len(inicios) else n_total
                if elem_index in self.elementos_destacados_clash:
                    cor_rgb = self.elementos_destacados_clash[elem_index]
                elif elem_index == self.elemento_selecionado_id:
                    cor_rgb = COR_SELECAO
                else:
                    cor_rgb = self.cor_base_por_id[elem_index]
                array_np[inicio:fim] = cor_rgb

        for mapper in self.mapper_por_grupo.values():
            mapper.GetInput().GetCellData().GetScalars().Modified()

        if hasattr(self, "vtk_canvas"):
            self.vtk_canvas.render_window.Render()

    # ---------- alfinetes (pins) de issues, coloridos por status ----------
    def atualizar_pins_issues(self):
        if not IFC_VIEWER_OK:
            return
        prioridade = ["Novo", "Reaberto", "Respondido", "Fechado"]
        ids_atuais = set()

        for issue in self.app.issues:
            if issue.get("tipo_doc") != "ifc" or issue.get("filepath") not in self.arquivos_ifc:
                continue
            posicao = issue.get("posicao_3d")
            if not posicao:
                continue  # issues antigas, criadas antes deste recurso, ficam sem pino

            issue_id = issue["id"]
            ids_atuais.add(issue_id)
            cor_hex = CORES_STATUS.get(issue.get("status"), "#999999")
            cor01 = hex_to_rgb01(cor_hex)

            ator = self.pins_por_issue_id.get(issue_id)
            if ator is None:
                ator = self._criar_pin_issue(posicao, cor01)
                self.pins_por_issue_id[issue_id] = ator
                self.issue_id_por_pin_actor[ator] = issue_id
            else:
                ator.SetPosition(*posicao)
                ator.GetProperty().SetColor(*cor01)

        for issue_id in list(self.pins_por_issue_id.keys()):
            if issue_id not in ids_atuais:
                ator = self.pins_por_issue_id.pop(issue_id)
                self.issue_id_por_pin_actor.pop(ator, None)
                self.renderer.RemoveActor(ator)

        if hasattr(self, "vtk_canvas"):
            self.vtk_canvas.render_window.Render()

    def _criar_pin_issue(self, posicao, cor01):
        esfera = vtk.vtkSphereSource()
        esfera.SetRadius(max(self._diagonal_modelo() * 0.003, 0.012))
        esfera.SetThetaResolution(16)
        esfera.SetPhiResolution(16)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(esfera.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.SetPosition(*posicao)
        actor.GetProperty().SetColor(*cor01)
        actor.GetProperty().SetAmbient(0.7)
        # Pickable: um clique em cima do pino mostra a issue (ver
        # `_selecionar_elemento`, que confere o mapa de pinos ANTES de tratar
        # o clique como seleção/criação de issue num elemento do modelo).
        self.renderer.AddActor(actor)
        return actor

    def atualizar_visual_issues(self):
        """Callback único chamado quando issues são criadas/editadas/excluídas:
        atualiza tanto o destaque de seleção quanto os pinos por status."""
        self.atualizar_destaques()
        self.atualizar_pins_issues()

    # ---------- vistas predefinidas, projeção e enquadramento ----------
    def _ao_redimensionar_viewport(self, event=None):
        """Chamado sempre que a viewport 3D muda de tamanho (redimensionar a
        janela ou arrastar a divisória do painel lateral). Ajusta o
        enquadramento da câmera para o novo tamanho e reaplica a caixa de
        corte — que é definida em coordenadas do mundo e não deveria mudar
        sozinha, mas isso garante que ela fique sempre sincronizada mesmo
        que o redimensionamento deixe algo temporariamente desatualizado."""
        self.renderer.ResetCameraClippingRange()
        if self.caixa_corte_ativa:
            self._aplicar_caixa_corte()
        self.vtk_canvas.render_window.Render()

    def _resetar_camera(self):
        self.renderer.ResetCamera()
        self.vtk_canvas.render_window.Render()

    def _vista_predefinida(self, nome):
        if not self.mapper_por_grupo:
            return
        bounds = self.renderer.ComputeVisiblePropBounds()
        cx, cy, cz = (bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, (bounds[4] + bounds[5]) / 2
        distancia = max(math.dist((bounds[0], bounds[2], bounds[4]), (bounds[1], bounds[3], bounds[5])), 1.0)

        camera = self.renderer.GetActiveCamera()
        camera.SetFocalPoint(cx, cy, cz)
        if nome == "superior":
            camera.SetPosition(cx, cy, cz + distancia)
            camera.SetViewUp(0, 1, 0)
        elif nome == "frontal":
            camera.SetPosition(cx, cy - distancia, cz)
            camera.SetViewUp(0, 0, 1)
        elif nome == "lateral":
            camera.SetPosition(cx + distancia, cy, cz)
            camera.SetViewUp(0, 0, 1)
        elif nome == "isometrica":
            d = distancia / math.sqrt(3)
            camera.SetPosition(cx + d, cy - d, cz + d)
            camera.SetViewUp(0, 0, 1)
        self.renderer.ResetCameraClippingRange()
        self.vtk_canvas.render_window.Render()

    def _alternar_projecao(self):
        camera = self.renderer.GetActiveCamera()
        ativar_ortogonal = not camera.GetParallelProjection()
        camera.SetParallelProjection(ativar_ortogonal)
        self.btn_projecao.config_texto("Ortogonal" if ativar_ortogonal else "Perspectiva")
        self.vtk_canvas.render_window.Render()

    # ---------- caixa de corte (section box) ----------
    # Implementada com 6 planos de corte calculados a partir de percentuais
    # (ajustados por slider na aba ⚙ Configurações) sobre os limites do
    # modelo, com um contorno (vtkOutlineSource) visível na cena mostrando
    # exatamente onde o corte está acontecendo. Um vtkBoxWidget arrastável
    # em 3D foi tentado antes, mas se mostrou pouco confiável junto com o
    # embutimento manual do VTK no Tkinter usado aqui; o corte por
    # vtkPolyDataMapper.SetClippingPlanes em si foi validado à parte
    # (renderização off-screen com contagem de pixels antes/depois do corte).
    def _alternar_caixa_corte(self):
        if self.caixa_corte_ativa:
            self._desativar_caixa_corte()
        else:
            self._ativar_caixa_corte()

    def _capturar_bounds_originais(self):
        """Calcula os limites do modelo (sem o contorno/manípulos da própria
        caixa de corte, que têm tamanho físico e 'vazam' um pouco para fora
        da caixa) — usar ComputeVisiblePropBounds() diretamente enquanto o
        contorno/manípulos já estão visíveis criava um loop de
        realimentação: cada vez que a caixa era reaplicada (inclusive ao
        redimensionar a viewport), os limites cresciam um pouco, fazendo a
        caixa 'andar sozinha'."""
        estava_visivel = bool(self.actor_caixa_corte.GetVisibility())
        if estava_visivel:
            self.actor_caixa_corte.VisibilityOff()
            for _, actor in self.handles_caixa_corte.values():
                actor.VisibilityOff()
        bounds = self.renderer.ComputeVisiblePropBounds()
        if estava_visivel:
            self.actor_caixa_corte.VisibilityOn()
            for _, actor in self.handles_caixa_corte.values():
                actor.VisibilityOn()
        self._bounds_originais = bounds
        return bounds

    def _ativar_caixa_corte(self):
        if not self.mapper_por_grupo:
            messagebox.showinfo("Caixa de Corte", "Abra um modelo IFC primeiro.")
            if hasattr(self, "var_caixa_corte"):
                self.var_caixa_corte.set(False)
            return
        self.caixa_corte_ativa = True
        self._capturar_bounds_originais()
        if hasattr(self, "btn_caixa_corte"):
            self.btn_caixa_corte.definir_variante("ativo")
        if hasattr(self, "var_caixa_corte"):
            self.var_caixa_corte.set(True)
        self._aplicar_caixa_corte()

    def _desativar_caixa_corte(self):
        self.caixa_corte_ativa = False
        self._arrastando_handle = None
        for mapper in self.mapper_por_grupo.values():
            mapper.RemoveAllClippingPlanes()
        if hasattr(self, "actor_caixa_corte"):
            self.actor_caixa_corte.VisibilityOff()
        for _, actor in getattr(self, "handles_caixa_corte", {}).values():
            actor.VisibilityOff()
        if hasattr(self, "btn_caixa_corte"):
            self.btn_caixa_corte.definir_variante("fantasma")
        if hasattr(self, "var_caixa_corte"):
            self.var_caixa_corte.set(False)
        if hasattr(self, "vtk_canvas"):
            self.vtk_canvas.render_window.Render()

    def _aplicar_caixa_corte(self):
        if not self.caixa_corte_ativa or not self.mapper_por_grupo:
            return
        limites = self._limites_caixa_corte()
        planos = self._planos_caixa_corte(limites)
        for mapper in self.mapper_por_grupo.values():
            mapper.SetClippingPlanes(planos)
        self.outline_source.SetBounds(*limites)
        self.actor_caixa_corte.VisibilityOn()
        self._posicionar_handles(limites)
        self.vtk_canvas.render_window.Render()

    def _tamanho_handle_atual(self, centro_caixa):
        """Tamanho dos manípulos com base no quanto da tela a caixa ocupa
        NESTE momento (distância da câmera), não uma fração fixa do
        tamanho absoluto do modelo — em um prédio grande, uma seta com
        alguns % do tamanho do prédio inteiro fica enorme na tela."""
        camera = self.renderer.GetActiveCamera()
        if camera.GetParallelProjection():
            meia_altura_mundo = camera.GetParallelScale()
        else:
            distancia = math.dist(camera.GetPosition(), centro_caixa)
            meia_altura_mundo = distancia * math.tan(math.radians(camera.GetViewAngle()) / 2)
        return max(meia_altura_mundo * 0.045, 1e-4)

    def _posicionar_handles(self, limites):
        cx0, cx1, cy0, cy1, cz0, cz1 = limites
        centro_x, centro_y, centro_z = (cx0 + cx1) / 2, (cy0 + cy1) / 2, (cz0 + cz1) / 2
        tamanho = self._tamanho_handle_atual((centro_x, centro_y, centro_z))
        posicoes = {
            "x0": (cx0, centro_y, centro_z), "x1": (cx1, centro_y, centro_z),
            "y0": (centro_x, cy0, centro_z), "y1": (centro_x, cy1, centro_z),
            "z0": (centro_x, centro_y, cz0), "z1": (centro_x, centro_y, cz1),
        }
        # Afasta cada manípulo um pouco para FORA da caixa (sentido oposto ao
        # "para dentro" usado no corte): posicionado exatamente na face, o
        # cone ficava embutido na própria geometria do modelo e o picking
        # acabava acertando a parede/duto em vez do manípulo.
        margem = tamanho * 2.0
        for chave, (cone, actor) in self.handles_caixa_corte.items():
            direcao_para_dentro = self._direcao_por_handle[chave]
            centro = posicoes[chave]
            centro_afastado = tuple(centro[i] - direcao_para_dentro[i] * margem for i in range(3))
            cone.SetHeight(tamanho)
            cone.SetRadius(tamanho * 0.4)
            cone.SetCenter(*centro_afastado)
            actor.VisibilityOn()

    def _sincronizar_handles_com_camera(self, obj, event):
        """Observer de 'StartEvent' da render window: roda antes de cada
        quadro para manter o tamanho dos manípulos consistente com o zoom
        atual. Só faz algo quando a caixa de corte está ativa (custo zero
        no resto do tempo) — e mesmo ativa, é só um pouco de aritmética
        sobre 6 cones, nada que toque na geometria do modelo."""
        if not self.caixa_corte_ativa or self._bounds_originais is None:
            return
        self._posicionar_handles(self._limites_caixa_corte())

    # ---------- arrastar os manípulos (setas) da caixa de corte ----------
    def iniciar_arraste_handle(self, x, y):
        picker = vtk.vtkPropPicker()
        picker.Pick(x, y, 0, self.renderer)
        actor = picker.GetActor()
        info = self._handles_por_actor.get(actor)
        if info is None:
            return False
        chave, direcao = info

        ponto_pick = picker.GetPickPosition()
        self.renderer.SetWorldPoint(ponto_pick[0], ponto_pick[1], ponto_pick[2], 1.0)
        self.renderer.WorldToDisplay()
        _, _, z_tela = self.renderer.GetDisplayPoint()

        if self._bounds_originais is None:
            self._capturar_bounds_originais()

        self._arrastando_handle = {"chave": chave, "direcao": direcao, "z_tela": z_tela, "ultimo_xy": (x, y)}
        return True

    def _mundo_em(self, x, y, z_tela):
        self.renderer.SetDisplayPoint(x, y, z_tela)
        self.renderer.DisplayToWorld()
        wx, wy, wz, w = self.renderer.GetWorldPoint()
        if w != 0:
            return (wx / w, wy / w, wz / w)
        return (wx, wy, wz)

    def continuar_arraste_handle(self, x, y):
        info = self._arrastando_handle
        if info is None:
            return
        p_antigo = self._mundo_em(info["ultimo_xy"][0], info["ultimo_xy"][1], info["z_tela"])
        p_novo = self._mundo_em(x, y, info["z_tela"])
        deslocamento = sum((p_novo[i] - p_antigo[i]) * info["direcao"][i] for i in range(3))
        info["ultimo_xy"] = (x, y)

        eixo_map = {"x0": 0, "x1": 0, "y0": 1, "y1": 1, "z0": 2, "z1": 2}
        idx = eixo_map[info["chave"]]
        tamanho_total = self._bounds_originais[idx * 2 + 1] - self._bounds_originais[idx * 2]
        if tamanho_total <= 1e-9:
            return

        delta_pct = (deslocamento / tamanho_total) * 100
        novo_valor = min(95.0, max(0.0, self.corte_pct[info["chave"]] + delta_pct))
        self.corte_pct[info["chave"]] = novo_valor
        self._aplicar_caixa_corte()

        escala = self.escalas_corte.get(info["chave"])
        if escala is not None:
            try:
                escala.set(novo_valor)
            except tk.TclError:
                pass

    def finalizar_arraste_handle(self):
        self._arrastando_handle = None

    def _limites_caixa_corte(self):
        if self._bounds_originais is None:
            self._capturar_bounds_originais()
        xmin, xmax, ymin, ymax, zmin, zmax = self._bounds_originais
        cx0 = xmin + (xmax - xmin) * self.corte_pct["x0"] / 100
        cx1 = xmax - (xmax - xmin) * self.corte_pct["x1"] / 100
        cy0 = ymin + (ymax - ymin) * self.corte_pct["y0"] / 100
        cy1 = ymax - (ymax - ymin) * self.corte_pct["y1"] / 100
        cz0 = zmin + (zmax - zmin) * self.corte_pct["z0"] / 100
        cz1 = zmax - (zmax - zmin) * self.corte_pct["z1"] / 100
        return cx0, cx1, cy0, cy1, cz0, cz1

    @staticmethod
    def _planos_caixa_corte(limites):
        # vtkMapper.SetClippingPlanes mantém o lado POSITIVO de cada plano
        # (normal · (ponto - origem) >= 0) e descarta o lado negativo —
        # confirmado com um teste isolado (retângulo assimétrico + contagem
        # de pixels visíveis por coluna antes/depois do corte). O normal de
        # cada plano deve apontar para DENTRO da região a manter, na mesma
        # convenção usada pelos manípulos (ver especificacao_handles).
        cx0, cx1, cy0, cy1, cz0, cz1 = limites
        especificacao = (
            ((1, 0, 0), (cx0, 0, 0)),
            ((-1, 0, 0), (cx1, 0, 0)),
            ((0, 1, 0), (0, cy0, 0)),
            ((0, -1, 0), (0, cy1, 0)),
            ((0, 0, 1), (0, 0, cz0)),
            ((0, 0, -1), (0, 0, cz1)),
        )
        planos = vtk.vtkPlaneCollection()
        for normal, origem in especificacao:
            plano = vtk.vtkPlane()
            plano.SetNormal(*normal)
            plano.SetOrigin(*origem)
            planos.AddItem(plano)
        return planos

    def _on_slider_corte(self, chave, valor):
        self.corte_pct[chave] = float(valor)
        self._aplicar_caixa_corte()

    def _on_checkbox_caixa_corte(self):
        if self.var_caixa_corte.get():
            self._ativar_caixa_corte()
        else:
            self._desativar_caixa_corte()

    # ---------- aba de engrenagem (configurações) ----------
    def _abrir_configuracoes(self):
        if self._janela_config is not None and self._janela_config.winfo_exists():
            self._janela_config.lift()
            return

        win = tk.Toplevel(self, bg=TEMA["surface"])
        win.title("⚙ Configurações do Visualizador IFC")
        win.geometry("380x580")
        win.transient(self.winfo_toplevel())
        self._janela_config = win

        def rotulo(texto, **kw):
            return tk.Label(win, text=texto, bg=TEMA["surface"], fg=TEMA["texto"], **kw)

        rotulo("Navegação", font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 4))

        tk.Button(win, text="🎮 Consultar / Mudar Controles de Navegação",
                  command=self._abrir_controles_navegacao, bg=TEMA["surface_alt"], fg=TEMA["texto"],
                  font=("Arial", 9)).pack(fill=tk.X, padx=12, pady=(0, 10))

        rotulo("Sensibilidade do mouse (olhar ao redor, modo 1ª Pessoa):").pack(
            anchor="w", padx=12
        )
        escala_sens = ttk.Scale(
            win, from_=0.05, to=1.0, orient=tk.HORIZONTAL,
            command=lambda v: setattr(self, "sensibilidade_mouse", float(v))
        )
        escala_sens.set(self.sensibilidade_mouse)
        escala_sens.pack(fill=tk.X, padx=12, pady=(0, 10))

        rotulo("Velocidade de deslocamento (W/A/S/D/Q/E):").pack(anchor="w", padx=12)
        escala_vel = ttk.Scale(
            win, from_=0.2, to=5.0, orient=tk.HORIZONTAL,
            command=lambda v: setattr(self, "velocidade_deslocamento", float(v))
        )
        escala_vel.set(self.velocidade_deslocamento)
        escala_vel.pack(fill=tk.X, padx=12, pady=(0, 15))

        tk.Frame(win, height=2, bg=TEMA["borda"]).pack(fill=tk.X, padx=12, pady=5)

        rotulo("Caixa de Corte", font=("Arial", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self.var_caixa_corte = tk.BooleanVar(value=self.caixa_corte_ativa)
        tk.Checkbutton(
            win, text="Ativar caixa de corte", variable=self.var_caixa_corte,
            bg=TEMA["surface"], fg=TEMA["texto"], activebackground=TEMA["surface"],
            selectcolor=TEMA["surface_alt"], command=self._on_checkbox_caixa_corte
        ).pack(anchor="w", padx=12)

        eixos = (
            ("Corte a partir de -X (%)", "x0"), ("Corte a partir de +X (%)", "x1"),
            ("Corte a partir de -Y (%)", "y0"), ("Corte a partir de +Y (%)", "y1"),
            ("Corte a partir de -Z / base (%)", "z0"), ("Corte a partir de +Z / topo (%)", "z1"),
        )
        self.escalas_corte = {}
        for texto, chave in eixos:
            rotulo(texto).pack(anchor="w", padx=12, pady=(6, 0))
            escala = ttk.Scale(
                win, from_=0, to=95, orient=tk.HORIZONTAL,
                command=lambda v, k=chave: self._on_slider_corte(k, v)
            )
            escala.set(self.corte_pct[chave])
            escala.pack(fill=tk.X, padx=12)
            self.escalas_corte[chave] = escala

        tk.Button(win, text="Fechar", command=win.destroy, bg=TEMA["surface_alt"], fg=TEMA["texto"]).pack(pady=15)

    def _abrir_controles_navegacao(self):
        """Referência dos controles de mouse/teclado, com as poucas opções
        que realmente fazem sentido o usuário poder mudar (inverter o eixo
        vertical do mouse, e a velocidade/sensibilidade já configuráveis
        acima) — em vez de uma tela de remapeamento livre tecla-a-tecla, que
        adicionaria complexidade sem necessidade real aqui."""
        if self._janela_controles is not None and self._janela_controles.winfo_exists():
            self._janela_controles.lift()
            return

        win = tk.Toplevel(self, bg=TEMA["surface"])
        win.title("🎮 Controles de Navegação")
        win.geometry("400x480")
        win.transient(self.winfo_toplevel())
        self._janela_controles = win

        def rotulo(texto, **kw):
            return tk.Label(win, text=texto, bg=TEMA["surface"], fg=TEMA["texto"], justify="left", **kw)

        def secao(titulo):
            rotulo(titulo, font=("Arial", 10, "bold")).pack(anchor="w", padx=14, pady=(12, 2))

        def linha(controle, acao):
            f = tk.Frame(win, bg=TEMA["surface"])
            f.pack(fill=tk.X, padx=14, pady=1)
            tk.Label(f, text=controle, bg=TEMA["surface"], fg=TEMA["acento"],
                     font=("Consolas", 9, "bold"), width=16, anchor="w").pack(side=tk.LEFT)
            tk.Label(f, text=acao, bg=TEMA["surface"], fg=TEMA["texto_fraco"],
                     anchor="w", wraplength=230, justify="left").pack(side=tk.LEFT, fill=tk.X, expand=True)

        secao("🧭 Orbitar (padrão)")
        linha("Botão esquerdo", "Girar (eixo vertical travado, sem tombar)")
        linha("Botão direito", "Zoom")
        linha("Botão do meio", "Deslocar a vista (pan)")
        linha("Roda do mouse", "Zoom")

        secao("🚶 1ª Pessoa")
        linha("W A S D", "Andar (frente/trás/esquerda/direita)")
        linha("↑ ← ↓ →", "O mesmo que W A S D")
        linha("Q / E", "Descer / subir")
        linha("Botão esquerdo", "Olhar ao redor (arrastar)")

        secao("📍 🔍 ✂ Ferramentas")
        linha("Clique esquerdo", "Marcar issue / Inspecionar / mover manípulo da caixa de corte")

        tk.Frame(win, height=2, bg=TEMA["borda"]).pack(fill=tk.X, padx=12, pady=10)

        secao("Personalizar")
        self.var_inverter_y = tk.BooleanVar(value=self.inverter_eixo_y)
        tk.Checkbutton(
            win, text="Inverter eixo vertical do mouse (olhar para cima/baixo)",
            variable=self.var_inverter_y, bg=TEMA["surface"], fg=TEMA["texto"],
            activebackground=TEMA["surface"], selectcolor=TEMA["surface_alt"],
            command=lambda: setattr(self, "inverter_eixo_y", self.var_inverter_y.get()),
        ).pack(anchor="w", padx=14, pady=(4, 0))
        rotulo(
            "Afeta a Órbita (arrastar para cima/baixo) e a 1ª Pessoa (olhar\n"
            "para cima/baixo) ao mesmo tempo.",
            font=("Arial", 8),
        ).pack(anchor="w", padx=14, pady=(2, 10))

        tk.Button(win, text="Fechar", command=win.destroy, bg=TEMA["surface_alt"], fg=TEMA["texto"]).pack(pady=10)

    # ---------- navegação: órbita travada ao eixo vertical ----------
    def orbitar_travado(self, dx_px, dy_px):
        """Órbita 'de carrossel': gira lateralmente em torno do eixo vertical
        do mundo e verticalmente em torno do eixo lateral da câmera, sem
        nunca inclinar/rolar a câmera de lado — ao contrário da órbita livre
        padrão (vtkInteractorStyleTrackballCamera), que permite qualquer
        rotação (inclusive "de cabeça para baixo") dependendo da direção do
        arraste."""
        camera = self.renderer.GetActiveCamera()
        sensibilidade = 0.4
        sinal_y = -1 if self.inverter_eixo_y else 1
        delta_azimute = -dx_px * sensibilidade
        delta_elevacao = -dy_px * sensibilidade * sinal_y

        fp = camera.GetFocalPoint()
        pos = camera.GetPosition()
        vetor = [pos[i] - fp[i] for i in range(3)]
        raio = math.sqrt(sum(c * c for c in vetor)) or 1.0

        vetor = list(_girar_vetor(vetor, EIXO_VERTICAL_MUNDO, delta_azimute))

        eixo_lateral = [0.0, 0.0, 0.0]
        vtk.vtkMath.Cross(EIXO_VERTICAL_MUNDO, vetor, eixo_lateral)
        norma_lateral = math.sqrt(sum(c * c for c in eixo_lateral))
        if norma_lateral > 1e-6:
            eixo_lateral = [c / norma_lateral for c in eixo_lateral]
            candidato = list(_girar_vetor(vetor, eixo_lateral, delta_elevacao))
            norma_candidato = math.sqrt(sum(c * c for c in candidato)) or 1.0
            cos_com_vertical = candidato[2] / norma_candidato
            # Não deixa a câmera cruzar os "polos" (olhar reto para cima/baixo)
            # para nunca ficar paralela ao eixo travado — evita o "gimbal lock".
            if abs(cos_com_vertical) < 0.98:
                vetor = candidato

        norma = math.sqrt(sum(c * c for c in vetor)) or 1.0
        vetor = [c / norma * raio for c in vetor]

        camera.SetPosition(*(fp[i] + vetor[i] for i in range(3)))
        camera.SetViewUp(*EIXO_VERTICAL_MUNDO)
        self.renderer.ResetCameraClippingRange()
        self.vtk_canvas.render_window.Render()

    # ---------- navegação em primeira pessoa ----------
    def _diagonal_modelo(self):
        if not self.mapper_por_grupo:
            return 1.0
        bounds = self.renderer.ComputeVisiblePropBounds()
        return math.dist((bounds[0], bounds[2], bounds[4]), (bounds[1], bounds[3], bounds[5])) or 1.0

    def _mover_fps(self, frente, lado, vertical):
        if self.ferramenta_atual != "fps" or not self.mapper_por_grupo:
            return
        camera = self.renderer.GetActiveCamera()
        pos = camera.GetPosition()
        fp = camera.GetFocalPoint()
        up = camera.GetViewUp()

        direcao = [fp[i] - pos[i] for i in range(3)]
        vtk.vtkMath.Normalize(direcao)

        direita = [0.0, 0.0, 0.0]
        vtk.vtkMath.Cross(direcao, up, direita)
        vtk.vtkMath.Normalize(direita)

        passo = max(self._diagonal_modelo() * 0.02, 0.1) * self.velocidade_deslocamento
        deslocamento = [
            direcao[i] * frente * passo + direita[i] * lado * passo + up[i] * vertical * passo
            for i in range(3)
        ]
        camera.SetPosition(*(pos[i] + deslocamento[i] for i in range(3)))
        camera.SetFocalPoint(*(fp[i] + deslocamento[i] for i in range(3)))
        self.renderer.ResetCameraClippingRange()
        self.vtk_canvas.render_window.Render()

    def olhar_ao_redor(self, dx_px, dy_px):
        """Olhar ao redor no modo 1ª Pessoa, travado ao eixo vertical do
        mundo — a mesma lógica de `orbitar_travado`, adaptada para girar a
        direção do olhar (em vez da posição da câmera): olhar para os lados
        gira em torno do eixo vertical do mundo, olhar para cima/baixo gira
        em torno do eixo lateral, e a câmera nunca "tomba" de lado."""
        camera = self.renderer.GetActiveCamera()
        sinal_y = -1 if self.inverter_eixo_y else 1
        yaw = -dx_px * self.sensibilidade_mouse
        pitch = -dy_px * self.sensibilidade_mouse * sinal_y

        pos = camera.GetPosition()
        fp = camera.GetFocalPoint()

        distancia = max(math.dist(pos, fp), 1e-6)
        direcao = [(fp[i] - pos[i]) / distancia for i in range(3)]

        direcao = list(_girar_vetor(direcao, EIXO_VERTICAL_MUNDO, yaw))

        eixo_lateral = [0.0, 0.0, 0.0]
        vtk.vtkMath.Cross(direcao, EIXO_VERTICAL_MUNDO, eixo_lateral)
        norma_lateral = math.sqrt(sum(c * c for c in eixo_lateral))
        if norma_lateral > 1e-6:
            eixo_lateral = [c / norma_lateral for c in eixo_lateral]
            candidato = list(_girar_vetor(direcao, eixo_lateral, pitch))
            norma_candidato = math.sqrt(sum(c * c for c in candidato)) or 1.0
            cos_com_vertical = candidato[2] / norma_candidato
            # Não deixa a mira cruzar os "polos" (olhar reto para cima/baixo),
            # pelo mesmo motivo do clamp em orbitar_travado: evita gimbal lock.
            if abs(cos_com_vertical) < 0.98:
                direcao = candidato

        norma = math.sqrt(sum(c * c for c in direcao)) or 1.0
        direcao = [c / norma for c in direcao]

        nova_fp = [pos[i] + direcao[i] * distancia for i in range(3)]
        camera.SetFocalPoint(*nova_fp)
        camera.SetViewUp(*EIXO_VERTICAL_MUNDO)
        self.renderer.ResetCameraClippingRange()
        self.vtk_canvas.render_window.Render()

    # ---------- ferramentas de medição (régua, ângulo, laser) ----------
    def _ponto_3d_no_clique(self, x, y):
        """Faz o picking na posição de tela (x, y) e ajusta ('snap') o ponto
        obtido para o vértice de malha mais próximo do ponto de interseção
        real — aproximação simples da 'referência automática' de softwares
        como SketchUp/Trimble Connect (que fazem inferência a vértices,
        arestas, pontos médios etc.). Retorna (ponto, escala_em_metros) ou
        (None, 1.0) se nada foi clicado."""
        if not self.mapper_por_grupo:
            return None, 1.0
        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.005)
        picker.Pick(x, y, 0, self.renderer)
        actor = picker.GetActor()
        if actor is None:
            return None, 1.0

        grupo_key = self.grupo_por_actor.get(actor)
        if grupo_key is None:
            return None, 1.0  # não é geometria do modelo (ex.: pino de issue) — nada a medir aqui

        ponto_clicado = picker.GetPickPosition()
        polydata = actor.GetMapper().GetInput()
        celula = polydata.GetCell(picker.GetCellId())
        pontos_celula = celula.GetPoints()

        melhor, menor_dist = None, None
        for i in range(pontos_celula.GetNumberOfPoints()):
            candidato = pontos_celula.GetPoint(i)
            d = math.dist(candidato, ponto_clicado)
            if menor_dist is None or d < menor_dist:
                menor_dist, melhor = d, candidato
        ponto = melhor if melhor is not None else tuple(ponto_clicado)

        escala = self.escala_por_arquivo.get(grupo_key[0], 1.0)
        return ponto, escala

    def on_clique_medicao(self, x, y):
        ponto, escala = self._ponto_3d_no_clique(x, y)
        if ponto is None:
            return
        modo = self.ferramenta_atual

        if modo == "medir_laser":
            self._limpar_previa()
            self._remover_atores(self._marcadores_atuais)
            self._marcadores_atuais = []
            self._medicao_pontos = [ponto]
            self._medicao_escala_atual = escala
            self._adicionar_marcador(ponto)
            return

        if not self._medicao_pontos:
            self._medicao_escala_atual = escala
        self._medicao_pontos.append(ponto)
        self._adicionar_marcador(ponto)

        if modo == "medir_regua" and len(self._medicao_pontos) == 2:
            self._concluir_medicao_regua()
        elif modo == "medir_angulo" and len(self._medicao_pontos) == 3:
            self._concluir_medicao_angulo()

    def atualizar_previa_medicao(self, x, y):
        if not self._medicao_pontos:
            return
        ponto_atual, _ = self._ponto_3d_no_clique(x, y)
        if ponto_atual is None:
            return
        self._limpar_previa()
        origem = self._medicao_pontos[-1]
        distancia = math.dist(origem, ponto_atual) * self._medicao_escala_atual
        linha = self._criar_linha(origem, ponto_atual, cor=(0.0, 1.0, 1.0), tracejado=True)
        meio = [(origem[i] + ponto_atual[i]) / 2 for i in range(3)]
        rotulo = self._criar_rotulo(meio, f"{distancia:.2f} m", cor=(0.0, 1.0, 1.0))
        self._preview_actors = [linha, rotulo]
        self.vtk_canvas.render_window.Render()

    def _concluir_medicao_regua(self):
        self._limpar_previa()
        p0, p1 = self._medicao_pontos
        distancia = math.dist(p0, p1) * self._medicao_escala_atual
        linha = self._criar_linha(p0, p1)
        meio = [(p0[i] + p1[i]) / 2 for i in range(3)]
        rotulo = self._criar_rotulo(meio, f"{distancia:.2f} m")
        self._medicoes_finalizadas.append([linha, rotulo] + self._marcadores_atuais)
        self._marcadores_atuais = []
        self._medicao_pontos = []
        self.vtk_canvas.render_window.Render()

    def _concluir_medicao_angulo(self):
        self._limpar_previa()
        p0, vertice, p2 = self._medicao_pontos
        v1 = [p0[i] - vertice[i] for i in range(3)]
        v2 = [p2[i] - vertice[i] for i in range(3)]
        n1 = math.sqrt(sum(c * c for c in v1)) or 1.0
        n2 = math.sqrt(sum(c * c for c in v2)) or 1.0
        cos_ang = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2)) / (n1 * n2)))
        angulo = math.degrees(math.acos(cos_ang))

        linha1 = self._criar_linha(p0, vertice)
        linha2 = self._criar_linha(vertice, p2)
        rotulo = self._criar_rotulo(vertice, f"{angulo:.1f}°")
        self._medicoes_finalizadas.append([linha1, linha2, rotulo] + self._marcadores_atuais)
        self._marcadores_atuais = []
        self._medicao_pontos = []
        self.vtk_canvas.render_window.Render()

    def limpar_medicoes(self):
        for atores in self._medicoes_finalizadas:
            self._remover_atores(atores)
        self._medicoes_finalizadas = []
        self._cancelar_medicao_em_andamento()
        if hasattr(self, "vtk_canvas"):
            self.vtk_canvas.render_window.Render()

    def _cancelar_medicao_em_andamento(self):
        self._limpar_previa()
        self._remover_atores(self._marcadores_atuais)
        self._marcadores_atuais = []
        self._medicao_pontos = []

    def _limpar_previa(self):
        self._remover_atores(self._preview_actors)
        self._preview_actors = []

    def _remover_atores(self, atores):
        for ator in atores:
            self.renderer.RemoveActor(ator)

    def _adicionar_marcador(self, ponto):
        esfera = vtk.vtkSphereSource()
        esfera.SetCenter(*ponto)
        esfera.SetRadius(max(self._diagonal_modelo() * 0.004, 0.01))
        esfera.SetThetaResolution(12)
        esfera.SetPhiResolution(12)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(esfera.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1.0, 0.6, 0.0)
        self.renderer.AddActor(actor)
        self._marcadores_atuais.append(actor)
        return actor

    def _criar_linha(self, p0, p1, cor=(1.0, 1.0, 0.0), tracejado=False):
        fonte = vtk.vtkLineSource()
        fonte.SetPoint1(*p0)
        fonte.SetPoint2(*p1)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(fonte.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*cor)
        actor.GetProperty().SetLineWidth(2)
        if tracejado:
            actor.GetProperty().SetLineStipplePattern(0xF0F0)
            actor.GetProperty().SetLineStippleRepeatFactor(2)
        self.renderer.AddActor(actor)
        return actor

    def _criar_rotulo(self, posicao, texto, cor=(1.0, 1.0, 0.0)):
        rotulo = vtk.vtkBillboardTextActor3D()
        rotulo.SetInput(texto)
        rotulo.SetPosition(*posicao)
        rotulo.GetTextProperty().SetColor(*cor)
        rotulo.GetTextProperty().SetFontSize(16)
        rotulo.GetTextProperty().SetBold(True)
        rotulo.GetTextProperty().SetBackgroundColor(0, 0, 0)
        rotulo.GetTextProperty().SetBackgroundOpacity(0.6)
        self.renderer.AddActor(rotulo)
        return rotulo

    # ---------- integração com AppCDE ----------
    def sincronizar(self):
        if self.painel:
            self.painel.atualizar_obras()
            self.painel.atualizar_lista()
        self.atualizar_visual_issues()
