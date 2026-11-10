"""Tela de validação de pranchas (protótipo Figma): visualizador de PDF
em tela cheia com cabeçalho do projeto, ferramentas de marcação
(comentários/pins, medição, desenho, formas, balões, textos), prancha
centralizada com sombra, painel de Comentários/Certificação à direita,
certificação por selo e exportação ("Baixar") da prancha revisada."""
import math
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import fitz  # PyMuPDF
from PIL import Image, ImageTk

from bcf_import import ler_issues_bcf
from certificacao import (
    ATIVO,
    aplicar_selo,
    estado_selo,
    legenda_selo,
    mover_selo,
    remover_selo,
    status_certificacao,
    tom_claro,
)
from config import CORES_STATUS, LISTA_CORES_ANOTACAO, TEMA
from dialogs import DialogNovaIssue, DialogObraImportacao, DialogTextoLivre
from pdf_exportacao import exportar_pdf_anotado
from projeto_vrf import iniciais, nome_certificado, pasta_vrf
from ui import preferencias
from ui.componentes import (
    FONTE_ICONE,
    Avatar,
    Botao,
    Icone,
    Pilula,
    fonte,
    retangulo_arredondado,
    texto_sobre,
)
from ui.atalhos import Dica, instalar_atalhos
from ui.painel_comentarios import LARGURA_PAINEL, PainelComentarios, titulo_do_texto
from ui.shell import imagem_marca
from utils import agora_str, carregar_anotacoes, filtro_issues_pdf, proximo_id, salvar_anotacoes

ZOOM_MINIMO = 0.15
ZOOM_MAXIMO = 5.0
MARGEM_PRANCHA = 40
_CACHE_SELOS = {}


def cor_cabecalho():
    return "#0E2F3A" if TEMA.esta_escuro() else "#14495D"


class _BotaoCabecalho(tk.Canvas):
    """Botão sobre o cabeçalho escuro: ícone e/ou texto brancos, contorno
    translúcido opcional e realce ao passar o mouse."""

    def __init__(self, parent, texto="", icone=None, comando=None, contorno=True, largura=None, altura=34):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0, cursor="hand2")
        self.texto, self.icone, self.comando, self.contorno = texto, icone, comando, contorno
        self._f = (fonte(10, "semi"))
        medida = tk.Label(self, text=texto, font=self._f).winfo_reqwidth() - 6 if texto else 0
        self.largura = largura or (medida + (26 if icone else 0) + (24 if texto else 16) + (0 if texto else 18))
        self.altura = altura
        self.configure(width=self.largura, height=altura)
        self._hover = False
        self._desenhar()
        self.bind("<Enter>", lambda e: self._set(True))
        self.bind("<Leave>", lambda e: self._set(False))
        self.bind("<ButtonRelease-1>", lambda e: self.comando(e) if self.comando else None)

    def _set(self, valor):
        self._hover = valor
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        fundo = "#1F5A70" if self._hover else self["bg"]
        borda = "#5A8696" if self.contorno else None
        if self._hover or self.contorno:
            retangulo_arredondado(self, 0, 0, self.largura, self.altura, 8, fundo, borda)
        if self.icone and self.texto:
            self.create_text(14, self.altura / 2, text=self.icone, font=(FONTE_ICONE, 10), fill="#FFFFFF", anchor="w")
            self.create_text(36, self.altura / 2, text=self.texto, font=self._f, fill="#FFFFFF", anchor="w")
        elif self.icone:
            self.create_text(self.largura / 2, self.altura / 2, text=self.icone, font=(FONTE_ICONE, 11),
                             fill="#FFFFFF")
        else:
            self.create_text(self.largura / 2, self.altura / 2, text=self.texto, font=self._f, fill="#FFFFFF")


