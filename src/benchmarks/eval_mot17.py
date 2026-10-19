"""Score a run from run_mot17.py with TrackEval (HOTA, MOTA, IDF1, ID switches).

    python -m src.benchmarks.eval_mot17 --name yolo11n_c055
"""
import argparse
import shutil
import sys
from pathlib import Path


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="VisionOps: score MOT17 results with TrackEval.")
    p.add_argument("--root", default="data/MOT17/train")
    p.add_argument("--out", default="results/mot17")
    p.add_argument("--name", required=True)
    p.add_argument("--trackeval", default="external/TrackEval")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    root, out = Path(args.root), Path(args.out)
    data_dir = out / "trackers" / "MOT17-train" / args.name / "data"
    seqs = sorted(p.stem for p in data_dir.glob("*.txt"))
    if not seqs:
        print(f"no result files in {data_dir}", file=sys.stderr)
        return 1

    # TrackEval wants GT in <gt>/MOT17-train/<seq>/{gt/gt.txt, seqinfo.ini}
    gt_dir = out / "gt" / "MOT17-train"
    for s in seqs:
        dst = gt_dir / s
        (dst / "gt").mkdir(parents=True, exist_ok=True)
        shutil.copy(root / s / "gt" / "gt.txt", dst / "gt" / "gt.txt")
        shutil.copy(root / s / "seqinfo.ini", dst / "seqinfo.ini")

    sys.path.insert(0, str(Path(args.trackeval).resolve()))
    import trackeval

    eval_config = trackeval.Evaluator.get_default_eval_config()
    eval_config.update({"USE_PARALLEL": False, "PLOT_CURVES": False, "PRINT_CONFIG": False})

    dataset_config = trackeval.datasets.MotChallenge2DBox.get_default_dataset_config()
    dataset_config.update({
        "GT_FOLDER": str(out / "gt"),
        "TRACKERS_FOLDER": str(out / "trackers"),
        "BENCHMARK": "MOT17",
        "SPLIT_TO_EVAL": "train",
        "TRACKERS_TO_EVAL": [args.name],
        "CLASSES_TO_EVAL": ["pedestrian"],
        "SEQ_INFO": {s: None for s in seqs},
        "PRINT_CONFIG": False,
    })

    evaluator = trackeval.Evaluator(eval_config)
    dataset = trackeval.datasets.MotChallenge2DBox(dataset_config)
    metrics = [trackeval.metrics.HOTA(), trackeval.metrics.CLEAR(), trackeval.metrics.Identity()]
    evaluator.evaluate([dataset], metrics)
    return 0


if __name__ == "__main__":
    sys.exit(main())