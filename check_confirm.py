import cv2

from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.tracker import PersonTracker

VIDEO = "data/demo1.mp4"
MANUAL_COUNT = 22
CONF = 0.55

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)

tracker = PersonTracker(conf=CONF)
flt = ConfirmedTrackFilter(fps=fps, min_seconds=0.5)

raw_ids, confirmed_ids = set(), set()
frames_seen = {}

n = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    tracks = tracker(frame)
    for t in tracks:
        raw_ids.add(t.id)
        frames_seen[t.id] = frames_seen.get(t.id, 0) + 1
    for t in flt.update(tracks):
        confirmed_ids.add(t.id)
    n += 1
cap.release()

dropped = sorted(raw_ids - confirmed_ids)
print(f"frames: {n}, fps: {fps:.1f}, min_hits: {flt.min_hits}, conf: {CONF}")
print(f"raw unique IDs:       {len(raw_ids)}")
print(f"confirmed unique IDs: {len(confirmed_ids)}")
print(f"manual count:         {MANUAL_COUNT}")
print(f"dropped IDs ({len(dropped)}): " + ", ".join(f"{i}({frames_seen[i]}f)" for i in dropped))