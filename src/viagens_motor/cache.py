"""Memória local das consultas (SQLite), com validade por registro."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable


class Cache:
    def __init__(self, caminho: Path | str, relogio: Callable[[], float] = time.time):
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(caminho), check_same_thread=False)
        self._db.execute(
            "create table if not exists memoria (chave text primary key, valor text, gravado real, expira real)"
        )
        self._relogio = relogio
        self._trava = threading.Lock()  # a conexão é compartilhada entre as threads do servidor

    def get(self, chave: str) -> tuple[Any, float] | None:
        with self._trava:
            linha = self._db.execute(
                "select valor, gravado, expira from memoria where chave = ?", (chave,)
            ).fetchone()
        if linha is None or linha[2] < self._relogio():
            return None
        return json.loads(linha[0]), linha[1]

    def put(self, chave: str, valor: Any, ttl: float) -> None:
        agora = self._relogio()
        texto = json.dumps(valor, ensure_ascii=False)
        with self._trava:
            self._db.execute("insert or replace into memoria values (?, ?, ?, ?)", (chave, texto, agora, agora + ttl))
            self._db.commit()
