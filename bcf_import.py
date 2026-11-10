"""Funções auxiliares para importação de issues a partir de arquivos BCF
(BIM Collaboration Format), associando-as à prancha em PDF atualmente aberta."""
import os
import re
import xml.etree.ElementTree as ET
import zipfile

_PADRAO_COORDENADAS = re.compile(
    r'pdf_x\s*[:=]\s*(-?\d+(?:\.\d+)?)[\s;,]+pdf_y\s*[:=]\s*(-?\d+(?:\.\d+)?)',
    re.IGNORECASE
)


def extrair_referencia_prancha(root):
    """
    Procura no XML do markup.bcf uma referência ao nome da prancha (PDF).
    Retorna o nome de referência encontrado (string) ou None se nada bater.
    Locais inspecionados:
      - Topic/DocumentReferences/DocumentReference (atributos e filhos)
      - Header/File (atributos ReferenceLink/Reference e elemento Filename)
      - Topic/Title e Topic/Description (procura por trecho .pdf)
    """
    candidatos = []

    for dr in root.findall('.//DocumentReference'):
        ref_attr = dr.get('ReferencedDocument')
        if ref_attr:
            candidatos.append(ref_attr)
        ref_el = dr.find('ReferencedDocument')
        if ref_el is not None and ref_el.text:
            candidatos.append(ref_el.text)
        desc_el = dr.find('Description')
        if desc_el is not None and desc_el.text:
            candidatos.append(desc_el.text)

    for f in root.findall('.//Header/File'):
        for attr in ('Reference', 'ReferenceLink'):
            val = f.get(attr)
            if val:
                candidatos.append(val)
        fname_el = f.find('Filename')
        if fname_el is not None and fname_el.text:
            candidatos.append(fname_el.text)

    topic = root.find('.//Topic')
    if topic is not None:
        t_el = topic.find('Title')
        if t_el is not None and t_el.text:
            candidatos.append(t_el.text)
        d_el = topic.find('Description')
        if d_el is not None and d_el.text:
            candidatos.append(d_el.text)

    for c in candidatos:
        if c and c.strip():
            return c.strip()
    return None


def referencia_bate_com_pdf(referencia, pdf_path):
    """
    Verifica se a string 'referencia' (extraída do BCF) aponta para o PDF aberto.
    Compara basename (sem extensão) de forma case-insensitive — também aceita
    match parcial (a referência contém o nome da prancha como substring).
    """
    if not referencia or not pdf_path:
        return False
    ref_low = referencia.lower()
    nome_pdf = os.path.splitext(os.path.basename(pdf_path))[0].lower()
    nome_pdf_completo = os.path.basename(pdf_path).lower()
    return (
        nome_pdf in ref_low
        or nome_pdf_completo in ref_low
        or ref_low in nome_pdf
    )


def extrair_localizacao(bcf_zip, pasta_uuid, root):
    """
    Procura a localização (pdf_x, pdf_y) da issue.
    Estratégia (em ordem):
      1) viewpoint.bcfv -> OrthogonalCamera/PerspectiveCamera -> CameraViewPoint (X,Y)
      2) Tag customizada na descrição/comentários no formato [pdf_x=NNN;pdf_y=NNN]
    Retorna (x, y) ou (None, None) se não encontrar.
    """
    viewpoints = [
        n for n in bcf_zip.namelist()
        if n.startswith(f"{pasta_uuid}/") and n.lower().endswith(".bcfv")
    ]
    for vp_path in viewpoints:
        try:
            with bcf_zip.open(vp_path) as vf:
                vroot = ET.parse(vf).getroot()
                for cam_tag in ('OrthogonalCamera', 'PerspectiveCamera'):
                    cam = vroot.find(f'.//{cam_tag}')
                    if cam is not None:
                        cvp = cam.find('CameraViewPoint')
                        if cvp is not None:
                            x_el = cvp.find('X')
                            y_el = cvp.find('Y')
                            if x_el is not None and y_el is not None:
                                try:
                                    return float(x_el.text), float(y_el.text)
                                except (TypeError, ValueError):
                                    pass
        except Exception:
            continue

    textos = []
    topic = root.find('.//Topic')
    if topic is not None:
        for tag in ('Description', 'Title'):
            el = topic.find(tag)
            if el is not None and el.text:
                textos.append(el.text)
    for c in root.findall('.//Comment/Comment'):
        if c.text:
            textos.append(c.text)
    for c in root.findall('.//Comment'):
        if c.text:
            textos.append(c.text)

    for t in textos:
        m = _PADRAO_COORDENADAS.search(t)
        if m:
            try:
                return float(m.group(1)), float(m.group(2))
            except ValueError:
                pass

    return None, None


