"""Ponto de entrada de DIAGNÓSTICO — igual main.py, mas com DB_DIR
isolado num diretório temporário (nunca toca na base de produção) e
pensado para ser empacotado com console=True, para enxergar erros reais
do PyInstaller/VTK que não aparecem numa build --windowed."""
import os
import tempfile

import config

config.DB_DIR = os.path.join(tempfile.gettempdir(), "cadari_debug_fixo")
os.makedirs(config.DB_DIR, exist_ok=True)
config.DB_FILE = os.path.join(config.DB_DIR, "db_issues.json")

import utils

utils.DB_DIR = config.DB_DIR
utils.DB_FILE = config.DB_FILE

from app import AppCDE

if __name__ == "__main__":
    app = AppCDE()
    if app.usuario_atual is not None:
        app.mainloop()
    else:
        app.destroy()
