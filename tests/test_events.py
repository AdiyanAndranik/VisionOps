import json
from types import SimpleNamespace

import pytest

from src.events.schema import JsonlWriter
from src.pipeline.lines import Line, LineCounter
from src.pipeline.zones import Zone, ZoneSet
from src.worker.pipeline import EventPipeline

FPS = 10
SQUARE = [(0, 0), (400, 0), (400, 400), (0, 400)]


def T(i, x, y):
    return SimpleNamespace(id=i, foot=(x, y))


def make():
    zones = ZoneSet([Zone.from_points("z", SQUARE)])
    lines = LineCounter(
        [Line("v", (200, 0), (200, 400), pos_label="right", neg_label="left")],
        fps=FPS,
        confirm_seconds=0.5,
    )
    return EventPipeline("test.mp4", FPS, zones, lines)


def run(pipe, frames):
    events = []
    for tracks in frames:
        events += pipe.update(tracks)
    events += pipe.finish()
    return events


def test_walk_across_line_inside_zone():
    walk = [[T(1, x, 100)] for x in range(50, 360, 10)]  # 31 frames
    ev = run(make(), walk)
    assert sorted(e["type"] for e in ev) == ["line_cross", "zone_enter", "zone_exit"]

    cross = next(e for e in ev if e["type"] == "line_cross")
    assert cross["direction"] == "right"
    assert cross["line"] == "v"
    assert cross["source"] == "test.mp4"
    assert cross["track_id"] == 1
    assert cross["x"] == pytest.approx(200, abs=1)

    leave = next(e for e in ev if e["type"] == "zone_exit")
    assert leave["zone"] == "z"
    # confirmed from frame 4, last inside frame 30 -> 27 frames
    assert leave["dwell_s"] == pytest.approx(2.7)


def test_short_lived_track_gives_no_events():
    assert run(make(), [[T(2, 50, 100)]] * 3) == []


def test_jsonl_writer(tmp_path):
    p = tmp_path / "sub" / "events.jsonl"
    with JsonlWriter(p) as w:
        w.write({"a": 1})
        w.write({"b": "ж"})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert [json.loads(l) for l in lines] == [{"a": 1}, {"b": "ж"}]
    assert w.count == 2