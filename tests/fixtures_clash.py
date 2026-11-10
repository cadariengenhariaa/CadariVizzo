"""Utilitários para gerar IFCs sintéticos usados pelos testes do pacote
`clash` — mesma técnica (ifcopenshell.api) já usada nos testes manuais
deste projeto durante o desenvolvimento do visualizador."""
import os

import ifcopenshell
import ifcopenshell.api

from clash.config_regras import carregar_regras

_CAMINHO_REGRAS_TESTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regras_teste.yaml")


def carregar_regras_teste():
    """Regras congeladas para os testes (cópia da Fase 1, com todos os
    pares da matriz em testar:true) — NUNCA o `clash/regras_clash.yaml`
    real, que é editado pela tela do app e pode ter qualquer coisa
    desligada a qualquer momento (ex.: o usuário clicando "Desmarcar
    todos"). Usar `carregar_regras()` direto nos testes os deixaria
    reféns de uma configuração de produção que muda por fora."""
    return carregar_regras(_CAMINHO_REGRAS_TESTE)


def criar_ifc_base(schema="IFC4", prefixo_unidade_comprimento="MILLI"):
    """Cria um IFC vazio com Project > Site > Building > Storey e um
    contexto 'Body' prontos para receber elementos.

    `prefixo_unidade_comprimento`: prefixo SI da unidade de comprimento
    do projeto (padrão "MILLI" = milímetro, a convenção mais comum em
    exportações de Revit/ArchiCAD). Passe `None` para metros (sem
    prefixo) — útil para testar modelos de coordenação com unidades
    diferentes entre arquivos."""
    f = ifcopenshell.file(schema=schema)
    project = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Teste")
    comprimento = ifcopenshell.api.run(
        "unit.add_si_unit", f, unit_type="LENGTHUNIT", prefix=prefixo_unidade_comprimento
    )
    area = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="AREAUNIT")
    volume = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="VOLUMEUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[comprimento, area, volume])
    contexto = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", f, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=contexto,
    )

    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="Building")
    storey = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Storey")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[building], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[storey], relating_object=building)

    return f, body, storey


def adicionar_elemento_prisma(f, body, storey, nome="Elemento", ifc_class="IfcWall",
                               length=5.0, height=3.0, thickness=0.2, deslocamento=(0.0, 0.0, 0.0)):
    """Cria um elemento de uma classe IFC qualquer com um prisma simples
    como geometria (via o helper de 'wall representation' do
    ifcopenshell.api) — suficiente para os testes de disciplina/geometria/
    pré-checagens, que não dependem da forma real do elemento, só da
    classe IFC e de ter alguma malha válida."""
    elemento = ifcopenshell.api.run("root.create_entity", f, ifc_class=ifc_class, name=nome)
    ifcopenshell.api.run("spatial.assign_container", f, products=[elemento], relating_structure=storey)
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation", f, context=body,
        length=length, height=height, thickness=thickness,
    )
    ifcopenshell.api.run("geometry.assign_representation", f, product=elemento, representation=rep)
    if deslocamento != (0.0, 0.0, 0.0):
        matriz = ifcopenshell.util.placement.get_local_placement(elemento.ObjectPlacement).copy() \
            if hasattr(ifcopenshell, "util") and hasattr(ifcopenshell.util, "placement") else None
        ifcopenshell.api.run(
            "geometry.edit_object_placement", f, product=elemento,
            matrix=_matriz_translacao(deslocamento),
        )
    return elemento


def _matriz_translacao(deslocamento):
    import numpy as np
    m = np.eye(4)
    m[0, 3], m[1, 3], m[2, 3] = deslocamento
    return m


def adicionar_pset_disciplina(f, elemento, disciplina, nome_prop="Disciplina", nome_pset="Pset_Teste"):
    pset = ifcopenshell.api.run("pset.add_pset", f, product=elemento, name=nome_pset)
    ifcopenshell.api.run("pset.edit_pset", f, pset=pset, properties={nome_prop: disciplina})
    return pset


def adicionar_sistema(f, elementos, predefined_type, nome="Sistema Teste", ifc_class="IfcDistributionSystem"):
    sistema = ifcopenshell.api.run("system.add_system", f, ifc_class=ifc_class)
    sistema.Name = nome
    sistema.PredefinedType = predefined_type  # falha alto e claro se o valor não existir no enum do schema
    ifcopenshell.api.run("system.assign_system", f, system=sistema, products=elementos)
    return sistema


def adicionar_abertura(f, body, storey, elemento_voidado, nome="Furo", length=1.0, height=0.5, thickness=0.5,
                        deslocamento=(0.0, 0.0, 0.0)):
    """Cria uma IfcOpeningElement com geometria própria e a associa a
    `elemento_voidado` via `feature.add_feature` (gera a IfcRelVoidsElement
    que `ifcopenshell.util.element.get_openings` enxerga)."""
    abertura = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcOpeningElement", name=nome)
    rep = ifcopenshell.api.run(
        "geometry.add_wall_representation", f, context=body, length=length, height=height, thickness=thickness
    )
    ifcopenshell.api.run("geometry.assign_representation", f, product=abertura, representation=rep)
    if deslocamento != (0.0, 0.0, 0.0):
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=abertura,
                              matrix=_matriz_translacao(deslocamento))
    ifcopenshell.api.run("feature.add_feature", f, feature=abertura, element=elemento_voidado)
    return abertura


