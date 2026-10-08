"""Câmbio: PTAX do Banco Central, BCE cruzado para as demais moedas, custo por meio de pagamento."""

from __future__ import annotations

from datetime import date, timedelta

from .config import Config
from .http import Cliente, rotulo
from .resultado import FonteErro

PTAX = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)
FRANKFURTER = "https://api.frankfurter.dev/v1/"
FONTE_PTAX = "PTAX do Banco Central"
FONTE_BCE = "BCE via Frankfurter"
MOEDAS_PTAX = frozenset({"AUD", "CAD", "CHF", "DKK", "EUR", "GBP", "JPY", "NOK", "SEK", "USD"})


def _taxa_txt(taxa: float) -> str:
    """Taxa para a conta impressa: 4 casas quando >= 1, 6 algarismos significativos abaixo disso."""
    return f"{taxa:.4f}" if taxa >= 1 else f"{taxa:.6g}"


def _ttl(data: date, hoje: date) -> int:
    return 365 * 86400 if data < hoje else 6 * 3600


def _ptax(cli: Cliente, moeda: str, data: date, hoje: date) -> tuple[dict, str]:
    ini = data - timedelta(days=10)
    params = {
        "@moeda": f"'{moeda}'",
        "@dataInicial": f"'{ini:%m-%d-%Y}'",
        "@dataFinalCotacao": f"'{data:%m-%d-%Y}'",
        "$format": "json",
    }
    r = cli.get_json(PTAX, params, fonte=FONTE_PTAX, ttl=_ttl(data, hoje))
    limite = data.isoformat()
    fech = [
        v for v in r.dados.get("value", [])
        if v.get("tipoBoletim") == "Fechamento" and v.get("dataHoraCotacao", "")[:10] <= limite
    ]
    if not fech:
        raise FonteErro(FONTE_PTAX, f"sem boletim de fechamento de {moeda} até {data:%d/%m/%Y}")
    v = max(fech, key=lambda v: v["dataHoraCotacao"])
    return {"moeda": moeda, "taxa": v["cotacaoVenda"], "data_taxa": v["dataHoraCotacao"][:10]}, rotulo(FONTE_PTAX, r)


def taxa_brl(cli: Cliente, moeda: str, data: date, hoje: date | None = None) -> tuple[dict, str, str | None]:
    hoje = hoje or date.today()
    moeda = moeda.upper().strip()
    futura = data > hoje
    data = min(data, hoje)
    if moeda == "BRL":
        return {"moeda": "BRL", "taxa": 1.0, "data_taxa": data.isoformat()}, "sem conversão", None
    if moeda in MOEDAS_PTAX:
        dados, fonte = _ptax(cli, moeda, data, hoje)
        return dados, fonte, _aviso_futura(futura, dados)
    eur, _ = _ptax(cli, "EUR", data, hoje)
    r = cli.get_json(FRANKFURTER + eur["data_taxa"], {"base": "EUR", "symbols": moeda}, fonte=FONTE_BCE, ttl=_ttl(data, hoje))
    por_euro = r.dados.get("rates", {}).get(moeda)
    if not por_euro:
        raise FonteErro(FONTE_BCE, f"moeda {moeda} sem cotação na PTAX nem no BCE")
    dados = {"moeda": moeda, "taxa": eur["taxa"] / por_euro, "data_taxa": eur["data_taxa"]}
    aviso = f"conversão cruzada: PTAX do euro de {eur['data_taxa']} dividida por {por_euro} {moeda} por euro (BCE de {r.dados.get('date')}); a bandeira do cartão converte por conta própria"
    aviso_futura = _aviso_futura(futura, dados)
    if aviso_futura:
        aviso = f"{aviso_futura}; {aviso}"
    return dados, f"{FONTE_PTAX} (EUR) e {FONTE_BCE}", aviso


def _aviso_futura(futura: bool, dados: dict) -> str | None:
    return f"data futura: usada a última PTAX disponível ({dados['data_taxa']})" if futura else None


def converter(cli: Cliente, cfg: Config, moeda: str, valor: float, meio: str, data: date, hoje=None) -> tuple[dict, str, str | None]:
    if moeda.upper().strip() == "BRL":
        dados = {
            "moeda": "BRL", "valor": valor, "meio": meio, "taxa": 1.0, "data_taxa": data.isoformat(),
            "spread": 0.0, "iof": 0.0, "valor_brl": round(valor, 2), "conta": f"{valor:g} = R$ {valor:.2f}",
        }
        return dados, "sem conversão", "valor já em reais"
    m = cfg.meio(meio)
    dia = data - timedelta(days=1) if m.ptax_dia_anterior else data
    t, fonte, aviso_taxa = taxa_brl(cli, moeda, dia, hoje)
    spread = m.spread or 0.0
    iof = 0.0 if m.iof_devolvido else m.iof
    total = valor * t["taxa"] * (1 + spread) * (1 + iof)
    avisos = [aviso_taxa] if aviso_taxa else []
    if m.spread is None:
        avisos.append(f"spread de {m.nome} não informado; calculado sem spread")
    elif m.spread_verificar:
        avisos.append(f"spread de {m.nome} não confirmado em fonte oficial ({m.fonte_spread})")
    if m.iof_devolvido:
        avisos.append(f"IOF de {m.iof:.1%} devolvido em fatura por {m.nome}; calculado sem IOF")
    dados = {
        "moeda": t["moeda"], "valor": valor, "meio": m.nome, "taxa": t["taxa"], "data_taxa": t["data_taxa"],
        "spread": spread, "iof": iof, "valor_brl": round(total, 2),
        "conta": f"{valor:g} × {_taxa_txt(t['taxa'])} × (1 + {spread:.2%}) × (1 + {iof:.2%}) = R$ {total:.2f}",
    }
    return dados, fonte, "; ".join(avisos) or None


def spread_efetivo(cli: Cliente, cfg: Config, cartao: str, data_compra: date, moeda: str, valor_moeda: float, valor_reais: float, hoje=None) -> tuple[dict, str]:
    if valor_moeda <= 0:
        raise ValueError("valor_moeda deve ser maior que zero")
    m = cfg.meio(f"cartao:{cartao}")
    dia = data_compra - timedelta(days=1) if m.ptax_dia_anterior else data_compra
    t, fonte, aviso_taxa = taxa_brl(cli, moeda, dia, hoje)
    efetiva = valor_reais / valor_moeda
    spread = round(efetiva / t["taxa"] - 1, 4)
    observacao = "valor em reais da fatura sem a linha de IOF"
    if aviso_taxa:
        observacao += f"; {aviso_taxa}"
    dados = {
        "cartao": m.nome, "taxa_referencia": t["taxa"], "data_taxa": t["data_taxa"], "taxa_efetiva": round(efetiva, 6),
        "spread": spread, "spread_configurado": m.spread,
        "conta": f"R$ {valor_reais:.2f} ÷ {valor_moeda:g} {t['moeda']} = {_taxa_txt(efetiva)}; {_taxa_txt(efetiva)} ÷ {_taxa_txt(t['taxa'])} − 1 = {spread:.2%}",
        "observacao": observacao,
    }
    return dados, fonte
