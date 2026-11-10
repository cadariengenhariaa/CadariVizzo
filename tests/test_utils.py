"""Testes de utils.py: funções puras que não tocam em disco (as que
tocam, como carregar/salvar_banco_dados, já são exercitadas indiretamente
pelos testes de integração de outras telas)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import transferir_atribuicoes, transferir_issues_por_id


def _issue(**kwargs):
    base = {"id": 1, "atribuido_para": "Fulano", "data_modificacao": "01/01/2026 10:00:00"}
    base.update(kwargs)
    return base


def test_transferir_atribuicoes_move_so_do_usuario_origem():
    issues = [
        _issue(id=1, atribuido_para="Fulano"),
        _issue(id=2, atribuido_para="Ciclano"),
        _issue(id=3, atribuido_para="Fulano"),
    ]
    qtd = transferir_atribuicoes(issues, "Fulano", "Beltrano")
    assert qtd == 2
    assert [i["atribuido_para"] for i in issues] == ["Beltrano", "Ciclano", "Beltrano"]
    print("OK transferir_atribuicoes move só as issues do usuário de origem")


def test_transferir_atribuicoes_atualiza_data_modificacao():
    issues = [_issue(id=1, atribuido_para="Fulano", data_modificacao="01/01/2026 10:00:00")]
    transferir_atribuicoes(issues, "Fulano", "Beltrano")
    assert issues[0]["data_modificacao"] != "01/01/2026 10:00:00"
    print("OK transferir_atribuicoes atualiza a data de modificação das issues transferidas")


def test_transferir_atribuicoes_nao_mexe_em_criado_por():
    issues = [_issue(id=1, atribuido_para="Fulano", criado_por="Fulano")]
    transferir_atribuicoes(issues, "Fulano", "Beltrano")
    assert issues[0]["criado_por"] == "Fulano"  # histórico de quem criou não muda
    assert issues[0]["atribuido_para"] == "Beltrano"
    print("OK transferir_atribuicoes preserva criado_por (só muda atribuido_para)")


def test_transferir_atribuicoes_sem_correspondencia_retorna_zero():
    issues = [_issue(id=1, atribuido_para="Ciclano")]
    qtd = transferir_atribuicoes(issues, "Fulano", "Beltrano")
    assert qtd == 0
    assert issues[0]["atribuido_para"] == "Ciclano"
    print("OK transferir_atribuicoes sem nenhuma issue do usuário de origem retorna 0 e não mexe em nada")


def test_transferir_issues_por_id_move_so_as_marcadas():
    issues = [
        _issue(id=1, atribuido_para="Fulano"),
        _issue(id=2, atribuido_para="Fulano"),
        _issue(id=3, atribuido_para="Fulano"),
    ]
    qtd = transferir_issues_por_id(issues, [1, 3], "Beltrano")
    assert qtd == 2
    assert [i["atribuido_para"] for i in issues] == ["Beltrano", "Fulano", "Beltrano"]
    print("OK transferir_issues_por_id move só as issues com id na lista selecionada")


def test_transferir_issues_por_id_atualiza_data_modificacao():
    issues = [_issue(id=1, atribuido_para="Fulano", data_modificacao="01/01/2026 10:00:00")]
    transferir_issues_por_id(issues, [1], "Beltrano")
    assert issues[0]["data_modificacao"] != "01/01/2026 10:00:00"
    print("OK transferir_issues_por_id atualiza a data de modificação das issues transferidas")


def test_transferir_issues_por_id_nao_mexe_em_criado_por():
    issues = [_issue(id=1, atribuido_para="Fulano", criado_por="Fulano")]
    transferir_issues_por_id(issues, [1], "Beltrano")
    assert issues[0]["criado_por"] == "Fulano"
    assert issues[0]["atribuido_para"] == "Beltrano"
    print("OK transferir_issues_por_id preserva criado_por (só muda atribuido_para)")


def test_transferir_issues_por_id_ignora_ids_nao_selecionados_ou_inexistentes():
    issues = [
        _issue(id=1, atribuido_para="Fulano"),
        _issue(id=2, atribuido_para="Fulano"),
    ]
    qtd = transferir_issues_por_id(issues, [1, 999], "Beltrano")  # 999 não existe
    assert qtd == 1
    assert issues[0]["atribuido_para"] == "Beltrano"
    assert issues[1]["atribuido_para"] == "Fulano"  # id 2 não estava selecionado, não muda
    print("OK transferir_issues_por_id ignora ids inexistentes e não mexe no que não foi selecionado")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE UTILS PASSARAM")
