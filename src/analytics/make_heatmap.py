"""Track a video and render a presence heatmap over one of its frames.

    python -m src.analytics.make_heatmap --video data/demo1.mp4
"""
import argparse
import sys
import time

import cv2

from src.analytics.heatmap import HeatmapAccumulator, render_overlay
from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.tracker import PersonTracker


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="VisionOps: presence heatmap.")
    p.add_argument("--video", required=True)
    p.add_argument("--out", default="results/heatmap.png")
    p.add_argument("--grid-out", default="results/heatmap.npy")
    p.add_argument("--conf", type=float, default=0.55)
    p.add_argument("--cell", type=int, default=8, help="grid cell size in px")
    p.add_argument("--sigma", type=float, default=2.0, help="blur in grid cells")
    p.add_argument("--max-frames", type=int, default=0)
    p.add_argument("--edge-margin", type=int, default=4, help="skip feet this close to the bottom edge")
    p.add_argument("--bg-frame", type=int, default=0, help="frame index used as the background")
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
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    tracker = PersonTracker(conf=args.conf)
    confirm = ConfirmedTrackFilter(fps=fps, min_seconds=0.5)
    acc = HeatmapAccumulator(width, height, fps, cell=args.cell, edge_margin=args.edge_margin)

    background = None
    frames = 0
    t0 = time.perf_counter()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frames == args.bg_frame:
                background = frame.copy()
            acc.update(confirm.update(tracker(frame)))
            frames += 1
            if args.max_frames and frames >= args.max_frames:
                break
    finally:
        cap.release()

    if background is None:
        print("background frame not reached", file=sys.stderr)
        return 1

    acc.save(args.grid_out)
    img, scale = render_overlay(background, acc.grid, args.cell, sigma_cells=args.sigma)
    cv2.imwrite(args.out, img)

    print(f"{frames} frames in {time.perf_counter() - t0:.1f}s")
    print(f"total presence: {acc.total_seconds:.1f} person-seconds (confirmed tracks only)")
    print(f"hottest color = {scale:.2f} s per blurred cell (99th percentile)")
    print(f"image: {args.out}, grid: {args.grid_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())