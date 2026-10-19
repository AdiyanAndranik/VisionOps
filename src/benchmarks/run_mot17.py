"""Run the tracker over MOT17 train sequences and write results in MOT format.

    python -m src.benchmarks.run_mot17 --name yolo11n_c055 --seqs MOT17-02-FRCNN MOT17-04-FRCNN
"""
import argparse
import configparser
import json
import sys
import time
from pathlib import Path

import cv2

from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.tracker import PersonTracker

# the three detector variants (DPM/FRCNN/SDP) share the same images and GT,
# so one is enough for a tracking benchmark
ALL_SEQS = [
    "MOT17-02-FRCNN", "MOT17-04-FRCNN", "MOT17-05-FRCNN", "MOT17-09-FRCNN",
    "MOT17-10-FRCNN", "MOT17-11-FRCNN", "MOT17-13-FRCNN",
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="VisionOps: run the tracker on MOT17 train.")
    p.add_argument("--root", default="data/MOT17/train")
    p.add_argument("--out", default="results/mot17")
    p.add_argument("--name", required=True, help="run name, e.g. yolo11n_c055")
    p.add_argument("--seqs", nargs="+", default=ALL_SEQS)
    p.add_argument("--conf", type=float, default=0.55)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--confirm-seconds", type=float, default=0.0,
                   help="confirmed-track filter; 0 = off")
    return p.parse_args(argv)


def read_fps(seq_dir: Path) -> float:
    cfg = configparser.ConfigParser()
    cfg.read(seq_dir / "seqinfo.ini")
    return float(cfg["Sequence"]["frameRate"])


def run_sequence(seq_dir: Path, out_file: Path, conf: float, imgsz: int, confirm_seconds: float) -> tuple[int, float]:
    images = sorted((seq_dir / "img1").glob("*.jpg"))
    if not images:
        raise FileNotFoundError(f"no images in {seq_dir / 'img1'}")
    fps = read_fps(seq_dir)

    # fresh tracker per sequence so IDs and state never leak between videos
    tracker = PersonTracker(conf=conf, imgsz=imgsz)
    confirm = ConfirmedTrackFilter(fps=fps, min_seconds=confirm_seconds) if confirm_seconds > 0 else None

    lines = []
    t0 = time.perf_counter()
    for n, path in enumerate(images, start=1):  # MOT frames are 1-based
        frame = cv2.imread(str(path))
        if frame is None:
            raise RuntimeError(f"could not read {path}")
        tracks = tracker(frame)
        if confirm is not None:
            tracks = confirm.update(tracks)
        for t in tracks:
            w, h = t.x2 - t.x1, t.y2 - t.y1
            lines.append(f"{n},{t.id},{t.x1:.2f},{t.y1:.2f},{w:.2f},{h:.2f},{t.conf:.4f},-1,-1,-1")
    elapsed = time.perf_counter() - t0

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines) + ("\n" if lines else ""))
    return len(images), elapsed


def main(argv=None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    run_dir = Path(args.out) / "trackers" / "MOT17-train" / args.name
    data_dir = run_dir / "data"

    for seq in args.seqs:
        seq_dir = root / seq
        if not seq_dir.is_dir():
            print(f"missing sequence folder: {seq_dir}", file=sys.stderr)
            return 1
        n, sec = run_sequence(seq_dir, data_dir / f"{seq}.txt", args.conf, args.imgsz, args.confirm_seconds)
        print(f"{seq}: {n} frames in {sec:.1f}s")

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(json.dumps({
        "weights": "yolo11n.pt", "conf": args.conf, "imgsz": args.imgsz,
        "confirm_seconds": args.confirm_seconds, "tracker": "configs/bytetrack_custom.yaml",
        "sequences": args.seqs,
    }, indent=2))
    print(f"results: {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())