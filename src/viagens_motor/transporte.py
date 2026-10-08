"""Transporte público (trem, ônibus, metrô) pelo Transitous, com horário de referência."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .http import Cliente, Resposta, rotulo
from .resultado import FonteErro

PLAN = "https://api.transitous.org/api/v1/plan"
FONTE = "Transitous (transitous.org/sources)"
TTL = 86400
SEMANAS_REFERENCIA = 4


def _consultar(cli: Cliente, a, b, quando: datetime) -> tuple[list[dict], Resposta]:
    params = {
        "fromPlace": f"{a[0]},{a[1]}",
        "toPlace": f"{b[0]},{b[1]}",
        "time": quando.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "numItineraries": 3,
    }
    r = cli.get_json(PLAN, params, fonte=FONTE, ttl=TTL)
    its = []
    for it in r.dados.get("itineraries", [])[:3]:
        pernas = [
            {
                "modo": l["mode"],
                "linha": l.get("displayName") or l.get("routeShortName") or "",
                "empresa": l.get("agencyName", ""),
                "de": l.get("from", {}).get("name", ""),
                "para": l.get("to", {}).get("name", ""),
                "partida": l.get("startTime"),
                "chegada": l.get("endTime"),
                "duracao_min": round(l.get("duration", 0) / 60),
            }
            for l in it.get("legs", [])
        ]
        its.append(
            {
                "duracao_min": round(it["duration"] / 60),
                "trocas": it.get("transfers", 0),
                "partida": it.get("startTime"),
                "chegada": it.get("endTime"),
                "pernas": pernas,
            }
        )
    return its, r


def _fora_da_janela(e: FonteErro) -> bool:
    return "HTTP 400" in str(e) and "timetable" in str(e)


def plano(cli: Cliente, a, b, quando_local: datetime, hoje: date | None = None) -> tuple[dict, str, str | None]:
    hoje = hoje or date.today()
    erro_janela = None
    try:
        its, r = _consultar(cli, a, b, quando_local)
    except FonteErro as e:
        if not _fora_da_janela(e):
            raise
        its, erro_janela = [], e
    if its:
        return {"itinerarios": its}, rotulo(FONTE, r), None
    if quando_local.date() <= hoje + timedelta(days=7):
        raise erro_janela or FonteErro(FONTE, "nenhum itinerário encontrado")
    base = hoje + timedelta(days=(quando_local.weekday() - hoje.weekday()) % 7 or 7)
    for k in range(SEMANAS_REFERENCIA):
        dia = base + timedelta(weeks=k)
        try:
            its, r = _consultar(cli, a, b, quando_local.replace(year=dia.year, month=dia.month, day=dia.day))
        except FonteErro as e:
            if not _fora_da_janela(e):
                raise
            continue
        if its:
            aviso = f"horário de referência de {dia:%d/%m/%Y}; conferir quando sair o horário da data da viagem"
            return {"itinerarios": its, "data_referencia": dia.isoformat()}, rotulo(FONTE, r), aviso
    raise FonteErro(FONTE, f"nenhum itinerário na data nem nas {SEMANAS_REFERENCIA} semanas de referência")
