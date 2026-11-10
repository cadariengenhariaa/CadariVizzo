"""Monta a estrutura de dados comum usada por todos os formatos de
relatório (XLSX, JSON, BCF, PDF) — resumo executivo, matriz heatmap,
totais, comparativo com a revisão anterior, distribuição por pavimento,
top elementos e pendências por disciplina responsável."""
from collections import Counter, defaultdict

# Status que o usuário já decidiu conscientemente (com justificativa) —
# ainda aparecem no relatório completo, mas somem da lista de
# "pendências" (que é só o que ainda precisa de ação de alguém).
STATUS_JA_DECIDIDOS = {"Aprovado", "Aceito"}


def clashes_ativos(clashes):
    """Interferências ainda fisicamente presentes na última rodada —
    inclui as que o usuário já marcou Aprovado/Aceito (uma decisão
    consciente ainda é uma interferência real, só não é mais uma
    pendência — ver `pendencias`)."""
    return [c for c in clashes if c.get("rastreamento") != "Resolvido"]


def pendencias(clashes):
    """Ativos que ainda precisam de ação de alguém."""
    return [c for c in clashes_ativos(clashes) if c.get("status") not in STATUS_JA_DECIDIDOS]


def aplicar_filtros(clashes, disciplina=None, pavimento=None, severidade=None, status=None, responsavel=None):
    """Filtros de exportação pedidos: disciplina, pavimento, severidade,
    status e responsável (sugerido OU atribuído)."""
    resultado = clashes
    if disciplina:
        resultado = [c for c in resultado if disciplina in (c["disciplina_a"], c["disciplina_b"])]
    if pavimento:
        resultado = [c for c in resultado if c.get("nivel") == pavimento]
    if severidade:
        resultado = [c for c in resultado if c["severidade"] == severidade]
    if status:
        resultado = [c for c in resultado if c["status"] == status]
    if responsavel:
        resultado = [
            c for c in resultado
            if responsavel in (c.get("responsavel_atribuido"), c.get("responsavel_sugerido"))
        ]
    return resultado


def totais_por_severidade(clashes):
    return dict(Counter(c["severidade"] for c in clashes))


def totais_por_status(clashes):
    return dict(Counter(c["status"] for c in clashes))


def totais_por_tipo(clashes):
    return dict(Counter(c["tipo"] for c in clashes))


def matriz_disciplina_x_disciplina(clashes):
    """Conta interferências ATIVAS por par de disciplinas — alimenta o
    heatmap do resumo executivo."""
    contagem = Counter()
    for c in clashes_ativos(clashes):
        par = tuple(sorted([c["disciplina_a"], c["disciplina_b"]]))
        contagem[par] += 1
    return dict(contagem)


def distribuicao_por_pavimento(clashes):
    return dict(Counter(c.get("nivel") or "SEM_NIVEL" for c in clashes_ativos(clashes)))


def comparativo_com_revisao_anterior(clashes):
    """Quantos itens desta rodada (já mesclada com o histórico) caem em
    cada categoria — Novo/Ativo/Resolvido/Reaberto."""
    return dict(Counter(c.get("rastreamento", "Novo") for c in clashes))


def top_elementos(clashes, limite=10):
    """Elementos (por GUID) que aparecem em mais interferências ativas —
    costuma apontar o 'problema sistêmico' por trás de uma pilha de
    itens (ex.: uma viga rebaixada cruzando várias tubulações)."""
    contagem = Counter()
    nomes = {}
    for c in clashes_ativos(clashes):
        for chave in ("elemento_a", "elemento_b"):
            elemento = c[chave]
            contagem[elemento["guid"]] += 1
            nomes[elemento["guid"]] = f"{elemento['ifc_class']} — {elemento['nome'] or '(sem nome)'}"
    return [
        {"guid": guid, "nome": nomes[guid], "quantidade": quantidade}
        for guid, quantidade in contagem.most_common(limite)
    ]


def pendencias_por_disciplina(clashes):
    """Agrupa as pendências pelo responsável SUGERIDO — cada projetista
    acha rápido o que é dele; é uma sugestão, não uma atribuição
    definitiva (ver campo `responsavel_atribuido`, editável pelo
    usuário)."""
    por_disciplina = defaultdict(list)
    for c in pendencias(clashes):
        por_disciplina[c["responsavel_sugerido"]].append(c)
    return dict(por_disciplina)


def pre_checagens_para_dict(resultado):
    if resultado is None:
        return {}
    return {
        "unidades_inconsistentes": resultado.unidades_inconsistentes,
        "escala_por_arquivo": resultado.escala_por_arquivo,
        "alerta_desalinhamento": resultado.alerta_desalinhamento,
        "distancia_entre_centros_m": resultado.distancia_entre_centros_m,
        "guids_duplicados": resultado.guids_duplicados,
        "elementos_sem_geometria": resultado.elementos_sem_geometria,
        "elementos_sem_nivel": resultado.elementos_sem_nivel,
        "geometria_invalida": resultado.geometria_invalida,
        "niveis_por_arquivo": resultado.niveis_por_arquivo,
        "niveis_sem_correspondencia": resultado.niveis_sem_correspondencia,
        "tem_alertas_bloqueantes": resultado.tem_alertas_bloqueantes(),
    }


def montar_resumo_executivo(clashes, resultado_pre_checagens=None, metadados_projeto=None):
    """`metadados_projeto`: dict livre (nome do projeto, arquivos/revisões
    analisados, data, regras usadas) — quem chama (UI/CLI) decide o que
    preencher; nada aqui é obrigatório."""
    ativos = clashes_ativos(clashes)

    return {
        "metadados_projeto": metadados_projeto or {},
        "pre_checagens": pre_checagens_para_dict(resultado_pre_checagens),
        "totais": {
            "total_ativo": len(ativos),
            "total_pendente": len(pendencias(clashes)),
            "por_severidade": totais_por_severidade(ativos),
            "por_status": totais_por_status(clashes),
            "por_tipo": totais_por_tipo(ativos),
        },
        "matriz_disciplinas": {
            f"{a} x {b}": quantidade for (a, b), quantidade in matriz_disciplina_x_disciplina(clashes).items()
        },
        "distribuicao_por_pavimento": distribuicao_por_pavimento(clashes),
        "comparativo_revisao_anterior": comparativo_com_revisao_anterior(clashes),
        "top_elementos": top_elementos(clashes),
        "pendencias_por_disciplina": {
            disciplina: len(itens) for disciplina, itens in pendencias_por_disciplina(clashes).items()
        },
    }
