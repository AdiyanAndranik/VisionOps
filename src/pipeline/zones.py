from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import shapely
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity


@dataclass(frozen=True)
class Zone:
    """A named polygon in source-frame pixel coordinates.

    A point on the border counts as inside.
    """

    name: str
    polygon: Polygon

    @classmethod
    def from_points(cls, name: str, points: Sequence[Sequence[float]]) -> "Zone":
        if len(points) < 3:
            raise ValueError(f"zone '{name}': need at least 3 points")
        poly = Polygon(points)
        if not poly.is_valid:
            raise ValueError(f"zone '{name}': invalid polygon ({explain_validity(poly)})")
        if poly.area <= 0:
            raise ValueError(f"zone '{name}': polygon has zero area")
        shapely.prepare(poly)  # speeds up repeated point checks
        return cls(name, poly)

    def contains(self, x: float, y: float) -> bool:
        return self.polygon.covers(Point(x, y))


class ZoneSet:
    def __init__(self, zones: Iterable[Zone]):
        self.zones = list(zones)
        names = [z.name for z in self.zones]
        if len(set(names)) != len(names):
            raise ValueError("duplicate zone names")

    @classmethod
    def from_json(cls, path: str | Path) -> "ZoneSet":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(Zone.from_points(z["name"], z["points"]) for z in data["zones"])

    def zones_at(self, x: float, y: float) -> list[str]:
        """Names of all zones containing the point (zones may overlap)."""
        return [z.name for z in self.zones if z.contains(x, y)]

    def assign(self, tracks: Iterable) -> dict[int, list[str]]:
        """Maps track id -> zone names, using each track's foot point."""
        return {t.id: self.zones_at(*t.foot) for t in tracks}