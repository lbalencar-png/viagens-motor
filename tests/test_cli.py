import json

from viagens_motor.cli import main


def test_configuracao_malformada_vira_json_com_ok_false(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "c.toml"
    cfg.write_text("[iof\nquebrado", encoding="utf-8")
    monkeypatch.setenv("VIAGENS_MOTOR_CONFIG", str(cfg))
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    assert main(["lugar", "Louvre"]) == 1
    r = json.loads(capsys.readouterr().out)
    assert r["ok"] is False and r["fonte"] == "viagens-motor" and "configuração inválida" in r["erro"]


def test_custos_com_arquivo_inexistente(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VIAGENS_MOTOR_CONFIG", str(tmp_path / "nao-existe.toml"))
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    assert main(["custos", str(tmp_path / "nao-existe.json")]) == 1
    r = json.loads(capsys.readouterr().out)
    assert r["ok"] is False and "arquivo de custos ilegível" in r["erro"]


def test_custos_com_json_quebrado(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VIAGENS_MOTOR_CONFIG", str(tmp_path / "nao-existe.toml"))
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    arq = tmp_path / "itens.json"
    arq.write_text("[{", encoding="utf-8")
    assert main(["custos", str(arq)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
