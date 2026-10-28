"""Per-run images for the dashboard: a background frame and a presence heatmap.

Files go to <root>/<run_id>/frame.jpg and heatmap.jpg. The api serves them.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import cv2
import numpy as np

from src.analytics.heatmap import HeatmapAccumulator, render_overlay

CELL = 8
SIGMA = 2.0
EDGE_MARGIN = 4
JPEG_QUALITY = 90
FRAME_NAME = "frame.jpg"
HEATMAP_NAME = "heatmap.jpg"
VIDEO_NAME = "annotated.mp4"
VIDEO_TMP_NAME = "annotated.tmp.mp4"


def _write(path: Path, img: np.ndarray) -> None:
    if not cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]):
        raise RuntimeError(f"could not write {path}")


class ArtifactWriter:
    def __init__(self, root: str | Path, run_id: int, fps: float):
        self.dir = Path(root) / str(run_id)
        self.dir.mkdir(parents=True, exist_ok=True)
        # run ids restart after `docker compose down -v`, so never leave an
        # old run's images behind for a new run with the same id
        for name in (FRAME_NAME, HEATMAP_NAME, VIDEO_NAME, VIDEO_TMP_NAME):
            (self.dir / name).unlink(missing_ok=True)
        self.fps = fps
        self.background: np.ndarray | None = None
        self.heat: HeatmapAccumulator | None = None

    def update(self, frame: np.ndarray, confirmed: Iterable) -> None:
        """Call once per frame with the frame and its confirmed tracks."""
        if self.heat is None:
            h, w = frame.shape[:2]
            self.background = frame.copy()
            self.heat = HeatmapAccumulator(w, h, self.fps, cell=CELL, edge_margin=EDGE_MARGIN)
            _write(self.dir / FRAME_NAME, self.background)
        self.heat.update(confirmed)

    def finish(self) -> None:
        """Render the heatmap over the first frame. Does nothing if no frame was seen."""
        if self.heat is None or self.background is None:
            return
        img, _scale = render_overlay(self.background, self.heat.grid, CELL, sigma_cells=SIGMA)
        _write(self.dir / HEATMAP_NAME, img)

        