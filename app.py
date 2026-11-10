"""Aplicativo principal: Visualizador Cadari de Projetos.

Tela inicial que dá acesso aos três módulos:
  - Validação de Pranchas (PDF), com marcação de issues e importação BCF;
  - Validação de Modelo (IFC), com visualizador 3D e marcação de issues por elemento;
  - Consulta, para gestão de todos os registros já criados.
"""
import os
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from auth.dialogs import DialogLogin, DialogTrocarSenha
from auth.painel_usuarios import PainelUsuarios
from auth.usuarios import carregar_usuarios, salvar_usuarios
from config import ICONE_VIZZO_ICO, ICONE_VIZZO_PNG, MODOS_TEMA, OBRAS_FILE, PROJETOS_DIR, TEMA
from consulta import ConsultaFrame
from dashboard.dados_painel import resumo_projetos
from dashboard.tela_dashboard import TelaDashboard
from dialogs import DialogSessao
from ifc_viewer import IFCViewerFrame
from pdf_viewer import PDFViewerFrame
from ui import preferencias
from ui.corretor import CORRETOR
from ui.componentes import configurar_estilos_ttk, fonte
from ui.painel_controle import PainelControle, TelaConformidade, TelaEquipe
from ui.shell import BarraLateral, BarraTopo
from ui.tela_inicio import TelaInicio
from ui.tela_projetos import TelaProjetos
from ui.tela_verificacao import TelaVerificacao
from utils import carregar_banco_dados as _carregar_banco_dados
from utils import salvar_banco_dados as _salvar_banco_dados

# openpyxl é necessário para ler o cadastro de obras (.xlsm).
# É importado de forma defensiva — se faltar, o app continua a funcionar
# e apenas avisa que a lista de obras ficará vazia.
try:
    from openpyxl import load_workbook
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False


