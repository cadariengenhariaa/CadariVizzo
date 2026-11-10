"""Compara a detecção de uma nova revisão com a revisão anterior salva
(`clash.armazenamento`) e classifica cada interferência como Novo,
Ativo, Resolvido ou Reaberto — preservando status, comentários, prazo e
histórico já registrados pelos projetistas em revisões anteriores."""
from utils import agora_str

STATUS_INICIAL = "Novo"
STATUS_ABERTOS = {"Novo", "Em análise", "Atribuído", "Reaberto"}
STATUS_FECHADOS = {"Resolvido", "Aprovado", "Aceito"}

CAMPOS_PRESERVADOS = ("status", "comentario", "prazo", "responsavel_atribuido", "historico_status")


def mesclar_com_historico(novos_clashes, clashes_anteriores):
    """`novos_clashes`: interferências recém-detectadas nesta rodada
    (dicts já com `id` estável, sem campos de workflow ainda).
    `clashes_anteriores`: o que estava salvo da rodada anterior (saída
    desta mesma função, numa chamada passada). Retorna a lista final a
    salvar — inclui os novos/ativos/reabertos E os que já estavam
    resolvidos e não voltaram a aparecer (para manter o histórico
    completo entre revisões)."""
    anteriores_por_id = {c["id"]: c for c in clashes_anteriores}
    ids_novos = {c["id"] for c in novos_clashes}
    agora = agora_str()

    resultado = []

    for clash in novos_clashes:
        anterior = anteriores_por_id.get(clash["id"])
        if anterior is None:
            clash["status"] = STATUS_INICIAL
            clash["rastreamento"] = "Novo"
            clash["comentario"] = ""
            clash["prazo"] = ""
            clash["responsavel_atribuido"] = ""
            clash["historico_status"] = [
                {"data": agora, "de": None, "para": STATUS_INICIAL, "por": "sistema"}
            ]
        else:
            for campo in CAMPOS_PRESERVADOS:
                if campo in anterior:
                    clash[campo] = anterior[campo]
            clash.setdefault("historico_status", [])
            if anterior.get("status") in STATUS_FECHADOS:
                clash["historico_status"].append({
                    "data": agora, "de": anterior.get("status"), "para": "Reaberto", "por": "sistema",
                })
                clash["status"] = "Reaberto"
                clash["rastreamento"] = "Reaberto"
            else:
                clash["rastreamento"] = "Ativo"
        resultado.append(clash)

    for anterior in clashes_anteriores:
        if anterior["id"] in ids_novos:
            continue
        if anterior.get("status") in STATUS_FECHADOS:
            anterior["rastreamento"] = "Resolvido"
            resultado.append(anterior)
            continue
        anterior["historico_status"] = anterior.get("historico_status", []) + [
            {"data": agora, "de": anterior.get("status"), "para": "Resolvido", "por": "sistema"}
        ]
        anterior["status"] = "Resolvido"
        anterior["rastreamento"] = "Resolvido"
        resultado.append(anterior)

    return resultado
