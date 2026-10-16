from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from src.pipeline.zones import ZoneSet


def _frames(fps: float, seconds: float) -> int:
    return max(1, math.ceil(round(fps * seconds, 6)))


@dataclass(frozen=True)
class ZoneEvent:
    kind: str  # "enter" or "exit"
    track_id: int
    zone: str
    frame: int  # enter: first frame inside; exit: last frame inside
    time_s: float  # same moment in seconds
    start_s: float  # when the visit started
    dwell_s: float | None  # only on exit


@dataclass
class _Visit:
    inside: bool = False  # confirmed inside
    run: int = 0  # consecutive frames inside, before confirmation
    start: int = 0  # first frame of the current inside run
    out: int = 0  # consecutive frames outside, after confirmation
    last_in: int = 0  # last frame seen inside


class DwellTracker:
    """Turns foot points into enter/exit events and dwell times per zone.

    Time is counted in frames of the source video. Zones may overlap, each
    zone is tracked independently. Call update() once per frame with
    confirmed tracks, and finish() after the last frame.
    """

    def __init__(
        self,
        zones: ZoneSet,
        fps: float,
        enter_seconds: float = 0.3,
        exit_seconds: float = 0.5,
        max_gap_seconds: float = 0.4,
    ):
        if fps <= 0:
            raise ValueError("fps must be positive")
        if min(enter_seconds, exit_seconds, max_gap_seconds) < 0:
            raise ValueError("seconds must not be negative")
        self.zones = zones
        self.fps = fps
        self.enter_frames = _frames(fps, enter_seconds)
        self.exit_frames = _frames(fps, exit_seconds)
        self.max_gap_frames = _frames(fps, max_gap_seconds)
        self._visits: dict[int, dict[str, _Visit]] = {}
        self._last_seen: dict[int, int] = {}
        self._frame = -1

    def update(self, tracks: Iterable) -> list[ZoneEvent]:
        self._frame += 1
        events: list[ZoneEvent] = []
        for t in tracks:
            self._last_seen[t.id] = self._frame
            here = set(self.zones.zones_at(*t.foot))
            per_zone = self._visits.setdefault(t.id, {})
            for z in self.zones.zones:
                v = per_zone.setdefault(z.name, _Visit())
                ev = (
                    self._inside(t.id, z.name, v)
                    if z.name in here
                    else self._outside(t.id, z.name, v)
                )
                if ev:
                    events.append(ev)
        events += self._close_lost()
        return events

    def finish(self) -> list[ZoneEvent]:
        """Closes all open visits. Call once after the last frame."""
        events: list[ZoneEvent] = []
        for tid in list(self._visits):
            events += self._close_all(tid)
        self._visits.clear()
        self._last_seen.clear()
        return events

    def _inside(self, tid: int, zone: str, v: _Visit) -> ZoneEvent | None:
        v.last_in = self._frame
        if v.inside:
            v.out = 0
            return None
        if v.run == 0:
            v.start = self._frame
        v.run += 1
        if v.run < self.enter_frames:
            return None
        v.inside, v.out = True, 0
        s = v.start / self.fps
        return ZoneEvent("enter", tid, zone, v.start, s, s, None)

    def _outside(self, tid: int, zone: str, v: _Visit) -> ZoneEvent | None:
        if not v.inside:
            v.run = 0
            return None
        v.out += 1
        if v.out < self.exit_frames:
            return None
        return self._close(tid, zone, v)

    def _close(self, tid: int, zone: str, v: _Visit) -> ZoneEvent:
        ev = ZoneEvent(
            "exit",
            tid,
            zone,
            v.last_in,
            v.last_in / self.fps,
            v.start / self.fps,
            (v.last_in - v.start + 1) / self.fps,
        )
        v.inside, v.run, v.out = False, 0, 0
        return ev

    def _close_all(self, tid: int) -> list[ZoneEvent]:
        return [
            self._close(tid, zone, v)
            for zone, v in self._visits.get(tid, {}).items()
            if v.inside
        ]

    def _close_lost(self) -> list[ZoneEvent]:
        limit = self._frame - self.max_gap_frames
        events: list[ZoneEvent] = []
        for tid in [i for i, last in self._last_seen.items() if last < limit]:
            events += self._close_all(tid)
            del self._last_seen[tid]
            self._visits.pop(tid, None)
        return events