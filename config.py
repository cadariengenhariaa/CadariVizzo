"""Configurações e constantes compartilhadas do Visualizador Cadari de Projetos."""
import os

_DIR_PROJETO = os.path.dirname(os.path.abspath(__file__))

# --- CONFIGURAÇÕES DE REDE E DIRETÓRIOS ---
DB_DIR = r"Z:\Temporario\João Gabriel\Checklist de projetos issues"
DB_FILE = os.path.join(DB_DIR, "db_issues.json")
LOGO_PATH = r"Z:\Biblioteca\Padronização\Cadari\Logo\Marca PNG\Marca_Cadari-01.png"
OBRAS_FILE = r"Z:\Publico\RELAÇÃO DE PROJETOS.xlsm"  # cadastro de obras (col B, a partir de B7)
PROJETOS_DIR = r"Z:\Projetos\Ativos"  # pasta de cada obra: PROJETOS_DIR\<Nº Cadari> (ex.: CA-1439A)
SELOS_DIR = r"Z:\Biblioteca\Padronização\Cadari\SELOS"  # selos de aprovação (imagens) para carimbar pranchas
# "Ajuda e suporte" (barra lateral) abre o formulário de abertura de chamados da Cadari
CHAMADOS_EXE = r"Z:\Biblioteca\Padronização\Cadari\Executaveis\Abertura de Chamados.exe"
EMAIL_ADMIN_INICIAL = "bim2@cadariengenharia.com.br"  # bootstrap: vira administrador no 1º uso do app
NOME_USUARIO_ADMIN_INICIAL = "JoaoGabriel"  # login (nome de usuário) da conta criada no bootstrap

# Identidade do app "Cadari Vizzo" — empacotada no próprio projeto (não na
# rede Z:) para funcionar mesmo offline e ir junto no executável gerado.
LOGO_VIZZO_PATH = os.path.join(_DIR_PROJETO, "assets", "logo_cadari_vizzo.png")
ICONE_VIZZO_PNG = os.path.join(_DIR_PROJETO, "assets", "icone_cadari_vizzo.png")
ICONE_VIZZO_ICO = os.path.join(_DIR_PROJETO, "assets", "icone_cadari_vizzo.ico")
# Tela de login: foto da fachada (imagem "portfólio" do Figma); se faltar,
# cai para a textura listrada da marca.
FUNDO_LOGIN_FOTO = os.path.join(_DIR_PROJETO, "assets", "fundo_login.jpg")
FUNDO_LOGIN_TEXTURA = os.path.join(_DIR_PROJETO, "assets", "fundo_login_textura.jpg")
LOGO_VIZZO_LOGIN = os.path.join(_DIR_PROJETO, "assets", "logo_vizzo_login.png")
LOGO_CADARI_BRANCO = os.path.join(_DIR_PROJETO, "assets", "logo_cadari_branco.png")

# Paleta de cores predefinidas para as ferramentas de marcação livre do PDF
# (desenho, formas, balão, texto) — além dessas, o usuário pode escolher
# "Outra cor..." via seletor de cores do sistema.
LISTA_CORES_ANOTACAO = [
    "#FF3B30", "#FF9800", "#FFEB3B", "#4CAF50",
    "#2196F3", "#9C27B0", "#000000", "#FFFFFF",
]

LISTA_STATUS = ["Novo", "Respondido", "Reaberto", "Fechado"]
LISTA_TIPOS_PDF = ["Concepção", "Documentação", "Dúvida", "Incompatibilidade", "Outro"]
TIPO_PADRAO_PDF = "Documentação"  # causa sugerida ao criar um problema numa prancha
LISTA_TIPOS_IFC = ["Concepção", "Modelagem", "Incompatibilidade", "Dúvida", "Outro"]
LISTA_DISCIPLINAS = ["ADI", "HID", "PCI", "PRE", "CLI", "EXS"]

# Setores da empresa — cadastro de usuários (auth/).
SETOR_BIM = "Setor BIM"  # setor com privilégios de administrador (vide auth/dialogs.py)
SETOR_COORDENACAO = "Coordenação de projetos"  # vê o Dashboard de todos, mas não é administrador
LISTA_SETORES = [
    SETOR_BIM, SETOR_COORDENACAO, "Projetista HIS",
    "Projetista PCI", "Projetista HVAC", "Projetista ADI",
]

