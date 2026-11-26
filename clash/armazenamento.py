"""Persistência dos resultados de clash — `db_clashes.json`, um arquivo
próprio em `config.DB_DIR`, separado de `db_issues.json` (issues
manuais) e `db_anotacoes_pdf.json` (marcações de PDF), seguindo o mesmo
padrão de arquivo-JSON-por-concern já usado em `utils.py`.

Diferente de `utils.py`, este módulo não depende de `tkinter` — ele
também é usado pelo CLI (`clash/cli.py`), que roda sem GUI. Erros de
leitura/escrita na rede são propagados como exceção; quem chama pela UI
(tela_clash.py) decide como mostrar isso ao usuário (messagebox), e o
CLI decide como logar."""
import json
import os

import banco_json
import config


def _caminho_padrao():
    # lido em tempo de CHAMADA (não de import) de propósito: assim um
    # teste que sobrescreve `config.DB_DIR` antes de chamar
    # carregar/salvar_clashes funciona mesmo que este módulo já tenha
    # sido importado antes por outro teste na mesma sessão do pytest —
    # uma constante de módulo calculada no import (`os.path.join(DB_DIR,...)`
    # com `from config import DB_DIR`) ficaria congelada no valor de
    # produção e um teste descuidado escreveria no db_clashes.json real.
    return os.path.join(config.DB_DIR, "db_clashes.json")


def carregar_clashes(caminho=None):
    return banco_json.ler(caminho or _caminho_padrao())


def salvar_clashes(clashes, caminho=None):
    banco_json.gravar(caminho or _caminho_padrao(), clashes)
