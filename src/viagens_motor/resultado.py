"""Formato comum das respostas do motor."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

RECIFE = ZoneInfo("America/Recife")


class FonteErro(Exception):
    """Falha de uma fonte externa. Nunca vira número estimado."""

    def __init__(self, fonte: str, mensagem: str):
        super().__init__(mensagem)
        self.fonte = fonte


def carimbo(dt: datetime | None = None) -> str:
    return (dt or datetime.now(RECIFE)).astimezone(RECIFE).strftime("%d/%m/%Y %Hh%M")


def ok(fonte: str, dados: dict, aviso: str | None = None) -> dict:
    r = {"ok": True, "fonte": fonte, "consultado_em": carimbo(), **dados}
    if aviso:
        r["aviso"] = aviso
    return r


def falha(fonte: str, erro: str) -> dict:
    return {"ok": False, "fonte": fonte, "erro": erro, "consultado_em": carimbo()}
