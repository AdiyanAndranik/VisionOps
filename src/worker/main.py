"""Run the full pipeline on a video and write events as JSON lines,
optionally also to Postgres.

    python -m src.worker.main --video data/demo1.mp4
    python -m src.worker.main --video data/demo1.mp4 --db
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2

from src.events.schema import JsonlWriter
from src.pipeline.tracker import PersonTracker
from src.worker.pipeline import EventPipeline


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="VisionOps worker: video -> events.")
    p.add_argument("--video", required=True, help="video file path or rtsp:// URL")
    p.add_argument("--zones", default="configs/zones.json")
    p.add_argument("--lines", default="configs/lines.json")
    p.add_argument("--out", default="results/events.jsonl")
    p.add_argument("--conf", type=float, default=0.55)
    p.add_argument("--source", default="", help="source name in events (default: video file name)")
    p.add_argument("--max-frames", type=int, default=0, help="stop after N frames (0 = all)")
    p.add_argument("--db", action="store_true", help="also write the run and its events to Postgres")
    p.add_argument("--db-url", default="", help="Postgres connection string for --db (default: built from .env)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"could not open: {args.video}", file=sys.stderr)
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        print("could not read fps from the source", file=sys.stderr)
        cap.release()
        return 1
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None

    source = args.source or Path(args.video).name
    pipe = EventPipeline.from_files(source, fps, args.zones, args.lines)
    tracker = PersonTracker(conf=args.conf)

    db = None
    if args.db:
        # imported here so psycopg and python-dotenv are only needed with --db
        from src.events.db import DbWriter, default_conninfo

        try:
            db = DbWriter(args.db_url or default_conninfo())
        except Exception as exc:
            print(f"could not connect to db: {exc}", file=sys.stderr)
            cap.release()
            return 1
        config = {
            "tracker": tracker.config(),
            "pipeline": pipe.config(),
            "zones": json.loads(Path(args.zones).read_text(encoding="utf-8")),
            "lines": json.loads(Path(args.lines).read_text(encoding="utf-8")),
        }
        db.start_run(source, fps, width, height, config)

    counts = Counter()
    frames = 0
    status = "done"
    t0 = time.perf_counter()
    try:
        with JsonlWriter(args.out) as out:

            def emit(ev: dict) -> None:
                out.write(ev)
                if db:
                    db.write(ev)
                counts[ev["type"]] += 1

            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    for ev in pipe.update(tracker(frame)):
                        emit(ev)
                    frames += 1
                    if args.max_frames and frames >= args.max_frames:
                        break
            finally:
                cap.release()
            for ev in pipe.finish():
                emit(ev)
    except BaseException:
        status = "failed"
        raise
    finally:
        if db:
            db.finish_run(status, frames)
            db.close()

    elapsed = time.perf_counter() - t0
    print(f"{frames} frames in {elapsed:.1f}s ({frames / elapsed:.1f} fps), source {fps:.1f} fps")
    for k in ("line_cross", "zone_enter", "zone_exit"):
        print(f"{k}: {counts[k]}")
    print(f"written to {args.out}")
    if db:
        print(f"saved to db as run {db.run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

    