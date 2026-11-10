"""ID estável por interferência (para acompanhar entre revisões) e chave
de agrupamento (para o relatório não listar centenas de itens soltos
sem contexto)."""
import hashlib


def id_estavel(guid_a, guid_b, tipo):
    """Hash determinístico dos dois GUIDs (em ordem alfabética, para não
    depender de qual veio primeiro) + tipo de interferência — o MESMO
    par de elementos gera sempre o mesmo id entre revisões, permitindo
    rastrear Novo/Ativo/Resolvido/Reaberto."""
    chave = "|".join(sorted([guid_a, guid_b]) + [tipo])
    return hashlib.sha1(chave.encode("utf-8")).hexdigest()[:12]


def chave_agrupamento(elemento_a, elemento_b):
    """Agrupa interferências do mesmo par de disciplinas no mesmo
    pavimento — usado pelo relatório para agrupar itens relacionados em
    vez de listar centenas de ocorrências soltas."""
    nivel = elemento_a.nivel or elemento_b.nivel or "SEM_NIVEL"
    disciplinas = tuple(sorted([elemento_a.disciplina, elemento_b.disciplina]))
    return (nivel, disciplinas)
