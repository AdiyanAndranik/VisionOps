import asyncio
import os
import re
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.api.live import Hub, listen_forever

from pathlib import Path

from fastapi.responses import FileResponse, Response, StreamingResponse

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://visionops:visionops@localhost:5433/visionops",
)
LISTEN_DSN = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
hub = Hub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ready = asyncio.Event()
    task = asyncio.create_task(listen_forever(hub, LISTEN_DSN, ready))
    try:
        await asyncio.wait_for(ready.wait(), timeout=3)
    except asyncio.TimeoutError:
        pass  # db not up yet, the listener keeps retrying in the background
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title="VisionOps API", lifespan=lifespan)

EventType = Literal["line_cross", "zone_enter", "zone_exit"]

RUN_COLS = "id, source, status, started_at, finished_at, fps, width, height, frame_count"
EVENT_COLS = "id, type, track_id, time_s, frame, zone, line, direction, x, y, start_s, dwell_s"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db unreachable: {type(exc).__name__}")
    return {"db": "ok"}


async def _require_run(conn, run_id: int) -> None:
    found = (await conn.execute(text("SELECT 1 FROM runs WHERE id = :id"), {"id": run_id})).first()
    if found is None:
        raise HTTPException(status_code=404, detail="run not found")


@app.get("/runs")
async def list_runs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(f"SELECT {RUN_COLS} FROM runs ORDER BY id DESC LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset},
            )
        ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/runs/{run_id}")
async def get_run(run_id: int):
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(f"SELECT {RUN_COLS}, config FROM runs WHERE id = :id"), {"id": run_id}
            )
        ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    out = dict(row)
    out["has_video"] = (ARTIFACTS_DIR / str(run_id) / VIDEO_NAME).is_file()
    return out


def _artifact(run_id: int, name: str) -> FileResponse:
    path = ARTIFACTS_DIR / str(run_id) / name  # run_id is an int, no path tricks possible
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{name} not available for this run")
    # no-cache = always revalidate (cheap 304), because run ids restart after down -v
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@app.get("/runs/{run_id}/frame")
async def run_frame(run_id: int):
    return _artifact(run_id, "frame.jpg")


@app.get("/runs/{run_id}/heatmap")
async def run_heatmap(run_id: int):
    return _artifact(run_id, "heatmap.jpg")

VIDEO_NAME = "annotated.mp4"
VIDEO_CHUNK = 1024 * 1024
_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _parse_range(header: str, size: int):
    """Returns (start, end) inclusive, None to ignore the header (malformed or
    multi-range, the full file is sent), or "bad" if it can't be satisfied."""
    m = _RANGE_RE.match(header.strip())
    if not m or (m.group(1) == "" and m.group(2) == ""):
        return None
    if m.group(1) == "":  # suffix form: the last N bytes
        n = int(m.group(2))
        if n == 0:
            return "bad"
        return max(size - n, 0), size - 1
    start = int(m.group(1))
    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
    if start >= size or start > end:
        return "bad"
    return start, end


def _file_chunks(path: Path, start: int, length: int):
    with path.open("rb") as f:
        f.seek(start)
        left = length
        while left > 0:
            data = f.read(min(VIDEO_CHUNK, left))
            if not data:
                break
            left -= len(data)
            yield data


@app.get("/runs/{run_id}/video")
async def run_video(run_id: int, request: Request):
    """The annotated video. Supports Range requests, so the browser can seek."""
    path = ARTIFACTS_DIR / str(run_id) / VIDEO_NAME
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"{VIDEO_NAME} not available for this run")
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "no-cache"}

    rng = request.headers.get("range")
    parsed = _parse_range(rng, size) if rng else None
    if parsed == "bad":
        return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
    if parsed is None:
        start, end, code = 0, size - 1, 200
    else:
        (start, end), code = parsed, 206
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    length = end - start + 1
    headers["Content-Length"] = str(length)
    return StreamingResponse(_file_chunks(path, start, length), status_code=code,
                             media_type="video/mp4", headers=headers)


@app.get("/runs/{run_id}/events")
async def list_events(
    run_id: int,
    event_type: EventType | None = Query(None, alias="type"),
    track_id: int | None = None,
    zone: str | None = None,
    line: str | None = None,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    where = ["run_id = :run_id"]
    params: dict = {"run_id": run_id, "limit": limit, "offset": offset}
    if event_type is not None:
        where.append("type = :type")
        params["type"] = event_type
    if track_id is not None:
        where.append("track_id = :track_id")
        params["track_id"] = track_id
    if zone is not None:
        where.append("zone = :zone")
        params["zone"] = zone
    if line is not None:
        where.append("line = :line")
        params["line"] = line
    sql = (
        f"SELECT {EVENT_COLS} FROM events WHERE {' AND '.join(where)} "
        "ORDER BY time_s, id LIMIT :limit OFFSET :offset"
    )
    async with engine.connect() as conn:
        await _require_run(conn, run_id)
        rows = (await conn.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]


@app.get("/runs/{run_id}/summary")
async def run_summary(run_id: int):
    p = {"id": run_id}
    async with engine.connect() as conn:
        await _require_run(conn, run_id)
        by_type = (
            await conn.execute(
                text("SELECT type, count(*) AS n FROM events WHERE run_id = :id GROUP BY type"), p
            )
        ).all()
        lines = (
            await conn.execute(
                text(
                    "SELECT line, direction, count(*) AS n FROM events "
                    "WHERE run_id = :id AND type = 'line_cross' "
                    "GROUP BY line, direction ORDER BY line, direction"
                ),
                p,
            )
        ).all()
        zones = (
            await conn.execute(
                text(
                    "SELECT zone, count(*) AS visits, avg(dwell_s) AS avg_dwell_s, "
                    "max(dwell_s) AS max_dwell_s FROM events "
                    "WHERE run_id = :id AND type = 'zone_exit' "
                    "GROUP BY zone ORDER BY zone"
                ),
                p,
            )
        ).all()

    def r1(v):
        return None if v is None else round(float(v), 2)

    return {
        "events": {t: n for t, n in by_type},
        "line_crossings": [{"line": l, "direction": d, "count": n} for l, d, n in lines],
        "zones": [
            {"zone": z, "visits": v, "avg_dwell_s": r1(a), "max_dwell_s": r1(m)}
            for z, v, a, m in zones
        ],
    }


async def _pump(ws: WebSocket, q: asyncio.Queue) -> None:
    while True:
        msg = await q.get()
        await ws.send_json(msg)
        if msg.get("kind") == "run_done":
            return


@app.websocket("/runs/{run_id}/ws")
async def run_ws(ws: WebSocket, run_id: int):
    """Pushes new events of a run: {"kind": "event", "event": {...}}, then
    {"kind": "run_done", "status": ...} once. Only events from now on, history
    is on REST: connect first, then load /events, drop duplicates by event id."""
    q = hub.subscribe(run_id)  # before accept, so nothing is missed after connect
    try:
        await ws.accept()
        async with engine.connect() as conn:
            status = (
                await conn.execute(text("SELECT status FROM runs WHERE id = :id"), {"id": run_id})
            ).scalar()
        if status is None:
            await ws.close(code=4404)
            return
        if status != "running":
            await ws.send_json({"kind": "run_done", "status": status})
            await ws.close()
            return

        tasks = [asyncio.create_task(_pump(ws, q)), asyncio.create_task(ws.receive_text())]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await ws.close()
        except Exception:
            pass  # client already gone
    finally:
        hub.unsubscribe(run_id, q)