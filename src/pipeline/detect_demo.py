import argparse
import time

import cv2

from src.pipeline.detector import PersonDetector

WARMUP = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="data/demo1.mp4")
    ap.add_argument("--weights", default="yolo11n.pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--quantize", type=int, default=32, choices=[16, 32])
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--save", default=None, help="output mp4 path")
    args = ap.parse_args()

    det = PersonDetector(args.weights, args.imgsz, args.conf,
                         quantize=args.quantize)
    cap = cv2.VideoCapture(args.video)
    fps_in = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = None
    if args.save:
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"),
                                 fps_in, (w, h))

    t_read, t_det = [], []
    counts = []
    i = 0
    while True:
        t0 = time.perf_counter()
        ok, frame = cap.read()
        t1 = time.perf_counter()
        if not ok:
            break
        dets = det(frame)
        t2 = time.perf_counter()

        if i >= WARMUP:
            t_read.append(t1 - t0)
            t_det.append(t2 - t1)
            counts.append(len(dets))

        for d in dets:
            cv2.rectangle(frame, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)),
                          (0, 255, 0), 2)
            cv2.putText(frame, f"{d.conf:.2f}", (int(d.x1), int(d.y1) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        if writer:
            writer.write(frame)
        if args.show:
            cv2.imshow("detect", cv2.resize(frame, (960, 540)))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        i += 1

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()

    n = len(t_det)
    if n:
        mean_read = sum(t_read) / n * 1000
        mean_det = sum(t_det) / n * 1000
        print(f"frames timed: {n} (first {WARMUP} skipped)")
        print(f"read:   {mean_read:.1f} ms/frame")
        print(f"detect: {mean_det:.1f} ms/frame")
        print(f"end-to-end: {1000 / (mean_read + mean_det):.1f} FPS (source is {fps_in:.0f} FPS)")
        print(f"avg persons/frame: {sum(counts) / n:.2f}")
        print(f"persons/frame min/max: {min(counts)}/{max(counts)}")


if __name__ == "__main__":
    main()

    