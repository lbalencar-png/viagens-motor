"""Ordem dos lugares de um dia que minimiza o deslocamento (puro)."""

from __future__ import annotations

import itertools

INF = float("inf")
LIMITE_EXATO = 8


def _c(m, i: int, j: int) -> float:
    v = m[i][j]
    return INF if v is None else float(v)


def total(m, seq: list[int], voltar: bool) -> float:
    pts = [0, *seq] + ([0] if voltar else [])
    return sum(_c(m, pts[k], pts[k + 1]) for k in range(len(pts) - 1))


def ordenar(m, voltar: bool) -> list[int]:
    """Índice 0 é a partida e não aparece no resultado.

    Até LIMITE_EXATO lugares testa todas as ordens; acima, vizinho mais próximo
    seguido de melhoria 2-opt.
    """
    resto = list(range(1, len(m)))
    if not resto:
        return []
    if len(resto) <= LIMITE_EXATO:
        return list(min(itertools.permutations(resto), key=lambda s: total(m, list(s), voltar)))
    seq, atual, livres = [], 0, set(resto)
    while livres:
        prox = min(sorted(livres), key=lambda j: _c(m, atual, j))
        seq.append(prox)
        livres.remove(prox)
        atual = prox
    melhorou = True
    while melhorou:
        melhorou = False
        for i in range(len(seq) - 1):
            for j in range(i + 1, len(seq)):
                novo = seq[:i] + seq[i : j + 1][::-1] + seq[j + 1 :]
                if total(m, novo, voltar) < total(m, seq, voltar):
                    seq, melhorou = novo, True
    return seq
