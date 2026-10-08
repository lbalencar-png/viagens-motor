"""Configuração pessoal (IOF, spreads, origem, chave do Google), fora do repositório."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Meio:
    chave: str
    nome: str
    iof: float
    spread: float | None
    spread_verificar: bool = False
    iof_devolvido: bool = False
    ptax_dia_anterior: bool = False
    fonte_spread: str = ""


@dataclass(frozen=True)
class Config:
    origem_padrao: str = ""
    projeto_url: str = ""
    google_chave_env: str = "GOOGLE_MAPS_API_KEY"
    iof: dict = field(default_factory=dict)
    cartoes: dict = field(default_factory=dict)
    conta_global_spread: float | None = None

    def meio(self, chave: str) -> Meio:
        tipo, _, cartao = chave.partition(":")
        if tipo not in ("cartao", "especie", "conta_global"):
            raise ValueError(f"meio desconhecido: {chave} (use cartao:<nome>, especie ou conta_global)")
        if tipo not in self.iof:
            raise ValueError(f"IOF de '{tipo}' não configurado")
        if tipo == "cartao":
            if cartao not in self.cartoes:
                raise ValueError(f"cartão '{cartao}' não está no motor-config.toml")
            c = self.cartoes[cartao]
            return Meio(
                chave=chave,
                nome=c.get("nome", cartao),
                iof=float(self.iof["cartao"]),
                spread=c.get("spread"),
                spread_verificar=bool(c.get("spread_verificar", False)),
                iof_devolvido=bool(c.get("iof_devolvido", False)),
                ptax_dia_anterior=bool(c.get("ptax_dia_anterior", False)),
                fonte_spread=c.get("fonte_spread", ""),
            )
        if tipo == "conta_global":
            return Meio(chave, "conta global", float(self.iof["conta_global"]), self.conta_global_spread)
        return Meio(chave, "espécie", float(self.iof["especie"]), None)

    def google_chave(self) -> str | None:
        return os.environ.get(self.google_chave_env) or None


def caminho_config() -> Path:
    env = os.environ.get("VIAGENS_MOTOR_CONFIG")
    return Path(env) if env else Path.home() / ".config/viagens-motor/config.toml"


def carregar(caminho: Path | None = None) -> Config:
    p = caminho or caminho_config()
    if not p.exists():
        return Config()
    d = tomllib.loads(p.read_text(encoding="utf-8"))
    return Config(
        origem_padrao=d.get("origem_padrao", ""),
        projeto_url=d.get("projeto_url", ""),
        google_chave_env=d.get("google_chave_env", "GOOGLE_MAPS_API_KEY"),
        iof=d.get("iof", {}),
        cartoes=d.get("cartoes", {}),
        conta_global_spread=d.get("conta_global", {}).get("spread"),
    )
