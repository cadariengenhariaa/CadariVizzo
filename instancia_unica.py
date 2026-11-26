"""Garante que só uma janela do Cadari Vizzo fique aberta por usuário.

No Windows usa um *mutex nomeado* do sistema: a primeira instância o cria
e o mantém enquanto o processo viver; uma segunda instância detecta que
ele já existe (ERROR_ALREADY_EXISTS), traz a janela aberta para a frente
e encerra. O mutex é liberado automaticamente pelo Windows quando o
processo termina — inclusive se travar ou for morto pelo Gerenciador de
Tarefas —, então nunca fica "preso".

O prefixo "Local\\" restringe a trava à sessão do usuário: em servidor de
terminal/RDP, cada usuário continua podendo abrir a sua própria janela.

Fora do Windows (ex.: testes em Linux) a verificação é ignorada.
"""
import sys

NOME_MUTEX = "Local\\CadariVizzo_InstanciaUnica"
TITULO_JANELA = "Cadari Vizzo — Visualizador de Projetos"  # igual a AppCDE.title()
TITULO_LOGIN = "Entrar — Cadari Vizzo"  # igual a DialogLogin._iniciar_vidro(...)

_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
_handle_mutex = None  # mantido vivo durante todo o processo


def adquirir(nome_mutex: str = NOME_MUTEX) -> bool:
    """Retorna True se esta é a única instância; False se já há outra aberta."""
    global _handle_mutex
    if sys.platform != "win32":
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    handle = kernel32.CreateMutexW(None, False, nome_mutex)
    erro = ctypes.get_last_error()
    if not handle:
        return True  # falha inesperada da API: não bloqueia o uso do app
    if erro == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False
    _handle_mutex = handle
    return True


def focar_instancia_existente(titulos=None) -> bool:
    """Tenta trazer para a frente uma janela VISÍVEL da instância aberta
    (a principal ou a de login). True se conseguiu.

    Atenção: durante o login a janela principal já existe com o título
    definitivo, porém escondida (withdraw). Focar uma janela invisível não
    mostra nada ao usuário — por isso só contam janelas visíveis; se não
    houver nenhuma, quem chama mostra o aviso."""
    if sys.platform != "win32":
        return False
    import ctypes

    user32 = ctypes.windll.user32
    for titulo in titulos or (TITULO_JANELA, TITULO_LOGIN):
        hwnd = user32.FindWindowW(None, titulo)
        if not hwnd or not user32.IsWindowVisible(hwnd):
            continue
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    return False


def avisar_ja_aberto() -> None:
    """Aviso nativo (sem criar janela Tk) de que o app já está aberto."""
    msg = ("O Cadari Vizzo já está aberto.\n\n"
           "Use a janela existente — não é possível abrir duas ao mesmo tempo.\n\n"
           "Se nenhuma janela aparecer, encerre \"CadariVizzo\" no Gerenciador "
           "de Tarefas (Ctrl+Shift+Esc) e abra de novo.")
    if sys.platform == "win32":
        import ctypes
        MB_ICONINFORMATION, MB_TOPMOST = 0x40, 0x40000
        ctypes.windll.user32.MessageBoxW(None, msg, "Cadari Vizzo", MB_ICONINFORMATION | MB_TOPMOST)
    else:
        print(msg, file=sys.stderr)


def garantir_instancia_unica() -> bool:
    """Atalho para o ponto de entrada. Se já houver outra instância, foca a
    janela dela (ou avisa, se ainda estiver na tela de login) e retorna False."""
    if adquirir():
        return True
    if not focar_instancia_existente():
        avisar_ja_aberto()
    return False
