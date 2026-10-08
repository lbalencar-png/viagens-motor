from viagens_motor.cache import Cache


def test_guarda_e_expira(tmp_path):
    agora = [1000.0]
    c = Cache(tmp_path / "c.sqlite", relogio=lambda: agora[0])
    c.put("k", {"a": 1}, ttl=60)
    assert c.get("k") == ({"a": 1}, 1000.0)
    agora[0] = 1061.0
    assert c.get("k") is None


def test_chave_ausente(tmp_path):
    assert Cache(tmp_path / "c.sqlite").get("nada") is None


def test_threads_gravam_e_leem_sem_erro(tmp_path):
    import threading

    c = Cache(tmp_path / "c.sqlite")
    erros = []

    def trabalhar(n):
        try:
            for i in range(50):
                c.put(f"{n}-{i}", {"i": i}, ttl=60)
                assert c.get(f"{n}-{i}")[0] == {"i": i}
        except Exception as e:  # noqa: BLE001
            erros.append(e)

    ts = [threading.Thread(target=trabalhar, args=(n,)) for n in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert erros == []
