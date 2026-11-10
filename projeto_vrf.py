"""Ecossistema de um projeto na rede: cada obra tem a pasta
Z:\\Projetos\\Ativos\\CA-xxxx e, dentro dela, a pasta de verificação
xxxx-VRF com uma subpasta por disciplina — ex.:
    Z:\\Projetos\\Ativos\\CA-1439A\\1439A-VRF\\1439A-PCI
(projetos antigos usam só ...\\1439A-VRF\\PCI). Uma verificação (VRF)
começa escolhendo CA + disciplina; daqui sai a pasta e a lista de
documentos para abrir direto, sem procurar no servidor.

Convenção de nomes já usada na empresa para a cópia certificada:
    <arquivo>_<INICIAIS DO VERIFICADOR>_<SELO>.pdf
    ex.: 1439A-PCI_EX_26_10_14_R00_NPG_HAC_APCR.pdf
"""
import os
import re
from datetime import datetime

import config
from config import SELOS_STATUS

EXTENSOES = {"pdf": (".pdf",), "ifc": (".ifc",)}
_PARTICULAS = {"de", "da", "do", "das", "dos", "e"}
_REVISAO = re.compile(r"(?:^|[_\-.\s])R(\d{2})(?=$|[_\-.\s])", re.IGNORECASE)
_OBRA_NO_CAMINHO = re.compile(r"(CA-\d+[A-Z]?)", re.IGNORECASE)


def numero_obra(obra):
    obra = (obra or "").strip()
    return obra[3:] if obra.upper().startswith("CA-") else obra


def obra_do_caminho(caminho):
    m = _OBRA_NO_CAMINHO.search(caminho or "")
    return m.group(1).upper() if m else None


def pasta_obra(obra, base=None):
    if not obra:
        return None
    base = base or config.PROJETOS_DIR  # lido na hora (os testes trocam a pasta-base)
    pasta = os.path.join(base, obra.strip())
    return pasta if os.path.isdir(pasta) else None


def pasta_vrf(obra, disciplina=None, base=None):
    """Pasta de verificação da disciplina (ou a VRF da obra, ou a própria
    obra, o que existir — nessa ordem). None se nem a obra existir."""
    raiz = pasta_obra(obra, base)
    if raiz is None:
        return None
    num = numero_obra(obra)
    vrf = os.path.join(raiz, f"{num}-VRF")
    if os.path.isdir(vrf):
        if disciplina:
            for nome in (f"{num}-{disciplina}", disciplina):
                candidato = os.path.join(vrf, nome)
                if os.path.isdir(candidato):
                    return candidato
            # nomes com caixa diferente (ex.: "pci")
            alvo = {f"{num}-{disciplina}".lower(), disciplina.lower()}
            for nome in os.listdir(vrf):
                if nome.lower() in alvo and os.path.isdir(os.path.join(vrf, nome)):
                    return os.path.join(vrf, nome)
        return vrf
    return raiz


def iniciais(nome):
    """"Lucas Coutinho Ferreira Gomes" -> "LCFG" (ignora de/da/do...)."""
    partes = [p for p in (nome or "").split() if p.lower() not in _PARTICULAS]
    return "".join(p[0] for p in partes if p[:1].isalpha()).upper()


def selo_no_nome(nome_arquivo):
    """Código do selo se o arquivo for uma cópia certificada (termina em
    _APR / _APCA / _APCR / _RPV antes da extensão), senão None."""
    base = os.path.splitext(os.path.basename(nome_arquivo))[0].upper()
    for codigo in sorted(SELOS_STATUS, key=len, reverse=True):
        if base.endswith("_" + codigo) or re.search(rf"_{codigo}\d*$", base):
            return codigo
    return None


def revisao(nome_arquivo):
    m = _REVISAO.search(os.path.splitext(os.path.basename(nome_arquivo))[0])
    return f"R{m.group(1)}" if m else None


def nome_certificado(caminho, iniciais_verificador, codigo):
    pasta, nome = os.path.split(caminho)
    base, ext = os.path.splitext(nome)
    sufixo = "_".join(p for p in (iniciais_verificador, codigo) if p)
    return os.path.join(pasta, f"{base}_{sufixo}{ext or '.pdf'}")


def listar_documentos(pasta, tipo="pdf"):
    """Documentos da pasta (sem subpastas), do mais recente ao mais
    antigo: dicts com caminho, nome, modificado, revisao e certificado
    (código do selo, se for cópia certificada)."""
    if not pasta or not os.path.isdir(pasta):
        return []
    extensoes = EXTENSOES.get(tipo, (".pdf",))
    documentos = []
    for nome in os.listdir(pasta):
        caminho = os.path.join(pasta, nome)
        if not nome.lower().endswith(extensoes) or not os.path.isfile(caminho):
            continue
        try:
            modificado = datetime.fromtimestamp(os.path.getmtime(caminho))
        except OSError:
            modificado = None
        documentos.append({"caminho": caminho, "nome": nome, "modificado": modificado,
                           "revisao": revisao(nome), "certificado": selo_no_nome(nome)})
    documentos.sort(key=lambda d: d["modificado"] or datetime.min, reverse=True)
    return documentos


def contar_pranchas(obra, tipo="pdf", base=None):
    """(originais, certificadas, revisão mais alta) na pasta VRF da obra
    inteira (todas as disciplinas, sem descer em PAST/Ultrapassados)."""
    vrf = pasta_vrf(obra, None, base)
    if not vrf:
        return 0, 0, None
    pastas = [vrf] + [os.path.join(vrf, n) for n in os.listdir(vrf) if os.path.isdir(os.path.join(vrf, n))]
    originais = certificadas = 0
    revisoes = []
    for pasta in pastas:
        for doc in listar_documentos(pasta, tipo):
            if doc["certificado"]:
                certificadas += 1
            else:
                originais += 1
            if doc["revisao"]:
                revisoes.append(doc["revisao"])
    return originais, certificadas, (max(revisoes) if revisoes else None)
