"""Base dos diálogos modais no estilo do protótipo ("Projeto Analisado"):
uma camada sem bordas cobre a janela do app com uma cópia desfocada e
clareada dela (vidro fosco) e o cartão arredondado fica no centro, com
sombra, ícone, título, texto, campos e botões Cancelar/Confirmar.

Uso: a subclasse chama `_abrir_modal(...)`, posiciona os campos com
`_rotulo`/`_colocar` (y relativo ao cartão), chama `_botoes(...)` e por
fim `_exibir(foco)` — que bloqueia até o diálogo fechar."""
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageGrab, ImageTk

from config import TEMA
from ui.componentes import FONTE_ICONE, Botao, Icone, fonte, retangulo_arredondado

MARGEM = 24


class ModalCartao(tk.Toplevel):
    def _abrir_modal(self, parent, titulo, texto, icone=Icone.RELATORIO, largura=400, altura=460):
        """Prepara a camada e o cartão; devolve o y (relativo ao cartão)
        onde o conteúdo começa, logo abaixo do texto de apresentação."""
        tk.Toplevel.__init__(self, parent, bg=TEMA["card"])
        self.withdraw()  # invisível até o print do fundo — senão ele mesmo sai no print
        self.title(titulo)
        self.largura_cartao, self.altura_cartao = largura, altura

        parent.update_idletasks()
        janela = parent.winfo_toplevel()
        self._janela_dona = janela
        x, y = janela.winfo_rootx(), janela.winfo_rooty()
        w = max(janela.winfo_width(), largura + 40)
        h = max(janela.winfo_height(), altura + 40)
        self.overrideredirect(True)
        self.geometry(f"{w}x{h}+{x}+{y}")

        fundo = self._capturar_fundo(x, y, w, h)
        self.x0, self.y0 = (w - largura) // 2, max(10, (h - altura) // 2)
        fundo = self._desenhar_cartao(fundo, self.x0, self.y0)
        self._foto_fundo = ImageTk.PhotoImage(fundo, master=self)

        c = tk.Canvas(self, width=w, height=h, highlightthickness=0, bd=0, bg=TEMA["card"])
        c.pack(fill=tk.BOTH, expand=True)
        c.create_image(0, 0, image=self._foto_fundo, anchor="nw")
        self.canvas = c

        x0, y0, m = self.x0, self.y0, MARGEM
        retangulo_arredondado(c, x0 + m, y0 + 24, x0 + m + 46, y0 + 70, 9, TEMA["card"], TEMA["card_borda"])
        c.create_text(x0 + m + 23, y0 + 47, text=icone, font=(FONTE_ICONE, 16), fill=TEMA["titulo"])
        xf = x0 + largura - m
        retangulo_arredondado(c, xf - 36, y0 + 20, xf, y0 + 56, 8, TEMA["campo"], tag="fechar")
        c.create_text(xf - 18, y0 + 38, text=Icone.FECHAR, font=(FONTE_ICONE, 10), fill=TEMA["texto"],
                      tags=("fechar",))
        c.tag_bind("fechar", "<Button-1>", lambda e: self.cancelar())
        c.tag_bind("fechar", "<Enter>", lambda e: c.config(cursor="hand2"))
        c.tag_bind("fechar", "<Leave>", lambda e: c.config(cursor=""))

        c.create_text(x0 + m, y0 + 96, text=titulo, anchor="w", fill=TEMA["titulo"], font=fonte(14, "semi"))
        fim_texto = y0 + 112
        if texto:
            item = c.create_text(x0 + m, y0 + 114, anchor="nw", width=self.largura_util, fill=TEMA["texto"],
                                 font=fonte(10), text=texto)
            fim_texto = c.bbox(item)[3]
        self.bind("<Escape>", lambda e: self.cancelar())
        return fim_texto - y0 + 18

    @property
    def largura_util(self):
        return self.largura_cartao - 2 * MARGEM

    def _capturar_fundo(self, x, y, w, h):
        veu = (255, 255, 255) if not TEMA.esta_escuro() else (8, 26, 32)
        try:
            img = ImageGrab.grab((x, y, x + w, y + h), all_screens=True).convert("RGB")
            if img.size != (w, h):
                img = img.resize((w, h))
            img = img.filter(ImageFilter.GaussianBlur(5))
            return Image.blend(img, Image.new("RGB", img.size, veu), 0.45)
        except Exception:
            return Image.new("RGB", (w, h), (205, 214, 218) if not TEMA.esta_escuro() else (8, 26, 32))

    def _desenhar_cartao(self, fundo, x0, y0):
        s = 3
        lw, lh = self.largura_cartao, self.altura_cartao
        sombra = Image.new("RGBA", fundo.size, (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle((x0, y0 + 10, x0 + lw, y0 + lh + 10), radius=14,
                                                 fill=(10, 30, 40, 60))
        sombra = sombra.filter(ImageFilter.GaussianBlur(18))
        fundo = fundo.convert("RGBA")
        fundo.alpha_composite(sombra)
        cartao = Image.new("RGBA", (lw * s, lh * s), (0, 0, 0, 0))
        ImageDraw.Draw(cartao).rounded_rectangle((0, 0, lw * s - 1, lh * s - 1), radius=12 * s,
                                                 fill=TEMA["card"], outline=TEMA["card_borda"], width=s)
        fundo.alpha_composite(cartao.resize((lw, lh), Image.LANCZOS), (x0, y0))
        return fundo.convert("RGB")

    # ---------- montagem ----------
    def _rotulo(self, texto, y, x=0):
        self.canvas.create_text(self.x0 + MARGEM + x, self.y0 + y, anchor="w", text=texto,
                                fill=TEMA["titulo"], font=fonte(10))

    def _colocar(self, widget, y, x=0):
        self.canvas.create_window(self.x0 + MARGEM + x, self.y0 + y, window=widget, anchor="nw")
        return widget

    def _botoes(self, texto_cancelar="Cancelar", texto_confirmar="Confirmar"):
        largura_botao = (self.largura_util - 10) // 2
        y = self.y0 + self.altura_cartao - MARGEM - 40
        Botao(self.canvas, texto_cancelar, comando=self.cancelar, variante="secundario",
              largura=largura_botao, altura=40, tamanho_fonte=10).place(x=self.x0 + MARGEM, y=y)
        Botao(self.canvas, texto_confirmar, comando=self.confirmar, variante="primario",
              largura=largura_botao, altura=40, tamanho_fonte=10
              ).place(x=self.x0 + MARGEM + largura_botao + 10, y=y)
        self.lbl_erro = self.canvas.create_text(
            self.x0 + MARGEM, y - 16, anchor="w", text="", fill=TEMA["pill_vermelho"][1], font=fonte(9),
            width=self.largura_util)

    def mostrar_erro(self, texto):
        self.canvas.itemconfig(self.lbl_erro, text=texto)

    def _exibir(self, foco=None):
        if self._janela_dona.winfo_viewable():
            self.transient(self._janela_dona)
        self.deiconify()
        self.lift()
        self.focus_force()
        if foco is not None:
            foco.focus_set()
        self.grab_set()
        self.wait_window(self)

    # ---------- ações (sobrescrever) ----------
    def cancelar(self):
        self.destroy()

    def confirmar(self):
        self.destroy()
