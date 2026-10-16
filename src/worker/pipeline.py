from __future__ import annotations

from collections.abc import Iterable

from src.events.schema import line_event, zone_event
from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.dwell import DwellTracker
from src.pipeline.lines import LineCounter
from src.pipeline.zones import ZoneSet


class EventPipeline:
    """Raw tracks in, event dicts out: confirm filter -> lines + zone dwell."""

    def __init__(self, source: str, fps: float, zones: ZoneSet, lines: LineCounter):
        self.source = source
        self.fps = fps
        self.confirm = ConfirmedTrackFilter(fps=fps, min_seconds=0.5)
        self.lines = lines
        self.dwell = DwellTracker(zones, fps=fps)

    @classmethod
    def from_files(cls, source: str, fps: float, zones_path: str, lines_path: str) -> "EventPipeline":
        zones = ZoneSet.from_json(zones_path)
        lines = LineCounter.from_json(lines_path, fps=fps, confirm_seconds=0.5)
        return cls(source, fps, zones, lines)

    def update(self, tracks: Iterable) -> list[dict]:
        """Call once per frame with all tracks from the tracker."""
        confirmed = self.confirm.update(tracks)
        out = [line_event(self.source, e, self.fps) for e in self.lines.update(confirmed)]
        out += [zone_event(self.source, e) for e in self.dwell.update(confirmed)]
        return out

    def finish(self) -> list[dict]:
        """Call once after the last frame. Closes visits that are still open."""
        return [zone_event(self.source, e) for e in self.dwell.finish()]