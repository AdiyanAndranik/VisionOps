from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np


class HeatmapAccumulator:
    """Sums presence time (seconds) per grid cell, using each track's foot point.

    Feed it the confirmed tracks once per frame. Cells are `cell` px wide in
    source-frame pixels.
    """

    def __init__(self, width: int, height: int, fps: float, cell: int = 8, edge_margin: int = 0):
        if fps <= 0 or cell <= 0:
            raise ValueError("fps and cell must be positive")
        self.edge_margin = edge_margin
        self.width = width
        self.height = height
        self.cell = cell
        self.seconds_per_frame = 1.0 / fps
        self.grid = np.zeros((math.ceil(height / cell), math.ceil(width / cell)), dtype=np.float32)

    def update(self, tracks: Iterable) -> None:
        for t in tracks:
            x, y = t.foot
            if not (0 <= x < self.width and 0 <= y < self.height - self.edge_margin):
                continue
            self.grid[int(y // self.cell), int(x // self.cell)] += self.seconds_per_frame

    @property
    def total_seconds(self) -> float:
        return float(self.grid.sum())

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, self.grid)


def render_overlay(
    frame: np.ndarray,
    grid: np.ndarray,
    cell: int,
    sigma_cells: float = 2.0,
    alpha: float = 0.6,
    percentile: float = 99.0,
) -> tuple[np.ndarray, float]:
    """Blend the heatmap over a frame. Returns (image, scale_seconds).

    Colors are scaled to the given percentile of the non-empty cells, so one
    extreme cell does not wash out the rest. scale_seconds is the value that
    maps to the hottest color. Cold areas stay transparent.
    """
    h, w = frame.shape[:2]
    heat = cv2.GaussianBlur(grid, (0, 0), sigma_cells)
    nonzero = heat[heat > 1e-6]
    if nonzero.size == 0:
        return frame.copy(), 0.0
    top = float(np.percentile(nonzero, percentile))
    norm = np.clip(heat / top, 0.0, 1.0)
    norm = cv2.resize(norm, (w, h), interpolation=cv2.INTER_LINEAR)
    color = cv2.applyColorMap((norm * 255).astype(np.uint8), cv2.COLORMAP_JET)
    a = (norm * alpha)[..., None]
    out = frame.astype(np.float32) * (1 - a) + color.astype(np.float32) * a
    return out.astype(np.uint8), top