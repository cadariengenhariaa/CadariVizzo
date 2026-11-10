"""Testes de utils.mesclar_issues / migrar_status: dois computadores com
o app aberto não podem mais desfazer o trabalho um do outro (o caso
real: problemas transferidos que "voltaram" porque um app com a lista
antiga na memória regravou o banco inteiro)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import mesclar_issues, migrar_status


def _i(id_, mod="20/10/2026 10:00:00", **kw):
    base = {"id": id_, "titulo": f"T{id_}", "status": "Novo", "atribuido_para": "Fulano",
            "data_criacao": "19/10/2026 10:00:00", "data_modificacao": mod}
    base.update(kw)
    return base


def test_transferencia_feita_em_outro_computador_nao_volta():
    # A (app antigo) carregou #1 atribuída a Lulu; B transferiu para Ana às 11h.
    locais_a = [_i(1, "20/10/2026 10:00:00", atribuido_para="Lulu"), _i(2, "20/10/2026 10:00:00")]
    disco = [_i(1, "20/10/2026 11:00:00", atribuido_para="Ana"), _i(2, "20/10/2026 10:00:00")]
    # A edita só a #2 e salva
    locais_a[1]["titulo"] = "editado"
    locais_a[1]["data_modificacao"] = "20/10/2026 12:00:00"
    mescladas, renum = mesclar_issues(locais_a, disco, ids_base={1, 2})
    por_id = {i["id"]: i for i in mescladas}
    assert por_id[1]["atribuido_para"] == "Ana"   # a transferência de B sobrevive
    assert por_id[2]["titulo"] == "editado"        # e a edição de A também
    assert renum == {}


def test_exclusoes_daqui_e_de_outro_computador_sao_respeitadas():
    locais = [_i(1), _i(3)]                 # excluí a #2 aqui
    disco = [_i(1), _i(2), _i(4)]           # outro computador excluiu a #3 e criou a #4
    mescladas, _ = mesclar_issues(locais, disco, ids_base={1, 2, 3})
    assert [i["id"] for i in mescladas] == [1, 4]


def test_problemas_novos_com_mesmo_id_em_dois_computadores_nao_se_perdem():
    locais = [_i(1), _i(5, titulo="criado aqui")]
    disco = [_i(1), _i(5, titulo="criado lá")]
    mescladas, renum = mesclar_issues(locais, disco, ids_base={1})
    titulos = {i["titulo"]: i["id"] for i in mescladas}
    assert titulos["criado lá"] == 5 and titulos["criado aqui"] == 6
    assert renum == {5: 6}


def test_migrar_status_problema_vira_novo():
    issues = [{"status": "Problema"}, {"status": "Fechado"}]
    assert [i["status"] for i in migrar_status(issues)] == ["Novo", "Fechado"]


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE MESCLAGEM PASSARAM")
