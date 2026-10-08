from datetime import datetime, timezone

from viagens_motor.resultado import FonteErro, carimbo, falha, ok


def test_carimbo_em_hora_de_recife():
    dt = datetime(2026, 10, 7, 12, 5, tzinfo=timezone.utc)
    assert carimbo(dt) == "07/10/2026 09h05"


def test_ok_e_falha_tem_campos_comuns():
    r = ok("Fonte X", {"valor": 1}, aviso="cuidado")
    assert r["ok"] is True and r["fonte"] == "Fonte X" and r["valor"] == 1 and r["aviso"] == "cuidado"
    assert "consultado_em" in r
    f = falha("Fonte Y", "caiu")
    assert f == {"ok": False, "fonte": "Fonte Y", "erro": "caiu", "consultado_em": f["consultado_em"]}


def test_fonte_erro_guarda_a_fonte():
    e = FonteErro("Photon", "sem resultado")
    assert e.fonte == "Photon" and str(e) == "sem resultado"
