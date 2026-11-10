"""Extração independente de geometria por elemento IFC, para uso pelo
motor de clash.

Importante: isto NÃO reaproveita as estruturas de `ifc_viewer.py`. Lá a
geometria é mesclada por grupo (arquivo, nível, cor) só para acelerar a
renderização, e os limites por elemento individual não sobrevivem a
isso — só um índice de faixas de célula para picking. O motor de clash
precisa testar pares de elementos individualmente, então itera o IFC do
zero e mantém uma malha (`trimesh.Trimesh`) própria por elemento, em
coordenadas do mundo."""
import multiprocessing
from dataclasses import dataclass
from typing import Optional

import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.unit
import numpy as np
import trimesh

from clash.disciplinas import inferir_disciplina


@dataclass
class ElementoClash:
    guid: str
    ifc_class: str
    nome: str
    disciplina: str
    nivel: Optional[str]
    arquivo: str
    malha: trimesh.Trimesh  # sempre em METROS, não na unidade nativa do arquivo IFC
    bbox_min: np.ndarray
    bbox_max: np.ndarray
    # GlobalId do IfcBuildingStorey (None se o elemento não estiver em
    # nenhum) — além do nome (`nivel`, só para exibição), guardado para
    # casar exatamente com a chave (caminho, GlobalId) que
    # ifc_viewer.IFCViewerFrame.niveis_info já usa, já que dois níveis
    # podem ter o mesmo nome. Usado por `clash.selecao` para decidir se
    # o elemento está marcado na árvore Seleção A/B. Campo com valor
    # padrão (vai por último) para não quebrar construções posicionais
    # antigas em teste.
    nivel_guid: Optional[str] = None


def configuracoes_padrao():
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    return settings


def extrair_elementos(ifc_file, caminho_arquivo, regras, settings=None, callback_progresso=None):
    """Itera todo o IFC e devolve uma lista de `ElementoClash` — um por
    elemento com geometria válida (triangulável), já normalizada para
    METROS. Elementos sem geometria (ex.: IfcSpace sem representação)
    não aparecem aqui; a pré-checagem de "geometria ausente"
    (`clash.pre_checagens`) é quem lista esses separadamente, iterando
    os IfcProduct do arquivo.

    Importante sobre unidades: `ifcopenshell.geom` devolve os vértices
    em bruto, no MESMO número que foi usado para desenhar o elemento —
    ele NÃO converte automaticamente para metros, mesmo com
    USE_WORLD_COORDS ligado (confirmado empiricamente: um elemento de
    "4.0" unidades num arquivo cuja unidade de comprimento é milímetro
    sai com bounding box de 4.0, não 0.004). Como as folgas/tolerâncias
    de `regras_clash.yaml` são todas em metros, e um modelo de
    coordenação pode ter arquivos em unidades diferentes, aqui a malha
    de cada elemento é escalada por
    `ifcopenshell.util.unit.calculate_unit_scale(ifc_file)` antes de
    qualquer teste de interferência."""
    settings = settings or configuracoes_padrao()
    escala_para_metros = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)

    elementos = []
    n_threads = max(1, multiprocessing.cpu_count() - 1)
    iterator = ifcopenshell.geom.iterator(settings, ifc_file, n_threads)
    total = 0
    if iterator.initialize():
        while True:
            shape = iterator.get()
            elemento = _shape_para_elemento(shape, ifc_file, caminho_arquivo, regras, escala_para_metros)
            if elemento is not None:
                elementos.append(elemento)
            total += 1
            if callback_progresso and total % 200 == 0:
                callback_progresso(total)
            if not iterator.next():
                break
    return elementos


def _shape_para_elemento(shape, ifc_file, caminho_arquivo, regras, escala_para_metros):
    verts = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
    faces = np.asarray(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
    if verts.shape[0] == 0 or faces.shape[0] == 0:
        return None

    verts = verts * escala_para_metros

    # process=False: mantém a malha exatamente como o ifcopenshell gerou
    # (sem o trimesh "corrigir" vértices duplicados/degenerados sozinho)
    # para não mascarar problemas reais de geometria nas pré-checagens.
    malha = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

    # shape.product não está vinculado ao arquivo (shape.product.file é
    # None) — ifcopenshell.util.* precisa do elemento "de verdade",
    # buscado pelo GlobalId no próprio ifc_file.
    elemento = ifc_file.by_guid(shape.guid)

    # IfcFeatureElement (aberturas/furos, projeções, features de
    # superfície) tem geometria só para fins de corte booleano — não é
    # um objeto físico e nunca deve ser testado como se fosse um sólido
    # colidível (senão toda abertura prevista geraria "clash" contra o
    # próprio elemento que ela voida e contra o que passa por dentro
    # dela). `clash.exclusoes.eh_furo_previsto` já consulta as aberturas
    # diretamente pelo IFC, então excluí-las daqui não afeta aquela checagem.
    if elemento.is_a("IfcFeatureElement"):
        return None

    nivel_nome, nivel_guid = _nivel_do_elemento(elemento)
    return ElementoClash(
        guid=shape.guid,
        ifc_class=elemento.is_a(),
        nome=getattr(elemento, "Name", None) or "",
        disciplina=inferir_disciplina(elemento, caminho_arquivo, regras),
        nivel=nivel_nome,
        arquivo=caminho_arquivo,
        malha=malha,
        bbox_min=malha.bounds[0],
        bbox_max=malha.bounds[1],
        nivel_guid=nivel_guid,
    )


def malha_por_guid(ifc_file, guid, escala_para_metros, settings=None):
    """Recria a malha (em metros) de UM elemento já conhecido pelo GUID —
    usado pelo relatório (ex.: `clash.relatorio.snapshot_3d`) para gerar
    a imagem de uma interferência específica sem precisar guardar a
    malha inteira de cada elemento no `db_clashes.json` (que fica só com
    guid/classe/nome, bem mais leve)."""
    settings = settings or configuracoes_padrao()
    elemento = ifc_file.by_guid(guid)
    shape = ifcopenshell.geom.create_shape(settings, elemento)
    verts = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3) * escala_para_metros
    faces = np.asarray(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def _nivel_do_elemento(elemento):
    """Devolve (nome, GlobalId) do IfcBuildingStorey do elemento, ou
    (None, None) se não estiver em nenhum."""
    container = ifcopenshell.util.element.get_container(elemento)
    if container is not None and container.is_a("IfcBuildingStorey"):
        return container.Name, container.GlobalId
    return None, None
