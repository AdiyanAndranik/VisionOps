"""Run the full pipeline on a video and write events as JSON lines.

    python -m src.worker.main --video data/demo1.mp4
"""
import argparse
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
        return 1

    source = args.source or Path(args.video).name
    pipe = EventPipeline.from_files(source, fps, args.zones, args.lines)
    tracker = PersonTracker(conf=args.conf)

    counts = Counter()
    frames = 0
    t0 = time.perf_counter()
    with JsonlWriter(args.out) as out:
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                for ev in pipe.update(tracker(frame)):
                    out.write(ev)
                    counts[ev["type"]] += 1
                frames += 1
                if args.max_frames and frames >= args.max_frames:
                    break
        finally:
            cap.release()
        for ev in pipe.finish():
            out.write(ev)
            counts[ev["type"]] += 1

    elapsed = time.perf_counter() - t0
    print(f"{frames} frames in {elapsed:.1f}s ({frames / elapsed:.1f} fps), source {fps:.1f} fps")
    for k in ("line_cross", "zone_enter", "zone_exit"):
        print(f"{k}: {counts[k]}")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

    