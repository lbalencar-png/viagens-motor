from datetime import date

import pytest
from conftest import fixture

from viagens_motor.calendario import feriados, mudancas_horario
from viagens_motor.resultado import FonteErro


def test_feriados_no_periodo(cliente_com):
    cli, rot = cliente_com([("date.nager.at", fixture("nager_cz_2028.json"))])
    lista, fonte = feriados(cli, "cz", date(2028, 4, 12), date(2028, 4, 19))
    assert lista == [{"data": "2028-04-14", "nome": "Velký pátek", "nome_en": "Good Friday", "abrangencia": "nacional"}]
    assert fonte == "Nager.Date" and "/2028/CZ" in str(rot.chamadas[0].url)


def test_feriado_regional_com_regiao(cliente_com):
    cli, _ = cliente_com([("date.nager.at", fixture("nager_cz_2028.json"))])
    lista, _ = feriados(cli, "CZ", date(2028, 4, 12), date(2028, 4, 19), regiao="10")
    assert [f["data"] for f in lista] == ["2028-04-14", "2028-04-18"]
    assert lista[1]["abrangencia"] == "CZ-10"


def test_periodo_sem_feriado(cliente_com):
    cli, _ = cliente_com([("date.nager.at", fixture("nager_cz_2028.json"))])
    assert feriados(cli, "CZ", date(2028, 3, 13), date(2028, 3, 17))[0] == []


def test_pais_nao_atendido(cliente_com):
    cli, _ = cliente_com([("date.nager.at", (404, {}))])
    with pytest.raises(FonteErro, match="HTTP 404"):
        feriados(cli, "XX", date(2028, 1, 1), date(2028, 1, 2))


def test_mudanca_de_horario_europa_e_recife():
    assert mudancas_horario("Europe/Prague", date(2028, 3, 24), date(2028, 3, 29)) == [
        {"data": "2028-03-26", "de": "+01:00", "para": "+02:00"}
    ]
    assert mudancas_horario("America/Recife", date(2028, 1, 1), date(2028, 12, 31)) == []
