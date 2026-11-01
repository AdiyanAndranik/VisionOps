# VisionOps

Video analytics that turns CCTV footage into structured events and metrics: zone entries/exits, dwell time, line crossings, occupancy, heatmaps.

Detection uses Ultralytics YOLO, which is AGPL-3.0. Commercial client work may need an Ultralytics enterprise license or a different detector.

Footage sources and licenses: docs/footage.md

## What it does

Video file or RTSP stream → YOLO (people only) → ByteTrack → zones and lines → events → PostgreSQL → FastAPI (REST + WebSocket) → React dashboard.

- Counts line crossings with direction, and zone visits with dwell time
- Presence heatmap per run
- Annotated video (boxes, ids, zones, lines, live counters) that plays in the dashboard; click an event to jump to it
- Live event feed while a run is in progress

Zone and line logic is written by hand on shapely, not taken from a library.