"""Corretor ortográfico (português) para as caixas de texto do app:
sublinha em vermelho as palavras desconhecidas e, no botão direito,
oferece sugestões, "Adicionar ao dicionário" e "Ignorar".

Dicionário: pyspellchecker (pt, ~400 mil palavras, offline), mais um
vocabulário técnico da empresa e o dicionário pessoal de cada usuário
(preferencias.json). O carregamento (~1 s) roda em segundo plano na
primeira vez; até lá, simplesmente não sublinha nada.

`sugestoes()` procura primeiro a mesma palavra com acentos ("tubulacao"
-> "tubulação"), o erro mais comum ao digitar rápido, e depois as
correções por distância de edição."""
import re
import threading
import tkinter as tk
import unicodedata

from config import LISTA_DISCIPLINAS, TEMA
from ui import preferencias

PALAVRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿ]+)*")
VOCABULARIO_TECNICO = {
    "bim", "ifc", "pdf", "bcf", "cad", "dwg", "revit", "navisworks", "shaft", "shafts", "sprinkler",
    "sprinklers", "drywall", "layout", "layouts", "clash", "clashes", "cadari", "vizzo", "hvac", "spda",
    "prumada", "prumadas", "pavimento", "subsolo", "mezanino", "eletrocalha", "eletrocalhas", "eletroduto",
    "eletrodutos", "luminotécnico", "hidrossanitário", "hidrossanitária", "fancoil", "fancoils", "chiller",
    "damper", "dampers", "selagem", "split", "splits", "rev", "obs", "ok",
    # o dicionário base mistura grafias de Portugal: termos de obra e grafias do Brasil que faltam nele
    "tubulação", "tubulações", "duto", "dutos", "hidrante", "hidrantes", "detector", "detectores",
    "aterramento", "detalhamento", "detalhamentos", "contato", "contatos", "registro", "registros",
    "registrar", "registrado", "registrada", "registrou", "fone", "time", "esquadria", "esquadrias",
    "drywall", "projetista", "projetistas",
}
# Brasil x Portugal: econômico/económico, anônimo/anónimo, gênero/género...
_VARIANTES_BR_PT = str.maketrans({"ô": "ó", "ê": "é"})


def _sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


class _Corretor:
    def __init__(self):
        self._sp = None
        self._por_forma_sem_acento = None
        self._pessoal = set(preferencias.carregar().get("dicionario", []))
        self._ignoradas = set()
        self._carregando = False
        self.indisponivel = False

    def carregar_em_segundo_plano(self):
        if self._sp is not None or self._carregando or self.indisponivel:
            return
        self._carregando = True
        threading.Thread(target=self._carregar, daemon=True).start()

    def _carregar(self):
        try:
            from spellchecker import SpellChecker
            sp = SpellChecker(language="pt", distance=2)
            sp.word_frequency.load_words(sorted(VOCABULARIO_TECNICO | self._pessoal))
            mapa = {}
            for palavra in sp.word_frequency.keys():
                chave = _sem_acento(palavra)
                if chave != palavra:
                    mapa.setdefault(chave, palavra)
            self._por_forma_sem_acento = mapa
            self._sp = sp
        except Exception:
            self.indisponivel = True  # sem a biblioteca/dicionário: o app segue sem corretor
        finally:
            self._carregando = False

    @property
    def pronto(self):
        return self._sp is not None

    def errada(self, palavra):
        if not self.pronto or len(palavra) < 3:
            return False
        if palavra.isupper() and len(palavra) <= 6:
            return False  # siglas (ADI, PCI, ART...)
        minuscula = palavra.lower()
        if (minuscula in VOCABULARIO_TECNICO or minuscula in self._pessoal or minuscula in self._ignoradas
                or palavra.upper() in LISTA_DISCIPLINAS):
            return False
        partes = minuscula.split("-")
        return any(p and p not in self._sp and p.translate(_VARIANTES_BR_PT) not in self._sp
                   and p not in VOCABULARIO_TECNICO for p in partes)

    def sugestoes(self, palavra, limite=6):
        if not self.pronto:
            return []
        minuscula = palavra.lower()
        resultado = []
        acentuada = self._por_forma_sem_acento.get(_sem_acento(minuscula))
        if acentuada:
            resultado.append(acentuada)
        candidatos = self._sp.candidates(minuscula) or set()
        ordenados = sorted(candidatos, key=lambda c: -self._sp.word_usage_frequency(c))
        for c in ordenados:
            if c not in resultado and c != minuscula:
                resultado.append(c)
        if palavra[:1].isupper():
            resultado = [r[:1].upper() + r[1:] for r in resultado]
        return resultado[:limite]

    def adicionar(self, palavra):
        self._pessoal.add(palavra.lower())
        preferencias.salvar(dicionario=sorted(self._pessoal))

    def ignorar(self, palavra):
        self._ignoradas.add(palavra.lower())


