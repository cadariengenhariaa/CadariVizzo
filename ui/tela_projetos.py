"""Tela "Meus projetos" (protótipo Figma) — porta de entrada da Validação
de Pranchas (PDF) e da Validação de Modelo (IFC): banner, filtros por
situação e um cartão por obra com progresso, situação e responsáveis.
"Abrir projeto" leva ao visualizador já com a obra na sessão."""
import math
import threading
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from certificacao import certificacoes_por_obra, tom_claro
from config import CORES_STATUS, TEMA
from dashboard.dados_dashboard import filtrar_por_papel
from dashboard.dados_painel import (
    FILTROS_PROJETOS,
    SITUACAO_CERTIFICADO,
    SITUACAO_REVISAO,
    filtrar_projetos,
    resumo_projetos,
    tempo_relativo,
)
from projeto_vrf import contar_pranchas
from utils import carregar_anotacoes
from ui.componentes import (
    AreaRolavel,
    BarraSegmentada,
    Botao,
    Cartao,
    Icone,
    Pilula,
    Segmentado,
    cabecalho_pagina,
    espacar,
    fonte,
    icone,
    iniciais,
    rotulo,
    separador,
)

COLUNAS = 3
ALTURA_MINIATURA = 150
SITUACAO_EXIBIDA = {"Certificado": "Certificação"}


def _hex(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# imagens desenhadas (banner e miniaturas)
# ---------------------------------------------------------------------------
def imagem_banner(largura, altura, quantidade):
    s = 2
    w, h = largura * s, altura * s
    base = Image.new("RGB", (w, h))
    inicio, fim = _hex("#123F52"), _hex("#1A5A6E")
    gradiente = Image.linear_gradient("L").rotate(90).resize((w, h))
    base = Image.composite(Image.new("RGB", (w, h), fim), Image.new("RGB", (w, h), inicio), gradiente)
    d = ImageDraw.Draw(base, "RGBA")
    # círculos decorativos suaves à direita
    for r, alfa in ((h * 1.1, 14), (h * 0.75, 18)):
        cx, cy = w - h * 0.55, h * 0.35
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, alfa))
    # cartões inclinados atrás da pasta
    cx, cy = w - h * 1.25, h * 0.52
    for ang, dx, alfa in ((-8, -h * 0.28, 40), (7, h * 0.3, 55)):
        cartao = Image.new("RGBA", (int(h * 0.62), int(h * 0.44)), (0, 0, 0, 0))
        ImageDraw.Draw(cartao).rounded_rectangle((0, 0, cartao.width - 1, cartao.height - 1),
                                                 radius=10 * s, fill=(255, 255, 255, alfa),
                                                 outline=(255, 255, 255, 90), width=s)
        cartao = cartao.rotate(ang, expand=True, resample=Image.BICUBIC)
        base.paste(cartao, (int(cx + dx - cartao.width / 2), int(cy - cartao.height / 2 + h * 0.05)), cartao)
    # pasta dourada
    pw, ph = int(h * 0.62), int(h * 0.5)
    px, py = int(cx - pw / 2), int(cy - ph / 2)
    sombra = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((px + 6 * s, py + 10 * s, px + pw + 6 * s, py + ph + 10 * s),
                                             radius=12 * s, fill=(0, 0, 0, 70))
    base.paste(sombra.filter(ImageFilter.GaussianBlur(8 * s)), (0, 0), sombra.filter(ImageFilter.GaussianBlur(8 * s)))
    d = ImageDraw.Draw(base, "RGBA")
    d.rounded_rectangle((px, py - int(ph * 0.12), px + int(pw * 0.42), py + 10 * s), radius=8 * s,
                        fill=(170, 153, 120, 255))
    d.rounded_rectangle((px, py, px + pw, py + ph), radius=12 * s, fill=(196, 178, 140, 255))
    # selo com a quantidade
    r = 13 * s
    bx, by = px + pw - 2 * s, py - int(ph * 0.12)
    d.ellipse((bx - r, by - r, bx + r, by + r), fill=(255, 255, 255, 255))
    return base.resize((largura, altura), Image.LANCZOS), (bx / s, by / s), (cx / s, cy / s)


