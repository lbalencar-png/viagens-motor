import pytest

from viagens_motor.config import Config, carregar

TOML = """
origem_padrao = "Recife"
projeto_url = "https://github.com/x/viagens-motor"
[iof]
cartao = 0.035
especie = 0.035
conta_global = 0.035
[conta_global]
spread = 0.01
[cartoes.a]
nome = "Cartão A"
spread = 0.0575
spread_verificar = true
iof_devolvido = true
fonte_spread = "comunicado do emissor"
"""


def test_carrega_e_resolve_meios(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(TOML, encoding="utf-8")
    cfg = carregar(p)
    assert cfg.origem_padrao == "Recife"
    m = cfg.meio("cartao:a")
    assert (m.nome, m.iof, m.spread, m.spread_verificar, m.iof_devolvido) == ("Cartão A", 0.035, 0.0575, True, True)
    assert cfg.meio("especie").spread is None
    assert cfg.meio("conta_global").spread == 0.01


def test_erros_claros(tmp_path):
    cfg = Config()
    with pytest.raises(ValueError, match="IOF de 'cartao' não configurado"):
        cfg.meio("cartao:a")
    p = tmp_path / "c.toml"
    p.write_text(TOML, encoding="utf-8")
    cfg = carregar(p)
    with pytest.raises(ValueError, match="cartão 'nubank' não está no motor-config.toml"):
        cfg.meio("cartao:nubank")
    with pytest.raises(ValueError, match="meio desconhecido"):
        cfg.meio("pix")


def test_arquivo_ausente_da_config_vazia(tmp_path):
    assert carregar(tmp_path / "nao-existe.toml") == Config()


def test_chave_google_pela_variavel(monkeypatch):
    cfg = Config(google_chave_env="MINHA_CHAVE")
    monkeypatch.delenv("MINHA_CHAVE", raising=False)
    assert cfg.google_chave() is None
    monkeypatch.setenv("MINHA_CHAVE", "abc")
    assert cfg.google_chave() == "abc"
