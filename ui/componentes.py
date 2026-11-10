"""Componentes visuais reutilizáveis do estilo Figma.

Tkinter não tem cantos arredondados nem antialiasing nas formas do
Canvas, então tudo que é arredondado é desenhado assim: o miolo com
retângulos do próprio Canvas (rápido, redimensiona sem custo) e só os
quatro cantos como pequenas imagens PIL suavizadas (cacheadas por raio
e cor). Anéis/donuts são imagens PIL inteiras (são pequenos).

Ícones: fonte "Segoe MDL2 Assets" (vem com o Windows 10/11) — ícones de
linha parecidos com os do protótipo, sem depender de arquivos."""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

from config import TEMA

FONTE = "Segoe UI"
FONTE_SEMI = "Segoe UI Semibold"
FONTE_ICONE = "Segoe MDL2 Assets"


class Icone:
    INICIO = ""
    DOCUMENTO = ""
    CUBO = ""
    PRANCHETA = ""
    GRAFICO = ""
    RELATORIO = ""
    PESSOAS = ""
    PESSOA = ""
    AJUDA = ""
    BUSCA = ""
    LUA = ""
    SOL = ""
    OLHO = ""
    VOLTAR = ""
    BAIXAR = ""
    SELECIONAR = ""
    REGUA = ""
    CANETA = ""
    COMENTAR = ""
    BALAO = ""
    CALIBRAR = ""
    FORMA = ""
    TEXTO = ""
    BORRACHA = ""
    SELO = ""
    IMPORTAR = ""
    MAPA_PIN = ""
    LIXEIRA = ""
    PAINEL = ""
    SINO = ""
    PASTA = ""
    MENSAGEM = ""
    RELOGIO = ""
    CHECK = ""
    SETA_DIREITA = ""
    CHEVRON_DIREITA = ""
    CHEVRON_ESQUERDA = ""
    CHEVRON_BAIXO = ""
    UPLOAD = ""
    GRADE = ""
    TENDENCIA = ""
    EDITAR = ""
    EXCLUIR = ""
    ATUALIZAR = ""
    FILTRO = ""
    MAIS = ""
    FECHAR = ""
    RETICENCIAS = ""
    TROCAR = ""
    SAIR = ""
    CADEADO = ""
    CHAVE = ""
    ADICIONAR_PESSOA = ""
    LISTA = ""
    LISTA_CHECK = ""
    ALERTA = ""
    INFO = ""
    CALENDARIO = ""


def fonte(tamanho, peso="normal"):
    if peso == "semi":
        return (FONTE_SEMI, tamanho)
    if peso == "bold":
        return (FONTE, tamanho, "bold")
    return (FONTE, tamanho)


def cor_fundo_de(widget):
    try:
        return widget.cget("bg")
    except tk.TclError:
        return TEMA["pagina"]


def iniciais(nome):
    partes = [p for p in (nome or "").replace(".", " ").split() if p[:1].isalpha()]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def nome_curto(nome):
    partes = (nome or "").split()
    if len(partes) <= 2:
        return nome or ""
    return f"{partes[0]} {partes[-1]}"


# ---------------------------------------------------------------------------
# retângulo arredondado no Canvas
# ---------------------------------------------------------------------------
_CACHE_CANTOS = {}


