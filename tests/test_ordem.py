from viagens_motor.ordem import ordenar, total

M = [
    [0, 10, 50, 40],
    [10, 0, 45, 35],
    [50, 45, 0, 5],
    [40, 35, 5, 0],
]


def test_ordem_minima_com_volta():
    from itertools import permutations

    seq = ordenar(M, voltar=True)
    assert total(M, seq, True) == min(total(M, list(p), True) for p in permutations([1, 2, 3]))


def test_ordem_sem_volta():
    assert ordenar(M, voltar=False) == [1, 3, 2]


def test_trecho_inalcancavel_nao_quebra():
    m = [[0, 1, None], [1, 0, 2], [None, 2, 0]]
    assert ordenar(m, voltar=False) == [1, 2]
    assert total(m, [2, 1], False) == float("inf")


def test_heuristica_para_10_lugares():
    import random

    random.seed(1)
    pts = [(random.random(), random.random()) for _ in range(11)]
    m = [[abs(a[0] - b[0]) + abs(a[1] - b[1]) for b in pts] for a in pts]
    seq = ordenar(m, voltar=True)
    assert sorted(seq) == list(range(1, 11))
    assert total(m, seq, True) <= total(m, list(range(1, 11)), True)
