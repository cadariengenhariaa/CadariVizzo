"""Tela "Verificações (VRF)": o ponto de partida de uma verificação, para
PDF e IFC.

- **Iniciar verificação**: escolhe o CA (lista suspensa digitável, com o
  nome do projeto), a disciplina e o projetista responsável padrão; a
  tela já mostra os documentos da pasta de verificação da obra
  (Z:\\Projetos\\Ativos\\CA-xxxx\\xxxx-VRF\\xxxx-DISC) e um clique abre o
  arquivo direto no visualizador, com a sessão preenchida.
- **Acompanhar verificações**: documentos que já têm issues ou selo,
  com o andamento das issues (fechadas, respondidas, reabertas, novas) e
  a certificação — "Continuar" reabre no ponto em que parou."""
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog

from auth.usuarios import listar_nomes_ativos
from certificacao import info_selo, status_certificacao, tom_claro
from config import CORES_STATUS, LISTA_DISCIPLINAS, LISTA_STATUS, TEMA
from dashboard.dados_dashboard import filtrar_por_papel
from dashboard.dados_painel import tempo_relativo, ultima_movimentacao
from projeto_vrf import listar_documentos, pasta_vrf
from ui.componentes import (
    AreaRolavel,
    BarraSegmentada,
    Botao,
    Cartao,
    ComboArredondado,
    Icone,
    Pilula,
    QuadradoIcone,
    Segmentado,
    cabecalho_cartao,
    cabecalho_pagina,
    espacar,
    fonte,
    icone,
    rotulo,
    separador,
)
from utils import carregar_anotacoes

TIPOS = {"PDF (pranchas)": "pdf", "IFC (modelos)": "ifc"}


def resumo_documentos(issues, anotacoes, tipo_doc):
    """Um item por documento com issues (ou selo): contagem por status,
    certificação e última movimentação — do mais recente ao mais antigo."""
    por_arquivo = {}
    for i in issues:
        if (i.get("tipo_doc") or "pdf") != tipo_doc or not i.get("filepath"):
            continue
        por_arquivo.setdefault(i["filepath"], []).append(i)
    if tipo_doc == "pdf":
        for a in anotacoes:
            if a.get("tipo") == "selo" and a.get("filepath"):
                por_arquivo.setdefault(a["filepath"], [])
    resultado = []
    for caminho, lista in por_arquivo.items():
        contagem = {s: sum(1 for i in lista if i.get("status") == s) for s in LISTA_STATUS}
        movs = [m for m in (ultima_movimentacao(i) for i in lista) if m]
        status = status_certificacao(anotacoes, caminho) if tipo_doc == "pdf" else None
        if status:
            try:
                movs.append(datetime.strptime(status["data"], "%d/%m/%Y %H:%M:%S"))
            except ValueError:
                pass
        obras = [i.get("obra") for i in lista if i.get("obra")]
        disciplinas = [i.get("disciplina") for i in lista if i.get("disciplina")]
        resultado.append({
            "caminho": caminho,
            "nome": os.path.basename(caminho),
            "obra": max(set(obras), key=obras.count) if obras else "",
            "disciplina": max(set(disciplinas), key=disciplinas.count) if disciplinas else "",
            "contagem": contagem,
            "total": len(lista),
            "certificacao": status,
            "ultima": max(movs) if movs else None,
        })
    resultado.sort(key=lambda r: r["ultima"] or datetime.min, reverse=True)
    return resultado


