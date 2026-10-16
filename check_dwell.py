import statistics

import cv2

from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.dwell import DwellTracker
from src.pipeline.tracker import PersonTracker
from src.pipeline.zones import ZoneSet

VIDEO = "data/demo1.mp4"
ZONES = "configs/zones.json"
CONF = 0.55

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
tracker = PersonTracker(conf=CONF)
flt = ConfirmedTrackFilter(fps=fps, min_seconds=0.5)
dwell = DwellTracker(ZoneSet.from_json(ZONES), fps=fps)

events = []
while True:
    ok, frame = cap.read()
    if not ok:
        break
    events += dwell.update(flt.update(tracker(frame)))
cap.release()
events += dwell.finish()

visits = sorted((e for e in events if e.kind == "exit"), key=lambda e: e.start_s)
print("zone | id | start -> end | dwell")
for e in visits:
    print(f"{e.zone} | id {e.track_id} | {e.start_s:.2f}s -> {e.time_s:.2f}s | {e.dwell_s:.2f}s")

print()
for z in dict.fromkeys(e.zone for e in visits):
    d = [e.dwell_s for e in visits if e.zone == z]
    print(f"{z}: {len(d)} visits, median {statistics.median(d):.2f}s, "
          f"min {min(d):.2f}s, max {max(d):.2f}s")
print(f"total visits: {len(visits)}")