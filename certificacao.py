"""Certificação de pranchas por selo (aba "Certificação" do visualizador
de PDF). O selo carimbado define o status da prancha: o código vem do
nome do arquivo do selo em SELOS_DIR (APR.png -> "APR") e a descrição/
cor, de `config.SELOS_STATUS`.

Cada prancha tem UM selo de cada vez: aplicar um novo SUBSTITUI o atual.
Nenhum selo é apagado do banco — cada um guarda o seu `estado`:
    "ativo"       o que aparece na prancha e define o status
    "substituido" trocado por um selo mais novo (fica no histórico)
    "removido"    retirado da prancha (fica no histórico)
Registros antigos, sem `estado`: o mais recente da prancha conta como
ativo e os demais como substituídos.

Funções puras: recebem a lista de anotações (o mesmo banco das marcações
livres, `utils.carregar_anotacoes`) e devolvem/alteram dados simples —
sem Tkinter."""
import os

from config import SELOS_DIR, SELOS_STATUS
from dashboard.dados_dashboard import _parse_data

EXTENSOES_SELO = (".png", ".jpg", ".jpeg", ".bmp")
COR_SEM_STATUS = "#5F6F76"


def codigo_selo(caminho):
    return os.path.splitext(os.path.basename(caminho or ""))[0].strip().upper()


def info_selo(caminho):
    codigo = codigo_selo(caminho)
    dados = SELOS_STATUS.get(codigo, {})
    return {
        "codigo": codigo,
        "descricao": dados.get("descricao", codigo.title() or "Selo"),
        "cor": dados.get("cor", COR_SEM_STATUS),
        "caminho": caminho,
    }


def listar_selos(pasta=SELOS_DIR):
    """Selos (imagens) disponíveis na pasta, os conhecidos de
    `SELOS_STATUS` primeiro, na ordem definida lá."""
    try:
        nomes = [n for n in os.listdir(pasta)
                 if n.lower().endswith(EXTENSOES_SELO) and os.path.isfile(os.path.join(pasta, n))]
    except OSError:
        return []
    ordem = list(SELOS_STATUS)

    def chave(nome):
        codigo = codigo_selo(nome)
        return (ordem.index(codigo) if codigo in ordem else len(ordem), codigo)

    return [info_selo(os.path.join(pasta, n)) for n in sorted(nomes, key=chave)]


def selos_do_documento(anotacoes, filepath):
    """Selos carimbados no PDF, do mais antigo ao mais recente."""
    selos = [a for a in anotacoes if a.get("tipo") == "selo" and a.get("filepath") == filepath]

    def chave(a):
        data = _parse_data(a.get("data"))
        return (data.timestamp() if data else 0, a.get("id", 0))

    return sorted(selos, key=chave)


ATIVO, SUBSTITUIDO, REMOVIDO = "ativo", "substituido", "removido"


def estado_selo(anotacao, anotacoes):
    """Estado do selo; para registros antigos (sem `estado`), deduz: o
    mais recente da prancha é o ativo, os demais foram substituídos."""
    if anotacao.get("estado"):
        return anotacao["estado"]
    selos = selos_do_documento(anotacoes, anotacao.get("filepath"))
    sem_estado = [s for s in selos if not s.get("estado")]
    tem_ativo_novo = any(s.get("estado") == ATIVO for s in selos)
    if not tem_ativo_novo and sem_estado and sem_estado[-1] is anotacao:
        return ATIVO
    return SUBSTITUIDO


def selo_ativo(anotacoes, filepath):
    """O selo que está na prancha agora (ou None)."""
    ativos = [s for s in selos_do_documento(anotacoes, filepath) if estado_selo(s, anotacoes) == ATIVO]
    return ativos[-1] if ativos else None