def ler_issues_bcf(filepath, pdf_path_atual, pagina_atual):
    """
    Lê um arquivo .bcfzip e retorna (issues_extraidas, relatorio):
      - issues_extraidas: lista de dicts prontos para virar issues (falta id/obra/tipo_doc)
      - relatorio: dict com contagens e detalhes das issues ignoradas
    """
    issues_extraidas = []
    ignoradas_sem_prancha = 0
    ignoradas_sem_localizacao = 0
    detalhes_ignoradas = []

    with zipfile.ZipFile(filepath, 'r') as bcf_zip:
        pastas = set(item.split('/')[0] for item in bcf_zip.namelist() if '/' in item)

        for pasta_uuid in pastas:
            markup_path = f"{pasta_uuid}/markup.bcf"
            if markup_path not in bcf_zip.namelist():
                continue

            with bcf_zip.open(markup_path) as file:
                root = ET.parse(file).getroot()

                topic = root.find('.//Topic')
                titulo = topic.find('Title').text if (topic is not None and topic.find('Title') is not None) else "Sem Título"
                status = topic.find('TopicStatus').text if (topic is not None and topic.find('TopicStatus') is not None) else "Novo"
                criado_por = topic.find('CreationAuthor').text if (topic is not None and topic.find('CreationAuthor') is not None) else "BCF Import"
                atribuido_para = topic.find('AssignedTo').text if (topic is not None and topic.find('AssignedTo') is not None) else ""
                desc = topic.find('Description').text if (topic is not None and topic.find('Description') is not None) else ""

                referencia = extrair_referencia_prancha(root)
                if not referencia_bate_com_pdf(referencia, pdf_path_atual):
                    ignoradas_sem_prancha += 1
                    detalhes_ignoradas.append(
                        f"• \"{titulo}\" — sem referência à prancha aberta "
                        f"(ref. encontrada: {referencia or 'nenhuma'})"
                    )
                    continue

                pdf_x, pdf_y = extrair_localizacao(bcf_zip, pasta_uuid, root)
                if pdf_x is None or pdf_y is None:
                    ignoradas_sem_localizacao += 1
                    detalhes_ignoradas.append(f"• \"{titulo}\" — sem localização (X,Y) detectável")
                    continue

                data_criacao_bcf = topic.find('CreationDate') if topic is not None else None
                data_mod_bcf = topic.find('ModifiedDate') if topic is not None else None

                status_map = {"Open": "Novo", "Closed": "Fechado", "Resolved": "Respondido"}

                issues_extraidas.append({
                    "page": pagina_atual,
                    "filepath": pdf_path_atual,
                    "pdf_x": pdf_x,
                    "pdf_y": pdf_y,
                    "titulo": f"[BCF] {titulo}",
                    "status": status_map.get(status, "Novo"),
                    "tipo": "Concepção",
                    "criado_por": criado_por,
                    "atribuido_para": atribuido_para,
                    "desc": desc,
                    "historico": [],
                    "data_criacao": data_criacao_bcf.text if (data_criacao_bcf is not None and data_criacao_bcf.text) else None,
                    "data_modificacao": data_mod_bcf.text if (data_mod_bcf is not None and data_mod_bcf.text) else None,
                })

    relatorio = {
        "importadas": len(issues_extraidas),
        "ignoradas_sem_prancha": ignoradas_sem_prancha,
        "ignoradas_sem_localizacao": ignoradas_sem_localizacao,
        "detalhes_ignoradas": detalhes_ignoradas,
    }
    return issues_extraidas, relatorio
