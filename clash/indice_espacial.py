"""Fase ampla (broad-phase) da detecção de interferências: usa um índice
espacial R-tree sobre os bounding boxes dos elementos para não testar
todos os pares contra todos (O(n²)) — só os pares cujos bounding boxes
(expandidos pela maior folga possível das regras) se sobrepõem viram
candidatos para a fase fina."""
import rtree.index

from clash import selecao as selecao_mod


def _bbox_expandido(elemento, margem):
    return (
        elemento.bbox_min[0] - margem, elemento.bbox_min[1] - margem, elemento.bbox_min[2] - margem,
        elemento.bbox_max[0] + margem, elemento.bbox_max[1] + margem, elemento.bbox_max[2] + margem,
    )


def construir_indice(elementos):
    propriedades = rtree.index.Property()
    propriedades.dimension = 3
    indice = rtree.index.Index(properties=propriedades)
    for i, elemento in enumerate(elementos):
        indice.insert(i, tuple(elemento.bbox_min) + tuple(elemento.bbox_max))
    return indice


def folga_maxima_global(regras):
    """Limite superior usado só para expandir a consulta espacial — a
    folga EXATA de cada par de disciplinas continua sendo aplicada,
    correta, na fase fina (`clash.deteccao`). Usar aqui um valor
    (seguramente) maior do que qualquer folga configurada só gera alguns
    candidatos extras e inofensivos, nunca perde um par real."""
    valores = [config.get("folga_m", regras.folga_padrao_m) for config in regras.matriz_disciplinas.values()]
    valores.append(regras.folga_padrao_m)
    return max(valores) if valores else regras.folga_padrao_m


def pares_candidatos(elementos, regras, selecao_a=None, selecao_b=None):
    """Retorna uma lista ordenada de (i, j) com i<j — índices em
    `elementos` — para pares cujos bounding boxes se sobrepõem (já
    considerando a folga) E que devem ser testados.

    Com `selecao_a`/`selecao_b` (ambos `clash.selecao.SelecaoLado`): só
    pares onde um elemento está em A e o outro em B viram candidatos —
    é o modo usado pela tela de clash (seleção estilo Navisworks,
    substituindo a matriz de disciplinas). Sem os dois, cai no modo
    antigo: testa qualquer par cujas disciplinas a matriz não tenha
    marcado explicitamente `testar: false` — usado pelo CLI e por
    scripts que não têm (nem precisam de) uma seleção A/B."""
    if len(elementos) < 2:
        return []

    usa_selecao_ab = selecao_a is not None and selecao_b is not None

    indice = construir_indice(elementos)
    margem = folga_maxima_global(regras)

    vistos = set()
    for i, elemento in enumerate(elementos):
        bbox = _bbox_expandido(elemento, margem)
        for j in indice.intersection(bbox):
            if j == i:
                continue
            par = (i, j) if i < j else (j, i)
            if par in vistos:
                continue
            primeiro = elementos[par[0]]
            outro = elementos[par[1]]
            if usa_selecao_ab:
                if not selecao_mod.par_deve_ser_testado(primeiro, outro, selecao_a, selecao_b):
                    continue
            elif not regras.par_deve_ser_testado(primeiro.disciplina, outro.disciplina):
                continue
            vistos.add(par)
    return sorted(vistos)
