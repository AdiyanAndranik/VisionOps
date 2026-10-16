from types import SimpleNamespace

from src.pipeline.confirm import ConfirmedTrackFilter


def T(i):
    return SimpleNamespace(id=i)


def make(fps=10, min_seconds=0.5, forget_seconds=2.0):
    # fps=10, 0.5 s -> min_hits = 5
    return ConfirmedTrackFilter(fps, min_seconds, forget_seconds)


def test_not_confirmed_before_min_hits():
    f = make()
    for _ in range(4):
        assert f.update([T(1)]) == []


def test_confirmed_exactly_at_min_hits():
    f = make()
    for _ in range(4):
        f.update([T(1)])
    assert [t.id for t in f.update([T(1)])] == [1]


def test_flicker_track_never_passes():
    f = make()
    for _ in range(3):
        f.update([T(7)])
    for _ in range(20):
        assert f.update([]) == []
    assert 7 not in f.confirmed_ids


def test_stays_confirmed_after_short_gap():
    f = make()
    for _ in range(5):
        f.update([T(1)])
    for _ in range(5):
        f.update([])
    assert [t.id for t in f.update([T(1)])] == [1]


def test_forgotten_after_long_absence():
    f = make()  # forget after 20 frames
    for _ in range(5):
        f.update([T(1)])
    for _ in range(30):
        f.update([])
    assert f.update([T(1)]) == []


def test_ids_are_independent():
    f = make()
    for _ in range(5):
        out = f.update([T(1), T(2)])
    assert {t.id for t in out} == {1, 2}
    out = f.update([T(3)])
    assert out == []