def aplicar_selo(anotacoes, novo, quando=None):
    """Acrescenta `novo` como o selo ativo da prancha; o que estava ativo
    passa a "substituido" (com data e o id do substituto). Muta e devolve
    `anotacoes`."""
    atual = selo_ativo(anotacoes, novo.get("filepath"))
    if atual is not None:
        atual["estado"] = SUBSTITUIDO
        atual["substituido_em"] = quando or novo.get("data", "")
        atual["substituido_por"] = novo.get("id")
    novo["estado"] = ATIVO
    anotacoes.append(novo)
    return anotacoes


def remover_selo(anotacoes, anotacao_id, autor="", quando=""):
    """Tira o selo da prancha mantendo-o no histórico. A prancha fica sem
    selo ativo ("aguardando certificação") — o anterior NÃO volta."""
    for a in anotacoes:
        if a.get("id") == anotacao_id and a.get("tipo") == "selo":
            a["estado"] = REMOVIDO
            a["removido_em"] = quando
            a["removido_por"] = autor
            return True
    return False


def mover_selo(anotacoes, anotacao_id, x, y, quando=""):
    """Nova posição (canto superior esquerdo, coordenadas da página)."""
    for a in anotacoes:
        if a.get("id") == anotacao_id and a.get("tipo") == "selo":
            a["pontos"] = [[x, y]]
            a["movido_em"] = quando
            return True
    return False


def status_certificacao(anotacoes, filepath):
    """Status atual da prancha (o selo ativo) ou None se ela não tem
    selo — nunca certificada, ou o selo foi removido."""
    ultimo = selo_ativo(anotacoes, filepath)
    if ultimo is None:
        return None
    info = info_selo(ultimo.get("arquivo_selo"))
    info.update({
        "autor": ultimo.get("autor") or "",
        "data": ultimo.get("data") or "",
        "pagina": ultimo.get("page", 0),
        "anotacao_id": ultimo.get("id"),
    })
    return info


def legenda_selo(anotacao):
    """Texto impresso sob o selo na prancha: "APR · Aprovado — 20/10/2026 · Ana"."""
    info = info_selo(anotacao.get("arquivo_selo"))
    data = (anotacao.get("data") or "")[:10]
    autor = anotacao.get("autor") or ""
    partes = [f"{info['codigo']} · {info['descricao']}"]
    detalhe = " · ".join(p for p in (data, autor) if p)
    if detalhe:
        partes.append(detalhe)
    return " — ".join(partes)


def tom_claro(cor_hex, fator=0.86):
    """Mistura a cor com branco (fundo de pílula a partir da cor do selo)."""
    cor_hex = cor_hex.lstrip("#")
    r, g, b = (int(cor_hex[i:i + 2], 16) for i in (0, 2, 4))
    misturar = lambda c: round(c + (255 - c) * fator)  # noqa: E731
    return f"#{misturar(r):02X}{misturar(g):02X}{misturar(b):02X}"


def certificacoes_por_obra(anotacoes, issues):
    """{obra: status do selo mais recente entre as pranchas dela}. A obra
    de cada prancha vem das issues dela ou, sem issues, do caminho do
    arquivo (pasta CA-xxxx)."""
    from projeto_vrf import obra_do_caminho

    obra_do_arquivo = {}
    for i in issues:
        if i.get("filepath") and i.get("obra"):
            obra_do_arquivo.setdefault(i["filepath"], i["obra"])
    resultado = {}
    for caminho in {a.get("filepath") for a in anotacoes if a.get("tipo") == "selo" and a.get("filepath")}:
        obra = obra_do_arquivo.get(caminho) or obra_do_caminho(caminho)
        status = status_certificacao(anotacoes, caminho)
        if not obra or not status:
            continue
        atual = resultado.get(obra)
        chave = lambda st: (_parse_data(st["data"]) or _parse_data("01/01/1900"), st.get("anotacao_id") or 0)  # noqa: E731
        if atual is None or chave(status) > chave(atual):
            resultado[obra] = status
    return resultado
