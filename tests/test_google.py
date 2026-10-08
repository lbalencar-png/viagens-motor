import json
from datetime import datetime, timezone

import httpx
import pytest
from conftest import fixture

from viagens_motor.google import rota
from viagens_motor.resultado import FonteErro


def test_rota_transporte(cliente_com):
    def responder(req):
        corpo = json.loads(req.read())
        assert req.headers["X-Goog-Api-Key"] == "CHAVE"
        assert req.headers["X-Goog-FieldMask"] == "routes.distanceMeters,routes.duration"
        assert corpo["travelMode"] == "TRANSIT" and corpo["departureTime"] == "2028-03-14T06:00:00Z"
        assert corpo["origin"]["location"]["latLng"] == {"latitude": 50.08, "longitude": 14.43}
        return httpx.Response(200, json=fixture("google_route.json"))

    cli, _ = cliente_com([("routes.googleapis.com", responder)])
    dados, fonte = rota(cli, "CHAVE", (50.08, 14.43), (48.18, 16.37), "transporte", datetime(2028, 3, 14, 6, tzinfo=timezone.utc))
    assert dados == {"distancia_m": 3600, "duracao_min": 48} and fonte == "Google Maps (Routes API)"


def test_sem_rota(cliente_com):
    cli, _ = cliente_com([("routes.googleapis.com", {})])
    with pytest.raises(FonteErro, match="sem rota"):
        rota(cli, "CHAVE", (0, 0), (1, 1), "pe")


def test_rota_do_google_nao_fica_na_memoria(cliente_com):
    cli, rot = cliente_com([("routes.googleapis.com", fixture("google_route.json"))])
    rota(cli, "CHAVE", (0, 0), (1, 1), "pe")
    rota(cli, "CHAVE", (0, 0), (1, 1), "pe")
    assert len(rot.chamadas) == 2
