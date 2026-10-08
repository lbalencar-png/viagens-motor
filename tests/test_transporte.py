from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import fixture

from viagens_motor.resultado import FonteErro
from viagens_motor.transporte import plano

PRAGA = ZoneInfo("Europe/Prague")
VAZIO = {"itineraries": []}


def test_itinerario_direto(cliente_com):
    cli, rot = cliente_com([("api.transitous.org", fixture("transitous_praga_viena.json"))])
    dados, fonte, aviso = plano(cli, (50.08, 14.43), (48.18, 16.37), datetime(2026, 10, 14, 7, 0, tzinfo=PRAGA), hoje=date(2026, 10, 7))
    it = dados["itinerarios"][0]
    assert (it["duracao_min"], it["trocas"]) == (260, 0)
    assert it["pernas"][1] == {
        "modo": "HIGHSPEED_RAIL", "linha": "RJ 55", "empresa": "České dráhy", "de": "Praha hl.n.",
        "para": "Wien Hauptbahnhof", "partida": "2026-10-14T06:09:00Z", "chegada": "2026-10-14T10:29:00Z", "duracao_min": 260,
    }
    assert aviso is None and fonte == "Transitous (transitous.org/sources)"
    assert rot.chamadas[0].url.params["time"] == "2026-10-14T05:00:00Z"


def test_data_distante_usa_referencia(cliente_com):
    def responder(req):
        import httpx

        quando = req.url.params["time"]
        corpo = fixture("transitous_praga_viena.json") if quando.startswith("2026-10-20") else VAZIO
        return httpx.Response(200, json=corpo)

    cli, rot = cliente_com([("api.transitous.org", responder)], cache=False)
    # 14/03/2028 é terça; hoje 07/10/2026 é quarta: próximas terças 13/10 (vazio) e 20/10 (com trem)
    dados, _, aviso = plano(cli, (50.08, 14.43), (48.18, 16.37), datetime(2028, 3, 14, 7, 0, tzinfo=PRAGA), hoje=date(2026, 10, 7))
    assert dados["data_referencia"] == "2026-10-20"
    assert aviso == "horário de referência de 20/10/2026; conferir quando sair o horário da data da viagem"
    assert [c.url.params["time"][:10] for c in rot.chamadas] == ["2028-03-14", "2026-10-13", "2026-10-20"]


def test_data_proxima_vazia_e_falha(cliente_com):
    cli, _ = cliente_com([("api.transitous.org", VAZIO)])
    with pytest.raises(FonteErro, match="nenhum itinerário encontrado"):
        plano(cli, (0, 0), (1, 1), datetime(2026, 10, 9, 7, tzinfo=PRAGA), hoje=date(2026, 10, 7))


def test_referencia_sem_resultado_e_falha(cliente_com):
    cli, rot = cliente_com([("api.transitous.org", VAZIO)], cache=False)
    with pytest.raises(FonteErro, match="nem nas 4 semanas de referência"):
        plano(cli, (0, 0), (1, 1), datetime(2028, 3, 14, 7, tzinfo=PRAGA), hoje=date(2026, 10, 7))
    assert len(rot.chamadas) == 5


@pytest.mark.live
def test_live_praga_viena_proxima_semana():
    from datetime import timedelta

    from viagens_motor.http import Cliente

    dia = date.today() + timedelta(days=7)
    dados, _, _ = plano(Cliente(), (50.0833, 14.4353), (48.1850, 16.3760), datetime(dia.year, dia.month, dia.day, 7, tzinfo=PRAGA))
    assert dados["itinerarios"]


JANELA = {"error": "query time 2029-03-13 06:00 is outside of loaded timetable window [2026-09-06 00:00, 2027-10-07 00:00["}


def test_400_de_janela_leva_ao_caminho_de_referencia(cliente_com):
    import httpx

    def responder(req):
        if req.url.params["time"].startswith("2029"):
            return httpx.Response(400, json=JANELA)
        return httpx.Response(200, json=fixture("transitous_praga_viena.json"))

    cli, _ = cliente_com([("api.transitous.org", responder)], cache=False)
    dados, _, aviso = plano(cli, (50.08, 14.43), (48.18, 16.37), datetime(2029, 3, 13, 7, 0, tzinfo=PRAGA), hoje=date(2026, 10, 7))
    assert dados["data_referencia"] == "2026-10-13" and "horário de referência" in aviso


def test_400_de_janela_em_dia_de_referencia_continua_o_laco(cliente_com):
    import httpx

    def responder(req):
        if req.url.params["time"].startswith(("2029", "2026-10-13")):
            return httpx.Response(400, json=JANELA)
        return httpx.Response(200, json=fixture("transitous_praga_viena.json"))

    cli, _ = cliente_com([("api.transitous.org", responder)], cache=False)
    dados, _, _ = plano(cli, (50.08, 14.43), (48.18, 16.37), datetime(2029, 3, 13, 7, 0, tzinfo=PRAGA), hoje=date(2026, 10, 7))
    assert dados["data_referencia"] == "2026-10-20"


def test_400_de_janela_em_data_proxima_e_falha(cliente_com):
    import httpx

    cli, _ = cliente_com([("api.transitous.org", lambda req: httpx.Response(400, json=JANELA))], cache=False)
    with pytest.raises(FonteErro, match="timetable"):
        plano(cli, (0, 0), (1, 1), datetime(2026, 10, 9, 7, tzinfo=PRAGA), hoje=date(2026, 10, 7))


def test_outro_erro_da_fonte_propaga(cliente_com):
    import httpx

    cli, _ = cliente_com([("api.transitous.org", lambda req: httpx.Response(400, json={"error": "bad coordinates"}))], cache=False)
    with pytest.raises(FonteErro, match="bad coordinates"):
        plano(cli, (0, 0), (1, 1), datetime(2029, 3, 13, 7, tzinfo=PRAGA), hoje=date(2026, 10, 7))