def _cantos(canvas, raio, preenchimento, contorno):
    """4 imagens (TL, TR, BL, BR) de um quarto de círculo suavizado.
    Cache por interpretador Tk (os testes criam/destroem várias raízes)."""
    chave = (id(canvas.tk), raio, preenchimento, contorno)
    if chave in _CACHE_CANTOS:
        return _CACHE_CANTOS[chave]
    s = 4
    d = raio * 2
    img = Image.new("RGBA", (d * s, d * s), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(img)
    desenho.ellipse((0, 0, d * s - 1, d * s - 1), fill=preenchimento or None,
                    outline=contorno or None, width=s if contorno else 0)
    img = img.resize((d, d), Image.LANCZOS)
    pecas = [img.crop((0, 0, raio, raio)), img.crop((raio, 0, d, raio)),
             img.crop((0, raio, raio, d)), img.crop((raio, raio, d, d))]
    fotos = [ImageTk.PhotoImage(p, master=canvas) for p in pecas]
    _CACHE_CANTOS[chave] = fotos
    return fotos


def retangulo_arredondado(canvas, x0, y0, x1, y1, raio, preenchimento, contorno=None, tag=""):
    """Desenha no `canvas` um retângulo de cantos arredondados ocupando
    os pixels [x0, x1) x [y0, y1). Devolve a tag usada."""
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    raio = max(1, min(int(raio), (x1 - x0) // 2, (y1 - y0) // 2))
    tags = (tag,) if tag else ()
    if preenchimento:
        canvas.create_rectangle(x0 + raio, y0, x1 - raio, y1, fill=preenchimento, width=0, tags=tags)
        canvas.create_rectangle(x0, y0 + raio, x1, y1 - raio, fill=preenchimento, width=0, tags=tags)
    if contorno:
        canvas.create_line(x0 + raio, y0, x1 - raio, y0, fill=contorno, tags=tags)
        canvas.create_line(x0 + raio, y1 - 1, x1 - raio, y1 - 1, fill=contorno, tags=tags)
        canvas.create_line(x0, y0 + raio, x0, y1 - raio, fill=contorno, tags=tags)
        canvas.create_line(x1 - 1, y0 + raio, x1 - 1, y1 - raio, fill=contorno, tags=tags)
    tl, tr, bl, br = _cantos(canvas, raio, preenchimento, contorno)
    canvas.create_image(x0, y0, image=tl, anchor="nw", tags=tags)
    canvas.create_image(x1, y0, image=tr, anchor="ne", tags=tags)
    canvas.create_image(x0, y1, image=bl, anchor="sw", tags=tags)
    canvas.create_image(x1, y1, image=br, anchor="se", tags=tags)
    return tag


# ---------------------------------------------------------------------------
# cartão
# ---------------------------------------------------------------------------
class Cartao(tk.Canvas):
    """Cartão branco arredondado com borda fina. Conteúdo vai em
    `self.corpo` (um Frame comum). `ajustar_altura=True`: a altura segue
    o conteúdo; False: o conteúdo estica para ocupar o cartão."""

    def __init__(self, parent, raio=12, padding=20, cor=None, borda="padrao",
                 ajustar_altura=True, tamanho_fixo=False, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=kw.pop("width", 50), height=kw.pop("height", 50), **kw)
        self.raio = raio
        self.padding = padding if isinstance(padding, tuple) else (padding, padding)
        self.cor = cor or TEMA["card"]
        self.borda = TEMA["card_borda"] if borda == "padrao" else borda
        self.ajustar_altura = ajustar_altura and not tamanho_fixo
        self.tamanho_fixo = tamanho_fixo  # True: mantém width/height passados, não segue o conteúdo
        self.corpo = tk.Frame(self, bg=self.cor)
        px, py = self.padding
        self._janela = self.create_window(px, py, window=self.corpo, anchor="nw")
        self.bind("<Configure>", self._redesenhar)
        self.corpo.bind("<Configure>", self._ajustar, add="+")

    def _ajustar(self, _evento=None):
        if self.tamanho_fixo:
            return
        px, py = self.padding
        largura = self.corpo.winfo_reqwidth() + 2 * px
        if int(float(self.cget("width"))) != largura:
            self.configure(width=largura)
        if self.ajustar_altura:
            altura = self.corpo.winfo_reqheight() + 2 * py
            if int(float(self.cget("height"))) != altura:
                self.configure(height=altura)

    def _redesenhar(self, evento):
        largura, altura = evento.width, evento.height
        self.delete("fundo")
        retangulo_arredondado(self, 0, 0, largura, altura, self.raio, self.cor, self.borda, tag="fundo")
        self.tag_lower("fundo")
        px, py = self.padding
        self.itemconfig(self._janela, width=max(1, largura - 2 * px))
        if not self.ajustar_altura:
            self.itemconfig(self._janela, height=max(1, altura - 2 * py))


# ---------------------------------------------------------------------------
# botões, pílulas, segmentados
# ---------------------------------------------------------------------------
def _cores_variante(variante):
    if variante == "primario":
        return TEMA["primario"], TEMA["primario_hover"], TEMA["primario_texto"], None
    if variante == "perigo":
        bg, fg = TEMA["pill_vermelho"]
        return bg, TEMA["card_borda"], fg, None
    if variante == "ativo":  # ferramenta selecionada (azul claro, texto azul)
        bg, fg = TEMA["pill_azul"]
        return bg, bg, fg, None
    if variante == "fantasma":
        return None, TEMA["sidebar_sel"], TEMA["titulo"], None
    if variante == "link":
        return None, None, TEMA["primario"] if not TEMA.esta_escuro() else TEMA["acento"], None
    # secundario: branco com borda
    return TEMA["card"], TEMA["sidebar_sel"], TEMA["titulo"], TEMA["card_borda"]


class Botao(tk.Canvas):
    """Botão arredondado (`variante`: primario, secundario, perigo,
    fantasma, link), com ícone opcional à esquerda (ou à direita para
    `icone_direita`)."""

    def __init__(self, parent, texto, comando=None, variante="secundario", icone=None,
                 icone_direita=None, largura=None, altura=36, raio=8, tamanho_fonte=10,
                 negrito=True, **kw):
        self._fundo_pai = cor_fundo_de(parent)
        super().__init__(parent, bg=self._fundo_pai, highlightthickness=0, bd=0,
                         cursor="hand2", **kw)
        self.texto = texto
        self.comando = comando
        self.variante = variante
        self.icone = icone
        self.icone_direita = icone_direita
        self.raio = raio
        self.tamanho_fonte = tamanho_fonte
        self._fonte = tkfont.Font(family=FONTE_SEMI if negrito else FONTE, size=tamanho_fonte)
        self._fonte_icone = tkfont.Font(family=FONTE_ICONE, size=max(8, tamanho_fonte - 1))
        largura_conteudo = self._fonte.measure(texto) if texto else 0
        for ic in (icone, icone_direita):
            if ic:
                largura_conteudo += self._fonte_icone.measure(ic) + (8 if texto else 0)
        padding = 0 if variante == "link" else 18
        self.largura = largura or (largura_conteudo + 2 * padding)
        self.altura = altura
        self.configure(width=self.largura, height=altura)
        self._hover = False
        self._desenhar()
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._clicar)
        self.bind("<Configure>", self._ao_redimensionar)

    def _ao_redimensionar(self, evento):
        if (evento.width, evento.height) != (self.largura, self.altura):
            self.largura, self.altura = evento.width, evento.height
            self._desenhar()

    def _set_hover(self, valor):
        self._hover = valor
        self._desenhar()

    def _clicar(self, evento):
        if 0 <= evento.x <= self.winfo_width() and 0 <= evento.y <= self.winfo_height() and self.comando:
            self.comando()

    def _desenhar(self):
        self.delete("all")
        fundo, fundo_hover, cor_texto, borda = _cores_variante(self.variante)
        preenchimento = fundo_hover if (self._hover and fundo_hover) else fundo
        if preenchimento or borda:
            retangulo_arredondado(self, 0, 0, self.largura, self.altura, self.raio,
                                  preenchimento or self._fundo_pai, borda)
        if self.variante == "link" and self._hover:
            cor_texto = TEMA["primario_hover"] if not TEMA.esta_escuro() else TEMA["acento_hover"]
        partes = []
        if self.icone:
            partes.append((self.icone, self._fonte_icone))
        if self.texto:
            partes.append((self.texto, self._fonte))
        if self.icone_direita:
            partes.append((self.icone_direita, self._fonte_icone))
        total = sum(f.measure(t) for t, f in partes) + 8 * (len(partes) - 1)
        x = (self.largura - total) / 2
        for texto, f in partes:
            self.create_text(x, self.altura / 2, text=texto, font=f, fill=cor_texto, anchor="w")
            x += f.measure(texto) + 8

    def config_texto(self, texto):
        self.texto = texto
        self._desenhar()

    def definir_variante(self, variante):
        if variante != self.variante:
            self.variante = variante
            self._desenhar()


class Pilula(tk.Canvas):
    """Etiqueta arredondada (status, contagens)."""

    def __init__(self, parent, texto, cores=None, tamanho_fonte=8, altura=22, icone=None, cor_icone=None, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0, **kw)
        bg, fg = cores or TEMA["pill_cinza"]
        f = tkfont.Font(family=FONTE, size=tamanho_fonte)
        # ícones da fonte MDL2 ficam na área de uso privado; "●" e afins usam a fonte normal
        familia_icone = FONTE_ICONE if icone and ord(icone[0]) >= 0xE000 else FONTE
        fi = tkfont.Font(family=familia_icone, size=tamanho_fonte - 1)
        largura = f.measure(texto) + 20 + ((fi.measure(icone) + 5) if icone else 0)
        self.configure(width=largura, height=altura)
        retangulo_arredondado(self, 0, 0, largura, altura, altura // 2, bg)
        x = 10
        if icone:
            self.create_text(x, altura / 2, text=icone, font=fi, fill=cor_icone or fg, anchor="w")
            x += fi.measure(icone) + 5
        self.create_text(x, altura / 2, text=texto, font=f, fill=fg, anchor="w")


CORES_STATUS_PILULA = {
    "Novo": "pill_vermelho",
    "Reaberto": "pill_dourado",
    "Respondido": "pill_azul",
    "Fechado": "pill_verde",
    "Em revisão": "pill_azul",
    "Em análise": "pill_dourado",
    "Certificação": "pill_verde",
    "Certificado": "pill_verde",
    "Pausado": "pill_cinza",
}


def imagem_pilula(texto, cores, master, tamanho_fonte=12, altura=22, largura=None):
    """Pílula como PhotoImage (para usar dentro de Treeview, que só
    aceita imagens). Desenhada em 3x e reduzida, para bordas suaves."""
    s = 3
    bg, fg = cores
    try:
        f = ImageFont.truetype("segoeui.ttf", tamanho_fonte * s)
    except OSError:
        f = ImageFont.load_default()
    caixa = f.getbbox(texto)
    largura = largura or (caixa[2] - caixa[0]) // s + 20
    img = Image.new("RGBA", (largura * s, altura * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, largura * s - 1, altura * s - 1), radius=altura * s // 2, fill=bg)
    d.text((largura * s / 2, altura * s / 2), texto, font=f, fill=fg, anchor="mm")
    return ImageTk.PhotoImage(img.resize((largura, altura), Image.LANCZOS), master=master)


def _misturar(cor_hex, alvo, fator):
    cor_hex = cor_hex.lstrip("#")
    r, g, b = (int(cor_hex[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02X}{:02X}{:02X}".format(*(round(c + (alvo - c) * fator) for c in (r, g, b)))


def luminancia(cor_hex):
    cor_hex = cor_hex.lstrip("#")
    r, g, b = (int(cor_hex[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def texto_sobre(cor_hex):
    """Branco ou quase-preto, o que for legível sobre `cor_hex`."""
    return "#1A1A1A" if luminancia(cor_hex) > 0.6 else "#FFFFFF"


def cores_status(status):
    """(fundo, texto) da pílula de um status de issue, derivadas da mesma
    cor do pino na prancha — assim o significado da cor é um só em todo o
    app (inclusive nos modos de daltonismo)."""
    from config import CORES_STATUS
    cor = CORES_STATUS.get(status)
    if not cor:
        return TEMA[CORES_STATUS_PILULA.get(status, "pill_cinza")]
    if TEMA.esta_escuro():
        return _misturar(cor, 0, 0.55), _misturar(cor, 255, 0.45)
    fundo = _misturar(cor, 255, 0.82)
    texto = _misturar(cor, 0, 0.55 if luminancia(cor) > 0.5 else 0.15)
    return fundo, texto


def pilula_status(parent, status, **kw):
    return Pilula(parent, status, cores=cores_status(status), **kw)


class Segmentado(tk.Frame):
    """Grupo de opções exclusivas. `agrupado=False`: pílulas separadas
    (filtros "Todos / Em andamento / ..."); True: botões colados dentro
    de uma moldura (seletor "7 dias / 30 dias / 90 dias")."""

    def __init__(self, parent, opcoes, valor=None, comando=None, agrupado=False, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), **kw)
        self.opcoes = list(opcoes)
        self.valor = valor if valor is not None else self.opcoes[0]
        self.comando = comando
        self.agrupado = agrupado
        if agrupado:
            self._moldura = Cartao(self, raio=8, padding=4)
            self._moldura.pack()
            self._alvo = self._moldura.corpo
        else:
            self._alvo = self
        self._botoes = {}
        self._montar()

    def _montar(self):
        for b in self._botoes.values():
            b.destroy()
        self._botoes = {}
        for opcao in self.opcoes:
            selecionado = opcao == self.valor
            if self.agrupado:
                variante = "primario" if selecionado else "fantasma"
            else:
                variante = "primario" if selecionado else "secundario"
            b = Botao(self._alvo, opcao, comando=lambda o=opcao: self.selecionar(o),
                      variante=variante, altura=30 if self.agrupado else 32,
                      raio=6, tamanho_fonte=9, negrito=selecionado)
            b.pack(side=tk.LEFT, padx=(0, 2 if self.agrupado else 6))
            self._botoes[opcao] = b

    def selecionar(self, opcao, disparar=True):
        self.valor = opcao
        self._montar()
        if disparar and self.comando:
            self.comando(opcao)


# ---------------------------------------------------------------------------
# textos de página
# ---------------------------------------------------------------------------
def espacar(texto):
    """Simula letter-spacing de títulos pequenos em caixa alta."""
    return " ".join(texto.upper())


def sobretitulo(parent, texto, com_linha=True, cor=None):
    """"— VISÃO GERAL": linha curta + texto pequeno espaçado."""
    f = tk.Frame(parent, bg=cor_fundo_de(parent))
    if com_linha:
        tk.Frame(f, bg=cor or TEMA["eyebrow"], width=22, height=1).pack(side=tk.LEFT, padx=(0, 8))
    tk.Label(f, text=espacar(texto), bg=f["bg"], fg=cor or TEMA["eyebrow"],
             font=fonte(8, "semi")).pack(side=tk.LEFT)
    return f


def cabecalho_pagina(parent, sobre, titulo, subtitulo=None, migalhas=None):
    """Cabeçalho padrão das telas: migalhas (Início › X), sobretítulo,
    título grande e subtítulo. Devolve (frame, frame_direita) — o da
    direita é para controles (ex.: seletor de período)."""
    f = tk.Frame(parent, bg=cor_fundo_de(parent))
    if migalhas:
        m = tk.Frame(f, bg=f["bg"])
        m.pack(anchor="w", pady=(0, 14))
        for i, (texto, comando) in enumerate(migalhas):
            ultimo = i == len(migalhas) - 1
            lbl = tk.Label(m, text=texto, bg=f["bg"], font=fonte(10, "semi" if ultimo else "normal"),
                           fg=TEMA["titulo"] if ultimo else TEMA["texto_fraco"],
                           cursor="" if ultimo or not comando else "hand2")
            lbl.pack(side=tk.LEFT)
            if comando and not ultimo:
                lbl.bind("<Button-1>", lambda e, c=comando: c())
            if not ultimo:
                tk.Label(m, text=Icone.CHEVRON_DIREITA, bg=f["bg"], fg=TEMA["texto_fraco"],
                         font=(FONTE_ICONE, 7)).pack(side=tk.LEFT, padx=10)
    linha = tk.Frame(f, bg=f["bg"])
    linha.pack(fill=tk.X)
    esquerda = tk.Frame(linha, bg=f["bg"])
    esquerda.pack(side=tk.LEFT, fill=tk.X, expand=True)
    direita = tk.Frame(linha, bg=f["bg"])
    direita.pack(side=tk.RIGHT, anchor="se")
    if sobre:
        sobretitulo(esquerda, sobre).pack(anchor="w", pady=(0, 6))
    tk.Label(esquerda, text=titulo, bg=f["bg"], fg=TEMA["titulo"],
             font=fonte(21, "semi")).pack(anchor="w")
    if subtitulo:
        tk.Label(esquerda, text=subtitulo, bg=f["bg"], fg=TEMA["texto_fraco"],
                 font=fonte(11), justify="left").pack(anchor="w", pady=(4, 0))
    return f, direita


def cabecalho_cartao(parent, sobre, titulo, direita_texto=None, direita_comando=None):
    """Topo de cartão: "ACESSO RÁPIDO / Projetos recentes ... Ver todos →"."""
    f = tk.Frame(parent, bg=cor_fundo_de(parent))
    esquerda = tk.Frame(f, bg=f["bg"])
    esquerda.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if sobre:
        tk.Label(esquerda, text=espacar(sobre), bg=f["bg"], fg=TEMA["eyebrow"],
                 font=fonte(7, "semi")).pack(anchor="w")
    tk.Label(esquerda, text=titulo, bg=f["bg"], fg=TEMA["titulo"],
             font=fonte(13, "semi")).pack(anchor="w", pady=(2, 0))
    direita = tk.Frame(f, bg=f["bg"])
    direita.pack(side=tk.RIGHT, anchor="n")
    if direita_texto:
        Botao(direita, direita_texto, comando=direita_comando, variante="link",
              icone_direita=Icone.SETA_DIREITA, altura=24, tamanho_fonte=10).pack()
    return f, direita


def separador(parent, pady=0, cor=None):
    s = tk.Frame(parent, bg=cor or TEMA["linha"], height=1)
    s.pack(fill=tk.X, pady=pady)
    return s


def rotulo(parent, texto, tamanho=10, peso="normal", cor=None, **kw):
    return tk.Label(parent, text=texto, bg=cor_fundo_de(parent), fg=cor or TEMA["titulo"],
                    font=fonte(tamanho, peso), **kw)


def icone(parent, glifo, tamanho=11, cor=None, **kw):
    return tk.Label(parent, text=glifo, bg=cor_fundo_de(parent), fg=cor or TEMA["texto_fraco"],
                    font=(FONTE_ICONE, tamanho), **kw)


class QuadradoIcone(tk.Canvas):
    """Ícone dentro de um quadradinho arredondado colorido (cartões de
    KPI, linhas de projeto, atividade recente)."""

    def __init__(self, parent, glifo, cores=None, tamanho=40, tamanho_icone=13, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=tamanho, height=tamanho, **kw)
        bg, fg = cores or TEMA["pill_azul"]
        retangulo_arredondado(self, 0, 0, tamanho, tamanho, 9, bg)
        self.create_text(tamanho / 2, tamanho / 2, text=glifo, font=(FONTE_ICONE, tamanho_icone), fill=fg)


# ---------------------------------------------------------------------------
# avatar, progresso, anel, donut, barras
# ---------------------------------------------------------------------------
class Avatar(tk.Canvas):
    def __init__(self, parent, nome, tamanho=40, cor=None, cor_texto="#FFFFFF", online=False,
                 tamanho_fonte=None, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=tamanho, height=tamanho, **kw)
        s = 4
        img = Image.new("RGBA", (tamanho * s, tamanho * s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((0, 0, tamanho * s - 1, tamanho * s - 1), fill=cor or TEMA["primario"])
        if online:
            r = tamanho * s * 0.13
            cx = cy = tamanho * s * 0.84
            d.ellipse((cx - r - s * 2, cy - r - s * 2, cx + r + s * 2, cy + r + s * 2), fill=cor_fundo_de(parent))
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#3FBF7F")
        self._foto = ImageTk.PhotoImage(img.resize((tamanho, tamanho), Image.LANCZOS), master=self)
        self.create_image(0, 0, image=self._foto, anchor="nw")
        self.create_text(tamanho / 2, tamanho / 2, text=iniciais(nome), fill=cor_texto,
                         font=fonte(tamanho_fonte or max(7, tamanho // 4), "semi"))


class BarraProgresso(tk.Canvas):
    def __init__(self, parent, valor=0.0, altura=3, cor=None, trilha=None, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         height=altura, width=kw.pop("width", 100), **kw)
        self.valor = valor
        self.altura = altura
        self.cor = cor or TEMA["primario"]
        self.trilha = trilha or TEMA["trilha"]
        self.bind("<Configure>", lambda e: self._desenhar())

    def _desenhar(self):
        self.delete("all")
        w = self.winfo_width()
        self.create_rectangle(0, 0, w, self.altura, fill=self.trilha, width=0)
        self.create_rectangle(0, 0, int(w * max(0.0, min(1.0, self.valor))), self.altura,
                              fill=self.cor, width=0)

    def definir(self, valor):
        self.valor = valor
        self._desenhar()


class BarraSegmentada(tk.Canvas):
    """Barra de progresso em segmentos coloridos (ex.: issues fechadas /
    respondidas / reabertas / novas), com o restante em cinza quando
    `total` é maior que a soma das partes."""

    def __init__(self, parent, partes, total=None, altura=8, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         height=altura, width=kw.pop("width", 120), **kw)
        self.partes = [(v, c) for v, c in partes if v > 0]
        self.total = max(total or 0, sum(v for v, _ in self.partes))
        self.altura = altura
        self.bind("<Configure>", lambda e: self._desenhar())

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.altura
        retangulo_arredondado(self, 0, 0, w, h, h // 2, TEMA["trilha"])
        if not self.total:
            return
        x = 0.0
        for n, (valor, cor) in enumerate(self.partes):
            largura = w * valor / self.total
            x1 = x + largura
            if largura >= 1:
                retangulo_arredondado(self, x, 0, max(x + 2, x1 - (2 if n < len(self.partes) - 1 else 0)), h,
                                      min(h // 2, 3), cor)
            x = x1


def _imagem_anel(tamanho, espessura, fatias, trilha, fundo):
    """`fatias`: [(fração, cor), ...] começando no topo, sentido horário."""
    s = 4
    t = tamanho * s
    img = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    caixa = (s, s, t - s - 1, t - s - 1)
    if trilha:
        d.ellipse(caixa, outline=trilha, width=espessura * s)
    inicio = -90.0
    for fracao, cor in fatias:
        if fracao <= 0:
            continue
        fim = inicio + 360.0 * fracao
        d.arc(caixa, inicio, fim, fill=cor, width=espessura * s)
        inicio = fim
    return img.resize((tamanho, tamanho), Image.LANCZOS)


class Anel(tk.Canvas):
    """Anel de progresso com texto central ("78 %")."""

    def __init__(self, parent, fracao, tamanho=90, espessura=7, cor=None, trilha=None,
                 texto=None, sufixo="%", tamanho_fonte=18, legenda=None, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=tamanho, height=tamanho, **kw)
        img = _imagem_anel(tamanho, espessura, [(fracao, cor or TEMA["primario"])],
                           trilha or TEMA["trilha"], None)
        self._foto = ImageTk.PhotoImage(img, master=self)
        self.create_image(0, 0, image=self._foto, anchor="nw")
        texto = texto if texto is not None else f"{round(fracao * 100)}"
        f = tkfont.Font(family=FONTE_SEMI, size=tamanho_fonte)
        fs = tkfont.Font(family=FONTE, size=max(7, tamanho_fonte // 2))
        largura = f.measure(texto) + (fs.measure(sufixo) + 2 if sufixo else 0)
        x = (tamanho - largura) / 2
        cy = tamanho / 2 - (6 if legenda else 0)
        self.create_text(x, cy, text=texto, font=f, fill=TEMA["titulo"], anchor="w")
        if sufixo:
            self.create_text(x + f.measure(texto) + 2, cy + tamanho_fonte * 0.25, text=sufixo,
                             font=fs, fill=TEMA["texto_fraco"], anchor="w")
        if legenda:
            self.create_text(tamanho / 2, cy + tamanho_fonte + 2, text=espacar(legenda),
                             font=fonte(6, "semi"), fill=TEMA["texto_fraco"])


class Donut(tk.Canvas):
    """Donut com várias fatias e número grande no centro."""

    def __init__(self, parent, fatias, tamanho=130, espessura=16, texto="", legenda="", **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=tamanho, height=tamanho, **kw)
        total = sum(v for v, _ in fatias) or 1
        img = _imagem_anel(tamanho, espessura, [(v / total, c) for v, c in fatias],
                           TEMA["trilha"], None)
        self._foto = ImageTk.PhotoImage(img, master=self)
        self.create_image(0, 0, image=self._foto, anchor="nw")
        self.create_text(tamanho / 2, tamanho / 2 - 6, text=texto, font=fonte(22, "semi"),
                         fill=TEMA["titulo"])
        if legenda:
            self.create_text(tamanho / 2, tamanho / 2 + 18, text=espacar(legenda),
                             font=fonte(7, "semi"), fill=TEMA["texto_fraco"])


class GraficoBarras(tk.Canvas):
    """Barras agrupadas (uma série por cor) com linhas de grade leves e
    rótulos embaixo — "Atividade de revisões" do protótipo."""

    def __init__(self, parent, rotulos, series, cores, altura=230, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         height=altura, width=kw.pop("width", 400), **kw)
        self.rotulos = rotulos
        self.series = series
        self.cores = cores
        self.bind("<Configure>", lambda e: self._desenhar())

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        base = h - 26
        topo = 10
        maximo = max([max(s) if s else 0 for s in self.series] + [1])
        for i in range(5):
            y = topo + (base - topo) * i / 4
            self.create_line(0, y, w, y, fill=TEMA["linha"])
        n = max(1, len(self.rotulos))
        largura_grupo = w / n
        largura_barra = min(14, largura_grupo / (len(self.series) + 2))
        for i, rotulo in enumerate(self.rotulos):
            cx = largura_grupo * (i + 0.5)
            total = largura_barra * len(self.series) + 4 * (len(self.series) - 1)
            x = cx - total / 2
            for serie, cor in zip(self.series, self.cores):
                valor = serie[i] if i < len(serie) else 0
                altura_barra = (base - topo) * valor / maximo
                if altura_barra >= 1:
                    retangulo_arredondado(self, x, base - altura_barra, x + largura_barra, base + 3,
                                          min(3, int(largura_barra // 2)), cor)
                x += largura_barra + 4
            self.create_text(cx, base + 14, text=rotulo, font=fonte(9), fill=TEMA["texto_fraco"])
        self.create_line(0, base, w, base, fill=TEMA["card_borda"])


# ---------------------------------------------------------------------------
# campos
# ---------------------------------------------------------------------------
class CampoArredondado(tk.Canvas):
    """Entrada de texto dentro de uma moldura arredondada, com ícone à
    esquerda e texto de exemplo (placeholder) opcional. O tk.Entry fica
    em `self.entry`."""

    def __init__(self, parent, placeholder="", icone_esquerda=None, largura=320, altura=38,
                 cor=None, borda="padrao", tamanho_fonte=10, extra_direita=None, **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=largura, height=altura, **kw)
        self.cor = cor or TEMA["card"]
        self.borda = TEMA["card_borda"] if borda == "padrao" else borda
        self.placeholder = placeholder
        self.icone_esquerda = icone_esquerda
        self.altura = altura
        self.extra_direita = extra_direita
        self.entry = tk.Entry(self, relief="flat", bd=0, bg=self.cor, fg=TEMA["titulo"],
                              insertbackground=TEMA["titulo"], highlightthickness=0,
                              font=fonte(tamanho_fonte))
        self._janela = self.create_window(0, altura / 2, window=self.entry, anchor="w")
        self._ph_ativo = False
        self.entry.bind("<FocusIn>", self._tirar_placeholder, add="+")
        self.entry.bind("<FocusOut>", self._por_placeholder, add="+")
        self._por_placeholder()
        self.bind("<Configure>", self._redesenhar)
        self.bind("<Button-1>", lambda e: self.entry.focus_set())

    def _redesenhar(self, evento):
        w, h = evento.width, evento.height
        self.delete("fundo")
        retangulo_arredondado(self, 0, 0, w, h, 8, self.cor, self.borda, tag="fundo")
        x = 12
        if self.icone_esquerda:
            self.create_text(12, h / 2, text=self.icone_esquerda, font=(FONTE_ICONE, 10),
                             fill=TEMA["texto_fraco"], anchor="w", tags=("fundo",))
            x = 36
        direita = 12 + (self.extra_direita or 0)
        self.coords(self._janela, x, h / 2)
        self.itemconfig(self._janela, width=max(10, w - x - direita), height=h - 12)
        self.tag_lower("fundo")

    def _tirar_placeholder(self, _e=None):
        if self._ph_ativo:
            self._ph_ativo = False
            self.entry.delete(0, tk.END)
            self.entry.config(fg=TEMA["titulo"])

    def _por_placeholder(self, _e=None):
        if self.placeholder and not self.entry.get():
            self._ph_ativo = True
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=TEMA["texto_fraco"])

    def get(self):
        return "" if self._ph_ativo else self.entry.get()

    def set(self, texto):
        self._tirar_placeholder()
        self.entry.delete(0, tk.END)
        self.entry.insert(0, texto)
        if not texto and self.focus_get() is not self.entry:
            self._por_placeholder()


def configurar_estilos_ttk(raiz):
    """Estilos ttk usados pelas telas novas: Treeview "de cartão" (linhas
    altas, sem bordas, cabeçalho discreto) e Combobox plano sem a seta
    nativa (a seta é desenhada à parte pelo `ComboArredondado`)."""
    style = ttk.Style(raiz)
    style.configure("Cartao.Treeview", background=TEMA["card"], fieldbackground=TEMA["card"],
                    foreground=TEMA["titulo"], borderwidth=0, rowheight=40, font=fonte(10))
    style.configure("Cartao.Treeview.Heading", background=TEMA["card"], foreground=TEMA["eyebrow"],
                    relief="flat", borderwidth=0, font=fonte(8, "semi"), padding=(6, 8))
    style.map("Cartao.Treeview", background=[("selected", TEMA["sidebar_sel"])],
              foreground=[("selected", TEMA["titulo"])])
    style.map("Cartao.Treeview.Heading", background=[("active", TEMA["card"])])
    style.layout("Cartao.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    style.layout("Plano.TCombobox", [
        ("Combobox.padding", {"expand": "1", "sticky": "nswe", "children": [
            ("Combobox.textarea", {"sticky": "nswe"})]})])
    style.configure("Plano.TCombobox", fieldbackground=TEMA["card"], background=TEMA["card"],
                    foreground=TEMA["titulo"], borderwidth=0, padding=0,
                    selectbackground=TEMA["card"], selectforeground=TEMA["titulo"])
    style.map("Plano.TCombobox", fieldbackground=[("readonly", TEMA["card"])],
              selectbackground=[("readonly", TEMA["card"])],
              selectforeground=[("readonly", TEMA["titulo"])])
    style.configure("Fino.Horizontal.TScrollbar", background=TEMA["card_borda"], troughcolor=TEMA["pagina"],
                    bordercolor=TEMA["pagina"], arrowsize=0, width=8, relief="flat")
    style.configure("Fino.Vertical.TScrollbar", background=TEMA["card_borda"], troughcolor=TEMA["pagina"],
                    bordercolor=TEMA["pagina"], arrowsize=0, width=8, relief="flat")
    style.configure("Placeholder.Plano.TCombobox", fieldbackground=TEMA["card"], background=TEMA["card"],
                    foreground=TEMA["texto_fraco"], borderwidth=0, padding=0,
                    selectbackground=TEMA["card"], selectforeground=TEMA["texto_fraco"])
    style.map("Placeholder.Plano.TCombobox", fieldbackground=[("readonly", TEMA["card"])],
              foreground=[("readonly", TEMA["texto_fraco"])],
              selectbackground=[("readonly", TEMA["card"])],
              selectforeground=[("readonly", TEMA["texto_fraco"])])
    style.layout("Placeholder.Plano.TCombobox", style.layout("Plano.TCombobox"))
    raiz.option_add("*TCombobox*Listbox.font", fonte(10))
    raiz.option_add("*TCombobox*Listbox.background", TEMA["card"])
    raiz.option_add("*TCombobox*Listbox.foreground", TEMA["titulo"])
    raiz.option_add("*TCombobox*Listbox.selectBackground", TEMA["primario"])
    raiz.option_add("*TCombobox*Listbox.selectForeground", TEMA["primario_texto"])


class ComboArredondado(tk.Canvas):
    """Combobox dentro de moldura arredondada: ícone à esquerda, divisória
    e chevron à direita (como "Obra (Nº Cadari)" no protótipo). Com
    `filtrar=True` (combo editável), a lista se restringe ao que já foi
    digitado — útil para a lista longa de obras."""

    def __init__(self, parent, valores, icone_esquerda=None, largura=320, altura=40,
                 editavel=False, filtrar=False, placeholder="", **kw):
        super().__init__(parent, bg=cor_fundo_de(parent), highlightthickness=0, bd=0,
                         width=largura, height=altura, **kw)
        self.valores = list(valores)
        self.icone_esquerda = icone_esquerda
        self.combo = ttk.Combobox(self, values=self.valores, style="Plano.TCombobox",
                                  state="normal" if editavel else "readonly", font=fonte(10))
        self._janela = self.create_window(0, altura / 2, window=self.combo, anchor="w")
        self._placeholder = placeholder
        self._ph_ativo = False
        if placeholder:
            self.combo.bind("<FocusIn>", self._tirar_placeholder, add="+")
            self.combo.bind("<FocusOut>", self._por_placeholder, add="+")
            self.combo.bind("<<ComboboxSelected>>", self._tirar_placeholder, add="+")
            self._por_placeholder()
        self._sugestoes = None  # janela de autocompletar (lista suspensa digitável)
        self.rotulos = {}       # valor -> texto extra mostrado na sugestão (ex.: nome do projeto)
        if filtrar:
            self.combo.bind("<KeyRelease>", self._filtrar, add="+")
            self.combo.bind("<Down>", lambda e: self._mover_sugestao(1), add="+")
            self.combo.bind("<Up>", lambda e: self._mover_sugestao(-1), add="+")
            self.combo.bind("<Return>", self._aceitar_sugestao, add="+")
            self.combo.bind("<Escape>", lambda e: self._fechar_sugestoes(), add="+")
            self.combo.bind("<FocusOut>", lambda e: self.after(150, self._fechar_sugestoes), add="+")
        self.bind("<Configure>", self._redesenhar)
        self.bind("<Destroy>", lambda e: self._fechar_sugestoes() if e.widget is self else None, add="+")
        self.tag_bind("seta", "<Button-1>", lambda e: self.abrir())
        self.bind("<Button-1>", lambda e: self.abrir() if self.combo.cget("state") == "readonly" else None)

    def _redesenhar(self, evento):
        w, h = evento.width, evento.height
        self.delete("fundo")
        self.delete("seta")
        retangulo_arredondado(self, 0, 0, w, h, 8, TEMA["card"], TEMA["card_borda"], tag="fundo")
        x = 12
        if self.icone_esquerda:
            self.create_text(14, h / 2, text=self.icone_esquerda, font=(FONTE_ICONE, 10),
                             fill=TEMA["titulo"], anchor="w", tags=("fundo",))
            x = 40
        self.create_line(w - 44, 0, w - 44, h, fill=TEMA["card_borda"], tags=("fundo",))
        self.create_rectangle(w - 43, 1, w - 1, h - 1, fill=TEMA["card"], width=0, tags=("seta",))
        self.create_text(w - 22, h / 2, text=Icone.CHEVRON_BAIXO, font=(FONTE_ICONE, 10),
                         fill=TEMA["titulo"], tags=("seta",))
        self.coords(self._janela, x, h / 2)
        self.itemconfig(self._janela, width=max(10, w - x - 52), height=h - 10)
        self.tag_lower("fundo")
        self.config(cursor="hand2")

    def _filtrar(self, evento):
        if evento.keysym in ("Down", "Up", "Return", "Escape", "Tab", "Shift_L", "Shift_R"):
            return
        texto = self.combo.get().strip().lower()
        if not texto:
            self.combo["values"] = self.valores
            self._fechar_sugestoes()
            return
        achados = [v for v in self.valores
                   if texto in str(v).lower() or texto in self.rotulos.get(v, "").lower()]
        self.combo["values"] = achados
        self._mostrar_sugestoes(achados[:10])

    # ---------- lista suspensa enquanto digita (sem roubar o foco do campo) ----------
    def _mostrar_sugestoes(self, valores):
        if not valores:
            self._fechar_sugestoes()
            return
        if self._sugestoes is None:
            janela = tk.Toplevel(self)
            janela.overrideredirect(True)
            janela.attributes("-topmost", True)
            lista = tk.Listbox(janela, activestyle="none", relief="flat", bd=0, highlightthickness=1,
                               highlightbackground=TEMA["card_borda"], bg=TEMA["card"], fg=TEMA["titulo"],
                               selectbackground=TEMA["sidebar_sel"], selectforeground=TEMA["titulo"],
                               font=fonte(10))
            lista.pack(fill=tk.BOTH, expand=True)
            lista.bind("<ButtonRelease-1>", self._aceitar_sugestao)
            self._sugestoes = (janela, lista)
        janela, lista = self._sugestoes
        lista.delete(0, tk.END)
        self._valores_sugeridos = list(valores)
        for v in valores:
            extra = self.rotulos.get(v)
            lista.insert(tk.END, f"{v}   ·   {extra}" if extra else str(v))
        lista.selection_set(0)
        x, y = self.winfo_rootx(), self.winfo_rooty() + self.winfo_height() + 2
        altura = min(10, len(valores)) * 24 + 4
        janela.geometry(f"{max(self.winfo_width(), 260)}x{altura}+{x}+{y}")
        janela.deiconify()

    def _fechar_sugestoes(self):
        if self._sugestoes is not None:
            try:
                self._sugestoes[0].destroy()
            except tk.TclError:
                pass
            self._sugestoes = None

    def _mover_sugestao(self, passo):
        if self._sugestoes is None:
            return None
        lista = self._sugestoes[1]
        atual = (lista.curselection() or (0,))[0]
        novo = max(0, min(lista.size() - 1, atual + passo))
        lista.selection_clear(0, tk.END)
        lista.selection_set(novo)
        lista.see(novo)
        return "break"

    def _aceitar_sugestao(self, _evento=None):
        if self._sugestoes is None:
            return None
        lista = self._sugestoes[1]
        selecao = lista.curselection()
        if selecao:
            self._tirar_placeholder()
            self.combo.set(self._valores_sugeridos[selecao[0]])
            self.combo.icursor(tk.END)
            self.combo.event_generate("<<ComboboxSelected>>")
        self._fechar_sugestoes()
        return "break"

    def _tirar_placeholder(self, _e=None):
        if self._ph_ativo:
            self._ph_ativo = False
            if self.combo.get() == self._placeholder:
                self.combo.set("")
            self.combo.configure(style="Plano.TCombobox")

    def _por_placeholder(self, _e=None):
        if self._placeholder and not self.combo.get():
            self._ph_ativo = True
            self.combo.set(self._placeholder)
            self.combo.configure(style="Placeholder.Plano.TCombobox")

    def abrir(self):
        try:
            self.combo.focus_set()
            self.combo.tk.call("ttk::combobox::Post", self.combo)
        except tk.TclError:
            pass

    def get(self):
        return "" if self._ph_ativo else self.combo.get()

    def set(self, valor):
        self._tirar_placeholder()
        self.combo.set(valor)
        if not valor and self.focus_get() is not self.combo:
            self._por_placeholder()


class AreaRolavel(tk.Frame):
    """Área com rolagem vertical para páginas mais altas que a janela.
    O conteúdo vai em `self.interno`. A roda do mouse só é capturada
    enquanto o ponteiro está sobre a área (e ignorada sobre widgets que
    já rolam sozinhos, como Treeview/Text)."""

    def __init__(self, parent, cor=None, **kw):
        cor = cor or TEMA["pagina"]
        super().__init__(parent, bg=cor, **kw)
        self.canvas = tk.Canvas(self, bg=cor, highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview,
                                   style="Fino.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self._ao_rolar)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.interno = tk.Frame(self.canvas, bg=cor)
        self._janela = self.canvas.create_window(0, 0, window=self.interno, anchor="nw")
        self.interno.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._janela, width=e.width))
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._roda))
        self.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))
        self.bind("<Destroy>", lambda e: self.unbind_all("<MouseWheel>") if e.widget is self else None)

    def _ao_rolar(self, primeiro, ultimo):
        self.barra.set(primeiro, ultimo)
        if float(primeiro) <= 0.0 and float(ultimo) >= 1.0:
            self.barra.pack_forget()
        elif not self.barra.winfo_ismapped():
            self.barra.pack(side=tk.RIGHT, fill=tk.Y, before=self.canvas)

    def _roda(self, evento):
        widget = evento.widget
        if isinstance(widget, (ttk.Treeview, tk.Text, tk.Listbox)):
            return
        try:
            if not str(widget).startswith(str(self)):
                return
        except Exception:
            return
        primeiro, ultimo = self.canvas.yview()
        if primeiro <= 0.0 and ultimo >= 1.0:
            return
        self.canvas.yview_scroll(int(-evento.delta / 120) * 3, "units")
