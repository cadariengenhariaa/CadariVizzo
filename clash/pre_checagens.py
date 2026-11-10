"""Pré-checagens de qualidade executadas ANTES do clash propriamente
dito. O objetivo é alertar sobre problemas que, se ignorados, geram
interferências enganosas (falsos positivos ou negativos) — estas
checagens nunca travam o processo, só registram os achados para
aparecerem no resumo executivo do relatório."""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

import ifcopenshell.util.unit

# Distância entre os centros de dois arquivos acima da qual soa alarme de
# possível desalinhamento (origem/georreferenciamento diferentes) — só
# dispara se, além disso, cada modelo individualmente for bem menor que
# isso (ver `checar_desalinhamento`). padrão a validar pela equipe
LIMIAR_DISTANCIA_DESALINHAMENTO_M = 1000.0


@dataclass
class ResultadoPreChecagens:
    escala_por_arquivo: Dict[str, float]
    unidades_inconsistentes: bool
    alerta_desalinhamento: bool
    distancia_entre_centros_m: Optional[float]
    guids_duplicados: List[dict] = field(default_factory=list)
    elementos_sem_geometria: List[dict] = field(default_factory=list)
    elementos_sem_nivel: List[dict] = field(default_factory=list)
    geometria_invalida: List[dict] = field(default_factory=list)
    niveis_por_arquivo: Dict[str, list] = field(default_factory=dict)
    niveis_sem_correspondencia: bool = False

    def tem_alertas_bloqueantes(self):
        """Problemas graves o bastante para o relatório abrir com um
        aviso de destaque recomendando NÃO confiar cegamente nos
        resultados de clash desta rodada."""
        return self.unidades_inconsistentes or self.alerta_desalinhamento


def checar_unidades(arquivos_ifc):
    """`arquivos_ifc`: dict {caminho: ifc_file}. Retorna o fator de escala
    (para metros) de cada arquivo e se há inconsistência entre eles —
    inconsistência aqui só preocupa porque o motor de clash JÁ normaliza
    cada arquivo para metros (ver `clash.geometria`); o alerta é para o
    usuário saber que a normalização foi necessária e confirmar que o
    valor faz sentido (ex.: um arquivo não declarado em milímetros por
    engano quando deveria ser metros)."""
    escala_por_arquivo = {
        caminho: ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
        for caminho, ifc_file in arquivos_ifc.items()
    }
    escalas = list(escala_por_arquivo.values())
    inconsistentes = len(escalas) > 1 and (max(escalas) - min(escalas)) > 1e-9
    return escala_por_arquivo, inconsistentes


def checar_desalinhamento(elementos):
    """Agrupa os elementos por arquivo, calcula o centro do bounding box
    de cada arquivo e compara a maior distância entre centros contra
    `LIMIAR_DISTANCIA_DESALINHAMENTO_M`. Só soa alarme quando, além de
    distantes, cada modelo é individualmente bem menor que essa
    distância — do contrário um prédio grande e genuinamente alinhado
    acionaria um falso alarme."""
    centros_por_arquivo = {}
    diagonal_por_arquivo = {}
    por_arquivo = defaultdict(list)
    for elemento in elementos:
        por_arquivo[elemento.arquivo].append(elemento)

    for arquivo, els in por_arquivo.items():
        mins = np.array([e.bbox_min for e in els])
        maxs = np.array([e.bbox_max for e in els])
        bbox_min = mins.min(axis=0)
        bbox_max = maxs.max(axis=0)
        centros_por_arquivo[arquivo] = (bbox_min + bbox_max) / 2.0
        diagonal_por_arquivo[arquivo] = float(np.linalg.norm(bbox_max - bbox_min))

    arquivos = list(centros_por_arquivo.keys())
    maior_distancia = None
    for i in range(len(arquivos)):
        for j in range(i + 1, len(arquivos)):
            a, b = arquivos[i], arquivos[j]
            distancia = float(np.linalg.norm(centros_por_arquivo[a] - centros_por_arquivo[b]))
            if maior_distancia is None or distancia > maior_distancia:
                maior_distancia = distancia

    if maior_distancia is None:
        return False, None

    modelos_pequenos_frente_a_distancia = all(
        diag < LIMIAR_DISTANCIA_DESALINHAMENTO_M for diag in diagonal_por_arquivo.values()
    )
    alerta = maior_distancia > LIMIAR_DISTANCIA_DESALINHAMENTO_M and modelos_pequenos_frente_a_distancia
    return alerta, maior_distancia


def checar_guids_duplicados(elementos):
    """GlobalId duplicado — seja dentro do mesmo arquivo (erro de
    modelagem/exportação) seja entre arquivos diferentes (GUIDs IFC
    deveriam ser globalmente únicos)."""
    por_guid = defaultdict(list)
    for elemento in elementos:
        por_guid[elemento.guid].append(elemento.arquivo)

    return [
        {"guid": guid, "arquivos": arquivos}
        for guid, arquivos in por_guid.items()
        if len(arquivos) > 1
    ]


