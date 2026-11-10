"""Atalhos de teclado das telas de trabalho (visualizadores PDF e IFC) e
dicas flutuantes ("tooltip") que mostram o atalho de cada ferramenta.

Os atalhos são teclas simples (sem Ctrl) e só valem enquanto a tela
existe; são ignorados quando o foco está num campo de texto (para não
atrapalhar quem está digitando um comentário) ou em outra janela."""
import tkinter as tk
from tkinter import ttk

from config import TEMA
from ui.componentes import fonte

_CAMPOS_TEXTO = (tk.Entry, tk.Text, tk.Spinbox, ttk.Entry, ttk.Combobox)


def instalar_atalhos(tela, mapa):
    """`mapa`: {tecla: função} — tecla como `event.keysym` (minúscula
    para letras, ex.: "c", "plus", "Escape", "Next")."""

    def ao_teclar(evento):
        try:
            if not tela.winfo_exists():
                return None
            widget = evento.widget
            if isinstance(widget, str) or isinstance(widget, _CAMPOS_TEXTO):
                return None
            if widget.winfo_toplevel() is not tela.winfo_toplevel():
                return None  # diálogo aberto por cima
        except (tk.TclError, KeyError, AttributeError):
            return None
        if evento.state & 0x4:  # Ctrl+tecla fica para os atalhos globais (ex.: Ctrl+K)
            return None
        funcao = mapa.get(evento.keysym) or mapa.get(evento.keysym.lower())
        if funcao is None:
            return None
        funcao()
        return "break"

    tela.bind_all("<KeyPress>", ao_teclar)
    tela.bind("<Destroy>", lambda e: tela.unbind_all("<KeyPress>") if e.widget is tela else None, add="+")


class Dica:
    """Balão de ajuda que aparece após meio segundo com o mouse parado
    sobre o widget."""

    def __init__(self, widget, texto):
        self.widget, self.texto = widget, texto
        self._janela = None
        self._agendado = None
        widget.bind("<Enter>", self._agendar, add="+")
        widget.bind("<Leave>", self._esconder, add="+")
        widget.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _e=None):
        self._cancelar()
        self._agendado = self.widget.after(500, self._mostrar)

    def _cancelar(self):
        if self._agendado:
            self.widget.after_cancel(self._agendado)
            self._agendado = None

    def _mostrar(self):
        self._agendado = None
        if self._janela or not self.widget.winfo_exists():
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._janela = tk.Toplevel(self.widget)
        self._janela.overrideredirect(True)
        self._janela.attributes("-topmost", True)
        tk.Label(self._janela, text=self.texto, bg=TEMA["titulo"], fg=TEMA["card"], font=fonte(9),
                 padx=8, pady=4).pack()
        self._janela.geometry(f"+{x}+{y}")

    def _esconder(self, _e=None):
        self._cancelar()
        if self._janela is not None:
            self._janela.destroy()
            self._janela = None
