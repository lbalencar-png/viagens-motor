from datetime import date

import httpx
from conftest import Roteador, fixture

from viagens_motor.cache import Cache
from viagens_motor.config import Config
from viagens_motor.ferramentas import Motor
from viagens_motor.http import Cliente

CFG = Config(iof={"cartao": 0.035, "especie": 0.035, "conta_global": 0.035},
             cartoes={"a": {"nome": "Cartão A", "spread": 0.0575, "iof_devolvido": True}})


def motor(tmp_path, regras, cfg=CFG):
    rot = Roteador(regras)
    cli = Cliente(Cache(tmp_path / "c.sqlite"), transport=httpx.MockTransport(rot), dormir=lambda s: None)
    return Motor(cfg, cli, hoje=lambda: date(2026, 10, 7)), rot


def test_lugar_ok(tmp_path):
    m, _ = motor(tmp_path, [("photon.komoot.io", fixture("photon_louvre.json"))])
    r = m.lugar("Louvre")
    assert r["ok"] and r["candidatos"][0]["nome"] == "Louvre" and r["fonte"].startswith("Photon")


def test_falha_de_fonte_vira_resposta_sem_numero(tmp_path):
    m, _ = motor(tmp_path, [("photon.komoot.io", (500, {}))])
    r = m.lugar("Louvre")
    assert r["ok"] is False and r["fonte"] == "Photon (OpenStreetMap)" and "HTTP 500" in r["erro"]


def test_rota_a_pe_por_coordenadas(tmp_path):
    m, _ = motor(tmp_path, [("routing.openstreetmap.de", fixture("osrm_route.json"))])
    r = m.rota("48.8443,2.3730", "48.8606,2.3376", "pe")
    assert r["ok"] and r["distancia_m"] == 3517 and r["duracao_min"] == 47


def test_rota_transporte_cai_para_google_com_chave(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "CHAVE")
    m, _ = motor(tmp_path, [("api.transitous.org", (500, {})), ("routes.googleapis.com", fixture("google_route.json"))])
    r = m.rota("50.08,14.43", "48.18,16.37", "transporte", quando="2026-10-14T07:00")
    assert r["ok"] and r["fonte"] == "Google Maps (Routes API)" and "Transitous falhou" in r["aviso"]


