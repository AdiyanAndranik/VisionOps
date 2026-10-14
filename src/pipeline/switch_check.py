import argparse
import math

import cv2

from src.pipeline.tracker import PersonTracker

LOOKBACK = 75   # frames (3 s at 25 FPS)
MAX_DIST = 200  # pixels at 1920x1080


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

    last = {}  # id -> (frame, foot)
    born_mid = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        tracks = tr(frame)
        present = {t.id for t in tracks}
        for t in tracks:
            if t.id not in last and i > 1:
                inside = not (t.x1 < mx or t.x2 > w - mx or t.y1 < my or t.y2 > h - my)
                if inside:
                    cands = []
                    for oid, (lf, (ox, oy)) in last.items():
                        if oid in present or i - lf > LOOKBACK:
                            continue
                        d = math.hypot(t.foot[0] - ox, t.foot[1] - oy)
                        if d < MAX_DIST:
                            cands.append((oid, i - lf, int(d)))
                    born_mid.append((t.id, i, cands))
            last[t.id] = (i, t.foot)
        i += 1
    cap.release()

    sw = sum(1 for _, _, c in born_mid if c)
    print(f"mid-scene births: {len(born_mid)}")
    print(f"  with a nearby recently-lost track (likely switch): {sw}")
    print(f"  with none (likely late first detection): {len(born_mid) - sw}\n")
    for tid, f, c in born_mid:
        if c:
            txt = ", ".join(f"id {o} (lost {g} fr ago, {d}px away)" for o, g, d in c)
        else:
            txt = "no predecessor"
        print(f"id {tid} @ frame {f} ({f / fps:.1f} s): {txt}")


if __name__ == "__main__":
    main()