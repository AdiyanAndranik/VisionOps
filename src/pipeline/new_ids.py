import argparse

import cv2

from src.pipeline.tracker import PersonTracker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/demo1.mp4")
    ap.add_argument("--weights", default="yolo11n.pt")
    ap.add_argument("--conf", type=float, default=0.55)
    ap.add_argument("--tracker", default="configs/bytetrack_custom.yaml")
    ap.add_argument("--margin", type=float, default=0.05)
    args = ap.parse_args()

    tr = PersonTracker(args.weights, 640, args.conf, quantize=32,
                       tracker=args.tracker)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    mx, my = args.margin * w, args.margin * h

    seen = set()
    at_start, at_edge, mid = 0, 0, []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        for t in tr(frame):
            if t.id in seen:
                continue
            seen.add(t.id)
            if i <= 1:
                at_start += 1
            elif t.x1 < mx or t.x2 > w - mx or t.y1 < my or t.y2 > h - my:
                at_edge += 1
            else:
                mid.append((t.id, i, t.foot))
        i += 1
    cap.release()

    print(f"total IDs: {len(seen)}")
    print(f"present at start: {at_start}")
    print(f"born at frame edge (entering): {at_edge}")
    print(f"born mid-scene (suspect): {len(mid)}")
    for tid, f, (x, y) in mid:
        print(f"  id {tid}: frame {f} ({f / fps:.1f} s) at x={x}, y={y}")


if __name__ == "__main__":
    main()