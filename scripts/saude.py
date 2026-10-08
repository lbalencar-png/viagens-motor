"""Verificador diário: uma consulta fixa por fonte; grava status.json e o log."""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ATRIBUICAO = (
    "© colaboradores do OpenStreetMap (openstreetmap.org/copyright; corrigir: openstreetmap.org/fixthemap), "
    "Photon, OSRM da FOSSGIS, Transitous (transitous.org/sources), Open-Meteo, Banco Central do Brasil, BCE via Frankfurter, Nager.Date"
)


def _proxima_semana() -> str:
    return (date.today() + timedelta(days=7)).isoformat()


CHECAGENS = [
    ("Photon", lambda m: m.lugar("Marco Zero, Recife")),
    ("OSRM FOSSGIS", lambda m: m.rota("-8.0631,-34.8711", "-8.0578,-34.8829", "pe")),
    ("Transitous", lambda m: m.rota("50.0833,14.4353", "48.1850,16.3760", "transporte", _proxima_semana() + "T07:00")),
    ("Open-Meteo", lambda m: m.clima("-8.05,-34.9", date.today().isoformat(), date.today().isoformat())),
    ("PTAX", lambda m: m.cambio("EUR")),
    ("BCE (Frankfurter)", lambda m: m.cambio("CZK")),
    ("Nager.Date", lambda m: m.calendario("BR", f"{date.today().year}-01-01", f"{date.today().year}-12-31")),
]


def verificar(m) -> dict:
    fontes = {}
    for nome, f in CHECAGENS:
        t0 = time.monotonic()
        try:
            r = f(m)
        except Exception as e:  # o verificador nunca para no meio
            r = {"ok": False, "erro": f"{type(e).__name__}: {e}"}
        item = {"ok": bool(r.get("ok")), "ms": round((time.monotonic() - t0) * 1000)}
        if not r.get("ok"):
            item["erro"] = str(r.get("erro", ""))[:300]
        fontes[nome] = item
    return {
        "ok": all(v["ok"] for v in fontes.values()),
        "quando": datetime.now().isoformat(timespec="seconds"),
        "fontes": fontes,
        "google_ligado": m.cfg.google_chave() is not None,
        "atribuicao": ATRIBUICAO,
    }


def main() -> int:
    from viagens_motor.ferramentas import criar_motor_sem_memoria, pasta_dados

    st = verificar(criar_motor_sem_memoria())
    texto = json.dumps(st, ensure_ascii=False, indent=1)
    try:
        pasta_dados().mkdir(parents=True, exist_ok=True)
        (pasta_dados() / "status.json").write_text(texto, encoding="utf-8")
        log = Path.home() / "Library/Logs/viagens-motor-saude.log"
        falhas = [k for k, v in st["fontes"].items() if not v["ok"]]
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{st['quando']} ok={st['ok']} falhas={','.join(falhas) or '-'}\n")
    except OSError as e:
        print(f"aviso: não foi possível gravar status.json/log: {e}", file=sys.stderr)
    print(texto)
    return 0 if st["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
