"""Testes de dashboard/dados_dashboard.py: agregações puras com issues
sintéticas — sem Tkinter, sem disco, sem tocar no banco de produção."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.dados_dashboard import (
    SEM_VALOR,
    aplicar_filtros,
    calcular_kpis,
    contagem_por_disciplina,
    contagem_por_mes,
    contagem_por_obra,
    contagem_por_projetista,
    contagem_por_status,
    contagem_por_tipo,
    eh_gestor_dashboard,
    filtrar_por_papel,
    listar_nomes_projetistas,
    media_movel_por_mes,
    percentual_por_disciplina,
)


def _issue(**kwargs):
    base = {
        "obra": "CA-1000", "disciplina": "ADI", "tipo": "Incompatibilidade",
        "status": "Novo", "criado_por": "Fulano", "atribuido_para": "Fulano",
        "data_criacao": "01/01/2026 10:00:00",
    }
    base.update(kwargs)
    return base


def test_filtrar_por_papel_projetista_so_ve_o_que_esta_atribuido_a_ele():
    issues = [
        _issue(atribuido_para="João Gabriel"),
        _issue(atribuido_para="Lucas Gomes"),
        _issue(atribuido_para="João Gabriel", criado_por="Outro"),
    ]
    usuario = {"papel": "projetista", "nome": "João Gabriel"}
    resultado = filtrar_por_papel(issues, usuario)
    assert len(resultado) == 2
    assert all(i["atribuido_para"] == "João Gabriel" for i in resultado)
    print("OK projetista só vê issues atribuídas a ele mesmo (atribuido_para)")


def test_filtrar_por_papel_administrador_ve_tudo_ou_filtra_por_projetista_escolhido():
    issues = [
        _issue(atribuido_para="João Gabriel"),
        _issue(atribuido_para="Lucas Gomes"),
    ]
    admin = {"papel": "administrador", "nome": "Admin"}
    assert len(filtrar_por_papel(issues, admin)) == 2
    assert len(filtrar_por_papel(issues, admin, projetista_filtro="Lucas Gomes")) == 1


def test_filtrar_por_papel_setor_bim_ve_tudo_mesmo_sendo_projetista():
    issues = [
        _issue(atribuido_para="João Gabriel"),
        _issue(atribuido_para="Lucas Gomes"),
    ]
    bim = {"papel": "projetista", "nome": "Fulano do BIM", "setor": "Setor BIM"}
    assert len(filtrar_por_papel(issues, bim)) == 2
    assert len(filtrar_por_papel(issues, bim, projetista_filtro="Lucas Gomes")) == 1
    print("OK papel projetista com setor 'Setor BIM' enxerga o Dashboard de todo mundo")


def test_eh_gestor_dashboard():
    assert eh_gestor_dashboard({"papel": "administrador"}) is True
    assert eh_gestor_dashboard({"papel": "coordenador"}) is True
    assert eh_gestor_dashboard({"papel": "projetista", "setor": "Setor BIM"}) is True
    assert eh_gestor_dashboard({"papel": "projetista", "setor": "Coordenação de projetos"}) is True
    assert eh_gestor_dashboard({"papel": "projetista", "setor": "Projetista PCI"}) is False
    assert eh_gestor_dashboard({"papel": "projetista"}) is False
    assert eh_gestor_dashboard(None) is False
    print("OK eh_gestor_dashboard: coordenador/administrador, ou qualquer papel com setor "
          "'Setor BIM'/'Coordenação de projetos'")
    print("OK administrador/coordenador vê tudo, ou só o de um projetista escolhido")


def test_filtrar_por_papel_setor_coordenacao_ve_tudo_mesmo_sendo_projetista():
    issues = [
        _issue(atribuido_para="João Gabriel"),
        _issue(atribuido_para="Lucas Gomes"),
    ]
    coordenacao = {"papel": "projetista", "nome": "Ana", "setor": "Coordenação de projetos"}
    assert len(filtrar_por_papel(issues, coordenacao)) == 2
    assert len(filtrar_por_papel(issues, coordenacao, projetista_filtro="Lucas Gomes")) == 1
    print("OK papel projetista com setor 'Coordenação de projetos' enxerga o Dashboard de todo mundo")


def test_listar_nomes_projetistas_ignora_vazios_e_duplica():
    issues = [
        _issue(atribuido_para="João Gabriel"),
        _issue(atribuido_para="João Gabriel"),
        _issue(atribuido_para="Lucas Gomes"),
        _issue(atribuido_para=""),
    ]
    assert listar_nomes_projetistas(issues) == ["João Gabriel", "Lucas Gomes"]
    print("OK lista de projetistas é distinta, ordenada e sem vazios")


def test_aplicar_filtros_combina_obra_disciplina_tipo_status_e_mes():
    issues = [
        _issue(obra="CA-1000", disciplina="ADI", tipo="Dúvida", status="Novo",
               data_criacao="05/01/2026 09:00:00"),
        _issue(obra="CA-1000", disciplina="HID", tipo="Dúvida", status="Novo",
               data_criacao="05/01/2026 09:00:00"),
        _issue(obra="CA-2000", disciplina="ADI", tipo="Dúvida", status="Fechado",
               data_criacao="05/02/2026 09:00:00"),
    ]
    assert len(aplicar_filtros(issues, obra="CA-1000")) == 2
    assert len(aplicar_filtros(issues, disciplina="ADI")) == 2
    assert len(aplicar_filtros(issues, status="Fechado")) == 1
    assert len(aplicar_filtros(issues, ano_mes="2026-01")) == 2
    assert len(aplicar_filtros(issues, obra="CA-1000", disciplina="HID")) == 1
    print("OK aplicar_filtros combina obra/disciplina/tipo/status/mês")


def test_aplicar_filtros_aceita_conjunto_de_valores_para_status_e_mes():
    issues = [
        _issue(status="Novo", data_criacao="05/01/2026 09:00:00"),
        _issue(status="Reaberto", data_criacao="05/02/2026 09:00:00"),
        _issue(status="Fechado", data_criacao="05/03/2026 09:00:00"),
    ]
    # "Novo" + "Reaberto" ao mesmo tempo (pedido explícito do usuário)
    resultado = aplicar_filtros(issues, status={"Novo", "Reaberto"})
    assert {i["status"] for i in resultado} == {"Novo", "Reaberto"}

    resultado_mes = aplicar_filtros(issues, ano_mes={"2026-01", "2026-03"})
    assert {i["status"] for i in resultado_mes} == {"Novo", "Fechado"}
    print("OK aplicar_filtros aceita um conjunto de valores para status/mês (filtro multi-seleção)")


def test_aplicar_filtros_com_conjunto_vazio_exclui_tudo():
    # conjunto vazio é um filtro ATIVO que não bate com nada — diferente
    # de None (sem filtro, mostra tudo). Importante para o Dashboard:
    # "desmarcar todos os status" deve mostrar uma lista vazia, não tudo.
    issues = [_issue(status="Novo")]
    assert aplicar_filtros(issues, status=set()) == []
    assert aplicar_filtros(issues, status=None) == issues
    print("OK conjunto vazio exclui tudo; None continua significando \"sem filtro\"")


def test_contagens_por_campo_incluem_sem_valor_e_somam_o_total():
    issues = [_issue(obra="CA-1000"), _issue(obra="CA-1000"), _issue(obra="")]
    contagem = contagem_por_obra(issues)
    assert contagem["CA-1000"] == 2
    assert contagem[SEM_VALOR] == 1
    assert sum(contagem.values()) == len(issues)
    print("OK contagem por campo agrupa valores ausentes em SEM_VALOR e soma bate com o total")


def test_contagem_por_status_disciplina_tipo_projetista():
    issues = [
        _issue(status="Novo", disciplina="ADI", tipo="Dúvida", atribuido_para="A"),
        _issue(status="Fechado", disciplina="HID", tipo="Erro", atribuido_para="B"),
        _issue(status="Fechado", disciplina="ADI", tipo="Erro", atribuido_para="B"),
    ]
    assert contagem_por_status(issues) == {"Fechado": 2, "Novo": 1}
    assert contagem_por_disciplina(issues) == {"ADI": 2, "HID": 1}
    assert contagem_por_tipo(issues) == {"Erro": 2, "Dúvida": 1}
    assert contagem_por_projetista(issues) == {"B": 2, "A": 1}
    print("OK contagem por status/disciplina/tipo/projetista")


def test_percentual_por_disciplina_soma_proximo_de_100():
    issues = [_issue(disciplina="ADI")] * 3 + [_issue(disciplina="HID")]
    percentuais = percentual_por_disciplina(issues)
    assert percentuais["ADI"] == 75.0
    assert percentuais["HID"] == 25.0
    assert abs(sum(percentuais.values()) - 100) < 0.01
    print("OK percentual por disciplina soma ~100%")


def test_percentual_por_disciplina_lista_vazia_nao_quebra():
    assert percentual_por_disciplina([]) == {}
    print("OK percentual por disciplina com lista vazia devolve dict vazio, sem ZeroDivisionError")


def test_contagem_por_mes_ordenada_cronologicamente_sem_inventar_meses_vazios():
    issues = [
        _issue(data_criacao="15/03/2026 10:00:00"),
        _issue(data_criacao="20/01/2026 10:00:00"),
        _issue(data_criacao="01/01/2026 08:00:00"),
        _issue(data_criacao="data inválida"),
    ]
    contagem = contagem_por_mes(issues)
    assert list(contagem.keys()) == ["2026-01", "2026-03"]
    assert contagem["2026-01"] == 2
    assert contagem["2026-03"] == 1
    print("OK contagem por mês ordena cronologicamente e ignora datas inválidas, sem mês fantasma")


def test_media_movel_por_mes_e_a_media_acumulada():
    issues = (
        [_issue(data_criacao="05/01/2026 10:00:00")] * 2
        + [_issue(data_criacao="05/02/2026 10:00:00")] * 4
    )
    media = media_movel_por_mes(issues)
    assert media["2026-01"] == 2.0
    assert media["2026-02"] == 3.0  # (2+4)/2
    print("OK média móvel por mês é a média acumulada mês a mês")


def test_calcular_kpis():
    issues = [
        _issue(status="Novo"), _issue(status="Novo"),
        _issue(status="Respondido"), _issue(status="Reaberto"),
        _issue(status="Fechado"), _issue(status="Fechado"), _issue(status="Fechado"),
    ]
    kpis = calcular_kpis(issues)
    assert kpis == {"total": 7, "problema": 2, "respondido": 1, "reaberto": 1, "fechado": 3}
    print("OK KPIs batem com as contagens de status")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE DADOS DO DASHBOARD PASSARAM")