def imagem_miniatura(largura, altura, tipo_doc, semente, cor_card, raio=11, todos_os_cantos=False):
    s = 2
    w, h = largura * s, altura * s
    fundo = _hex(TEMA["campo"])
    linha_grade = _hex(TEMA["linha"])
    escuro = TEMA.esta_escuro()
    traco = (90, 120, 132) if not escuro else (160, 190, 200)
    img = Image.new("RGB", (w, h), fundo)
    d = ImageDraw.Draw(img)
    passo = 14 * s
    for x in range(0, w, passo):
        d.line((x, 0, x, h), fill=linha_grade, width=1)
    for y in range(0, h, passo):
        d.line((0, y, w, y), fill=linha_grade, width=1)

    if tipo_doc == "ifc":
        _desenhar_modelo_3d(d, w, h, s, traco, semente)
    else:
        folha_w, folha_h = int(w * 0.6), int(h * 0.82)
        folha = Image.new("RGBA", (folha_w, folha_h), (0, 0, 0, 0))
        f = ImageDraw.Draw(folha)
        papel = (255, 255, 255, 255) if not escuro else (24, 60, 72, 255)
        f.rectangle((0, 0, folha_w - 1, folha_h - 1), fill=papel, outline=traco + (255,), width=2 * s)
        m = 10 * s
        f.rectangle((m, m, folha_w - m, folha_h - m), outline=traco + (255,), width=s)
        # "planta" simplificada, variando um pouco com a semente
        a = 0.3 + (semente % 3) * 0.05
        x1, x2 = folha_w * a, folha_w * (a + 0.33)
        y1, y2 = folha_h * 0.25, folha_h * 0.6
        f.rectangle((x1, y1, x2, y2), outline=traco + (255,), width=s)
        f.line((m, folha_h * 0.45, folha_w - m, folha_h * 0.42), fill=traco + (255,), width=s)
        f.line((x1 + (x2 - x1) * 0.6, y1 + (y2 - y1) * 0.4, x1 + (x2 - x1) * 0.6, folha_h - m),
               fill=traco + (255,), width=s)
        f.rectangle((x1 + (x2 - x1) * 0.6, y1 + (y2 - y1) * 0.4, x2 + folha_w * 0.1, y2),
                    outline=traco + (255,), width=s)
        f.rectangle((folha_w - m - 34 * s, folha_h - m - 8 * s, folha_w - m - 2 * s, folha_h - m - 2 * s),
                    outline=traco + (160,), width=1)
        folha = folha.rotate(1.5 + (semente % 2), expand=True, resample=Image.BICUBIC)
        img.paste(folha, ((w - folha.width) // 2, (h - folha.height) // 2 + 4 * s), folha)

    # cantos de cima arredondados (o resto do cartão é desenhado pelo Cartao)
    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w - 1, (h - 1) if todos_os_cantos else h + raio * s * 2),
                                              radius=raio * s, fill=255)
    final = Image.new("RGB", (w, h), _hex(cor_card))
    final.paste(img, (0, 0), mascara)
    return final.resize((largura, altura), Image.LANCZOS)


def _desenhar_modelo_3d(d, w, h, s, cor, semente):
    """Prédio em perspectiva isométrica (wireframe), para os modelos IFC."""
    cx, base_y = w / 2, h * 0.88
    largura = w * 0.16
    profundidade = w * 0.11
    andares = 3 + semente % 3
    altura_andar = h * 0.32 / andares

    def iso(x, y, z):
        return (cx + (x - y) * math.cos(math.radians(30)),
                base_y - z - (x + y) * math.sin(math.radians(30)))

    for k in range(andares + 1):
        z = k * altura_andar
        pts = [iso(0, 0, z), iso(largura, 0, z), iso(largura, profundidade, z), iso(0, profundidade, z)]
        d.polygon(pts, outline=cor, width=s)
    topo = andares * altura_andar
    for x, y in ((0, 0), (largura, 0), (largura, profundidade), (0, profundidade)):
        d.line((iso(x, y, 0), iso(x, y, topo)), fill=cor, width=s)


