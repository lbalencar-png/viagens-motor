import json

import httpx
import pytest

from viagens_motor.cache import Cache
from viagens_motor.http import Cliente, Resposta, rotulo, user_agent
from viagens_motor.resultado import FonteErro


def test_user_agent_sem_e_com_url():
    assert user_agent("") == "viagens-motor/0.1.0 (+https://github.com/lbalencar-png/viagens-motor)"
    assert user_agent("https://github.com/x/viagens-motor") == "viagens-motor/0.1.0 (+https://github.com/x/viagens-motor)"


def test_user_agent_enviado_e_ascii():
    enviados = []

    def capturar(req):
        enviados.append(req.headers["User-Agent"])
        return httpx.Response(200, json={})

    cli = Cliente(None, transport=httpx.MockTransport(capturar), dormir=lambda s: None)
    cli.get_json("https://exemplo.org/ua", fonte="F", ttl=0)
    assert enviados[0].isascii()
    assert enviados[0] == "viagens-motor/0.1.0 (+https://github.com/lbalencar-png/viagens-motor)"


def test_usa_memoria_na_segunda_chamada(cliente_com):
    cli, rot = cliente_com([("exemplo.org", {"a": 1})])
    r1 = cli.get_json("https://exemplo.org/x", {"q": "1"}, fonte="F", ttl=60)
    r2 = cli.get_json("https://exemplo.org/x", {"q": "1"}, fonte="F", ttl=60)
    assert r1 == Resposta({"a": 1}, None)
    assert r2.dados == {"a": 1} and r2.memoria_em is not None
    assert len(rot.chamadas) == 1
    assert rotulo("F", r2).startswith("F (memória de ")


def test_tenta_de_novo_em_503_e_429(cliente_com):
    respostas = iter([httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"ok": 1})])
    cli, rot = cliente_com([("exemplo.org", lambda req: next(respostas))])
    assert cli.get_json("https://exemplo.org/y", fonte="F", ttl=0).dados == {"ok": 1}
    assert len(rot.chamadas) == 3


def test_desiste_depois_de_3_tentativas(cliente_com):
    cli, rot = cliente_com([("exemplo.org", (500, {}))])
    with pytest.raises(FonteErro, match="HTTP 500 após 3 tentativas") as e:
        cli.get_json("https://exemplo.org/z", fonte="Fonte Z", ttl=0)
    assert e.value.fonte == "Fonte Z" and len(rot.chamadas) == 3


def test_4xx_nao_repete(cliente_com):
    cli, rot = cliente_com([("exemplo.org", (404, {"erro": "x"}))])
    with pytest.raises(FonteErro, match="HTTP 404"):
        cli.get_json("https://exemplo.org/w", fonte="F", ttl=0)
    assert len(rot.chamadas) == 1


def test_intervalo_por_host(tmp_path):
    esperas, tempo = [], [100.0]
    cli = Cliente(
        None,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        dormir=lambda s: esperas.append(round(s, 2)),
        relogio=lambda: tempo[0],
    )
    cli.get_json("https://photon.komoot.io/api/", fonte="F", ttl=0)
    tempo[0] = 100.3
    cli.get_json("https://photon.komoot.io/api/", fonte="F", ttl=0)
    assert esperas == [0.7]


def test_post_envia_corpo_e_cabecalho(cliente_com):
    def responder(req):
        assert req.headers["X-Teste"] == "1" and json.loads(req.read()) == {"a": 1}
        return httpx.Response(200, json={"r": 2})

    cli, _ = cliente_com([("exemplo.org", responder)])
    assert cli.post_json("https://exemplo.org/p", {"a": 1}, fonte="F", ttl=0, headers={"X-Teste": "1"}).dados == {"r": 2}


def test_intervalo_por_host_com_duas_threads():
    """Duas threads no mesmo host: a segunda espera o intervalo inteiro depois da primeira."""
    import threading
    import time

    esperas, tempo, trava = [], [100.0], threading.Lock()

    def relogio():
        time.sleep(0.02)  # abre a janela em que, sem trava, as duas threads leriam o mesmo estado
        with trava:
            return tempo[0]

    def dormir(s):
        with trava:
            esperas.append(round(s, 2))
            tempo[0] += s

    cli = Cliente(None, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})), dormir=dormir, relogio=relogio)
    ts = [threading.Thread(target=cli.get_json, args=("https://photon.komoot.io/api/",), kwargs={"fonte": "F", "ttl": 0}) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sum(esperas) == 1.0
