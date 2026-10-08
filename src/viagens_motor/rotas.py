"""Rotas a pé, de bicicleta e de carro e tabela de tempos (OSRM da FOSSGIS)."""

from __future__ import annotations

from .http import Cliente, rotulo
from .resultado import FonteErro

BASE = "https://routing.openstreetmap.de"
PERFIS = {"pe": "routed-foot", "bicicleta": "routed-bike", "carro": "routed-car"}
MODOS = tuple(PERFIS)
FONTE = "OSRM da FOSSGIS (OpenStreetMap)"
TTL = 30 * 86400


def _perfil(modo: str) -> str:
    if modo not in PERFIS:
        raise ValueError("modo deve ser pe, bicicleta ou carro")
    return PERFIS[modo]


def rota(cli: Cliente, a: tuple[float, float], b: tuple[float, float], modo: str) -> tuple[dict, str]:
    perfil = _perfil(modo)
    url = f"{BASE}/{perfil}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}"
    r = cli.get_json(url, {"overview": "false"}, fonte=FONTE, ttl=TTL)
    if r.dados.get("code") != "Ok" or not r.dados.get("routes"):
        motivo = f"{r.dados.get('code')} {r.dados.get('message', '')}".strip()
        raise FonteErro(FONTE, f"sem rota: {motivo}")
    rt = r.dados["routes"][0]
    dados = {"distancia_m": round(rt["distance"]), "duracao_min": round(rt["duration"] / 60)}
    return dados, rotulo(FONTE, r)


def matriz(cli: Cliente, pontos: list[tuple[float, float]], modo: str) -> tuple[dict, str]:
    if not 2 <= len(pontos) <= 25:
        raise ValueError("distancias aceita de 2 a 25 pontos")
    perfil = _perfil(modo)
    coords = ";".join(f"{lon},{lat}" for lat, lon in pontos)
    url = f"{BASE}/{perfil}/table/v1/driving/{coords}"
    r = cli.get_json(url, {"annotations": "duration,distance"}, fonte=FONTE, ttl=TTL)
    if r.dados.get("code") != "Ok":
        motivo = f"{r.dados.get('code')} {r.dados.get('message', '')}".strip()
        raise FonteErro(FONTE, f"sem tabela: {motivo}")
    dados = {"duracoes_s": r.dados["durations"], "distancias_m": r.dados.get("distances")}
    return dados, rotulo(FONTE, r)
