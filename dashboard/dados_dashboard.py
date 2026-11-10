"""Agregações puras sobre `issues` para o Dashboard — nenhuma função
aqui toca em Tkinter/matplotlib nem em disco; tudo recebe listas de
dicts e devolve dicts/listas simples, pensado para ser fácil de testar
com issues sintéticas.

Visibilidade por papel: por padrão, cada usuário só enxerga as issues
ATRIBUÍDAS A ELE (`atribuido_para` == seu `nome` completo) — é o que
corresponde a "Ajustes por Projetista" no relatório Power BI original
(o trabalho que ele precisa resolver, não o que ele apontou). Quem
enxerga o de todo mundo (`eh_gestor_dashboard`): papel Coordenador/
Administrador, OU setor "Setor BIM"/"Coordenação de projetos" — esses
dois setores acompanham o progresso de todos os projetistas
independentemente do papel de cada um (diferença: Setor BIM também é
Administrador, para gerenciar contas; Coordenação de projetos só vê o
Dashboard, continua Projetista para todo o resto). Esses podem
opcionalmente filtrar por um projetista específico (mesmo critério:
`atribuido_para`)."""
from collections import OrderedDict
from datetime import datetime

from auth.usuarios import eh_coordenador_ou_administrador
from config import SETOR_BIM, SETOR_COORDENACAO

SEM_VALOR = "(Não informado)"

_SETORES_GESTORES_DASHBOARD = {SETOR_BIM, SETOR_COORDENACAO}


def eh_gestor_dashboard(usuario_atual):
    """Quem enxerga o Dashboard de todo mundo, não só o seu: Coordenador/
    Administrador (qualquer setor), ou qualquer papel se o setor for
    "Setor BIM" ou "Coordenação de projetos". Na prática o setor BIM já
    é cadastrado como administrador (ver auth/dialogs.py), mas o checa
    aqui também por segurança, caso o papel e o setor fiquem fora de
    sincronia."""
    if not usuario_atual:
        return False
    if eh_coordenador_ou_administrador(usuario_atual):
        return True
    return (usuario_atual.get("setor") or "") in _SETORES_GESTORES_DASHBOARD


_FORMATOS_DATA = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")


def _valor(issue, campo):
    v = (issue.get(campo) or "").strip()
    return v or SEM_VALOR


def _parse_data(texto):
    texto = (texto or "").strip()
    for fmt in _FORMATOS_DATA:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


# ---------- visibilidade por papel ----------
def filtrar_por_papel(issues, usuario_atual, projetista_filtro=None):
    """Quem não é gestor (ver `eh_gestor_dashboard`): só o que está
    atribuído a ele mesmo. Gestor: tudo, ou só o de `projetista_filtro`
    se informado (nome completo, mesmo critério)."""
    if usuario_atual and not eh_gestor_dashboard(usuario_atual):
        nome = usuario_atual.get("nome", "")
        return [i for i in issues if i.get("atribuido_para") == nome]
    if projetista_filtro:
        return [i for i in issues if i.get("atribuido_para") == projetista_filtro]
    return list(issues)


def listar_nomes_projetistas(issues):
    """Nomes distintos de `atribuido_para` presentes nas issues — para
    popular o filtro de projetista do Coordenador/Administrador."""
    nomes = {i.get("atribuido_para") for i in issues if (i.get("atribuido_para") or "").strip()}
    return sorted(nomes)


# ---------- filtros combináveis ----------
def _bate_filtro(valor, filtro):
    """`filtro` aceita um valor único (igualdade) OU uma coleção
    (lista/conjunto: pertencimento) — isso é o que permite o Dashboard
    filtrar por VÁRIOS meses ou VÁRIOS status ao mesmo tempo."""
    if isinstance(filtro, (set, frozenset, list, tuple)):
        return valor in filtro
    return valor == filtro