class PDFViewerFrame(tk.Frame):
    # (ferramenta, rótulo, ícone, tecla de atalho)
    FERRAMENTAS = (
        ("pan", "Selecionar", Icone.SELECIONAR, "V"),
        ("pin", "Comentar", Icone.COMENTAR, "C"),
        ("measure", "Medir", Icone.REGUA, "M"),
        ("calibrate", "Calibrar", Icone.CALIBRAR, "K"),
        ("desenho", "Desenhar", Icone.CANETA, "D"),
        ("forma", "Forma", Icone.FORMA, "F"),
        ("balao", "Balão", Icone.BALAO, "B"),
        ("texto", "Texto", Icone.TEXTO, "T"),
        ("edicao", "Apagar", Icone.BORRACHA, "E"),
    )

    def __init__(self, parent, app):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self.painel = None

        self.current_pdf_path = ""
        self.pdf_document = None
        self.current_page = 0
        self.zoom_level = 1.0
        self.current_image = None

        self.current_tool = "pan"
        self.base_scale_factor = 1.0
        self.measure_start_cx = None
        self.measure_start_cy = None
        self.temp_line = None
        self.temp_text = None
        self.temp_bg = None
        self._updating_zoom = False

        # zoom com preview instantâneo (PIL) + re-renderização real debounced
        self._zoom_debounce_id = None
        self._pil_image_base = None
        self._zoom_base_level = None
        self._imagem_item = None
        self._largura_preview_atual = None
        self._altura_preview_atual = None

        # marcações livres (desenho/forma/balão/texto/selo), persistidas
        # separadamente das issues
        self.anotacoes = carregar_anotacoes()
        self._stroke_item = None
        self._stroke_pdf = []
        self.cor_atual = LISTA_CORES_ANOTACAO[0]
        self.espessura_atual = 3
        self.forma_atual = "retangulo"
        self.fonte_tamanho_atual = 16
        self.tamanho_selo_atual = 130.0
        self._selo_para_colocar = None
        self._selo_photo_refs = {}
        self._movendo_selo = None  # arrastando o selo com "Selecionar"

        # comentários: local marcado na prancha à espera do texto, e o
        # problema em destaque (pino + cartão)
        self.local_pendente = None  # (página, pdf_x, pdf_y)
        self.issue_selecionada_id = None
        self.painel_visivel = True
        self.modo_leitura = False
        self.rolagem_continua = bool(preferencias.carregar().get("rolagem_entre_paginas", True))
        self._insistencia_borda = 0
        self._issue_copiando = None
        self._fotos = {}

        self._montar_cabecalho()
        self._montar_barra_ferramentas()
        self._montar_barra_propriedades()
        self._montar_corpo()
        self.set_tool("pan")
        self._atualizar_cabecalho()
        self.painel.atualizar_lista()
        atalhos = {tecla.lower(): (lambda k=chave: self.set_tool(k)) for chave, _t, _i, tecla in self.FERRAMENTAS}
        atalhos.update({
            "Escape": self._cancelar_modo, "plus": self.zoom_in_btn, "equal": self.zoom_in_btn,
            "KP_Add": self.zoom_in_btn, "minus": self.zoom_out_btn, "KP_Subtract": self.zoom_out_btn,
            "0": self.ajustar_a_tela, "Next": self.next_page, "Prior": self.prev_page,
            "l": self.alternar_modo_leitura, "F11": self.alternar_tela_cheia,
        })
        instalar_atalhos(self, atalhos)

    # ---------- cabeçalho ----------
    def _montar_cabecalho(self):
        bg = cor_cabecalho()
        self.cabecalho = tk.Frame(self, bg=bg, height=64)
        self.cabecalho.pack(side=tk.TOP, fill=tk.X)
        self.cabecalho.pack_propagate(False)

        esquerda = tk.Frame(self.cabecalho, bg=bg)
        esquerda.pack(side=tk.LEFT, padx=(14, 0), fill=tk.Y)
        _BotaoCabecalho(esquerda, icone=Icone.VOLTAR, contorno=False, largura=36,
                        comando=lambda e: self.app.abrir_tela_projetos_pdf()).pack(side=tk.LEFT, pady=15)
        self._img_marca = imagem_marca(32, self, cor_fundo="#FFFFFF", cor_logo=TEMA["primario"]
                                       if not TEMA.esta_escuro() else "#14495D")
        tk.Label(esquerda, image=self._img_marca, bg=bg).pack(side=tk.LEFT, padx=(14, 14))
        textos = tk.Frame(esquerda, bg=bg)
        textos.pack(side=tk.LEFT, pady=12)
        linha = tk.Frame(textos, bg=bg)
        linha.pack(anchor="w")
        self.lbl_projeto = tk.Label(linha, text="", bg=bg, fg="#FFFFFF", font=fonte(11, "semi"))
        self.lbl_projeto.pack(side=tk.LEFT)
        self.caixa_status = tk.Frame(linha, bg=bg)
        self.caixa_status.pack(side=tk.LEFT, padx=(10, 0))
        self.lbl_arquivo = tk.Label(textos, text="", bg=bg, fg="#9DB9C3", font=fonte(9))
        self.lbl_arquivo.pack(anchor="w")

        centro = tk.Frame(self.cabecalho, bg=bg)
        centro.place(relx=0.5, rely=0.5, anchor="center")
        _BotaoCabecalho(centro, icone=Icone.CHEVRON_ESQUERDA, largura=28, altura=28,
                        comando=lambda e: self.prev_page()).pack(side=tk.LEFT)
        self.lbl_page = tk.Label(centro, text="— / —", bg=bg, fg="#FFFFFF", font=fonte(11, "semi"), width=9)
        self.lbl_page.pack(side=tk.LEFT, padx=6)
        _BotaoCabecalho(centro, icone=Icone.CHEVRON_DIREITA, largura=28, altura=28,
                        comando=lambda e: self.next_page()).pack(side=tk.LEFT)

        direita = tk.Frame(self.cabecalho, bg=bg)
        direita.pack(side=tk.RIGHT, padx=(0, 16))
        nome = (self.app.usuario_atual or {}).get("nome", "")
        avatar = Avatar(direita, nome, tamanho=38, cor=TEMA["acento"], cor_texto="#13343D", tamanho_fonte=9)
        avatar.pack(side=tk.RIGHT, padx=(14, 0), pady=13)
        avatar.configure(cursor="hand2")
        avatar.bind("<Button-1>", self._menu_usuario)
        _BotaoCabecalho(direita, texto="Baixar", icone=Icone.BAIXAR, comando=lambda e: self.exportar_pdf()
                        ).pack(side=tk.RIGHT, padx=(8, 0))
        _BotaoCabecalho(direita, texto="Abrir PDF", icone=Icone.PASTA, comando=lambda e: self.open_pdf()
                        ).pack(side=tk.RIGHT, padx=(8, 0))
        glifo = Icone.SOL if TEMA.esta_escuro() else Icone.OLHO if TEMA.eh_daltonico() else Icone.LUA
        _BotaoCabecalho(direita, icone=glifo, contorno=False, largura=36, comando=self.app.abrir_menu_tema
                        ).pack(side=tk.RIGHT)

    def _menu_usuario(self, evento):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        menu.add_command(label="Abrir outro PDF…", command=self.open_pdf)
        menu.add_command(label="Importar BCF…", command=self.importar_bcf_local)
        menu.add_command(label="Sincronizar com a rede", command=self.app.sincronizar_banco)
        menu.add_command(label="Obra / disciplina da sessão…", command=self.app.abrir_dialogo_sessao)
        menu.add_separator()
        menu.add_command(label="Voltar para Meus projetos", command=self.app.abrir_tela_projetos_pdf)
        menu.tk_popup(evento.x_root - 200, evento.y_root + 20)

    def _obra_do_documento(self):
        obras = [i.get("obra") for i in self.app.issues
                 if i.get("filepath") == self.current_pdf_path and i.get("obra")]
        if obras:
            return max(set(obras), key=obras.count)
        return self.app.sessao.get("obra") or ""

    def _atualizar_cabecalho(self):
        if self.pdf_document:
            obra = self._obra_do_documento() or "Prancha"
            disciplina = self.app.sessao.get("disciplina") or ""
            arquivo = os.path.basename(self.current_pdf_path)
            self.lbl_projeto.config(text=obra)
            self.lbl_arquivo.config(text=" · ".join(p for p in (disciplina, arquivo) if p))
            total = self.pdf_document.page_count
            self.lbl_page.config(text=f"{self.current_page + 1:02d} / {total:02d}")
        else:
            self.lbl_projeto.config(text=self.app.sessao.get("obra") or "Validação de pranchas")
            self.lbl_arquivo.config(text="Nenhum PDF aberto")
            self.lbl_page.config(text="— / —")
        for w in self.caixa_status.winfo_children():
            w.destroy()
        responsavel = self.app.sessao.get("atribuido_para")
        if responsavel:
            chip = Pilula(self.caixa_status, f"Para: {responsavel}", cores=("#1F5A70", "#FFFFFF"), altura=22,
                          tamanho_fonte=8, icone=Icone.EDITAR)
            chip.pack(side=tk.LEFT, padx=(0, 6))
            chip.configure(cursor="hand2")
            chip.bind("<Button-1>", lambda e: self.painel.editar_atribuicao() if self.painel else None)
        status = status_certificacao(self.anotacoes, self.current_pdf_path) if self.pdf_document else None
        if status:
            Pilula(self.caixa_status, f"{status['codigo']} · {status['descricao']}",
                   cores=(tom_claro(status["cor"], 0.8), status["cor"]), altura=22, tamanho_fonte=8,
                   icone=Icone.SELO).pack(side=tk.LEFT)

    def ao_mudar_sessao(self):
        self._atualizar_cabecalho()

    # ---------- barra de ferramentas ----------
    def _montar_barra_ferramentas(self):
        barra = tk.Frame(self, bg=TEMA["card"])
        barra.pack(side=tk.TOP, fill=tk.X)
        self._barra_ferramentas = barra
        self._linha_barra = tk.Frame(self, bg=TEMA["card_borda"], height=1)
        self._linha_barra.pack(side=tk.TOP, fill=tk.X)
        linha = tk.Frame(barra, bg=TEMA["card"])
        linha.pack(fill=tk.X, padx=20, pady=10)

        self.botoes_ferramenta = {}
        for chave, texto, glifo, tecla in self.FERRAMENTAS:
            b = Botao(linha, texto, variante="fantasma", icone=glifo, altura=34, tamanho_fonte=10, negrito=False,
                      comando=lambda k=chave: self.set_tool(k))
            b.pack(side=tk.LEFT, padx=(0, 4))
            Dica(b, f"{texto}  ·  atalho {tecla}")
            self.botoes_ferramenta[chave] = b
        tk.Frame(linha, bg=TEMA["card_borda"], width=1, height=22).pack(side=tk.LEFT, padx=10)
        Botao(linha, "Limpar página", variante="fantasma", icone=Icone.LIXEIRA, altura=34, tamanho_fonte=10,
              negrito=False, comando=self.limpar_anotacoes_pagina).pack(side=tk.LEFT)

        direita = tk.Frame(linha, bg=TEMA["card"])
        direita.pack(side=tk.RIGHT)
        self.btn_painel = Botao(direita, "", variante="secundario", icone=Icone.PAINEL, largura=34, altura=34,
                                comando=self.alternar_painel)
        zoom = tk.Frame(direita, bg=TEMA["card"], highlightthickness=1, highlightbackground=TEMA["card_borda"])
        zoom.pack(side=tk.RIGHT)
        Botao(zoom, "−", variante="fantasma", largura=30, altura=30, raio=6, comando=self.zoom_out_btn
              ).pack(side=tk.LEFT, padx=2, pady=2)
        self.lbl_zoom_pct = tk.Label(zoom, text="100%", bg=TEMA["card"], fg=TEMA["titulo"], font=fonte(10), width=6)
        self.lbl_zoom_pct.pack(side=tk.LEFT)
        Botao(zoom, "+", variante="fantasma", largura=30, altura=30, raio=6, comando=self.zoom_in_btn
              ).pack(side=tk.LEFT, padx=2, pady=2)
        Botao(direita, "Ajustar", variante="link", altura=30, tamanho_fonte=9, comando=self.ajustar_a_tela
              ).pack(side=tk.RIGHT, padx=(0, 12))
        self.btn_exibir = Botao(direita, "Exibir", variante="fantasma", icone=Icone.DOCUMENTO,
                                icone_direita=Icone.CHEVRON_BAIXO, altura=32, tamanho_fonte=9, negrito=False,
                                comando=self._menu_exibir)
        self.btn_exibir.pack(side=tk.RIGHT, padx=(0, 8))

    def _montar_barra_propriedades(self):
        """Opções da ferramenta de marcação ativa (cor, espessura, forma,
        tamanho da fonte). Só aparece para as ferramentas que têm opções."""
        bg = TEMA["campo"]
        self.props_bar = tk.Frame(self, bg=bg)
        self._props_linha = tk.Frame(self.props_bar, bg=bg)
        self._props_linha.pack(fill=tk.X, padx=24, pady=6)

        self.frame_cor = tk.Frame(self._props_linha, bg=bg)
        tk.Label(self.frame_cor, text="Cor", bg=bg, fg=TEMA["texto"], font=fonte(9)).pack(side=tk.LEFT, padx=(0, 8))
        self._amostras = {}
        for cor in LISTA_CORES_ANOTACAO:
            amostra = tk.Canvas(self.frame_cor, width=22, height=22, bg=bg, highlightthickness=0, cursor="hand2")
            amostra.pack(side=tk.LEFT, padx=1)
            amostra.bind("<Button-1>", lambda e, c=cor: self._definir_cor(c))
            self._amostras[cor] = amostra
        Botao(self.frame_cor, "Outra…", variante="link", altura=22, tamanho_fonte=9,
              comando=self._abrir_seletor_cor).pack(side=tk.LEFT, padx=(8, 18))
        self._desenhar_amostras()

        self.frame_espessura = tk.Frame(self._props_linha, bg=bg)
        tk.Label(self.frame_espessura, text="Espessura", bg=bg, fg=TEMA["texto"], font=fonte(9)).pack(
            side=tk.LEFT, padx=(0, 8))
        self.espessura_slider = ttk.Scale(self.frame_espessura, from_=1, to=14, orient=tk.HORIZONTAL,
                                          command=self._on_espessura_slider, length=110)
        self.espessura_slider.set(self.espessura_atual)
        self.espessura_slider.pack(side=tk.LEFT, padx=(0, 18))

        self.frame_forma_tipo = tk.Frame(self._props_linha, bg=bg)
        tk.Label(self.frame_forma_tipo, text="Forma", bg=bg, fg=TEMA["texto"], font=fonte(9)).pack(
            side=tk.LEFT, padx=(0, 8))
        self.botoes_forma = {}
        for chave, simbolo in (("retangulo", "▭"), ("circulo", "◯"), ("triangulo", "△"), ("seta", "➚")):
            b = Botao(self.frame_forma_tipo, simbolo, variante="fantasma", largura=32, altura=28, raio=6,
                      comando=lambda k=chave: self._definir_forma(k))
            b.pack(side=tk.LEFT, padx=1)
            self.botoes_forma[chave] = b
        self._atualizar_botoes_forma()

        self.frame_fonte = tk.Frame(self._props_linha, bg=bg)
        tk.Label(self.frame_fonte, text="Tamanho da fonte", bg=bg, fg=TEMA["texto"], font=fonte(9)).pack(
            side=tk.LEFT, padx=(0, 8))
        self.fonte_spin = tk.Spinbox(self.frame_fonte, from_=8, to=64, width=4, command=self._on_fonte_spin,
                                     bg=TEMA["card"], fg=TEMA["titulo"], relief="flat", font=fonte(9),
                                     buttonbackground=TEMA["card"])
        self.fonte_spin.delete(0, tk.END)
        self.fonte_spin.insert(0, str(self.fonte_tamanho_atual))
        self.fonte_spin.bind("<Return>", lambda e: self._on_fonte_spin())
        self.fonte_spin.bind("<FocusOut>", lambda e: self._on_fonte_spin())
        self.fonte_spin.pack(side=tk.LEFT)

        self.frame_copia = tk.Frame(self._props_linha, bg=bg)
        icone_copia = tk.Label(self.frame_copia, text=Icone.COMENTAR, bg=bg, fg=TEMA["titulo"],
                               font=(FONTE_ICONE, 10))
        icone_copia.pack(side=tk.LEFT, padx=(0, 8))
        self.lbl_copia = tk.Label(self.frame_copia, text="", bg=bg, fg=TEMA["titulo"], font=fonte(9))
        self.lbl_copia.pack(side=tk.LEFT)
        Botao(self.frame_copia, "Terminar", variante="link", altura=22, tamanho_fonte=9,
              comando=lambda: self.set_tool("pan")).pack(side=tk.LEFT, padx=(10, 0))

        self.frame_tamanho_selo = tk.Frame(self._props_linha, bg=bg)
        tk.Label(self.frame_tamanho_selo, text="Clique na prancha para carimbar o selo  ·  Tamanho", bg=bg,
                 fg=TEMA["texto"], font=fonte(9)).pack(side=tk.LEFT, padx=(0, 8))
        self.selo_tamanho_slider = ttk.Scale(self.frame_tamanho_selo, from_=40, to=400, orient=tk.HORIZONTAL,
                                             command=self._on_tamanho_selo_slider, length=120)
        self.lbl_tamanho_selo = tk.Label(self.frame_tamanho_selo, text=f"{int(self.tamanho_selo_atual)} pt",
                                         bg=bg, fg=TEMA["titulo"], width=7, font=fonte(9))
        self.selo_tamanho_slider.set(self.tamanho_selo_atual)
        self.selo_tamanho_slider.pack(side=tk.LEFT)
        self.lbl_tamanho_selo.pack(side=tk.LEFT, padx=(4, 8))
        Botao(self.frame_tamanho_selo, "Cancelar", variante="link", altura=22, tamanho_fonte=9,
              comando=lambda: self.set_tool("pan")).pack(side=tk.LEFT)

    def _desenhar_amostras(self):
        for cor, amostra in self._amostras.items():
            amostra.delete("all")
            if cor == self.cor_atual:
                amostra.create_oval(1, 1, 21, 21, outline=TEMA["primario"], width=2)
            amostra.create_oval(5, 5, 17, 17, fill=cor, outline=TEMA["card_borda"])

    def _definir_cor(self, cor):
        self.cor_atual = cor
        self._desenhar_amostras()

    def _definir_forma(self, chave):
        self.forma_atual = chave
        self._atualizar_botoes_forma()

    def _atualizar_botoes_forma(self):
        for chave, b in self.botoes_forma.items():
            b.definir_variante("ativo" if chave == self.forma_atual else "fantasma")

    def _on_tamanho_selo_slider(self, val):
        self.tamanho_selo_atual = max(20, float(val))
        self.lbl_tamanho_selo.config(text=f"{int(self.tamanho_selo_atual)} pt")

    def _atualizar_barra_propriedades(self, tool_name):
        mapa = {
            "desenho": (self.frame_cor, self.frame_espessura),
            "forma": (self.frame_cor, self.frame_espessura, self.frame_forma_tipo),
            "balao": (self.frame_cor, self.frame_espessura),
            "texto": (self.frame_cor, self.frame_fonte),
            "selo_colocar": (self.frame_tamanho_selo,),
            "copiar": (self.frame_copia,),
        }
        for f in (self.frame_cor, self.frame_espessura, self.frame_forma_tipo, self.frame_fonte,
                  self.frame_tamanho_selo, self.frame_copia):
            f.pack_forget()
        frames = mapa.get(tool_name, ())
        for f in frames:
            f.pack(side=tk.LEFT)
        if frames and not self.props_bar.winfo_manager():
            self.props_bar.pack(side=tk.TOP, fill=tk.X, before=self.corpo)
        elif not frames and self.props_bar.winfo_manager():
            self.props_bar.pack_forget()
        if tool_name == "selo_colocar":
            self.selo_tamanho_slider.set(self.tamanho_selo_atual)

    # ---------- corpo: prancha + painel ----------
    def _montar_corpo(self):
        self.corpo = tk.Frame(self, bg=TEMA["pagina"])
        self.corpo.pack(fill=tk.BOTH, expand=True)

        self.painel_frame = tk.Frame(self.corpo, bg=TEMA["card"], width=LARGURA_PAINEL)
        self.painel_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.painel_frame.pack_propagate(False)
        tk.Frame(self.corpo, bg=TEMA["card_borda"], width=1).pack(side=tk.RIGHT, fill=tk.Y)
        self._divisoria_painel = self.corpo.winfo_children()[-1]

        canvas_frame = tk.Frame(self.corpo, bg=TEMA["pagina"])
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, style="Fino.Vertical.TScrollbar")
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, style="Fino.Horizontal.TScrollbar")
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas = tk.Canvas(canvas_frame, bg=TEMA["pagina"], cursor="arrow", highlightthickness=0,
                                xscrollcommand=hbar.set, yscrollcommand=vbar.set,
                                yscrollincrement=1, xscrollincrement=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        vbar.config(command=self.canvas.yview)
        hbar.config(command=self.canvas.xview)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Control-MouseWheel>", self.zoom_com_mouse)
        self.canvas.bind("<Control-Button-4>", self.zoom_com_mouse)
        self.canvas.bind("<Control-Button-5>", self.zoom_com_mouse)
        self.canvas.bind("<MouseWheel>", self.rolar_vertical)
        self.canvas.bind("<Shift-MouseWheel>", self.rolar_horizontal)
        self.canvas.bind("<Button-4>", self.rolar_vertical)
        self.canvas.bind("<Button-5>", self.rolar_vertical)
        self.canvas.bind("<Shift-Button-4>", self.rolar_horizontal)
        self.canvas.bind("<Shift-Button-5>", self.rolar_horizontal)
        self.canvas.bind("<Configure>", lambda e: self._atualizar_regiao())
        self.canvas.bind("<Escape>", lambda e: self._cancelar_modo())

        self.painel = PainelComentarios(self.painel_frame, self)
        self.painel.pack(fill=tk.BOTH, expand=True)
        self._estado_vazio()

    def _estado_vazio(self):
        """Sem PDF aberto: convite centralizado para abrir uma prancha."""
        self.canvas.delete("vazio")
        if self.pdf_document:
            if getattr(self, "_botao_vazio", None) is not None:
                self._botao_vazio.destroy()
                self._botao_vazio = None
            return
        w, h = max(self.canvas.winfo_width(), 400), max(self.canvas.winfo_height(), 300)
        self.canvas.configure(scrollregion=(0, 0, w, h))
        self.canvas.create_text(w / 2, h / 2 - 50, text=Icone.DOCUMENTO, font=(FONTE_ICONE, 30),
                                fill=TEMA["texto_fraco"], tags=("vazio",))
        self.canvas.create_text(w / 2, h / 2, text="Nenhuma prancha aberta", font=fonte(14, "semi"),
                                fill=TEMA["titulo"], tags=("vazio",))
        self.canvas.create_text(w / 2, h / 2 + 26, text="Abra um PDF para marcar comentários, medir e certificar.",
                                font=fonte(10), fill=TEMA["texto_fraco"], tags=("vazio",))
        if getattr(self, "_botao_vazio", None) is None:
            self._botao_vazio = Botao(self.canvas, "Abrir PDF", variante="primario", icone=Icone.PASTA,
                                      altura=38, comando=self.open_pdf)
        self.canvas.create_window(w / 2, h / 2 + 76, window=self._botao_vazio, tags=("vazio",))

    def alternar_painel(self):
        if self.painel_visivel:
            self.ocultar_painel()
        else:
            self.painel_visivel = True
            self.btn_painel.pack_forget()
            self._divisoria_painel.pack(side=tk.RIGHT, fill=tk.Y, before=self.canvas.master)
            self.painel_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self._divisoria_painel)

    def ocultar_painel(self):
        self.painel_visivel = False
        self.painel_frame.pack_forget()
        self._divisoria_painel.pack_forget()
        self.btn_painel.pack(side=tk.RIGHT, padx=(12, 0))

    # ---------- ferramentas e eventos de mouse ----------
    def set_tool(self, tool_name):
        self.current_tool = tool_name
        destaque = {"selo_colocar": "pan", "copiar": "pin"}.get(tool_name, tool_name)
        for chave, b in self.botoes_ferramenta.items():
            b.definir_variante("ativo" if chave == destaque else "fantasma")
        cursores = {"pan": "fleur", "pin": "crosshair", "measure": "tcross", "calibrate": "pencil",
                    "desenho": "pencil", "forma": "crosshair", "balao": "crosshair", "texto": "xterm",
                    "selo_colocar": "plus", "edicao": "X_cursor", "copiar": "plus"}
        self.canvas.config(cursor=cursores.get(tool_name, "arrow"))
        if tool_name not in ("measure", "calibrate"):
            self._limpar_medicao()
        if tool_name != "pin" and self.local_pendente:
            self.local_pendente = None
            self.draw_pins()
            if self.painel:
                self.painel._atualizar_dica()
        self._atualizar_barra_propriedades(tool_name)
        self.canvas.focus_set()

    def _cancelar_modo(self):
        if self._limpar_medicao():
            return
        if self.winfo_toplevel().attributes("-fullscreen"):
            self.alternar_tela_cheia()
            return
        if self.modo_leitura:
            self.alternar_modo_leitura()
            return
        if self.local_pendente or self.current_tool != "pan":
            self.set_tool("pan")

    # ---------- medição: a linha fica até ser apagada (✕, Esc ou outra ferramenta) ----------
    def _limpar_medicao(self):
        itens = [i for i in (self.temp_line, self.temp_text, self.temp_bg) if i]
        if not itens and not self.canvas.find_withtag("medida"):
            return False
        for item in itens:
            self.canvas.delete(item)
        self.canvas.delete("medida")
        self.temp_line = self.temp_text = self.temp_bg = None
        return True

    def _botao_apagar_medicao(self):
        """✕ no canto do rótulo da medida para apagá-la."""
        self.canvas.delete("medida")
        if not self.temp_bg:
            return
        x0, y0, x1, y1 = self.canvas.coords(self.temp_bg)
        r = 8
        self.canvas.create_oval(x1 - r, y0 - r, x1 + r, y0 + r, fill="#FFFFFF", outline=TEMA["primario"],
                                width=1.5, tags=("medida", "medida_fechar", "marcacao"))
        self.canvas.create_text(x1, y0, text="✕", font=("Segoe UI", 7, "bold"), fill=TEMA["primario"],
                                tags=("medida", "medida_fechar", "marcacao"))

    def _clicou_em(self, cx, cy, tag):
        for item in self.canvas.find_overlapping(cx - 2, cy - 2, cx + 2, cy + 2):
            if tag in self.canvas.gettags(item):
                return True
        return False

    # ---------- menu "Exibir" (modos de ajuste e leitura) ----------
    def _menu_exibir(self):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        menu.add_command(label="✓  Exibição em uma página")
        menu.add_command(label="     Exibição em duas páginas (em breve)", state="disabled")
        menu.add_command(label=("✓  " if self.rolagem_continua else "     ") + "Habilitar rolagem entre páginas",
                         command=self._alternar_rolagem)
        menu.add_separator()
        menu.add_command(label="     Tamanho real", command=self.tamanho_real)
        menu.add_command(label="     Ampliar para o nível de página    0", command=self.ajustar_a_tela)
        menu.add_command(label="     Ajustar à largura", command=lambda: self._ajustar("largura"))
        menu.add_command(label="     Ajustar à altura", command=lambda: self._ajustar("altura"))
        menu.add_command(label="     Ajustar conteúdo visível", command=self.ajustar_conteudo_visivel)
        menu.add_separator()
        menu.add_command(label=("✓  " if self.modo_leitura else "     ") + "Modo de leitura    L",
                         command=self.alternar_modo_leitura)
        tela_cheia = self.winfo_toplevel().attributes("-fullscreen")
        menu.add_command(label=("✓  " if tela_cheia else "     ") + "Modo de tela cheia    F11",
                         command=self.alternar_tela_cheia)
        b = self.btn_exibir
        menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 4)

    def _alternar_rolagem(self):
        self.rolagem_continua = not self.rolagem_continua
        preferencias.salvar(rolagem_entre_paginas=self.rolagem_continua)

    # ---------- copiar issue para outros locais ----------
    def iniciar_copia(self, issue):
        """Mesmo comentário em vários pontos da verificação (ex.: um ajuste
        que o projetista pode esquecer em várias partes): cada clique na
        prancha — em qualquer página — cria uma cópia. Esc termina."""
        self._issue_copiando = issue
        self.set_tool("copiar")
        self.lbl_copia.config(text=f"Copiando #{issue['id']} · {issue.get('titulo', '')[:40]} — clique nos locais "
                                   "da prancha (pode trocar de página). Esc termina.")

    def _colar_copia(self, cx, cy):
        original = self._issue_copiando
        if not original or not (0 <= cx <= (self._largura_preview_atual or 0)
                                and 0 <= cy <= (self._altura_preview_atual or 0)):
            return
        agora = agora_str()
        copia = {k: original.get(k) for k in ("titulo", "tipo", "obra", "disciplina", "atribuido_para", "desc")}
        copia.update({
            "id": proximo_id(self.app.issues), "status": "Novo",
            "criado_por": self.app.sessao.get("nome") or original.get("criado_por"),
            "historico": [{"data": agora[:16], "texto": f"Copiado do problema #{original['id']}.",
                           "autor": self.app.sessao.get("nome", "")}],
            "data_criacao": agora, "data_modificacao": agora, "tipo_doc": "pdf",
            "page": self.current_page, "filepath": self.current_pdf_path,
            "pdf_x": cx / self.zoom_level, "pdf_y": cy / self.zoom_level,
        })
        self.app.issues.append(copia)
        self.app.salvar_banco_dados()
        self.draw_pins()
        if self.painel:
            self.painel.atualizar_lista()

    def _area_util(self):
        self.update_idletasks()
        return (max(200, self.canvas.winfo_width() - 2 * MARGEM_PRANCHA),
                max(200, self.canvas.winfo_height() - 2 * MARGEM_PRANCHA))

    def _ajustar(self, modo):
        if not self.pdf_document:
            return
        pagina = self.pdf_document.load_page(self.current_page)
        largura, altura = self._area_util()
        zoom = largura / pagina.rect.width if modo == "largura" else altura / pagina.rect.height
        self.zoom_level = max(ZOOM_MINIMO, min(ZOOM_MAXIMO, zoom))
        self.render_page()
        self.canvas.yview_moveto(0)

    def tamanho_real(self):
        if not self.pdf_document:
            return
        self.zoom_level = max(ZOOM_MINIMO, min(ZOOM_MAXIMO, self.winfo_fpixels("1i") / 72.0))
        self.render_page()

    def ajustar_conteudo_visivel(self):
        """Enquadra só a área desenhada da folha (ignora margens em branco)."""
        if not self.pdf_document:
            return
        pagina = self.pdf_document.load_page(self.current_page)
        area_pagina = abs(pagina.rect)
        caixa = fitz.Rect()
        try:
            for _tipo, retangulo in pagina.get_bboxlog():
                r = fitz.Rect(retangulo) * pagina.rotation_matrix
                if r.is_empty or abs(r) > 0.95 * area_pagina:
                    continue  # fundo branco da página inteira
                caixa |= r
        except Exception:
            caixa = fitz.Rect()
        caixa &= pagina.rect
        if caixa.is_empty:
            self.ajustar_a_tela()
            return
        largura, altura = self._area_util()
        self.zoom_level = max(ZOOM_MINIMO, min(ZOOM_MAXIMO, min(largura / caixa.width, altura / caixa.height)))
        self.render_page()
        self.update_idletasks()
        x0, y0, x1, y1 = (float(v) for v in str(self.canvas.cget("scrollregion")).split())
        if x1 - x0 > 0:
            self.canvas.xview_moveto(max(0.0, (caixa.x0 * self.zoom_level - x0 - 10) / (x1 - x0)))
        if y1 - y0 > 0:
            self.canvas.yview_moveto(max(0.0, (caixa.y0 * self.zoom_level - y0 - 10) / (y1 - y0)))

    def alternar_modo_leitura(self):
        """Só a prancha: esconde a barra de ferramentas e o painel lateral."""
        self.modo_leitura = not self.modo_leitura
        if self.modo_leitura:
            self.set_tool("pan")
            self._barra_ferramentas.pack_forget()
            self._linha_barra.pack_forget()
            self.props_bar.pack_forget()
            if self.painel_visivel:
                self.ocultar_painel()
        else:
            self._barra_ferramentas.pack(side=tk.TOP, fill=tk.X, before=self.corpo)
            self._linha_barra.pack(side=tk.TOP, fill=tk.X, before=self.corpo)
            if not self.painel_visivel:
                self.alternar_painel()
        self.after(50, self._atualizar_regiao)

    def alternar_tela_cheia(self):
        janela = self.winfo_toplevel()
        janela.attributes("-fullscreen", not janela.attributes("-fullscreen"))
        self.after(100, self._atualizar_regiao)

    def iniciar_colocacao_selo(self, caminho):
        self._selo_para_colocar = caminho
        self.set_tool("selo_colocar")

    def on_press(self, event):
        if not self.pdf_document:
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self._clicou_em(cx, cy, "medida_fechar"):
            self._limpar_medicao()
            self.measure_start_cx = None
            return

        if self.current_tool not in ("desenho", "forma", "balao", "texto", "selo_colocar"):
            issue_existente = self._pin_issue_sob_cursor(cx, cy)
            if issue_existente is not None:
                self.selecionar_issue(issue_existente)
                return

        if self.current_tool == "copiar":
            self._colar_copia(cx, cy)
            return

        if self.current_tool == "pan":
            issue_existente = self._pin_issue_sob_cursor(cx, cy)
            if issue_existente is not None:
                self.selecionar_issue(issue_existente)
                return
            selo = self._selo_sob_cursor(cx, cy)
            if selo is not None:  # arrastar o selo para outro lugar
                self._movendo_selo = {"id": selo["id"], "inicio": (cx, cy), "ultimo": (cx, cy)}
                self.canvas.config(cursor="fleur")
                return
            self.canvas.scan_mark(event.x, event.y)
            self._arrastando = True
            return

        if self.current_tool == "pin":
            issue_existente = self._pin_issue_sob_cursor(cx, cy)
            if issue_existente is not None:
                self.selecionar_issue(issue_existente)
                return
            if not (0 <= cx <= (self._largura_preview_atual or 0) and 0 <= cy <= (self._altura_preview_atual or 0)):
                return  # fora da prancha
            self.local_pendente = (self.current_page, cx / self.zoom_level, cy / self.zoom_level)
            self.draw_pins()
            if self.painel:
                if not self.painel_visivel:
                    self.alternar_painel()
                self.painel.marcar_local_pendente()

        elif self.current_tool in ("measure", "calibrate"):
            self._limpar_medicao()
            self.measure_start_cx = cx
            self.measure_start_cy = cy

        elif self.current_tool == "desenho":
            self._stroke_pdf = [(cx / self.zoom_level, cy / self.zoom_level)]
            self._stroke_item = self.canvas.create_line(
                cx, cy, cx, cy, fill=self.cor_atual, width=self.espessura_atual, smooth=True,
                tags=("anot", "marcacao")
            )

        elif self.current_tool == "forma":
            self.measure_start_cx = cx
            self.measure_start_cy = cy
            self._stroke_item = self._criar_item_forma(
                self.forma_atual, cx, cy, cx, cy, self.cor_atual, self.espessura_atual, ("anot", "marcacao")
            )

        elif self.current_tool == "balao":
            self.measure_start_cx = cx
            self.measure_start_cy = cy
            self._stroke_item = self.canvas.create_rectangle(
                cx, cy, cx, cy, outline=self.cor_atual, width=self.espessura_atual, dash=(4, 2)
            )

        elif self.current_tool == "texto":
            dialogo = DialogTextoLivre(self.winfo_toplevel(), titulo="Caixa de Texto")
            if not dialogo.texto:
                return
            nova = {
                "id": proximo_id(self.anotacoes),
                "filepath": self.current_pdf_path,
                "page": self.current_page,
                "tipo": "texto",
                "pontos": [[cx / self.zoom_level, cy / self.zoom_level]],
                "cor": self.cor_atual,
                "fonte_tamanho": self.fonte_tamanho_atual,
                "texto": dialogo.texto,
                "autor": self.app.sessao.get("nome", ""),
                "data": agora_str(),
            }
            self.anotacoes.append(nova)
            salvar_anotacoes(self.anotacoes)
            self._desenhar_texto(nova)

        elif self.current_tool == "selo_colocar":
            self._colocar_selo(cx, cy)

        elif self.current_tool == "edicao":
            self._apagar_anotacao_em(cx, cy)

    # ---------- métodos de marcação, navegação e BCF (inalterados) ----------
    def _abrir_seletor_cor(self):
        cor = colorchooser.askcolor(color=self.cor_atual, parent=self.winfo_toplevel())[1]
        if cor:
            self._definir_cor(cor)

    def _on_espessura_slider(self, val):
        self.espessura_atual = max(1, int(float(val)))

    def _on_fonte_spin(self):
        try:
            self.fonte_tamanho_atual = max(6, int(self.fonte_spin.get()))
        except ValueError:
            pass

    def rolar_vertical(self, event):
        """Roda do mouse rola a prancha; com "rolagem entre páginas" ligada,
        insistir na borda (2 giros seguidos no fim/começo) vira a página."""
        if not self.pdf_document:
            return
        delta = event.delta if getattr(event, "delta", 0) else (120 if event.num == 4 else -120)
        topo, base = self.canvas.yview()
        if self.rolagem_continua:
            descendo = delta < 0
            na_borda = (descendo and base >= 0.999) or (not descendo and topo <= 0.001)
            if na_borda:
                self._insistencia_borda += 1
                if self._insistencia_borda >= 2:
                    self._insistencia_borda = 0
                    if descendo and self.current_page < self.pdf_document.page_count - 1:
                        self.next_page()
                        self.canvas.yview_moveto(0)
                    elif not descendo and self.current_page > 0:
                        self.prev_page()
                        self.canvas.yview_moveto(1)
                return
            self._insistencia_borda = 0
        self.canvas.yview_scroll(int(-1 * (delta / 120) * 60), "units")

    def rolar_horizontal(self, event):
        if not self.pdf_document:
            return
        delta = event.delta if getattr(event, "delta", 0) else (120 if event.num == 4 else -120)
        self.canvas.xview_scroll(int(-1 * (delta / 120) * 60), "units")

    def on_drag(self, event):
        if not self.pdf_document:
            return
        if self.current_tool == "pan" and self._movendo_selo:
            cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            ux, uy = self._movendo_selo["ultimo"]
            self.canvas.move(f"anot_{self._movendo_selo['id']}", cx - ux, cy - uy)
            self._movendo_selo["ultimo"] = (cx, cy)
            return
        if self.current_tool == "pan":
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self.current_tool in ("measure", "calibrate") and self.measure_start_cx is not None:
            for item in (self.temp_line, self.temp_text, self.temp_bg):
                if item:
                    self.canvas.delete(item)

            cor = "#00FFFF" if self.current_tool == "measure" else "#FF9800"
            self.temp_line = self.canvas.create_line(self.measure_start_cx, self.measure_start_cy, cx, cy,
                                                      fill=cor, width=3, dash=(4, 2))

            if self.current_tool == "measure":
                pdf_start_x = self.measure_start_cx / self.zoom_level
                pdf_start_y = self.measure_start_cy / self.zoom_level
                pdf_end_x = cx / self.zoom_level
                pdf_end_y = cy / self.zoom_level
                dist_pdf = math.hypot(pdf_end_x - pdf_start_x, pdf_end_y - pdf_start_y)
                real_dist = dist_pdf * self.base_scale_factor

                self.temp_bg = self.canvas.create_rectangle(cx + 10, cy - 35, cx + 100, cy - 5,
                                                              fill="#13343D", outline="#FFFFFF")
                self.temp_text = self.canvas.create_text(cx + 55, cy - 20, text=f"{real_dist:.2f}",
                                                           fill="#FFFFFF", font=("Segoe UI", 11, "bold"))

        elif self.current_tool == "desenho" and self._stroke_item is not None:
            self._stroke_pdf.append((cx / self.zoom_level, cy / self.zoom_level))
            coords_atuais = self.canvas.coords(self._stroke_item)
            coords_atuais.extend([cx, cy])
            self.canvas.coords(self._stroke_item, *coords_atuais)

        elif self.current_tool == "forma" and self._stroke_item is not None:
            self.canvas.delete(self._stroke_item)
            self._stroke_item = self._criar_item_forma(
                self.forma_atual, self.measure_start_cx, self.measure_start_cy, cx, cy,
                self.cor_atual, self.espessura_atual, ("anot", "marcacao")
            )

        elif self.current_tool == "balao" and self._stroke_item is not None:
            self.canvas.coords(self._stroke_item, self.measure_start_cx, self.measure_start_cy, cx, cy)

    def on_release(self, event):
        if not self.pdf_document:
            return
        if self._movendo_selo:
            self._soltar_selo()
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if self.current_tool == "desenho":
            self._finalizar_desenho()
            return
        if self.current_tool == "forma":
            self._finalizar_forma(cx, cy)
            return
        if self.current_tool == "balao":
            self._finalizar_balao(cx, cy)
            return
        if self.measure_start_cx is None:
            return

        if self.current_tool == "calibrate":
            pdf_start_x = self.measure_start_cx / self.zoom_level
            pdf_start_y = self.measure_start_cy / self.zoom_level
            pdf_end_x = cx / self.zoom_level
            pdf_end_y = cy / self.zoom_level
            dist_pdf = math.hypot(pdf_end_x - pdf_start_x, pdf_end_y - pdf_start_y)

            if dist_pdf > 1:
                real_dist = simpledialog.askfloat(
                    "Calibrar Régua", "Qual a distância real dessa linha? (Use ponto para decimais)",
                    parent=self.winfo_toplevel()
                )
                if real_dist and real_dist > 0:
                    self.base_scale_factor = real_dist / dist_pdf
                    messagebox.showinfo("Calibrado", "Régua calibrada com sucesso!")
            if self.temp_line:
                self.canvas.delete(self.temp_line)
        elif self.current_tool == "measure":
            self._botao_apagar_medicao()
        self.measure_start_cx = None

    def _criar_item_forma(self, subtipo, x1, y1, x2, y2, cor, espessura, tags):
        if subtipo == "circulo":
            return self.canvas.create_oval(x1, y1, x2, y2, outline=cor, width=espessura, tags=tags)
        if subtipo == "triangulo":
            xm = (x1 + x2) / 2
            return self.canvas.create_polygon(xm, y1, x2, y2, x1, y2, outline=cor, width=espessura,
                                               fill="", tags=tags)
        if subtipo == "seta":
            return self.canvas.create_line(x1, y1, x2, y2, fill=cor, width=espessura, arrow=tk.LAST,
                                            arrowshape=(16, 20, 6), tags=tags)
        return self.canvas.create_rectangle(x1, y1, x2, y2, outline=cor, width=espessura, tags=tags)

    def _pontos_balao(self, x1, y1, x2, y2):
        """Retângulo com um 'rabicho' apontando para o canto inferior-esquerdo,
        dando a aparência de um balão de nota/comentário."""
        r = min(14, abs(x2 - x1) / 4, abs(y2 - y1) / 4)
        return [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2,
            x1 + 18, y2, x1 + 8, y2 + 16, x1 + 14, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]

    def _finalizar_desenho(self):
        if self._stroke_item is None:
            return
        if len(self._stroke_pdf) > 1:
            nova = {
                "id": proximo_id(self.anotacoes),
                "filepath": self.current_pdf_path,
                "page": self.current_page,
                "tipo": "desenho",
                "pontos": self._stroke_pdf,
                "cor": self.cor_atual,
                "espessura": self.espessura_atual,
                "autor": self.app.sessao.get("nome", ""),
                "data": agora_str(),
            }
            self.anotacoes.append(nova)
            salvar_anotacoes(self.anotacoes)
            self.canvas.itemconfig(self._stroke_item, tags=("anot", "marcacao", f"anot_{nova['id']}"))
        else:
            self.canvas.delete(self._stroke_item)
        self._stroke_item = None
        self._stroke_pdf = []

    def _finalizar_forma(self, cx, cy):
        if self._stroke_item is None:
            return
        self.canvas.delete(self._stroke_item)
        self._stroke_item = None
        x1, y1 = self.measure_start_cx, self.measure_start_cy
        self.measure_start_cx = None
        self.measure_start_cy = None
        if x1 is None or (abs(cx - x1) < 3 and abs(cy - y1) < 3):
            return
        nova = {
            "id": proximo_id(self.anotacoes),
            "filepath": self.current_pdf_path,
            "page": self.current_page,
            "tipo": "forma",
            "forma": self.forma_atual,
            "pontos": [[x1 / self.zoom_level, y1 / self.zoom_level],
                       [cx / self.zoom_level, cy / self.zoom_level]],
            "cor": self.cor_atual,
            "espessura": self.espessura_atual,
            "autor": self.app.sessao.get("nome", ""),
            "data": agora_str(),
        }
        self.anotacoes.append(nova)
        salvar_anotacoes(self.anotacoes)
        self._criar_item_forma(self.forma_atual, x1, y1, cx, cy, self.cor_atual, self.espessura_atual,
                                ("anot", "marcacao", f"anot_{nova['id']}"))

    def _finalizar_balao(self, cx, cy):
        if self._stroke_item is None:
            return
        self.canvas.delete(self._stroke_item)
        self._stroke_item = None
        x1, y1 = self.measure_start_cx, self.measure_start_cy
        self.measure_start_cx = None
        self.measure_start_cy = None
        if x1 is None or abs(cx - x1) < 20 or abs(cy - y1) < 20:
            return

        dialogo = DialogTextoLivre(self.winfo_toplevel(), titulo="Nota do Balão")
        if not dialogo.texto:
            return

        x1, x2 = sorted((x1, cx))
        y1, y2 = sorted((y1, cy))
        nova = {
            "id": proximo_id(self.anotacoes),
            "filepath": self.current_pdf_path,
            "page": self.current_page,
            "tipo": "balao",
            "pontos": [[x1 / self.zoom_level, y1 / self.zoom_level],
                       [x2 / self.zoom_level, y2 / self.zoom_level]],
            "cor": self.cor_atual,
            "espessura": self.espessura_atual,
            "texto": dialogo.texto,
            "autor": self.app.sessao.get("nome", ""),
            "data": agora_str(),
        }
        self.anotacoes.append(nova)
        salvar_anotacoes(self.anotacoes)
        self._desenhar_balao(nova)

    def _desenhar_balao(self, a):
        (x1, y1), (x2, y2) = a["pontos"]
        x1, y1 = x1 * self.zoom_level, y1 * self.zoom_level
        x2, y2 = x2 * self.zoom_level, y2 * self.zoom_level
        tag_id = f"anot_{a['id']}"
        pontos = self._pontos_balao(x1, y1, x2, y2)
        self.canvas.create_polygon(*pontos, outline=a.get("cor", "#FF9800"), width=a.get("espessura", 3),
                                    fill="#FFF6D8", smooth=True, tags=("anot", "marcacao", tag_id))
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=a.get("texto", ""), fill="#222222",
                                 width=max(20, (x2 - x1) - 12), font=("Arial", 10), tags=("anot", "marcacao", tag_id))

    def _desenhar_texto(self, a):
        (px, py), = a["pontos"]
        x, y = px * self.zoom_level, py * self.zoom_level
        tamanho = max(6, round(a.get("fonte_tamanho", 16) * self.zoom_level))
        tag_id = f"anot_{a['id']}"
        self.canvas.create_text(x, y, text=a.get("texto", ""), fill=a.get("cor", "#000000"), anchor="nw",
                                 font=("Arial", tamanho, "bold"), tags=("anot", "marcacao", tag_id))

    def desenhar_anotacoes(self):
        self.canvas.delete("anot")
        if not self.pdf_document:
            return
        for a in self.anotacoes:
            if a.get("filepath") != self.current_pdf_path or a.get("page") != self.current_page:
                continue
            tipo = a.get("tipo")
            tag_id = f"anot_{a['id']}"
            if tipo == "desenho":
                pontos_canvas = []
                for px, py in a["pontos"]:
                    pontos_canvas.extend([px * self.zoom_level, py * self.zoom_level])
                self.canvas.create_line(*pontos_canvas, fill=a.get("cor", "#FF3B30"), width=a.get("espessura", 3),
                                         smooth=True, tags=("anot", "marcacao", tag_id))
            elif tipo == "revisao":  # legado: marcações antigas em retângulo simples
                (x1, y1), (x2, y2) = a["pontos"]
                self.canvas.create_rectangle(
                    x1 * self.zoom_level, y1 * self.zoom_level, x2 * self.zoom_level, y2 * self.zoom_level,
                    outline=a.get("cor", "#FF9800"), width=3, tags=("anot", "marcacao", tag_id)
                )
            elif tipo == "forma":
                (x1, y1), (x2, y2) = a["pontos"]
                self._criar_item_forma(
                    a.get("forma", "retangulo"), x1 * self.zoom_level, y1 * self.zoom_level,
                    x2 * self.zoom_level, y2 * self.zoom_level, a.get("cor", "#FF3B30"),
                    a.get("espessura", 3), ("anot", "marcacao", tag_id)
                )
            elif tipo == "balao":
                self._desenhar_balao(a)
            elif tipo == "texto":
                self._desenhar_texto(a)
            elif tipo == "selo" and estado_selo(a, self.anotacoes) == ATIVO:
                self._desenhar_selo(a)

    def limpar_anotacoes_pagina(self):
        if not self.pdf_document:
            return
        if not messagebox.askyesno(
            "Confirmar", "Remover todas as marcações desta página (desenhos, formas, balões, textos e selos)?"
        ):
            return
        da_pagina = [a for a in self.anotacoes
                     if a.get("filepath") == self.current_pdf_path and a.get("page") == self.current_page]
        havia_selo = False
        for a in da_pagina:
            if a.get("tipo") == "selo":  # selo nunca some do banco: vai para o histórico
                if estado_selo(a, self.anotacoes) == ATIVO:
                    remover_selo(self.anotacoes, a["id"], self.app.sessao.get("nome", ""), agora_str())
                    havia_selo = True
        removidas = {a["id"] for a in da_pagina if a.get("tipo") != "selo"}
        self.anotacoes = [a for a in self.anotacoes if a["id"] not in removidas]
        for rid in removidas:
            self._selo_photo_refs.pop(rid, None)
        salvar_anotacoes(self.anotacoes)
        self.desenhar_anotacoes()
        if havia_selo:
            self._ao_mudar_certificacao()

    def zoom_in_btn(self):
        if self.pdf_document:
            self._ajustar_zoom(self.zoom_level + 0.2)

    def zoom_out_btn(self):
        if self.pdf_document:
            self._ajustar_zoom(self.zoom_level - 0.2)

    def zoom_com_mouse(self, event):
        if not self.pdf_document:
            return
        if event.num == 4 or (getattr(event, "delta", 0) and event.delta > 0):
            self._ajustar_zoom(self.zoom_level + 0.2)
        else:
            self._ajustar_zoom(self.zoom_level - 0.2)

    def _commit_zoom_real(self):
        self._zoom_debounce_id = None
        self.render_page()

    def next_page(self):
        if self.pdf_document and self.current_page < self.pdf_document.page_count - 1:
            self._cancelar_marcacao_em_andamento()
            self.current_page += 1
            self.render_page()

    def prev_page(self):
        if self.pdf_document and self.current_page > 0:
            self._cancelar_marcacao_em_andamento()
            self.current_page -= 1
            self.render_page()

    def _cancelar_marcacao_em_andamento(self):
        self._stroke_item = None
        self._stroke_pdf = []
        self.measure_start_cx = None
        self.measure_start_cy = None

    def _pin_issue_sob_cursor(self, cx, cy):
        """Devolve o id da issue cujo pino está sob o clique (com uma margem
        de tolerância, já que a bolinha é pequena), ou None."""
        raio = 12
        for item in self.canvas.find_overlapping(cx - raio, cy - raio, cx + raio, cy + raio):
            for tag in self.canvas.gettags(item):
                if tag.startswith("issuepin_"):
                    return int(tag.split("_")[1])
        return None

    def importar_bcf_local(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("BCF Zip", "*.bcfzip"), ("Arquivos Zip", "*.zip"), ("Todos os arquivos", "*.*")]
        )
        if not filepath:
            return

        if not self.pdf_document:
            messagebox.showwarning("Atenção", "Por favor, abra um PDF primeiro para poder associar as issues do BCF à prancha atual.")
            return

        obra_dialog = DialogObraImportacao(self.winfo_toplevel(), lista_obras=self.app.obras_lista)
        if not obra_dialog.obra:
            return
        obra_lote = obra_dialog.obra

        try:
            issues_extraidas, relatorio = ler_issues_bcf(filepath, self.current_pdf_path, self.current_page)
            agora = agora_str()
            for dados in issues_extraidas:
                dados["id"] = max([i["id"] for i in self.app.issues], default=0) + 1
                dados["obra"] = obra_lote
                dados["tipo_doc"] = "pdf"
                dados["data_criacao"] = dados["data_criacao"] or agora
                dados["data_modificacao"] = dados["data_modificacao"] or agora
                self.app.issues.append(dados)

            self.app.salvar_banco_dados()
            if self.painel:
                self.painel.atualizar_lista()
            self.draw_pins()

            msg = (
                "Importação concluída.\n\n"
                f"✔ Importadas: {relatorio['importadas']}\n"
                f"✘ Ignoradas (sem referência à prancha): {relatorio['ignoradas_sem_prancha']}\n"
                f"✘ Ignoradas (sem localização X,Y): {relatorio['ignoradas_sem_localizacao']}\n"
            )
            detalhes = relatorio["detalhes_ignoradas"]
            if detalhes:
                msg += "\nDetalhe das ignoradas:\n" + "\n".join(detalhes[:15])
                if len(detalhes) > 15:
                    msg += f"\n... e mais {len(detalhes) - 15}."
            messagebox.showinfo("Resultado da importação BCF", msg)

        except Exception as e:
            messagebox.showerror("Erro na Importação", f"Falha ao ler arquivo BCF:\n{e}")

    # ---------- selos (certificação) ----------
    def _imagem_selo(self, caminho):
        """Selo reduzido uma vez (os PNGs originais têm ~3000 px)."""
        if caminho not in _CACHE_SELOS:
            img = Image.open(caminho).convert("RGBA")
            img.thumbnail((900, 900), Image.LANCZOS)
            _CACHE_SELOS[caminho] = img
        return _CACHE_SELOS[caminho]

    def _colocar_selo(self, cx, cy):
        if not self._selo_para_colocar:
            return
        try:
            img = self._imagem_selo(self._selo_para_colocar)
            largura_pdf = self.tamanho_selo_atual
            altura_pdf = largura_pdf * img.height / img.width
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir o selo:\n{e}")
            return

        nova = {
            "id": proximo_id(self.anotacoes),
            "filepath": self.current_pdf_path,
            "page": self.current_page,
            "tipo": "selo",
            "arquivo_selo": self._selo_para_colocar,
            "pontos": [[cx / self.zoom_level - largura_pdf / 2, cy / self.zoom_level - altura_pdf / 2]],
            "largura": largura_pdf,
            "altura": altura_pdf,
            "autor": self.app.sessao.get("nome", ""),
            "data": agora_str(),
        }
        aplicar_selo(self.anotacoes, nova)  # o selo que estava na prancha passa a "substituído"
        salvar_anotacoes(self.anotacoes)
        self.desenhar_anotacoes()
        self.set_tool("pan")
        self._ao_mudar_certificacao()

    def _desenhar_selo(self, a):
        caminho = a.get("arquivo_selo")
        if not caminho:
            return
        largura_px = max(1, int(a.get("largura", 130) * self.zoom_level))
        altura_px = max(1, int(a.get("altura", 60) * self.zoom_level))
        tag_id = f"anot_{a['id']}"
        (px, py), = a["pontos"]
        x, y = px * self.zoom_level, py * self.zoom_level
        try:
            img = self._imagem_selo(caminho).resize((largura_px, altura_px), Image.LANCZOS)
            foto = ImageTk.PhotoImage(img, master=self)
            self._selo_photo_refs[a["id"]] = foto
            self.canvas.create_image(x, y, anchor="nw", image=foto, tags=("anot", "marcacao", tag_id))
        except Exception:
            pass  # selo removido da rede: a legenda ainda mostra o status
        # legenda com o status certificado, logo abaixo do selo
        tamanho = max(6, round(7.5 * self.zoom_level))
        self.canvas.create_text(x + largura_px / 2, y + altura_px + 3 * self.zoom_level, anchor="n",
                                text=legenda_selo(a), fill="#26343B", font=("Segoe UI", tamanho, "bold"),
                                tags=("anot", "marcacao", tag_id))

    def _selo_sob_cursor(self, cx, cy):
        """O selo ativo sob o clique (imagem ou legenda), ou None."""
        for item in reversed(self.canvas.find_overlapping(cx - 2, cy - 2, cx + 2, cy + 2)):
            for tag in self.canvas.gettags(item):
                if tag.startswith("anot_"):
                    anot_id = int(tag.split("_")[1])
                    a = next((x for x in self.anotacoes if x.get("id") == anot_id), None)
                    if a and a.get("tipo") == "selo" and estado_selo(a, self.anotacoes) == ATIVO:
                        return a
        return None

    def _soltar_selo(self):
        movendo, self._movendo_selo = self._movendo_selo, None
        self.canvas.config(cursor="fleur")
        (x0, y0), (x1, y1) = movendo["inicio"], movendo["ultimo"]
        if abs(x1 - x0) < 2 and abs(y1 - y0) < 2:
            return  # foi só um clique
        a = next((x for x in self.anotacoes if x.get("id") == movendo["id"]), None)
        if a is None:
            return
        (px, py), = a["pontos"]
        mover_selo(self.anotacoes, a["id"], px + (x1 - x0) / self.zoom_level, py + (y1 - y0) / self.zoom_level,
                   agora_str())
        salvar_anotacoes(self.anotacoes)
        self.desenhar_anotacoes()
        if self.painel:
            self.painel.atualizar_certificacao()

    def remover_anotacao(self, anotacao_id):
        era_selo = any(a.get("id") == anotacao_id and a.get("tipo") == "selo" for a in self.anotacoes)
        if era_selo:
            # o selo sai da prancha mas continua no histórico de certificação
            remover_selo(self.anotacoes, anotacao_id, self.app.sessao.get("nome", ""), agora_str())
        else:
            self.anotacoes = [a for a in self.anotacoes if a.get("id") != anotacao_id]
        salvar_anotacoes(self.anotacoes)
        self.canvas.delete(f"anot_{anotacao_id}")
        self._selo_photo_refs.pop(anotacao_id, None)
        if era_selo:
            self._ao_mudar_certificacao()

    def _apagar_anotacao_em(self, cx, cy):
        raio = 6
        for item in self.canvas.find_overlapping(cx - raio, cy - raio, cx + raio, cy + raio):
            tags = self.canvas.gettags(item)
            if "anot" not in tags:
                continue
            anot_tag = next((t for t in tags if t.startswith("anot_")), None)
            if not anot_tag:
                continue
            self.remover_anotacao(int(anot_tag.split("_")[1]))
            return

    def _ao_mudar_certificacao(self):
        self._atualizar_cabecalho()
        if self.painel:
            self.painel.atualizar_certificacao()

    # ---------- PDF e zoom ----------
    def open_pdf(self, initialdir=None):
        if initialdir is None:
            sessao = self.app.sessao
            initialdir = (pasta_vrf(sessao.get("obra"), sessao.get("disciplina"))
                          or (os.path.dirname(self.current_pdf_path) if self.current_pdf_path else None))
        filepath = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")], initialdir=initialdir)
        if filepath:
            self._abrir_documento(filepath, 0, None)
            self.app.sincronizar_banco()

    def reabrir_arquivo(self, filepath, pagina=0, zoom=None):
        """Reabre um PDF numa página (e zoom, se informado — senão ajusta
        à tela). Usado pela Consulta e ao trocar o tema."""
        self._abrir_documento(filepath, pagina, zoom)

    def _abrir_documento(self, filepath, pagina, zoom):
        self.current_pdf_path = filepath
        self.pdf_document = fitz.open(filepath)
        self.current_page = max(0, min(pagina, self.pdf_document.page_count - 1))
        self.local_pendente = None
        self.issue_selecionada_id = None
        self._estado_vazio()  # já com documento: só limpa o convite "Abrir PDF"
        if zoom is not None:
            self.zoom_level = zoom
        else:
            self.zoom_level = self._zoom_para_caber()
        self.render_page()
        if self.painel:
            self.painel.atualizar_certificacao()

    def _zoom_para_caber(self):
        self.update_idletasks()
        pagina = self.pdf_document.load_page(self.current_page)
        largura = max(200, self.canvas.winfo_width() - 2 * MARGEM_PRANCHA)
        altura = max(200, self.canvas.winfo_height() - 2 * MARGEM_PRANCHA)
        zoom = min(largura / pagina.rect.width, altura / pagina.rect.height)
        return max(ZOOM_MINIMO, min(ZOOM_MAXIMO, zoom))

    def ajustar_a_tela(self):
        if self.pdf_document:
            self.zoom_level = self._zoom_para_caber()
            self.render_page()

    def _ajustar_zoom(self, novo_zoom):
        """Aplica um novo nível de zoom com feedback visual instantâneo
        (redimensionando a imagem já carregada via PIL, sem re-rasterizar o
        PDF a cada tick de scroll) e agenda a re-renderização real (nítida)
        depois de um curto período sem novos eventos de zoom."""
        novo_zoom = max(ZOOM_MINIMO, min(ZOOM_MAXIMO, novo_zoom))
        if abs(novo_zoom - self.zoom_level) < 1e-6:
            return
        self.zoom_level = novo_zoom
        self._aplicar_preview_zoom()
        self.lbl_zoom_pct.config(text=f"{int(self.zoom_level * 100)}%")
        if self._zoom_debounce_id:
            self.after_cancel(self._zoom_debounce_id)
        self._zoom_debounce_id = self.after(180, self._commit_zoom_real)

    def _aplicar_preview_zoom(self):
        if self._pil_image_base is None or not self._zoom_base_level or self._imagem_item is None:
            return
        fator_total = self.zoom_level / self._zoom_base_level
        novo_w = max(1, int(self._pil_image_base.width * fator_total))
        novo_h = max(1, int(self._pil_image_base.height * fator_total))

        img_redim = self._pil_image_base.resize((novo_w, novo_h), Image.BILINEAR)
        self.current_image = ImageTk.PhotoImage(img_redim, master=self)
        self.canvas.itemconfig(self._imagem_item, image=self.current_image)
        self.canvas.delete("sombra")

        fator_passo = novo_w / self._largura_preview_atual if self._largura_preview_atual else fator_total
        if abs(fator_passo - 1.0) > 1e-9:
            self.canvas.scale("marcacao", 0, 0, fator_passo, fator_passo)
        self._largura_preview_atual = novo_w
        self._altura_preview_atual = novo_h
        self._atualizar_regiao()

    def _atualizar_regiao(self):
        """Centraliza a prancha quando ela é menor que a área visível (a
        imagem fica sempre em (0, 0); quem centraliza é a scrollregion com
        margens negativas — assim as coordenadas das marcações não mudam)."""
        if not self.pdf_document or not self._largura_preview_atual:
            self._estado_vazio()
            return
        w, h = self._largura_preview_atual, self._altura_preview_atual
        cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        mx = max(MARGEM_PRANCHA, (cw - w) / 2)
        my = max(MARGEM_PRANCHA, (ch - h) / 2)
        self.canvas.configure(scrollregion=(-mx, -my, w + mx, h + my))

    def _desenhar_sombra(self, w, h):
        """Sombra suave da folha: camadas de retângulos do canvas (barato
        mesmo com pranchas enormes em zoom alto) e uma borda fina."""
        self.canvas.delete("sombra")
        base = TEMA["pagina"]
        r0, g0, b0 = (int(base[i:i + 2], 16) for i in (1, 3, 5))
        escuro = TEMA.esta_escuro()
        for k in range(8, 0, -1):
            fator = (9 - k) / 9 * (0.05 if escuro else 0.11)
            cor = "#{:02X}{:02X}{:02X}".format(*(round(c * (1 - fator)) for c in (r0, g0, b0)))
            self.canvas.create_rectangle(-k, -k + 4, w + k, h + k + 4, fill=cor, outline="", tags=("sombra",))
        self.canvas.create_rectangle(-1, -1, w, h, outline=TEMA["card_borda"], tags=("sombra",))
        self.canvas.tag_lower("sombra")

    def render_page(self):
        if not self.pdf_document:
            return
        if self._zoom_debounce_id:
            self.after_cancel(self._zoom_debounce_id)
            self._zoom_debounce_id = None

        page = self.pdf_document.load_page(self.current_page)
        mat = fitz.Matrix(self.zoom_level, self.zoom_level)
        pix = page.get_pixmap(matrix=mat)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.current_image = ImageTk.PhotoImage(img, master=self)

        self._pil_image_base = img
        self._zoom_base_level = self.zoom_level
        self._largura_preview_atual = pix.width
        self._altura_preview_atual = pix.height

        self.canvas.delete("all")
        self._desenhar_sombra(pix.width, pix.height)
        self._imagem_item = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_image)
        self._atualizar_regiao()

        self.lbl_zoom_pct.config(text=f"{int(self.zoom_level * 100)}%")
        self._atualizar_cabecalho()

        self.draw_pins()
        self.desenhar_anotacoes()
        if self.painel:
            self.painel.atualizar_lista()

    # ---------- pins (comentários) ----------
    def draw_pins(self):
        self.canvas.delete("pin")
        if not self.pdf_document:
            return
        for issue in filtro_issues_pdf(self.app.issues, self.current_pdf_path, self.current_page):
            x = issue.get("pdf_x", 0) * self.zoom_level
            y = issue.get("pdf_y", 0) * self.zoom_level
            cor = CORES_STATUS.get(issue["status"], "#999999")
            tag_pin = f"issuepin_{issue['id']}"
            tags = ("pin", "marcacao", tag_pin)
            r = 11
            if issue["id"] == self.issue_selecionada_id:
                self.canvas.create_oval(x - r - 6, y - r - 6, x + r + 6, y + r + 6, outline=TEMA["acento"],
                                        width=3, tags=tags)
            self.canvas.create_oval(x - r - 1, y - r + 1, x + r + 1, y + r + 3, fill="#B8C2C6", outline="",
                                    tags=tags)  # sombrinha
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=cor, outline="#FFFFFF", width=2, tags=tags)
            self.canvas.create_text(x, y, text=str(issue["id"]), fill=texto_sobre(cor), font=("Segoe UI", 8, "bold"),
                                    tags=tags)
        if self.local_pendente and self.local_pendente[0] == self.current_page:
            _, px, py = self.local_pendente
            x, y = px * self.zoom_level, py * self.zoom_level
            self.canvas.create_oval(x - 13, y - 13, x + 13, y + 13, outline=TEMA["acento"], width=2, dash=(4, 3),
                                    fill="#FFFFFF", tags=("pin", "marcacao"))
            self.canvas.create_text(x, y, text="+", fill=TEMA["acento"], font=("Segoe UI", 12, "bold"),
                                    tags=("pin", "marcacao"))

    def selecionar_issue(self, issue_id):
        self.issue_selecionada_id = issue_id
        self.draw_pins()
        if self.painel:
            if not self.painel_visivel:
                self.alternar_painel()
            self.painel.selecionar_issue(issue_id)

    def ir_para_issue(self, issue):
        """Vai até a página do problema, centraliza o pino e o destaca."""
        if not self.pdf_document:
            return
        pagina = issue.get("page", 0)
        if pagina != self.current_page and 0 <= pagina < self.pdf_document.page_count:
            self._cancelar_marcacao_em_andamento()
            self.current_page = pagina
            self.issue_selecionada_id = issue["id"]
            self.render_page()
        self.issue_selecionada_id = issue["id"]
        self.draw_pins()
        self.update_idletasks()
        self._pulsar(issue)
        x0, y0, x1, y1 = (float(v) for v in str(self.canvas.cget("scrollregion")).split())
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        alvo_x = issue.get("pdf_x", 0) * self.zoom_level
        alvo_y = issue.get("pdf_y", 0) * self.zoom_level
        if x1 - x0 > cw:
            self.canvas.xview_moveto(max(0.0, (alvo_x - x0 - cw / 2) / (x1 - x0)))
        if y1 - y0 > ch:
            self.canvas.yview_moveto(max(0.0, (alvo_y - y0 - ch / 2) / (y1 - y0)))
        if self.painel:
            self.painel._destacar(issue["id"])

    def _pulsar(self, issue, passo=0):
        """Anel que se expande e some sobre o pino — destaca na prancha o
        problema clicado na lista de comentários."""
        self.canvas.delete("pulso")
        if passo > 14 or issue.get("page") != self.current_page:
            return
        x = issue.get("pdf_x", 0) * self.zoom_level
        y = issue.get("pdf_y", 0) * self.zoom_level
        r = 14 + (passo % 7) * 6
        self.canvas.create_oval(x - r, y - r, x + r, y + r, outline=TEMA["acento"], width=max(1, 4 - (passo % 7) // 2),
                                tags=("pulso", "marcacao"))
        self.after(55, lambda: self._pulsar(issue, passo + 1))

    def criar_issue_no_local(self, texto, tipo, atribuido_inicial=None, titulo=None):
        """Cria o problema no local marcado com a ferramenta Comentar (o
        texto vira título + descrição). Devolve o id, ou None se cancelado."""
        if not self.local_pendente:
            return None
        sessao = self.app.sessao
        if DialogNovaIssue.sessao_completa(dict(sessao, atribuido_para=atribuido_inicial or sessao.get("atribuido_para"))):
            # obra/disciplina/projetista já definidos em "Projeto Analisado":
            # cria direto (um "@nome" no texto troca o responsável)
            obra, disciplina, criado_por = sessao["obra"], sessao["disciplina"], sessao["nome"]
            atribuido = atribuido_inicial or sessao["atribuido_para"]
        else:
            dialogo = DialogNovaIssue(self.winfo_toplevel(), lista_obras=self.app.obras_lista, sessao=sessao,
                                      atribuido_inicial=atribuido_inicial)
            if not dialogo.criado_por or not dialogo.atribuido_para or not dialogo.obra:
                return None
            obra, disciplina = dialogo.obra, dialogo.disciplina
            criado_por, atribuido = dialogo.criado_por, dialogo.atribuido_para
        pagina, px, py = self.local_pendente
        agora = agora_str()
        issue = {
            "id": proximo_id(self.app.issues),
            "titulo": titulo or titulo_do_texto(texto),
            "status": "Novo",
            "tipo": tipo,
            "obra": obra,
            "disciplina": disciplina,
            "criado_por": criado_por,
            "atribuido_para": atribuido,
            "desc": (texto or "").strip(),
            "historico": [],
            "data_criacao": agora,
            "data_modificacao": agora,
            "tipo_doc": "pdf",
            "page": pagina,
            "filepath": self.current_pdf_path,
            "pdf_x": px,
            "pdf_y": py,
        }
        self.app.issues.append(issue)
        self.app.salvar_banco_dados()
        self.local_pendente = None
        self.issue_selecionada_id = issue["id"]
        self.draw_pins()
        self._atualizar_cabecalho()
        if self.painel:
            self.painel.atualizar_lista()
            self.painel.selecionar_issue(issue["id"])
        return issue["id"]

    # ---------- "Baixar" ----------
    def exportar_pdf(self):
        if not self.pdf_document:
            messagebox.showinfo("Baixar", "Abra uma prancha (PDF) primeiro.")
            return
        pasta, nome = os.path.split(self.current_pdf_path)
        destino = filedialog.asksaveasfilename(
            title="Salvar prancha revisada", initialdir=pasta, defaultextension=".pdf",
            initialfile=self._nome_sugerido_baixar(), filetypes=[("PDF", "*.pdf")])
        if not destino:
            return
        if os.path.normcase(os.path.abspath(destino)) == os.path.normcase(os.path.abspath(self.current_pdf_path)):
            messagebox.showwarning("Baixar", "Escolha outro nome: o PDF original não é sobrescrito.")
            return
        try:
            qtd = exportar_pdf_anotado(self.current_pdf_path, destino, self.anotacoes, self.app.issues, CORES_STATUS)
        except Exception as e:
            messagebox.showerror("Baixar", f"Não foi possível gerar o PDF revisado:\n{e}")
            return
        status = status_certificacao(self.anotacoes, self.current_pdf_path)
        texto_status = f"\nStatus: {status['codigo']} · {status['descricao']}" if status else ""
        messagebox.showinfo("Baixar", f"PDF revisado salvo com {qtd} marcação(ões).{texto_status}\n\n{destino}")

    def _nome_sugerido_baixar(self):
        """Padrão já usado nas pastas VRF: <arquivo>_<INICIAIS>_<SELO>.pdf
        (sem selo: <arquivo>_<INICIAIS>_REV.pdf)."""
        status = status_certificacao(self.anotacoes, self.current_pdf_path)
        sigla = iniciais((self.app.usuario_atual or {}).get("nome", ""))
        caminho = nome_certificado(self.current_pdf_path, sigla, status["codigo"] if status else "REV")
        return os.path.basename(caminho)

    # ---------- integração com AppCDE ----------
    def sincronizar(self):
        self.anotacoes = carregar_anotacoes()
        self.draw_pins()
        self.desenhar_anotacoes()
        self._atualizar_cabecalho()
        if self.painel:
            self.painel.atualizar_lista()
            self.painel.atualizar_certificacao()
