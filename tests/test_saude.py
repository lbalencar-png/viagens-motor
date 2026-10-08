import importlib.util
from pathlib import Path


def carregar_saude():
    spec = importlib.util.spec_from_file_location("saude", Path(__file__).parents[1] / "scripts/saude.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MotorFalso:
    def __init__(self, cai):
        self.cai = cai
        self.cfg = type("C", (), {"google_chave": lambda self: None})()

    def __getattr__(self, nome):
        def f(*a, **k):
            return {"ok": nome not in self.cai, "fonte": nome, "erro": "x"}

        return f


def test_verificar_marca_falhas():
    saude = carregar_saude()
    r = saude.verificar(MotorFalso(cai={"clima"}))
    assert r["ok"] is False
    assert r["fontes"]["Open-Meteo"]["ok"] is False and r["fontes"]["Photon"]["ok"] is True
    assert set(r["fontes"]) == {"Photon", "OSRM FOSSGIS", "Transitous", "Open-Meteo", "PTAX", "BCE (Frankfurter)", "Nager.Date"}
    assert "OpenStreetMap" in r["atribuicao"] and r["google_ligado"] is False


def test_motor_do_verificador_nao_usa_memoria(monkeypatch, tmp_path):
    from viagens_motor.ferramentas import criar_motor_sem_memoria

    monkeypatch.setenv("VIAGENS_MOTOR_CONFIG", str(tmp_path / "inexistente.toml"))
    assert criar_motor_sem_memoria().cli.cache is None


def test_main_usa_motor_sem_memoria(monkeypatch, tmp_path, capsys):
    saude = carregar_saude()
    usados = []
    import viagens_motor.ferramentas as f

    def fake():
        usados.append(1)
        return MotorFalso(cai=set())

    monkeypatch.setattr(f, "criar_motor_sem_memoria", fake)
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert saude.main() == 0 and usados == [1]
    assert (tmp_path / "status.json").exists()


def test_main_avisa_em_stderr_quando_nao_grava(monkeypatch, tmp_path, capsys):
    saude = carregar_saude()
    import viagens_motor.ferramentas as f

    monkeypatch.setattr(f, "criar_motor_sem_memoria", lambda: MotorFalso(cai=set()))
    arquivo = tmp_path / "arquivo"
    arquivo.write_text("x")
    monkeypatch.setenv("VIAGENS_MOTOR_DADOS", str(arquivo / "sub"))
    saude.main()
    assert "não foi possível gravar" in capsys.readouterr().err
