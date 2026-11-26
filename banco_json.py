"""Leitura e gravação seguras dos arquivos JSON do banco na rede
(`config.DB_DIR`): db_issues, db_usuarios, db_clashes e db_anotacoes_pdf.

Três proteções, criadas depois que o banco de usuários foi recriado
vazio (26/11/2026) quando a pasta do banco mudou de lugar:

1. **Pasta inacessível não vira banco novo.** Se `config.DB_DIR` não
   existir ou não estiver acessível (rede Z: fora, pasta movida), nada é
   gravado — `gravar()` levanta `BancoIndisponivel` em vez de criar a
   pasta e um arquivo novo.
2. **Backup antes de gravar.** O arquivo atual é copiado para
   `config.BACKUP_DIR` (`<nome>_AAAAMMDD_HHMMSS.json`) antes de cada
   gravação — no máximo um a cada `INTERVALO_BACKUP` por arquivo,
   mantendo os `MAX_BACKUPS` mais recentes.
3. **Gravação atômica.** Escreve num `.tmp` e troca com `os.replace`:
   uma falha no meio nunca deixa o arquivo vazio ou pela metade.

Os caminhos são lidos de `config` em tempo de CHAMADA, para os testes
(que trocam `config.DB_DIR`) nunca tocarem no banco real.
"""
import glob
import json
import os
import shutil
from datetime import datetime, timedelta

import config

INTERVALO_BACKUP = timedelta(minutes=10)
MAX_BACKUPS = 50  # por arquivo


class BancoIndisponivel(Exception):
    """A pasta do banco na rede não está acessível."""


def _pasta_backup():
    return getattr(config, "BACKUP_DIR", None) or os.path.join(config.DB_DIR, "backups")


def banco_acessivel():
    return os.path.isdir(config.DB_DIR)


def garantir_acesso():
    if not banco_acessivel():
        raise BancoIndisponivel(
            "Sem acesso à pasta do banco de dados:\n"
            f"{config.DB_DIR}\n\n"
            "Verifique se a unidade Z: está conectada. Nada foi gravado.")


def _backups_de(caminho):
    base = os.path.splitext(os.path.basename(caminho))[0]
    return sorted(glob.glob(os.path.join(_pasta_backup(), f"{base}_*.json")))


def existe_backup(nome_arquivo):
    """True se já houve algum backup desse arquivo — sinal de que ele já
    existiu com dados (então sumir agora é problema, não 1º uso)."""
    return bool(_backups_de(os.path.join(config.DB_DIR, nome_arquivo)))


def fazer_backup(caminho, agora=None):
    """Copia `caminho` para a pasta de backups (se existir e o último
    backup dele for mais antigo que INTERVALO_BACKUP). Devolve o caminho
    do backup criado, ou None."""
    if not os.path.exists(caminho):
        return None
    agora = agora or datetime.now()
    existentes = _backups_de(caminho)
    if existentes:
        ultimo = datetime.fromtimestamp(os.path.getmtime(existentes[-1]))
        if agora - ultimo < INTERVALO_BACKUP:
            return None
    os.makedirs(_pasta_backup(), exist_ok=True)
    base = os.path.splitext(os.path.basename(caminho))[0]
    destino = os.path.join(_pasta_backup(), f"{base}_{agora:%Y%m%d_%H%M%S}.json")
    shutil.copy2(caminho, destino)
    os.utime(destino)  # mtime = momento do backup (copy2 copia o do original)
    for antigo in _backups_de(caminho)[:-MAX_BACKUPS]:
        try:
            os.remove(antigo)
        except OSError:
            pass
    return destino


def ler(caminho, padrao=None):
    """Conteúdo do JSON, ou `padrao` (lista vazia) se o arquivo não existir."""
    if not os.path.exists(caminho):
        return [] if padrao is None else padrao
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def gravar(caminho, dados, indent=4):
    """Grava `dados` com as três proteções descritas no topo do módulo."""
    pasta = os.path.dirname(caminho)
    if os.path.normcase(os.path.abspath(pasta)) == os.path.normcase(os.path.abspath(config.DB_DIR)):
        garantir_acesso()
    elif not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)  # caminho explícito (ex.: testes, CLI)
    fazer_backup(caminho)
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=indent)
    os.replace(temporario, caminho)
