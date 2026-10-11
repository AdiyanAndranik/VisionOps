import cv2
import numpy as np

from src.pipeline.run import main


def make_video(path, n=20, size=(320, 240), fps=10):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for i in range(n):
        frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        cv2.rectangle(frame, (10 + i * 5, 50), (60 + i * 5, 150), (0, 255, 0), -1)
        w.write(frame)
    w.release()


def test_reads_video_without_display(tmp_path):
    video = tmp_path / "synthetic.mp4"
    make_video(video)
    assert main(["--video", str(video), "--no-display"]) == 0


def test_max_frames(tmp_path, capsys):
    video = tmp_path / "synthetic.mp4"
    make_video(video, n=20)
    assert main(["--video", str(video), "--no-display", "--max-frames", "5"]) == 0
    assert "read 5 frames" in capsys.readouterr().out


def test_missing_file_fails(tmp_path):
    assert main(["--video", str(tmp_path / "nope.mp4"), "--no-display"]) == 1

    