"""Testes de clash/pre_checagens.py: unidades, desalinhamento, GUIDs
duplicados, elementos sem geometria/nível, geometria inválida e níveis
sem correspondência entre arquivos."""
import os
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ifcopenshell.api

from clash.geometria import ElementoClash, extrair_elementos
from clash.pre_checagens import (
    checar_desalinhamento,
    checar_elementos_sem_geometria,
    checar_elementos_sem_nivel,
    checar_geometria_invalida,
    checar_guids_duplicados,
    checar_niveis_entre_arquivos,
    checar_unidades,
    executar_pre_checagens,
)
from tests.fixtures_clash import adicionar_elemento_prisma
from tests.fixtures_clash import carregar_regras_teste as carregar_regras
from tests.fixtures_clash import criar_ifc_base


def _elemento_fake(guid, arquivo, nivel="Pav1", centro=(0, 0, 0), tamanho=(1, 1, 1)):
    malha = trimesh.creation.box(extents=tamanho)
    malha.apply_translation(centro)
    return ElementoClash(
        guid=guid, ifc_class="IfcWall", nome="x", disciplina="ARQ", nivel=nivel,
        arquivo=arquivo, malha=malha, bbox_min=malha.bounds[0], bbox_max=malha.bounds[1],
    )


# ---------- unidades ----------
def test_unidades_consistentes_mesmo_prefixo():
    f1, _, _ = criar_ifc_base(prefixo_unidade_comprimento="MILLI")
    f2, _, _ = criar_ifc_base(prefixo_unidade_comprimento="MILLI")
    escalas, inconsistentes = checar_unidades({"a.ifc": f1, "b.ifc": f2})
    assert not inconsistentes
    assert escalas["a.ifc"] == escalas["b.ifc"]
    print("OK unidades iguais não disparam alerta")


def test_unidades_inconsistentes_entre_arquivos():
    f1, _, _ = criar_ifc_base(prefixo_unidade_comprimento="MILLI")
    f2, _, _ = criar_ifc_base(prefixo_unidade_comprimento=None)
    escalas, inconsistentes = checar_unidades({"a.ifc": f1, "b.ifc": f2})
    assert inconsistentes
    assert escalas["a.ifc"] != escalas["b.ifc"]
    print("OK unidades diferentes entre arquivos são detectadas")


# ---------- desalinhamento ----------
def test_sem_alerta_quando_modelos_proximos():
    elementos = [
        _elemento_fake("g1", "a.ifc", centro=(0, 0, 0)),
        _elemento_fake("g2", "b.ifc", centro=(5, 0, 0)),
    ]
    alerta, distancia = checar_desalinhamento(elementos)
    assert not alerta
    print("OK modelos próximos não disparam alerta de desalinhamento, distância:", distancia)


def test_alerta_quando_modelos_muito_distantes():
    elementos = [
        _elemento_fake("g1", "a.ifc", centro=(0, 0, 0), tamanho=(10, 10, 3)),
        _elemento_fake("g2", "b.ifc", centro=(500000, 200000, 0), tamanho=(10, 10, 3)),
    ]
    alerta, distancia = checar_desalinhamento(elementos)
    assert alerta
    assert distancia > 100000
    print("OK modelos distantes (georreferenciados x locais) disparam alerta, distância:", distancia)


# ---------- GUIDs duplicados ----------
def test_guid_duplicado_entre_arquivos():
    elementos = [
        _elemento_fake("GUID-REPETIDO", "a.ifc"),
        _elemento_fake("GUID-REPETIDO", "b.ifc"),
        _elemento_fake("guid-unico", "a.ifc"),
    ]
    duplicados = checar_guids_duplicados(elementos)
    assert len(duplicados) == 1
    assert duplicados[0]["guid"] == "GUID-REPETIDO"
    assert sorted(duplicados[0]["arquivos"]) == ["a.ifc", "b.ifc"]
    print("OK GUID duplicado entre arquivos detectado")


def test_sem_duplicados_nao_reporta_nada():
    elementos = [_elemento_fake("g1", "a.ifc"), _elemento_fake("g2", "a.ifc")]
    assert checar_guids_duplicados(elementos) == []
    print("OK nenhum falso positivo quando todos os GUIDs são únicos")


# ---------- elementos sem geometria ----------
def test_elemento_sem_representacao_e_listado():
    f, body, storey = criar_ifc_base()
    adicionar_elemento_prisma(f, body, storey, nome="ComGeometria", ifc_class="IfcWall")
    sem_rep = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="SemGeometria")
    ifcopenshell.api.run("spatial.assign_container", f, products=[sem_rep], relating_structure=storey)

    regras = carregar_regras()
    extraidos = extrair_elementos(f, "a.ifc", regras)
    assert len(extraidos) == 1  # só o que tem geometria foi extraído

    sem_geometria = checar_elementos_sem_geometria(f, "a.ifc", extraidos)
    assert len(sem_geometria) == 1
    assert sem_geometria[0]["guid"] == sem_rep.GlobalId
    print("OK elemento sem representação geométrica é listado, não ignorado")


