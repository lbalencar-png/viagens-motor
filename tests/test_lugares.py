import pytest
from conftest import fixture

from viagens_motor.lugares import buscar, coordenadas
from viagens_motor.resultado import FonteErro


def test_buscar_devolve_candidato(cliente_com):
    cli, rot = cliente_com([("photon.komoot.io", fixture("photon_louvre.json"))])
    cands, fonte = buscar(cli, "Louvre Paris", perto_de=(48.85, 2.35))
    assert cands[0] == {
        "nome": "Louvre",
        "endereco": "Rue de Rivoli, 75001, Paris, France",
        "lat": 48.8611473,
        "lon": 2.3380277,
        "tipo": "tourism:museum",
        "pais": "FR",
    }
    assert fonte == "Photon (OpenStreetMap)"
    assert rot.chamadas[0].url.params["lat"] == "48.85"


def test_buscar_sem_resultado_e_falha(cliente_com):
    cli, _ = cliente_com([("photon.komoot.io", fixture("photon_vazio.json"))])
    with pytest.raises(FonteErro, match="nenhum lugar encontrado para 'Xyzzy'"):
        buscar(cli, "Xyzzy")


def test_coordenadas_aceita_par_e_texto(cliente_com):
    cli, rot = cliente_com([("photon.komoot.io", fixture("photon_louvre.json"))])
    assert coordenadas(cli, (-8.05, -34.9)) == (-8.05, -34.9, "-8.05,-34.9")
    assert coordenadas(cli, " -8.05 , -34.9 ") == (-8.05, -34.9, "-8.05 , -34.9")
    assert rot.chamadas == []
    assert coordenadas(cli, "Louvre") == (48.8611473, 2.3380277, "Louvre")


def test_endereco_com_virgula_nao_e_coordenada(cliente_com):
    cli, rot = cliente_com([("photon.komoot.io", fixture("photon_louvre.json"))])
    coordenadas(cli, "Rua 7, 120")
    assert len(rot.chamadas) == 1


@pytest.mark.live
def test_live_gare_de_lyon():
    from viagens_motor.http import Cliente

    cands, _ = buscar(Cliente(), "Novotel Paris Gare de Lyon", limite=1)
    assert 48.83 < cands[0]["lat"] < 48.86 and 2.36 < cands[0]["lon"] < 2.39


def test_coordenadas_com_vies_escolhe_o_candidato_mais_proximo(cliente_com):
    import httpx

    def feat(nome, lat, lon):
        return {"geometry": {"coordinates": [lon, lat]}, "properties": {"name": nome}}

    corpo = {"features": [feat("Longe", 49.0, 2.3), feat("Perto", 48.861, 2.338), feat("Meio", 48.9, 2.3)]}
    cli, rot = cliente_com([("photon.komoot.io", lambda req: httpx.Response(200, json=corpo))])
    lat, lon, nome = coordenadas(cli, "Louvre", perto_de=(48.84, 2.37))
    assert nome == "Perto" and (lat, lon) == (48.861, 2.338)
    assert rot.chamadas[0].url.params["limit"] == "5"


def test_coordenadas_sem_vies_pega_o_primeiro_com_limite_1(cliente_com):
    cli, rot = cliente_com([("photon.komoot.io", fixture("photon_louvre.json"))])
    coordenadas(cli, "Louvre")
    assert rot.chamadas[0].url.params["limit"] == "1" and "lat" not in rot.chamadas[0].url.params


def test_localizar_avisa_quando_nao_e_o_primeiro(cliente_com):
    import httpx

    from viagens_motor.lugares import localizar

    def feat(nome, lat, lon):
        return {"geometry": {"coordinates": [lon, lat]}, "properties": {"name": nome}}

    corpo = {"features": [feat("Longe", 49.0, 2.3), feat("Perto", 48.861, 2.338)]}
    cli, _ = cliente_com([("photon.komoot.io", lambda req: httpx.Response(200, json=corpo))])
    assert localizar(cli, "X", perto_de=(48.84, 2.37))[3] == "Perto escolhido entre homônimos pelo mais próximo; confira o nome"
    assert localizar(cli, "X", perto_de=(49.0, 2.3))[3] is None
