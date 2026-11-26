"""Testes de auth/painel_usuarios.py: exclusão de usuário e o diálogo de
transferência de problemas (filtros por projeto/tipo/status/id, seleção
manual de quais problemas transferir, descrição do item em foco) —
isolado, nunca toca no banco de produção nem em issues de verdade."""
import os
import sys
import tempfile
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

config.DB_DIR = tempfile.mkdtemp(prefix="teste_cadari_painel_usuarios_")

# nenhum teste aqui depende de um usuário real clicando — substitui
# wait_window por um no-op para a construção dos diálogos não travar
# (mesma técnica já usada em test_auth_dialogs.py).
tk.Toplevel.wait_window = lambda self, *a, **k: None

from auth.painel_usuarios import _DialogTransferirProblemas


def _janela_raiz():
    raiz = tk.Tk()
    raiz.withdraw()
    return raiz


def _usuarios_exemplo():
    return [
        {"nome_usuario": "fulano", "nome": "Fulano", "ativo": True},
        {"nome_usuario": "ciclano", "nome": "Ciclano", "ativo": True},
    ]


def _issue(**kwargs):
    base = {
        "id": 1, "titulo": "Novo", "obra": "CA-1000", "tipo": "Incompatibilidade",
        "status": "Novo", "atribuido_para": "Fulano", "desc": "Descrição padrão de teste",
    }
    base.update(kwargs)
    return base


def test_trocar_origem_popula_filtros_e_lista_so_as_issues_daquele_usuario():
    raiz = _janela_raiz()
    issues = [
        _issue(id=1, atribuido_para="Fulano", obra="CA-1000", tipo="Dúvida"),
        _issue(id=2, atribuido_para="Fulano", obra="CA-2000", tipo="Erro"),
        _issue(id=3, atribuido_para="Ciclano", obra="CA-3000", tipo="Dúvida"),
    ]
    dialogo = _DialogTransferirProblemas(raiz, _usuarios_exemplo(), issues)

    dialogo.cb_origem.set("Fulano")
    dialogo._ao_trocar_origem()

    ids_na_lista = {int(iid) for iid in dialogo.tree.get_children()}
    assert ids_na_lista == {1, 2}  # só as do Fulano, não a do Ciclano
    assert set(dialogo.cb_filtro_obra["values"]) == {"— Todos —", "CA-1000", "CA-2000"}
    assert set(dialogo.cb_filtro_tipo["values"]) == {"— Todos —", "Dúvida", "Erro"}
    raiz.destroy()
    print("OK trocar \"De\" popula os filtros de projeto/tipo e lista só as issues daquele usuário")


def test_filtro_por_projeto_tipo_status_e_id_restringe_a_lista():
    raiz = _janela_raiz()
    issues = [
        _issue(id=1, atribuido_para="Fulano", obra="CA-1000", tipo="Dúvida", status="Novo"),
        _issue(id=2, atribuido_para="Fulano", obra="CA-1000", tipo="Erro", status="Reaberto"),
        _issue(id=12, atribuido_para="Fulano", obra="CA-2000", tipo="Dúvida", status="Fechado"),
    ]
    dialogo = _DialogTransferirProblemas(raiz, _usuarios_exemplo(), issues)
    dialogo.cb_origem.set("Fulano")
    dialogo._ao_trocar_origem()

    dialogo.cb_filtro_obra.set("CA-1000")
    dialogo._atualizar_lista()
    assert {int(i) for i in dialogo.tree.get_children()} == {1, 2}

    dialogo.cb_filtro_status.set("Reaberto")
    dialogo._atualizar_lista()
    assert {int(i) for i in dialogo.tree.get_children()} == {2}

    dialogo.cb_filtro_obra.set("— Todos —")
    dialogo.cb_filtro_status.set("— Todos —")
    dialogo.ent_filtro_id.insert(0, "12")
    dialogo._atualizar_lista()
    assert {int(i) for i in dialogo.tree.get_children()} == {12}
    raiz.destroy()
    print("OK filtros de projeto/status/id restringem a lista corretamente")


