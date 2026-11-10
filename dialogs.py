"""Caixas de diálogo utilizadas para criação de issues, sessão do usuário,
importação de BCF e marcações livres sobre o PDF (texto/balão/selos)."""
import os
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from auth.usuarios import listar_nomes_ativos
from config import LISTA_DISCIPLINAS, LISTA_STATUS, SELOS_DIR, TEMA
from ui.componentes import CampoArredondado, Cartao, ComboArredondado, Icone, fonte
from ui.corretor import ativar_corretor
from ui.modal import MARGEM, ModalCartao


class DialogSessao(ModalCartao):
    """"Projeto Analisado" (protótipo Figma): pede Obra / Disciplina uma
    vez (no início do uso, ou quando o usuário atualiza a sessão) para
    não precisar repetir essas informações em toda issue criada depois.
    O nome não é perguntado — vem da conta de login (`sessao_atual["nome"]`)
    e só aparece como referência. `sessao_atual`, se passado, pré-preenche
    os campos. Visual: ver ui/modal.py."""

    def __init__(self, parent, lista_obras=None, sessao_atual=None):
        sessao_atual = sessao_atual or {}
        self.nome = sessao_atual.get("nome", "")
        self.obra = None
        self.disciplina = None
        self.atribuido = None
        y = self._abrir_modal(
            parent, "Projeto Analisado",
            "Informe o projeto em análise e preencha automaticamente as próximas issues criadas",
            icone=Icone.RELATORIO, largura=400, altura=540)
        c = self.canvas
        self._rotulo("Analista:", y + 10)
        c.create_text(self.x0 + MARGEM + 70, self.y0 + y + 10, anchor="w", text=f"“{self.nome or '—'}”",
                      fill=TEMA["texto"], font=fonte(10))

        self._rotulo("Obra (Nº Cadari):", y + 48)
        self.ent_obra = self._colocar(ComboArredondado(
            c, lista_obras or [], icone_esquerda=Icone.LISTA, largura=self.largura_util, altura=42,
            editavel=True, filtrar=True, placeholder="CA-XXXX"), y + 64)
        if sessao_atual.get("obra"):
            self.ent_obra.set(sessao_atual["obra"])

        self._rotulo("Disciplina:", y + 132)
        self.ent_disciplina = self._colocar(ComboArredondado(
            c, LISTA_DISCIPLINAS, icone_esquerda=Icone.LISTA_CHECK, largura=self.largura_util, altura=42,
            placeholder="Selecione"), y + 148)
        if sessao_atual.get("disciplina"):
            self.ent_disciplina.set(sessao_atual["disciplina"])

        self._rotulo("Projetista (responsável padrão):", y + 216)
        self.ent_atribuido = self._colocar(ComboArredondado(
            c, listar_nomes_ativos(), icone_esquerda=Icone.ADICIONAR_PESSOA, largura=self.largura_util, altura=42,
            editavel=True, filtrar=True, placeholder="Para quem vão as issues (opcional)"), y + 232)
        if sessao_atual.get("atribuido_para"):
            self.ent_atribuido.set(sessao_atual["atribuido_para"])

        tem_sessao = sessao_atual.get("obra") and sessao_atual.get("disciplina")
        self._botoes("Cancelar" if tem_sessao else "Pular por enquanto", "Confirmar")
        self.bind("<Return>", lambda e: self.confirmar())
        self._exibir(self.ent_obra.combo if not sessao_atual.get("obra") else self.ent_disciplina.combo)

    def confirmar(self):
        if not self.ent_obra.get().strip() or not self.ent_disciplina.get().strip():
            self.mostrar_erro("Preencha obra e disciplina.")
            return
        self.obra = self.ent_obra.get().strip()
        self.disciplina = self.ent_disciplina.get().strip()
        self.atribuido = self.ent_atribuido.get().strip()
        self.destroy()


