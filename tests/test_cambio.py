from datetime import date

import pytest
from conftest import fixture

from viagens_motor.cambio import converter, spread_efetivo, taxa_brl
from viagens_motor.config import Config
from viagens_motor.resultado import FonteErro

CFG = Config(
    iof={"cartao": 0.035, "especie": 0.035, "conta_global": 0.035},
    cartoes={
        "a": {"nome": "Cartão A", "spread": 0.0575, "spread_verificar": True, "iof_devolvido": True, "fonte_spread": "comunicado"},
        "b": {"nome": "Cartão B", "spread": 0.053, "spread_verificar": True, "fonte_spread": "ranking"},
        "c": {"nome": "Cartão C", "spread": 0.06, "ptax_dia_anterior": True},
    },
)
HOJE = date(2026, 10, 7)


def test_ptax_fechamento_mais_recente(cliente_com):
    cli, rot = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    dados, fonte, aviso = taxa_brl(cli, "eur", HOJE, hoje=HOJE)
    assert dados == {"moeda": "EUR", "taxa": 5.6, "data_taxa": "2026-10-07"}
    assert fonte == "PTAX do Banco Central" and aviso is None
    assert rot.chamadas[0].url.params["@moeda"] == "'EUR'"


def test_ptax_ignora_boletim_posterior_a_data(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    dados, _, _ = taxa_brl(cli, "EUR", date(2026, 10, 6), hoje=HOJE)
    assert dados["taxa"] == 5.85 and dados["data_taxa"] == "2026-10-06"


def test_moeda_fora_da_ptax_cruza_com_bce(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json")), ("api.frankfurter.dev", fixture("frankfurter.json"))])
    dados, fonte, aviso = taxa_brl(cli, "CZK", HOJE, hoje=HOJE)
    assert dados["taxa"] == 5.6 / 24.405 and dados["moeda"] == "CZK"
    assert fonte == "PTAX do Banco Central (EUR) e BCE via Frankfurter"
    assert "conversão cruzada" in aviso


def test_converter_huf_taxa_pequena_reproduz_valor(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json")), ("api.frankfurter.dev", fixture("frankfurter.json"))])
    dados, _, _ = converter(cli, CFG, "HUF", 1000, "cartao:b", HOJE, hoje=HOJE)
    assert f"{5.6 / 364.95:.6g}" in dados["conta"]
    assert dados["valor_brl"] == round(1000 * (5.6 / 364.95) * 1.053 * 1.035, 2)


def test_moeda_inexistente(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json")), ("api.frankfurter.dev", fixture("frankfurter.json"))])
    with pytest.raises(FonteErro, match="moeda XYZ sem cotação"):
        taxa_brl(cli, "XYZ", HOJE, hoje=HOJE)


def test_converter_cartao_a_sem_iof(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    dados, _, aviso = converter(cli, CFG, "EUR", 100, "cartao:a", HOJE, hoje=HOJE)
    assert dados["iof"] == 0.0 and dados["spread"] == 0.0575
    assert dados["valor_brl"] == round(100 * 5.6 * 1.0575, 2)
    assert "IOF de 3.5% devolvido em fatura" in aviso and "não confirmado" in aviso


def test_converter_cartao_b_com_iof(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    dados, _, _ = converter(cli, CFG, "EUR", 100, "cartao:b", HOJE, hoje=HOJE)
    assert dados["valor_brl"] == round(100 * 5.6 * 1.053 * 1.035, 2)
    assert dados["conta"].startswith("100 × 5.6000 × (1 + 5.30%) × (1 + 3.50%) = R$ ")


def test_converter_especie_avisa_spread(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    _, _, aviso = converter(cli, CFG, "EUR", 100, "especie", HOJE, hoje=HOJE)
    assert "spread de espécie não informado" in aviso


def test_spread_efetivo(cliente_com):
    cli, rot = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    dados, _ = spread_efetivo(cli, CFG, "c", date(2026, 10, 7), "EUR", 100, round(100 * 5.85 * 1.06, 2), hoje=HOJE)
    assert dados["taxa_referencia"] == 5.85 and dados["data_taxa"] == "2026-10-06"
    assert dados["spread"] == 0.06 and dados["spread_configurado"] == 0.06
    assert "valor em reais da fatura sem a linha de IOF" in dados["observacao"]


def test_spread_efetivo_rejeita_valor_zero(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    with pytest.raises(ValueError, match="valor_moeda deve ser maior que zero"):
        spread_efetivo(cli, CFG, "c", HOJE, "EUR", 0, 100, hoje=HOJE)


@pytest.mark.live
def test_live_eur_e_czk():
    from viagens_motor.http import Cliente

    cli = Cliente()
    eur, _, _ = taxa_brl(cli, "EUR", date.today())
    czk, _, _ = taxa_brl(cli, "CZK", date.today())
    assert 4 < eur["taxa"] < 9 and 0.1 < czk["taxa"] < 0.4


def test_converter_brl_sem_spread_nem_iof(cliente_com):
    cli, rot = cliente_com([])
    dados, fonte, aviso = converter(cli, CFG, "BRL", 250, "cartao:b", HOJE, hoje=HOJE)
    assert dados["valor_brl"] == 250 and dados["spread"] == 0.0 and dados["iof"] == 0.0
    assert aviso == "valor já em reais" and fonte == "sem conversão" and rot.chamadas == []


def test_data_futura_avisa_ultima_ptax(cliente_com):
    cli, _ = cliente_com([("olinda.bcb.gov.br", fixture("ptax_eur.json")), ("api.frankfurter.dev", fixture("frankfurter.json"))])
    dados, _, aviso = taxa_brl(cli, "EUR", date(2027, 1, 10), hoje=HOJE)
    assert dados["data_taxa"] == "2026-10-07" and aviso == "data futura: usada a última PTAX disponível (2026-10-07)"
    _, _, aviso = taxa_brl(cli, "CZK", date(2027, 1, 10), hoje=HOJE)
    assert aviso.startswith("data futura: usada a última PTAX disponível (2026-10-07); conversão cruzada")
    assert taxa_brl(cli, "EUR", HOJE, hoje=HOJE)[2] is None
