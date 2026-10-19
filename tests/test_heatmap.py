from types import SimpleNamespace

import numpy as np

from src.analytics.heatmap import HeatmapAccumulator, render_overlay


def track(i, x, y):
    return SimpleNamespace(id=i, foot=(x, y))


def test_adds_seconds_to_the_right_cell():
    acc = HeatmapAccumulator(100, 80, fps=10, cell=10)
    acc.update([track(1, 25, 35)])
    acc.update([track(1, 26, 36)])
    assert abs(acc.grid[3, 2] - 0.2) < 1e-6
    assert abs(acc.total_seconds - 0.2) < 1e-6


def test_ignores_points_outside_the_frame():
    acc = HeatmapAccumulator(100, 80, fps=10, cell=10)
    acc.update([track(1, -1, 5), track(2, 100, 5), track(3, 5, 80)])
    assert acc.total_seconds == 0


def test_empty_grid_returns_frame_unchanged():
    frame = np.full((80, 100, 3), 7, dtype=np.uint8)
    acc = HeatmapAccumulator(100, 80, fps=10, cell=10)
    img, scale = render_overlay(frame, acc.grid, 10)
    assert scale == 0.0
    assert (img == frame).all()


def test_overlay_keeps_shape_and_colors_the_hot_spot():
    frame = np.zeros((80, 100, 3), dtype=np.uint8)
    acc = HeatmapAccumulator(100, 80, fps=10, cell=10)
    for _ in range(50):
        acc.update([track(1, 55, 35)])
    img, scale = render_overlay(frame, acc.grid, 10)
    assert img.shape == frame.shape
    assert scale > 0
    assert img[35, 55].sum() > img[5, 5].sum()


def test_skips_feet_on_the_bottom_edge():
    acc = HeatmapAccumulator(100, 80, fps=10, cell=10, edge_margin=4)
    acc.update([track(1, 50, 78), track(2, 50, 70)])
    assert abs(acc.total_seconds - 0.1) < 1e-6