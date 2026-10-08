"""Custos da viagem: soma por categoria, situação e pessoa, em reais (puro)."""

from __future__ import annotations

from typing import Callable

CATEGORIAS = frozenset(
    {"voo", "hotel", "trem", "onibus", "carro", "transfer", "ingresso", "alimentacao", "transporte_local", "seguro", "documentos", "outros"}
)
SITUACOES = frozenset({"previsto", "reservado", "pago"})


def validar(item: dict) -> None:
    if not isinstance(item, dict):
        raise ValueError("item inválido: esperado um objeto com id, categoria, valor e moeda")
    if not item.get("id"):
        raise ValueError("item ?: id ausente")
    i = item["id"]
    if item.get("categoria") not in CATEGORIAS:
        raise ValueError(f"item {i}: categoria '{item.get('categoria')}' inválida")
    if item.get("situacao") not in SITUACOES:
        raise ValueError(f"item {i}: situacao '{item.get('situacao')}' inválida")
    if not isinstance(item.get("valor"), (int, float)) or not item.get("moeda"):
        raise ValueError(f"item {i}: valor e moeda são obrigatórios")
    if str(item.get("meio", "")).startswith("pontos:") and not item.get("pontos"):
        raise ValueError(f"item {i}: pontos ausentes")
    if not _numero_positivo(item.get("quantidade", 1)):
        raise ValueError(f"item {i}: quantidade deve ser um número maior que zero")
    if item.get("por_pessoa"):
        pessoas = item.get("pessoas")
        if not _numero_positivo(pessoas) or pessoas < 1:
            raise ValueError(f"item {i}: com por_pessoa, pessoas é obrigatório e deve ser pelo menos 1")
    moeda = str(item["moeda"]).upper()
    if moeda != "BRL" and not item.get("meio"):
        raise ValueError(f"item {i}: meio ausente para moeda {moeda}")


def _numero_positivo(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def somar(itens: list[dict], cotar: Callable[[dict, float], tuple[float, str]], viajantes: int | None = None) -> dict:
    if not isinstance(itens, list):
        raise ValueError("itens deve ser uma lista")
    por_categoria: dict[str, float] = {}
    por_situacao: dict[str, float] = {}
    pontos: dict[str, int] = {}
    notas: list[str] = []
    linhas = []
    total = 0.0
    for item in itens:
        validar(item)
        meio = str(item.get("meio", ""))
        if meio.startswith("pontos:"):
            programa = meio.split(":", 1)[1]
            pontos[programa] = pontos.get(programa, 0) + int(item["pontos"])
            continue
        mult = item.get("quantidade", 1) * (item.get("pessoas", 1) if item.get("por_pessoa") else 1)
        try:
            valor_brl, nota = cotar(item, item["valor"] * mult)
        except Exception as e:
            raise ValueError(f"item {item['id']}: cotação falhou: {e}") from e
        total += valor_brl
        por_categoria[item["categoria"]] = round(por_categoria.get(item["categoria"], 0) + valor_brl, 2)
        por_situacao[item["situacao"]] = round(por_situacao.get(item["situacao"], 0) + valor_brl, 2)
        if nota not in notas:
            notas.append(nota)
        linhas.append({"id": item["id"], "valor_brl": valor_brl, "nota": nota})
    return {
        "total_brl": round(total, 2),
        "por_categoria": por_categoria,
        "por_situacao": por_situacao,
        "por_pessoa": round(total / viajantes, 2) if viajantes else None,
        "pontos": pontos,
        "cambio_usado": notas,
        "itens": linhas,
    }
