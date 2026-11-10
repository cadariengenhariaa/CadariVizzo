"""Exportação BCF 2.1 — um tópico por interferência, com viewpoint
(câmera + os dois componentes IFC selecionados) e snapshot quando
possível, para abrir direto no Revit/Navisworks/Solibri/BIMcollab etc.

Segue o mesmo estilo já usado no projeto para lidar com BCF — zipfile +
xml.etree.ElementTree manual, sem biblioteca externa (ver
`bcf_import.py`, que lê o formato inverso, pensado para o modelo de PDF
x,y das issues manuais; este módulo escreve o formato "de verdade",
baseado em seleção de componentes IFC)."""
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone

from clash.relatorio.snapshot_3d import capturar_snapshot_do_clash

STATUS_PARA_BCF = {
    "Novo": "Open", "Em análise": "Open", "Atribuído": "Open", "Reaberto": "ReOpened",
    "Resolvido": "Resolved", "Aprovado": "Closed", "Aceito": "Closed",
}
TIPO_PARA_BCF = {"hard": "Clash", "folga": "Clearance", "duplicado": "Duplicate"}


def _sub(pai, tag, texto=None, **atributos):
    el = ET.SubElement(pai, tag, atributos)
    if texto is not None:
        el.text = str(texto)
    return el


def _descricao(clash):
    linhas = [
        f"Disciplinas: {clash['disciplina_a']} x {clash['disciplina_b']}",
        f"Responsável sugerido: {clash['responsavel_sugerido']}",
        f"Pavimento: {clash.get('nivel') or '—'}",
        f"Elemento A: {clash['elemento_a']['ifc_class']} \"{clash['elemento_a']['nome']}\" "
        f"({clash['elemento_a']['guid']}) — {clash['elemento_a']['arquivo']}",
        f"Elemento B: {clash['elemento_b']['ifc_class']} \"{clash['elemento_b']['nome']}\" "
        f"({clash['elemento_b']['guid']}) — {clash['elemento_b']['arquivo']}",
    ]
    if clash.get("penetracao_m") is not None:
        linhas.append(f"Penetração: {clash['penetracao_m']:.3f} m")
    if clash.get("volume_intersecao_m3") is not None:
        linhas.append(f"Volume de interseção: {clash['volume_intersecao_m3']:.4f} m³")
    if clash.get("distancia_m") is not None and clash.get("folga_exigida_m") is not None:
        linhas.append(f"Distância medida: {clash['distancia_m']:.3f} m "
                       f"(folga exigida: {clash['folga_exigida_m']:.3f} m)")
    linhas.append("")
    linhas.append("[Sugestão automática — avaliar com a equipe, não é uma decisão de projeto]")
    return "\n".join(linhas)


def _montar_markup(clash, agora):
    root = ET.Element("Markup")
    topic = ET.SubElement(root, "Topic", {
        "Guid": clash["id_bcf"],
        "TopicType": TIPO_PARA_BCF.get(clash["tipo"], "Issue"),
        "TopicStatus": STATUS_PARA_BCF.get(clash.get("status", "Novo"), "Open"),
    })
    _sub(topic, "Title",
         f"[{clash['severidade']}] {clash['disciplina_a']} x {clash['disciplina_b']} — "
         f"{clash['elemento_a']['ifc_class']} x {clash['elemento_b']['ifc_class']}")
    _sub(topic, "Priority", clash["severidade"])
    _sub(topic, "CreationDate", clash.get("data_criacao") or agora)
    _sub(topic, "CreationAuthor", "Visualizador Cadari — Clash Detection")
    if clash.get("responsavel_atribuido"):
        _sub(topic, "AssignedTo", clash["responsavel_atribuido"])
    _sub(topic, "Description", _descricao(clash))

    for comentario in clash.get("historico_status", []):
        bloco = ET.SubElement(root, "Comment", {"Guid": str(uuid.uuid4())})
        _sub(bloco, "Date", comentario.get("data") or agora)
        _sub(bloco, "Author", comentario.get("por", "sistema"))
        _sub(bloco, "Comment", f"Status alterado de {comentario.get('de') or '—'} para {comentario.get('para')}")
        ET.SubElement(bloco, "Topic", {"Guid": clash["id_bcf"]})

    if clash.get("comentario"):
        bloco = ET.SubElement(root, "Comment", {"Guid": str(uuid.uuid4())})
        _sub(bloco, "Date", agora)
        _sub(bloco, "Author", "Visualizador Cadari")
        _sub(bloco, "Comment", clash["comentario"])
        ET.SubElement(bloco, "Topic", {"Guid": clash["id_bcf"]})

    viewpoints = ET.SubElement(root, "Viewpoints", {"Guid": str(uuid.uuid4())})
    _sub(viewpoints, "Viewpoint", "viewpoint.bcfv")
    if clash.get("_tem_snapshot"):
        _sub(viewpoints, "Snapshot", "snapshot.png")

    return root