class DialogNovaIssue(ModalCartao):
    """Pede Obra / Disciplina / Criado por / Atribuído para antes de criar
    uma nova issue (usada pelos visualizadores de PDF e de IFC). Com uma
    sessão de trabalho ativa (`sessao`), Obra, Disciplina e Criado por já
    vêm preenchidos — só falta escolher para quem a issue vai —, mas os
    campos continuam editáveis para o caso excepcional de uma issue fora
    da sessão. `atribuido_inicial`: sugestão (ex.: quem foi mencionado
    com @ no comentário)."""

    def __init__(self, parent, lista_obras=None, sessao=None, atribuido_inicial=None):
        sessao = sessao or {}
        self.criado_por = None
        self.atribuido_para = None
        self.obra = None
        self.disciplina = None
        y = self._abrir_modal(
            parent, "Atribuir responsável",
            "Confira o projeto e escolha para quem este problema será atribuído.",
            icone=Icone.ADICIONAR_PESSOA, largura=440, altura=470)
        c = self.canvas
        meia = (self.largura_util - 12) // 2
        nomes = listar_nomes_ativos()

        self._rotulo("Obra (Nº Cadari):", y + 10)
        self.ent_obra = self._colocar(ComboArredondado(
            c, lista_obras or [], icone_esquerda=Icone.LISTA, largura=meia, altura=40,
            editavel=True, filtrar=True, placeholder="CA-XXXX"), y + 26)
        self._rotulo("Disciplina:", y + 10, x=meia + 12)
        self.ent_disciplina = self._colocar(ComboArredondado(
            c, LISTA_DISCIPLINAS, icone_esquerda=Icone.LISTA_CHECK, largura=meia, altura=40,
            placeholder="Selecione"), y + 26, x=meia + 12)

        self._rotulo("Criado por:", y + 90)
        self.ent_criado = self._colocar(ComboArredondado(
            c, nomes, icone_esquerda=Icone.PESSOA, largura=self.largura_util, altura=40, editavel=True,
            filtrar=True), y + 106)
        self._rotulo("Atribuído para:", y + 170)
        self.ent_atrib = self._colocar(ComboArredondado(
            c, nomes, icone_esquerda=Icone.ADICIONAR_PESSOA, largura=self.largura_util, altura=40,
            editavel=True, filtrar=True, placeholder="Selecione o responsável"), y + 186)

        if sessao.get("obra"):
            self.ent_obra.set(sessao["obra"])
        if sessao.get("disciplina"):
            self.ent_disciplina.set(sessao["disciplina"])
        if sessao.get("nome"):
            self.ent_criado.set(sessao["nome"])
        if atribuido_inicial or sessao.get("atribuido_para"):
            self.ent_atrib.set(atribuido_inicial or sessao["atribuido_para"])

        self._botoes("Cancelar", "Confirmar")
        self.bind("<Return>", lambda e: self.confirmar())
        # foca direto no único campo que a sessão não resolve
        self._exibir(self.ent_atrib.combo if sessao.get("obra") else self.ent_obra.combo)

    @staticmethod
    def sessao_completa(sessao):
        """Com obra, disciplina, analista e projetista já na sessão, o
        visualizador de PDF cria o problema direto, sem este diálogo."""
        sessao = sessao or {}
        return all(sessao.get(k) for k in ("obra", "disciplina", "nome", "atribuido_para"))

    def confirmar(self):
        if not self.ent_obra.get().strip():
            self.mostrar_erro("Selecione a obra (Nº Cadari) à qual este problema pertence.")
            return
        if not self.ent_disciplina.get().strip():
            self.mostrar_erro("Selecione a disciplina responsável por este problema.")
            return
        if not self.ent_criado.get().strip() or not self.ent_atrib.get().strip():
            self.mostrar_erro("Preencha quem está criando e para quem será atribuído.")
            return
        self.obra = self.ent_obra.get().strip()
        self.disciplina = self.ent_disciplina.get().strip()
        self.criado_por = self.ent_criado.get().strip()
        self.atribuido_para = self.ent_atrib.get().strip()
        self.destroy()


