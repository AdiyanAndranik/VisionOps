from pathlib import Path

import cv2
import pytest

from src.pipeline.tracker import PersonTracker, Track

VIDEO = Path("data/demo1.mp4")


@pytest.mark.skipif(not VIDEO.exists(), reason="demo clip missing")
def test_tracker_returns_valid_tracks():
    tr = PersonTracker()
    cap = cv2.VideoCapture(str(VIDEO))
    tracks = []
    for _ in range(30):
        ok, frame = cap.read()
        assert ok
        tracks = tr(frame)
    cap.release()

    assert tracks
    assert all(isinstance(t, Track) for t in tracks)
    assert all(t.x2 > t.x1 and t.y2 > t.y1 for t in tracks)
    assert len({t.id for t in tracks}) == len(tracks)