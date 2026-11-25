"""Ponto de entrada do Visualizador Cadari de Projetos."""
import sys

from instancia_unica import garantir_instancia_unica


if __name__ == "__main__":
    if not garantir_instancia_unica():
        sys.exit(0)
    from app import AppCDE

    app = AppCDE()
    if app.usuario_atual is not None:
        app.mainloop()
    else:
        app.destroy()  # login cancelado/fechado — encerra sem abrir a janela principal
