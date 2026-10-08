import pytest

from viagens_motor.custos import somar, validar


def cotar_fixo(item, valor):
    taxas = {"BRL": 1.0, "EUR": 6.0, "JPY": 0.015}
    if item["moeda"] == "XXX":
        raise ValueError("sem cotação")
    return round(valor * taxas[item["moeda"]], 2), f"{item['moeda']} a {taxas[item['moeda']]}"


ITENS = [
    {"id": "v1", "categoria": "voo", "descricao": "Lisboa-Faro", "valor": 150, "moeda": "EUR", "por_pessoa": True, "pessoas": 3, "situacao": "previsto", "meio": "cartao:a"},
    {"id": "h1", "categoria": "hotel", "descricao": "Hotel em Lisboa", "valor": 100000, "moeda": "JPY", "quantidade": 4, "situacao": "reservado", "meio": "cartao:a"},
    {"id": "s1", "categoria": "seguro", "descricao": "seguro", "valor": 500, "moeda": "BRL", "situacao": "pago", "meio": "cartao:b"},
    {"id": "p1", "categoria": "voo", "descricao": "voo de ida e volta", "valor": 0, "moeda": "BRL", "situacao": "pago", "meio": "pontos:programa_x", "pontos": 120000},
]


def test_somar():
    r = somar(ITENS, cotar_fixo, viajantes=3)
    assert r["total_brl"] == 2700 + 6000 + 500
    assert r["por_categoria"] == {"voo": 2700.0, "hotel": 6000.0, "seguro": 500.0}
    assert r["por_situacao"] == {"previsto": 2700.0, "reservado": 6000.0, "pago": 500.0}
    assert r["por_pessoa"] == round(9200 / 3, 2)
    assert r["pontos"] == {"programa_x": 120000}
    assert r["itens"][0] == {"id": "v1", "valor_brl": 2700.0, "nota": "EUR a 6.0"}


def test_validar():
    with pytest.raises(ValueError, match="item x: categoria 'barco' inválida"):
        validar({"id": "x", "categoria": "barco", "valor": 1, "moeda": "BRL", "situacao": "pago", "meio": "especie"})
    with pytest.raises(ValueError, match="item y: situacao 'talvez' inválida"):
        validar({"id": "y", "categoria": "voo", "valor": 1, "moeda": "BRL", "situacao": "talvez", "meio": "especie"})
    with pytest.raises(ValueError, match="item z: pontos ausentes"):
        validar({"id": "z", "categoria": "voo", "valor": 0, "moeda": "BRL", "situacao": "pago", "meio": "pontos:programa_x"})


def test_falha_de_cotacao_derruba_o_total():
    itens = ITENS + [{"id": "e9", "categoria": "outros", "descricao": "?", "valor": 1, "moeda": "XXX", "situacao": "previsto", "meio": "especie"}]
    with pytest.raises(ValueError, match="item e9: cotação falhou: sem cotação"):
        somar(itens, cotar_fixo)


def test_item_sem_id_e_rejeitado():
    item = {"categoria": "hotel", "valor": 1, "moeda": "BRL", "situacao": "previsto"}
    with pytest.raises(ValueError, match="id ausente"):
        validar(item)
    with pytest.raises(ValueError, match="itens deve ser uma lista"):
        somar({"a": 1}, cotar_fixo)
    with pytest.raises(ValueError, match="item inválido"):
        validar("texto")


def _item(**extra):
    base = {"id": "q", "categoria": "hotel", "valor": 1, "moeda": "BRL", "situacao": "previsto", "meio": "especie"}
    return {**base, **extra}


def test_quantidade_deve_ser_numero_positivo():
    for ruim in (0, -1, "2", True, None):
        with pytest.raises(ValueError, match="item q: quantidade deve ser um número maior que zero"):
            validar(_item(quantidade=ruim))
    validar(_item(quantidade=2.5))
    validar(_item())  # padrão 1


def test_por_pessoa_exige_pessoas():
    for ruim in ({}, {"pessoas": 0}, {"pessoas": "3"}, {"pessoas": 0.5}):
        with pytest.raises(ValueError, match="item q: com por_pessoa, pessoas é obrigatório"):
            validar(_item(por_pessoa=True, **ruim))
    validar(_item(por_pessoa=True, pessoas=2))


def test_moeda_estrangeira_sem_meio():
    item = _item(moeda="eur")
    del item["meio"]
    with pytest.raises(ValueError, match="item q: meio ausente para moeda EUR"):
        validar(item)
    sem_meio_em_reais = _item()
    del sem_meio_em_reais["meio"]
    validar(sem_meio_em_reais)
