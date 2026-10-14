from dataclasses import dataclass

import numpy as np
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
    def __init__(self, weights="yolo11n.pt", imgsz=640, conf=0.35,
                 device=0, quantize=32, tracker="configs/bytetrack_custom.yaml"):
        self.model = YOLO(weights)
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self.quantize = quantize
        self.tracker = tracker

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

    