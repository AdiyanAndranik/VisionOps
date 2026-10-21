from dataclasses import dataclass
from pathlib import Path

import numpy as np
import ultralytics
import yaml
from ultralytics import YOLO

PERSON_CLASS = 0


@dataclass
class Track:
    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float

    @property
    def foot(self):
        # bottom-center of the box, this is the point zones will use later
        return int((self.x1 + self.x2) / 2), int(self.y2)


class PersonTracker:
    def __init__(self, weights="yolo11n.pt", imgsz=640, conf=0.55,
                 device=0, quantize=32, tracker="configs/bytetrack_custom.yaml"):
        self.model = YOLO(weights)
        self.weights = weights
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self.quantize = quantize
        self.tracker = tracker

    def config(self) -> dict:
        """Settings that shaped the tracks, for the run snapshot."""
        try:
            params = yaml.safe_load(Path(self.tracker).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            params = None
        return {
            "weights": self.weights,
            "imgsz": self.imgsz,
            "conf": self.conf,
            "device": self.device,
            "quantize": self.quantize,
            "tracker": self.tracker,
            "tracker_params": params,
            "ultralytics": ultralytics.__version__,
        }

    def __call__(self, frame: np.ndarray) -> list[Track]:
        result = self.model.track(
            frame,
            persist=True,
            tracker=self.tracker,
            classes=[PERSON_CLASS],
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            quantize=self.quantize,
            verbose=False,
        )[0]
        if result.boxes.id is None:
            return []
        xyxy = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.int().cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        return [
            Track(int(i), float(b[0]), float(b[1]), float(b[2]), float(b[3]), float(c))
            for b, i, c in zip(xyxy, ids, confs)
        ]

    