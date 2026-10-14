import argparse
import csv
import itertools
import time
from pathlib import Path

import cv2
import torch

from src.pipeline.tracker import PersonTracker

WARMUP = 10


def run_one(video, weights, conf, tracker_cfg, quantize, imgsz):
    tracker = PersonTracker(weights, imgsz, conf, quantize=quantize,
                            tracker=tracker_cfg)
    cap = cv2.VideoCapture(video)
    first_seen, last_seen = {}, {}
    t_read, t_track = [], []
    i = 0
    while True:
        t0 = time.perf_counter()
        ok, frame = cap.read()
        t1 = time.perf_counter()
        if not ok:
            break
        tracks = tracker(frame)
        t2 = time.perf_counter()
        if i >= WARMUP:
            t_read.append(t1 - t0)
            t_track.append(t2 - t1)
        for t in tracks:
            first_seen.setdefault(t.id, i)
            last_seen[t.id] = i
        i += 1
    cap.release()

    n = len(t_track)
    spans = [last_seen[k] - first_seen[k] + 1 for k in first_seen]
    mean_ms = (sum(t_read) + sum(t_track)) / n * 1000
    return {
        "weights": weights,
        "conf": conf,
        "tracker": tracker_cfg,
        "quantize": quantize,
        "imgsz": imgsz,
        "frames_timed": n,
        "ms_per_frame": round(mean_ms, 1),
        "fps": round(1000 / mean_ms, 1),
        "unique_ids": len(spans),
        "tracks_under_1s": sum(1 for s in spans if s < 25),
        "longest_track": max(spans) if spans else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/demo1.mp4")
    ap.add_argument("--people", type=int, required=True,
                    help="your manual count of distinct people in the clip")
    ap.add_argument("--out", default="results/tracking_bench.csv")
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    weights_list = ["yolo11n.pt", "yolo11s.pt"]
    confs = [0.35, 0.45, 0.55]
    trackers = ["bytetrack.yaml", "configs/bytetrack_custom.yaml"]

    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    rows = []
    for w, c, t in itertools.product(weights_list, confs, trackers):
        print(f"running {w} conf={c} tracker={t} ...")
        r = run_one(args.video, w, c, t, 32, args.imgsz)
        r["ids_per_person"] = round(r["unique_ids"] / args.people, 2)
        r["people_manual"] = args.people
        r["video"] = args.video
        r["gpu"] = gpu
        rows.append(r)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    print(f"\nGPU: {gpu} | manual count: {args.people} people\n")
    print(f"{'model':<11}{'conf':<6}{'tracker':<30}{'FPS':<7}{'IDs':<6}{'<1s':<5}{'IDs/person'}")
    for r in rows:
        print(f"{r['weights']:<11}{r['conf']:<6}{r['tracker']:<30}"
              f"{r['fps']:<7}{r['unique_ids']:<6}{r['tracks_under_1s']:<5}{r['ids_per_person']}")
    print(f"\nsaved to {args.out}")


if __name__ == "__main__":
    main()