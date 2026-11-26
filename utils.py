"""Funções utilitárias: banco de dados JSON, datas e filtros de issues."""
import json
import os
from datetime import datetime
from tkinter import messagebox

import banco_json
from config import DB_DIR, DB_FILE

ANOTACOES_FILE = os.path.join(DB_DIR, "db_anotacoes_pdf.json")


def agora_str():
    """Retorna data/hora atual formatada como string padrão do sistema."""
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def atualizar_data_modificacao(issue):
    """Atualiza o carimbo de última modificação de uma issue (in-place)."""
    issue["data_modificacao"] = agora_str()


def proximo_id(issues):
    return max([i["id"] for i in issues], default=0) + 1


# status renomeado: "Problema" passou a se chamar "Novo" (registros antigos
# são convertidos ao carregar e regravados com o nome novo)
_STATUS_ANTIGOS = {"Problema": "Novo"}


def migrar_status(issues):
    for issue in issues:
        if issue.get("status") in _STATUS_ANTIGOS:
            issue["status"] = _STATUS_ANTIGOS[issue["status"]]
    return issues


def carregar_banco_dados(silencioso=False):
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return migrar_status(json.load(f))
        return []
    except Exception as e:
        if silencioso:
            raise
        messagebox.showwarning(
            "Aviso de Rede",
            "Não foi possível carregar o banco de dados na unidade Z:.\n"
            f"Você está conectado à rede?\n\nErro: {e}"
        )
        return []


def _data_modificacao(issue):
    for campo in ("data_modificacao", "data_criacao"):
        try:
            return datetime.strptime((issue.get(campo) or "").strip(), "%d/%m/%Y %H:%M:%S")
        except ValueError:
            continue
    return datetime.min


def mesclar_issues(locais, disco, ids_base):
    """Combina a lista em memória deste app (`locais`) com a que está na
    rede agora (`disco`), para que um app aberto com dados antigos não
    desfaça o que outro computador gravou (ex.: uma transferência de
    problemas "voltar").

    `ids_base`: ids que existiam no banco quando este app carregou/salvou
    pela última vez. Regras:
    - some daqui e estava na base -> excluído aqui: sai do resultado;
    - existe nos dois -> fica a versão com `data_modificacao` mais recente
      (empate: a daqui);
    - estava na base mas sumiu da rede -> outro computador excluiu: sai;
    - é novo daqui (fora da base) -> entra; se o id colidir com um
      problema novo de outro computador, ganha o próximo id livre.
    Devolve (lista mesclada ordenada por id, {id_antigo: id_novo})."""
    ids_base = set(ids_base)
    ids_locais = {i.get("id") for i in locais}
    excluidos_aqui = ids_base - ids_locais
    resultado = {i.get("id"): i for i in disco if i.get("id") not in excluidos_aqui}
    renumerados = {}
    novos = []
    for issue in locais:
        iid = issue.get("id")
        if iid in ids_base:
            if iid not in resultado:
                continue  # excluído em outro computador
            if _data_modificacao(issue) >= _data_modificacao(resultado[iid]):
                resultado[iid] = issue
        elif iid in resultado and resultado[iid] != issue:
            novos.append(issue)  # colisão de id com problema novo de outro computador
        else:
            resultado[iid] = issue
    for issue in novos:
        novo_id = max(list(resultado) + [0]) + 1
        renumerados[issue.get("id")] = novo_id
        issue["id"] = novo_id
        resultado[novo_id] = issue
    return [resultado[k] for k in sorted(resultado)], renumerados


def salvar_banco_dados(issues, ids_base=None):
    """Grava as issues na rede. Com `ids_base` (ids conhecidos na última
    leitura), mescla antes com o que está gravado agora — ver
    `mesclar_issues`. Devolve a lista efetivamente gravada (e quem chama
    deve passar a usá-la), ou a própria lista se a leitura falhar."""
    gravadas = issues
    try:
        if ids_base is not None and os.path.exists(DB_FILE):
            try:
                gravadas, _ = mesclar_issues(issues, carregar_banco_dados(silencioso=True), ids_base)
            except Exception:
                gravadas = issues
        banco_json.gravar(DB_FILE, gravadas)  # backup + troca atômica; recusa se a rede estiver fora
    except Exception as e:
        messagebox.showerror("Erro de Salvamento", f"Falha ao salvar no banco de dados da rede.\n\nErro: {e}")
    return gravadas


def carregar_anotacoes():
    """Marcações livres (desenho/revisão) feitas sobre as pranchas em PDF —
    guardadas num arquivo próprio, separado do banco de issues, para não
    arriscar o formato dele."""
    try:
        if os.path.exists(ANOTACOES_FILE):
            with open(ANOTACOES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except Exception:
        return []


def salvar_anotacoes(anotacoes):
    try:
        banco_json.gravar(ANOTACOES_FILE, anotacoes)
    except Exception as e:
        messagebox.showerror("Erro de Salvamento", f"Falha ao salvar as marcações na rede.\n\nErro: {e}")


def transferir_atribuicoes(issues, nome_origem, nome_destino):
    """Passa todas as issues ATRIBUÍDAS a `nome_origem` para `nome_destino`
    (campo `atribuido_para`) — uso típico: alguém sai da empresa ou entra
    de férias e o trabalho em aberto precisa ir para outra pessoa. Não
    mexe em `criado_por` (é o registro histórico de quem apontou o
    problema, não muda). Mutação in-place; quem chama ainda precisa
    salvar. Retorna quantas issues foram transferidas."""
    transferidas = 0
    for issue in issues:
        if issue.get("atribuido_para") == nome_origem:
            issue["atribuido_para"] = nome_destino
            atualizar_data_modificacao(issue)
            transferidas += 1
    return transferidas


def transferir_issues_por_id(issues, ids_selecionados, nome_destino):
    """Como `transferir_atribuicoes`, mas move só as issues cujo `id`
    está em `ids_selecionados` — usado quando o usuário escolhe
    manualmente (com filtros de projeto/tipo/status) quais problemas
    transferir, em vez de mover TODOS de um usuário de uma vez. Também
    não mexe em `criado_por`. Mutação in-place; quem chama ainda precisa
    salvar. Retorna quantas issues foram transferidas."""
    ids_selecionados = set(ids_selecionados)
    transferidas = 0
    for issue in issues:
        if issue.get("id") in ids_selecionados:
            issue["atribuido_para"] = nome_destino
            atualizar_data_modificacao(issue)
            transferidas += 1
    return transferidas


def tipo_doc_issue(issue):
    """Retorna 'pdf' ou 'ifc'. Registros antigos (sem o campo) são tratados como 'pdf'."""
    return issue.get("tipo_doc", "pdf")


def filtro_issues_pdf(issues, filepath, page):
    return [
        i for i in issues
        if tipo_doc_issue(i) == "pdf" and i.get("filepath") == filepath and i.get("page") == page
    ]


def filtro_issues_ifc(issues, filepath):
    return [
        i for i in issues
        if tipo_doc_issue(i) == "ifc" and i.get("filepath") == filepath
    ]


def hex_to_rgb01(hex_color):
    """Converte '#RRGGBB' para uma tupla (r, g, b) normalizada em [0, 1], usada pelo VTK."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return r, g, b
