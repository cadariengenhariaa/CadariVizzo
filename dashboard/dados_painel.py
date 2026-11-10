"""Agregações puras para as telas no estilo do protótipo Figma (Início,
Meus projetos e Painel de controle). Como `dados_dashboard.py`: nada de
Tkinter nem disco — recebe listas de issues (dicts) e devolve dados
simples, fácil de testar com issues sintéticas.

O protótipo usa conceitos que não existem 1:1 no banco de issues; o
mapeamento adotado (documentado aqui para poder ser ajustado depois):

- "Projeto" = obra (Nº Cadari). Progresso = issues fechadas / total.
- Situação do projeto: todas fechadas → "Certificado"; alguma
  "Respondido" (aguardando conferência) → "Em revisão"; senão →
  "Em análise". Sem movimentação há mais de 30 dias (e não certificado)
  → "Pausado" (só no Painel de controle).
- Revisões = issues; Comentários = entradas do histórico.
- Tempo médio = dias entre a criação e a última modificação das issues
  fechadas (a data exata de fechamento não é registrada).
- Conformidade = % dos projetos sem nenhuma pendência aberta há mais de
  `prazo_dias` dias.
"""
from datetime import datetime, timedelta

from dashboard.dados_dashboard import _parse_data

STATUS_ABERTOS = ("Novo", "Reaberto", "Respondido")
SITUACAO_ANALISE = "Em análise"
SITUACAO_REVISAO = "Em revisão"
SITUACAO_CERTIFICADO = "Certificado"
SITUACAO_PAUSADO = "Pausado"
DIAS_PAUSADO = 30
DIAS_SEMANA = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


# ---------- datas ----------
def ultima_movimentacao(issue):
    datas = [_parse_data(issue.get("data_criacao")), _parse_data(issue.get("data_modificacao"))]
    datas += [_parse_data(c.get("data")) for c in issue.get("historico") or []]
    datas = [d for d in datas if d is not None]
    return max(datas) if datas else None


