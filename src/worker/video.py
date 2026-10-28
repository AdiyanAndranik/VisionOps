"""Pipe BGR frames into ffmpeg and get an H.264 mp4 that browsers can play."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np


class FfmpegWriter:
    def __init__(self, path: str | Path, width: int, height: int, fps: float,
                 crf: int = 23, preset: str = "veryfast"):
        exe = shutil.which("ffmpeg")
        if not exe:
            raise RuntimeError("ffmpeg not found on PATH")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.width = width
        self.height = height
        self._err = tempfile.TemporaryFile()
        cmd = [
            exe, "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{width}x{height}", "-r", f"{fps}",
            "-i", "-",
            "-an",
            # yuv420p needs even sides, pad by at most one pixel
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(self.path),
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=self._err)

    def _ffmpeg_error(self) -> str:
        self._err.seek(0)
        return self._err.read().decode("utf-8", "replace").strip()

    def write(self, frame: np.ndarray) -> None:
        if frame.shape[:2] != (self.height, self.width):
            raise ValueError(f"frame is {frame.shape[1]}x{frame.shape[0]}, writer expects {self.width}x{self.height}")
        try:
            self.proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        except (BrokenPipeError, OSError):
            raise RuntimeError(f"ffmpeg stopped: {self._ffmpeg_error()}") from None

    def close(self) -> None:
        """Finish the file. Raises if ffmpeg failed."""
        try:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
        except OSError:
            pass
        code = self.proc.wait()
        msg = self._ffmpeg_error()
        self._err.close()
        if code != 0:
            raise RuntimeError(f"ffmpeg exited with {code}: {msg}")

    def abort(self) -> None:
        """Stop ffmpeg and remove the half-written file (crash or Ctrl+C)."""
        try:
            self.proc.kill()
            self.proc.wait()
        finally:
            self._err.close()
            self.path.unlink(missing_ok=True)