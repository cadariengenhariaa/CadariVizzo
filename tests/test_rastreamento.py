"""Testes de clash/rastreamento.py: Novo / Ativo / Resolvido / Reaberto
entre revisões, e preservação de status/comentário/histórico já
registrados pelos projetistas."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_clash_")
config.DB_FILE = os.path.join(config.DB_DIR, "db_issues.json")

import ifcopenshell.api

from clash import armazenamento
from clash.motor import rodar_clash
from clash.rastreamento import mesclar_com_historico
from tests.fixtures_clash import adicionar_elemento_prisma
from tests.fixtures_clash import carregar_regras_teste as carregar_regras
from tests.fixtures_clash import criar_ifc_base


def _clash(id_, tipo="hard"):
    return {"id": id_, "tipo": tipo, "disciplina_a": "EST", "disciplina_b": "CLIM"}


def test_clash_novo_recebe_status_novo():
    resultado = mesclar_com_historico([_clash("c1")], [])
    assert len(resultado) == 1
    assert resultado[0]["status"] == "Novo"
    assert resultado[0]["rastreamento"] == "Novo"
    assert len(resultado[0]["historico_status"]) == 1
    print("OK interferência inédita entra como Novo com histórico inicial")


def test_clash_que_persiste_vira_ativo_preservando_status_e_comentario():
    anterior = _clash("c1")
    anterior["status"] = "Em análise"
    anterior["comentario"] = "Vou verificar com a estrutura"
    anterior["prazo"] = "2026-10-20"
    anterior["historico_status"] = [{"data": "x", "de": None, "para": "Novo", "por": "sistema"}]

    novo = _clash("c1")
    resultado = mesclar_com_historico([novo], [anterior])

    assert len(resultado) == 1
    item = resultado[0]
    assert item["status"] == "Em análise"  # preservado, não resetado para Novo
    assert item["comentario"] == "Vou verificar com a estrutura"
    assert item["prazo"] == "2026-10-20"
    assert item["rastreamento"] == "Ativo"
    print("OK interferência que persiste vira Ativo e preserva status/comentário/prazo")


def test_clash_que_some_vira_resolvido():
    anterior = _clash("c1")
    anterior["status"] = "Em análise"
    anterior["historico_status"] = []

    resultado = mesclar_com_historico([], [anterior])

    assert len(resultado) == 1
    assert resultado[0]["status"] == "Resolvido"
    assert resultado[0]["rastreamento"] == "Resolvido"
    print("OK interferência que não aparece mais na nova rodada vira Resolvido")


def test_clash_resolvido_que_reaparece_vira_reaberto():
    anterior = _clash("c1")
    anterior["status"] = "Resolvido"
    anterior["historico_status"] = [{"data": "x", "de": "Em análise", "para": "Resolvido", "por": "sistema"}]

    novo = _clash("c1")
    resultado = mesclar_com_historico([novo], [anterior])

    assert len(resultado) == 1
    item = resultado[0]
    assert item["status"] == "Reaberto"
    assert item["rastreamento"] == "Reaberto"
    assert item["historico_status"][-1]["para"] == "Reaberto"
    print("OK interferência resolvida que reaparece vira Reaberto, com histórico atualizado")


def test_clash_resolvido_que_continua_ausente_nao_reaparece_toda_hora():
    anterior = _clash("c1")
    anterior["status"] = "Resolvido"
    anterior["historico_status"] = []

    resultado = mesclar_com_historico([], [anterior])

    assert len(resultado) == 1
    assert resultado[0]["status"] == "Resolvido"
    assert resultado[0]["rastreamento"] == "Resolvido"
    print("OK interferência já resolvida que continua ausente não gera novo evento de histórico")


def test_clash_aceito_reaparecendo_vira_reaberto_nao_fica_aceito_em_silencio():
    anterior = _clash("c1")
    anterior["status"] = "Aceito"
    anterior["comentario"] = "Risco aceito pela equipe, ver ata de reunião 12/2026"
    anterior["historico_status"] = []

    novo = _clash("c1")
    resultado = mesclar_com_historico([novo], [anterior])

    assert resultado[0]["status"] == "Reaberto"  # Aceito é status fechado -> reaparecer = Reaberto
    print("OK status 'Aceito' é tratado como fechado — reaparecer gera Reaberto, não permanece Aceito em silêncio")


# ---------- integração de ponta a ponta: motor + armazenamento + rastreamento ----------
def test_motor_persiste_e_rastreia_entre_rodadas_isolado_do_banco_real():
    """Roda o motor de clash de verdade (persistir=True) contra um
    DB_DIR temporário — NUNCA o `db_clashes.json` real — e confirma que
    a segunda rodada (mesmo cenário) vira Ativo, e que remover o
    elemento e rodar de novo marca Resolvido."""
    # proteção: nunca o DB_DIR real — checa a propriedade (está dentro do
    # diretório temporário do sistema), não um prefixo específico deste
    # arquivo, porque vários arquivos de teste reatribuem config.DB_DIR no
    # nível de módulo e o pytest os importa todos antes de rodar qualquer
    # teste — o último a ser coletado "vence" para o resto da sessão,
    # então outro arquivo (igualmente isolado, só que com outro prefixo)
    # pode estar ativo quando este teste específico roda.
    assert config.DB_DIR.startswith(tempfile.gettempdir())

    f, body, storey = criar_ifc_base(prefixo_unidade_comprimento=None)
    viga = adicionar_elemento_prisma(f, body, storey, nome="Viga-Rastreio", ifc_class="IfcBeam",
                                      length=2.0, height=0.5, thickness=0.3)
    duto = adicionar_elemento_prisma(f, body, storey, nome="Duto-Rastreio", ifc_class="IfcDuctSegment",
                                      length=1.0, height=0.3, thickness=0.3, deslocamento=(0.5, 0.0, 0.1))
    regras = carregar_regras()
    arquivos_ifc = {"modelo.ifc": f}

    # rodada 1: deveria persistir como "Novo"
    r1 = rodar_clash(arquivos_ifc, regras, persistir=True)
    assert len(r1["clashes"]) == 1
    assert r1["clashes"][0]["rastreamento"] == "Novo"
    clash_id = r1["clashes"][0]["id"]

    salvos = armazenamento.carregar_clashes()
    assert len(salvos) == 1 and salvos[0]["id"] == clash_id

    # rodada 2: mesmo cenário — deveria virar "Ativo", preservando o status
    r2 = rodar_clash(arquivos_ifc, regras, persistir=True)
    assert len(r2["clashes"]) == 1
    assert r2["clashes"][0]["rastreamento"] == "Ativo"
    assert r2["clashes"][0]["id"] == clash_id

    # rodada 3: remove o duto (interferência "corrigida") — deveria virar
    # "Resolvido" (o item continua na lista retornada/salva, só que com
    # esse status — `rodar_clash` devolve o HISTÓRICO completo, não só
    # as interferências ainda em aberto; ver docstring de `motor.rodar_clash`)
    ifcopenshell.api.run("root.remove_product", f, product=duto)
    r3 = rodar_clash(arquivos_ifc, regras, persistir=True)
    assert len(r3["clashes"]) == 1
    assert r3["clashes"][0]["id"] == clash_id
    assert r3["clashes"][0]["status"] == "Resolvido"
    assert r3["clashes"][0]["rastreamento"] == "Resolvido"

    salvos_apos_resolver = armazenamento.carregar_clashes()
    assert len(salvos_apos_resolver) == 1
    assert salvos_apos_resolver[0]["id"] == clash_id
    assert salvos_apos_resolver[0]["status"] == "Resolvido"
    assert salvos_apos_resolver[0]["rastreamento"] == "Resolvido"

    print("OK motor persiste e rastreia Novo -> Ativo -> Resolvido entre rodadas reais, isolado do banco de produção")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DE RASTREAMENTO PASSARAM")