def aplicar_filtros(issues, obra=None, disciplina=None, tipo=None, status=None,
                     ano_mes=None):
    """`status`/`ano_mes` (e os demais) aceitam um valor único ou uma
    coleção de valores. `ano_mes`: string(s) "AAAA-MM" para restringir
    por `data_criacao`. Uma coleção VAZIA é um filtro válido (exclui
    tudo), por isso o teste é `is not None`, não truthiness."""
    resultado = issues
    if obra is not None:
        resultado = [i for i in resultado if _bate_filtro(i.get("obra"), obra)]
    if disciplina is not None:
        resultado = [i for i in resultado if _bate_filtro(i.get("disciplina"), disciplina)]
    if tipo is not None:
        resultado = [i for i in resultado if _bate_filtro(i.get("tipo"), tipo)]
    if status is not None:
        resultado = [i for i in resultado if _bate_filtro(i.get("status"), status)]
    if ano_mes is not None:
        def _bate_mes(i):
            data = _parse_data(i.get("data_criacao"))
            if data is None:
                return False
            return _bate_filtro(f"{data.year:04d}-{data.month:02d}", ano_mes)
        resultado = [i for i in resultado if _bate_mes(i)]
    return resultado


# ---------- contagens por categoria (para donuts/barras) ----------
def _contagem_por_campo(issues, campo):
    contagem = OrderedDict()
    for i in issues:
        chave = _valor(i, campo)
        contagem[chave] = contagem.get(chave, 0) + 1
    return dict(sorted(contagem.items(), key=lambda kv: kv[1], reverse=True))


def contagem_por_obra(issues):
    return _contagem_por_campo(issues, "obra")


def contagem_por_status(issues):
    return _contagem_por_campo(issues, "status")


def contagem_por_disciplina(issues):
    return _contagem_por_campo(issues, "disciplina")


def contagem_por_tipo(issues):
    return _contagem_por_campo(issues, "tipo")


def contagem_por_projetista(issues):
    """'Ajustes por Projetista' — por `atribuido_para`."""
    return _contagem_por_campo(issues, "atribuido_para")


def percentual_por_disciplina(issues):
    """Igual a `contagem_por_disciplina`, mas em % do total (soma ~100,
    sujeito a arredondamento)."""
    contagem = contagem_por_disciplina(issues)
    total = sum(contagem.values())
    if total == 0:
        return {}
    return {chave: round(qtd / total * 100, 1) for chave, qtd in contagem.items()}


# ---------- séries temporais ----------
def contagem_por_mes(issues, campo_data="data_criacao"):
    """Dict ordenado cronologicamente {"AAAA-MM": quantidade}. Meses
    sem nenhuma issue não aparecem (gráfico de linha só com os pontos
    que existem, sem inventar zeros no meio)."""
    contagem = {}
    for i in issues:
        data = _parse_data(i.get(campo_data))
        if data is None:
            continue
        chave = f"{data.year:04d}-{data.month:02d}"
        contagem[chave] = contagem.get(chave, 0) + 1
    return dict(sorted(contagem.items()))


def media_movel_por_mes(issues, campo_data="data_criacao"):
    """'Média Ponderada por Mês': como o relatório Power BI original não
    foi reproduzido com sua fórmula DAX exata, isto é implementado como
    a média móvel/acumulada de problemas por mês (quantidade média por
    mês considerando todos os meses até aquele ponto) — mostra a
    tendência de ritmo ao longo do tempo. Ajustável depois se não bater
    com o que o usuário espera."""
    por_mes = contagem_por_mes(issues, campo_data)
    resultado = OrderedDict()
    acumulado = 0
    for indice, (mes, qtd) in enumerate(por_mes.items(), start=1):
        acumulado += qtd
        resultado[mes] = round(acumulado / indice, 2)
    return resultado


# ---------- KPIs ----------
def calcular_kpis(issues):
    total = len(issues)
    por_status = contagem_por_status(issues)
    return {
        "total": total,
        "problema": por_status.get("Novo", 0),
        "respondido": por_status.get("Respondido", 0),
        "reaberto": por_status.get("Reaberto", 0),
        "fechado": por_status.get("Fechado", 0),
    }
