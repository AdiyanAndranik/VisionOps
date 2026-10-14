import argparse
import time
from collections import defaultdict, deque

import cv2

from src.pipeline.tracker import PersonTracker

WARMUP = 10
TRAIL_LEN = 40


def color_for(track_id: int):
    return (
        (track_id * 67) % 200 + 55,
        (track_id * 131) % 200 + 55,
        (track_id * 197) % 200 + 55,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/demo1.mp4")
    ap.add_argument("--weights", default="yolo11n.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.55)
    ap.add_argument("--quantize", type=int, default=32, choices=[16, 32])
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--save", default=None, help="output mp4 path")
    ap.add_argument("--tracker", default="configs/bytetrack_custom.yaml")
    args = ap.parse_args()

    tracker = PersonTracker(args.weights, args.imgsz, args.conf,
                            quantize=args.quantize, tracker=args.tracker)
    cap = cv2.VideoCapture(args.video)
    fps_in = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = None
    if args.save:
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps_in, (w, h))

    trails = defaultdict(lambda: deque(maxlen=TRAIL_LEN))
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
            trails[t.id].append(t.foot)
            col = color_for(t.id)
            cv2.rectangle(frame, (int(t.x1), int(t.y1)), (int(t.x2), int(t.y2)), col, 2)
            cv2.putText(frame, f"#{t.id}", (int(t.x1), int(t.y1) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            pts = list(trails[t.id])
            for a, b in zip(pts, pts[1:]):
                cv2.line(frame, a, b, col, 2)

        if writer:
            writer.write(frame)
        if args.show:
            cv2.imshow("track", cv2.resize(frame, (960, 540)))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        i += 1

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()

    n = len(t_track)
    if n:
        mean_read = sum(t_read) / n * 1000
        mean_trk = sum(t_track) / n * 1000
        print(f"frames timed: {n} (first {WARMUP} skipped)")
        print(f"read:   {mean_read:.1f} ms/frame")
        print(f"detect+track: {mean_trk:.1f} ms/frame")
        print(f"end-to-end: {1000 / (mean_read + mean_trk):.1f} FPS (source is {fps_in:.0f} FPS)")

    spans = [last_seen[k] - first_seen[k] + 1 for k in first_seen]
    short = sum(1 for s in spans if s < 25)
    print(f"unique track IDs: {len(spans)}")
    print(f"tracks shorter than 1 s: {short}")
    print(f"longest track: {max(spans) if spans else 0} frames")


if __name__ == "__main__":
    main()

