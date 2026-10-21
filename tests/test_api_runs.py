"""API tests against the real db (docker compose up -d db). Skipped if it is not reachable."""
import pytest
from fastapi.testclient import TestClient

psycopg = pytest.importorskip("psycopg")

from src.api.main import app
from src.events.db import DbWriter, default_conninfo
from starlette.websockets import WebSocketDisconnect

# written out of time order on purpose, the API must sort by time_s
EVENTS = [
    {"type": "zone_exit", "track_id": 2, "time_s": 7.0, "frame": 175,
     "zone": "center", "start_s": 2.0, "dwell_s": 5.0},
    {"type": "line_cross", "track_id": 1, "time_s": 5.0, "frame": 125,
     "line": "h_line", "direction": "pos", "x": 100.0, "y": 200.0},
    {"type": "zone_enter", "track_id": 2, "time_s": 2.0, "frame": 50,
     "zone": "center", "start_s": 2.0},
]


@pytest.fixture(scope="module")
def run_id():
    conninfo = default_conninfo()
    try:
        db = DbWriter(conninfo)
    except Exception:
        pytest.skip("test db not reachable (docker compose up -d db)")
    rid = db.start_run("test.mp4", 25.0, 1920, 1080, {"zones": {"zones": []}, "lines": {"lines": []}})
    for ev in EVENTS:
        db.write(ev)
    db.finish_run("done", 100)
    db.close()
    yield rid
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("DELETE FROM runs WHERE id = %s", (rid,))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # one event loop for all requests
        yield c


def test_list_runs_contains_run(client, run_id):
    r = client.get("/runs")
    assert r.status_code == 200
    assert run_id in [x["id"] for x in r.json()]


def test_get_run(client, run_id):
    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "test.mp4"
    assert body["status"] == "done"
    assert body["frame_count"] == 100
    assert "zones" in body["config"]


def test_unknown_run_is_404(client):
    for path in ("", "/events", "/summary"):
        assert client.get(f"/runs/999999999{path}").status_code == 404


def test_events_sorted_by_time(client, run_id):
    r = client.get(f"/runs/{run_id}/events")
    assert r.status_code == 200
    times = [e["time_s"] for e in r.json()]
    assert times == [2.0, 5.0, 7.0]


def test_events_filters(client, run_id):
    only_lines = client.get(f"/runs/{run_id}/events", params={"type": "line_cross"}).json()
    assert [e["track_id"] for e in only_lines] == [1]
    track2 = client.get(f"/runs/{run_id}/events", params={"track_id": 2}).json()
    assert [e["type"] for e in track2] == ["zone_enter", "zone_exit"]
    paged = client.get(f"/runs/{run_id}/events", params={"limit": 1, "offset": 1}).json()
    assert [e["time_s"] for e in paged] == [5.0]


def test_bad_event_type_is_422(client, run_id):
    assert client.get(f"/runs/{run_id}/events", params={"type": "nope"}).status_code == 422


def test_summary(client, run_id):
    body = client.get(f"/runs/{run_id}/summary").json()
    assert body["events"] == {"line_cross": 1, "zone_enter": 1, "zone_exit": 1}
    assert body["line_crossings"] == [{"line": "h_line", "direction": "pos", "count": 1}]
    assert body["zones"] == [
        {"zone": "center", "visits": 1, "avg_dwell_s": 5.0, "max_dwell_s": 5.0}
    ]

def test_ws_finished_run_sends_run_done(client, run_id):
    with client.websocket_connect(f"/runs/{run_id}/ws") as ws:
        assert ws.receive_json() == {"kind": "run_done", "status": "done"}


def test_ws_unknown_run_closes(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/runs/999999999/ws") as ws:
            ws.receive_json()


def test_ws_live_events(client):
    with psycopg.connect(default_conninfo(), autocommit=True) as conn:
        rid = conn.execute(
            "INSERT INTO runs (source, fps) VALUES ('ws-test.mp4', 25) RETURNING id"
        ).fetchone()[0]
        try:
            with client.websocket_connect(f"/runs/{rid}/ws") as ws:
                conn.execute(
                    "INSERT INTO events (run_id, type, track_id, time_s, frame, line, direction) "
                    "VALUES (%s, 'line_cross', 1, 1.0, 25, 'h_line', 'pos')",
                    (rid,),
                )
                msg = ws.receive_json()
                assert msg["kind"] == "event"
                assert msg["event"]["track_id"] == 1
                assert msg["event"]["line"] == "h_line"
                conn.execute("UPDATE runs SET status = 'done' WHERE id = %s", (rid,))
                assert ws.receive_json() == {"kind": "run_done", "status": "done"}
        finally:
            conn.execute("DELETE FROM runs WHERE id = %s", (rid,))