class DialogAtribuicao(ModalCartao):
    """"Edição de atribuição" da verificação: o projetista responsável
    padrão (já vem selecionado em toda issue nova) e, quando o projeto foi
    elaborado por mais de uma pessoa, os demais — eles aparecem primeiro
    no campo "Para" de cada issue. `self.padrao`/`self.outros` ficam None
    se cancelado."""

    def __init__(self, parent, sessao):
        self.padrao = None
        self.outros = None
        nomes = listar_nomes_ativos()
        y = self._abrir_modal(parent, "Edição de atribuição",
                              "Quem recebe as issues desta verificação. O padrão já vem marcado em toda issue nova; "
                              "dá para trocar em cada uma.", icone=Icone.ADICIONAR_PESSOA, largura=440,
                              altura=min(620, 330 + 28 * ((len(nomes) + 1) // 2)))
        c = self.canvas
        self._rotulo("Responsável padrão:", y + 10)
        self.cb_padrao = self._colocar(ComboArredondado(
            c, nomes, icone_esquerda=Icone.PESSOA, largura=self.largura_util, altura=40, editavel=True,
            filtrar=True, placeholder="Selecione o projetista"), y + 26)
        if sessao.get("atribuido_para"):
            self.cb_padrao.set(sessao["atribuido_para"])

        self._rotulo("Também elaboraram este projeto:", y + 90)
        grade = tk.Frame(c, bg=TEMA["card"])
        self._vars = {}
        ja = set(sessao.get("projetistas") or [])
        for n, nome in enumerate(nomes):
            var = tk.BooleanVar(master=self, value=nome in ja)
            tk.Checkbutton(grade, text=nome, variable=var, bg=TEMA["card"], fg=TEMA["titulo"],
                           activebackground=TEMA["card"], selectcolor=TEMA["card"], font=fonte(9),
                           anchor="w").grid(row=n // 2, column=n % 2, sticky="w", padx=(0, 12))
            self._vars[nome] = var
        self._colocar(grade, y + 104)
        self._botoes("Cancelar", "Salvar")
        self._exibir(self.cb_padrao.combo)

    def confirmar(self):
        padrao = self.cb_padrao.get().strip()
        if not padrao:
            self.mostrar_erro("Escolha o responsável padrão.")
            return
        self.padrao = padrao
        self.outros = [n for n, v in self._vars.items() if v.get() and n != padrao]
        self.destroy()


class DialogEditarIssue(ModalCartao):
    """Editar um problema já registrado (menu "…" do comentário):
    título, tipo, status, disciplina, responsável e descrição.
    `self.valores` fica com o dict alterado, ou None se cancelado."""

    def __init__(self, parent, issue, tipos):
        self.valores = None
        y = self._abrir_modal(parent, f"Editar problema #{issue.get('id')}",
                              "As alterações ficam registradas no histórico do problema.",
                              icone=Icone.EDITAR, largura=480, altura=600)
        c = self.canvas
        meia = (self.largura_util - 12) // 2

        self._rotulo("Título:", y + 10)
        self.ent_titulo = self._colocar(CampoArredondado(c, largura=self.largura_util, altura=40), y + 26)
        self.ent_titulo.set(issue.get("titulo", ""))

        self._rotulo("Tipo:", y + 90)
        self.cb_tipo = self._colocar(ComboArredondado(c, tipos, largura=meia, altura=40), y + 106)
        self.cb_tipo.set(issue.get("tipo", ""))
        self._rotulo("Status:", y + 90, x=meia + 12)
        self.cb_status = self._colocar(ComboArredondado(c, LISTA_STATUS, largura=meia, altura=40),
                                       y + 106, x=meia + 12)
        self.cb_status.set(issue.get("status", ""))

        self._rotulo("Disciplina:", y + 170)
        self.cb_disciplina = self._colocar(ComboArredondado(c, LISTA_DISCIPLINAS, largura=meia, altura=40),
                                           y + 186)
        self.cb_disciplina.set(issue.get("disciplina", ""))
        self._rotulo("Atribuído para:", y + 170, x=meia + 12)
        self.cb_atrib = self._colocar(ComboArredondado(c, listar_nomes_ativos(), largura=meia, altura=40,
                                                       editavel=True, filtrar=True), y + 186, x=meia + 12)
        self.cb_atrib.set(issue.get("atribuido_para", ""))

        self._rotulo("Descrição:", y + 250)
        moldura = Cartao(c, padding=(10, 8), raio=8, tamanho_fixo=True, width=self.largura_util, height=110)
        self.txt_desc = tk.Text(moldura.corpo, wrap="word", relief="flat", bd=0, highlightthickness=0,
                                width=1, height=1,
                                bg=TEMA["card"], fg=TEMA["titulo"], insertbackground=TEMA["titulo"],
                                font=fonte(10))
        self.txt_desc.pack(fill=tk.BOTH, expand=True)
        self.txt_desc.insert("1.0", issue.get("desc", ""))
        ativar_corretor(self.txt_desc)
        self._colocar(moldura, y + 266)

        self._botoes("Cancelar", "Salvar alterações")
        self._exibir(self.ent_titulo.entry)

    def confirmar(self):
        if not self.cb_status.get():
            self.mostrar_erro("Escolha o status.")
            return
        self.valores = {
            "titulo": self.ent_titulo.get().strip() or "Sem título",
            "tipo": self.cb_tipo.get().strip(),
            "status": self.cb_status.get().strip(),
            "disciplina": self.cb_disciplina.get().strip(),
            "atribuido_para": self.cb_atrib.get().strip(),
            "desc": self.txt_desc.get("1.0", tk.END).strip(),
        }
        self.destroy()


class DialogObraImportacao(tk.Toplevel):
    """Pergunta a obra uma vez e aplica a todas as issues importadas de um BCF."""

    def __init__(self, parent, lista_obras=None):
        super().__init__(parent, bg=TEMA["surface"])
        self.title("Importação BCF — Obra do lote")
        self.geometry("380x150")
        self.resizable(False, False)

        self.obra = None
        if lista_obras is None:
            lista_obras = []

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 190
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
        self.geometry(f"+{x}+{y}")

        tk.Label(
            self,
            text="Selecione a obra (Nº Cadari) que receberá\nas issues importadas deste BCF:",
            bg=TEMA["surface"], fg=TEMA["texto"], font=("Arial", 10), justify="left"
        ).pack(padx=15, pady=(15, 8), anchor="w")

        self.ent_obra = ttk.Combobox(self, values=lista_obras, width=35)
        self.ent_obra.pack(padx=15, pady=5)

        tk.Button(
            self, text="✔ Confirmar", command=self.confirmar,
            bg=TEMA["atencao"], fg=TEMA["acento_texto"], font=("Arial", 9, "bold")
        ).pack(pady=10)

        self.ent_obra.focus_set()
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def confirmar(self):
        v = self.ent_obra.get().strip()
        if not v:
            messagebox.showwarning("Aviso", "Selecione a obra (Nº Cadari).", parent=self)
            return
        self.obra = v
        self.destroy()


class DialogTextoLivre(tk.Toplevel):
    """Editor de texto curto e multi-linha, usado tanto para a nota da
    ferramenta 'Balão' quanto para a ferramenta 'Caixa de Texto'."""

    def __init__(self, parent, titulo="Texto", texto_inicial=""):
        super().__init__(parent, bg=TEMA["surface"])
        self.title(titulo)
        self.geometry("360x220")
        self.resizable(False, False)

        self.texto = None

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 180
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 110
        self.geometry(f"+{x}+{y}")

        tk.Label(self, text=titulo, bg=TEMA["surface"], fg=TEMA["texto"],
                  font=("Arial", 10, "bold")).pack(padx=12, pady=(12, 6), anchor="w")

        corpo = tk.Frame(self, bg=TEMA["surface"])
        corpo.pack(padx=12, fill=tk.BOTH, expand=True)

        self.txt = tk.Text(corpo, height=6, wrap="word", bg=TEMA["surface_alt"], fg=TEMA["texto"],
                            insertbackground=TEMA["texto"], relief=tk.FLAT, font=("Arial", 10))
        self.txt.pack(fill=tk.BOTH, expand=True)
        self.txt.insert("1.0", texto_inicial)
        ativar_corretor(self.txt)

        botoes = tk.Frame(self, bg=TEMA["surface"])
        botoes.pack(pady=10)
        tk.Button(botoes, text="✔ Salvar", command=self.confirmar, bg=TEMA["acento"], fg=TEMA["acento_texto"],
                  font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(botoes, text="Cancelar", command=self.destroy, bg=TEMA["surface_alt"],
                  fg=TEMA["texto"]).pack(side=tk.LEFT, padx=5)

        self.txt.focus_set()
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def confirmar(self):
        conteudo = self.txt.get("1.0", "end-1c").strip()
        if not conteudo:
            messagebox.showwarning("Aviso", "Digite um texto.", parent=self)
            return
        self.texto = conteudo
        self.destroy()


class DialogSelecionarSelo(tk.Toplevel):
    """Lista os selos de aprovação (imagens) disponíveis na pasta padrão da
    rede e deixa o usuário escolher um para carimbar na prancha."""

    def __init__(self, parent):
        super().__init__(parent, bg=TEMA["surface"])
        self.title("Selos de Aprovação")
        self.geometry("420x420")
        self.resizable(False, False)

        self.caminho_selecionado = None
        self._thumb_atual = None

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 210
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 210
        self.geometry(f"+{x}+{y}")

        tk.Label(self, text="Selecione o selo para inserir na prancha:", bg=TEMA["surface"],
                  fg=TEMA["texto"], font=("Arial", 10, "bold")).pack(padx=12, pady=(12, 6), anchor="w")

        corpo = tk.Frame(self, bg=TEMA["surface"])
        corpo.pack(padx=12, fill=tk.BOTH, expand=True)

        lista_frame = tk.Frame(corpo, bg=TEMA["surface"])
        lista_frame.pack(side=tk.LEFT, fill=tk.Y)

        scrollbar = ttk.Scrollbar(lista_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox = tk.Listbox(lista_frame, width=26, height=18, yscrollcommand=scrollbar.set,
                                   bg=TEMA["surface_alt"], fg=TEMA["texto"], relief=tk.FLAT,
                                   selectbackground=TEMA["acento"], selectforeground=TEMA["acento_texto"])
        self.listbox.pack(side=tk.LEFT, fill=tk.Y)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._ao_selecionar)

        self.preview_frame = tk.Frame(corpo, width=150, height=150, bg=TEMA["surface_alt"])
        self.preview_frame.pack(side=tk.LEFT, padx=(12, 0), fill=tk.BOTH, expand=True)
        self.preview_frame.pack_propagate(False)
        self.lbl_preview = tk.Label(self.preview_frame, bg=TEMA["surface_alt"])
        self.lbl_preview.pack(expand=True)

        self._arquivos = []
        self._carregar_lista()

        botoes = tk.Frame(self, bg=TEMA["surface"])
        botoes.pack(pady=10)
        tk.Button(botoes, text="✔ Usar este selo", command=self.confirmar, bg=TEMA["acento"],
                  fg=TEMA["acento_texto"], font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(botoes, text="Cancelar", command=self.destroy, bg=TEMA["surface_alt"],
                  fg=TEMA["texto"]).pack(side=tk.LEFT, padx=5)

        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def _carregar_lista(self):
        extensoes = (".png", ".jpg", ".jpeg", ".bmp")
        try:
            nomes = sorted(f for f in os.listdir(SELOS_DIR) if f.lower().endswith(extensoes))
        except Exception as e:
            messagebox.showwarning(
                "Aviso de Rede",
                f"Não foi possível acessar a pasta de selos na rede.\nVocê está conectado?\n\n{SELOS_DIR}\n\nErro: {e}",
                parent=self,
            )
            nomes = []

        self._arquivos = [os.path.join(SELOS_DIR, n) for n in nomes]
        for n in nomes:
            self.listbox.insert(tk.END, os.path.splitext(n)[0])

    def _ao_selecionar(self, event=None):
        selecao = self.listbox.curselection()
        if not selecao:
            return
        caminho = self._arquivos[selecao[0]]
        try:
            img = Image.open(caminho)
            img.thumbnail((140, 140))
            self._thumb_atual = ImageTk.PhotoImage(img)
            self.lbl_preview.config(image=self._thumb_atual, text="")
        except Exception:
            self.lbl_preview.config(image="", text="(prévia indisponível)", fg=TEMA["texto_fraco"])

    def confirmar(self):
        selecao = self.listbox.curselection()
        if not selecao:
            messagebox.showwarning("Aviso", "Selecione um selo na lista.", parent=self)
            return
        self.caminho_selecionado = self._arquivos[selecao[0]]
        self.destroy()
