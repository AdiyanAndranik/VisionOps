"""Label line crossings by hand on a clip. Do this BEFORE looking at the system's events.

    python -m src.benchmarks.label_crossings --video data/demo1.mp4

Keys: space play/pause, a / d = 1 frame back / forward, [ / ] = 10 frames,
      z undo last label, s save, q or Esc save and quit.
Each line gets two keys (shown on screen), one per direction.
Label the frame where the person's feet (bottom of the body) touch the line.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2

from src.pipeline.draw import Annotator


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/demo1.mp4")
    ap.add_argument("--zones", default="configs/zones.json")
    ap.add_argument("--lines", default="configs/lines.json")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    out = Path(args.out or f"benchmarks/labels/{Path(args.video).stem}_crossings.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"could not open: {args.video}", file=sys.stderr)
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    lines = json.loads(Path(args.lines).read_text(encoding="utf-8"))["lines"]
    keys = {}  # key char -> (line, direction)
    help_rows = []
    for i, ln in enumerate(lines):
        a, b = str(2 * i + 1), str(2 * i + 2)
        keys[a] = (ln["name"], ln["pos_label"])
        keys[b] = (ln["name"], ln["neg_label"])
        help_rows.append(f"{a}: {ln['name']} {ln['pos_label']}   {b}: {ln['name']} {ln['neg_label']}")

    labels = []
    if out.exists():
        labels = json.loads(out.read_text(encoding="utf-8")).get("labels", [])
        print(f"continuing with {len(labels)} labels from {out}")

    def save():
        data = {"video": Path(args.video).name, "fps": fps, "labels": labels}
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"saved {len(labels)} labels to {out}")

    def seek(i):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(i, total - 1)))
        ok, f = cap.read()
        return (max(0, min(i, total - 1)), f) if ok else None

    ann = Annotator(args.zones, args.lines, w, h)
    idx, frame = seek(0)
    playing = False
    last = ""

    while True:
        if playing:
            ok, f = cap.read()
            if ok:
                idx, frame = idx + 1, f
            else:
                playing = False
        img = frame.copy()
        info = [f"frame {idx}/{total - 1}   t = {idx / fps:.2f} s", f"labels: {len(labels)}   {last}"] + help_rows
        ann.draw(img, [], info)
        cv2.imshow("label", cv2.resize(img, (1280, 720)))

        k = cv2.waitKey(int(1000 / fps) if playing else 0) & 0xFF
        ch = chr(k) if 32 <= k < 127 else ""
        if k in (27, ord("q")):
            break
        elif ch == " ":
            playing = not playing
        elif ch in "ad[]" and ch:
            playing = False
            step = {"a": -1, "d": 1, "[": -10, "]": 10}[ch]
            res = seek(idx + step)
            if res:
                idx, frame = res
        elif ch in keys:
            line, direction = keys[ch]
            labels.append({"frame": idx, "time_s": round(idx / fps, 3), "line": line, "direction": direction})
            labels.sort(key=lambda x: x["frame"])
            last = f"added {line} {direction} at {idx / fps:.2f} s"
            print(last)
        elif ch == "z" and labels:
            gone = labels.pop()
            last = f"removed {gone['line']} {gone['direction']} at {gone['time_s']} s"
            print(last)
        elif ch == "s":
            save()
    save()
    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())