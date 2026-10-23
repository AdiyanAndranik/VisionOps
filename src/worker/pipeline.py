from __future__ import annotations

from collections.abc import Iterable

from src.events.schema import line_event, zone_event
from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.dwell import DwellTracker
from src.pipeline.lines import LineCounter
from src.pipeline.zones import ZoneSet

# one value for the track filter and the line counter
CONFIRM_SECONDS = 0.5


class EventPipeline:
    """Raw tracks in, event dicts out: confirm filter -> lines + zone dwell."""

    def __init__(self, source: str, fps: float, zones: ZoneSet, lines: LineCounter):
        self.source = source
        self.fps = fps
        self.confirm = ConfirmedTrackFilter(fps=fps, min_seconds=CONFIRM_SECONDS)
        self.lines = lines
        self.dwell = DwellTracker(zones, fps=fps)
        # confirmed tracks of the last update() call, for other consumers (heatmap)
        self.last_confirmed: list = []

    @classmethod
    def from_files(cls, source: str, fps: float, zones_path: str, lines_path: str) -> "EventPipeline":
        zones = ZoneSet.from_json(zones_path)
        lines = LineCounter.from_json(lines_path, fps=fps, confirm_seconds=CONFIRM_SECONDS)
        return cls(source, fps, zones, lines)

    def config(self) -> dict:
        """Settings that shaped the events, read from the live objects.
        Frame counts are what the code really uses (seconds * fps, rounded up)."""
        return {
            "confirm_seconds": CONFIRM_SECONDS,
            "line_margin_px": self.lines.margin_px,
            "line_confirm_frames": self.lines.confirm_frames,
            "line_max_gap_frames": self.lines.max_gap_frames,
            "line_forget_frames": self.lines.forget_frames,
            "dwell_enter_frames": self.dwell.enter_frames,
            "dwell_exit_frames": self.dwell.exit_frames,
            "dwell_max_gap_frames": self.dwell.max_gap_frames,
        }

    def update(self, tracks: Iterable) -> list[dict]:
        """Call once per frame with all tracks from the tracker."""
        confirmed = list(self.confirm.update(tracks))
        self.last_confirmed = confirmed
        out = [line_event(self.source, e, self.fps) for e in self.lines.update(confirmed)]
        out += [zone_event(self.source, e) for e in self.dwell.update(confirmed)]
        return out

    def finish(self) -> list[dict]:
        """Call once after the last frame. Closes visits that are still open."""
        return [zone_event(self.source, e) for e in self.dwell.finish()]