import json
from types import SimpleNamespace

import pytest

from src.pipeline.zones import Zone, ZoneSet

SQUARE = [(0, 0), (100, 0), (100, 100), (0, 100)]


def test_inside_and_outside():
    z = Zone.from_points("a", SQUARE)
    assert z.contains(50, 50)
    assert not z.contains(150, 50)
    assert not z.contains(-1, 50)


def test_border_counts_as_inside():
    z = Zone.from_points("a", SQUARE)
    assert z.contains(0, 50)
    assert z.contains(100, 100)


def test_too_few_points():
    with pytest.raises(ValueError):
        Zone.from_points("a", [(0, 0), (10, 10)])


def test_self_intersecting_polygon_rejected():
    with pytest.raises(ValueError):
        Zone.from_points("bad", [(0, 0), (10, 10), (10, 0), (0, 10)])


def test_zero_area_rejected():
    with pytest.raises(ValueError):
        Zone.from_points("flat", [(0, 0), (5, 5), (10, 10)])


def test_duplicate_names_rejected():
    z = Zone.from_points("a", SQUARE)
    with pytest.raises(ValueError):
        ZoneSet([z, z])


def test_overlapping_zones_both_returned():
    a = Zone.from_points("a", SQUARE)
    b = Zone.from_points("b", [(50, 50), (150, 50), (150, 150), (50, 150)])
    zs = ZoneSet([a, b])
    assert zs.zones_at(75, 75) == ["a", "b"]
    assert zs.zones_at(10, 10) == ["a"]
    assert zs.zones_at(500, 500) == []


def test_assign_uses_foot():
    zs = ZoneSet([Zone.from_points("a", SQUARE)])
    tracks = [
        SimpleNamespace(id=1, foot=(50, 50)),
        SimpleNamespace(id=2, foot=(300, 300)),
    ]
    assert zs.assign(tracks) == {1: ["a"], 2: []}


def test_from_json(tmp_path):
    p = tmp_path / "zones.json"
    p.write_text(json.dumps({"zones": [{"name": "a", "points": SQUARE}]}), encoding="utf-8")
    zs = ZoneSet.from_json(p)
    assert zs.zones_at(50, 50) == ["a"]