def test_rota_transporte_sem_google_e_falha(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    m, _ = motor(tmp_path, [("api.transitous.org", (500, {}))])
    r = m.rota("50.08,14.43", "48.18,16.37", "transporte", quando="2026-10-14T07:00")
    assert r["ok"] is False and "Transitous" in r["fonte"]


def test_ordenar_dia(tmp_path):
    m, _ = motor(tmp_path, [("routing.openstreetmap.de", fixture("osrm_table.json"))])
    r = m.ordenar_dia("48.84,2.37", ["48.86,2.33", "48.85,2.29"], voltar=True)
    assert r["ok"] and r["total_min"] <= r["total_ordem_dada_min"]
    assert [p["de"] for p in r["pernas"]][0] == "48.84,2.37"


def test_ordenar_dia_com_trecho_inalcancavel(tmp_path):
    tabela = {"code": "Ok", "durations": [[0, 60, None], [60, 0, 120], [None, 120, 0]], "distances": None}
    m, _ = motor(tmp_path, [("routing.openstreetmap.de", tabela)])
    r = m.ordenar_dia("1,1", ["2,2", "3,3"], voltar=False)
    assert r["ok"] and r["ordem"] == ["2,2", "3,3"]
    tabela2 = {"code": "Ok", "durations": [[0, None, None], [None, 0, 1], [None, 1, 0]], "distances": None}
    m2, _ = motor(tmp_path / "b", [("routing.openstreetmap.de", tabela2)])
    r2 = m2.ordenar_dia("1,1", ["2,2", "3,3"], voltar=False)
    assert r2["ok"] and "inalcançável" in r2["aviso"]


def test_cambio_e_custos(tmp_path):
    m, _ = motor(tmp_path, [("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    r = m.cambio("EUR", 100, meio="cartao:a")
    assert r["ok"] and r["valor_brl"] == round(100 * 5.6 * 1.0575, 2) and "IOF" in r["aviso"]
    c = m.custos([{"id": "a", "categoria": "hotel", "descricao": "x", "valor": 100, "moeda": "EUR", "situacao": "previsto", "meio": "cartao:a"}], viajantes=1)
    assert c["ok"] and c["total_brl"] == round(100 * 5.6 * 1.0575, 2)


def test_custos_com_item_que_falha(tmp_path):
    m, _ = motor(tmp_path, [("olinda.bcb.gov.br", fixture("ptax_eur.json"))])
    c = m.custos([{"id": "q", "categoria": "hotel", "descricao": "x", "valor": 1, "moeda": "EUR", "situacao": "previsto", "meio": "cartao:nubank"}])
    assert c["ok"] is False and "item q" in c["erro"]


def test_calendario_com_lugar(tmp_path):
    m, _ = motor(tmp_path, [("date.nager.at", fixture("nager_cz_2028.json"))])
    r = m.calendario("CZ", "2028-03-24", "2028-04-15", lugar="50.08,14.43")
    assert r["ok"] and r["feriados"][0]["data"] == "2028-04-14"
    assert r["mudancas_horario"] == [{"data": "2028-03-26", "de": "+01:00", "para": "+02:00"}] and r["fuso"] == "Europe/Prague"


def test_data_invalida(tmp_path):
    m, _ = motor(tmp_path, [])
    r = m.clima("1,1", "2028-02-30", "2028-03-01")
    assert r["ok"] is False and "data inválida" in r["erro"]


def test_custos_item_sem_id_vira_falha(tmp_path):
    m, _ = motor(tmp_path, [])
    c = m.custos([{"categoria": "hotel", "descricao": "x", "valor": 1, "moeda": "BRL", "situacao": "previsto"}])
    assert c["ok"] is False and "id ausente" in c["erro"]


def test_formato_inesperado_da_fonte_vira_falha(tmp_path):
    m, _ = motor(tmp_path, [("date.nager.at", {"x": 1})])
    r = m.calendario("CZ", "2028-03-24", "2028-03-29")
    assert r["ok"] is False and "resposta inesperada" in r["erro"]


def _photon_com_vies(request):
    p = dict(request.url.params)
    longe = {"type": "FeatureCollection", "features": [{"geometry": {"coordinates": [-9.1, 38.7]}, "properties": {"name": "Longe"}}]}
    perto = {"type": "FeatureCollection", "features": [{"geometry": {"coordinates": [2.33, 48.86]}, "properties": {"name": "Perto"}}]}
    return httpx.Response(200, json=perto if "lat" in p else longe)


def test_ordenar_dia_usa_vies_do_primeiro_ponto(tmp_path):
    tabela = {"code": "Ok", "durations": [[0, 60, 60], [60, 0, 60], [60, 60, 0]], "distances": None}
    m, rot = motor(tmp_path, [("photon.komoot.io", _photon_com_vies), ("routing.openstreetmap.de", tabela)])
    r = m.ordenar_dia("48.84,2.37", ["Louvre", "Torre Eiffel"], voltar=False)
    fotos = [c for c in rot.chamadas if "photon" in str(c.url)]
    assert len(fotos) == 2
    for c in fotos:
        assert c.url.params["lat"] == "48.84" and c.url.params["lon"] == "2.37"
    assert r["ok"] and not r.get("aviso") and r["ordem"][0] == "Perto"


def test_primeiro_ponto_por_nome_vai_sem_vies(tmp_path):
    tabela = {"code": "Ok", "durations": [[0, 60], [60, 0]], "distances": None}
    m, rot = motor(tmp_path, [("photon.komoot.io", _photon_com_vies), ("routing.openstreetmap.de", tabela)])
    m.ordenar_dia("Hotel", ["48.86,2.33"], voltar=False)
    foto = [c for c in rot.chamadas if "photon" in str(c.url)]
    assert len(foto) == 1 and "lat" not in foto[0].url.params


def test_rota_destino_com_vies_da_origem(tmp_path):
    m, rot = motor(tmp_path, [("photon.komoot.io", _photon_com_vies), ("routing.openstreetmap.de", fixture("osrm_route.json"))])
    m.rota("48.84,2.37", "Louvre", "pe")
    foto = [c for c in rot.chamadas if "photon" in str(c.url)]
    assert foto[0].url.params["lat"] == "48.84"


def test_ordenar_dia_avisa_ponto_distante(tmp_path):
    tabela = {"code": "Ok", "durations": [[0, 60, 60], [60, 0, 60], [60, 60, 0]], "distances": None}
    m, _ = motor(tmp_path, [("routing.openstreetmap.de", tabela)])
    r = m.ordenar_dia("48.8,2.3", ["38.7,-9.1", "48.85,2.29"], voltar=False)
    assert r["ok"] and "ficou a" in r["aviso"] and "confira o nome" in r["aviso"] and "38.7,-9.1" in r["aviso"]


def test_distancias_aviso_limite_maior_para_carro(tmp_path):
    tabela = {"code": "Ok", "durations": [[0, 60], [60, 0]], "distances": [[0, 100], [100, 0]]}
    m, _ = motor(tmp_path, [("routing.openstreetmap.de", tabela)])
    assert "confira o nome" in m.distancias(["48.8,2.3", "50.8,2.3"], "pe")["aviso"]  # ~222 km
    assert not m.distancias(["48.8,2.3", "50.8,2.3"], "carro").get("aviso")


def _photon_homonimos(request):
    """O Photon devolve a cidade primeiro; o bairro homônimo é o mais próximo da origem."""
    def feat(nome, lat, lon):
        return {"geometry": {"coordinates": [lon, lat]}, "properties": {"name": nome}}

    return httpx.Response(200, json={"features": [feat("São Paulo", -23.55, -46.63), feat("Jardim São Paulo", -8.07, -34.95)]})


def test_rota_de_carro_entre_cidades_usa_o_primeiro_candidato(tmp_path):
    m, rot = motor(tmp_path, [("photon.komoot.io", _photon_homonimos), ("routing.openstreetmap.de", fixture("osrm_route.json"))])
    r = m.rota("-8.05,-34.9", "São Paulo", "carro")
    foto = [c for c in rot.chamadas if "photon" in str(c.url)]
    assert "lat" not in foto[0].url.params and foto[0].url.params["limit"] == "1"
    assert r["ok"] and r["destino"] == "São Paulo" and not r.get("aviso")


def test_rota_a_pe_usa_o_mais_proximo_e_avisa_homonimo(tmp_path):
    m, rot = motor(tmp_path, [("photon.komoot.io", _photon_homonimos), ("routing.openstreetmap.de", fixture("osrm_route.json"))])
    r = m.rota("-8.05,-34.9", "São Paulo", "pe")
    foto = [c for c in rot.chamadas if "photon" in str(c.url)]
    assert foto[0].url.params["lat"] == "-8.05"
    assert r["ok"] and r["destino"] == "Jardim São Paulo"
    assert "Jardim São Paulo escolhido entre homônimos pelo mais próximo; confira o nome" in r["aviso"]


def test_rota_de_carro_com_pontos_muito_proximos_avisa(tmp_path):
    m, _ = motor(tmp_path, [("routing.openstreetmap.de", fixture("osrm_route.json"))])
    r = m.rota("-8.05,-34.9", "-8.051,-34.901", "carro")
    assert r["ok"] and "menos de 2 km" in r["aviso"] and "confira o nome" in r["aviso"]
    assert not m.rota("-8.05,-34.9", "-8.051,-34.901", "pe").get("aviso")


def test_distancias_avisa_homonimo_escolhido_pelo_mais_proximo(tmp_path):
    tabela = {"code": "Ok", "durations": [[0, 60], [60, 0]], "distances": None}
    m, _ = motor(tmp_path, [("photon.komoot.io", _photon_homonimos), ("routing.openstreetmap.de", tabela)])
    r = m.distancias(["-8.05,-34.9", "São Paulo"], "pe")
    assert r["ok"] and r["pontos"][1] == "Jardim São Paulo" and "escolhido entre homônimos" in r["aviso"]
