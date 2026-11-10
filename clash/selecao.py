"""Seleção A/B de arquivos e níveis para o teste de interferência —
estilo "Select" do Navisworks Clash Detective: duas árvores (arquivo >
nível), cada uma marcando o que participa daquele lado do teste. Testa-se
tudo que está em A contra tudo que está em B — substitui a matriz
disciplina x disciplina como critério de QUAIS pares testar (a matriz
continua valendo para folga/severidade/responsável sugerido por par de
disciplinas, isso não muda)."""


def agrupar_por_arquivo(niveis_info):
    """`niveis_info`: dict {(caminho, storey_guid|None): {"nome",
    "elevacao", "caminho", ...}} — mesma estrutura mantida por
    `ifc_viewer.IFCViewerFrame.niveis_info`. Devolve {caminho:
    [(nivel_guid, nome, elevacao), ...]} ordenado por elevação, pronto
    para montar a árvore de seleção."""
    por_arquivo = {}
    for (caminho, nivel_guid), info in niveis_info.items():
        por_arquivo.setdefault(caminho, []).append((nivel_guid, info["nome"], info["elevacao"]))
    for niveis in por_arquivo.values():
        niveis.sort(key=lambda t: t[2])
    return por_arquivo


class SelecaoLado:
    """Conjunto de (caminho, nivel_guid) marcados para um lado (A ou B)
    do teste. Começa vazio — o usuário monta os dois lados marcando a
    árvore, nada entra por padrão."""

    def __init__(self):
        self._marcados = set()

    def nivel_marcado(self, caminho, nivel_guid):
        return (caminho, nivel_guid) in self._marcados

    def arquivo_marcado(self, caminho, niveis_do_arquivo):
        """True só se TODOS os níveis do arquivo estiverem marcados —
        define o estado "totalmente marcado" do nó arquivo na árvore."""
        if not niveis_do_arquivo:
            return False
        return all(self.nivel_marcado(caminho, ng) for ng, _, _ in niveis_do_arquivo)

    def arquivo_parcial(self, caminho, niveis_do_arquivo):
        """True se ALGUNS (não todos) os níveis do arquivo estão
        marcados — para mostrar um estado "parcial" (nem ✔ nem ☐)."""
        marcados = [self.nivel_marcado(caminho, ng) for ng, _, _ in niveis_do_arquivo]
        return any(marcados) and not all(marcados)

    def alternar_nivel(self, caminho, nivel_guid):
        chave = (caminho, nivel_guid)
        if chave in self._marcados:
            self._marcados.discard(chave)
        else:
            self._marcados.add(chave)

    def definir_arquivo(self, caminho, niveis_do_arquivo, marcado):
        """Marca/desmarca TODOS os níveis do arquivo de uma vez — é o
        que acontece ao clicar no checkbox do nó arquivo (não do nível)."""
        for nivel_guid, _, _ in niveis_do_arquivo:
            chave = (caminho, nivel_guid)
            if marcado:
                self._marcados.add(chave)
            else:
                self._marcados.discard(chave)

    def esvaziar(self):
        self._marcados.clear()

    def limitar_aos_arquivos(self, caminhos_validos):
        """Remove marcações de arquivos que não existem mais (ex.: o
        usuário removeu o modelo do visualizador) — chamar sempre que a
        lista de arquivos carregados mudar."""
        self._marcados = {(c, ng) for (c, ng) in self._marcados if c in caminhos_validos}

    def esta_vazia(self):
        return not self._marcados

    def elemento_incluido(self, elemento):
        """`elemento`: ElementoClash — usa `.arquivo` e `.nivel_guid`
        (não `.nivel`, que é só o nome e pode repetir entre arquivos ou
        até dentro do mesmo arquivo)."""
        return self.nivel_marcado(elemento.arquivo, elemento.nivel_guid)


def par_deve_ser_testado(elemento_a, elemento_b, selecao_a, selecao_b):
    """Um par é candidato se um dos dois lados cobre `elemento_a` e o
    outro cobre `elemento_b` — em qualquer ordem, já que a interferência
    é simétrica (A x B é o mesmo teste que B x A)."""
    return (
        (selecao_a.elemento_incluido(elemento_a) and selecao_b.elemento_incluido(elemento_b))
        or (selecao_a.elemento_incluido(elemento_b) and selecao_b.elemento_incluido(elemento_a))
    )
