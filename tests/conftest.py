import json
from pathlib import Path

import httpx
import pytest

from viagens_motor.cache import Cache
from viagens_motor.http import Cliente

FIX = Path(__file__).parent / "fixtures"


def fixture(nome):
    return json.loads((FIX / nome).read_text(encoding="utf-8"))


class Roteador:
    """Responde pela primeira regra cujo trecho aparece na URL e registra as chamadas.

    Cada regra é (trecho_da_url, resposta); resposta é um dict (HTTP 200 com JSON),
    uma tupla (status, corpo) ou uma função request -> httpx.Response.
    """

    def __init__(self, regras):
        self.regras = regras
        self.chamadas = []

    def __call__(self, request):
        url = str(request.url)
        self.chamadas.append(request)
        for trecho, resposta in self.regras:
            if trecho in url:
                if callable(resposta):
                    return resposta(request)
                status, corpo = resposta if isinstance(resposta, tuple) else (200, resposta)
                return httpx.Response(status, json=corpo)
        raise AssertionError(f"URL inesperada: {url}")


@pytest.fixture
def cliente_com(tmp_path):
    def fazer(regras, cache=True):
        rot = Roteador(regras)
        cli = Cliente(
            Cache(tmp_path / "c.sqlite") if cache else None,
            transport=httpx.MockTransport(rot),
            dormir=lambda s: None,
        )
        return cli, rot

    return fazer