def _somar(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


# ---------------------------------------------------------------------
# Os 4 cenários de teste pedidos: hard clash, folga insuficiente,
# duplicado e o falso positivo de furo previsto (que NÃO deve virar
# clash). Todas as dimensões abaixo já estão em metros (unidade do
# projeto = metro, sem prefixo) para os números ficarem legíveis.
#
# Cada função aceita um `offset` opcional (padrão: origem) — usado por
# quem quiser combinar vários cenários no mesmo arquivo/rodada sem que
# os bounding boxes de cenários diferentes se sobreponham entre si (o
# que geraria "clashes" espúrios entre elementos de cenários não
# relacionados).
# ---------------------------------------------------------------------
def cenario_hard_clash(offset=(0.0, 0.0, 0.0)):
    """Viga de estrutura (EST) e duto de climatização (CLIM) se cruzando
    fisicamente de verdade — deve virar um hard clash."""
    f, body, storey = criar_ifc_base(prefixo_unidade_comprimento=None)
    viga = adicionar_elemento_prisma(f, body, storey, nome="Viga-Hard", ifc_class="IfcBeam",
                                      length=2.0, height=0.5, thickness=0.3, deslocamento=offset)
    duto = adicionar_elemento_prisma(f, body, storey, nome="Duto-Hard", ifc_class="IfcDuctSegment",
                                      length=1.0, height=0.3, thickness=0.3,
                                      deslocamento=_somar(offset, (0.5, 0.0, 0.1)))
    return {"modelo_coordenacao.ifc": f}, viga, duto


def cenario_folga_insuficiente(offset=(0.0, 0.0, 0.0)):
    """Tubo hidrossanitário (HID) e duto de climatização (CLIM) com 2 cm
    de vão livre — a folga mínima do par HID|CLIM nas regras padrão é
    5 cm, então isso deve virar um soft clash (folga insuficiente)."""
    f, body, storey = criar_ifc_base(prefixo_unidade_comprimento=None)
    tubo = adicionar_elemento_prisma(f, body, storey, nome="Tubo-Folga", ifc_class="IfcPipeSegment",
                                      length=1.0, height=0.1, thickness=0.1, deslocamento=offset)
    duto = adicionar_elemento_prisma(f, body, storey, nome="Duto-Folga", ifc_class="IfcDuctSegment",
                                      length=1.0, height=0.1, thickness=0.1,
                                      deslocamento=_somar(offset, (1.02, 0.0, 0.0)))
    return {"modelo_coordenacao.ifc": f}, tubo, duto


def cenario_duplicado(offset=(0.0, 0.0, 0.0)):
    """Duas paredes de arquitetura (mesma disciplina) praticamente na
    mesma posição e com o mesmo volume — elemento duplicado, não uma
    interferência real entre disciplinas."""
    f, body, storey = criar_ifc_base(prefixo_unidade_comprimento=None)
    parede1 = adicionar_elemento_prisma(f, body, storey, nome="Parede-Dup-1", ifc_class="IfcWall",
                                         length=3.0, height=2.0, thickness=0.15, deslocamento=offset)
    parede2 = adicionar_elemento_prisma(f, body, storey, nome="Parede-Dup-2", ifc_class="IfcWall",
                                         length=3.0, height=2.0, thickness=0.15,
                                         deslocamento=_somar(offset, (0.005, 0.0, 0.0)))
    return {"modelo_coordenacao.ifc": f}, parede1, parede2


def cenario_furo_previsto(offset=(0.0, 0.0, 0.0)):
    """Mesma geometria física do cenário de hard clash (viga x duto se
    cruzando), mas agora a viga já tem uma IfcOpeningElement exatamente
    onde o duto passa — furo previsto no projeto estrutural. O motor de
    clash deve excluir este par, não reportar hard clash nenhum."""
    f, body, storey = criar_ifc_base(prefixo_unidade_comprimento=None)
    viga = adicionar_elemento_prisma(f, body, storey, nome="Viga-Furo", ifc_class="IfcBeam",
                                      length=2.0, height=0.5, thickness=0.3, deslocamento=offset)
    duto = adicionar_elemento_prisma(f, body, storey, nome="Duto-Furo", ifc_class="IfcDuctSegment",
                                      length=1.0, height=0.3, thickness=0.3,
                                      deslocamento=_somar(offset, (0.5, 0.0, 0.1)))
    # abertura um pouco maior que o duto, posicionada exatamente na
    # região de sobreposição (mesma margem de folga que um furo real
    # de projeto teria ao redor da tubulação/duto)
    adicionar_abertura(f, body, storey, viga, nome="Furo-Previsto",
                        length=1.2, height=0.4, thickness=0.3, deslocamento=_somar(offset, (0.4, 0.0, 0.05)))
    return {"modelo_coordenacao.ifc": f}, viga, duto
