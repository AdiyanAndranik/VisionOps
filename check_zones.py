import cv2
import numpy as np

from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.tracker import PersonTracker
from src.pipeline.zones import ZoneSet

VIDEO = "data/demo1.mp4"
ZONES = "configs/zones.json"
CONF = 0.55
SCALE = 0.5  # display size only

COLORS = [(0, 255, 0), (255, 128, 0), (0, 200, 255), (255, 0, 255)]

zs = ZoneSet.from_json(ZONES)
polys = [
    (z.name, np.array(list(z.polygon.exterior.coords)[:-1], np.int32))
    for z in zs.zones
]

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
tracker = PersonTracker(conf=CONF)
flt = ConfirmedTrackFilter(fps=fps, min_seconds=0.5)

seen = {z.name: set() for z in zs.zones}

while True:
    ok, frame = cap.read()
    if not ok:
        break

    confirmed = flt.update(tracker(frame))
    assigned = zs.assign(confirmed)

    layer = frame.copy()
    for i, (_, pts) in enumerate(polys):
        cv2.fillPoly(layer, [pts], COLORS[i % len(COLORS)])
    frame = cv2.addWeighted(layer, 0.25, frame, 0.75, 0)
    for i, (name, pts) in enumerate(polys):
        c = COLORS[i % len(COLORS)]
        cv2.polylines(frame, [pts], True, c, 3)
        cv2.putText(frame, name, tuple(int(v) for v in pts[0]),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, c, 2)

    for t in confirmed:
        names = assigned[t.id]
        for n in names:
            seen[n].add(t.id)
        fx, fy = (int(v) for v in t.foot)
        cv2.rectangle(frame, (int(t.x1), int(t.y1)), (int(t.x2), int(t.y2)), (255, 255, 255), 2)
        cv2.circle(frame, (fx, fy), 8, (0, 255, 255) if names else (0, 0, 255), -1)
        label = f"{t.id} " + ",".join(names)
        cv2.putText(frame, label, (int(t.x1), int(t.y1) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    cv2.imshow("zones", cv2.resize(frame, None, fx=SCALE, fy=SCALE))
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
for name, ids in seen.items():
    print(f"{name}: {len(ids)} unique IDs entered")