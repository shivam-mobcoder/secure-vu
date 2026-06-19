"""Continuous recording segments and per-camera health registry."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

_health_lock = threading.Lock()
_health_by_camera: dict[int, dict] = {}


def update_camera_health(
    camera_id: int | None,
    *,
    last_frame_ts: float | None = None,
    reconnect_count: int | None = None,
) -> None:
    if camera_id is None:
        return
    try:
        cam = int(camera_id)
    except Exception:
        return
    now = time.time()
    with _health_lock:
        rec = _health_by_camera.setdefault(
            cam,
            {
                "last_frame_ts": 0.0,
                "reconnect_count": 0,
                "updated_at": now,
            },
        )
        if last_frame_ts is not None:
            rec["last_frame_ts"] = float(last_frame_ts)
        if reconnect_count is not None:
            rec["reconnect_count"] = int(reconnect_count)
        rec["updated_at"] = now


def get_camera_health_snapshot(now_ts: float | None = None) -> dict[int, dict]:
    now_ts = now_ts or time.time()
    out: dict[int, dict] = {}
    with _health_lock:
        for cam, rec in _health_by_camera.items():
            last = float(rec.get("last_frame_ts", 0.0))
            if last <= 0:
                status = "offline"
            elif now_ts - last <= 10.0:
                status = "online"
            elif now_ts - last <= 60.0:
                status = "stale"
            else:
                status = "offline"
            out[cam] = {
                "camera_id": cam,
                "status": status,
                "last_frame_ts": last,
                "reconnect_count": int(rec.get("reconnect_count", 0)),
            }
    return out


class SegmentWriter:
    """Write time-chunked MP4 segments from raw RTSP frames."""

    def __init__(
        self,
        camera_id: int | None,
        out_dir: Path,
        segment_secs: int = 300,
        fps: int = 10,
    ):
        self.camera_id = camera_id
        self.out_dir = Path(out_dir)
        self.segment_secs = max(30, int(segment_secs))
        self.fps = max(1, int(fps))
        self._writer = None
        self._segment_start = 0.0
        self._segment_path: Path | None = None
        self._lock = threading.Lock()
        self._last_write = 0.0
        self._on_segment_closed = None

    def set_on_segment_closed(self, callback) -> None:
        self._on_segment_closed = callback

    def write(self, frame, ts: float | None = None) -> None:
        if frame is None:
            return
        ts = float(ts or time.time())
        min_dt = 1.0 / float(self.fps)
        with self._lock:
            if self._last_write and (ts - self._last_write) < min_dt:
                return
            self._last_write = ts
            if self._writer is None or (ts - self._segment_start) >= self.segment_secs:
                self._rotate(ts, frame)
            if self._writer is not None:
                self._writer.write(frame)

    def _rotate(self, ts: float, frame) -> None:
        self._close_writer(ts)
        try:
            cam = int(self.camera_id) if self.camera_id is not None else -1
        except Exception:
            cam = -1
        day_dir = self.out_dir / datetime.fromtimestamp(ts).strftime("%Y-%m-%d") / f"cam{cam}"
        day_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(ts).strftime("%H%M%S")
        path = day_dir / f"{stamp}.mp4"
        h, w = frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(path), fourcc, float(self.fps), (int(w), int(h)))
        if not writer.isOpened():
            return
        self._writer = writer
        self._segment_start = ts
        self._segment_path = path

    def _close_writer(self, ts: float) -> None:
        if self._writer is None:
            return
        try:
            self._writer.release()
        except Exception:
            pass
        path = self._segment_path
        start = self._segment_start
        self._writer = None
        self._segment_path = None
        if path and path.exists() and self._on_segment_closed:
            try:
                size = path.stat().st_size
            except Exception:
                size = 0
            try:
                self._on_segment_closed(
                    {
                        "camera_id": self.camera_id,
                        "path": str(path),
                        "start_ts": start,
                        "end_ts": ts,
                        "size_bytes": size,
                    }
                )
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            self._close_writer(time.time())
