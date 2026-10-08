"""Provedor alternativo: Google Maps Routes API (só quando a chave existir)."""

from __future__ import annotations

from datetime import datetime, timezone

from .http import Cliente, rotulo
from .resultado import FonteErro

ROUTES = "https://routes.googleapis.com/directions/v2:computeRoutes"
FONTE = "Google Maps (Routes API)"
MODOS = {"pe": "WALK", "bicicleta": "BICYCLE", "carro": "DRIVE", "transporte": "TRANSIT"}


def _ponto(p) -> dict:
    return {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}


def rota(cli: Cliente, chave: str, a, b, modo: str, partida: datetime | None = None) -> tuple[dict, str]:
    if modo not in MODOS:
        raise ValueError("modo deve ser pe, bicicleta, carro ou transporte")
    corpo = {"origin": _ponto(a), "destination": _ponto(b), "travelMode": MODOS[modo]}
    if partida is not None and modo in ("transporte", "carro"):
        corpo["departureTime"] = partida.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = cli.post_json(
        ROUTES, corpo, fonte=FONTE, ttl=0,  # os termos do Google Maps Platform restringem guardar rotas
        headers={"X-Goog-Api-Key": chave, "X-Goog-FieldMask": "routes.distanceMeters,routes.duration"},
    )
    rotas = r.dados.get("routes") or []
    if not rotas:
        raise FonteErro(FONTE, "sem rota")
    segundos = int(str(rotas[0]["duration"]).rstrip("s"))
    return {"distancia_m": int(rotas[0].get("distanceMeters", 0)), "duracao_min": round(segundos / 60)}, rotulo(FONTE, r)
