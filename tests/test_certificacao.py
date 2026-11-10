"""Testes de certificacao.py (selo -> status da prancha) e de
pdf_exportacao.py ("Baixar": cópia do PDF com selos/marcações/pinos) —
tudo em pasta temporária, com PDF e selos sintéticos."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz
from PIL import Image

from certificacao import (
    ATIVO,
    REMOVIDO,
    SUBSTITUIDO,
    aplicar_selo,
    estado_selo,
    mover_selo,
    remover_selo,
    selo_ativo,
    codigo_selo,
    info_selo,
    legenda_selo,
    listar_selos,
    selos_do_documento,
    status_certificacao,
    tom_claro,
)
from pdf_exportacao import exportar_pdf_anotado

PDF = "Z:/obra/prancha.pdf"


def _selo(id_, arquivo, data, filepath=PDF, page=0):
    return {"id": id_, "tipo": "selo", "filepath": filepath, "page": page, "arquivo_selo": arquivo,
            "pontos": [[50, 50]], "largura": 80, "altura": 80, "autor": "Ana", "data": data}


def test_codigo_e_info_do_selo_vem_do_nome_do_arquivo():
    assert codigo_selo("Z:/SELOS/apr.png") == "APR"
    info = info_selo("Z:/SELOS/RPV.png")
    assert (info["codigo"], info["descricao"]) == ("RPV", "Reprovado")
    desconhecido = info_selo("Z:/SELOS/LIBERADO.png")
    assert desconhecido["codigo"] == "LIBERADO" and desconhecido["descricao"] == "Liberado"


def test_status_e_o_selo_mais_recente_do_documento():
    anotacoes = [
        _selo(1, "S/APCR.png", "18/10/2026 10:00:00"),
        _selo(2, "S/APR.png", "20/10/2026 09:00:00"),
        _selo(3, "S/RPV.png", "21/10/2026 09:00:00", filepath="outro.pdf"),
        {"id": 4, "tipo": "desenho", "filepath": PDF, "page": 0, "pontos": [[0, 0], [1, 1]]},
    ]
    assert [a["id"] for a in selos_do_documento(anotacoes, PDF)] == [1, 2]
    status = status_certificacao(anotacoes, PDF)
    assert status["codigo"] == "APR" and status["autor"] == "Ana" and status["anotacao_id"] == 2
    assert status_certificacao(anotacoes, "sem_selo.pdf") is None
    assert legenda_selo(anotacoes[1]) == "APR · Aprovado — 20/10/2026 · Ana"


def test_listar_selos_ordena_conhecidos_primeiro_e_ignora_o_resto():
    pasta = tempfile.mkdtemp(prefix="teste_selos_")
    for nome in ("RPV.png", "APR.png", "ZZZ.png", "Thumbs.db", "APR.pdf"):
        open(os.path.join(pasta, nome), "wb").close()
    os.mkdir(os.path.join(pasta, "Ultrapassados"))
    assert [s["codigo"] for s in listar_selos(pasta)] == ["APR", "RPV", "ZZZ"]
    assert listar_selos(os.path.join(pasta, "nao_existe")) == []


def test_tom_claro():
    assert tom_claro("#000000", 0.5) == "#80808" + "0"
    assert tom_claro("#FFFFFF") == "#FFFFFF"


def test_exportar_pdf_anotado_grava_selo_legenda_marcacoes_e_pinos():
    pasta = tempfile.mkdtemp(prefix="teste_export_")
    origem = os.path.join(pasta, "prancha.pdf")
    destino = os.path.join(pasta, "prancha_revisada.pdf")
    doc = fitz.open()
    doc.new_page(width=600, height=400)
    doc.save(origem)
    doc.close()
    selo_png = os.path.join(pasta, "APR.png")
    Image.new("RGBA", (64, 64), (74, 138, 18, 255)).save(selo_png)

    anotacoes = [
        _selo(1, selo_png, "20/10/2026 09:00:00", filepath=origem),
        {"id": 2, "tipo": "desenho", "filepath": origem, "page": 0, "pontos": [[10, 10], [60, 80]], "cor": "#FF0000"},
        {"id": 3, "tipo": "forma", "forma": "seta", "filepath": origem, "page": 0, "pontos": [[100, 100], [200, 150]]},
        {"id": 4, "tipo": "balao", "filepath": origem, "page": 0, "pontos": [[300, 50], [450, 120]], "texto": "Nota"},
        {"id": 5, "tipo": "texto", "filepath": origem, "page": 0, "pontos": [[300, 300]], "texto": "Ver detalhe"},
        {"id": 6, "tipo": "desenho", "filepath": "outro.pdf", "page": 0, "pontos": [[0, 0], [1, 1]]},
    ]
    issues = [{"id": 7, "tipo_doc": "pdf", "filepath": origem, "page": 0, "pdf_x": 500, "pdf_y": 350,
               "status": "Novo"}]
    gravados = exportar_pdf_anotado(origem, destino, anotacoes, issues, {"Novo": "#E74C3C"})
    assert gravados == 6  # 5 anotações deste PDF + 1 pino

    resultado = fitz.open(destino)
    pagina = resultado[0]
    texto = pagina.get_text()
    assert "APR · Aprovado" in texto and "Nota" in texto and "Ver detalhe" in texto and "7" in texto
    assert len(pagina.get_images()) == 1
    resultado.close()
    assert fitz.open(origem)[0].get_text() == ""  # original intocado


def test_um_selo_por_prancha_novo_substitui_e_historico_fica():
    anotacoes = []
    aplicar_selo(anotacoes, _selo(1, "S/APCR.png", "18/10/2026 10:00:00"))
    aplicar_selo(anotacoes, _selo(2, "S/APR.png", "20/10/2026 09:00:00"))
    aplicar_selo(anotacoes, _selo(3, "S/RPV.png", "20/10/2026 09:30:00", filepath="outra.pdf"))
    primeiro, segundo, outro = anotacoes
    assert len(anotacoes) == 3                                   # nada é apagado
    assert estado_selo(primeiro, anotacoes) == SUBSTITUIDO
    assert primeiro["substituido_por"] == 2 and primeiro["substituido_em"] == "20/10/2026 09:00:00"
    assert estado_selo(segundo, anotacoes) == ATIVO
    assert estado_selo(outro, anotacoes) == ATIVO                # outra prancha não é afetada
    assert selo_ativo(anotacoes, PDF)["id"] == 2
    assert [a["id"] for a in selos_do_documento(anotacoes, PDF)] == [1, 2]  # histórico completo


def test_remover_tira_da_prancha_sem_apagar_e_sem_reativar_o_anterior():
    anotacoes = []
    aplicar_selo(anotacoes, _selo(1, "S/APCR.png", "18/10/2026 10:00:00"))
    aplicar_selo(anotacoes, _selo(2, "S/APR.png", "20/10/2026 09:00:00"))
    assert remover_selo(anotacoes, 2, autor="Ana", quando="21/10/2026 08:00:00")
    assert estado_selo(anotacoes[1], anotacoes) == REMOVIDO and anotacoes[1]["removido_por"] == "Ana"
    assert estado_selo(anotacoes[0], anotacoes) == SUBSTITUIDO
    assert status_certificacao(anotacoes, PDF) is None           # "aguardando certificação"
    assert len(selos_do_documento(anotacoes, PDF)) == 2


def test_mover_selo_e_registros_antigos_sem_estado():
    anotacoes = [_selo(1, "S/APCR.png", "18/10/2026 10:00:00"), _selo(2, "S/APR.png", "20/10/2026 09:00:00")]
    # antigos (sem "estado"): o mais recente é o ativo
    assert [estado_selo(a, anotacoes) for a in anotacoes] == [SUBSTITUIDO, ATIVO]
    assert mover_selo(anotacoes, 2, 300.0, 120.0, "21/10/2026 08:00:00")
    assert anotacoes[1]["pontos"] == [[300.0, 120.0]] and anotacoes[1]["movido_em"].startswith("21/10")
    aplicar_selo(anotacoes, _selo(3, "S/RPV.png", "21/10/2026 09:00:00"))
    assert [estado_selo(a, anotacoes) for a in anotacoes] == [SUBSTITUIDO, SUBSTITUIDO, ATIVO]


def test_exportar_grava_so_o_selo_ativo():
    pasta = tempfile.mkdtemp(prefix="teste_export_selo_")
    origem = os.path.join(pasta, "prancha.pdf")
    destino = os.path.join(pasta, "saida.pdf")
    doc = fitz.open()
    doc.new_page(width=600, height=400)
    doc.save(origem)
    doc.close()
    for nome, cor in (("APCR.png", (217, 130, 43, 255)), ("APR.png", (74, 138, 18, 255))):
        Image.new("RGBA", (32, 32), cor).save(os.path.join(pasta, nome))
    anotacoes = []
    aplicar_selo(anotacoes, _selo(1, os.path.join(pasta, "APCR.png"), "18/10/2026 10:00:00", filepath=origem))
    aplicar_selo(anotacoes, _selo(2, os.path.join(pasta, "APR.png"), "20/10/2026 09:00:00", filepath=origem))
    exportar_pdf_anotado(origem, destino, anotacoes, [], {})
    pagina = fitz.open(destino)[0]
    texto = pagina.get_text()
    assert "APR · Aprovado" in texto and "APCR" not in texto
    assert len(pagina.get_images()) == 1


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE CERTIFICAÇÃO/EXPORTAÇÃO PASSARAM")