def checar_elementos_sem_geometria(ifc_file, caminho_arquivo, elementos_extraidos):
    """Compara todos os IfcElement do arquivo contra os que
    `clash.geometria.extrair_elementos` conseguiu triangular — a
    diferença são elementos sem representação geométrica (ou com
    representação que o ifcopenshell não conseguiu processar)."""
    guids_com_geometria = {e.guid for e in elementos_extraidos if e.arquivo == caminho_arquivo}
    sem_geometria = []
    for elemento in ifc_file.by_type("IfcElement"):
        if elemento.GlobalId not in guids_com_geometria:
            sem_geometria.append({
                "guid": elemento.GlobalId,
                "arquivo": caminho_arquivo,
                "ifc_class": elemento.is_a(),
                "nome": getattr(elemento, "Name", None) or "",
            })
    return sem_geometria


def checar_elementos_sem_nivel(elementos):
    return [
        {"guid": e.guid, "arquivo": e.arquivo, "ifc_class": e.ifc_class, "nome": e.nome}
        for e in elementos
        if e.nivel is None
    ]


def checar_geometria_invalida(elementos):
    """Malha com vértices não-finitos (NaN/Inf) ou com uma das três
    dimensões do bounding box praticamente zero enquanto as outras duas
    não são (sólido "achatado" — sinal comum de representação
    corrompida ou de uma extrusão com espessura zero)."""
    invalidos = []
    for elemento in elementos:
        malha = elemento.malha
        motivo = None
        if not np.all(np.isfinite(malha.vertices)):
            motivo = "vértices não-finitos (NaN/Inf) na malha"
        else:
            tamanho = elemento.bbox_max - elemento.bbox_min
            quase_zero = tamanho < 1e-6
            if quase_zero.sum() >= 1 and not quase_zero.all() and max(tamanho) > 1e-3:
                motivo = "geometria achatada (uma dimensão do bounding box é ~0 enquanto as outras não são)"
        if motivo:
            invalidos.append({"guid": elemento.guid, "arquivo": elemento.arquivo,
                               "ifc_class": elemento.ifc_class, "motivo": motivo})
    return invalidos


def checar_niveis_entre_arquivos(elementos):
    """Lista o conjunto de nomes de pavimento encontrados em cada
    arquivo e sinaliza quando, havendo mais de um arquivo, eles não têm
    NENHUM nome de pavimento em comum — indício forte de nomenclatura de
    pavimento inconsistente entre disciplinas, o que quebra qualquer
    filtro/relatório "por pavimento"."""
    niveis_por_arquivo = defaultdict(set)
    for elemento in elementos:
        if elemento.nivel:
            niveis_por_arquivo[elemento.arquivo].add(elemento.nivel)

    niveis_por_arquivo = {arquivo: sorted(niveis) for arquivo, niveis in niveis_por_arquivo.items()}

    sem_correspondencia = False
    conjuntos = [set(niveis) for niveis in niveis_por_arquivo.values() if niveis]
    if len(conjuntos) > 1:
        intersecao = set.intersection(*conjuntos)
        sem_correspondencia = len(intersecao) == 0

    return niveis_por_arquivo, sem_correspondencia


def executar_pre_checagens(arquivos_ifc, elementos):
    """`arquivos_ifc`: dict {caminho: ifc_file} já abertos.
    `elementos`: lista de `ElementoClash` já extraída (todos os
    arquivos) por `clash.geometria.extrair_elementos`."""
    escala_por_arquivo, unidades_inconsistentes = checar_unidades(arquivos_ifc)
    alerta_desalinhamento, distancia = checar_desalinhamento(elementos)
    niveis_por_arquivo, niveis_sem_correspondencia = checar_niveis_entre_arquivos(elementos)

    sem_geometria = []
    for caminho, ifc_file in arquivos_ifc.items():
        sem_geometria.extend(checar_elementos_sem_geometria(ifc_file, caminho, elementos))

    return ResultadoPreChecagens(
        escala_por_arquivo=escala_por_arquivo,
        unidades_inconsistentes=unidades_inconsistentes,
        alerta_desalinhamento=alerta_desalinhamento,
        distancia_entre_centros_m=distancia,
        guids_duplicados=checar_guids_duplicados(elementos),
        elementos_sem_geometria=sem_geometria,
        elementos_sem_nivel=checar_elementos_sem_nivel(elementos),
        geometria_invalida=checar_geometria_invalida(elementos),
        niveis_por_arquivo=niveis_por_arquivo,
        niveis_sem_correspondencia=niveis_sem_correspondencia,
    )