# Cores de status por modo de tema. `CORES_STATUS` (definido no fim do
# arquivo) é um mapeamento dinâmico: devolve as cores do modo atual.
#
# Os dois modos de daltonismo foram escolhidos simulando cada paleta com
# as matrizes de Machado et al. (2009) e medindo a menor diferença (ΔE,
# CIELAB) entre os 4 status — quanto maior, mais fácil de distinguir:
#   paleta padrão ............ protanopia 28 · deuteranopia 22 · tritanopia 39
#   vermelho-verde (abaixo) .. protanopia 50 · deuteranopia 34 · tritanopia 57
#   azul-amarelo (abaixo) .... tritanopia 50 (era 39)
# Vermelho-verde: eixo azul x laranja/amarelo e diferença de claridade (base
# Okabe-Ito). Azul-amarelo (tritan): evita azul x verde e azul x amarelo,
# usa magenta x turquesa e claro x escuro.
_CORES_STATUS_PADRAO = {
    "Novo": "#e74c3c",
    "Respondido": "#f39c12",
    "Reaberto": "#3E3BF3",
    "Fechado": "#2ecc71",
}
_CORES_STATUS_VERMELHO_VERDE = {
    "Novo": "#D55E00",        # vermelhão
    "Respondido": "#F0E442",  # amarelo
    "Reaberto": "#1A1A1A",    # preto
    "Fechado": "#0072B2",     # azul
}
_CORES_STATUS_AZUL_AMARELO = {
    "Novo": "#D81B60",        # magenta
    "Respondido": "#FFB000",  # âmbar
    "Reaberto": "#3D3D3D",    # grafite
    "Fechado": "#009E9E",     # turquesa
}

# --- CERTIFICAÇÃO (selos de aprovação das pranchas) ---
# O nome do arquivo do selo (ex.: "APR.png" em SELOS_DIR) define o status
# da prancha. Descrições ajustáveis aqui; a cor é a do próprio selo.
SELOS_STATUS = {
    "APR": {"descricao": "Aprovado", "cor": "#4A8A12"},
    "APCA": {"descricao": "Aprovado com anotações", "cor": "#C9A51F"},
    "APCR": {"descricao": "Aprovado com ressalvas", "cor": "#D9822B"},
    "RPV": {"descricao": "Reprovado", "cor": "#E2400B"},
}

# --- TEMA VISUAL: modo dia/noite ---
# Paleta baseada no Manual de Identidade Visual da Cadari (cores oficiais:
# azul petróleo #10475C/#17546C e dourado #BCA985/#AA9978, cinza claro
# #F1F2F2). `TEMA` é um objeto que resolve as cores em tempo real conforme
# `TEMA.modo`, então todo `TEMA["chave"]` espalhado pelo app já reflete o
# modo atual sem precisar mudar cada ponto de uso — só quem constrói a tela
# (ao trocar de modo, o app reconstrói a tela atual) precisa rodar de novo
# para os widgets pegarem a nova cor.
PALETA_ESCURA = {
    "bg": "#081A20",           # fundo geral das telas (azul petróleo bem escuro)
    "surface": "#10475C",      # barras de ferramentas, cabeçalho, rodapé (azul primário da marca)
    "surface_alt": "#17546C",  # painéis/cards dentro das telas (azul secundário da marca)
    "borda": "#2E6472",
    "texto": "#ECEFF4",
    "texto_fraco": "#9FB7BE",
    "acento": "#BCA985",        # dourado primário da marca
    "acento_hover": "#D1C2A2",
    "acento_texto": "#13343D",  # texto sobre fundo de acento (contraste)
    "sucesso": "#57C08A",
    "atencao": "#E8A33D",
    "critico": "#F05B5B",
    "info": "#5AA9F0",
    "fonte": ("Segoe UI", 10),
    "fonte_titulo": ("Segoe UI Semibold", 12),
    "fonte_mono": ("Consolas", 9),
    # --- telas no estilo do protótipo Figma (shell com barra lateral) ---
    "pagina": "#0B1F26",
    "card": "#11303A",
    "card_borda": "#1F4652",
    "titulo": "#F1F4F5",
    "eyebrow": "#9FB7BE",
    "primario": "#BCA985",
    "primario_hover": "#D1C2A2",
    "primario_texto": "#13343D",
    "linha": "#1C3F4A",
    "sidebar_sel": "#18414D",
    "sidebar_sel_borda": "#24525F",
    "campo": "#163844",
    "trilha": "#1F4652",
    "pill_azul": ("#173F4C", "#8FC3D6"),
    "pill_dourado": ("#3A3A2E", "#D8C7A3"),
    "pill_verde": ("#17402F", "#86D0A8"),
    "pill_vermelho": ("#4A2626", "#F2A39B"),
    "pill_cinza": ("#1C3A44", "#A9BCC2"),
    "grafico": ("#5AA9C9", "#BCA985", "#6BA48A", "#5D7781"),
}

PALETA_CLARA = {
    "bg": "#F4F6F7",            # cinza claro (protótipo Figma)
    "surface": "#FFFFFF",
    "surface_alt": "#EEF1F2",
    "borda": "#D9E0E3",
    "texto": "#26343B",
    "texto_fraco": "#5F6F76",
    "acento": "#AA9978",         # dourado secundário da marca (mais contraste no claro)
    "acento_hover": "#937F5A",
    "acento_texto": "#13343D",
    "sucesso": "#2E8B57",
    "atencao": "#B8790A",
    "critico": "#C4362D",
    "info": "#1D6FB8",
    "fonte": ("Segoe UI", 10),
    "fonte_titulo": ("Segoe UI Semibold", 12),
    "fonte_mono": ("Consolas", 9),
    "pagina": "#F4F6F7",
    "card": "#FFFFFF",
    "card_borda": "#E3E8EA",
    "titulo": "#1B262C",
    "eyebrow": "#5E6E75",
    "primario": "#14495D",
    "primario_hover": "#1B5A71",
    "primario_texto": "#FFFFFF",
    "linha": "#E9EDEF",
    "sidebar_sel": "#EDF1F3",
    "sidebar_sel_borda": "#DCE3E6",
    "campo": "#F1F4F5",
    "trilha": "#E3E8EA",
    "pill_azul": ("#E3EFF3", "#2C6377"),
    "pill_dourado": ("#F4EEE2", "#8A7650"),
    "pill_verde": ("#E4F1EA", "#3C7A5A"),
    "pill_vermelho": ("#FBE9E7", "#B0473C"),
    "pill_cinza": ("#EEF1F2", "#5F6F76"),
    "grafico": ("#14495D", "#BCA985", "#6BA48A", "#C5CDD1"),
}


