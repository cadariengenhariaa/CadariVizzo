"""Inferência da disciplina de um elemento IFC.

Ordem de prioridade (a primeira fonte que encontrar algo vence) — ver
`regras_clash.yaml: mapeamento_disciplina`:
  1. Padrão no caminho do arquivo de origem — útil porque os arquivos já
     costumam vir organizados em pastas por disciplina
     (ex.: ".../1386-ARQ/...").
  2. Propriedade explícita num Pset do elemento.
  3. PredefinedType do IfcSystem/IfcDistributionSystem ao qual o
     elemento está associado.
  4. Classe IFC do próprio elemento, como fallback.

Se nenhuma fonte configurada bater, a disciplina é DISCIPLINA_DESCONHECIDA
— o elemento é listado no relatório, nunca descartado silenciosamente."""
import re

import ifcopenshell.util.element
import ifcopenshell.util.system

DISCIPLINA_DESCONHECIDA = "OUTRO"


def disciplina_por_caminho(caminho_arquivo, regras):
    padroes = regras.mapeamento_disciplina.get("padroes_caminho_arquivo", {})
    for padrao, disciplina in padroes.items():
        if re.search(padrao, caminho_arquivo, re.IGNORECASE):
            return disciplina
    return None


def _disciplina_por_pset(elemento, regras):
    nomes_aceitos = regras.mapeamento_disciplina.get("propriedade_disciplina_pset", [])
    if not nomes_aceitos:
        return None
    psets = ifcopenshell.util.element.get_psets(elemento)
    for pset in psets.values():
        for nome in nomes_aceitos:
            valor = pset.get(nome)
            if valor:
                return str(valor).strip().upper()
    return None


def _disciplina_por_sistema(elemento, regras):
    mapa = regras.mapeamento_disciplina.get("predefinedtype_sistema", {})
    if not mapa:
        return None
    try:
        sistemas = ifcopenshell.util.system.get_element_systems(elemento)
    except Exception:
        return None
    for sistema in sistemas:
        tipo = getattr(sistema, "PredefinedType", None)
        if tipo and tipo in mapa:
            return mapa[tipo]
        nome = getattr(sistema, "Name", None) or getattr(sistema, "LongName", None) or ""
        for chave, disciplina in mapa.items():
            if chave.lower() in nome.lower():
                return disciplina
    return None


def _disciplina_por_classe(elemento, regras):
    mapa = regras.mapeamento_disciplina.get("classe_ifc", {})
    return mapa.get(elemento.is_a())


def inferir_disciplina(elemento, caminho_arquivo, regras):
    """Retorna a disciplina (string) inferida para `elemento`, ou
    DISCIPLINA_DESCONHECIDA se nenhuma fonte configurada bateu."""
    por_arquivo = disciplina_por_caminho(caminho_arquivo, regras)
    if por_arquivo:
        return por_arquivo

    por_pset = _disciplina_por_pset(elemento, regras)
    if por_pset:
        return por_pset

    por_sistema = _disciplina_por_sistema(elemento, regras)
    if por_sistema:
        return por_sistema

    por_classe = _disciplina_por_classe(elemento, regras)
    if por_classe:
        return por_classe

    return DISCIPLINA_DESCONHECIDA
