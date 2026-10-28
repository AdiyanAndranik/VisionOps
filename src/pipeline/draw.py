"""Draw tracks, zones, lines and a counter panel on a frame (in place).

Used by the worker's --annotate. Zones and lines are read from the same
json files the pipeline uses, so the video always shows what the events used.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np

TRAIL_LEN = 40
PRUNE_EVERY = 200
FONT = cv2.FONT_HERSHEY_SIMPLEX

ZONE_COLORS = [(255, 160, 60), (80, 200, 120), (60, 180, 255), (200, 120, 255)]
LINE_COLOR = (180, 90, 255)
ZONE_ALPHA = 0.18


def color_for(track_id: int) -> tuple[int, int, int]:
    return (
        (track_id * 67) % 200 + 55,
        (track_id * 131) % 200 + 55,
        (track_id * 197) % 200 + 55,
    )


def _text(img, text, org, scale, color, thick=2):
    """Text with a dark outline so it stays readable on any background."""
    cv2.putText(img, text, org, FONT, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, FONT, scale, color, thick, cv2.LINE_AA)


class Annotator:
    def __init__(self, zones_path: str, lines_path: str, width: int, height: int,
                 trail_len: int = TRAIL_LEN):
        self.width = width
        self.height = height
        zones = json.loads(Path(zones_path).read_text(encoding="utf-8"))["zones"]
        lines = json.loads(Path(lines_path).read_text(encoding="utf-8"))["lines"]
        self.zone_names = [z["name"] for z in zones]

        # The tint is static, so build it once: a colored layer plus a mask,
        # cut to the rows the zones really cover. Per frame it is one blend.
        overlay = np.zeros((height, width, 3), dtype=np.uint8)
        mask = np.zeros((height, width), dtype=np.uint8)
        self._zones = []
        for i, z in enumerate(zones):
            pts = np.array(z["points"], dtype=np.int32)
            col = ZONE_COLORS[i % len(ZONE_COLORS)]
            cv2.fillPoly(overlay, [pts], col)
            cv2.fillPoly(mask, [pts], 255)
            self._zones.append((z["name"], pts, col))
        rows = np.nonzero(mask.any(axis=1))[0]
        if len(rows):
            self._y0, self._y1 = int(rows[0]), int(rows[-1]) + 1
            self._overlay = np.ascontiguousarray(overlay[self._y0:self._y1])
            self._mask = np.ascontiguousarray(mask[self._y0:self._y1])
        else:
            self._overlay = None

        self._lines = [(ln["name"], tuple(ln["points"][0]), tuple(ln["points"][1])) for ln in lines]

        self.trail_len = trail_len
        self._trails = defaultdict(lambda: deque(maxlen=trail_len))
        self._last_seen: dict[int, int] = {}
        self._n = 0

    def _label_pos(self, text: str, x: int, y: int, scale: float) -> tuple[int, int]:
        (tw, th), _ = cv2.getTextSize(text, FONT, scale, 2)
        x = min(max(x, 10), self.width - tw - 10)
        y = min(max(y, th + 10), self.height - 10)
        return x, y

    def draw(self, frame: np.ndarray, tracks: Iterable, info_lines: list[str] | None = None) -> np.ndarray:
        """Draw on frame in place and return it. tracks are Track objects
        (the confirmed ones, so the video matches the events)."""
        # zone tint: full-width row band, so the slice stays contiguous for OpenCV
        if self._overlay is not None:
            band = frame[self._y0:self._y1]
            blended = cv2.addWeighted(band, 1 - ZONE_ALPHA, self._overlay, ZONE_ALPHA, 0)
            cv2.copyTo(blended, self._mask, band)

        # zone outlines and labels (label at the bottom-left, away from the lines)
        for name, pts, col in self._zones:
            cv2.polylines(frame, [pts], True, col, 2, cv2.LINE_AA)
            left = sorted(pts.tolist())[:2]  # the two left-most vertices
            vx, vy = max(left, key=lambda p: p[1])
            x, y = self._label_pos(name, vx + 12, vy - 14, 0.8)
            _text(frame, name, (x, y), 0.8, col)

        # lines (label at the right-most end)
        for name, a, b in self._lines:
            cv2.line(frame, a, b, LINE_COLOR, 3, cv2.LINE_AA)
            end = a if a[0] >= b[0] else b
            x, y = self._label_pos(name, end[0] + 10, end[1] - 12, 0.7)
            _text(frame, name, (x, y), 0.7, LINE_COLOR)

        # tracks
        for t in tracks:
            self._last_seen[t.id] = self._n
            self._trails[t.id].append(t.foot)
            col = color_for(t.id)
            p1, p2 = (int(t.x1), int(t.y1)), (int(t.x2), int(t.y2))
            cv2.rectangle(frame, p1, p2, col, 2)
            _text(frame, f"#{t.id}", (p1[0], max(p1[1] - 8, 24)), 0.7, col)
            pts = list(self._trails[t.id])
            for p, q in zip(pts, pts[1:]):
                cv2.line(frame, p, q, col, 2, cv2.LINE_AA)
            cv2.circle(frame, t.foot, 4, col, -1, cv2.LINE_AA)

        # counter panel, top left
        if info_lines:
            scale, pad, gap = 0.8, 12, 12
            sizes = [cv2.getTextSize(s, FONT, scale, 2)[0] for s in info_lines]
            box_w = max(w for w, _ in sizes) + 2 * pad
            box_h = sum(h for _, h in sizes) + gap * (len(info_lines) - 1) + 2 * pad
            roi = frame[10:10 + box_h, 10:10 + box_w]
            roi[:] = (roi * 0.35).astype(np.uint8)
            y = 10 + pad
            for s, (_, h) in zip(info_lines, sizes):
                y += h
                _text(frame, s, (10 + pad, y), scale, (255, 255, 255))
                y += gap

        self._n += 1
        if self._n % PRUNE_EVERY == 0:
            stale = [i for i, n in self._last_seen.items() if self._n - n > self.trail_len]
            for i in stale:
                self._last_seen.pop(i, None)
                self._trails.pop(i, None)
        return frame