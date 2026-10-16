from __future__ import annotations

import math
from collections.abc import Iterable


class ConfirmedTrackFilter:
    """Passes a track through only after it has been detected in enough frames.

    Once confirmed, a track stays confirmed while its ID is alive. State for an
    ID is dropped after it has not been seen for `forget_seconds`.
    Time is counted in frames of the source video, not wall-clock time.
    """

    def __init__(self, fps: float, min_seconds: float = 0.5, forget_seconds: float = 10.0):
        if fps <= 0:
            raise ValueError("fps must be positive")
        self.min_hits = max(1, math.ceil(fps * min_seconds))
        self.forget_frames = max(1, math.ceil(fps * forget_seconds))
        self._hits: dict[int, int] = {}
        self._last_seen: dict[int, int] = {}
        self._confirmed: set[int] = set()
        self._frame = -1

    def update(self, tracks: Iterable) -> list:
        """Call once per frame with all tracks. Returns only confirmed ones."""
        self._frame += 1
        out = []
        for t in tracks:
            hits = self._hits.get(t.id, 0) + 1
            self._hits[t.id] = hits
            self._last_seen[t.id] = self._frame
            if hits >= self.min_hits:
                self._confirmed.add(t.id)
            if t.id in self._confirmed:
                out.append(t)
        self._forget_stale()
        return out

    @property
    def confirmed_ids(self) -> set[int]:
        return set(self._confirmed)

    def reset(self) -> None:
        self._hits.clear()
        self._last_seen.clear()
        self._confirmed.clear()
        self._frame = -1

    def _forget_stale(self) -> None:
        limit = self._frame - self.forget_frames
        stale = [i for i, last in self._last_seen.items() if last < limit]
        for i in stale:
            del self._last_seen[i]
            self._hits.pop(i, None)
            self._confirmed.discard(i)