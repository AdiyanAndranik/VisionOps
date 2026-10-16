import cv2

from src.pipeline.confirm import ConfirmedTrackFilter
from src.pipeline.lines import LineCounter
from src.pipeline.tracker import PersonTracker

VIDEO = "data/demo1.mp4"
LINES = "configs/lines.json"
CONF = 0.55
SCALE = 0.5  # display size only

cap = cv2.VideoCapture(VIDEO)
fps = cap.get(cv2.CAP_PROP_FPS)
tracker = PersonTracker(conf=CONF)
flt = ConfirmedTrackFilter(fps=fps, min_seconds=0.5)
counter = LineCounter.from_json(LINES, fps=fps, confirm_seconds=0.5)

all_events = []
flash = {}  # line name -> frames left to draw it highlighted

while True:
    ok, frame = cap.read()
    if not ok:
        break

    confirmed = flt.update(tracker(frame))
    for e in counter.update(confirmed):
        all_events.append(e)
        flash[e.line] = 10
        print(f"t={e.frame / fps:6.2f}s  id={e.track_id:<3} {e.line}: {e.direction}")

    for t in confirmed:
        fx, fy = (int(v) for v in t.foot)
        cv2.rectangle(frame, (int(t.x1), int(t.y1)), (int(t.x2), int(t.y2)), (255, 255, 255), 2)
        cv2.circle(frame, (fx, fy), 8, (0, 255, 255), -1)
        cv2.putText(frame, str(t.id), (int(t.x1), int(t.y1) - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    y_text = 40
    for line in counter.lines:
        hot = flash.get(line.name, 0) > 0
        flash[line.name] = max(0, flash.get(line.name, 0) - 1)
        color = (0, 0, 255) if hot else (0, 255, 0)
        a = tuple(int(v) for v in line.a)
        b = tuple(int(v) for v in line.b)
        cv2.line(frame, a, b, color, 4 if hot else 2)

        # "+" marker on the positive side, at the line midpoint
        nx, ny = line.normal()
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        cv2.putText(frame, "+" + line.pos_label, (int(mx + nx * 50), int(my + ny * 50)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

        c = counter.counts[line.name]
        txt = f"{line.name}: {line.pos_label}={c[line.pos_label]}  {line.neg_label}={c[line.neg_label]}"
        cv2.putText(frame, txt, (20, y_text), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        y_text += 40

    cv2.imshow("lines", cv2.resize(frame, None, fx=SCALE, fy=SCALE))
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
print()
for name, c in counter.counts.items():
    print(f"{name}: {c}")
print(f"total events: {len(all_events)}")