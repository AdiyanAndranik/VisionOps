from __future__ import annotations

import json
from pathlib import Path

from src.pipeline.dwell import ZoneEvent
from src.pipeline.lines import CrossEvent


def line_event(source: str, e: CrossEvent, fps: float) -> dict:
    """time_s is when the crossing was confirmed, about confirm_seconds after
    the person really crossed. x, y is where the path met the line."""
    return {
        "type": "line_cross",
        "source": source,
        "track_id": e.track_id,
        "time_s": round(e.frame / fps, 3),
        "frame": e.frame,
        "line": e.line,
        "direction": e.direction,
        "x": round(e.x, 1),
        "y": round(e.y, 1),
    }


def zone_event(source: str, e: ZoneEvent) -> dict:
    """enter: time_s is the first frame inside. exit: time_s is the last frame inside."""
    d = {
        "type": f"zone_{e.kind}",
        "source": source,
        "track_id": e.track_id,
        "time_s": round(e.time_s, 3),
        "frame": e.frame,
        "zone": e.zone,
        "start_s": round(e.start_s, 3),
    }
    if e.dwell_s is not None:
        d["dwell_s"] = round(e.dwell_s, 3)
    return d


class JsonlWriter:
    """One JSON object per line. Overwrites the file if it exists."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.path.open("w", encoding="utf-8")
        self.count = 0

    def write(self, event: dict) -> None:
        self._f.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._f.flush()
        self.count += 1

    def close(self) -> None:
        self._f.close()

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()