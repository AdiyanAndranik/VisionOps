import json
from types import SimpleNamespace

import pytest

from src.pipeline.lines import Line, LineCounter

# vertical line x=100, a=(100,0) -> b=(100,200); screen right is positive
V = Line("v", (100, 0), (100, 200), pos_label="right", neg_label="left")


def T(i, x, y):
    return SimpleNamespace(id=i, foot=(x, y))


def make(fps=10, margin=15, forget=2.0, confirm=0.0):
    return LineCounter([V], fps=fps, margin_px=margin, forget_seconds=forget, confirm_seconds=confirm)


def walk(counter, path, tid=1):
    events = []
    for x, y in path:
        events += counter.update([T(tid, x, y)])
    return events


def test_left_to_right_counts_once():
    c = make()
    ev = walk(c, [(50, 100), (80, 100), (110, 100), (140, 100), (170, 100)])
    assert len(ev) == 1
    assert ev[0].direction == "right"
    assert abs(ev[0].x - 100) < 1e-6
    assert c.counts["v"] == {"right": 1, "left": 0}


def test_right_to_left_counts_once():
    c = make()
    ev = walk(c, [(170, 100), (140, 100), (110, 100), (80, 100), (50, 100)])
    assert [e.direction for e in ev] == ["left"]


def test_jitter_inside_margin_no_event():
    c = make()
    assert walk(c, [(50, 100), (95, 100), (105, 100), (96, 100), (104, 100)]) == []


def test_there_and_back_counts_twice():
    c = make()
    ev = walk(c, [(50, 100), (130, 100), (50, 100)])
    assert [e.direction for e in ev] == ["right", "left"]


def test_walking_around_the_end_does_not_count():
    c = make()
    assert walk(c, [(50, 300), (150, 300)]) == []


def test_ids_are_independent():
    c = make()
    c.update([T(1, 50, 100), T(2, 150, 100)])
    ev = c.update([T(1, 150, 100), T(2, 50, 100)])
    assert sorted((e.track_id, e.direction) for e in ev) == [(1, "right"), (2, "left")]


def test_state_forgotten_after_long_absence():
    c = make()  # forget after 20 frames
    c.update([T(1, 50, 100)])
    for _ in range(30):
        c.update([])
    assert c.update([T(1, 150, 100)]) == []


def test_horizontal_line_positive_side_is_above():
    h = Line("h", (0, 100), (200, 100))
    assert h.signed_distance(50, 50) > 0
    assert h.signed_distance(50, 150) < 0


def test_zero_length_rejected():
    with pytest.raises(ValueError):
        Line("x", (5, 5), (5, 5))


def test_duplicate_names_rejected():
    with pytest.raises(ValueError):
        LineCounter([V, V], fps=10)


def test_from_json(tmp_path):
    p = tmp_path / "lines.json"
    p.write_text(
        json.dumps({"lines": [{"name": "v", "points": [[100, 0], [100, 200]]}]}),
        encoding="utf-8",
    )
    c = LineCounter.from_json(p, fps=10)
    assert [l.name for l in c.lines] == ["v"]


# --- confirm_seconds (fps=10, 0.5 s -> 5 frames) ---


def test_short_stay_on_other_side_ignored():
    c = make(confirm=0.5)
    ev = walk(c, [(50, 100)] * 5 + [(130, 100)] * 4 + [(50, 100)])
    assert ev == []


def test_flicker_across_line_no_events():
    c = make(confirm=0.5)
    ev = walk(c, [(50, 100)] * 5 + [(130, 100), (50, 100)] * 10)
    assert ev == []
    assert c.counts["v"] == {"right": 0, "left": 0}


def test_crossing_counted_after_n_frames():
    c = make(confirm=0.5)
    assert walk(c, [(50, 100)] * 5 + [(130, 100)] * 4) == []
    ev = c.update([T(1, 130, 100)])
    assert len(ev) == 1
    assert ev[0].direction == "right"
    assert ev[0].frame == 9
    assert abs(ev[0].x - 100) < 1e-6


def test_first_side_is_not_decided_by_one_frame():
    c = make(confirm=0.5)
    assert walk(c, [(130, 100)] + [(50, 100)] * 5) == []
    ev = walk(c, [(130, 100)] * 5)
    assert [e.direction for e in ev] == ["right"]


def test_gap_resets_pending_crossing():
    c = make(confirm=0.5)  # fps=10: 5 frames to confirm, gap limit 4 frames
    walk(c, [(50, 100)] * 5 + [(130, 100)] * 3)
    for _ in range(10):
        c.update([])
    assert walk(c, [(130, 100)] * 10) == []