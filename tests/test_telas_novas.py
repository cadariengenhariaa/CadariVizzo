"""Teste de fumaça das telas no estilo Figma (Início, Meus projetos PDF/
IFC, Consulta, Painel de controle/Equipe/Conformidade, Usuários) e da
troca de tema/barra lateral — monta cada tela com issues sintéticas num
DB_DIR temporário (nunca o banco de produção) e confere que nada quebra.
Os visualizadores PDF/IFC em si ficam de fora (pesados, já têm testes
próprios das partes lógicas)."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_telas_novas_")
config.DB_FILE = os.path.join(config.DB_DIR, "db_issues.json")

import utils

utils.DB_DIR = config.DB_DIR
utils.DB_FILE = config.DB_FILE
utils.ANOTACOES_FILE = os.path.join(config.DB_DIR, "db_anotacoes_pdf.json")
os.environ["CADARI_VIZZO_PREFS"] = os.path.join(config.DB_DIR, "preferencias.json")

import app as app_module
from app import AppCDE
from consulta import ConsultaFrame

ADMIN = {"nome_usuario": "admin", "email": "admin@a.com", "nome": "Ana Admin", "papel": "administrador",
         "setor": "Setor BIM", "ativo": True}
PROJETISTA = {"nome_usuario": "bruno", "email": "bruno@a.com", "nome": "Bruno Projetista",
              "papel": "projetista", "setor": "Projetista PCI", "ativo": True}


def _issues():
    base = []
    for n, (obra, status, tipo_doc) in enumerate([
        ("CA-1000", "Novo", "pdf"), ("CA-1000", "Fechado", "pdf"), ("CA-2000", "Respondido", "pdf"),
        ("CA-3000", "Reaberto", "ifc"), ("", "Novo", "pdf"),
    ], start=1):
        base.append({
            "id": n, "titulo": f"Issue {n}", "status": status, "tipo": "Dúvida", "obra": obra,
            "disciplina": "PCI", "criado_por": "Ana Admin", "atribuido_para": "Bruno Projetista",
            "desc": "Descrição", "historico": [{"data": "18/10/2026 10:00", "texto": "ok", "autor": "Ana Admin"}],
            "data_criacao": "15/10/2026 10:00:00", "data_modificacao": "18/10/2026 10:00:00",
            "tipo_doc": tipo_doc, "filepath": "C:/nao/existe.pdf", "page": 0,
        })
    return base


def _preparar(usuario):
    assert config.DB_DIR.startswith(tempfile.gettempdir())
    with open(config.DB_FILE, "w", encoding="utf-8") as f:
        json.dump(_issues(), f)
    with open(os.path.join(config.DB_DIR, "db_usuarios.json"), "w", encoding="utf-8") as f:
        json.dump([dict(ADMIN, senha_hash="x", senha_salt="y"), dict(PROJETISTA, senha_hash="x", senha_salt="y")], f)

    class _Login:
        def __init__(self, parent):
            self.usuario = usuario

    app_module.DialogLogin = _Login
    AppCDE.carregar_obras = lambda self, silencioso=True: setattr(self, "obras_lista", ["CA-1000", "CA-2000"])
    AppCDE.abrir_dialogo_sessao = lambda self: None
    return AppCDE()


def test_todas_as_telas_novas_montam_sem_erro_e_navegacao_marca_a_barra_lateral():
    a = _preparar(ADMIN)
    try:
        a.update()
        assert a.navegacao_ativa == ("inicio", None)
        a.abrir_tela_projetos_pdf()
        assert a.navegacao_ativa == ("pdf", None)
        a.abrir_tela_projetos_ifc()
        a.abrir_tela_consulta(issue_id=3)
        assert isinstance(a.tela_atual, ConsultaFrame)
        assert a.tela_atual.issue_atual["id"] == 3
        a.abrir_tela_consulta(busca="issue 2")
        assert set(a.tela_atual.tree_consulta.get_children()) == {"2"}
        a.abrir_tela_consulta(atribuido="Bruno Projetista", obra="CA-1000")
        assert set(a.tela_atual.tree_consulta.get_children()) == {"1", "2"}
        for aba in ("visao", "equipe", "conformidade", "relatorio"):
            a.abrir_tela_dashboard(aba)
            assert a.navegacao_ativa == ("dashboard", aba)
        a.abrir_tela_usuarios()
        a.tela_atual.tree.selection_set("bruno")
        a.tela_atual._mostrar_detalhes()
        a.alternar_barra_lateral()
        a.alternar_tema()   # reconstrói a moldura e reabre a tela atual
        a.alternar_tema()
        a.abrir_tela_home()
        a.update()
    finally:
        a.destroy()
    print("OK todas as telas novas montam, navegam e sobrevivem à troca de tema")


def test_projetista_ve_so_os_proprios_projetos_e_nao_ve_gerenciar_usuarios():
    a = _preparar(PROJETISTA)
    try:
        a.abrir_tela_projetos_pdf()
        obras = {r["obra"] for r in a.tela_atual.resumos}
        assert obras == {"CA-1000", "CA-2000"}  # PDF; CA-3000 é IFC
        textos = []

        def coletar(w):
            for filho in w.winfo_children():
                if hasattr(filho, "texto"):
                    textos.append(filho.texto)
                coletar(filho)
        coletar(a.barra_lateral)
        assert "Gerenciar Usuários" not in textos
        assert "Início" in textos
    finally:
        a.destroy()
    print("OK projetista: projetos filtrados por papel e sem o item Gerenciar Usuários")


def test_visualizador_pdf_comentar_status_selo_exibir_e_baixar():
    import fitz
    from PIL import Image

    import tkinter as tk
    from certificacao import status_certificacao

    pasta = config.DB_DIR
    pdf = os.path.join(pasta, "prancha_teste.pdf")
    doc = fitz.open()
    pg = doc.new_page(width=842, height=595)
    pg.insert_text((100, 100), "PLANTA")
    doc.save(pdf)
    doc.close()
    selo = os.path.join(pasta, "APR.png")
    Image.new("RGBA", (64, 64), (74, 138, 18, 255)).save(selo)

    a = _preparar(ADMIN)
    tk.Toplevel.wait_window = lambda self, *x, **k: None  # diálogos não bloqueiam no teste
    try:
        a.sessao.update({"obra": "CA-1000", "disciplina": "PCI", "atribuido_para": "Bruno Projetista"})
        tela = a.abrir_tela_visualizador_pdf()
        assert a.tela_cheia and not a.barra_lateral.winfo_manager()  # visualizador em tela cheia
        tela.reabrir_arquivo(pdf, 0)
        a.update()

        # Comentar: marca o local e cria direto (sessão completa: obra/disciplina/projetista)
        tela.set_tool("pin")
        tela.local_pendente = (0, 200.0, 150.0)
        novo_id = tela.criar_issue_no_local("Verificar cota do shaft\ndetalhe", "Documentação")
        issue = next(i for i in a.issues if i["id"] == novo_id)
        assert (issue["status"], issue["tipo"], issue["atribuido_para"]) == ("Novo", "Documentação", "Bruno Projetista")
        assert issue["titulo"] == "Verificar cota do shaft" and issue["filepath"] == pdf
        tela.ir_para_issue(issue)
        tela.painel.alterar_status(issue, "Respondido")
        assert issue["status"] == "Respondido" and "Status alterado" in issue["historico"][-1]["texto"]

        # Certificação: selo -> status da prancha
        tela.iniciar_colocacao_selo(selo)
        tela._colocar_selo(100, 100)
        assert status_certificacao(tela.anotacoes, pdf)["codigo"] == "APR"
        tela.painel.mostrar_aba("certificacao")

        # um selo por prancha: o segundo substitui o primeiro (que some da prancha, fica no histórico)
        selo2 = os.path.join(pasta, "APCA.png")
        Image.new("RGBA", (64, 64), (201, 165, 31, 255)).save(selo2)
        tela.iniciar_colocacao_selo(selo2)
        tela._colocar_selo(400, 300)
        selos = [x for x in tela.anotacoes if x.get("tipo") == "selo"]
        assert len(selos) == 2 and status_certificacao(tela.anotacoes, pdf)["codigo"] == "APCA"
        desenhados = {t for item in tela.canvas.find_withtag("anot") for t in tela.canvas.gettags(item)
                      if t.startswith("anot_")}
        assert desenhados == {f"anot_{selos[1]['id']}"}

        # arrastar o selo com "Selecionar"
        tela.set_tool("pan")
        (px, py), = selos[1]["pontos"]
        x0 = px * tela.zoom_level + 5
        y0 = py * tela.zoom_level + 5
        tela._movendo_selo = {"id": selos[1]["id"], "inicio": (x0, y0), "ultimo": (x0 + 50, y0 + 20)}
        tela._soltar_selo()
        (nx, ny), = selos[1]["pontos"]
        assert abs(nx - (px + 50 / tela.zoom_level)) < 1e-6 and abs(ny - (py + 20 / tela.zoom_level)) < 1e-6
        assert selos[1].get("movido_em")

        # voltando ao APR para o resto do teste (APCA vira "substituído")
        tela.iniciar_colocacao_selo(selo)
        tela._colocar_selo(100, 100)
        assert len([x for x in tela.anotacoes if x.get("tipo") == "selo"]) == 3

        # menu Exibir e modos
        for acao in (tela.tamanho_real, lambda: tela._ajustar("largura"), lambda: tela._ajustar("altura"),
                     tela.ajustar_conteudo_visivel, tela.ajustar_a_tela):
            acao()
        tela.alternar_modo_leitura()
        assert not tela._barra_ferramentas.winfo_manager()
        tela.alternar_modo_leitura()

        # Baixar (sem diálogo de arquivo)
        destino = os.path.join(pasta, "prancha_teste_revisado.pdf")
        import pdf_viewer
        pdf_viewer.filedialog.asksaveasfilename = lambda **k: destino
        pdf_viewer.messagebox.showinfo = lambda *x, **k: None
        tela.exportar_pdf()
        assert os.path.exists(destino) and "APR" in fitz.open(destino)[0].get_text()

        # título genérico pré-preenchido, copiar issue para outro local, nome do "Baixar"
        assert tela.painel.ent_titulo.get().startswith("Problema ")
        antes = len(a.issues)
        tela.iniciar_copia(issue)
        tela._colar_copia(300, 200)
        copia = a.issues[-1]
        assert len(a.issues) == antes + 1 and copia["titulo"] == issue["titulo"] and copia["status"] == "Novo"
        assert "Copiado do problema" in copia["historico"][0]["texto"]
        tela.set_tool("pan")
        assert tela._nome_sugerido_baixar() == "prancha_teste_AA_APR.pdf"  # Ana Admin + selo APR

        # tema daltônico reabre o mesmo PDF
        a.definir_tema("daltonico_vv")
        a.definir_tema("daltonico_aa")
        assert a.tela_atual.current_pdf_path == pdf
        a.definir_tema("claro")
        a.abrir_tela_projetos_pdf()
        assert not a.tela_cheia and a.barra_lateral.winfo_manager()
        resumo = next(r for r in a.tela_atual.resumos if r["obra"] == "CA-1000")
        assert resumo["situacao"] == "Certificado" and resumo["certificacao"]["codigo"] == "APR"
    finally:
        a.destroy()
    print("OK visualizador PDF: comentar, status, selo, Exibir, modo leitura, Baixar e tema daltônico")


def test_tela_verificacao_lista_arquivos_da_pasta_vrf_e_abre_direto():
    base = tempfile.mkdtemp(prefix="teste_cadari_vrf_")
    pasta = os.path.join(base, "CA-1000", "1000-VRF", "1000-PCI")
    os.makedirs(pasta)
    import fitz
    doc = fitz.open()
    doc.new_page()
    doc.save(os.path.join(pasta, "1000-PCI_PE_R00.pdf"))
    doc.close()
    open(os.path.join(pasta, "1000-PCI_PE_R00_AA_APCA.pdf"), "wb").close()
    config.PROJETOS_DIR = base

    a = _preparar(ADMIN)
    try:
        a.abrir_tela_verificacao("pdf", obra="CA-1000")
        tela = a.tela_atual
        tela.cb_disciplina.set("PCI")
        tela.cb_projetista.set("Bruno Projetista")
        tela._atualizar_documentos()
        assert tela.lbl_pasta.cget("text") == pasta
        assert len(tela.lista_docs.winfo_children()) == 4  # 2 linhas + 2 separadores
        tela._abrir(os.path.join(pasta, "1000-PCI_PE_R00.pdf"))
        assert a.tela_cheia and a.tela_atual.current_pdf_path.endswith("1000-PCI_PE_R00.pdf")
        assert (a.sessao["obra"], a.sessao["disciplina"], a.sessao["atribuido_para"]) ==             ("CA-1000", "PCI", "Bruno Projetista")
    finally:
        a.destroy()
    print("OK Verificações: arquivos da pasta VRF da obra/disciplina, abre direto com a sessão preenchida")


def test_ajuda_e_suporte_abre_o_formulario_de_chamados():
    import ui.shell as shell
    abertos = []
    original_startfile, original_exists = shell.os.startfile, shell.os.path.exists
    shell.os.startfile = abertos.append
    shell.os.path.exists = lambda caminho: caminho == config.CHAMADOS_EXE or original_exists(caminho)
    a = _preparar(ADMIN)
    try:
        a.barra_lateral._ajuda()
        assert abertos == [config.CHAMADOS_EXE]
        assert config.CHAMADOS_EXE.endswith("Abertura de Chamados.exe")
    finally:
        shell.os.startfile, shell.os.path.exists = original_startfile, original_exists
        a.destroy()
    print("OK Ajuda e suporte abre o executável de abertura de chamados")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DAS TELAS NOVAS PASSARAM")