# ---------- elementos sem nível ----------
def test_elemento_sem_nivel_e_listado():
    f, body, storey = criar_ifc_base()
    com_nivel = adicionar_elemento_prisma(f, body, storey, nome="ComNivel", ifc_class="IfcWall")
    sem_nivel = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="SemNivel")
    rep = ifcopenshell.api.run("geometry.add_wall_representation", f, context=body, length=1.0, height=1.0, thickness=0.1)
    ifcopenshell.api.run("geometry.assign_representation", f, product=sem_nivel, representation=rep)
    # propositalmente NÃO associado a nenhum IfcBuildingStorey

    regras = carregar_regras()
    extraidos = extrair_elementos(f, "a.ifc", regras)
    sem_nivel_resultado = checar_elementos_sem_nivel(extraidos)

    guids_sem_nivel = {e["guid"] for e in sem_nivel_resultado}
    assert sem_nivel.GlobalId in guids_sem_nivel
    assert com_nivel.GlobalId not in guids_sem_nivel
    print("OK elemento sem pavimento associado é listado")


# ---------- geometria inválida ----------
def test_geometria_achatada_e_detectada():
    malha_normal = trimesh.creation.box(extents=(1, 1, 1))
    malha_achatada = trimesh.creation.box(extents=(5, 5, 1e-9))

    elementos = [
        ElementoClash("g_ok", "IfcWall", "ok", "ARQ", "Pav1", "a.ifc", malha_normal,
                       malha_normal.bounds[0], malha_normal.bounds[1]),
        ElementoClash("g_ruim", "IfcWall", "ruim", "ARQ", "Pav1", "a.ifc", malha_achatada,
                       malha_achatada.bounds[0], malha_achatada.bounds[1]),
    ]
    invalidos = checar_geometria_invalida(elementos)
    guids_invalidos = {e["guid"] for e in invalidos}
    assert "g_ruim" in guids_invalidos
    assert "g_ok" not in guids_invalidos
    print("OK geometria achatada (bounding box quase 2D) é detectada como inválida")


def test_vertices_nao_finitos_sao_detectados():
    malha = trimesh.creation.box(extents=(1, 1, 1))
    malha.vertices[0] = [np.nan, 0, 0]
    elemento = ElementoClash("g_nan", "IfcWall", "nan", "ARQ", "Pav1", "a.ifc", malha,
                              malha.bounds[0], malha.bounds[1])
    invalidos = checar_geometria_invalida([elemento])
    assert len(invalidos) == 1
    assert "não-finitos" in invalidos[0]["motivo"]
    print("OK vértices NaN/Inf são detectados como geometria inválida")


# ---------- níveis entre arquivos ----------
def test_niveis_sem_correspondencia_entre_arquivos():
    elementos = [
        _elemento_fake("g1", "a.ifc", nivel="Pavimento 1"),
        _elemento_fake("g2", "b.ifc", nivel="Pavimento Térreo"),
    ]
    niveis, sem_correspondencia = checar_niveis_entre_arquivos(elementos)
    assert sem_correspondencia
    assert niveis["a.ifc"] == ["Pavimento 1"]
    print("OK nomenclatura de pavimento totalmente diferente entre arquivos é sinalizada")


def test_niveis_com_correspondencia_nao_alerta():
    elementos = [
        _elemento_fake("g1", "a.ifc", nivel="Pavimento 1"),
        _elemento_fake("g2", "b.ifc", nivel="Pavimento 1"),
    ]
    _, sem_correspondencia = checar_niveis_entre_arquivos(elementos)
    assert not sem_correspondencia
    print("OK pelo menos um nome de pavimento em comum não alerta")


# ---------- orquestração completa ----------
def test_executar_pre_checagens_nao_quebra_com_tudo_junto():
    f, body, storey = criar_ifc_base()
    adicionar_elemento_prisma(f, body, storey, ifc_class="IfcWall")
    regras = carregar_regras()
    extraidos = extrair_elementos(f, "a.ifc", regras)

    resultado = executar_pre_checagens({"a.ifc": f}, extraidos)
    assert resultado.unidades_inconsistentes is False
    assert resultado.alerta_desalinhamento is False
    assert isinstance(resultado.tem_alertas_bloqueantes(), bool)
    print("OK orquestração completa roda de ponta a ponta sem quebrar")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE PRE-CHECAGENS PASSARAM")
