"""Carregamento, validação e gravação do arquivo de regras de clash
(`regras_clash.yaml`) — matriz disciplina x disciplina, tolerâncias,
folgas, exclusões, severidade e mapeamento de disciplina. Nenhum valor
aqui é norma: tudo o que vem marcado no YAML como "padrão a validar pela
equipe" é uma estimativa de mercado que a equipe de projeto deve
revisar antes de confiar no relatório gerado."""
import os

import yaml

CAMINHO_REGRAS_PADRAO = os.path.join(os.path.dirname(__file__), "regras_clash.yaml")


class RegrasClash:
    """Visão tipada do YAML de regras — carregada uma vez e consultada
    pelo motor de detecção e pela tela de edição de regras."""

    def __init__(self, dados):
        self.disciplinas = list(dados.get("disciplinas", []))
        self.tolerancia_hard_clash_m = float(dados.get("tolerancia_hard_clash_m", 0.01))
        self.folga_padrao_m = float(dados.get("folga_padrao_m", 0.05))
        self.matriz_disciplinas = dados.get("matriz_disciplinas", {})
        self.severidade = dados.get("severidade", [])
        self.ordem_rigidez_disciplinas = list(dados.get("ordem_rigidez_disciplinas", []))
        self.exclusoes = dados.get("exclusoes", {})
        self.duplicados = dados.get("duplicados", {})
        self.mapeamento_disciplina = dados.get("mapeamento_disciplina", {})
        self._dados_brutos = dados

    # ---------- matriz disciplina x disciplina ----------
    @staticmethod
    def chave_par(disc_a, disc_b):
        return "|".join(sorted([disc_a, disc_b]))

    def par_deve_ser_testado(self, disc_a, disc_b):
        """Por padrão todo par é testado, a menos que a matriz diga
        explicitamente `testar: false`."""
        config = self.matriz_disciplinas.get(self.chave_par(disc_a, disc_b))
        if config is None:
            return True
        return config.get("testar", True)

    def folga_minima(self, disc_a, disc_b):
        config = self.matriz_disciplinas.get(self.chave_par(disc_a, disc_b))
        if config is None or "folga_m" not in config:
            return self.folga_padrao_m
        return float(config["folga_m"])

    # ---------- severidade ----------
    def severidade_para(self, disciplina_a, disciplina_b, tipo):
        """Primeira regra cujas condições baterem vence; `quando: {}` é o
        catch-all e deve ficar por último no YAML."""
        par = {disciplina_a, disciplina_b}
        for regra in self.severidade:
            if self._condicoes_batem(regra.get("quando", {}), tipo, par):
                return regra.get("nivel", "Media")
        return "Media"

    @staticmethod
    def _condicoes_batem(condicoes, tipo, par):
        if not condicoes:
            return True
        if "disciplina_a" in condicoes and "disciplina_b" in condicoes:
            if {condicoes["disciplina_a"], condicoes["disciplina_b"]} != par:
                return False
        elif "disciplina_a" in condicoes:
            if condicoes["disciplina_a"] not in par:
                return False
        if "par" in condicoes and set(condicoes["par"]) != par:
            return False
        if "tipo" in condicoes and condicoes["tipo"] != tipo:
            return False
        return True

    # ---------- responsável sugerido ----------
    def responsavel_sugerido(self, disciplina_a, disciplina_b):
        """A disciplina mais 'flexível' (mais ao final de
        `ordem_rigidez_disciplinas`) é sugerida como responsável — a mais
        rígida (ex.: Estrutura) raramente se move. Isto é só uma
        SUGESTÃO, nunca uma decisão automática."""
        ordem = self.ordem_rigidez_disciplinas

        def posicao(disciplina):
            return ordem.index(disciplina) if disciplina in ordem else len(ordem)

        return max([disciplina_a, disciplina_b], key=posicao)


def carregar_regras(caminho=None):
    caminho = caminho or CAMINHO_REGRAS_PADRAO
    with open(caminho, "r", encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}
    return RegrasClash(dados)


def salvar_regras(regras, caminho=None):
    caminho = caminho or CAMINHO_REGRAS_PADRAO
    with open(caminho, "w", encoding="utf-8") as f:
        yaml.safe_dump(regras._dados_brutos, f, allow_unicode=True, sort_keys=False)
