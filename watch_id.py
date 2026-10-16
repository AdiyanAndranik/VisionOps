import sys

import cv2

from src.pipeline.lines import LineCounter
from src.pipeline.tracker import PersonTracker

VIDEO = "data/demo1.mp4"
ID = int(sys.argv[1]) if len(sys.argv) > 1 else 19
START = float(sys.argv[2]) if len(sys.argv) > 2 else 18.0
END = float(sys.argv[3]) if len(sys.argv) > 3 else 22.5
CONF = 0.55
SCALE = 0.6
DELAY_MS = 100  # bigger = slower playback

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
lines = LineCounter.from_json("configs/lines.json", fps=fps).lines
tracker = PersonTracker(conf=CONF)

print(f"ID {ID}, {START}s to {END}s")
print("Tracking up to the start point, wait a few seconds...")
print("space = pause/resume | any key while paused = next frame | q = quit")

paused = False
n = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    tracks = tracker(frame)  # runs on every frame so the IDs match the earlier run
    t = n / fps
    n += 1
    if t < START:
        continue
    if t > END:
        break

    for l in lines:
        cv2.line(frame, tuple(int(v) for v in l.a), tuple(int(v) for v in l.b), (0, 255, 0), 2)

    for tr in tracks:
        hot = tr.id == ID
        color = (0, 0, 255) if hot else (255, 255, 255)
        cv2.rectangle(frame, (int(tr.x1), int(tr.y1)), (int(tr.x2), int(tr.y2)), color, 4 if hot else 2)
        cv2.circle(frame, tuple(int(v) for v in tr.foot), 8, (0, 255, 255), -1)
        cv2.putText(frame, str(tr.id), (int(tr.x1), int(tr.y1) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3)

    cv2.putText(frame, f"frame {n - 1}  t={t:.2f}s", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
    cv2.imshow("watch", cv2.resize(frame, None, fx=SCALE, fy=SCALE))

    k = cv2.waitKey(0 if paused else DELAY_MS) & 0xFF
    if k == ord("q"):
        break
    if k == 32:  # space
        paused = not paused

cap.release()
cv2.destroyAllWindows()