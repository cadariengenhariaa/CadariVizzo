"""Ponto de entrada de linha de comando para rodar a detecção de
interferências sem abrir a interface gráfica — útil para pipeline/CI ou
para automatizar relatórios periódicos."""
import argparse
import sys

import ifcopenshell

from clash.config_regras import carregar_regras
from clash.motor import rodar_clash


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Detecção de interferências (clash) entre disciplinas a partir de arquivos IFC."
    )
    parser.add_argument("ifcs", nargs="+", help="Um ou mais arquivos .ifc a analisar juntos (modelo de coordenação).")
    parser.add_argument("--regras", help="Caminho para um regras_clash.yaml alternativo.")
    parser.add_argument(
        "--nao-salvar", action="store_true",
        help="Não mescla com a revisão anterior nem grava db_clashes.json (só mostra o resumo).",
    )
    args = parser.parse_args(argv)

    regras = carregar_regras(args.regras)

    arquivos_ifc = {}
    for caminho in args.ifcs:
        try:
            arquivos_ifc[caminho] = ifcopenshell.open(caminho)
        except Exception as e:
            print(f"ERRO ao abrir {caminho}: {e}", file=sys.stderr)
            return 1

    def progresso(total):
        print(f"  ... {total} elementos processados", file=sys.stderr)

    resultado = rodar_clash(arquivos_ifc, regras, callback_progresso=progresso, persistir=not args.nao_salvar)
    _imprimir_resumo(resultado)
    return 0


def _imprimir_resumo(resultado):
    pre = resultado["pre_checagens"]
    print("=" * 70)
    print("PRÉ-CHECAGENS DE QUALIDADE")
    print("=" * 70)
    if pre.unidades_inconsistentes:
        print("⚠ ALERTA: arquivos com unidades de comprimento diferentes — escala aplicada:")
        for arquivo, escala in pre.escala_por_arquivo.items():
            print(f"    {arquivo}: fator {escala}")
    if pre.alerta_desalinhamento:
        print(f"⚠ ALERTA: modelos possivelmente desalinhados — distância entre centros: "
              f"{pre.distancia_entre_centros_m:.1f} m")
    if pre.guids_duplicados:
        print(f"⚠ {len(pre.guids_duplicados)} GUID(s) duplicado(s)")
    if pre.elementos_sem_geometria:
        print(f"⚠ {len(pre.elementos_sem_geometria)} elemento(s) sem geometria")
    if pre.elementos_sem_nivel:
        print(f"⚠ {len(pre.elementos_sem_nivel)} elemento(s) sem pavimento associado")
    if pre.geometria_invalida:
        print(f"⚠ {len(pre.geometria_invalida)} elemento(s) com geometria inválida")
    if pre.niveis_sem_correspondencia:
        print("⚠ ALERTA: nomenclatura de pavimento sem nenhuma correspondência entre arquivos")
    if not pre.tem_alertas_bloqueantes():
        print("Nenhum alerta bloqueante.")

    print()
    print("=" * 70)
    print("INTERFERÊNCIAS")
    print("=" * 70)
    print(f"{resultado['n_elementos']} elementos, {resultado['n_pares_candidatos']} pares candidatos, "
          f"{len(resultado['clashes'])} interferência(s) em {resultado['tempo_execucao_s']:.2f}s")
    por_severidade = {}
    for clash in resultado["clashes"]:
        por_severidade[clash["severidade"]] = por_severidade.get(clash["severidade"], 0) + 1
    for severidade, quantidade in sorted(por_severidade.items()):
        print(f"  {severidade}: {quantidade}")


if __name__ == "__main__":
    sys.exit(main())