class TelaVerificacao(tk.Frame):
    def __init__(self, parent, app, tipo_doc="pdf", obra=None):
        super().__init__(parent, bg=TEMA["pagina"])
        self.app = app
        self.tipo_doc = tipo_doc

        area = AreaRolavel(self)
        area.pack(fill=tk.BOTH, expand=True)
        self.pagina = tk.Frame(area.interno, bg=TEMA["pagina"])
        self.pagina.pack(fill=tk.BOTH, expand=True, padx=32, pady=(24, 28))

        cab, _ = cabecalho_pagina(
            self.pagina, "Verificação de projetos", "Verificações (VRF)",
            "Escolha o projeto e a disciplina: os arquivos da pasta de verificação aparecem aqui, prontos para abrir.",
            migalhas=[("Início", app.abrir_tela_home), ("Verificações", None)])
        cab.pack(fill=tk.X, pady=(0, 18))

        corpo = tk.Frame(self.pagina, bg=TEMA["pagina"])
        corpo.pack(fill=tk.BOTH, expand=True)
        corpo.columnconfigure(0, weight=5, uniform="vrf")
        corpo.columnconfigure(1, weight=4, uniform="vrf")
        self._montar_inicio(corpo, obra)
        self._montar_acompanhamento(corpo)
        self._atualizar_documentos()

    # ---------- iniciar ----------
    def _montar_inicio(self, corpo, obra):
        cartao = Cartao(corpo, padding=(20, 18))
        cartao.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        c = cartao.corpo
        cab, _ = cabecalho_cartao(c, "Passo 1", "Iniciar verificação")
        cab.pack(fill=tk.X, pady=(0, 14))

        tipo_inicial = next(k for k, v in TIPOS.items() if v == self.tipo_doc)
        Segmentado(c, list(TIPOS), valor=tipo_inicial, comando=self._ao_mudar_tipo).pack(anchor="w", pady=(0, 14))

        campos = tk.Frame(c, bg=c["bg"])
        campos.pack(fill=tk.X)
        campos.columnconfigure(0, weight=3, uniform="c")
        campos.columnconfigure(1, weight=2, uniform="c")

        def campo(texto, linha, coluna, colspan=1):
            f = tk.Frame(campos, bg=c["bg"])
            f.grid(row=linha, column=coluna, columnspan=colspan, sticky="new",
                   padx=(0, 10 if coluna == 0 and colspan == 1 else 0), pady=(0, 12))
            rotulo(f, espacar(texto), 7, "semi", cor=TEMA["eyebrow"]).pack(anchor="w", pady=(0, 4))
            return f

        sessao = self.app.sessao
        f = campo("Projeto (CA)", 0, 0)
        self.cb_obra = ComboArredondado(f, self.app.obras_lista, icone_esquerda=Icone.BUSCA, largura=10, altura=40,
                                        editavel=True, filtrar=True, placeholder="Digite o CA ou o nome do projeto")
        self.cb_obra.rotulos = {k: v.get("nome", "") for k, v in getattr(self.app, "obras_info", {}).items()
                                if v.get("nome")}
        self.cb_obra.pack(fill=tk.X)
        self.cb_obra.combo.bind("<<ComboboxSelected>>", lambda e: self._atualizar_documentos(), add="+")
        self.cb_obra.combo.bind("<FocusOut>", lambda e: self.after(200, self._atualizar_documentos), add="+")
        self.lbl_nome_obra = rotulo(f, "", 9, cor=TEMA["texto_fraco"])
        self.lbl_nome_obra.pack(anchor="w", pady=(4, 0))

        f = campo("Disciplina", 0, 1)
        self.cb_disciplina = ComboArredondado(f, LISTA_DISCIPLINAS, icone_esquerda=Icone.LISTA_CHECK, largura=10,
                                              altura=40, placeholder="Selecione")
        self.cb_disciplina.pack(fill=tk.X)
        self.cb_disciplina.combo.bind("<<ComboboxSelected>>", lambda e: self._atualizar_documentos(), add="+")

        f = campo("Projetista responsável (padrão das issues)", 1, 0, colspan=2)
        self.cb_projetista = ComboArredondado(f, listar_nomes_ativos(), icone_esquerda=Icone.ADICIONAR_PESSOA,
                                              largura=10, altura=40, editavel=True, filtrar=True,
                                              placeholder="Para quem vão as issues desta verificação")
        self.cb_projetista.pack(fill=tk.X)

        if obra or sessao.get("obra"):
            self.cb_obra.set(obra or sessao["obra"])
        if sessao.get("disciplina"):
            self.cb_disciplina.set(sessao["disciplina"])
        if sessao.get("atribuido_para"):
            self.cb_projetista.set(sessao["atribuido_para"])

        separador(c, pady=(4, 12))
        linha = tk.Frame(c, bg=c["bg"])
        linha.pack(fill=tk.X)
        icone(linha, Icone.PASTA, 10).pack(side=tk.LEFT, padx=(0, 8))
        self.lbl_pasta = rotulo(linha, "", 9, cor=TEMA["texto"], wraplength=520, justify="left", anchor="w")
        self.lbl_pasta.pack(side=tk.LEFT, fill=tk.X, expand=True)
        Botao(linha, "Procurar outro arquivo…", variante="link", altura=26, tamanho_fonte=9,
              comando=self._procurar).pack(side=tk.RIGHT)

        self.lista_docs = tk.Frame(c, bg=c["bg"])
        self.lista_docs.pack(fill=tk.X, pady=(10, 0))

    def _ao_mudar_tipo(self, rotulo_tipo):
        self.tipo_doc = TIPOS[rotulo_tipo]
        self._atualizar_documentos()
        self._preencher_acompanhamento()

    def _pasta(self):
        return pasta_vrf(self.cb_obra.get().strip().upper(), self.cb_disciplina.get().strip() or None)

    def _atualizar_documentos(self):
        if not self.winfo_exists():
            return
        obra = self.cb_obra.get().strip().upper()
        info = getattr(self.app, "obras_info", {}).get(obra, {})
        self.lbl_nome_obra.config(text=" · ".join(p for p in (info.get("nome"), info.get("cliente")) if p))
        for w in self.lista_docs.winfo_children():
            w.destroy()
        if not obra:
            self.lbl_pasta.config(text="Escolha o projeto (CA) e a disciplina para ver os arquivos da verificação.")
            return
        pasta = self._pasta()
        if not pasta:
            self.lbl_pasta.config(text=f"Pasta da obra {obra} não encontrada em Z:\\Projetos\\Ativos.")
            return
        self.lbl_pasta.config(text=pasta)
        documentos = listar_documentos(pasta, self.tipo_doc)
        if not documentos:
            rotulo(self.lista_docs, "Nenhum arquivo " + ("PDF" if self.tipo_doc == "pdf" else "IFC") +
                   " nesta pasta. Use \"Procurar outro arquivo…\".", 9, cor=TEMA["texto_fraco"]).pack(anchor="w")
            return
        for doc in documentos[:14]:
            self._linha_documento(doc)

    def _linha_documento(self, doc):
        bg = TEMA["card"]
        linha = tk.Frame(self.lista_docs, bg=bg, cursor="hand2")
        linha.pack(fill=tk.X)
        QuadradoIcone(linha, Icone.DOCUMENTO if self.tipo_doc == "pdf" else Icone.CUBO,
                      cores=TEMA["pill_azul"], tamanho=34, tamanho_icone=11).pack(side=tk.LEFT, padx=(0, 12), pady=8)
        textos = tk.Frame(linha, bg=bg)
        textos.pack(side=tk.LEFT, fill=tk.X, expand=True)
        nome = rotulo(textos, doc["nome"], 10, "semi", anchor="w")
        nome.pack(anchor="w", fill=tk.X)
        quando = doc["modificado"].strftime("%d/%m/%Y %H:%M") if doc["modificado"] else ""
        detalhe = " · ".join(p for p in (doc["revisao"], f"modificado em {quando}" if quando else "") if p)
        rotulo(textos, detalhe, 8, cor=TEMA["texto_fraco"]).pack(anchor="w")
        if doc["certificado"]:
            info = info_selo(doc["certificado"] + ".png")
            Pilula(linha, f"{info['codigo']} · cópia certificada", cores=(tom_claro(info["cor"], 0.82), info["cor"]),
                   altura=22, tamanho_fonte=8).pack(side=tk.LEFT, padx=8)
        Botao(linha, "Verificar", variante="primario", icone_direita=Icone.SETA_DIREITA, altura=30, tamanho_fonte=9,
              comando=lambda d=doc: self._abrir(d["caminho"])).pack(side=tk.RIGHT)
        for w in (linha, textos, nome):
            w.bind("<Double-Button-1>", lambda e, d=doc: self._abrir(d["caminho"]))
        separador(self.lista_docs)

    def _procurar(self):
        pasta = self._pasta() or os.path.expanduser("~")
        tipos = [("PDF", "*.pdf")] if self.tipo_doc == "pdf" else [("Modelos IFC", "*.ifc")]
        caminho = filedialog.askopenfilename(initialdir=pasta, filetypes=tipos + [("Todos os arquivos", "*.*")])
        if caminho:
            self._abrir(caminho)

    def _abrir(self, caminho):
        obra = self.cb_obra.get().strip().upper()
        disciplina = self.cb_disciplina.get().strip()
        projetista = self.cb_projetista.get().strip()
        self.app.abrir_documento(caminho, self.tipo_doc, obra=obra or None, disciplina=disciplina or None,
                                 atribuido=projetista)

    # ---------- acompanhar ----------
    def _montar_acompanhamento(self, corpo):
        cartao = Cartao(corpo, padding=(20, 18))
        cartao.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        c = cartao.corpo
        cab, self._direita_acomp = cabecalho_cartao(c, "Passo 2", "Acompanhar verificações")
        cab.pack(fill=tk.X, pady=(0, 6))
        self.legenda = tk.Frame(c, bg=c["bg"])
        self.legenda.pack(anchor="w", pady=(0, 10))
        for status, texto in (("Fechado", "Fechadas"), ("Respondido", "Respondidas"), ("Reaberto", "Reabertas"),
                              ("Novo", "Novas")):
            tk.Label(self.legenda, text="●", fg=CORES_STATUS[status], bg=c["bg"], font=fonte(8)).pack(side=tk.LEFT)
            rotulo(self.legenda, texto, 8, cor=TEMA["texto"]).pack(side=tk.LEFT, padx=(2, 10))
        self.lista_acomp = tk.Frame(c, bg=c["bg"])
        self.lista_acomp.pack(fill=tk.X)
        self._preencher_acompanhamento()

    def _preencher_acompanhamento(self):
        for w in self.lista_acomp.winfo_children():
            w.destroy()
        for w in self._direita_acomp.winfo_children():
            w.destroy()
        visiveis = filtrar_por_papel(self.app.issues, self.app.usuario_atual)
        documentos = resumo_documentos(visiveis, carregar_anotacoes(), self.tipo_doc)
        Pilula(self._direita_acomp, f"{len(documentos)} documento{'s' if len(documentos) != 1 else ''}",
               cores=(TEMA["campo"], TEMA["texto_fraco"]), altura=24).pack()
        if not documentos:
            rotulo(self.lista_acomp, "Nenhuma verificação em andamento ainda.", 9,
                   cor=TEMA["texto_fraco"]).pack(anchor="w", pady=10)
            return
        for doc in documentos[:12]:
            self._linha_acompanhamento(doc)

    def _linha_acompanhamento(self, doc):
        bg = TEMA["card"]
        linha = tk.Frame(self.lista_acomp, bg=bg)
        linha.pack(fill=tk.X, pady=(8, 8))
        topo = tk.Frame(linha, bg=bg)
        topo.pack(fill=tk.X)
        rotulo(topo, doc["nome"], 9, "semi", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        Botao(topo, "Continuar", variante="link", icone_direita=Icone.SETA_DIREITA, altura=22, tamanho_fonte=9,
              comando=lambda d=doc: self.app.abrir_documento(
                  d["caminho"], self.tipo_doc, obra=d["obra"] or None, disciplina=d["disciplina"] or None)
              ).pack(side=tk.RIGHT)
        meta = " · ".join(p for p in (doc["obra"], doc["disciplina"], tempo_relativo(doc["ultima"])) if p)
        rotulo(linha, meta, 8, cor=TEMA["texto_fraco"]).pack(anchor="w")
        barra = tk.Frame(linha, bg=bg)
        barra.pack(fill=tk.X, pady=(6, 0))
        partes = [(doc["contagem"][s], CORES_STATUS[s]) for s in ("Fechado", "Respondido", "Reaberto", "Novo")]
        BarraSegmentada(barra, partes, altura=6).pack(side=tk.LEFT, fill=tk.X, expand=True)
        abertas = doc["total"] - doc["contagem"]["Fechado"]
        rotulo(barra, f"  {doc['contagem']['Fechado']} de {doc['total']}", 8, "semi").pack(side=tk.LEFT)
        rodape = tk.Frame(linha, bg=bg)
        rodape.pack(fill=tk.X, pady=(4, 0))
        if abertas:
            tk.Label(rodape, text="●", fg=CORES_STATUS["Novo"], bg=bg, font=fonte(8)).pack(side=tk.LEFT)
            rotulo(rodape, f"{abertas} em aberto", 8, cor=TEMA["texto"]).pack(side=tk.LEFT, padx=(2, 0))
        if doc["certificacao"]:
            cert = doc["certificacao"]
            Pilula(rodape, f"{cert['codigo']} · {cert['descricao']}", cores=(tom_claro(cert["cor"], 0.82), cert["cor"]),
                   altura=20, tamanho_fonte=7, icone=Icone.SELO).pack(side=tk.RIGHT)
        separador(self.lista_acomp)

    def sincronizar(self):
        self._atualizar_documentos()
        self._preencher_acompanhamento()
