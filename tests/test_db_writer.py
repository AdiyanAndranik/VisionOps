"""DbWriter and worker-main run status, against the real db
(docker compose up -d db). Skipped if it is not reachable."""
import cv2
import numpy as np
import psycopg
import pytest

from src.events.db import DbWriter, default_conninfo
from src.worker import main as worker_main


@pytest.fixture
def conninfo():
    ci = default_conninfo()
    try:
        psycopg.connect(ci, connect_timeout=3).close()
    except Exception:
        pytest.skip("test db not reachable (docker compose up -d db)")
    return ci


@pytest.fixture
def cleanup(conninfo):
    sources = []
    yield sources
    with psycopg.connect(conninfo, autocommit=True) as conn:
        for s in sources:
            conn.execute("DELETE FROM runs WHERE source = %s", (s,))


def test_start_run_creates_running_row(conninfo, cleanup):
    cleanup.append("dbw-start.mp4")
    db = DbWriter(conninfo)
    rid = db.start_run("dbw-start.mp4", 25.0, 1920, 1080, {"conf": 0.55})
    db.close()
    with psycopg.connect(conninfo) as conn:
        row = conn.execute(
            "SELECT status, fps, width, height, config, finished_at FROM runs WHERE id = %s", (rid,)
        ).fetchone()
    assert row[0] == "running"
    assert row[1] == 25.0
    assert (row[2], row[3]) == (1920, 1080)
    assert row[4] == {"conf": 0.55}
    assert row[5] is None


def test_write_before_start_run_raises(conninfo):
    db = DbWriter(conninfo)
    try:
        with pytest.raises(RuntimeError):
            db.write({"type": "zone_enter"})
    finally:
        db.close()


def test_write_stores_fields_and_ignores_source(conninfo, cleanup):
    cleanup.append("dbw-write.mp4")
    db = DbWriter(conninfo)
    rid = db.start_run("dbw-write.mp4", 25.0, None, None, {})
    db.write({
        "type": "line_cross", "source": "dbw-write.mp4", "track_id": 7, "time_s": 3.5,
        "frame": 88, "line": "h_line", "direction": "pos", "x": 10.5, "y": 20.5,
    })
    db.close()
    assert db.count == 1
    with psycopg.connect(conninfo) as conn:
        row = conn.execute(
            "SELECT type, track_id, time_s, frame, line, direction, x, y, zone, dwell_s "
            "FROM events WHERE run_id = %s",
            (rid,),
        ).fetchone()
    assert row == ("line_cross", 7, 3.5, 88, "h_line", "pos", 10.5, 20.5, None, None)


def test_finish_run_sets_status_and_frames(conninfo, cleanup):
    cleanup.append("dbw-finish.mp4")
    db = DbWriter(conninfo)
    rid = db.start_run("dbw-finish.mp4", 25.0, None, None, {})
    db.finish_run("done", 123)
    db.close()
    with psycopg.connect(conninfo) as conn:
        status, frames, finished = conn.execute(
            "SELECT status, frame_count, finished_at FROM runs WHERE id = %s", (rid,)
        ).fetchone()
    assert (status, frames) == ("done", 123)
    assert finished is not None


def test_bad_event_is_rejected_by_the_db(conninfo, cleanup):
    cleanup.append("dbw-bad.mp4")
    db = DbWriter(conninfo)
    db.start_run("dbw-bad.mp4", 25.0, None, None, {})
    try:
        # zone_enter without a zone breaks the CHECK constraint
        with pytest.raises(psycopg.errors.CheckViolation):
            db.write({"type": "zone_enter", "track_id": 1, "time_s": 1.0, "frame": 25, "start_s": 1.0})
    finally:
        db.close()


# --- worker main(): run status ---------------------------------------------

class _FakeTracker:
    """Returns no tracks. Raises on call number `fail_on` if set."""
    fail_on = 0

    def __init__(self, conf=0.55):
        self.calls = 0

    def config(self):
        return {"weights": "fake.pt", "conf": 0.55}

    def __call__(self, frame):
        self.calls += 1
        if self.fail_on and self.calls == self.fail_on:
            raise RuntimeError("tracker exploded")
        return []


@pytest.fixture
def tiny_video(tmp_path):
    path = tmp_path / "tiny.avi"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (64, 48))
    assert w.isOpened(), "could not create the test video (MJPG avi)"
    for _ in range(10):
        w.write(np.zeros((48, 64, 3), dtype=np.uint8))
    w.release()
    return path


def _run_row(conninfo, source):
    with psycopg.connect(conninfo) as conn:
        return conn.execute(
            "SELECT status, frame_count FROM runs WHERE source = %s ORDER BY id DESC LIMIT 1",
            (source,),
        ).fetchone()


def test_main_marks_run_done(conninfo, cleanup, tiny_video, tmp_path, monkeypatch):
    cleanup.append("main-ok.avi")
    monkeypatch.setattr(worker_main, "PersonTracker", _FakeTracker)
    code = worker_main.main([
        "--video", str(tiny_video), "--db", "--source", "main-ok.avi",
        "--out", str(tmp_path / "out.jsonl"),
    ])
    assert code == 0
    assert _run_row(conninfo, "main-ok.avi") == ("done", 10)
    with psycopg.connect(conninfo) as conn:
        config = conn.execute(
            "SELECT config FROM runs WHERE source = 'main-ok.avi' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert config["tracker"]["weights"] == "fake.pt"
    assert config["pipeline"]["line_margin_px"] == 15.0
    assert "zones" in config and "lines" in config


def test_main_marks_run_failed_on_crash(conninfo, cleanup, tiny_video, tmp_path, monkeypatch):
    cleanup.append("main-fail.avi")

    class Crashing(_FakeTracker):
        fail_on = 4

    monkeypatch.setattr(worker_main, "PersonTracker", Crashing)
    with pytest.raises(RuntimeError):
        worker_main.main([
            "--video", str(tiny_video), "--db", "--source", "main-fail.avi",
            "--out", str(tmp_path / "out.jsonl"),
        ])
    assert _run_row(conninfo, "main-fail.avi") == ("failed", 3)