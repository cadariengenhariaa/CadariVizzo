"""Testes de dashboard/dados_painel.py (Início / Meus projetos / Painel
de controle) — issues sintéticas, sem Tkinter nem disco."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.dados_painel import (
    SITUACAO_ANALISE,
    SITUACAO_CERTIFICADO,
    SITUACAO_PAUSADO,
    SITUACAO_REVISAO,
    atividade_por_dia_semana,
    atividades_recentes,
    desempenho_equipe,
    filtrar_projetos,
    indice_conformidade,
    issues_pendentes_de,
    kpis_painel,
    projetos_por_situacao,
    resumo_projetos,
    resumo_semana,
    rotulo_dia_hora,
    tempo_relativo,
    ultima_movimentacao,
)

AGORA = datetime(2026, 10, 19, 12, 0, 0)


def _issue(**kwargs):
    base = {
        "id": 1, "obra": "CA-1000", "disciplina": "ADI", "tipo": "Dúvida", "status": "Novo",
        "criado_por": "Ana", "atribuido_para": "Bruno", "titulo": "T", "desc": "D",
        "data_criacao": "15/10/2026 10:00:00", "historico": [], "tipo_doc": "pdf",
    }
    base.update(kwargs)
    return base


def test_tempo_relativo_e_rotulo_dia():
    assert tempo_relativo(datetime(2026, 10, 19, 11, 42), AGORA) == "Há 18 minutos"
    assert tempo_relativo(datetime(2026, 10, 19, 9, 0), AGORA) == "Há 3 horas"
    assert tempo_relativo(datetime(2026, 10, 18, 9, 0), AGORA) == "Ontem"
    assert tempo_relativo(datetime(2026, 10, 10, 9, 0), AGORA) == "Há 9 dias"
    assert rotulo_dia_hora(datetime(2026, 10, 19, 9, 42), AGORA) == "Hoje, 09:42"
    assert rotulo_dia_hora(datetime(2026, 10, 18, 9, 42), AGORA) == "Ontem, 09:42"


def test_ultima_movimentacao_considera_comentarios():
    issue = _issue(data_modificacao="16/10/2026 10:00:00",
                   historico=[{"data": "18/10/2026 08:30", "texto": "ok"}])
    assert ultima_movimentacao(issue) == datetime(2026, 10, 18, 8, 30)


def test_issues_pendentes_so_do_usuario_e_nao_fechadas():
    issues = [
        _issue(id=1, atribuido_para="Bruno"),
        _issue(id=2, atribuido_para="Bruno", status="Fechado"),
        _issue(id=3, atribuido_para="Carla"),
        _issue(id=4, atribuido_para="Bruno", status="Respondido", data_criacao="18/10/2026 10:00:00"),
    ]
    assert [i["id"] for i in issues_pendentes_de(issues, "Bruno")] == [4, 1]


def test_resumo_projetos_situacao_progresso_e_ordem():
    issues = [
        _issue(id=1, obra="CA-1", status="Fechado"),
        _issue(id=2, obra="CA-1", status="Novo"),
        _issue(id=3, obra="CA-2", status="Respondido", data_criacao="18/10/2026 10:00:00"),
        _issue(id=4, obra="CA-3", status="Fechado"),
        _issue(id=5, obra="CA-4", status="Novo", data_criacao="01/08/2026 10:00:00"),
        _issue(id=6, obra="", status="Novo"),
    ]
    resumos = resumo_projetos(issues, AGORA)
    por_obra = {r["obra"]: r for r in resumos}
    assert set(por_obra) == {"CA-1", "CA-2", "CA-3", "CA-4"}  # sem obra fica de fora
    assert resumos[0]["obra"] == "CA-2"  # movimentação mais recente primeiro
    assert por_obra["CA-1"]["progresso"] == 0.5
    assert por_obra["CA-1"]["situacao"] == SITUACAO_ANALISE
    assert por_obra["CA-2"]["situacao"] == SITUACAO_REVISAO
    assert por_obra["CA-3"]["situacao"] == SITUACAO_CERTIFICADO
    assert por_obra["CA-4"]["pausado"] is True
    assert projetos_por_situacao(resumos) == {
        SITUACAO_ANALISE: 1, SITUACAO_REVISAO: 1, SITUACAO_CERTIFICADO: 1, SITUACAO_PAUSADO: 1}
    assert [r["obra"] for r in filtrar_projetos(resumos, "Certificados")] == ["CA-3"]
    assert len(filtrar_projetos(resumos, "Todos")) == 4


def test_resumo_projetos_filtra_por_tipo_doc():
    issues = [_issue(id=1, obra="CA-1", tipo_doc="pdf"), _issue(id=2, obra="CA-2", tipo_doc="ifc")]
    assert [r["obra"] for r in resumo_projetos(issues, AGORA, tipo_doc="ifc")] == ["CA-2"]


def test_resumo_semana():
    issues = [
        _issue(status="Fechado"), _issue(status="Respondido"), _issue(status="Novo"),
        _issue(status="Reaberto", data_criacao="01/01/2026 10:00:00", criado_por="Davi"),
    ]
    r = resumo_semana(issues, AGORA)
    assert (r["total"], r["concluidas"], r["revisoes"], r["pendencias"]) == (4, 1, 1, 2)
    assert r["fracao"] == 0.25
    assert r["colaboracoes"] == 3  # Ana, Bruno, Davi
    assert r["novas_semana"] == 3


def test_atividades_recentes_inclui_comentarios_em_ordem():
    issues = [
        _issue(id=1, data_criacao="17/10/2026 10:00:00",
               historico=[{"data": "19/10/2026 11:00", "texto": "Corrigido", "autor": "Bruno"}]),
        _issue(id=2, data_criacao="18/10/2026 10:00:00"),
    ]
    eventos = atividades_recentes(issues)
    assert [(e["tipo"], e["issue"]["id"]) for e in eventos] == [("comentou", 1), ("criou", 2), ("criou", 1)]
    assert eventos[0]["autor"] == "Bruno"


def test_kpis_painel():
    issues = [
        _issue(id=1, obra="CA-1", status="Novo", data_criacao="15/10/2026 10:00:00"),
        _issue(id=2, obra="CA-2", status="Fechado", data_criacao="10/10/2026 10:00:00",
               data_modificacao="14/10/2026 10:00:00"),
        _issue(id=3, obra="CA-3", status="Respondido", data_criacao="01/08/2026 10:00:00",
               data_modificacao="01/09/2026 10:00:00"),
    ]
    k = kpis_painel(issues, dias=30, agora=AGORA)
    assert k["projetos_ativos"] == 1  # CA-1 (CA-2 está fechado, CA-3 sem movimento no período)
    assert k["revisoes_abertas"] == 2
    assert k["revisoes_saldo_semana"] == 1 - 1  # 1 criada e 1 fechada na última semana
    assert k["taxa_conclusao"] == 50.0
    assert abs(k["tempo_medio_dias"] - 4.0) < 1e-9


def test_atividade_por_dia_semana():
    issues = [_issue(data_criacao="19/10/2026 10:00:00",  # segunda-feira
                     historico=[{"data": "18/10/2026 09:00", "texto": "x"}])]  # domingo
    revisoes, comentarios = atividade_por_dia_semana(issues, 30, AGORA)
    assert revisoes[0] == 1 and sum(revisoes) == 1
    assert comentarios[6] == 1 and sum(comentarios) == 1


def test_desempenho_equipe_e_conformidade():
    issues = [
        _issue(atribuido_para="Bruno", status="Fechado"),
        _issue(atribuido_para="Bruno", status="Novo"),
        _issue(atribuido_para="Carla", status="Novo", obra="CA-9", data_criacao="01/09/2026 10:00:00"),
    ]
    equipe = desempenho_equipe(issues, [{"nome": "Bruno", "setor": "Projetista HVAC"}])
    assert equipe[0] == {"nome": "Bruno", "revisoes": 2, "fechadas": 1, "pendencias": 1,
                         "desempenho": 0.5, "setor": "Projetista HVAC"}
    fracao, conformes, total = indice_conformidade(issues, AGORA, prazo_dias=15)
    assert (conformes, total) == (1, 2)  # CA-9 tem pendência de 48 dias
    assert fracao == 0.5


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE DADOS DO PAINEL PASSARAM")
