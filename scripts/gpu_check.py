"""Check that PyTorch can actually use the GPU (GTX 1050 Ti = Pascal, compute capability 6.1).

    python scripts/gpu_check.py          # torch + CUDA kernel test
    python scripts/gpu_check.py --yolo   # also time yolo11n on a blank 640x640 frame

The kernel test is the real answer. Newer PyTorch CUDA builds may drop old architectures,
in which case torch.cuda.is_available() can still say True but kernels fail.
"""
import argparse
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo", action="store_true", help="also benchmark yolo11n (downloads weights on first run)")
    args = ap.parse_args()

    try:
        import torch
    except ImportError:
        print("torch is not installed. Install it first (see the setup steps).")
        return 1

    print(f"torch {torch.__version__}, built for CUDA {torch.version.cuda}")
    if not torch.cuda.is_available():
        print("CUDA not available. Check the NVIDIA driver, and that you installed a CUDA build of torch (not CPU).")
        return 1

    name = torch.cuda.get_device_name(0)
    major, minor = torch.cuda.get_device_capability(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"device: {name}, compute capability {major}.{minor}, {vram:.1f} GB VRAM")
    print(f"archs in this torch build: {torch.cuda.get_arch_list()}")

    try:
        a = torch.randn(1024, 1024, device="cuda")
        (a @ a).sum().item()
        torch.cuda.synchronize()
    except Exception as exc:
        print(f"kernel test FAILED: {exc}")
        print("Your torch build probably dropped this GPU architecture. Install an older CUDA build (cu126, then cu118).")
        return 1
    print("kernel test: ok")

    if args.yolo:
        import numpy as np
        from ultralytics import YOLO

        model = YOLO("yolo11n.pt")
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        for _ in range(3):  # warmup
            model.predict(frame, device=0, classes=[0], verbose=False)
        n = 30
        t0 = time.perf_counter()
        for _ in range(n):
            model.predict(frame, device=0, classes=[0], verbose=False)
        ms = (time.perf_counter() - t0) / n * 1000
        print(f"yolo11n @640 on {name}: {ms:.1f} ms/frame (blank frame, fp32, not a benchmark)")
    return 0


if __name__ == "__main__":
    sys.exit(main())