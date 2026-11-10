"""Orquestra pré-checagens → broad-phase → fase fina → exclusões →
agrupamento → rastreamento entre revisões. Usado tanto pela tela de
clash no app (`tela_clash.py`) quanto pelo CLI (`clash/cli.py`) — nenhum
dos dois reimplementa a lógica, só chamam `rodar_clash`."""
import time

from clash import agrupamento, armazenamento, deteccao, exclusoes, indice_espacial, pre_checagens, rastreamento
from clash.geometria import configuracoes_padrao, extrair_elementos


def rodar_clash(arquivos_ifc, regras, callback_progresso=None, persistir=True, selecao_a=None, selecao_b=None):
    """`arquivos_ifc`: dict {caminho: ifc_file} já abertos — tanto a UI
    (que já tem os arquivos carregados no visualizador) quanto o CLI
    (que abre via `ifcopenshell.open`) montam esse dict antes de chamar
    aqui. `persistir`: quando True (padrão), mescla com a revisão
    anterior salva e grava `db_clashes.json`; passe False para só
    inspecionar o resultado sem persistir (usado pelos testes).

    `selecao_a`/`selecao_b` (ambos `clash.selecao.SelecaoLado`, opcionais):
    quando os dois são passados, só são testados pares com um elemento
    em cada lado (modo Navisworks, usado pela tela de clash). Sem os
    dois, usa o modo antigo por matriz de disciplinas (ver
    `clash.indice_espacial.pares_candidatos`).

    Retorna um dict com: `clashes`, `pre_checagens` (ResultadoPreChecagens),
    `tempo_execucao_s`, `n_elementos`, `n_pares_candidatos`.

    Importante: `clashes` é o HISTÓRICO COMPLETO a persistir — inclui
    não só as interferências detectadas agora (Novo/Ativo/Reaberto) mas
    também as que já estavam resolvidas e não reapareceram nesta rodada
    (ver `clash.rastreamento.mesclar_com_historico`). Quem for mostrar
    só as interferências EM ABERTO (ex.: a lista principal da tela de
    clash) deve filtrar por `item["status"] not in
    clash.rastreamento.STATUS_FECHADOS`."""
    inicio = time.monotonic()
    settings = configuracoes_padrao()

    elementos = []
    for caminho, ifc_file in arquivos_ifc.items():
        elementos.extend(
            extrair_elementos(ifc_file, caminho, regras, settings=settings, callback_progresso=callback_progresso)
        )

    resultado_pre = pre_checagens.executar_pre_checagens(arquivos_ifc, elementos)
    escala_por_arquivo = resultado_pre.escala_por_arquivo

    pares = indice_espacial.pares_candidatos(elementos, regras, selecao_a=selecao_a, selecao_b=selecao_b)

    clashes_detectados = []
    for i, j in pares:
        elemento_a, elemento_b = elementos[i], elementos[j]

        excluido, _motivo = exclusoes.deve_excluir(
            elemento_a, elemento_b, arquivos_ifc, escala_por_arquivo, settings, regras
        )
        if excluido:
            continue

        classificacao = deteccao.classificar_par(elemento_a, elemento_b, regras)
        if classificacao is None:
            continue

        clash_id = agrupamento.id_estavel(elemento_a.guid, elemento_b.guid, classificacao["tipo"])
        nivel_agrupamento, disciplinas_agrupamento = agrupamento.chave_agrupamento(elemento_a, elemento_b)

        clashes_detectados.append({
            "id": clash_id,
            **classificacao,
            "disciplina_a": elemento_a.disciplina,
            "disciplina_b": elemento_b.disciplina,
            "elemento_a": _elemento_para_dict(elemento_a),
            "elemento_b": _elemento_para_dict(elemento_b),
            "severidade": regras.severidade_para(elemento_a.disciplina, elemento_b.disciplina, classificacao["tipo"]),
            "responsavel_sugerido": regras.responsavel_sugerido(elemento_a.disciplina, elemento_b.disciplina),
            "nivel": nivel_agrupamento,
        })

    clashes_anteriores = armazenamento.carregar_clashes() if persistir else []
    clashes_finais = rastreamento.mesclar_com_historico(clashes_detectados, clashes_anteriores)

    if persistir:
        armazenamento.salvar_clashes(clashes_finais)

    return {
        "clashes": clashes_finais,
        "pre_checagens": resultado_pre,
        "tempo_execucao_s": time.monotonic() - inicio,
        "n_elementos": len(elementos),
        "n_pares_candidatos": len(pares),
    }


def _elemento_para_dict(elemento):
    return {
        "guid": elemento.guid,
        "ifc_class": elemento.ifc_class,
        "nome": elemento.nome,
        "arquivo": elemento.arquivo,
        "nivel": elemento.nivel,
    }
