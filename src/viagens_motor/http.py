"""Cliente HTTP único: memória, intervalo mínimo por host e novas tentativas."""

from __future__ import annotations

import json
import threading
import time
import unicodedata
from datetime import datetime
from typing import Any, Callable, NamedTuple
from urllib.parse import urlsplit

import httpx

from . import __version__
from .cache import Cache
from .resultado import RECIFE, FonteErro

INTERVALOS = {"routing.openstreetmap.de": 1.0, "photon.komoot.io": 1.0, "api.transitous.org": 1.0}
INTERVALO_PADRAO = 0.2
TENTATIVAS = 3


PROJETO_URL_PADRAO = "https://github.com/lbalencar-png/viagens-motor"


def user_agent(projeto_url: str) -> str:
    """Identificação exigida pelas fontes (nome, versão e contato); projeto_url só substitui o padrão."""
    return f"viagens-motor/{__version__} (+{projeto_url or PROJETO_URL_PADRAO})"


def _ascii(texto: str) -> str:
    """httpx só aceita cabeçalho em ASCII; 'código' vira 'codigo' no cabeçalho."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


class Resposta(NamedTuple):
    dados: Any
    memoria_em: float | None


def rotulo(fonte: str, resp: Resposta) -> str:
    if resp.memoria_em is None:
        return fonte
    quando = datetime.fromtimestamp(resp.memoria_em, RECIFE).strftime("%d/%m/%Y %Hh%M")
    return f"{fonte} (memória de {quando})"


class Cliente:
    def __init__(
        self,
        cache: Cache | None = None,
        *,
        projeto_url: str = "",
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ):
        self.cache = cache
        self._dormir = dormir
        self._relogio = relogio
        self._ultimo: dict[str, float] = {}
        # O FastMCP roda as ferramentas em threads: uma trava por host mantém o intervalo.
        self._travas: dict[str, threading.Lock] = {}
        self._trava_travas = threading.Lock()
        self.http = httpx.Client(
            transport=transport,
            timeout=40,
            follow_redirects=True,
            headers={"User-Agent": _ascii(user_agent(projeto_url))},
        )

    def get_json(self, url, params=None, *, fonte, ttl, headers=None) -> Resposta:
        return self._pedir("GET", url, params, None, fonte, ttl, headers)

    def post_json(self, url, corpo, *, fonte, ttl, headers=None) -> Resposta:
        return self._pedir("POST", url, None, corpo, fonte, ttl, headers)

    def _pedir(self, metodo, url, params, corpo, fonte, ttl, headers) -> Resposta:
        chave = json.dumps([metodo, url, sorted((params or {}).items()), corpo], sort_keys=True, default=str)
        if self.cache is not None and ttl > 0:
            achado = self.cache.get(chave)
            if achado is not None:
                return Resposta(achado[0], achado[1])
        host = urlsplit(url).hostname or ""
        ultimo_erro = ""
        for tentativa in range(TENTATIVAS):
            self._esperar_vez(host)
            try:
                r = self.http.request(metodo, url, params=params, json=corpo, headers=headers)
            except httpx.TimeoutException as e:
                ultimo_erro = f"tempo esgotado ({e})"
            except httpx.HTTPError as e:
                raise FonteErro(fonte, f"falha de conexão: {e}") from e
            else:
                if r.status_code == 429 or r.status_code >= 500:
                    ultimo_erro = f"HTTP {r.status_code}"
                elif r.status_code >= 400:
                    raise FonteErro(fonte, f"HTTP {r.status_code}: {r.text[:200]}")
                else:
                    try:
                        dados = r.json()
                    except ValueError as e:
                        raise FonteErro(fonte, "resposta não é JSON") from e
                    if self.cache is not None and ttl > 0:
                        self.cache.put(chave, dados, ttl)
                    return Resposta(dados, None)
            if tentativa < TENTATIVAS - 1:
                self._dormir(2**tentativa)
        raise FonteErro(fonte, f"{ultimo_erro} após {TENTATIVAS} tentativas")

    def _trava(self, host: str) -> threading.Lock:
        with self._trava_travas:
            return self._travas.setdefault(host, threading.Lock())

    def _esperar_vez(self, host: str) -> None:
        """Checagem, espera e registro sob a trava do host: duas threads não saem juntas."""
        intervalo = INTERVALOS.get(host, INTERVALO_PADRAO)
        with self._trava(host):
            agora = self._relogio()
            anterior = self._ultimo.get(host)
            if anterior is not None and agora - anterior < intervalo:
                self._dormir(intervalo - (agora - anterior))
            self._ultimo[host] = self._relogio()
