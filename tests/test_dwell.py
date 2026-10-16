from types import SimpleNamespace

import pytest

from src.pipeline.dwell import DwellTracker
from src.pipeline.zones import Zone, ZoneSet

SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]
IN = (50, 50)
OUT = (300, 300)


def T(i, pos):
    return SimpleNamespace(id=i, foot=pos)


def make(zones=None):
    zs = ZoneSet(zones or [Zone.from_points("a", SQUARE)])
    # fps=10: enter 3 frames, exit 5 frames, gap limit 4 frames
    return DwellTracker(zs, fps=10, enter_seconds=0.3, exit_seconds=0.5, max_gap_seconds=0.4)


def feed(d, positions, tid=1):
    ev = []
    for p in positions:
        ev += d.update([] if p is None else [T(tid, p)])
    return ev


def kinds(ev):
    return [e.kind for e in ev]


def test_short_visit_gives_no_events():
    d = make()
    assert feed(d, [IN, IN] + [OUT] * 10) == []
    assert d.finish() == []


def test_enter_after_debounce_with_real_start():
    d = make()
    assert feed(d, [IN] * 2) == []
    ev = feed(d, [IN])
    assert len(ev) == 1
    assert ev[0].kind == "enter"
    assert ev[0].frame == 0
    assert ev[0].dwell_s is None


def test_exit_and_dwell_do_not_include_exit_wait():
    d = make()
    ev = feed(d, [IN] * 10 + [OUT] * 5)
    assert kinds(ev) == ["enter", "exit"]
    assert ev[1].frame == 9
    assert ev[1].dwell_s == pytest.approx(1.0)
    assert ev[1].start_s == pytest.approx(0.0)


def test_short_flicker_out_does_not_exit():
    d = make()
    ev = feed(d, [IN] * 5 + [OUT] * 3 + [IN] * 5)
    assert kinds(ev) == ["enter"]
    ev = d.finish()
    assert kinds(ev) == ["exit"]
    assert ev[0].dwell_s == pytest.approx(1.3)


def test_lost_track_closes_at_last_frame_inside():
    d = make()
    ev = feed(d, [IN] * 5 + [None] * 10)
    assert kinds(ev) == ["enter", "exit"]
    assert ev[1].frame == 4
    assert ev[1].dwell_s == pytest.approx(0.5)


def test_return_after_gap_is_a_new_visit():
    d = make()
    ev = feed(d, [IN] * 5 + [None] * 10 + [IN] * 5)
    assert kinds(ev) == ["enter", "exit", "enter"]
    assert kinds(d.finish()) == ["exit"]


def test_finish_closes_open_visit():
    d = make()
    feed(d, [IN] * 6)
    ev = d.finish()
    assert kinds(ev) == ["exit"]
    assert ev[0].dwell_s == pytest.approx(0.6)


def test_overlapping_zones_both_tracked():
    a = Zone.from_points("a", SQUARE)
    b = Zone.from_points("b", [(50, 50), (150, 50), (150, 150), (50, 150)])
    d = make([a, b])
    ev = feed(d, [(75, 75)] * 3)
    assert sorted(e.zone for e in ev) == ["a", "b"]


def test_ids_are_independent():
    d = make()
    ev = []
    for _ in range(3):
        ev += d.update([T(1, IN), T(2, OUT)])
    assert [(e.kind, e.track_id) for e in ev] == [("enter", 1)]


def test_bad_fps_rejected():
    with pytest.raises(ValueError):
        DwellTracker(ZoneSet([Zone.from_points("a", SQUARE)]), fps=0)