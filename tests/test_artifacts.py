from types import SimpleNamespace

import cv2
import numpy as np
from fastapi.testclient import TestClient

import src.api.main as api_main
from src.worker.artifacts import ArtifactWriter


def test_writer_saves_frame_and_heatmap(tmp_path):
    frame = np.full((120, 160, 3), 80, np.uint8)
    track = SimpleNamespace(foot=(80, 60))
    w = ArtifactWriter(tmp_path, 7, fps=10)
    for _ in range(10):
        w.update(frame, [track])
    w.finish()

    run_dir = tmp_path / "7"
    assert (run_dir / "frame.jpg").is_file()
    heat = cv2.imread(str(run_dir / "heatmap.jpg"))
    assert heat.shape == frame.shape


def test_writer_without_frames_writes_no_heatmap(tmp_path):
    w = ArtifactWriter(tmp_path, 8, fps=10)
    w.finish()
    assert not (tmp_path / "8" / "heatmap.jpg").exists()


def test_writer_removes_stale_images(tmp_path):
    d = tmp_path / "3"
    d.mkdir()
    (d / "frame.jpg").write_bytes(b"old")
    (d / "heatmap.jpg").write_bytes(b"old")
    ArtifactWriter(tmp_path, 3, fps=10)
    assert not (d / "frame.jpg").exists()
    assert not (d / "heatmap.jpg").exists()


def test_api_serves_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "ARTIFACTS_DIR", tmp_path)
    d = tmp_path / "5"
    d.mkdir()
    (d / "frame.jpg").write_bytes(b"jpgdata")

    client = TestClient(api_main.app)  # no `with`: skips the db listener
    r = client.get("/runs/5/frame")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == b"jpgdata"
    assert client.get("/runs/5/heatmap").status_code == 404
    assert client.get("/runs/6/frame").status_code == 404