CORRETOR = _Corretor()


def ativar_corretor(texto):
    """Liga o corretor num `tk.Text`."""
    CORRETOR.carregar_em_segundo_plano()
    try:
        texto.tag_configure("erro_ortografia", underline=True, underlinefg="#D9534F")
    except tk.TclError:  # Tk antigo sem underlinefg
        texto.tag_configure("erro_ortografia", underline=True)
    estado = {"agendado": None}

    def verificar():
        estado["agendado"] = None
        if not texto.winfo_exists():
            return
        if not CORRETOR.pronto:
            if not CORRETOR.indisponivel:
                estado["agendado"] = texto.after(700, verificar)  # dicionário ainda carregando
            return
        texto.tag_remove("erro_ortografia", "1.0", tk.END)
        conteudo = texto.get("1.0", "end-1c")
        if str(texto.cget("fg")).lower() == str(TEMA["texto_fraco"]).lower():
            return  # placeholder ("Adicione um comentário...") não é texto do usuário
        for m in PALAVRA.finditer(conteudo):
            if m.start() > 0 and conteudo[m.start() - 1] == "@":
                continue  # menção a pessoa
            if CORRETOR.errada(m.group()):
                texto.tag_add("erro_ortografia", f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def agendar(_e=None):
        if estado["agendado"]:
            texto.after_cancel(estado["agendado"])
        estado["agendado"] = texto.after(350, verificar)

    def menu_contexto(evento):
        indice = texto.index(f"@{evento.x},{evento.y}")
        intervalo = texto.tag_prevrange("erro_ortografia", f"{indice}+1c")
        menu = tk.Menu(texto, tearoff=0)
        if intervalo and texto.compare(intervalo[0], "<=", indice) and texto.compare(indice, "<=", intervalo[1]):
            inicio, fim = intervalo
            palavra = texto.get(inicio, fim)
            opcoes = CORRETOR.sugestoes(palavra)
            for s in opcoes:
                menu.add_command(label=s, font=("Segoe UI", 10, "bold"),
                                 command=lambda s=s, i=inicio, f=fim: (texto.delete(i, f), texto.insert(i, s), agendar()))
            if not opcoes:
                menu.add_command(label="(sem sugestões)", state="disabled")
            menu.add_separator()
            menu.add_command(label=f"Adicionar \"{palavra}\" ao dicionário",
                             command=lambda: (CORRETOR.adicionar(palavra), agendar()))
            menu.add_command(label="Ignorar", command=lambda: (CORRETOR.ignorar(palavra), agendar()))
            menu.add_separator()
        menu.add_command(label="Recortar", command=lambda: texto.event_generate("<<Cut>>"))
        menu.add_command(label="Copiar", command=lambda: texto.event_generate("<<Copy>>"))
        menu.add_command(label="Colar", command=lambda: texto.event_generate("<<Paste>>"))
        menu.tk_popup(evento.x_root, evento.y_root)

    texto.bind("<KeyRelease>", agendar, add="+")
    texto.bind("<FocusIn>", agendar, add="+")
    texto.bind("<<Paste>>", lambda e: texto.after(10, agendar), add="+")
    texto.bind("<Button-3>", menu_contexto, add="+")
    agendar()
    return texto
