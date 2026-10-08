"""Linha de comando: viagens-motor <ferramenta> [argumentos]; imprime JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tomllib

from .ferramentas import criar_motor
from .resultado import falha

ERROS_DE_PARTIDA = (OSError, ValueError, tomllib.TOMLDecodeError, sqlite3.Error)  # ValueError inclui JSONDecodeError


def _imprimir(r: dict) -> int:
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="viagens-motor")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("lugar"); s.add_argument("texto"); s.add_argument("--perto-de")
    s = sub.add_parser("rota"); s.add_argument("origem"); s.add_argument("destino"); s.add_argument("--modo", default="pe"); s.add_argument("--quando")
    s = sub.add_parser("distancias"); s.add_argument("pontos", nargs="+"); s.add_argument("--modo", default="pe")
    s = sub.add_parser("ordenar-dia"); s.add_argument("partida"); s.add_argument("lugares", nargs="+"); s.add_argument("--sem-volta", action="store_true"); s.add_argument("--modo", default="pe")
    s = sub.add_parser("clima"); s.add_argument("lugar"); s.add_argument("inicio"); s.add_argument("fim")
    s = sub.add_parser("cambio"); s.add_argument("moeda"); s.add_argument("--valor", type=float, default=1.0); s.add_argument("--data"); s.add_argument("--meio")
    s = sub.add_parser("calendario"); s.add_argument("pais"); s.add_argument("inicio"); s.add_argument("fim"); s.add_argument("--regiao"); s.add_argument("--lugar")
    s = sub.add_parser("custos"); s.add_argument("arquivo_json"); s.add_argument("--viajantes", type=int); s.add_argument("--data")
    s = sub.add_parser("spread-da-fatura"); s.add_argument("cartao"); s.add_argument("data_compra"); s.add_argument("moeda"); s.add_argument("valor_moeda", type=float); s.add_argument("valor_reais", type=float)
    a = p.parse_args(argv)
    try:
        m = criar_motor()
    except ERROS_DE_PARTIDA as e:
        return _imprimir(falha("viagens-motor", f"configuração inválida: {e}"))
    if a.cmd == "lugar":
        r = m.lugar(a.texto, a.perto_de)
    elif a.cmd == "rota":
        r = m.rota(a.origem, a.destino, a.modo, a.quando)
    elif a.cmd == "distancias":
        r = m.distancias(a.pontos, a.modo)
    elif a.cmd == "ordenar-dia":
        r = m.ordenar_dia(a.partida, a.lugares, not a.sem_volta, a.modo)
    elif a.cmd == "clima":
        r = m.clima(a.lugar, a.inicio, a.fim)
    elif a.cmd == "cambio":
        r = m.cambio(a.moeda, a.valor, a.data, a.meio)
    elif a.cmd == "calendario":
        r = m.calendario(a.pais, a.inicio, a.fim, a.regiao, a.lugar)
    elif a.cmd == "custos":
        try:
            with open(a.arquivo_json, encoding="utf-8") as f:
                itens = json.load(f)
        except ERROS_DE_PARTIDA as e:
            return _imprimir(falha("viagens-motor", f"arquivo de custos ilegível: {e}"))
        r = m.custos(itens, a.viajantes, a.data)
    else:
        r = m.spread_da_fatura(a.cartao, a.data_compra, a.moeda, a.valor_moeda, a.valor_reais)
    return _imprimir(r)


if __name__ == "__main__":
    sys.exit(main())
