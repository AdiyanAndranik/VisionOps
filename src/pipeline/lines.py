from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Line:
    """A segment a->b in source-frame pixels.

    The positive side is the left-hand side when travelling a->b on screen
    (top->bottom: screen right is positive; left->right: above is positive).
    """

    name: str
    a: tuple[float, float]
    b: tuple[float, float]
    pos_label: str = "pos"  # label of a crossing that ends on the positive side
    neg_label: str = "neg"

    def __post_init__(self):
        if self.length == 0:
            raise ValueError(f"line '{self.name}': both points are the same")

    @property
    def length(self) -> float:
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

    def signed_distance(self, x: float, y: float) -> float:
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        return ((x - self.a[0]) * dy - (y - self.a[1]) * dx) / self.length

    def project(self, x: float, y: float) -> float:
        """Position along the segment: 0 at a, 1 at b."""
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        return ((x - self.a[0]) * dx + (y - self.a[1]) * dy) / (self.length ** 2)

    def normal(self) -> tuple[float, float]:
        """Unit vector pointing toward the positive side."""
        dx, dy = self.b[0] - self.a[0], self.b[1] - self.a[1]
        return dy / self.length, -dx / self.length

    @classmethod
    def from_dict(cls, d: dict) -> "Line":
        pts = d["points"]
        if len(pts) != 2:
            raise ValueError(f"line '{d['name']}': need exactly 2 points")
        return cls(
            d["name"],
            tuple(pts[0]),
            tuple(pts[1]),
            d.get("pos_label", "pos"),
            d.get("neg_label", "neg"),
        )


@dataclass(frozen=True)
class CrossEvent:
    track_id: int
    line: str
    direction: str  # label of the side the track ended on
    frame: int
    x: float
    y: float


@dataclass
class _SideState:
    side: int = 0        # confirmed side: 1 or -1, 0 = not known yet
    d: float = 0.0       # last position seen on the confirmed side
    x: float = 0.0
    y: float = 0.0
    cand_side: int = 0   # side the track is trying to switch to
    cand_n: int = 0      # frames in a row (outside the margin) on cand_side


class LineCounter:
    """Counts crossings of lines by tracked foot points.

    margin_px: a foot point closer than this to a line is ignored.
    confirm_seconds: a track must stay on a side for this long (counted in
        frames outside the margin) before that side is believed. This also
        applies to the first side a track is seen on. 0 = believe at once.
    """

    def __init__(
        self,
        lines: Iterable[Line],
        fps: float,
        margin_px: float = 15.0,
        forget_seconds: float = 10.0,
        confirm_seconds: float = 0.0,
        max_gap_seconds: float = 0.4,
    ):
        if fps <= 0:
            raise ValueError("fps must be positive")
        if confirm_seconds < 0:
            raise ValueError("confirm_seconds must not be negative")
        self.lines = list(lines)
        names = [l.name for l in self.lines]
        if len(set(names)) != len(names):
            raise ValueError("duplicate line names")
        self.margin_px = margin_px
        self.forget_frames = max(1, math.ceil(fps * forget_seconds))
        self.max_gap_frames = max(1, math.ceil(fps * max_gap_seconds))
        self.confirm_frames = max(1, math.ceil(fps * confirm_seconds))
        self.counts: dict[str, dict[str, int]] = {
            l.name: {l.pos_label: 0, l.neg_label: 0} for l in self.lines
        }
        self._state: dict[int, dict[str, _SideState]] = {}
        self._last_seen: dict[int, int] = {}
        self._frame = -1

    @classmethod
    def from_json(cls, path: str | Path, fps: float, **kw) -> "LineCounter":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([Line.from_dict(d) for d in data["lines"]], fps, **kw)

    def update(self, tracks: Iterable) -> list[CrossEvent]:
        """Call once per frame with confirmed tracks. Returns new crossings."""
        self._frame += 1
        events: list[CrossEvent] = []
        for t in tracks:
            prev = self._last_seen.get(t.id)
            self._last_seen[t.id] = self._frame
            fx, fy = t.foot
            states = self._state.setdefault(t.id, {})
            if prev is not None and self._frame - prev > self.max_gap_frames:
                states.clear()
            for line in self.lines:
                d = line.signed_distance(fx, fy)
                if abs(d) < self.margin_px:
                    continue  # too close to the line to trust the side
                side = 1 if d > 0 else -1
                st = states.setdefault(line.name, _SideState())

                if side == st.side:
                    # still on the confirmed side: cancel any pending switch
                    st.cand_n = 0
                    st.d, st.x, st.y = d, fx, fy
                    continue

                if side == st.cand_side:
                    st.cand_n += 1
                else:
                    st.cand_side, st.cand_n = side, 1
                if st.cand_n < self.confirm_frames:
                    continue

                # The new side is confirmed. If the track had a confirmed side
                # before, find where its path crossed the infinite line and
                # count it only if that point is within the segment.
                if st.side != 0:
                    s = st.d / (st.d - d)
                    cx, cy = st.x + s * (fx - st.x), st.y + s * (fy - st.y)
                    if 0.0 <= line.project(cx, cy) <= 1.0:
                        label = line.pos_label if side == 1 else line.neg_label
                        self.counts[line.name][label] += 1
                        events.append(CrossEvent(t.id, line.name, label, self._frame, cx, cy))
                st.side = side
                st.d, st.x, st.y = d, fx, fy
                st.cand_n = 0
        self._forget_stale()
        return events

    def reset(self) -> None:
        for c in self.counts.values():
            for k in c:
                c[k] = 0
        self._state.clear()
        self._last_seen.clear()
        self._frame = -1

    def _forget_stale(self) -> None:
        limit = self._frame - self.forget_frames
        stale = [i for i, last in self._last_seen.items() if last < limit]
        for i in stale:
            del self._last_seen[i]
            self._state.pop(i, None)