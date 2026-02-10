"""
Lightweight gameplay video recorder.
Tries imageio (ffmpeg) first, then OpenCV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


class VideoRecorder:
    def __init__(self, path: Path, fps: float = 35.0):
        self.path = Path(path)
        self.fps = float(fps)
        self._backend = None
        self._writer = None
        self._cv2 = None
        self._frame_size = None

        try:
            import imageio.v2 as imageio
            self._backend = "imageio"
            self._writer = imageio.get_writer(
                str(self.path),
                fps=self.fps,
                codec="libx264",
                quality=8,
            )
            return
        except Exception:
            pass

        try:
            import cv2
            self._backend = "cv2"
            self._cv2 = cv2
            return
        except Exception:
            pass

        raise RuntimeError("No video backend available (imageio/cv2 missing)")

    def add_frame(self, frame: np.ndarray) -> None:
        if frame is None:
            return
        if frame.ndim == 2:
            frame = np.stack([frame, frame, frame], axis=2)
        if frame.ndim != 3 or frame.shape[2] < 3:
            return

        if self._backend == "imageio":
            self._writer.append_data(frame[:, :, :3])
            return

        if self._backend == "cv2":
            h, w = frame.shape[:2]
            if self._writer is None:
                fourcc = self._cv2.VideoWriter_fourcc(*"mp4v")
                self._frame_size = (w, h)
                self._writer = self._cv2.VideoWriter(
                    str(self.path), fourcc, self.fps, self._frame_size
                )
            if self._writer is None:
                return
            bgr = self._cv2.cvtColor(frame[:, :, :3], self._cv2.COLOR_RGB2BGR)
            self._writer.write(bgr)

    def close(self) -> None:
        if self._backend == "imageio":
            if self._writer is not None:
                self._writer.close()
        elif self._backend == "cv2":
            if self._writer is not None:
                self._writer.release()
