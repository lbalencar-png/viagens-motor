import asyncio

from viagens_motor.mcp_server import mcp


def test_ferramentas_registradas():
    async def listar():
        from fastmcp import Client

        async with Client(mcp) as c:
            return sorted(t.name for t in await c.list_tools())

    assert asyncio.run(listar()) == sorted(
        ["lugar", "rota", "distancias", "ordenar_dia", "clima", "cambio", "calendario", "custos", "spread_da_fatura", "saude"]
    )


def _chamar(nome, args=None):
    async def go():
        from fastmcp import Client

        async with Client(mcp) as c:
            r = await c.call_tool(nome, args or {}, raise_on_error=False)
            return r.data if r.data is not None else r.structured_content

    return asyncio.run(go())


def test_saude_sem_verificacao(tmp_path, monkeypatch):
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    r = _chamar("saude")
    assert r["ok"] is False and r["consultado_em"]


def test_saude_com_arquivo_corrompido(tmp_path, monkeypatch):
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    (tmp_path / "status.json").write_text("{nao e json", encoding="utf-8")
    r = _chamar("saude")
    assert r["ok"] is False and "ilegível" in r["erro"]


def test_configuracao_invalida_vira_falha(tmp_path, monkeypatch):
    import viagens_motor.mcp_server as srv

    cfg = tmp_path / "c.toml"
    cfg.write_text("[iof\nquebrado", encoding="utf-8")
    monkeypatch.setenv("VIAGENS_MOTOR_CONFIG", str(cfg))
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    monkeypatch.setattr(srv, "_motor", None)
    r = _chamar("lugar", {"texto": "Louvre"})
    assert r["ok"] is False and "configuração inválida" in r["erro"]


def test_saude_com_status_traz_fonte_e_ok_de_dentro(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    status = {"ok": False, "quando": "2026-10-07T08:35:00", "fontes": {"Photon": {"ok": False, "ms": 1, "erro": "x"}}}
    (tmp_path / "status.json").write_text(json.dumps(status), encoding="utf-8")
    r = _chamar("saude")
    assert r["ok"] is False and r["fonte"] == "verificação diária (status.json)" and r["consultado_em"]
    assert r["fontes"]["Photon"]["erro"] == "x"
    status["ok"] = True
    (tmp_path / "status.json").write_text(json.dumps(status), encoding="utf-8")
    assert _chamar("saude")["ok"] is True
