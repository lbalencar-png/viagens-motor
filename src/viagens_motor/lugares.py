"""Lugares: texto ou endereço para coordenadas (Photon, dados do OpenStreetMap)."""

from __future__ import annotations

import math
import re

from .http import Cliente, rotulo
from .resultado import FonteErro

PHOTON = "https://photon.komoot.io/api/"
FONTE = "Photon (OpenStreetMap)"
TTL = 180 * 86400
_COORD = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


def km_entre(a, b) -> float:
    """Distância em linha reta (haversine) entre dois (lat, lon), em km."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _endereco(p: dict) -> str:
    rua = " ".join(x for x in (p.get("street"), p.get("housenumber")) if x)
    partes = (rua, p.get("postcode"), p.get("city") or p.get("locality"), p.get("country"))
    return ", ".join(x for x in partes if x)


def buscar(cli: Cliente, texto: str, perto_de=None, limite: int = 5) -> tuple[list[dict], str]:
    params = {"q": texto, "limit": limite}
    if perto_de:
        params["lat"], params["lon"] = perto_de
    r = cli.get_json(PHOTON, params, fonte=FONTE, ttl=TTL)
    cands = []
    for f in r.dados.get("features", []):
        lon, lat = f["geometry"]["coordinates"][:2]
        p = f.get("properties", {})
        cands.append(
            {
                "nome": p.get("name") or texto,
                "endereco": _endereco(p),
                "lat": lat,
                "lon": lon,
                "tipo": f"{p.get('osm_key', '')}:{p.get('osm_value', '')}",
                "pais": p.get("countrycode", ""),
            }
        )
    if not cands:
        raise FonteErro(FONTE, f"nenhum lugar encontrado para '{texto}'")
    return cands, rotulo(FONTE, r)


def localizar(cli: Cliente, ponto, perto_de=None) -> tuple[float, float, str, str | None]:
    """Como coordenadas, mais o aviso quando o escolhido não é o primeiro candidato do Photon.

    Com perto_de, escolhe o candidato mais próximo entre 5; sem, o primeiro do Photon.
    """
    if isinstance(ponto, (tuple, list)):
        return float(ponto[0]), float(ponto[1]), f"{ponto[0]},{ponto[1]}", None
    m = _COORD.match(ponto)
    if m:
        return float(m[1]), float(m[2]), ponto.strip(), None
    if perto_de:
        cands, _ = buscar(cli, ponto, perto_de=perto_de, limite=5)
        c = min(cands, key=lambda x: km_entre(perto_de, (x["lat"], x["lon"])))  # empate: ordem do Photon
    else:
        cands, _ = buscar(cli, ponto, limite=1)
        c = cands[0]
    aviso = None
    if c is not cands[0]:
        aviso = f"{c['nome']} escolhido entre homônimos pelo mais próximo; confira o nome"
    return c["lat"], c["lon"], c["nome"], aviso


def coordenadas(cli: Cliente, ponto, perto_de=None) -> tuple[float, float, str]:
    """Aceita (lat, lon), 'lat,lon' ou texto. Devolve lat, lon e o nome usado."""
    return localizar(cli, ponto, perto_de)[:3]