# Modos de daltonismo: base clara, com as cores que carregam significado
# (status, positivo/negativo, gráficos) trocadas (ver comentário acima).
PALETA_DALTONICA_VV = dict(PALETA_CLARA)  # vermelho-verde (protanopia/deuteranopia)
PALETA_DALTONICA_VV.update({
    "sucesso": "#0072B2",
    "atencao": "#E69F00",
    "critico": "#D55E00",
    "info": "#56B4E9",
    "pill_azul": ("#DCEBF5", "#005A8C"),
    "pill_dourado": ("#FBF3C8", "#6B5E00"),
    "pill_verde": ("#DCEBF5", "#005A8C"),     # "positivo" = azul
    "pill_vermelho": ("#FBE3D3", "#A4480A"),  # "negativo" = vermelhão
    "grafico": ("#0072B2", "#E69F00", "#1A1A1A", "#56B4E9"),
})
PALETA_DALTONICA_AA = dict(PALETA_CLARA)  # azul-amarelo (tritanopia)
PALETA_DALTONICA_AA.update({
    "sucesso": "#009E9E",
    "atencao": "#FFB000",
    "critico": "#D81B60",
    "info": "#009E9E",
    "acento": "#8A6D00",
    "pill_azul": ("#DDF2F2", "#00696B"),
    "pill_dourado": ("#FFF0CC", "#7A5400"),
    "pill_verde": ("#DDF2F2", "#00696B"),     # "positivo" = turquesa
    "pill_vermelho": ("#FADDE7", "#A0124A"),  # "negativo" = magenta
    "grafico": ("#009E9E", "#D81B60", "#3D3D3D", "#FFB000"),
})

MODOS_TEMA = {
    "claro": "Dia",
    "escuro": "Noturno",
    "daltonico_vv": "Daltonismo vermelho-verde",
    "daltonico_aa": "Daltonismo azul-amarelo",
}
_MODOS_ANTIGOS = {"daltonico": "daltonico_vv"}


class _TemaDinamico:
    """Objeto tipo-dicionário cujo conteúdo muda conforme o modo atual
    (dia / noturno / daltônico) — permite `TEMA["acento"]` em todo o
    código sem precisar de uma referência mutável explícita em cada
    arquivo."""

    def __init__(self):
        # claro por padrão: é o modo do protótipo do Figma.
        self.modo = "claro"

    def _paleta(self):
        if self.modo == "escuro":
            return PALETA_ESCURA
        if self.modo == "daltonico_vv":
            return PALETA_DALTONICA_VV
        if self.modo == "daltonico_aa":
            return PALETA_DALTONICA_AA
        return PALETA_CLARA

    def __getitem__(self, chave):
        return self._paleta()[chave]

    def definir(self, modo):
        modo = _MODOS_ANTIGOS.get(modo, modo)
        self.modo = modo if modo in MODOS_TEMA else "claro"
        return self.modo

    def alternar(self):
        """Dia <-> noturno (o daltônico volta para o dia)."""
        return self.definir("claro" if self.modo == "escuro" else "escuro")

    def esta_escuro(self):
        return self.modo == "escuro"

    def eh_daltonico(self):
        return self.modo.startswith("daltonico")


TEMA = _TemaDinamico()


class _CoresStatusDinamicas(dict):
    """`CORES_STATUS["Novo"]` / `.get(...)` com as cores do modo atual
    (é um dict de verdade para quem itera ou passa adiante)."""

    def _atual(self):
        if TEMA.modo == "daltonico_vv":
            return _CORES_STATUS_VERMELHO_VERDE
        if TEMA.modo == "daltonico_aa":
            return _CORES_STATUS_AZUL_AMARELO
        return _CORES_STATUS_PADRAO

    def __getitem__(self, chave):
        return self._atual()[chave]

    def get(self, chave, padrao=None):
        return self._atual().get(chave, padrao)

    def __iter__(self):
        return iter(self._atual())

    def __len__(self):
        return len(self._atual())

    def __contains__(self, chave):
        return chave in self._atual()

    def items(self):
        return self._atual().items()

    def keys(self):
        return self._atual().keys()

    def values(self):
        return self._atual().values()


CORES_STATUS = _CoresStatusDinamicas(_CORES_STATUS_PADRAO)
