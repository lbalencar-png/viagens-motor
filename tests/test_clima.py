from datetime import date

import httpx
import pytest
from conftest import fixture

from viagens_motor.clima import clima


def test_previsao(cliente_com):
    cli, rot = cliente_com([("api.open-meteo.com", fixture("meteo_previsao.json"))])
    dados, fonte = clima(cli, -8.05, -34.9, date(2026, 10, 7), date(2026, 10, 8), hoje=date(2026, 10, 7))
    assert dados["tipo"] == "previsao"
    assert dados["dias"][1] == {"data": "2026-10-08", "max": 28.1, "min": 23.4, "chuva_mm": 2.7, "chuva_prob": 81,
                                "tipo": "previsao"}
    assert fonte == "Open-Meteo"


def _arquivo(req):
    ini = date.fromisoformat(req.url.params["start_date"])
    fim = date.fromisoformat(req.url.params["end_date"])
    n = (fim - ini).days + 1
    ano = ini.year
    datas = [date.fromordinal(ini.toordinal() + i).isoformat() for i in range(n)]
    return httpx.Response(200, json={"daily": {
        "time": datas,
        "temperature_2m_max": [10 + (ano % 10)] * n,
        "temperature_2m_min": [ano % 10] * n,
        "precipitation_sum": [2.0 if ano % 2 else 0.0] * n,
    }})


def test_media_10_anos(cliente_com):
    cli, rot = cliente_com([("archive-api.open-meteo.com", _arquivo)])
    dados, _ = clima(cli, 38.72, -9.14, date(2028, 5, 10), date(2028, 5, 12), hoje=date(2026, 10, 7))
    assert dados["tipo"] == "media_10_anos"
    assert dados["anos"] == list(range(2017, 2027))
    assert len(rot.chamadas) == 10
    d0 = dados["dias"][0]
    assert d0["data"] == "2028-05-10" and d0["max_media"] == 14.5 and d0["max_faixa"] == [10, 19]
    assert d0["min_media"] == 4.5 and d0["min_faixa"] == [0, 9]
    assert dados["dias_chuva_media"] == 1.5


def test_periodo_que_atravessa_o_ano_e_29_de_fevereiro(cliente_com):
    cli, _ = cliente_com([("archive-api.open-meteo.com", _arquivo)])
    dados, _ = clima(cli, 38.72, -9.14, date(2028, 12, 30), date(2029, 1, 2), hoje=date(2026, 10, 7))
    assert [d["data"] for d in dados["dias"]] == ["2028-12-30", "2028-12-31", "2029-01-01", "2029-01-02"]
    dados, _ = clima(cli, 38.72, -9.14, date(2028, 2, 28), date(2028, 3, 1), hoje=date(2026, 10, 7))
    assert len(dados["dias"]) == 3


def _previsao(req):
    ini = date.fromisoformat(req.url.params["start_date"])
    fim = date.fromisoformat(req.url.params["end_date"])
    n = (fim - ini).days + 1
    datas = [date.fromordinal(ini.toordinal() + i).isoformat() for i in range(n)]
    return httpx.Response(200, json={"daily": {
        "time": datas,
        "temperature_2m_max": [30.0] * n,
        "temperature_2m_min": [20.0] * n,
        "precipitation_sum": [0.0] * n,
        "precipitation_probability_max": [10] * n,
    }})


def test_periodo_que_cruza_o_horizonte(cliente_com):
    # hoje + 15 = 2026-10-22: 20, 21 e 22 vêm da previsão; 23 a 25 da média.
    # A regra do arquivo vem antes porque "archive-api.open-meteo.com" contém "api.open-meteo.com".
    cli, rot = cliente_com([("archive-api.open-meteo.com", _arquivo), ("api.open-meteo.com", _previsao)])
    dados, fonte = clima(cli, -23.5, -46.6, date(2026, 10, 20), date(2026, 10, 25), hoje=date(2026, 10, 7))
    assert dados["tipo"] == "misto"
    assert [d["data"] for d in dados["dias"]] == [
        "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"]
    assert [d["tipo"] for d in dados["dias"]] == ["previsao"] * 3 + ["media_10_anos"] * 3
    assert dados["dias"][0]["max"] == 30.0 and "max_media" not in dados["dias"][0]
    assert dados["dias"][3]["max_media"] is not None
    # fim em 25/10/2026: 2026 ainda não tem 6 dias de atraso do arquivo, então os 10 anos vão de 2016 a 2025
    assert dados["anos"] == list(range(2016, 2026))
    assert dados["dias_chuva_media"] == 1.5
    assert fonte == "Open-Meteo e Open-Meteo (histórico)"


def test_29_de_fevereiro_alinha_por_data(cliente_com):
    def por_data(req):
        ini = date.fromisoformat(req.url.params["start_date"])
        fim = date.fromisoformat(req.url.params["end_date"])
        n = (fim - ini).days + 1
        datas = [date.fromordinal(ini.toordinal() + i) for i in range(n)]
        return httpx.Response(200, json={"daily": {
            "time": [d.isoformat() for d in datas],
            "temperature_2m_max": [float(d.day) for d in datas],
            "temperature_2m_min": [0.0] * n,
            "precipitation_sum": [0.0] * n,
        }})

    cli, _ = cliente_com([("archive-api.open-meteo.com", por_data)])
    dados, _ = clima(cli, 38.72, -9.14, date(2028, 2, 28), date(2028, 3, 1), hoje=date(2026, 10, 7))
    dias = {d["data"]: d for d in dados["dias"]}
    assert dias["2028-03-01"]["max_media"] == 1.0
    assert dias["2028-02-28"]["max_media"] == 28.0
    # 8 anos sem 29/02 (cai no 28/02) e 2020 e 2024 com 29/02: (8 * 28 + 2 * 29) / 10
    assert dias["2028-02-29"]["max_media"] == 28.2


def test_periodo_invalido():
    with pytest.raises(ValueError, match="fim antes do início"):
        clima(None, 0, 0, date(2026, 10, 9), date(2026, 10, 8), hoje=date(2026, 10, 7))
    with pytest.raises(ValueError, match="período no passado"):
        clima(None, 0, 0, date(2026, 10, 1), date(2026, 10, 8), hoje=date(2026, 10, 7))


@pytest.mark.live
def test_live_lisboa_maio():
    from viagens_motor.http import Cliente

    dados, _ = clima(Cliente(), 38.72, -9.14, date(2028, 5, 10), date(2028, 5, 15))
    assert dados["tipo"] == "media_10_anos" and len(dados["dias"]) == 6
