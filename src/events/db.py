from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

_COLS = (
    "type", "track_id", "time_s", "frame",
    "zone", "line", "direction", "x", "y", "start_s", "dwell_s",
)
_INSERT_EVENT = (
    f"INSERT INTO events (run_id, {', '.join(_COLS)}) "
    f"VALUES (%s, {', '.join(['%s'] * len(_COLS))})"
)


def default_conninfo() -> str:
    """Connection string for the native worker. DATABASE_URL from .env (or the
    shell) wins; otherwise it is built from the POSTGRES_* variables."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return make_conninfo(
        host="127.0.0.1",
        port=os.environ.get("POSTGRES_HOST_PORT", "5433"),
        user=os.environ.get("POSTGRES_USER", "visionops"),
        password=os.environ.get("POSTGRES_PASSWORD", "visionops"),
        dbname=os.environ.get("POSTGRES_DB", "visionops"),
    )


class DbWriter:
    """Writes one run and its events to Postgres. Same write(event) shape as
    JsonlWriter. Autocommit, so each event is visible as soon as it is written."""

    def __init__(self, conninfo: str):
        self._conn = psycopg.connect(conninfo, autocommit=True)
        self.run_id: int | None = None
        self.count = 0

    def start_run(self, source: str, fps: float, width: int | None,
                  height: int | None, config: dict) -> int:
        row = self._conn.execute(
            "INSERT INTO runs (source, fps, width, height, config) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (source, fps, width, height, Jsonb(config)),
        ).fetchone()
        self.run_id = row[0]
        return self.run_id

    def write(self, event: dict) -> None:
        if self.run_id is None:
            raise RuntimeError("start_run() must be called before write()")
        values = [event.get(c) for c in _COLS]  # "source" is not stored per event
        self._conn.execute(_INSERT_EVENT, [self.run_id, *values])
        self.count += 1

    def finish_run(self, status: str, frame_count: int) -> None:
        if self.run_id is None:
            return
        self._conn.execute(
            "UPDATE runs SET status = %s, finished_at = now(), frame_count = %s WHERE id = %s",
            (status, frame_count, self.run_id),
        )

    def close(self) -> None:
        self._conn.close()