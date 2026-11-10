"""Botão "Baixar" do visualizador de PDF: gera uma CÓPIA da prancha com
tudo que foi marcado no app gravado no próprio PDF — selos de
certificação (com a legenda do status), desenhos, formas, balões, textos
e os pinos numerados dos problemas. O arquivo original nunca é alterado.

Coordenadas: o app guarda os pontos no espaço da página renderizada
(`page.get_pixmap`, já com a rotação aplicada); as funções de desenho do
PyMuPDF usam o espaço sem rotação, então todo ponto passa pela
`page.derotation_matrix`."""
import math

import fitz  # PyMuPDF

from certificacao import ATIVO, estado_selo, legenda_selo
from utils import hex_to_rgb01

LARGURA_LINHA = 0.75  # px de tela -> pt (as espessuras foram escolhidas em pixels)


def _cor(hex_cor, padrao="#FF3B30"):
    try:
        return hex_to_rgb01(hex_cor or padrao)
    except (ValueError, TypeError):
        return hex_to_rgb01(padrao)


def _ponto(pagina, x, y):
    return fitz.Point(x, y) * pagina.derotation_matrix


def _retangulo(pagina, x1, y1, x2, y2):
    p1, p2 = _ponto(pagina, x1, y1), _ponto(pagina, x2, y2)
    return fitz.Rect(min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y))


def _desenhar_anotacao(pagina, a):
    tipo = a.get("tipo")
    cor = _cor(a.get("cor"))
    largura = max(0.5, a.get("espessura", 3) * LARGURA_LINHA)
    forma = pagina.new_shape()

    if tipo == "desenho" and len(a.get("pontos", [])) > 1:
        forma.draw_polyline([_ponto(pagina, x, y) for x, y in a["pontos"]])
        forma.finish(color=cor, width=largura, closePath=False)
    elif tipo in ("forma", "revisao"):
        (x1, y1), (x2, y2) = a["pontos"]
        subtipo = a.get("forma", "retangulo") if tipo == "forma" else "retangulo"
        if subtipo == "circulo":
            forma.draw_oval(_retangulo(pagina, x1, y1, x2, y2))
        elif subtipo == "triangulo":
            xm = (x1 + x2) / 2
            forma.draw_polyline([_ponto(pagina, xm, y1), _ponto(pagina, x2, y2),
                                 _ponto(pagina, x1, y2), _ponto(pagina, xm, y1)])
        elif subtipo == "seta":
            inicio, fim = _ponto(pagina, x1, y1), _ponto(pagina, x2, y2)
            forma.draw_line(inicio, fim)
            angulo = math.atan2(fim.y - inicio.y, fim.x - inicio.x)
            for desvio in (2.6, -2.6):
                ponta = fim + (12 * math.cos(angulo + desvio), 12 * math.sin(angulo + desvio))
                forma.draw_line(fim, ponta)
        else:
            forma.draw_rect(_retangulo(pagina, x1, y1, x2, y2))
        forma.finish(color=cor, width=largura)
    elif tipo == "balao":
        (x1, y1), (x2, y2) = a["pontos"]
        caixa = _retangulo(pagina, x1, y1, x2, y2)
        forma.draw_rect(caixa)
        forma.finish(color=cor, fill=(1, 0.965, 0.847), width=largura)
        forma.commit()
        pagina.insert_textbox(caixa + (4, 4, -4, -4), a.get("texto", ""), fontsize=9, color=(0.13, 0.13, 0.13))
        return
    elif tipo == "texto":
        (x, y), = a["pontos"]
        tamanho = a.get("fonte_tamanho", 16)
        pagina.insert_text(_ponto(pagina, x, y + tamanho), a.get("texto", ""), fontsize=tamanho,
                           color=cor, fontname="helv")
        return
    elif tipo == "selo":
        (x, y), = a["pontos"]
        caixa = _retangulo(pagina, x, y, x + a.get("largura", 130), y + a.get("altura", 130))
        try:
            pagina.insert_image(caixa, filename=a["arquivo_selo"], keep_proportion=True, overlay=True)
        except Exception:
            pass  # selo removido da rede: a legenda abaixo ainda registra o status
        legenda = fitz.Rect(caixa.x0 - 40, caixa.y1 + 2, caixa.x1 + 40, caixa.y1 + 26)
        # fonte base do PDF (Helvetica) não tem travessão: troca por hífen
        pagina.insert_textbox(legenda, legenda_selo(a).replace("—", "-"), fontsize=7.5, align=fitz.TEXT_ALIGN_CENTER,
                              color=(0.15, 0.2, 0.22))
        return
    else:
        return
    forma.commit()


def _desenhar_pino(pagina, issue, cores_status):
    centro = _ponto(pagina, issue.get("pdf_x", 0), issue.get("pdf_y", 0))
    forma = pagina.new_shape()
    forma.draw_circle(centro, 8)
    forma.finish(color=(1, 1, 1), fill=_cor(cores_status.get(issue.get("status"), "#999999")), width=1.5)
    forma.commit()
    texto = str(issue.get("id", ""))
    largura = fitz.get_text_length(texto, fontname="hebo", fontsize=7)
    pagina.insert_text(fitz.Point(centro.x - largura / 2, centro.y + 2.5), texto, fontsize=7,
                       fontname="hebo", color=(1, 1, 1))


def exportar_pdf_anotado(origem, destino, anotacoes, issues, cores_status):
    """Grava em `destino` a cópia de `origem` com as marcações e pinos.
    Devolve quantos itens foram gravados."""
    documento = fitz.open(origem)
    gravados = 0
    try:
        for a in anotacoes:
            if a.get("filepath") != origem:
                continue
            if a.get("tipo") == "selo" and estado_selo(a, anotacoes) != ATIVO:
                continue  # substituídos/removidos ficam só no histórico
            pagina_idx = a.get("page", 0)
            if not 0 <= pagina_idx < documento.page_count:
                continue
            _desenhar_anotacao(documento[pagina_idx], a)
            gravados += 1
        for issue in issues:
            if issue.get("tipo_doc", "pdf") != "pdf" or issue.get("filepath") != origem:
                continue
            pagina_idx = issue.get("page", 0)
            if not 0 <= pagina_idx < documento.page_count:
                continue
            _desenhar_pino(documento[pagina_idx], issue, cores_status)
            gravados += 1
        documento.save(destino, garbage=3, deflate=True)
    finally:
        documento.close()
    return gravados