class AppCDE(tk.Tk):
    def report_callback_exception(self, exc, val, tb):
        """Por padrão, uma exceção dentro de um callback do Tkinter (ex.:
        comando de botão) só vai pro stderr — invisível numa build
        --windowed sem console, o que já deixou uma tela travada em
        branco sem nenhum aviso (ver histórico: regras_clash.yaml faltando
        no pacote do PyInstaller). Mostra numa caixa de erro em vez de
        engolir silenciosamente."""
        detalhes = "".join(traceback.format_exception(exc, val, tb))
        messagebox.showerror(
            "Erro inesperado",
            f"Ocorreu um erro inesperado e a ação não foi concluída:\n\n{val}\n\n"
            f"Detalhes técnicos (envie um print para o suporte):\n{detalhes[-1500:]}",
        )

    def __init__(self):
        super().__init__()
        self.withdraw()  # some até o login terminar — evita o flash de uma janela sem login
        self.title("Cadari Vizzo — Visualizador de Projetos")
        TEMA.definir(preferencias.carregar().get("tema", "claro"))
        self._aplicar_icone()
        self._aplicar_tema()  # já deixa o estilo ttk pronto para os Entry/Combobox do login

        self.usuario_atual = None
        dialogo_login = DialogLogin(self)
        if dialogo_login.usuario is None:
            return  # main.py não chama mainloop() quando usuario_atual continua None

        self.usuario_atual = dialogo_login.usuario
        CORRETOR.carregar_em_segundo_plano()  # dicionário pt pronto antes do 1º comentário

        self.geometry("1200x800")
        self.state('zoomed')
        self.configure(bg=TEMA["pagina"])
        self.deiconify()

        self.obras_lista = []
        self.obras_info = {}  # "CA-1439A" -> {"nome", "cliente", "projetista"} (planilha de obras)
        self.tela_atual = None
        self.sessao = {"nome": self.usuario_atual["nome"], "obra": "", "disciplina": ""}
        # (item da barra lateral, sub-item) — destacado na navegação
        self.navegacao_ativa = ("inicio", None)
        self.barra_lateral_recolhida = False
        # tela cheia: o visualizador de PDF esconde a barra lateral e a
        # superior (tem o próprio cabeçalho, como no protótipo)
        self.tela_cheia = False
        self._reabrir_ultima_tela = self.abrir_tela_home

        self.issues = _carregar_banco_dados()
        self._ids_base = {i.get("id") for i in self.issues}
        self.ultima_sincronizacao = datetime.now()
        self.carregar_obras()
        self._montar_shell()
        self.abrir_tela_home()
        self.bind_all("<Control-k>", lambda e: self.barra_topo.focar_busca())
        self.bind_all("<Control-K>", lambda e: self.barra_topo.focar_busca())
        # obra/disciplina/projetista agora são escolhidos ao INICIAR uma
        # verificação (tela "Verificações"), não num pop-up logo após o login

    # ==========================================
    # MOLDURA (barra lateral + barra superior + conteúdo)
    # ==========================================
    def _montar_shell(self):
        if getattr(self, "raiz_ui", None) is not None:
            self.raiz_ui.destroy()
        self.raiz_ui = tk.Frame(self, bg=TEMA["pagina"])
        self.raiz_ui.pack(fill=tk.BOTH, expand=True)
        self.barra_lateral = BarraLateral(self.raiz_ui, self, recolhida=self.barra_lateral_recolhida)
        self.barra_lateral.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=10)
        self._lado_direito = tk.Frame(self.raiz_ui, bg=TEMA["pagina"])
        self._lado_direito.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.barra_topo = BarraTopo(self._lado_direito, self)
        self.barra_topo.pack(side=tk.TOP, fill=tk.X)
        self.main_container = tk.Frame(self._lado_direito, bg=TEMA["pagina"])
        self.main_container.pack(fill=tk.BOTH, expand=True)

    def _atualizar_barras(self, so_lateral=False):
        self.barra_lateral.destroy()
        self.barra_lateral = BarraLateral(self.raiz_ui, self, recolhida=self.barra_lateral_recolhida)
        if not so_lateral:
            self.barra_topo.destroy()
            self.barra_topo = BarraTopo(self._lado_direito, self)
        self._aplicar_tela_cheia()

    def _aplicar_tela_cheia(self):
        if self.tela_cheia:
            self.barra_lateral.pack_forget()
            self.barra_topo.pack_forget()
            return
        if not self.barra_lateral.winfo_manager():
            self.barra_lateral.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=10, before=self._lado_direito)
        if not self.barra_topo.winfo_manager():
            self.barra_topo.pack(side=tk.TOP, fill=tk.X, before=self.main_container)

    def _navegar(self, chave, sub=None):
        self.navegacao_ativa = (chave, sub)
        self._atualizar_barras(so_lateral=True)

    def alternar_barra_lateral(self):
        self.barra_lateral_recolhida = not self.barra_lateral_recolhida
        self._atualizar_barras(so_lateral=True)

    def sair(self):
        """Encerra a sessão e volta para a tela de login (trocar de usuário)."""
        if not messagebox.askyesno("Sair", "Encerrar a sessão e voltar para a tela de login?"):
            return
        self.withdraw()
        dialogo = DialogLogin(self)
        if dialogo.usuario is None:
            self.destroy()
            return
        self.usuario_atual = dialogo.usuario
        self.sessao = {"nome": self.usuario_atual["nome"], "obra": "", "disciplina": ""}
        self.navegacao_ativa = ("inicio", None)
        self._montar_shell()
        self.abrir_tela_home()
        self.deiconify()
        self.state("zoomed")

    # ==========================================
    # SESSÃO DE TRABALHO (obra / disciplina) — nome vem do login
    # ==========================================
    def abrir_dialogo_sessao(self):
        """Pergunta (ou deixa atualizar) obra/disciplina uma vez, para não
        precisar repetir isso em toda issue criada — só 'Atribuído para'
        continua sendo perguntado por issue, já que varia. Não troca de
        tela: se chamado a partir do visualizador de IFC/PDF, o usuário
        continua exatamente onde estava depois de atualizar a sessão."""
        dialogo = DialogSessao(self, lista_obras=self.obras_lista, sessao_atual=self.sessao)
        if dialogo.obra:
            self.sessao = {"nome": self.usuario_atual["nome"], "obra": dialogo.obra,
                           "disciplina": dialogo.disciplina, "atribuido_para": dialogo.atribuido or ""}
            if hasattr(self.tela_atual, "ao_mudar_sessao"):
                self.tela_atual.ao_mudar_sessao()

    def trocar_minha_senha(self):
        """Troca de senha voluntária, acionável a qualquer momento pelo
        próprio usuário logado (botão no cabeçalho da Home)."""
        usuarios = carregar_usuarios()
        usuario = next((u for u in usuarios if u["nome_usuario"] == self.usuario_atual["nome_usuario"]), None)
        if usuario is None:
            messagebox.showerror("Erro", "Não foi possível localizar sua conta no banco de usuários.")
            return
        dialogo = DialogTrocarSenha(self, usuario, obrigatoria=False)
        if dialogo.trocou:
            salvar_usuarios(usuarios)
            self.usuario_atual = usuario
            messagebox.showinfo("OK", "Senha alterada com sucesso.")

    # ==========================================
    # IDENTIDADE VISUAL (ícone da janela/barra de tarefas)
    # ==========================================
    def _aplicar_icone(self):
        """Define o ícone da janela/barra de tarefas como o símbolo do
        Cadari Vizzo. Tenta o .ico (melhor suporte nativo no Windows) e
        cai para o .png via iconphoto se o .ico não estiver disponível."""
        try:
            if os.path.exists(ICONE_VIZZO_ICO):
                self.iconbitmap(default=ICONE_VIZZO_ICO)
                return
        except Exception:
            pass
        try:
            if os.path.exists(ICONE_VIZZO_PNG):
                self._icone_img = ImageTk.PhotoImage(Image.open(ICONE_VIZZO_PNG))
                self.iconphoto(True, self._icone_img)
        except Exception:
            pass

    # ==========================================
    # TEMA VISUAL (modo dia/noite, aplicado globalmente aos widgets ttk)
    # ==========================================
    def alternar_tema(self):
        """Dia <-> noturno (atalho; o menu de tema oferece também o daltônico)."""
        self.definir_tema("claro" if TEMA.esta_escuro() else "escuro")

    def definir_tema(self, modo):
        """Troca o modo (dia / noturno / daltônico) e lembra a escolha
        neste computador. Widgets tk "crus" só pegam a cor no momento em
        que são criados, então a moldura e a tela atual são reconstruídas
        — tentando preservar o que está aberto (modelo IFC carregado, PDF
        aberto, página atual)."""
        if modo == TEMA.modo:
            return
        tela = self.tela_atual
        TEMA.definir(modo)
        preferencias.salvar(tema=TEMA.modo)
        self.configure(bg=TEMA["pagina"])
        self._aplicar_tema()
        self._montar_shell()
        self._reabrir_tela_atual(tela)

    def abrir_menu_tema(self, evento):
        """Menu único de aparência — o mesmo na barra superior e no
        cabeçalho do visualizador de PDF."""
        menu = tk.Menu(self, tearoff=0, font=fonte(10))
        escolha = tk.StringVar(master=menu, value=TEMA.modo)
        for modo, rotulo in MODOS_TEMA.items():
            menu.add_radiobutton(label=rotulo, value=modo, variable=escolha,
                                 command=lambda m=modo: self.definir_tema(m))
        menu._escolha = escolha  # mantém a variável viva enquanto o menu existe
        menu.tk_popup(evento.x_root - 120, evento.y_root + 18)

    def _reabrir_tela_atual(self, tela):
        if isinstance(tela, IFCViewerFrame):
            arquivos = list(tela.arquivos_ifc.keys())
            corte_pct = dict(tela.corte_pct)
            self.abrir_tela_visualizador_ifc()
            for caminho in arquivos:
                self.tela_atual._carregar_ifc(caminho, limpar_existente=False)
            self.tela_atual.corte_pct = corte_pct
            return

        if isinstance(tela, PDFViewerFrame):
            caminho_pdf = tela.current_pdf_path
            pagina = tela.current_page
            zoom = tela.zoom_level
            self.abrir_tela_visualizador_pdf()
            if caminho_pdf:
                self.tela_atual.reabrir_arquivo(caminho_pdf, pagina, zoom)
            return

        # Demais telas não guardam estado importante — reabre a última.
        self._reabrir_ultima_tela()

    def _aplicar_tema(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=TEMA["bg"], foreground=TEMA["texto"],
                         fieldbackground=TEMA["surface_alt"], font=TEMA["fonte"])
        style.configure("TFrame", background=TEMA["bg"])
        style.configure("TLabel", background=TEMA["bg"], foreground=TEMA["texto"])

        style.configure("TNotebook", background=TEMA["surface"], borderwidth=0)
        style.configure("TNotebook.Tab", background=TEMA["surface"], foreground=TEMA["texto_fraco"],
                         padding=(14, 9), borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", TEMA["surface_alt"])],
                  foreground=[("selected", TEMA["texto"])])

        style.configure("Treeview", background=TEMA["surface_alt"], fieldbackground=TEMA["surface_alt"],
                         foreground=TEMA["texto"], borderwidth=0, rowheight=26)
        style.configure("Treeview.Heading", background=TEMA["surface"], foreground=TEMA["texto_fraco"],
                         relief="flat", borderwidth=0)
        style.map("Treeview",
                  background=[("selected", TEMA["acento"])],
                  foreground=[("selected", TEMA["acento_texto"])])
        style.map("Treeview.Heading", background=[("active", TEMA["surface"])])

        style.configure("TCombobox", fieldbackground=TEMA["surface_alt"], background=TEMA["surface_alt"],
                         foreground=TEMA["texto"], arrowcolor=TEMA["texto_fraco"])
        style.map("TCombobox", fieldbackground=[("readonly", TEMA["surface_alt"])])
        style.configure("TEntry", fieldbackground=TEMA["surface_alt"], foreground=TEMA["texto"])

        style.configure("TScrollbar", background=TEMA["surface"], troughcolor=TEMA["bg"],
                         bordercolor=TEMA["bg"], arrowcolor=TEMA["texto_fraco"])
        style.configure("TScale", background=TEMA["bg"], troughcolor=TEMA["surface_alt"])
        style.configure("TPanedwindow", background=TEMA["bg"])
        configurar_estilos_ttk(self)

    # ==========================================
    # BANCO DE DADOS (REDE)
    # ==========================================
    def salvar_banco_dados(self):
        """Grava mesclando com o que está na rede (ver utils.mesclar_issues):
        um app aberto há horas não desfaz mais o trabalho dos outros. A
        lista é atualizada no lugar, para quem guardou referência a ela."""
        gravadas = _salvar_banco_dados(self.issues, ids_base=self._ids_base)
        if gravadas is not self.issues:
            self.issues[:] = gravadas
        self._ids_base = {i.get("id") for i in self.issues}

    def sincronizar_banco(self):
        self.issues = _carregar_banco_dados()
        self._ids_base = {i.get("id") for i in self.issues}
        self.ultima_sincronizacao = datetime.now()
        if self.tela_atual is not None and hasattr(self.tela_atual, "sincronizar"):
            self.tela_atual.sincronizar()
        elif self.tela_atual is None:
            self.abrir_tela_home()
        self._atualizar_barras()
        messagebox.showinfo("Sincronização", "Banco de dados atualizado com as modificações da rede.")

    # ==========================================
    # CADASTRO DE OBRAS (Excel)
    # ==========================================
    def carregar_obras(self, silencioso=True):
        """
        Lê a coluna B (a partir de B7) do arquivo OBRAS_FILE e popula self.obras_lista
        com os números de obra (Nº CADARI). O cabeçalho 'N CADARI' em B7 é descartado
        automaticamente. Aceita valores numéricos e textuais; remove duplicatas
        mantendo a ordem.
        """
        self.obras_lista = []

        if not OPENPYXL_OK:
            if not silencioso:
                messagebox.showwarning(
                    "openpyxl ausente",
                    "A biblioteca openpyxl não está instalada.\n"
                    "Sem ela, a lista de obras ficará vazia.\n\nInstale com:  pip install openpyxl"
                )
            return

        if not os.path.exists(OBRAS_FILE):
            if not silencioso:
                messagebox.showwarning(
                    "Cadastro de obras indisponível",
                    f"Não foi possível encontrar:\n{OBRAS_FILE}\n\n"
                    "Verifique a conexão com a rede (unidade Z:)."
                )
            return

        try:
            wb = load_workbook(OBRAS_FILE, data_only=True, read_only=True, keep_vba=True)
            ws = wb.active  # primeira planilha; ajuste se precisar de outra
            vistos = set()
            ordem = []
            info = {}
            for row in ws.iter_rows(min_row=7, min_col=2, max_col=8, values_only=True):
                valor = row[0]
                if valor is None:
                    continue
                txt = str(valor).strip()
                if not txt:
                    continue
                if txt.upper().replace(".", "").replace(" ", "") in ("NCADARI", "N°CADARI", "NºCADARI"):
                    continue
                if txt not in vistos:
                    vistos.add(txt)
                    ordem.append(txt)
                    # colunas: B Nº CADARI, C início, D nome do projeto, E comercial,
                    # F cliente, G desenhista, H projetista
                    limpar = lambda v: (str(v).strip() if v not in (None, "-") else "")  # noqa: E731
                    info[txt] = {"nome": limpar(row[2]), "cliente": limpar(row[4]),
                                 "projetista": limpar(row[6])}
            wb.close()
            self.obras_lista = ordem
            self.obras_info = info
            if not silencioso:
                messagebox.showinfo("Obras", f"{len(self.obras_lista)} obras carregadas do cadastro.")
        except Exception as e:
            if not silencioso:
                messagebox.showerror(
                    "Erro ao ler cadastro de obras",
                    f"Falha ao abrir {OBRAS_FILE}\n\nErro: {e}"
                )

    # ==========================================
    # NAVEGAÇÃO ENTRE TELAS
    # ==========================================
    def limpar_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()
        self.tela_atual = None

    def abrir_tela_home(self):
        """Início não passa por `_abrir_modulo` (tela_atual fica None):
        não tem estado próprio para sincronizar/preservar."""
        self.limpar_container()
        self.tela_cheia = False
        self._aplicar_tela_cheia()
        TelaInicio(self.main_container, self).pack(fill=tk.BOTH, expand=True)
        self._reabrir_ultima_tela = self.abrir_tela_home
        self._navegar("inicio")

    def _abrir_modulo(self, classe_frame, navegacao=None, tela_cheia=False, **kwargs):
        self.limpar_container()
        self.tela_cheia = tela_cheia
        self._aplicar_tela_cheia()
        frame = classe_frame(self.main_container, self, **kwargs)
        frame.pack(fill=tk.BOTH, expand=True)
        self.tela_atual = frame
        if navegacao:
            self._navegar(*navegacao)
        # Força o Windows a repintar a janela: trocar de tela destrói uma
        # árvore de widgets grande e constrói outra pesada na sequência
        # (ex.: o IFC viewer, que cria uma janela nativa do VTK) sem ceder
        # o controle pro loop de eventos entre os dois passos — às vezes
        # isso deixa a área da janela em preto até algum evento de
        # foco/redimensionamento forçar o repaint.
        self.update()
        frame.focus_set()
        return frame

    # --- Validação de pranchas (PDF) / modelos (IFC) ---
    def abrir_tela_projetos_pdf(self):
        self._reabrir_ultima_tela = self.abrir_tela_projetos_pdf
        self._abrir_modulo(TelaProjetos, ("pdf",), tipo_doc="pdf")

    def abrir_tela_projetos_ifc(self):
        self._reabrir_ultima_tela = self.abrir_tela_projetos_ifc
        self._abrir_modulo(TelaProjetos, ("ifc",), tipo_doc="ifc")

    def abrir_tela_visualizador_pdf(self, pasta_inicial=None):
        tela = self._abrir_modulo(PDFViewerFrame, ("pdf",), tela_cheia=True)
        if pasta_inicial:
            self.after(100, lambda: tela.open_pdf(initialdir=pasta_inicial))
        return tela

    def abrir_tela_visualizador_ifc(self, pasta_inicial=None):
        tela = self._abrir_modulo(IFCViewerFrame, ("ifc",), tela_cheia=True)
        if pasta_inicial and hasattr(tela, "lbl_modelo"):
            self.after(100, lambda: tela.abrir_ifc(initialdir=pasta_inicial))
        return tela

    def abrir_projeto(self, obra, tipo_doc="pdf"):
        """"Abrir projeto": o projeto já tem caminho — abre DIRETO o último
        documento verificado dele (sem seletor de arquivo). Sem documento
        anterior, vai para "Iniciar verificação" já com a obra escolhida."""
        for resumo in resumo_projetos(self.issues, tipo_doc=tipo_doc):
            if resumo["obra"] == obra and resumo["ultimo_arquivo"] and os.path.exists(resumo["ultimo_arquivo"]):
                disciplina = resumo["disciplinas"][0] if len(resumo["disciplinas"]) == 1 else \
                    self.sessao.get("disciplina", "")
                self.abrir_documento(resumo["ultimo_arquivo"], tipo_doc, obra=obra, disciplina=disciplina)
                return
        self.abrir_tela_verificacao(tipo_doc=tipo_doc, obra=obra)

    def abrir_documento(self, caminho, tipo_doc="pdf", obra=None, disciplina=None, atribuido=None, pagina=0):
        """Abre um documento direto no visualizador, já com a sessão da
        verificação (obra/disciplina/projetista) preenchida."""
        if obra:
            self.sessao["obra"] = obra
        if disciplina:
            self.sessao["disciplina"] = disciplina
        if atribuido is not None:
            self.sessao["atribuido_para"] = atribuido
        if tipo_doc == "ifc":
            tela = self.abrir_tela_visualizador_ifc()
            if hasattr(tela, "_carregar_ifc"):
                def carregar():
                    tela._carregar_ifc(caminho, limpar_existente=True)
                    tela.after(300, tela._resetar_camera)  # garante o 1º quadro (senão fica preto até mexer)
                self.after(50, carregar)
        else:
            tela = self.abrir_tela_visualizador_pdf()
            tela.reabrir_arquivo(caminho, pagina)
        return tela

    def abrir_tela_verificacao(self, tipo_doc="pdf", obra=None):
        self._reabrir_ultima_tela = lambda: self.abrir_tela_verificacao(tipo_doc)
        self._abrir_modulo(TelaVerificacao, ("vrf",), tipo_doc=tipo_doc, obra=obra)

    @staticmethod
    def pasta_da_obra(obra):
        if not obra:
            return None
        pasta = os.path.join(PROJETOS_DIR, obra.strip())
        return pasta if os.path.isdir(pasta) else None


    # --- Consulta / Dashboard / Usuários ---
    def abrir_tela_consulta(self, busca=None, issue_id=None, atribuido=None, obra=None):
        self._reabrir_ultima_tela = self.abrir_tela_consulta
        self._abrir_modulo(ConsultaFrame, ("consulta",), busca=busca, issue_id=issue_id,
                           atribuido=atribuido, obra=obra)

    def abrir_tela_dashboard(self, aba="visao"):
        telas = {"visao": PainelControle, "equipe": TelaEquipe,
                 "conformidade": TelaConformidade, "relatorio": TelaDashboard}
        aba = aba if aba in telas else "visao"
        self._reabrir_ultima_tela = lambda: self.abrir_tela_dashboard(aba)
        self._abrir_modulo(telas[aba], ("dashboard", aba))

    def abrir_tela_usuarios(self):
        self._reabrir_ultima_tela = self.abrir_tela_usuarios
        self._abrir_modulo(PainelUsuarios, ("usuarios",))
