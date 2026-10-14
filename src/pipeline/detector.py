from dataclasses import dataclass

import numpy as np
from ultralytics import YOLO

PERSON_CLASS = 0


@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float


class PersonDetector:
    def __init__(self, weights="yolo11n.pt", imgsz=640, conf=0.35,
                 device=0, quantize=16):
        self.model = YOLO(weights)
        self.imgsz = imgsz
        self.conf = conf
        self.device = device
        self.quantize = quantize

    def __call__(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.predict(
            frame,
            classes=[PERSON_CLASS],
            imgsz=self.imgsz,
            conf=self.conf,
            device=self.device,
            quantize=self.quantize,
            verbose=False,
        )[0]
        out = []
        for (x1, y1, x2, y2), c in zip(result.boxes.xyxy.cpu().numpy(),
                                       result.boxes.conf.cpu().numpy()):
            out.append(Detection(float(x1), float(y1), float(x2), float(y2), float(c)))
        return out

    