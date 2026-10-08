"""Servidor MCP (stdio) do motor de viagens."""

from __future__ import annotations

import json
import sqlite3
import threading
import tomllib
from typing import Any

from fastmcp import FastMCP

from .ferramentas import Motor, criar_motor, pasta_dados
from .resultado import falha, ok

mcp = FastMCP("viagens-motor")
_motor: Motor | None = None
_trava_motor = threading.Lock()
LEITURA = {"readOnlyHint": True, "idempotentHint": True}


def motor() -> Motor:
    global _motor
    with _trava_motor:  # as ferramentas rodam em threads; o Motor é criado uma vez só
        if _motor is None:
            _motor = criar_motor()
        return _motor


def _chamar(nome: str, *args) -> dict:
    """Cria o Motor (uma vez) e chama a ferramenta; erro de configuração vira resposta sem número."""
    try:
        m = motor()
    except (tomllib.TOMLDecodeError, OSError, ValueError, sqlite3.Error) as e:
        return falha("viagens-motor", f"configuração inválida: {e}")
    return getattr(m, nome)(*args)


@mcp.tool(annotations=LEITURA)
def lugar(texto: str, perto_de: str | None = None) -> dict:
    """Acha um lugar (nome ou endereço) e devolve até 5 candidatos com coordenadas. perto_de: lugar ou 'lat,lon' para desempatar."""
    return _chamar("lugar", texto, perto_de)


@mcp.tool(annotations=LEITURA)
def rota(origem: str, destino: str, modo: str = "pe", quando: str | None = None) -> dict:
    """Rota entre dois pontos (texto ou 'lat,lon'). modo: pe, bicicleta, carro ou transporte. quando: AAAA-MM-DDTHH:MM na hora local da origem (só transporte)."""
    return _chamar("rota", origem, destino, modo, quando)


@mcp.tool(annotations=LEITURA)
def distancias(pontos: list[str], modo: str = "pe") -> dict:
    """Tabela de minutos e km entre 2 a 25 pontos. modo: pe, bicicleta ou carro."""
    return _chamar("distancias", pontos, modo)


@mcp.tool(annotations=LEITURA)
def ordenar_dia(partida: str, lugares: list[str], voltar: bool = True, modo: str = "pe") -> dict:
    """Ordem dos lugares do dia (1 a 10) que minimiza o deslocamento a partir de 'partida' (em geral o hotel). Não considera horário de abertura."""
    return _chamar("ordenar_dia", partida, lugares, voltar, modo)


@mcp.tool(annotations=LEITURA)
def clima(lugar: str, inicio: str, fim: str) -> dict:
    """Clima por dia (AAAA-MM-DD): previsão até 16 dias; além disso, média e faixa dos 10 anos anteriores nas mesmas datas."""
    return _chamar("clima", lugar, inicio, fim)


@mcp.tool(annotations=LEITURA)
def cambio(moeda: str, valor: float = 1.0, data: str | None = None, meio: str | None = None) -> dict:
    """Câmbio para reais. Sem meio: PTAX (ou BCE cruzado). Com meio (cartao:<nome>, especie, conta_global): soma spread e IOF do motor-config.toml."""
    return _chamar("cambio", moeda, valor, data, meio)


@mcp.tool(annotations=LEITURA)
def calendario(pais: str, inicio: str, fim: str, regiao: str | None = None, lugar: str | None = None) -> dict:
    """Feriados do país (código ISO de 2 letras) no período e, com lugar, o fuso e a mudança de horário de verão."""
    return _chamar("calendario", pais, inicio, fim, regiao, lugar)


@mcp.tool(annotations=LEITURA)
def custos(itens: list[dict[str, Any]], viajantes: int | None = None, data: str | None = None) -> dict:
    """Soma os itens de custo da viagem em reais por categoria, situação e pessoa; pontos ficam à parte por programa."""
    return _chamar("custos", itens, viajantes, data)


@mcp.tool(annotations=LEITURA)
def spread_da_fatura(cartao: str, data_compra: str, moeda: str, valor_moeda: float, valor_reais: float) -> dict:
    """Spread efetivo de um cartão a partir de uma compra no exterior lançada na fatura (valor em reais sem o IOF)."""
    return _chamar("spread_da_fatura", cartao, data_compra, moeda, valor_moeda, valor_reais)


@mcp.tool(annotations=LEITURA)
def saude() -> dict:
    """Situação de cada fonte do motor (última verificação diária)."""
    p = pasta_dados() / "status.json"
    if not p.exists():
        return falha("viagens-motor", "verificação ainda não rodou (viagens-motor-saude)")
    try:
        conteudo = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return falha("viagens-motor", f"status.json ilegível: {e}")
    if not isinstance(conteudo, dict):
        return falha("viagens-motor", "status.json ilegível: esperado um objeto")
    # O ok do status.json vem depois do ok da resposta e prevalece.
    return ok("verificação diária (status.json)", conteudo)


def main() -> None:
    mcp.run(transport="stdio")
