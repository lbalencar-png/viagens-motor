"""Clima: previsão até 16 dias e, além disso, média dos 10 anos anteriores (Open-Meteo)."""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean

from .http import Cliente, rotulo

PREVISAO = "https://api.open-meteo.com/v1/forecast"
ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"
FONTE = "Open-Meteo"
DIARIO = "temperature_2m_max,temperature_2m_min,precipitation_sum"
HORIZONTE = 15
ATRASO_ARQUIVO = 6


def _no_ano(d: date, ano: int) -> date:
    try:
        return d.replace(year=ano)
    except ValueError:
        return d.replace(year=ano, day=28)


def _historico(d: date, ano: int, fim: date) -> date:
    """Data de `d` no ano `ano`, deslocada pelo mesmo intervalo de anos que separa `d` de `fim`."""
    return _no_ano(d, ano + d.year - fim.year)


def _valor(por_data: dict, dia: date):
    """Valores do dia pelo calendário (mês, dia); 29/02 cai em 28/02 quando o ano do histórico não tem."""
    chave = (dia.month, dia.day)
    if chave not in por_data and chave == (2, 29):
        chave = (2, 28)
    return por_data.get(chave)


def _previsao(cli: Cliente, lat: float, lon: float, inicio: date, fim: date) -> tuple[list[dict], str]:
    r = cli.get_json(
        PREVISAO,
        {"latitude": lat, "longitude": lon, "daily": DIARIO + ",precipitation_probability_max", "timezone": "auto",
         "start_date": inicio.isoformat(), "end_date": fim.isoformat()},
        fonte=FONTE,
        ttl=3 * 3600,
    )
    d = r.dados["daily"]
    dias = [
        {"data": d["time"][i], "max": d["temperature_2m_max"][i], "min": d["temperature_2m_min"][i],
         "chuva_mm": d["precipitation_sum"][i], "chuva_prob": d["precipitation_probability_max"][i],
         "tipo": "previsao"}
        for i in range(len(d["time"]))
    ]
    return dias, rotulo(FONTE, r)


def _media(cli: Cliente, lat: float, lon: float, inicio: date, fim: date, hoje: date):
    limite = hoje - timedelta(days=ATRASO_ARQUIVO)
    ano = fim.year - 1
    anos: list[int] = []
    while len(anos) < 10:
        if _no_ano(fim, ano) <= limite:
            anos.append(ano)
        ano -= 1
    anos.sort()
    datas = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    maxs = [[] for _ in datas]
    mins = [[] for _ in datas]
    chuvosos = []
    ultimo = None
    for a in anos:
        r = cli.get_json(
            ARQUIVO,
            {"latitude": lat, "longitude": lon, "daily": DIARIO, "timezone": "auto",
             "start_date": _historico(inicio, a, fim).isoformat(),
             "end_date": _historico(fim, a, fim).isoformat()},
            fonte=FONTE,
            ttl=365 * 86400,
        )
        ultimo = r
        d = r.dados["daily"]
        por_data = {}
        for i, t in enumerate(d["time"]):
            dt = date.fromisoformat(t)
            por_data[(dt.month, dt.day)] = (
                d["temperature_2m_max"][i], d["temperature_2m_min"][i], d["precipitation_sum"][i])
        chuva_do_ano = 0
        for i, dia in enumerate(datas):
            v = _valor(por_data, dia)
            if v is None:
                continue
            tmax, tmin, pr = v
            if tmax is not None:
                maxs[i].append(tmax)
            if tmin is not None:
                mins[i].append(tmin)
            if pr is not None and pr > 1.0:
                chuva_do_ano += 1
        chuvosos.append(chuva_do_ano)
    dias = [
        {"data": dia.isoformat(),
         "max_media": round(mean(maxs[i]), 1) if maxs[i] else None,
         "max_faixa": [min(maxs[i]), max(maxs[i])] if maxs[i] else None,
         "min_media": round(mean(mins[i]), 1) if mins[i] else None,
         "min_faixa": [min(mins[i]), max(mins[i])] if mins[i] else None,
         "tipo": "media_10_anos"}
        for i, dia in enumerate(datas)
    ]
    return anos, dias, round(mean(chuvosos), 1), rotulo(FONTE + " (histórico)", ultimo)


def clima(cli: Cliente, lat: float, lon: float, inicio: date, fim: date, hoje: date | None = None) -> tuple[dict, str]:
    hoje = hoje or date.today()
    if fim < inicio:
        raise ValueError("fim antes do início")
    if inicio < hoje:
        raise ValueError("período no passado: use datas de hoje em diante")
    corte = hoje + timedelta(days=HORIZONTE)
    tem_previsao = inicio <= corte
    tem_media = fim > corte
    dias: list[dict] = []
    fontes: list[str] = []
    anos = dchuva = None
    if tem_previsao:
        d_prev, f_prev = _previsao(cli, lat, lon, inicio, min(fim, corte))
        dias += d_prev
        fontes.append(f_prev)
    if tem_media:
        anos, d_media, dchuva, f_media = _media(cli, lat, lon, max(inicio, corte + timedelta(days=1)), fim, hoje)
        dias += d_media
        fontes.append(f_media)
    if tem_previsao and tem_media:
        tipo = "misto"
    elif tem_previsao:
        tipo = "previsao"
    else:
        tipo = "media_10_anos"
    resultado: dict = {"tipo": tipo, "dias": dias}
    if tem_media:
        resultado["anos"] = anos
        resultado["dias_chuva_media"] = dchuva
    return resultado, " e ".join(fontes)
