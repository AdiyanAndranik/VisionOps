import json
import sys

import cv2
import numpy as np

VIDEO = sys.argv[1] if len(sys.argv) > 1 else "data/demo1.mp4"
FRAME = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SCALE = 0.5  # window is half size, clicks are mapped back to full-res

cap = cv2.VideoCapture(VIDEO)
cap.set(cv2.CAP_PROP_POS_FRAMES, FRAME)
ok, frame = cap.read()
cap.release()
if not ok:
    raise SystemExit(f"could not read frame {FRAME} of {VIDEO}")

points = []


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((int(x / SCALE), int(y / SCALE)))


def render():
    img = cv2.resize(frame, None, fx=SCALE, fy=SCALE)
    pts = np.array([(int(x * SCALE), int(y * SCALE)) for x, y in points], np.int32)
    if len(pts) >= 2:
        cv2.polylines(img, [pts], len(pts) >= 3, (0, 255, 0), 2)
    for p in pts:
        cv2.circle(img, (int(p[0]), int(p[1])), 4, (0, 0, 255), -1)
    return img


cv2.namedWindow("pick")
cv2.setMouseCallback("pick", on_mouse)
print("left click = add point | z = undo | c = clear | p = print JSON | q = quit")

while True:
    cv2.imshow("pick", render())
    k = cv2.waitKey(30) & 0xFF
    if k == ord("z") and points:
        points.pop()
    elif k == ord("c"):
        points.clear()
    elif k == ord("p"):
        print(json.dumps([list(p) for p in points]))
    elif k == ord("q"):
        break

cv2.destroyAllWindows()