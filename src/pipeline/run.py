"""Phase 0: open a video file or RTSP URL and show it. Nothing else yet.

    python -m src.pipeline.run --video data/demo1.mp4
    python -m src.pipeline.run --video rtsp://user:pass@host/stream
"""
import argparse
import sys
import time

import cv2


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="VisionOps: show a video source.")
    p.add_argument("--video", required=True, help="video file path or rtsp:// URL")
    p.add_argument("--no-display", action="store_true", help="don't open a window (tests, headless)")
    p.add_argument("--max-frames", type=int, default=0, help="stop after N frames (0 = whole video)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"could not open: {args.video}", file=sys.stderr)
        return 1

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"source: {width}x{height}, {src_fps:.1f} fps, {total if total > 0 else 'unknown'} frames")

    # pace playback to the source fps so it looks natural; RTSP paces itself
    delay_ms = max(1, int(1000 / src_fps)) if src_fps > 0 else 1

    frames = 0
    t0 = time.perf_counter()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames += 1
            if not args.no_display:
                cv2.imshow("visionops", frame)
                if cv2.waitKey(delay_ms) & 0xFF in (ord("q"), 27):
                    break
            if args.max_frames and frames >= args.max_frames:
                break
    finally:
        cap.release()
        if not args.no_display:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - t0
    if frames:
        print(f"read {frames} frames in {elapsed:.2f}s ({frames / elapsed:.1f} fps incl. display/pacing)")
    else:
        print("no frames read", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())