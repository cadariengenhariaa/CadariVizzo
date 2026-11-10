"""Preferências locais do usuário (por computador, fora da rede): hoje só
o modo de tema escolhido. Arquivo JSON em %APPDATA%\\CadariVizzo — ou no
caminho da variável CADARI_VIZZO_PREFS (usada pelos testes)."""
import json
import os


def _caminho():
    if os.environ.get("CADARI_VIZZO_PREFS"):
        return os.environ["CADARI_VIZZO_PREFS"]
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "CadariVizzo", "preferencias.json")


def carregar():
    try:
        with open(_caminho(), encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def salvar(**valores):
    dados = carregar()
    dados.update(valores)
    try:
        os.makedirs(os.path.dirname(_caminho()), exist_ok=True)
        with open(_caminho(), "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # preferência é conveniência: falhar ao salvar não pode travar o app
