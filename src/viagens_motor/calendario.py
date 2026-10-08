"""Calendário: feriados por país (Nager.Date) e mudança de horário de verão (zoneinfo)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .http import Cliente, rotulo

NAGER = "https://date.nager.at/api/v3/PublicHolidays/{ano}/{pais}"
FONTE = "Nager.Date"
TTL = 365 * 86400


def feriados(cli: Cliente, pais: str, inicio: date, fim: date, regiao: str | None = None) -> tuple[list[dict], str]:
    pais = pais.upper().strip()
    achados, fonte = [], FONTE
    for ano in range(inicio.year, fim.year + 1):
        r = cli.get_json(NAGER.format(ano=ano, pais=pais), fonte=FONTE, ttl=TTL)
        fonte = rotulo(FONTE, r)
        for h in r.dados:
            d = date.fromisoformat(h["date"])
            if not inicio <= d <= fim:
                continue
            condados = h.get("counties") or []
            regional = bool(regiao) and any(c == regiao or c.endswith("-" + regiao) for c in condados)
            if h.get("global") or regional:
                achados.append(
                    {"data": h["date"], "nome": h["localName"], "nome_en": h["name"],
                     "abrangencia": "nacional" if h.get("global") else ", ".join(condados)}
                )
    return achados, fonte


def _offset(fuso: ZoneInfo, d: date) -> str:
    s = datetime(d.year, d.month, d.day, 12, tzinfo=fuso).strftime("%z")
    return f"{s[:3]}:{s[3:]}"


def mudancas_horario(fuso: str, inicio: date, fim: date) -> list[dict]:
    z = ZoneInfo(fuso)
    mudancas = []
    anterior = _offset(z, inicio - timedelta(days=1))
    d = inicio
    while d <= fim:
        atual = _offset(z, d)
        if atual != anterior:
            mudancas.append({"data": d.isoformat(), "de": anterior, "para": atual})
        anterior = atual
        d += timedelta(days=1)
    return mudancas
