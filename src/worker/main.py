"""Run the full pipeline on a video and write events as JSON lines,
optionally also to Postgres (with a background frame and heatmap per run).

    python -m src.worker.main --video data/demo1.mp4
    python -m src.worker.main --video data/demo1.mp4 --db
    python -m src.worker.main --video data/demo1.mp4 --db --annotate
"""
import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import cv2

from src.events.schema import JsonlWriter
from src.pipeline.draw import Annotator
from src.pipeline.tracker import PersonTracker
from src.worker.artifacts import VIDEO_NAME, VIDEO_TMP_NAME, ArtifactWriter
from src.worker.pipeline import EventPipeline
from src.worker.video import FfmpegWriter


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
    p.add_argument("--artifacts-dir", default="artifacts", help="where --db runs save frame.jpg and heatmap.jpg")
    p.add_argument("--annotate", action="store_true",
                   help="with --db: also write annotated.mp4 (boxes, zones, lines, counters). Needs ffmpeg.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.annotate:
        if not args.db:
            print("--annotate needs --db (the video is saved under the run id)", file=sys.stderr)
            return 1
        if not shutil.which("ffmpeg"):
            print("--annotate needs ffmpeg on PATH", file=sys.stderr)
            return 1

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
    if args.annotate and not (width and height):
        print("could not read the frame size, needed for --annotate", file=sys.stderr)
        cap.release()
        return 1

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
    inside = Counter()  # people inside each zone, from zone_enter / zone_exit events
    frames = 0
    status = "done"
    vid = None
    t0 = time.perf_counter()
    try:
        # images are only for runs in the db, the dashboard needs the run id
        art = ArtifactWriter(args.artifacts_dir, db.run_id, fps) if db else None
        ann = None
        if args.annotate:
            ann = Annotator(args.zones, args.lines, width, height)
            vid = FfmpegWriter(art.dir / VIDEO_TMP_NAME, width, height, fps)

        with JsonlWriter(args.out) as out:

            def emit(ev: dict) -> None:
                out.write(ev)
                if db:
                    db.write(ev)
                counts[ev["type"]] += 1
                if ev["type"] == "zone_enter":
                    inside[ev["zone"]] += 1
                elif ev["type"] == "zone_exit":
                    inside[ev["zone"]] -= 1

            def panel() -> list[str]:
                rows = [f"people: {len(pipe.last_confirmed)}",
                        f"line crossings: {counts['line_cross']}"]
                rows += [f"{z}: {inside[z]} inside" for z in ann.zone_names]
                return rows

            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    for ev in pipe.update(tracker(frame)):
                        emit(ev)
                    if art:
                        # before drawing, so frame.jpg stays a clean frame
                        art.update(frame, pipe.last_confirmed)
                    if vid:
                        ann.draw(frame, pipe.last_confirmed, panel())
                        vid.write(frame)
                    frames += 1
                    if args.max_frames and frames >= args.max_frames:
                        break
            finally:
                cap.release()
            for ev in pipe.finish():
                emit(ev)
        # before finish_run, so a client that reacts to run_done finds the heatmap and video
        if art:
            art.finish()
        if vid:
            vid.close()
            (art.dir / VIDEO_TMP_NAME).replace(art.dir / VIDEO_NAME)
    except BaseException:
        status = "failed"
        if vid:
            vid.abort()
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
        print(f"saved to db as run {db.run_id}, images in {args.artifacts_dir}/{db.run_id}")
        if args.annotate:
            print(f"video: {args.artifacts_dir}/{db.run_id}/{VIDEO_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())