def _montar_viewpoint(clash):
    """Viewpoint com os dois elementos da interferência selecionados
    (por IfcGuid) — o essencial pedido no requisito ("com viewpoint,
    câmera e componentes selecionados"). A câmera usa uma direção
    genérica olhando de cima/lado para os componentes; cada software
    BIM reenquadra automaticamente a seleção ao abrir o tópico."""
    root = ET.Element("VisualizationInfo", {"Guid": str(uuid.uuid4())})

    componentes = ET.SubElement(root, "Components")
    selecao = ET.SubElement(componentes, "Selection")
    for chave in ("elemento_a", "elemento_b"):
        ET.SubElement(selecao, "Component", {"IfcGuid": clash[chave]["guid"]})

    camera = ET.SubElement(root, "PerspectiveCamera")
    ponto = ET.SubElement(camera, "CameraViewPoint")
    _sub(ponto, "X", 0); _sub(ponto, "Y", 0); _sub(ponto, "Z", 0)
    direcao = ET.SubElement(camera, "CameraDirection")
    _sub(direcao, "X", 0); _sub(direcao, "Y", -1); _sub(direcao, "Z", -1)
    cima = ET.SubElement(camera, "CameraUpVector")
    _sub(cima, "X", 0); _sub(cima, "Y", 0); _sub(cima, "Z", 1)
    _sub(camera, "FieldOfView", 60)

    return root


def _escrever_xml(elemento_raiz, bcf_zip, caminho_no_zip):
    conteudo = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(elemento_raiz, encoding="unicode")
    bcf_zip.writestr(caminho_no_zip, conteudo)


def exportar_bcf(clashes, caminho_bcfzip, arquivos_ifc=None, escala_por_arquivo=None, settings=None,
                  incluir_snapshot=True):
    """`arquivos_ifc`/`escala_por_arquivo`: se fornecidos (os mesmos
    dicts usados em `clash.motor.rodar_clash`), cada tópico ganha um
    snapshot.png (ver `clash.relatorio.snapshot_3d`). Sem eles, ou se o
    arquivo de origem de algum elemento não estiver mais acessível
    (ex.: relatório gerado fora da rede), o BCF sai válido do mesmo
    jeito, só sem a imagem — nunca falha o export inteiro por causa de
    um snapshot."""
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with zipfile.ZipFile(caminho_bcfzip, "w", zipfile.ZIP_DEFLATED) as bcf_zip:
        bcf_zip.writestr(
            "bcf.version",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Version VersionId="2.1">\n  <DetailedVersion>2.1</DetailedVersion>\n</Version>',
        )

        for clash_original in clashes:
            clash = dict(clash_original)
            clash["id_bcf"] = str(uuid.uuid4())
            pasta = clash["id_bcf"]

            clash["_tem_snapshot"] = False
            if incluir_snapshot and arquivos_ifc and escala_por_arquivo:
                with tempfile.TemporaryDirectory() as tmp:
                    caminho_png = os.path.join(tmp, "snapshot.png")
                    if capturar_snapshot_do_clash(clash, arquivos_ifc, escala_por_arquivo, caminho_png,
                                                   settings=settings):
                        bcf_zip.write(caminho_png, f"{pasta}/snapshot.png")
                        clash["_tem_snapshot"] = True

            _escrever_xml(_montar_markup(clash, agora), bcf_zip, f"{pasta}/markup.bcf")
            _escrever_xml(_montar_viewpoint(clash), bcf_zip, f"{pasta}/viewpoint.bcfv")

    return caminho_bcfzip