def tempo_relativo(data, agora=None):
    if data is None:
        return "—"
    agora = agora or datetime.now()
    segundos = (agora - data).total_seconds()
    if segundos < 60:
        return "Agora mesmo"
    if segundos < 3600:
        minutos = int(segundos // 60)
        return f"Há {minutos} minuto{'s' if minutos > 1 else ''}"
    if segundos < 86400 and data.date() == agora.date():
        horas = int(segundos // 3600)
        return f"Há {horas} hora{'s' if horas > 1 else ''}"
    dias = (agora.date() - data.date()).days
    if dias == 1:
        return "Ontem"
    if dias < 30:
        return f"Há {dias} dias"
    return data.strftime("%d/%m/%Y")


def rotulo_dia_hora(data, agora=None):
    """"Hoje, 09:42" / "Ontem, 17:10" / "12/10, 08:00"."""
    if data is None:
        return "—"
    agora = agora or datetime.now()
    dias = (agora.date() - data.date()).days
    if dias == 0:
        return f"Hoje, {data:%H:%M}"
    if dias == 1:
        return f"Ontem, {data:%H:%M}"
    return f"{data:%d/%m}, {data:%H:%M}"


# ---------- Início ----------
def issues_pendentes_de(issues, nome):
    """Issues atribuídas a `nome` que ainda não foram fechadas, da mais
    recente para a mais antiga."""
    pendentes = [i for i in issues if i.get("atribuido_para") == nome and i.get("status") != "Fechado"]
    return sorted(pendentes, key=lambda i: ultima_movimentacao(i) or datetime.min, reverse=True)


def ultimo_comentario(issue):
    historico = issue.get("historico") or []
    if historico:
        return historico[-1].get("texto", "")
    return issue.get("desc") or issue.get("titulo") or ""


def situacao_projeto(issues_da_obra):
    status = [i.get("status") for i in issues_da_obra]
    if status and all(s == "Fechado" for s in status):
        return SITUACAO_CERTIFICADO
    if any(s == "Respondido" for s in status):
        return SITUACAO_REVISAO
    return SITUACAO_ANALISE


def resumo_projetos(issues, agora=None, tipo_doc=None):
    """Um dict por obra, ordenado da movimentação mais recente para a
    mais antiga. `tipo_doc` ("pdf"/"ifc") restringe às issues daquele
    tipo de documento."""
    agora = agora or datetime.now()
    por_obra = {}
    for issue in issues:
        if tipo_doc and (issue.get("tipo_doc") or "pdf") != tipo_doc:
            continue
        obra = (issue.get("obra") or "").strip()
        if not obra:
            continue
        por_obra.setdefault(obra, []).append(issue)

    resumos = []
    for obra, lista in por_obra.items():
        fechados = sum(1 for i in lista if i.get("status") == "Fechado")
        movimentacoes = [m for m in (ultima_movimentacao(i) for i in lista) if m]
        ultima = max(movimentacoes) if movimentacoes else None
        situacao = situacao_projeto(lista)
        pausado = (situacao != SITUACAO_CERTIFICADO and ultima is not None
                   and (agora - ultima).days > DIAS_PAUSADO)
        pessoas = []
        for i in sorted(lista, key=lambda x: ultima_movimentacao(x) or datetime.min, reverse=True):
            for nome in (i.get("atribuido_para"), i.get("criado_por")):
                if nome and nome not in pessoas:
                    pessoas.append(nome)
        com_arquivo = sorted((i for i in lista if i.get("filepath")),
                             key=lambda x: ultima_movimentacao(x) or datetime.min, reverse=True)
        resumos.append({
            "obra": obra,
            "total": len(lista),
            "fechados": fechados,
            "abertos": len(lista) - fechados,
            "contagem": {s: sum(1 for i in lista if i.get("status") == s)
                         for s in ("Novo", "Respondido", "Reaberto", "Fechado")},
            "progresso": fechados / len(lista) if lista else 0.0,
            "situacao": situacao,
            "pausado": pausado,
            "disciplinas": sorted({i.get("disciplina") for i in lista if i.get("disciplina")}),
            "pessoas": pessoas,
            "comentarios": sum(len(i.get("historico") or []) for i in lista),
            "ultima_movimentacao": ultima,
            "ultimo_arquivo": com_arquivo[0]["filepath"] if com_arquivo else None,
            "tipos_doc": sorted({(i.get("tipo_doc") or "pdf") for i in lista}),
        })
    resumos.sort(key=lambda r: r["ultima_movimentacao"] or datetime.min, reverse=True)
    return resumos


FILTROS_PROJETOS = {
    "Todos": None,
    "Em andamento": SITUACAO_ANALISE,
    "Em revisão": SITUACAO_REVISAO,
    "Certificados": SITUACAO_CERTIFICADO,
}


def filtrar_projetos(resumos, filtro):
    alvo = FILTROS_PROJETOS.get(filtro)
    if alvo is None:
        return list(resumos)
    return [r for r in resumos if r["situacao"] == alvo]


def resumo_semana(issues, agora=None):
    agora = agora or datetime.now()
    total = len(issues)
    concluidas = sum(1 for i in issues if i.get("status") == "Fechado")
    pessoas = {n for i in issues for n in (i.get("atribuido_para"), i.get("criado_por")) if n}
    limite = agora - timedelta(days=7)
    novas = sum(1 for i in issues if (_parse_data(i.get("data_criacao")) or datetime.min) >= limite)
    return {
        "total": total,
        "concluidas": concluidas,
        "fracao": concluidas / total if total else 0.0,
        "revisoes": sum(1 for i in issues if i.get("status") == "Respondido"),
        "pendencias": sum(1 for i in issues if i.get("status") in ("Novo", "Reaberto")),
        "colaboracoes": len(pessoas),
        "novas_semana": novas,
    }


def atividades_recentes(issues, limite=5):
    """Eventos (criação de issue e comentários), do mais recente ao mais
    antigo: dicts com `tipo` ("criou"/"comentou"), `autor`, `issue`,
    `quando` e `texto`."""
    eventos = []
    for issue in issues:
        criada = _parse_data(issue.get("data_criacao"))
        if criada:
            eventos.append({"tipo": "criou", "autor": issue.get("criado_por") or "Alguém",
                            "issue": issue, "quando": criada, "texto": issue.get("titulo") or ""})
        for comentario in issue.get("historico") or []:
            quando = _parse_data(comentario.get("data"))
            if quando:
                eventos.append({"tipo": "comentou", "autor": comentario.get("autor") or "",
                                "issue": issue, "quando": quando, "texto": comentario.get("texto", "")})
    eventos.sort(key=lambda e: e["quando"], reverse=True)
    return eventos[:limite]


# ---------- Painel de controle ----------
def _no_intervalo(data, inicio, fim):
    return data is not None and inicio <= data <= fim


def _variacao_percentual(atual, anterior):
    if not anterior:
        return None
    return (atual - anterior) / anterior * 100


def kpis_painel(issues, dias=30, agora=None):
    agora = agora or datetime.now()
    inicio = agora - timedelta(days=dias)
    inicio_anterior = inicio - timedelta(days=dias)

    def projetos_ativos(ini, fim):
        return {(i.get("obra") or "").strip() for i in issues
                if (i.get("obra") or "").strip() and i.get("status") != "Fechado"
                and _no_intervalo(ultima_movimentacao(i), ini, fim)}

    ativos = projetos_ativos(inicio, agora)
    ativos_anterior = projetos_ativos(inicio_anterior, inicio)

    abertas = sum(1 for i in issues if i.get("status") in STATUS_ABERTOS)
    semana = agora - timedelta(days=7)
    criadas_semana = sum(1 for i in issues if _no_intervalo(_parse_data(i.get("data_criacao")), semana, agora))
    fechadas_semana = sum(1 for i in issues if i.get("status") == "Fechado"
                          and _no_intervalo(_parse_data(i.get("data_modificacao")), semana, agora))

    def taxa(ini, fim):
        criadas = [i for i in issues if _no_intervalo(_parse_data(i.get("data_criacao")), ini, fim)]
        if not criadas:
            return None
        return sum(1 for i in criadas if i.get("status") == "Fechado") / len(criadas) * 100

    def tempo_medio(ini, fim):
        duracoes = []
        for i in issues:
            if i.get("status") != "Fechado":
                continue
            criada, modificada = _parse_data(i.get("data_criacao")), _parse_data(i.get("data_modificacao"))
            if criada and modificada and _no_intervalo(modificada, ini, fim):
                duracoes.append(max(0.0, (modificada - criada).total_seconds() / 86400))
        return sum(duracoes) / len(duracoes) if duracoes else None

    taxa_atual, taxa_anterior = taxa(inicio, agora), taxa(inicio_anterior, inicio)
    tempo_atual, tempo_anterior = tempo_medio(inicio, agora), tempo_medio(inicio_anterior, inicio)
    return {
        "projetos_ativos": len(ativos),
        "projetos_ativos_variacao": _variacao_percentual(len(ativos), len(ativos_anterior)),
        "revisoes_abertas": abertas,
        "revisoes_saldo_semana": criadas_semana - fechadas_semana,
        "taxa_conclusao": taxa_atual,
        "taxa_conclusao_variacao": (taxa_atual - taxa_anterior)
        if taxa_atual is not None and taxa_anterior is not None else None,
        "tempo_medio_dias": tempo_atual,
        "tempo_medio_variacao": (tempo_atual - tempo_anterior)
        if tempo_atual is not None and tempo_anterior is not None else None,
    }


def atividade_por_dia_semana(issues, dias=30, agora=None):
    """(revisões, comentários) por dia da semana (Seg..Dom) no período."""
    agora = agora or datetime.now()
    inicio = agora - timedelta(days=dias)
    revisoes = [0] * 7
    comentarios = [0] * 7
    for issue in issues:
        criada = _parse_data(issue.get("data_criacao"))
        if _no_intervalo(criada, inicio, agora):
            revisoes[criada.weekday()] += 1
        for c in issue.get("historico") or []:
            quando = _parse_data(c.get("data"))
            if _no_intervalo(quando, inicio, agora):
                comentarios[quando.weekday()] += 1
    return revisoes, comentarios


def projetos_por_situacao(resumos):
    contagem = {SITUACAO_ANALISE: 0, SITUACAO_REVISAO: 0, SITUACAO_CERTIFICADO: 0, SITUACAO_PAUSADO: 0}
    for r in resumos:
        chave = SITUACAO_PAUSADO if r["pausado"] else r["situacao"]
        contagem[chave] += 1
    return contagem


def desempenho_equipe(issues, usuarios=None):
    """Um dict por responsável (`atribuido_para`): revisões (total
    atribuído), pendências (abertas) e desempenho (fração fechada)."""
    setores = {u.get("nome"): (u.get("setor") or "") for u in usuarios or []}
    por_pessoa = {}
    for i in issues:
        nome = (i.get("atribuido_para") or "").strip()
        if not nome:
            continue
        dados = por_pessoa.setdefault(nome, {"nome": nome, "revisoes": 0, "fechadas": 0})
        dados["revisoes"] += 1
        if i.get("status") == "Fechado":
            dados["fechadas"] += 1
    resultado = []
    for dados in por_pessoa.values():
        dados["pendencias"] = dados["revisoes"] - dados["fechadas"]
        dados["desempenho"] = dados["fechadas"] / dados["revisoes"] if dados["revisoes"] else 0.0
        dados["setor"] = setores.get(dados["nome"], "")
        resultado.append(dados)
    resultado.sort(key=lambda d: (-d["revisoes"], d["nome"]))
    return resultado


def indice_conformidade(issues, agora=None, prazo_dias=15):
    """(fração, conformes, total): projetos sem pendência aberta há mais
    de `prazo_dias` dias, sobre o total de projetos com issues."""
    agora = agora or datetime.now()
    por_obra = {}
    for i in issues:
        obra = (i.get("obra") or "").strip()
        if not obra:
            continue
        atrasada = False
        if i.get("status") in STATUS_ABERTOS:
            criada = _parse_data(i.get("data_criacao"))
            atrasada = criada is not None and (agora - criada).days > prazo_dias
        por_obra[obra] = por_obra.get(obra, False) or atrasada
    total = len(por_obra)
    conformes = sum(1 for atrasada in por_obra.values() if not atrasada)
    return (conformes / total if total else 0.0), conformes, total


def pendencias_atrasadas(issues, agora=None, prazo_dias=15):
    agora = agora or datetime.now()
    resultado = []
    for i in issues:
        if i.get("status") not in STATUS_ABERTOS:
            continue
        criada = _parse_data(i.get("data_criacao"))
        if criada and (agora - criada).days > prazo_dias:
            resultado.append((i, (agora - criada).days))
    resultado.sort(key=lambda par: -par[1])
    return resultado