# ---------------------------------------------------------------------------
# tela
# ---------------------------------------------------------------------------
class TelaProjetos(tk.Frame):
    def __init__(self, parent, app, tipo_doc="pdf"):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self.tipo_doc = tipo_doc
        self.filtro = "Todos"
        self._fotos = {}
        self._pranchas = {}       # obra -> (originais, certificadas, revisão) das pastas VRF
        self._lbl_detalhes = {}
        self._carregar_dados()

        area = AreaRolavel(self)
        area.pack(fill=tk.BOTH, expand=True)
        self.pagina = tk.Frame(area.interno, bg=TEMA["pagina"])
        self.pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(24, 28))

        eh_pdf = tipo_doc == "pdf"
        migalhas = [("Início", app.abrir_tela_home), ("Meus projetos" if eh_pdf else "Meus modelos", None)]
        cab, _ = cabecalho_pagina(self.pagina, None, "", migalhas=migalhas)
        for filho in cab.winfo_children()[1:]:
            filho.destroy()  # só as migalhas; o título vai no banner
        cab.pack(fill=tk.X)

        self._banner()
        self._barra_filtros()
        self.grade = tk.Frame(self.pagina, bg=TEMA["pagina"])
        self.grade.pack(fill=tk.X)
        for col in range(COLUNAS):
            self.grade.columnconfigure(col, weight=1, uniform="cartoes")
        self._montar_cartoes()
        self._contar_pranchas_em_segundo_plano()

    def _carregar_dados(self):
        visiveis = filtrar_por_papel(self.app.issues, self.app.usuario_atual)
        self.resumos = resumo_projetos(visiveis, tipo_doc=self.tipo_doc)
        if self.tipo_doc == "pdf":
            # pranchas com selo: o projeto conta como certificado (e aparece
            # mesmo sem issues — ex.: aprovado direto)
            certificados = certificacoes_por_obra(carregar_anotacoes(), visiveis)
            por_obra = {r["obra"]: r for r in self.resumos}
            for obra, status in certificados.items():
                r = por_obra.get(obra)
                if r is None:
                    r = {"obra": obra, "total": 0, "fechados": 0, "abertos": 0, "progresso": 0.0,
                         "situacao": SITUACAO_CERTIFICADO, "pausado": False, "disciplinas": [], "pessoas": [],
                         "comentarios": 0, "ultima_movimentacao": None, "ultimo_arquivo": None,
                         "tipos_doc": ["pdf"], "contagem": {}}
                    self.resumos.append(r)
                r["situacao"] = SITUACAO_CERTIFICADO
                r["certificacao"] = status

    # ---------- banner ----------
    def _banner(self):
        eh_pdf = self.tipo_doc == "pdf"
        self.canvas_banner = tk.Canvas(self.pagina, bg=TEMA["pagina"], highlightthickness=0, bd=0, height=164)
        self.canvas_banner.pack(fill=tk.X, pady=(0, 20))
        self._textos_banner = (
            "Ambiente de projetos" if eh_pdf else "Ambiente de modelos",
            "Meus projetos" if eh_pdf else "Meus modelos",
            "Centralize documentos, revisões e certificações dos projetos sob sua responsabilidade."
            if eh_pdf else
            "Valide os modelos IFC, marque problemas nos elementos e acompanhe as revisões de cada projeto.",
        )
        self.canvas_banner.bind("<Configure>", self._desenhar_banner)

    def _desenhar_banner(self, evento):
        c = self.canvas_banner
        w, h = evento.width, evento.height
        if w < 50:
            return
        img, (bx, by), _ = imagem_banner(w, h, len(self.resumos))
        mascara = Image.new("L", (w * 3, h * 3), 0)
        ImageDraw.Draw(mascara).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=36, fill=255)
        mascara = mascara.resize((w, h), Image.LANCZOS)
        final = Image.new("RGB", (w, h), _hex(TEMA["pagina"]))
        final.paste(img, (0, 0), mascara)
        self._fotos["banner"] = ImageTk.PhotoImage(final, master=self)
        c.delete("all")
        c.create_image(0, 0, image=self._fotos["banner"], anchor="nw")
        sobre, titulo, sub = self._textos_banner
        c.create_line(28, 34, 48, 34, fill=TEMA["acento"])
        c.create_text(56, 34, text=espacar(sobre), anchor="w", fill="#DDE7EA", font=fonte(8, "semi"))
        c.create_text(28, 70, text=titulo, anchor="w", fill="#FFFFFF", font=fonte(22, "semi"))
        c.create_text(28, 104, text=sub, anchor="nw", fill="#E6EEF0", font=fonte(11), width=min(560, w * 0.5))
        c.create_text(bx, by, text=str(len(self.resumos)), fill=TEMA["primario"] if not TEMA.esta_escuro()
                      else "#14495D", font=fonte(8, "bold"))

    # ---------- filtros ----------
    def _barra_filtros(self):
        linha = tk.Frame(self.pagina, bg=TEMA["pagina"])
        linha.pack(fill=tk.X, pady=(0, 16))
        Segmentado(linha, list(FILTROS_PROJETOS), valor=self.filtro, comando=self._ao_filtrar).pack(side=tk.LEFT)
        self.lbl_contagem = tk.Frame(linha, bg=TEMA["pagina"])
        self.lbl_contagem.pack(side=tk.RIGHT)
        eh_pdf = self.tipo_doc == "pdf"
        Botao(linha, "Iniciar verificação", variante="primario", icone=Icone.LISTA_CHECK, altura=32,
              tamanho_fonte=9, comando=lambda: self.app.abrir_tela_verificacao("pdf" if eh_pdf else "ifc")
              ).pack(side=tk.RIGHT, padx=(0, 18))

    def _atualizar_contagem(self, n):
        for w in self.lbl_contagem.winfo_children():
            w.destroy()
        rotulo(self.lbl_contagem, str(n), 10, "semi").pack(side=tk.LEFT)
        rotulo(self.lbl_contagem, f" projeto{'s' if n != 1 else ''} encontrado{'s' if n != 1 else ''}", 10,
               cor=TEMA["texto"]).pack(side=tk.LEFT)

    def _ao_filtrar(self, valor):
        self.filtro = valor
        self._montar_cartoes()

    # ---------- cartões ----------
    def _montar_cartoes(self):
        for w in self.grade.winfo_children():
            w.destroy()
        projetos = filtrar_projetos(self.resumos, self.filtro)
        self._atualizar_contagem(len(projetos))
        if not projetos:
            vazio = Cartao(self.grade, padding=(24, 30))
            vazio.grid(row=0, column=0, columnspan=COLUNAS, sticky="ew")
            rotulo(vazio.corpo, "Nenhum projeto por aqui ainda", 13, "semi").pack()
            rotulo(vazio.corpo, "Os projetos aparecem assim que o primeiro problema for registrado neles. "
                                "Use \"Iniciar verificação\" para começar." if self.tipo_doc == "pdf" else
                   "Os modelos aparecem assim que o primeiro problema for registrado neles. "
                   "Use \"Iniciar verificação\" para começar.", 10, cor=TEMA["texto_fraco"]).pack(pady=(6, 0))
            return
        for n, projeto in enumerate(projetos):
            self._cartao_projeto(n, projeto).grid(row=n // COLUNAS, column=n % COLUNAS, sticky="nsew",
                                                  padx=(0 if n % COLUNAS == 0 else 8, 0 if n % COLUNAS == COLUNAS - 1 else 8),
                                                  pady=(0, 16))

    def _cartao_projeto(self, n, p):
        """Cartão no modelo do protótipo: CA + situação no topo, miniatura,
        nome do projeto, disciplinas/revisão/nº de pranchas, barra de
        andamento das issues (fechadas, respondidas, reabertas, novas) e
        rodapé com issues em aberto, última atualização e responsáveis."""
        cartao = Cartao(self.grade, padding=(14, 14), raio=12)
        c = cartao.corpo
        bg = c["bg"]

        topo = tk.Frame(c, bg=bg)
        topo.pack(fill=tk.X, pady=(0, 10))
        Pilula(topo, p["obra"], cores=(TEMA["campo"], TEMA["titulo"]), altura=24, tamanho_fonte=9).pack(side=tk.LEFT)
        cert = p.get("certificacao")
        if cert:
            Pilula(topo, f"{cert['codigo']} · {cert['descricao']}", icone=Icone.SELO, altura=24, tamanho_fonte=8,
                   cores=(tom_claro(cert["cor"], 0.84), cert["cor"])).pack(side=tk.RIGHT)
        else:
            situacao = SITUACAO_EXIBIDA.get(p["situacao"], p["situacao"])
            cor_ponto = {SITUACAO_REVISAO: CORES_STATUS["Respondido"], SITUACAO_CERTIFICADO: CORES_STATUS["Fechado"]
                         }.get(p["situacao"], TEMA["info"])
            Pilula(topo, situacao, cores=(TEMA["campo"], TEMA["titulo"]), altura=24, tamanho_fonte=9,
                   icone="●", cor_icone=cor_ponto).pack(side=tk.RIGHT)

        mini = tk.Canvas(c, bg=bg, highlightthickness=0, bd=0, height=ALTURA_MINIATURA, cursor="hand2")
        mini.pack(fill=tk.X)
        mini.bind("<Configure>", lambda e, cv=mini, k=n: self._desenhar_miniatura(cv, e, k))
        mini.bind("<Button-1>", lambda e: self._abrir(p))

        corpo = tk.Frame(c, bg=bg)
        corpo.pack(fill=tk.X, padx=4, pady=(14, 0))
        linha_titulo = tk.Frame(corpo, bg=bg)
        linha_titulo.pack(fill=tk.X)
        info = getattr(self.app, "obras_info", {}).get(p["obra"], {})
        nome = (info.get("nome") or p["obra"]).strip()
        titulo = rotulo(linha_titulo, nome if len(nome) <= 34 else nome[:33] + "…", 13, "semi", cursor="hand2")
        titulo.pack(side=tk.LEFT)
        titulo.bind("<Button-1>", lambda e: self._abrir(p))
        mais = icone(linha_titulo, Icone.RETICENCIAS, 12, cor=TEMA["texto"], cursor="hand2")
        mais.pack(side=tk.RIGHT)
        mais.bind("<Button-1>", lambda e: self._menu(e, p))
        self._lbl_detalhes[p["obra"]] = rotulo(corpo, self._texto_detalhe(p), 9, cor=TEMA["texto_fraco"])
        self._lbl_detalhes[p["obra"]].pack(anchor="w", pady=(3, 12))

        contagem = p.get("contagem") or {}
        linha_prog = tk.Frame(corpo, bg=bg)
        linha_prog.pack(fill=tk.X)
        rotulo(linha_prog, "Andamento das issues", 9, cor=TEMA["texto"]).pack(side=tk.LEFT)
        rotulo(linha_prog, f" de {p['total']}", 9, cor=TEMA["texto"]).pack(side=tk.RIGHT)
        rotulo(linha_prog, str(contagem.get("Fechado", p["fechados"])), 9, "bold").pack(side=tk.RIGHT)
        partes = [(contagem.get(s, 0), CORES_STATUS[s]) for s in ("Fechado", "Respondido", "Reaberto", "Novo")]
        BarraSegmentada(corpo, partes, total=p["total"], altura=7).pack(fill=tk.X, pady=(6, 12))
        separador(corpo)

        rodape = tk.Frame(corpo, bg=bg)
        rodape.pack(fill=tk.X, pady=(10, 0))
        if p["abertos"]:
            tk.Label(rodape, text="●", fg=CORES_STATUS["Novo"], bg=bg, font=fonte(9)).pack(side=tk.LEFT)
            rotulo(rodape, f"{p['abertos']} issue{'s' if p['abertos'] != 1 else ''} em aberto", 9, "semi"
                   ).pack(side=tk.LEFT, padx=(4, 0))
        else:
            tk.Label(rodape, text="●", fg=CORES_STATUS["Fechado"], bg=bg, font=fonte(9)).pack(side=tk.LEFT)
            rotulo(rodape, "Sem issues em aberto", 9, "semi").pack(side=tk.LEFT, padx=(4, 0))
        if p.get("ultima_movimentacao"):
            rotulo(rodape, f"  ·  Atualizado {tempo_relativo(p['ultima_movimentacao']).lower()}", 8,
                   cor=TEMA["texto_fraco"]).pack(side=tk.LEFT)
        self._avatares(rodape, p["pessoas"]).pack(side=tk.RIGHT)
        for w in (c, corpo):
            w.bind("<Double-Button-1>", lambda e: self._abrir(p))
        return cartao

    def _texto_detalhe(self, p):
        partes = list(p["disciplinas"]) or ["Sem disciplina"]
        pranchas = self._pranchas.get(p["obra"])
        if pranchas:
            originais, _certificadas, rev = pranchas
            if rev:
                partes.append(f"Rev. {rev[1:]}")
            if originais:
                unidade = "prancha" if self.tipo_doc == "pdf" else "modelo"
                partes.append(f"{originais} {unidade}{'s' if originais != 1 else ''}")
        else:
            partes.append(f"{p['total']} registro{'s' if p['total'] != 1 else ''}")
        return " · ".join(partes)

    def _contar_pranchas_em_segundo_plano(self):
        """Contar os arquivos das pastas VRF na rede leva um tempinho por
        obra: roda numa thread e o texto do cartão é atualizado depois."""
        obras = [r["obra"] for r in self.resumos]
        resultados = {}

        def trabalhar():
            for obra in obras:
                try:
                    resultados[obra] = contar_pranchas(obra, self.tipo_doc)
                except OSError:
                    resultados[obra] = None

        thread = threading.Thread(target=trabalhar, daemon=True)
        thread.start()

        def conferir():
            if not self.winfo_exists():
                return
            for obra, valor in list(resultados.items()):
                if obra not in self._pranchas and valor:
                    self._pranchas[obra] = valor
                    rotulo_ = self._lbl_detalhes.get(obra)
                    resumo = next((r for r in self.resumos if r["obra"] == obra), None)
                    if rotulo_ is not None and rotulo_.winfo_exists() and resumo:
                        rotulo_.config(text=self._texto_detalhe(resumo))
            if thread.is_alive():
                self.after(250, conferir)

        self.after(250, conferir)

    def _desenhar_miniatura(self, canvas, evento, n):
        w, h = evento.width, evento.height
        if w < 40:
            return
        img = imagem_miniatura(w, h, self.tipo_doc, n, TEMA["card"], todos_os_cantos=True)
        foto = ImageTk.PhotoImage(img, master=self)
        self._fotos[("mini", n)] = foto
        canvas.delete("all")
        canvas.create_image(0, 0, image=foto, anchor="nw")

    def _avatares(self, parent, pessoas):
        mostrar = pessoas[:2]
        extra = len(pessoas) - len(mostrar)
        tamanho, passo = 24, 17
        total = len(mostrar) + (1 if extra > 0 else 0)
        cv = tk.Canvas(parent, bg=parent["bg"], highlightthickness=0, bd=0,
                       width=max(1, tamanho + passo * (total - 1)), height=tamanho)
        bg, fg = TEMA["pill_azul"]
        for k, nome in enumerate(mostrar + (["+"] if extra > 0 else [])):
            x = k * passo
            cv.create_oval(x, 0, x + tamanho - 1, tamanho - 1, fill=bg, outline=parent["bg"], width=2)
            texto = f"+{extra}" if nome == "+" else iniciais(nome)
            cv.create_text(x + tamanho / 2, tamanho / 2, text=texto, font=fonte(7, "bold"), fill=fg)
        return cv

    def _menu(self, evento, p):
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        menu.add_command(label="Abrir projeto", command=lambda: self._abrir(p))
        menu.add_command(label="Ver registros na Consulta",
                         command=lambda: self.app.abrir_tela_consulta(obra=p["obra"]))
        menu.tk_popup(evento.x_root, evento.y_root)

    def _abrir(self, p):
        self.app.abrir_projeto(p["obra"], self.tipo_doc)

    def sincronizar(self):
        self._carregar_dados()
        self._montar_cartoes()
