"""Regras de exclusão automática — interferências que, por regra de
negócio, nunca deveriam aparecer no relatório porque não representam um
problema real de compatibilização."""
import numpy as np

import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.system

CLASSES_VOIDAVEIS = {
    "IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcBeam", "IfcColumn",
    "IfcFooting", "IfcRoof", "IfcCurtainWall",
}
CLASSES_ISOLAMENTO = {"IfcCovering"}


def _bbox_sobrepoe(min_a, max_a, min_b, max_b, folga=0.0):
    return all(min_a[k] - folga <= max_b[k] and min_b[k] - folga <= max_a[k] for k in range(3))


def _bbox_contem(min_a, max_a, min_b, max_b, tolerancia=0.0):
    return all(min_a[k] - tolerancia <= min_b[k] and max_b[k] <= max_a[k] + tolerancia for k in range(3))


def _bbox_da_abertura(abertura, escala_para_metros, settings):
    try:
        shape = ifcopenshell.geom.create_shape(settings, abertura)
    except Exception:
        return None
    verts = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3) * escala_para_metros
    if verts.shape[0] == 0:
        return None
    return verts.min(axis=0), verts.max(axis=0)


def eh_furo_previsto(elemento_a, elemento_b, arquivos_ifc, escala_por_arquivo, settings):
    """True se um dos dois elementos é uma estrutura/vedação que já tem
    uma IfcOpeningElement cujo bounding box sobrepõe o bounding box do
    OUTRO elemento — ou seja, o furo/passagem já estava previsto no
    projeto de origem, não é uma interferência a corrigir."""
    for estrutural, outro in ((elemento_a, elemento_b), (elemento_b, elemento_a)):
        if estrutural.ifc_class not in CLASSES_VOIDAVEIS:
            continue
        ifc_file = arquivos_ifc.get(estrutural.arquivo)
        if ifc_file is None:
            continue
        elemento_ifc = ifc_file.by_guid(estrutural.guid)
        # get_openings devolve IfcRelVoidsElement, não a abertura em si
        aberturas = [rel.RelatedOpeningElement for rel in ifcopenshell.util.element.get_openings(elemento_ifc)]
        if not aberturas:
            continue
        escala = escala_por_arquivo.get(estrutural.arquivo, 1.0)
        for abertura in aberturas:
            bbox = _bbox_da_abertura(abertura, escala, settings)
            if bbox is None:
                continue
            bbox_min, bbox_max = bbox
            if _bbox_sobrepoe(bbox_min, bbox_max, outro.bbox_min, outro.bbox_max):
                return True
    return False


def _sistemas_do_elemento(elemento, arquivos_ifc):
    ifc_file = arquivos_ifc.get(elemento.arquivo)
    if ifc_file is None:
        return set()
    elemento_ifc = ifc_file.by_guid(elemento.guid)
    try:
        sistemas = ifcopenshell.util.system.get_element_systems(elemento_ifc)
    except Exception:
        return set()
    return {sistema.id() for sistema in sistemas}


def eh_mesmo_sistema(elemento_a, elemento_b, arquivos_ifc):
    """Aproximação para 'elementos do mesmo sistema conectados entre
    si': True se os dois elementos compartilham pelo menos um
    IfcSystem. Não verifica conectividade porta-a-porta — ver
    docs/CLASH_DETECTION.md para a limitação."""
    sistemas_a = _sistemas_do_elemento(elemento_a, arquivos_ifc)
    if not sistemas_a:
        return False
    sistemas_b = _sistemas_do_elemento(elemento_b, arquivos_ifc)
    return bool(sistemas_a & sistemas_b)


def eh_isolamento_sobre_duto(elemento_a, elemento_b):
    """True se um dos dois é um IfcCovering (tipicamente a camada de
    isolamento) cujo bounding box contém quase inteiramente o do outro —
    sinal de que é o próprio isolamento em volta do tubo/duto, não uma
    interferência real."""
    for revestimento, outro in ((elemento_a, elemento_b), (elemento_b, elemento_a)):
        if revestimento.ifc_class not in CLASSES_ISOLAMENTO or outro.ifc_class in CLASSES_ISOLAMENTO:
            continue
        if _bbox_contem(revestimento.bbox_min, revestimento.bbox_max, outro.bbox_min, outro.bbox_max,
                         tolerancia=0.02):
            return True
    return False


def elemento_ignorado_manualmente(elemento, regras):
    return elemento.guid in set(regras.exclusoes.get("guids_aceitos_manualmente", []))


def deve_excluir(elemento_a, elemento_b, arquivos_ifc, escala_por_arquivo, settings, regras):
    """Ponto único de checagem de exclusão, usado pelo motor antes de
    classificar um par candidato como interferência. Retorna
    (True, motivo) ou (False, None)."""
    if regras.exclusoes.get("ignorar_furos_previstos", True):
        if eh_furo_previsto(elemento_a, elemento_b, arquivos_ifc, escala_por_arquivo, settings):
            return True, "furo previsto (IfcOpeningElement já existente no projeto)"

    if regras.exclusoes.get("ignorar_mesmo_sistema_conectado", True):
        if eh_mesmo_sistema(elemento_a, elemento_b, arquivos_ifc):
            return True, "elementos pertencem ao mesmo sistema"

    if regras.exclusoes.get("ignorar_isolamento_proprio_duto", True):
        if eh_isolamento_sobre_duto(elemento_a, elemento_b):
            return True, "isolamento sobre o próprio tubo/duto"

    if elemento_ignorado_manualmente(elemento_a, regras) or elemento_ignorado_manualmente(elemento_b, regras):
        return True, "elemento na lista de exclusão manual das regras"

    return False, None
