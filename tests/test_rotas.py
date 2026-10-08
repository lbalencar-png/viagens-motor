import pytest
from conftest import fixture

from viagens_motor.resultado import FonteErro
from viagens_motor.rotas import matriz, rota


def test_rota_a_pe(cliente_com):
    cli, rot = cliente_com([("routing.openstreetmap.de", fixture("osrm_route.json"))])
    dados, fonte = rota(cli, (48.8443, 2.3730), (48.8606, 2.3376), "pe")
    assert dados == {"distancia_m": 3517, "duracao_min": 47}
    assert fonte == "OSRM da FOSSGIS (OpenStreetMap)"
    assert "/routed-foot/route/v1/driving/2.373,48.8443;2.3376,48.8606" in str(rot.chamadas[0].url)


def test_modo_invalido():
    with pytest.raises(ValueError, match="modo deve ser pe, bicicleta ou carro"):
        rota(None, (0, 0), (1, 1), "aviao")


def test_sem_rota_e_falha(cliente_com):
    cli, _ = cliente_com([("routing.openstreetmap.de", {"code": "NoRoute", "message": "Impossible route"})])
    with pytest.raises(FonteErro, match="sem rota"):
        rota(cli, (0, 0), (1, 1), "carro")


def test_matriz(cliente_com):
    cli, rot = cliente_com([("routing.openstreetmap.de", fixture("osrm_table.json"))])
    dados, _ = matriz(cli, [(48.84, 2.37), (48.86, 2.33), (48.85, 2.29)], "pe")
    assert dados["duracoes_s"][0][2] == 5340 and dados["distancias_m"][1][2] == 3700
    assert "/routed-foot/table/v1/driving/" in str(rot.chamadas[0].url)


def test_matriz_limites():
    with pytest.raises(ValueError, match="de 2 a 25 pontos"):
        matriz(None, [(0, 0)], "pe")


@pytest.mark.live
def test_live_gare_de_lyon_louvre():
    from viagens_motor.http import Cliente

    dados, _ = rota(Cliente(), (48.8443, 2.3730), (48.8606, 2.3376), "pe")
    assert 2000 <= dados["distancia_m"] <= 4000 and dados["duracao_min"] >= 25
