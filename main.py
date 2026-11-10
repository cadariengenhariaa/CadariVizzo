"""Ponto de entrada do Visualizador Cadari de Projetos."""
from app import AppCDE

if __name__ == "__main__":
    app = AppCDE()
    if app.usuario_atual is not None:
        app.mainloop()
    else:
        app.destroy()  # login cancelado/fechado — encerra sem abrir a janela principal