def test_selecionar_todos_e_limpar_selecao():
    raiz = _janela_raiz()
    issues = [_issue(id=1), _issue(id=2), _issue(id=3)]
    dialogo = _DialogTransferirProblemas(raiz, _usuarios_exemplo(), issues)
    dialogo.cb_origem.set("Fulano")
    dialogo._ao_trocar_origem()

    dialogo._selecionar_todos()
    assert len(dialogo.tree.selection()) == 3

    dialogo._limpar_selecao()
    assert len(dialogo.tree.selection()) == 0
    raiz.destroy()
    print("OK \"Selecionar todos (filtrados)\" e \"Limpar seleção\" funcionam")


def test_selecionar_linha_mostra_descricao_do_item_em_foco():
    raiz = _janela_raiz()
    issues = [_issue(id=1, desc="Interferência entre viga e duto")]
    dialogo = _DialogTransferirProblemas(raiz, _usuarios_exemplo(), issues)
    dialogo.cb_origem.set("Fulano")
    dialogo._ao_trocar_origem()

    dialogo.tree.selection_set("1")
    dialogo._ao_selecionar_na_lista()
    assert dialogo.txt_descricao.get("1.0", tk.END).strip() == "Interferência entre viga e duto"
    raiz.destroy()
    print("OK selecionar uma linha mostra a descrição do item em foco")


def test_confirmar_exige_origem_destino_diferentes_e_pelo_menos_um_selecionado():
    raiz = _janela_raiz()
    issues = [_issue(id=1)]
    dialogo = _DialogTransferirProblemas(raiz, _usuarios_exemplo(), issues)

    dialogo._confirmar()  # nem origem nem destino escolhidos
    assert dialogo.confirmado is False
    assert "Selecione os dois usuários" in dialogo.lbl_erro.cget("text")

    dialogo.cb_origem.set("Fulano")
    dialogo.cb_destino.set("Fulano")
    dialogo._confirmar()
    assert dialogo.confirmado is False
    assert "diferentes" in dialogo.lbl_erro.cget("text")

    dialogo.cb_destino.set("Ciclano")
    dialogo._ao_trocar_origem()
    dialogo._confirmar()  # nada selecionado na lista ainda
    assert dialogo.confirmado is False
    assert "Selecione ao menos um problema" in dialogo.lbl_erro.cget("text")
    raiz.destroy()
    print("OK _confirmar valida usuários diferentes e ao menos um problema selecionado")


def test_confirmar_com_selecao_valida_preenche_resultado():
    raiz = _janela_raiz()
    issues = [
        _issue(id=1, atribuido_para="Fulano"),
        _issue(id=2, atribuido_para="Fulano"),
    ]
    dialogo = _DialogTransferirProblemas(raiz, _usuarios_exemplo(), issues)
    dialogo.cb_origem.set("Fulano")
    dialogo._ao_trocar_origem()
    dialogo.cb_destino.set("Ciclano")
    dialogo.tree.selection_set("1")  # transfere só a issue 1, não a 2

    dialogo._confirmar()

    assert dialogo.confirmado is True
    assert dialogo.destino == "Ciclano"
    assert dialogo.ids_selecionados == [1]
    print("OK confirmar com seleção válida preenche confirmado/destino/ids_selecionados")


if __name__ == "__main__":
    for nome, funcao in list(globals().items()):
        if nome.startswith("test_") and callable(funcao):
            funcao()
    print("TODOS OS TESTES DO PAINEL DE USUÁRIOS PASSARAM")


def test_ordem_alfabetica_ignora_acentos_e_maiusculas():
    from auth.painel_usuarios import PainelUsuarios
    usuarios = [{"nome_usuario": n, "nome": n} for n in ("bruno", "Ângela", "carla", "Ana")]
    nomes = [u["nome"] for u in sorted(usuarios, key=PainelUsuarios._chave_nome)]
    assert nomes == ["Ana", "Ângela", "bruno", "carla"]
