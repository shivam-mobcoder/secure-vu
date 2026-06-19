#!/usr/bin/env python3
from __future__ import annotations
import os
from dotenv import load_dotenv

from pathlib import Path
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path)


os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|stimeout;5000000|rw_timeout;5000000"
)
os.environ.setdefault("OPENCV_FFMPEG_THREAD_COUNT", "1")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
import sys

import torch

# --------------------------------------------------
# TORCH PERFORMANCE DEFAULTS
# --------------------------------------------------
# These are safe defaults; actual GPU usage still depends on having a CUDA-enabled
# PyTorch build and a working NVIDIA driver.
try:
    # Prefer speed on supported backends; no effect on older GPUs.
    torch.set_float32_matmul_precision("high")
except Exception:
    pass
torch.set_float32_matmul_precision("high")


# If this machine doesn't have a working CUDA device, prevent InsightFace/ONNXRuntime
# from attempting to initialize the CUDA execution provider.
FORCE_INSIGHTFACE_CPU = os.getenv("FORCE_INSIGHTFACE_CPU", "0").strip() == "1"
if FORCE_INSIGHTFACE_CPU or not torch.cuda.is_available():
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    os.environ.setdefault("ORT_DISABLE_CUDA", "1")

import cv2
import json
import asyncpg
import time
from datetime import datetime
from copy import deepcopy
import asyncio
import logging
import numpy as np
from ssl import SSLContext
import ssl
import argparse
from queue import Queue
from fractions import Fraction
import threading
import secrets
import re
from urllib.parse import quote
from aiohttp import web, WSMsgType
from collections import deque
from time import monotonic
import psutil
import subprocess

# Optional auth/RBAC modules
auth_middleware = None
login = None
signup = None
user_can_access_camera = None
can = None
db_get_camera = None
set_pool = None
AUTH_READY = False

try:
    from middleware import auth_middleware  # type: ignore
except Exception as e:
    print(f"[AUTH] middleware import failed: {e}")

try:
    from auth import login, signup  # type: ignore
except Exception as e:
    print(f"[AUTH] login import failed: {e}")

try:
    from rbac import user_can_access_camera, can  # type: ignore

    AUTH_READY = True
except Exception as e:
    print(f"[AUTH] rbac import failed: {e}")

try:
    from db import (  # type: ignore
        db_get_camera,
        set_pool,
        db_list_users_by_client,
        db_get_user_by_id,
        db_update_user_permissions,
        db_insert_alert,
        db_list_alerts,
        db_insert_recording_segment,
        db_list_recording_segments,
        db_list_cameras_for_client,
    )
except Exception as e:
    print(f"[AUTH] db helper import failed: {e}")

from security.roles import require_role

from ultralytics import YOLO
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import ROOT as ULTRA_ROOT
from types import SimpleNamespace
import yaml
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer,
    RTCRtpSender,
)
from aiortc.mediastreams import VideoStreamTrack
from av import VideoFrame

cv2.setNumThreads(0)
cv2.ocl.setUseOpenCL(False)
try:
    # Hide noisy OpenCV FFmpeg warnings like stream timeout callbacks.
    cv2.setLogLevel(cv2.LOG_LEVEL_ERROR)
except Exception:
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass


face_db_lock = threading.Lock()
# Serialises InsightFace GPU inference across camera threads.
# acquire(blocking=False) so a camera that can't get the lock simply
# skips face-id this frame and uses the cached name instead of blocking.
faceid_inference_lock = threading.Lock()

# Per-camera frame counters (keyed by camera_id).  Using a single global
# counter means all 4 RTSP threads hit should_faceid_now on the same tick,
# firing 4 concurrent InsightFace calls at once.
_cam_frame_counters: dict = {}
_cam_frame_counters_lock = threading.Lock()


def _get_cam_frame_counter(camera_id) -> int:
    key = camera_id if camera_id is not None else "default"
    with _cam_frame_counters_lock:
        _cam_frame_counters[key] = _cam_frame_counters.get(key, 0) + 1
        return _cam_frame_counters[key]


def log_step(name, t0):
    try:
        if not PROCESS_FRAME_DEBUG:
            return time.perf_counter()
    except Exception:
        pass
    dt = (time.perf_counter() - t0) * 1000
    print(f"[PERF] {name:<12} {dt:6.2f} ms | thread={threading.get_ident()}")
    return time.perf_counter()


ENROLLMENT_ACTIVE = False

# Face enrollment imports
from insightface.app import FaceAnalysis

# Always run in CCTV mode; local USB device support removed.
MODE = "cctv"
print(f"🔁 Running in {MODE.upper()} mode")

# RTSP may be configured regardless of MODE so the UI can switch sources
# without restarting the server. RTSP is only *opened* when source=='cctv'.
RTSP_URLS = {
    1: os.getenv(
        "RTSP_URL_1",
        "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=1&subtype=0",
    ).strip(),
    2: os.getenv(
        "RTSP_URL_2",
        "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=2&subtype=0",
    ).strip(),
    3: os.getenv(
        "RTSP_URL_3",
        "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=3&subtype=0",
    ).strip(),
    4: os.getenv(
        "RTSP_URL_4",
        "rtsp://test:qazwsx2580@192.168.2.25:554/cam/realmonitor?channel=4&subtype=0",
    ).strip(),
}

# Backward-compat single RTSP URL (optional override)
RTSP_URL = os.getenv("RTSP_URL", RTSP_URLS.get(1, "")).strip() or None


def _with_subtype(url: str, subtype: int) -> str:
    try:
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["subtype"] = str(int(subtype))
        new_query = urlencode(query, doseq=True)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
        )
    except Exception:
        # Best-effort fallback: append/replace manually
        if "subtype=" in url:
            prefix, _ = url.split("subtype=", 1)
            return f"{prefix}subtype={int(subtype)}"
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}subtype={int(subtype)}"


def _get_rtsp_url(camera_id: int | None, subtype: int | None = None) -> str | None:
    if camera_id is None:
        base = RTSP_URL
        return _with_subtype(base, subtype) if (base and subtype is not None) else base
    try:
        cam_id = int(camera_id)
    except Exception:
        base = RTSP_URL
        return _with_subtype(base, subtype) if (base and subtype is not None) else base
    url = RTSP_URLS.get(cam_id) or RTSP_URL
    if not url:
        return None
    return _with_subtype(url, subtype) if subtype is not None else url


if RTSP_URL or any(RTSP_URLS.values()):
    configured = [str(k) for k, v in RTSP_URLS.items() if v]
    print(
        f"📶 RTSP cameras configured: {', '.join(configured) if configured else 'default'}"
    )
else:
    print("📶 RTSP not configured")


def _parse_int_list_env(name: str, default: str) -> list:
    raw = os.getenv(name, default)
    out = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except Exception:
            continue
    return out


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    s = str(raw).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _bool_param(val, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


SERVER_CAMERA_FPS = int(os.getenv("SERVER_CAMERA_FPS", "30"))
GRID_CAMERA_FPS = int(os.getenv("GRID_CAMERA_FPS", "30"))   # HD: full 30 fps for all views
SERVER_CAMERA_WIDTH = int(os.getenv("SERVER_CAMERA_WIDTH", "1280"))
SERVER_CAMERA_HEIGHT = int(os.getenv("SERVER_CAMERA_HEIGHT", "720"))

# --- Output Resolution (HD: 1280×720 for all views) ---
GRID_CAMERA_WIDTH = int(os.getenv("GRID_CAMERA_WIDTH", "1280"))
GRID_CAMERA_HEIGHT = int(os.getenv("GRID_CAMERA_HEIGHT", "720"))
FOCUS_CAMERA_WIDTH = int(os.getenv("FOCUS_CAMERA_WIDTH", str(SERVER_CAMERA_WIDTH)))
FOCUS_CAMERA_HEIGHT = int(os.getenv("FOCUS_CAMERA_HEIGHT", str(SERVER_CAMERA_HEIGHT)))
RTSP_OPEN_TIMEOUT_MS = _int_env("RTSP_OPEN_TIMEOUT_MS", 5000)
RTSP_READ_TIMEOUT_MS = _int_env("RTSP_READ_TIMEOUT_MS", 5000)
RTSP_RETRY_DELAY_SEC = float(os.getenv("RTSP_RETRY_DELAY_SEC", "1.0"))

# Alert queue for thread-safe communication
alert_queue = Queue()
db_persist_queue = Queue()

# Runtime stats (thread-safe)
stats_lock = threading.Lock()
stats_counters = {
    "detection_runs": 0,  # how many times process_frame actually ran YOLO
    "outgoing_frames": 0,
}
perf_lock = threading.Lock()

def _get_hardware_stats():
    """Returns a dict of current CPU, RAM, and GPU usage metrics."""
    stats = {
        "cpu_percent": psutil.cpu_percent(),
        "ram_percent": psutil.virtual_memory().percent,
        "gpu_util": "N/A",
        "gpu_mem": "N/A"
    }
    try:
        # Quick non-blocking call to nvidia-smi if available
        # Format: utilization.gpu, memory.used, memory.total
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8", stderr=subprocess.STDOUT
        ).strip().split("\n")[0]
        data = [x.strip() for x in out.split(",")]
        if len(data) >= 3:
            stats["gpu_util"] = f"{data[0]}%"
            stats["gpu_mem"] = f"{data[1]}/{data[2]}MB"
    except Exception:
        pass
    return stats


perf_counters = {
    "frames": 0,
    "resize_ms": 0.0,
    "yolo_ms": 0.0,
    "track_ms": 0.0,
    "faceid_ms": 0.0,
    "draw_ms": 0.0,
    "total_ms": 0.0,
}

pid_identity = {}
pid_identity_lock = threading.Lock()
PID_NAME_GRACE = float(os.getenv("PID_NAME_GRACE", "0.8"))
PID_STATE_TTL = float(os.getenv("PID_STATE_TTL", "15.0"))
pid_display_map = {}
pid_display_lock = threading.Lock()
last_active_pids = set()
last_active_alert_keys = set()
frame_times = deque(maxlen=60)
# Per-camera state — keyed by camera_id (int or None).
# Replacing the 4 old shared globals that caused ghost bboxes across cameras.
_cam_state: dict = {}  # camera_id -> {"yolo_time", "yolo_frame", "draw_dets", "draw_time"}
_cam_state_lock = threading.Lock()


def _cs(camera_id):
    """Return the mutable per-camera state dict, creating it if needed."""
    key = camera_id if camera_id is not None else -1
    with _cam_state_lock:
        if key not in _cam_state:
            _cam_state[key] = {
                "yolo_time": 0.0,
                "yolo_frame": None,
                "draw_dets": [],
                "draw_time": 0.0,
            }
        return _cam_state[key]


FACE_ENABLE = os.getenv("FACE_ENABLE", "1").strip() == "1"

# --------------------------------------------------
# MODEL_SELECT — Choose which detection models to load
# --------------------------------------------------
# 1 = General Object Detection (YOLO, uses YOLO_WEIGHTS)
# 2 = Face Detection (yolov8n-face)
# 3 = Fire & Smoke Detection
# 4 = License Plate Detection (LPD)
# 5 = ALL specialized models (YOLO + face det + fire + LPD)
# 6 = PRODUCTION MODE — secure_cv_best.pt + InsightFace + all features (default)
# 8 = OPEN WORLD MODE — yolov8s-worldv2.pt (YOLO-World)
MODEL_SELECT = _int_env("MODEL_SELECT", 6)
if MODEL_SELECT not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
    print(f"⚠️ Invalid MODEL_SELECT={MODEL_SELECT}, defaulting to 7 (full package)")
    MODEL_SELECT = 7
print(f"🔧 MODEL_SELECT={MODEL_SELECT}")

# FaceID can be very expensive when ONNXRuntime is CPU-only.
# Default to a slower cadence for better FPS; override via env.
# Increased to 5 for better responsiveness as per user request (was 90)
FACE_EVERY_N_FRAMES = _int_env("FACE_EVERY_N_FRAMES", 5)
# Per-model cadence for specialized detectors (used when MODEL_SELECT=5 or 7)
FIRE_EVERY_N_FRAMES = _int_env("FIRE_EVERY_N_FRAMES", 3)
LPD_EVERY_N_FRAMES = _int_env("LPD_EVERY_N_FRAMES", 5)
FACE_DET_EVERY_N_FRAMES = _int_env("FACE_DET_EVERY_N_FRAMES", 3)

# Performance: Disable visual overlays to save CPU
DISABLE_DRAWING = _int_env("DISABLE_DRAWING", 0) == 1
if DISABLE_DRAWING:
    print("🚀 PERFORMANCE MODE: Visual overlays and drawing DISABLED (Logs only)")

# YOLO: default to smaller input for higher FPS; override via env.
YOLO_PROCESS_EVERY_N_FRAMES = _int_env("YOLO_PROCESS_EVERY_N_FRAMES", 1)
YOLO_INPUT_RESOLUTION = (
    _int_env("YOLO_INPUT_WIDTH", 1280),
    _int_env("YOLO_INPUT_HEIGHT", 1280),
)
FOCUS_YOLO_INPUT_RESOLUTION = (
    _int_env("FOCUS_YOLO_INPUT_WIDTH", 1280),
    _int_env("FOCUS_YOLO_INPUT_HEIGHT", 1280),
)
# Minimum confidence for YOLO detections passed to ByteTracker.
# Raised to 0.25 to eliminate false positives from the single-class
# person model.  ByteTracker's rescue pool still handles 0.15–0.25
# range detections that YOLO passes through (BT_TRACK_LOW_THRESH=0.15).
YOLO_MIN_CONF = float(os.getenv("YOLO_MIN_CONF", "0.25"))
PERSON_CLASS_IDS = set(_parse_int_list_env("PERSON_CLASS_IDS", default=""))
OUTGOING_TRACK_FPS = _int_env("OUTGOING_TRACK_FPS", 30)

# Performance/latency tuning
PROCESS_FRAME_DEBUG = os.getenv("PROCESS_FRAME_DEBUG", "0").strip() == "1"
PROCESSING_FPS = _int_env("PROCESSING_FPS", OUTGOING_TRACK_FPS)
PERF_STATS = os.getenv("PERF_STATS", "1").strip() == "1"

# --------------------------------------------------
# GPU / PRECISION TUNING
# --------------------------------------------------
# For max FPS on RTX: enable FP16 + AMP.
# For max quality (at lower FPS): disable FP16 + AMP.
YOLO_ENABLE_FUSE = os.getenv("YOLO_ENABLE_FUSE", "1").strip() == "1"
YOLO_ENABLE_FP16 = os.getenv("YOLO_ENABLE_FP16", "1").strip() == "1"
YOLO_TILING = os.getenv("YOLO_TILING", "0").strip() == "1"
YOLO_DET_PERSIST_SECONDS = float(os.getenv("YOLO_DET_PERSIST_SECONDS", "1.5"))
USE_BYTETRACK = True
PID_ENABLE = os.getenv("PID_ENABLE", "1").strip() == "1"
PID_REUSE_WINDOW = float(os.getenv("PID_REUSE_WINDOW", "2.0"))
WORK_TIMER_ENABLE = os.getenv("WORK_TIMER_ENABLE", "1").strip() == "1"
WORK_TIMER_REQUIRE_ROI = os.getenv("WORK_TIMER_REQUIRE_ROI", "1").strip() == "1"
WORK_TIMER_STALE_SEC = float(os.getenv("WORK_TIMER_STALE_SEC", str(PID_STATE_TTL)))
WORK_KEY_MAX_GAP_SEC = float(os.getenv("WORK_KEY_MAX_GAP_SEC", "4.0"))
WORK_KEY_MATCH_DISTANCE_PX = float(os.getenv("WORK_KEY_MATCH_DISTANCE_PX", "180"))
WORK_CROSS_CAMERA_BY_NAME = os.getenv("WORK_CROSS_CAMERA_BY_NAME", "1").strip() == "1"
WORK_EMBED_REID_ENABLE = os.getenv("WORK_EMBED_REID_ENABLE", "1").strip() == "1"
WORK_EMBED_MATCH_THRESHOLD = float(os.getenv("WORK_EMBED_MATCH_THRESHOLD", "0.60"))
WORK_EMBED_ROLLING_ALPHA = float(os.getenv("WORK_EMBED_ROLLING_ALPHA", "0.20"))
WORK_HYBRID_MOTION_WEIGHT = float(os.getenv("WORK_HYBRID_MOTION_WEIGHT", "0.35"))
WORK_HANDOFF_POOL_SEC = float(os.getenv("WORK_HANDOFF_POOL_SEC", "12.0"))
WORK_HANDOFF_MAX_DIST_PX = float(os.getenv("WORK_HANDOFF_MAX_DIST_PX", "260"))
WORK_DEDUPE_IOU = float(os.getenv("WORK_DEDUPE_IOU", "0.72"))



ALERT_LINE_ZONE_MIN_GAP = float(os.getenv("ALERT_LINE_ZONE_MIN_GAP", "0.30"))
ALERT_WEBROI_MIN_GAP = float(
    os.getenv("ALERT_WEBROI_MIN_GAP", str(ALERT_LINE_ZONE_MIN_GAP))
)
ALERT_KNOWN_DETECT_MIN_GAP = float(os.getenv("ALERT_KNOWN_DETECT_MIN_GAP", "20.0"))
ALERT_UNKNOWN_ONCE_TTL_SEC = float(os.getenv("ALERT_UNKNOWN_ONCE_TTL_SEC", "3600.0"))
ROI_TOUCH_MARGIN_PX = max(0.0, float(os.getenv("ROI_TOUCH_MARGIN_PX", "6.0")))
ROI_TOUCH_MIN_OVERLAP_PX = max(0.0, float(os.getenv("ROI_TOUCH_MIN_OVERLAP_PX", "1.0")))
CROSS_OVERLAY_TTL_SEC = max(0.5, float(os.getenv("CROSS_OVERLAY_TTL_SEC", "4.0")))
CROSS_OVERLAY_FLASH_HZ = max(0.0, float(os.getenv("CROSS_OVERLAY_FLASH_HZ", "2.0")))
FEED_PRESENCE_ALERT_ENABLE = os.getenv("FEED_PRESENCE_ALERT_ENABLE", "1").strip() == "1"
FEED_NEW_PERSON_MIN_HITS = _int_env("FEED_NEW_PERSON_MIN_HITS", 2)
FEED_NEW_PERSON_REALERT_SEC = float(os.getenv("FEED_NEW_PERSON_REALERT_SEC", "60.0"))
EVENT_CLIP_ENABLE = os.getenv("EVENT_CLIP_ENABLE", "1").strip() == "1"
EVENT_CLIP_SECONDS = float(os.getenv("EVENT_CLIP_SECONDS", "8.0"))
EVENT_CLIP_PRE_SECONDS = float(os.getenv("EVENT_CLIP_PRE_SECONDS", "6.0"))
EVENT_CLIP_POST_SECONDS = max(0.0, EVENT_CLIP_SECONDS - EVENT_CLIP_PRE_SECONDS)
EVENT_CLIP_FPS = max(1, _int_env("EVENT_CLIP_FPS", 6))
EVENT_CLIP_JPEG_QUALITY = max(40, min(95, _int_env("EVENT_CLIP_JPEG_QUALITY", 92)))
EVENT_CLIP_RETENTION_HOURS = max(1, _int_env("EVENT_CLIP_RETENTION_HOURS", 24))
EVENT_CLIP_DRAW_OVERLAYS = os.getenv("EVENT_CLIP_DRAW_OVERLAYS", "1").strip() == "1"
EVENT_CLIP_DIR = Path(
    os.getenv(
        "EVENT_CLIP_DIR", str(Path(__file__).resolve().parent.parent / "event_clips")
    )
)
RECORDINGS_DIR = Path(
    os.getenv(
        "RECORDINGS_DIR", str(Path(__file__).resolve().parent.parent / "recordings")
    )
)
CONTINUOUS_RECORDING_ENABLE = _bool_env("CONTINUOUS_RECORDING_ENABLE", True)
CONTINUOUS_SEGMENT_SECS = int(os.getenv("CONTINUOUS_SEGMENT_SECS", "300"))
LINGER_SECONDS = int(os.getenv("LINGER_SECONDS", "30"))
MOTION_ENABLE = _bool_env("MOTION_ENABLE", True)
MOTION_THRESH = float(os.getenv("MOTION_THRESH", "0.02"))
MOTION_ALERT_GAP_SEC = float(os.getenv("MOTION_ALERT_GAP_SEC", "30"))
MOTION_ONLY_WHEN_NO_PERSONS = _bool_env("MOTION_ONLY_WHEN_NO_PERSONS", True)
FACE_MIN_BBOX_HEIGHT = int(os.getenv("FACE_MIN_BBOX_HEIGHT", "60"))

_segment_writers_lock = threading.Lock()
_segment_writers: dict = {}

# Optional runtime-persisted feature flags (so UI toggles survive restarts).
# This is separate from .env so operators can flip features without redeploy.
RUNTIME_FLAGS_FILE = Path(__file__).resolve().parent.parent / "config" / "runtime_flags.json"


def _load_runtime_flags() -> None:
    global EVENT_CLIP_ENABLE
    try:
        if not RUNTIME_FLAGS_FILE.exists():
            return
        data = json.loads(RUNTIME_FLAGS_FILE.read_text(encoding="utf-8") or "{}")
        if isinstance(data, dict) and "event_clip_enable" in data:
            EVENT_CLIP_ENABLE = bool(data.get("event_clip_enable"))
    except Exception:
        # Never block server start on optional runtime flags.
        return


_load_runtime_flags()
ANALYTICS_ALL_CCTV = os.getenv("ANALYTICS_ALL_CCTV", "1").strip() == "1"
ANALYTICS_CAMERA_IDS = _parse_int_list_env("ANALYTICS_CAMERA_IDS", "1,2,3,4")

work_timer_lock = threading.Lock()
work_timer_state = {}
work_key_lock = threading.Lock()
work_key_by_pid = {}
work_track_state = {}
work_display_lock = threading.Lock()
work_display_map = {}
work_display_counter = 0
work_face_reid_lock = threading.Lock()
work_face_profiles = {}
work_face_profile_counter = 0
work_handoff_lock = threading.Lock()
work_handoff_pool = {}

bytetrack_lock = threading.Lock()
bytetrackers = {}
_bytetrack_args = None


def _load_bytetrack_args() -> SimpleNamespace:
    global _bytetrack_args
    if _bytetrack_args is not None:
        return _bytetrack_args
    cfg_path = ULTRA_ROOT / "cfg" / "trackers" / "bytetrack.yaml"
    try:
        data = yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        data = {}
    # ── Optimised multi-person tracking parameters for single-class person model ─
    # track_high_thresh: detections ≥ this are "high confidence" — used to create
    #   new tracks and maintain existing ones.  Raised to 0.35 so random low-conf
    #   noise doesn't create phantom person tracks.
    # track_low_thresh: detections in [track_low_thresh, track_high_thresh) form
    #   the "rescue pool" — they can re-link lost tracks but won't create new ones.
    #   Raised to 0.15 to cut out near-zero-confidence false positives.
    # new_track_thresh: minimum confidence to *initialise* a brand-new track.
    #   Set equal to track_high_thresh (0.35).
    # track_buffer 90 (3 s at 30 fps): keeps a lost track alive through brief
    #   occlusions / detection gaps, so the same ID is recovered when the person
    #   reappears rather than getting a new ID.
    # match_thresh 0.85 (> previous 0.7): accepts detection→track matches with
    #   IoU ≥ 0.15.  More permissive matching means a track can be re-linked even
    #   if the person moved somewhat between frames — the primary fix for the
    #   "box flickers / new ID every re-appearance" symptom.
    data["track_high_thresh"] = float(os.getenv("BT_TRACK_HIGH_THRESH", "0.35"))
    data["track_low_thresh"]  = float(os.getenv("BT_TRACK_LOW_THRESH",  "0.15"))
    data["new_track_thresh"]  = float(os.getenv("BT_NEW_TRACK_THRESH",  "0.35"))
    data["track_buffer"]      = int(os.getenv("BT_TRACK_BUFFER",        "90"))
    data["match_thresh"]      = float(os.getenv("BT_MATCH_THRESH",      "0.85"))
    data.setdefault("fuse_score", True)
    _bytetrack_args = SimpleNamespace(**data)
    return _bytetrack_args


def _get_bytetracker(camera_id: int | None, frame_rate: int = 30) -> BYTETracker:
    key = int(camera_id) if camera_id is not None else -1
    with bytetrack_lock:
        tracker = bytetrackers.get(key)
        if tracker is None:
            tracker = BYTETracker(_load_bytetrack_args(), frame_rate=frame_rate)
            bytetrackers[key] = tracker
    return tracker


def _apply_bytetrack(raw_dets, frame, camera_id, label_fn):
    if not raw_dets:
        return []
    data = []
    for det in raw_dets:
        x1, y1, x2, y2 = det.get("box", (0, 0, 0, 0))
        conf = det.get("conf")
        cls_id = det.get("cls_id")
        data.append(
            [
                float(x1),
                float(y1),
                float(x2),
                float(y2),
                float(conf if conf is not None else 0.0),
                float(cls_id if cls_id is not None else 0),
            ]
        )
    boxes = Boxes(np.asarray(data, dtype=np.float32), frame.shape[:2])
    tracker = _get_bytetracker(camera_id, frame_rate=PROCESSING_FPS)
    tracks = tracker.update(boxes, img=frame)
    if tracks is None or len(tracks) == 0:
        return []
    tracked = []
    for t in tracks.tolist():
        x1, y1, x2, y2, track_id, score, cls_id, _idx = t
        cls_int = int(cls_id)
        tracked.append(
            {
                "box": [x1, y1, x2, y2],
                "cls_id": cls_int,
                "conf": float(score),
                "label": label_fn(cls_int),
                "track_id": int(track_id),
            }
        )
    return tracked


def _bbox_iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(float(ax1), float(bx1))
    iy1 = max(float(ay1), float(by1))
    ix2 = min(float(ax2), float(bx2))
    iy2 = min(float(ay2), float(by2))
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    aa = max(0.0, float(ax2) - float(ax1)) * max(0.0, float(ay2) - float(ay1))
    bb = max(0.0, float(bx2) - float(bx1)) * max(0.0, float(by2) - float(by1))
    denom = aa + bb - inter
    return (inter / denom) if denom > 0 else 0.0


def _dedupe_overlapping_dets(dets: list[dict], iou_thr: float = 0.7) -> list[dict]:
    if not dets:
        return []
    sorted_dets = sorted(
        dets,
        key=lambda d: float(d.get("conf") if d.get("conf") is not None else 0.0),
        reverse=True,
    )
    keep = []
    for d in sorted_dets:
        box = d.get("box", (0, 0, 0, 0))
        cls_id = d.get("cls_id")
        skip = False
        for k in keep:
            if cls_id != k.get("cls_id"):
                continue
            if _bbox_iou(box, k.get("box", (0, 0, 0, 0))) >= iou_thr:
                skip = True
                break
        if not skip:
            keep.append(d)
    return keep


def _motion_similarity(
    c1: tuple[float, float] | None, c2: tuple[float, float] | None, max_dist: float
) -> float:
    if c1 is None or c2 is None:
        return 0.5
    try:
        dx = float(c1[0]) - float(c2[0])
        dy = float(c1[1]) - float(c2[1])
        d = (dx * dx + dy * dy) ** 0.5
        if max_dist <= 1e-6:
            return 0.0
        return max(0.0, 1.0 - min(1.0, d / float(max_dist)))
    except Exception:
        return 0.5


def _hybrid_face_motion_score(face_sim: float, motion_sim: float) -> float:
    w = max(0.0, min(1.0, float(WORK_HYBRID_MOTION_WEIGHT)))
    return ((1.0 - w) * float(face_sim)) + (w * float(motion_sim))


# --------------------------------------------------
# IMPORT MODULES
# --------------------------------------------------
ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
sys.path.append(str(REPO_ROOT))

try:
    from app.faceid import FaceIDManager
except Exception:
    from faceid import FaceIDManager

try:
    from app.tracking import PIDTracker
except Exception:
    from tracking import PIDTracker

# --------------------------------------------------
# FACE ENROLLMENT SETUP
# --------------------------------------------------
FACE_DB_DIR = REPO_ROOT / "models" / "arcface" / "face_db"
FACE_DB_DIR.mkdir(parents=True, exist_ok=True)
FACE_DB = FACE_DB_DIR / "face_db.npz"  # legacy global (kept for backward compat)
RAW_DIR = REPO_ROOT / "faces_raw"
RAW_DIR.mkdir(exist_ok=True, parents=True)

# Import liveness module
try:
    from liveness import check_frames_liveness, get_liveness_checker  # type: ignore

    LIVENESS_ENABLED = True
    print("[LIVENESS] Liveness detection enabled")
except Exception as _le:
    LIVENESS_ENABLED = False
    print(f"[LIVENESS] Liveness detection disabled: {_le}")

    def check_frames_liveness(frames, face_data):
        return True, 1.0, []

    def get_liveness_checker():
        return None


PID_MAP_DIR = REPO_ROOT / "tracking"
PID_MAP_DIR.mkdir(exist_ok=True, parents=True)
pid_tracker_lock = threading.Lock()
pid_tracker_op_lock = threading.Lock()
pid_trackers: dict[int, PIDTracker] = {}


def _face_db_path(client_id=None) -> Path:
    """Return the per-client face DB path. Falls back to global legacy path."""
    # Always return global FACE_DB to unify all enrollments (fix for recognition failure)
    return FACE_DB


def _get_pid_tracker(camera_id: int | None) -> PIDTracker:
    key = int(camera_id) if camera_id is not None else -1
    with pid_tracker_lock:
        tracker = pid_trackers.get(key)
        if tracker is None:
            map_path = PID_MAP_DIR / f"tracker_id_map_{key}.json"
            tracker = PIDTracker(map_path=map_path)
            pid_trackers[key] = tracker
    return tracker


# Active enrollment sessions: ws_id -> {name, frames, ws, task}
enroll_sessions = {}
# token -> {"exp": float, "client_id": int|None}  (invite links)
enroll_tokens: dict[str, dict] = {}


def _enroll_token_valid(token: str) -> bool:
    meta = enroll_tokens.get(token)
    if not meta:
        return False
    exp = meta if isinstance(meta, float) else meta.get("exp", 0)
    return bool(exp and time.time() <= exp)


def _enroll_token_client_id(token: str):
    meta = enroll_tokens.get(token)
    if not meta or isinstance(meta, float):
        return None
    return meta.get("client_id")


async def create_enroll_link(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "faces", "enroll"):
        return web.Response(status=403)
    token = secrets.token_urlsafe(16)
    client_id = user.get("client_id")
    # Build absolute URL so admin can copy-paste it directly
    scheme = request.url.scheme
    host = request.url.host
    port = request.url.port
    if port and port not in (80, 443):
        base = f"{scheme}://{host}:{port}"
    else:
        base = f"{scheme}://{host}"
    enroll_tokens[token] = {"exp": time.time() + 3600, "client_id": client_id}
    return web.json_response(
        {"url": f"{base}/enroll/{token}", "token": token, "expires_in": 3600}
    )


async def enroll_page(request):
    """Serve the React SPA for /enroll/:token so SelfEnrollment.jsx handles it."""
    return await _serve_react_spa(request)


async def enroll_validate_token(request):
    """GET /api/enroll/{token}/validate — check if a share-link token is still valid."""
    token = request.match_info.get("token", "")
    valid = _enroll_token_valid(token)
    return web.json_response({"valid": valid, "expired": not valid})


async def enroll_token_frames(request):
    """
    POST /api/enroll/{token}/frames
    Accepts {name, frames: [base64...]} using invite-token auth (no JWT needed).
    Used by the React self-enrollment page.
    """
    import base64 as b64mod

    token = request.match_info.get("token", "")
    if not _enroll_token_valid(token):
        return web.json_response({"error": "Invalid or expired link"}, status=400)

    client_id = _enroll_token_client_id(token)

    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"[ENROLL-TOKEN] JSON decode error: {e}")
        return web.json_response({"error": "invalid JSON", "details": str(e)}, status=400)

    raw_name = (body.get("name") or "").strip()
    if not raw_name:
        return web.json_response({"error": "name required"}, status=400)
    name = normalize_name(raw_name)
    if not name:
        return web.json_response({"error": "invalid name"}, status=400)

    b64_frames = body.get("frames") or []
    if not b64_frames:
        return web.json_response({"error": "frames required"}, status=400)

    # Decode base64 frames
    frames = []
    for b64 in b64_frames:
        try:
            if isinstance(b64, str) and "," in b64:
                b64 = b64.split(",", 1)[1]
            raw_bytes = b64mod.b64decode(b64)
            arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frames.append(img)
        except Exception as e:
            print(f"[ENROLL-TOKEN] Frame decode error: {e}")
            continue

    if not frames:
        return web.json_response({"error": "no valid frames decoded"}, status=400)

    # Liveness check
    liveness_score = 1.0
    if LIVENESS_ENABLED:
        face_data_list = []
        for img in frames:
            try:
                if face_app:
                    detected = face_app.get(img)
                    if detected:
                        best = max(
                            detected,
                            key=lambda f: (
                                (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
                            ),
                        )
                        face_data_list.append(
                            {"bbox": best.bbox, "pose": getattr(best, "pose", None)}
                        )
                    else:
                        face_data_list.append(
                            {"bbox": [0, 0, img.shape[1], img.shape[0]]}
                        )
                else:
                    face_data_list.append({"bbox": [0, 0, img.shape[1], img.shape[0]]})
            except Exception:
                face_data_list.append({"bbox": [0, 0, img.shape[1], img.shape[0]]})

        if face_data_list:
            is_live, liveness_score, _ = check_frames_liveness(frames, face_data_list)
            print(f"[ENROLL-TOKEN] Liveness: {is_live} score={liveness_score:.3f}")
            if not is_live:
                return web.json_response(
                    {
                        "status": "failed",
                        "message": f"Liveness check failed (score={liveness_score:.2f}). Please use a live camera.",
                        "liveness_score": round(liveness_score, 3),
                    },
                    status=400,
                )

    success, message = enroll_face(name, frames, client_id=client_id)
    if success and faceid:
        faceid.load()
        send_enrollment_alert(f"[LINK] {name} enrolled via share link")

    # Consume the token on success
    if success:
        enroll_tokens.pop(token, None)

    return web.json_response(
        {
            "status": "ok" if success else "failed",
            "message": message,
            "liveness_score": round(liveness_score, 3),
            "frames_used": len(frames),
        }
    )


async def login_handler(request):
    if not login:
        return web.json_response({"error": "auth modules not available"}, status=503)
    return await login(request)


async def signup_handler(request):
    if not signup:
        return web.json_response({"error": "auth modules not available"}, status=503)
    return await signup(request)


async def enroll_upload(request):
    token = request.match_info.get("token", "")
    if not _enroll_token_valid(token):
        return web.Response(text="Invalid or expired link", status=400)

    client_id = _enroll_token_client_id(token)
    reader = await request.multipart()

    name = None
    frames = []
    face_data_list = []

    while True:
        part = await reader.next()
        if not part:
            break

        if part.name == "name":
            name = (await part.text()).strip()

        if part.name == "images":
            data = await part.read()
            if not data:
                continue

            tmp = RAW_DIR / f"_upload_{secrets.token_hex(4)}.jpg"
            with open(tmp, "wb") as f:
                f.write(data)

            img = cv2.imread(str(tmp))
            tmp.unlink(missing_ok=True)

            if img is None:
                continue

            # Detect face to get bbox for liveness check
            faces_detected = face_app.get(img) if face_app else []
            if faces_detected:
                face_data_list.append(
                    {
                        "bbox": faces_detected[0].bbox,
                        "pose": getattr(faces_detected[0], "pose", None),
                    }
                )
            else:
                face_data_list.append({"bbox": [0, 0, img.shape[1], img.shape[0]]})

            frames.append(img)

    if not name:
        return web.Response(text="Missing name", status=400)

    normalized = normalize_name(name)
    if not normalized:
        return web.Response(text="Invalid name", status=400)

    if not frames:
        return web.Response(text="No valid images uploaded", status=400)

    # Liveness check
    if LIVENESS_ENABLED and face_data_list:
        is_live, liveness_score, _ = check_frames_liveness(frames, face_data_list)
        print(f"[ENROLL-LINK] Liveness: {is_live} score={liveness_score:.3f}")
        if not is_live:
            return web.Response(
                text=f"Liveness check failed (score={liveness_score:.2f}). Please use a live camera, not a photo of a photo.",
                status=400,
            )

    success, msg = enroll_face(normalized, frames, client_id=client_id)

    if success and faceid:
        faceid.load()

    enroll_tokens.pop(token, None)

    return web.Response(text=f"{msg} ({len(frames)} images)")


def _create_face_app() -> FaceAnalysis:
    root = str(REPO_ROOT / "pre_trained" / "insightface")
    ort_has_cuda_ep = False
    try:
        import onnxruntime as ort

        ort_has_cuda_ep = "CUDAExecutionProvider" in (
            ort.get_available_providers() or []
        )
    except Exception:
        ort_has_cuda_ep = False

    prefer_cuda = (
        (not FORCE_INSIGHTFACE_CPU) and torch.cuda.is_available() and ort_has_cuda_ep
    )
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if prefer_cuda
        else ["CPUExecutionProvider"]
    )
    print(f"🔍 InsightFace providers: {providers}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    print(f"   ORT has CUDA: {ort_has_cuda_ep}")
    print(f"   FORCE_CPU: {FORCE_INSIGHTFACE_CPU}")
    try:
        return FaceAnalysis(name="buffalo_l", root=root, providers=providers)
    except Exception as e:
        print(
            f"⚠️ InsightFace init failed with providers={providers}; retrying on CPU: {e}"
        )
        return FaceAnalysis(
            name="buffalo_l", root=root, providers=["CPUExecutionProvider"]
        )


face_app = _create_face_app()
# Defer prepare until we know whether CUDA is available so we can select GPU when possible.
face_app_prepared = False


def enroll_face(name: str, frames: list, client_id=None):
    """Enroll a face into the per-client database.

    Args:
        name: normalized person name
        frames: list of BGR numpy arrays (already quality-filtered)
        client_id: the admin's client_id from JWT — scopes the database
    """
    db_path = _face_db_path(client_id)
    # Save directly under name in RAW_DIR (no client_id subfolder per user request)
    person_dir = RAW_DIR / name
    person_dir.mkdir(parents=True, exist_ok=True)

    embeddings = []
    import time

    ts = int(time.time())

    for i, frame in enumerate(frames):
        send_alert("SYSTEM", f"Processing frame {i + 1}/{len(frames)} for {name}")

        faces = face_app.get(frame)
        if not faces:
            continue
        # Pick the largest face
        face = max(
            faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
        )
        emb = face.embedding
        # L2 normalize
        emb = emb / (np.linalg.norm(emb) + 1e-8)
        embeddings.append(emb)

        # Use unique filename with timestamp to avoid overwriting existing data
        filename = f"frame_{ts}_{i}.jpg"
        cv2.imwrite(str(person_dir / filename), frame)

    if not embeddings:
        msg = f"No faces detected for {name} — enrollment failed"
        send_alert("SYSTEM", msg)
        return False, msg

    embeddings_arr = np.array(embeddings)

    # Compute the mean embedding (most robust representation)
    mean_emb = embeddings_arr.mean(axis=0)
    mean_emb = mean_emb / (np.linalg.norm(mean_emb) + 1e-8)

    # load or create client DB
    with face_db_lock:
        if db_path.exists():
            data = np.load(db_path, allow_pickle=True)
            all_emb = list(data["embeddings"])
            all_lbl = list(data["labels"])
        else:
            all_emb, all_lbl = [], []

        # Add mean embedding as a single authoritative vector + individual frames
        all_emb.append(mean_emb)
        all_lbl.append(name)
        for e in embeddings_arr:
            all_emb.append(e)
            all_lbl.append(name)

        np.savez(db_path, embeddings=np.array(all_emb), labels=np.array(all_lbl))

    msg = f"Face enrolled for {name} ({len(embeddings)} frames, client={client_id})"
    send_alert("SYSTEM", msg)
    return True, msg


# --- PID bbox smoothing ---
pid_smooth = {}  # pid -> (x1,y1,x2,y2)
pid_smooth_lock = threading.Lock()

from bbox_smoother import BBoxSmoother
from recording import SegmentWriter, update_camera_health, get_camera_health_snapshot

# Bounding Box Smoothing Configurations
BBOX_SMOOTHING_MODE = os.getenv("BBOX_SMOOTHING_MODE", "fixed").strip().lower()
BBOX_FIXED_ALPHA = float(os.getenv("BBOX_FIXED_ALPHA", os.getenv("BBOX_SMOOTH_ALPHA", "0.75")))
BBOX_ALPHA_HIGH = float(os.getenv("BBOX_ALPHA_HIGH", "0.30"))
BBOX_ALPHA_MEDIUM = float(os.getenv("BBOX_ALPHA_MEDIUM", "0.55"))
BBOX_ALPHA_LOW = float(os.getenv("BBOX_ALPHA_LOW", "0.80"))
BBOX_CONF_HIGH = float(os.getenv("BBOX_CONF_HIGH", "0.85"))
BBOX_CONF_MEDIUM = float(os.getenv("BBOX_CONF_MEDIUM", "0.60"))

bbox_smoother = BBoxSmoother(
    mode=BBOX_SMOOTHING_MODE,
    fixed_alpha=BBOX_FIXED_ALPHA,
    alpha_high=BBOX_ALPHA_HIGH,
    alpha_medium=BBOX_ALPHA_MEDIUM,
    alpha_low=BBOX_ALPHA_LOW,
    conf_high=BBOX_CONF_HIGH,
    conf_medium=BBOX_CONF_MEDIUM
)


def smooth_bbox(pid, box, confidence=1.0):
    """EMA bbox smoothing delegation to BBoxSmoother."""
    with pid_smooth_lock:
        if pid not in pid_smooth:
            pid_smooth[pid] = box
            return box

        pid_smooth[pid] = bbox_smoother.smooth(pid_smooth[pid], box, confidence)
        return pid_smooth[pid]



def force_h264(pc):
    """Prefer H264 codecs for video transceivers (helps Safari/iOS)."""
    try:
        caps = RTCRtpSender.getCapabilities("video")
        if not caps or not hasattr(caps, "codecs"):
            return
        h264 = [
            c for c in caps.codecs if getattr(c, "mimeType", "").lower() == "video/h264"
        ]
        if not h264:
            return
        for transceiver in pc.getTransceivers():
            if getattr(transceiver, "kind", None) == "video":
                try:
                    transceiver.setCodecPreferences(h264)
                except Exception as e:
                    logger.debug(f"setCodecPreferences failed: {e}")
    except Exception as e:
        logger.debug(f"force_h264 error: {e}")


# Target WebRTC video bitrate in kbps.  6 Mbps gives crisp 1280×720 @ 30fps.
# Raise WEBRTC_VIDEO_KBPS env var if your LAN can handle more (e.g. 10000 for
# near-lossless), lower it if clients are on Wi-Fi / mobile.
WEBRTC_VIDEO_KBPS = _int_env("WEBRTC_VIDEO_KBPS", 6000)


def _munge_sdp_bitrate(sdp: str, video_kbps: int) -> str:
    """Inject bandwidth hints into the video section of an SDP string.

    Inserts:
      b=AS:<kbps>           — application-specific max kbps (RFC 4566)
      b=TIAS:<bps>          — transport-independent application-specific (RFC 3890)

    aiortc's VP8/H264 encoder reads the b=AS line from the local description
    and raises its target bitrate accordingly, which is the primary lever for
    improving outgoing video quality.
    """
    eol = "\r\n" if "\r\n" in sdp else "\n"
    lines = sdp.replace("\r\n", "\n").splitlines()
    out: list[str] = []
    in_video = False
    bw_inserted = False
    for line in lines:
        if line.startswith("m=video"):
            in_video = True
            bw_inserted = False
            out.append(line)
            continue
        if line.startswith("m=") and not line.startswith("m=video"):
            in_video = False
        # Insert bandwidth lines immediately after the connection line (c=)
        # inside the video section.  If there is no c= line, insert after m=.
        if in_video and not bw_inserted:
            if line.startswith("c=") or line.startswith("a="):
                # Remove any existing bandwidth lines for this section first.
                if not line.startswith("b="):
                    out.append(f"b=AS:{video_kbps}")
                    out.append(f"b=TIAS:{video_kbps * 1000}")
                    bw_inserted = True
        if line.startswith("b=") and in_video and not bw_inserted:
            # Skip old bandwidth lines — we'll replace them.
            continue
        out.append(line)
    return eol.join(out)


roi_state = {}  # Remove roi_polygons entirely
roi_state_lock = threading.Lock()
roi_updated_at = 0.0
# Global flag set per-offer to indicate client is iOS/Safari
latest_client_is_ios = False
# Global process lock (created at startup) to ensure only one client is processed at a time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc-yolo")
pcs = set()
print("🚀 Server starting with iOS compatibility mode")


def normalize_name(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    return name[0].upper() + name[1:].lower()


# --------------------------------------------------
# SAFE CUDA INIT (OPTION-A READY)
# --------------------------------------------------


def safe_cuda_available():
    try:
        return torch.cuda.is_available()
    except Exception as e:
        print(f"⚠️ CUDA check failed, using CPU: {e}")
        return False


use_cuda = safe_cuda_available()
device = torch.device("cuda:0" if use_cuda else "cpu")
print(f"🔍 Using device: {device}")
print("CUDA available:", torch.cuda.is_available())

# --------------------------------------------------
# MODEL LOADING — controlled by MODEL_SELECT
# --------------------------------------------------
# Globals for specialized models (None = not loaded)
face_det_model = None   # YOLO face detector (yolov8n-face.pt)
fire_model = None        # Fire/smoke detector (fire_smoke.pt)
lpd_model = None         # License plate detector (model.pt)
yolo_model = None        # General YOLO object detector
CURRENT_YOLO_RUNTIME = "pytorch"



def _load_yolo_model(path, label="YOLO"):
    """Load a YOLO model, apply GPU optimizations, and return it."""
    if not os.path.isabs(path):
        path = str(REPO_ROOT / path)
    if not os.path.exists(path):
        print(f"⚠️ {label} weights not found at {path}, skipping")
        return None
    print(f"🔁 Loading {label} weights from: {path}")
    is_engine = path.endswith(".engine")
    model = YOLO(path)
    if is_engine:
        print(f"⚡ {label} loaded as TensorRT engine")
        return model
    model.to(device)
    if use_cuda and YOLO_ENABLE_FUSE:
        try:
            model.fuse()
            print(f"⚡ {label} model fused")
        except Exception as e:
            print(f"⚠️ {label} fuse skipped: {e}")
    if use_cuda and YOLO_ENABLE_FP16:
        try:
            model.model.half()
            print(f"⚡ {label} set to FP16")
        except Exception as e:
            print(f"⚠️ {label} FP16 skipped: {e}")
    print(f"✅ {label} loaded on {model.device}")
    return model



_PRODUCTION_CONFIGS = {
    6: {
        "mode": "Production",
        "variant": "YOLO11m",
        "weights": "models/yolo/secure_cv_best.pt",
        "specialized": "Disabled",
        "face_rec": "Enabled",
        "open_world": "Disabled"
    },
    7: {
        "mode": "Full Package",
        "variant": "YOLO11m",
        "weights": "models/yolo/secure_cv_best.pt",
        "specialized": "Enabled",
        "face_rec": "Enabled",
        "open_world": "Disabled"
    },
    9: {
        "mode": "Production",
        "variant": "YOLO11l",
        "weights": "models/yolo/secure_cv_best_l.pt",
        "specialized": "Disabled",
        "face_rec": "Enabled",
        "open_world": "Disabled"
    },
    10: {
        "mode": "Production",
        "variant": "YOLO11x",
        "weights": "models/yolo/secure_cv_best_x.pt",
        "specialized": "Disabled",
        "face_rec": "Enabled",
        "open_world": "Disabled"
    },
    11: {
        "mode": "Full Package",
        "variant": "YOLO11l",
        "weights": "models/yolo/secure_cv_best_l.pt",
        "specialized": "Enabled",
        "face_rec": "Enabled",
        "open_world": "Disabled"
    },
    12: {
        "mode": "Full Package",
        "variant": "YOLO11x",
        "weights": "models/yolo/secure_cv_best_x.pt",
        "specialized": "Enabled",
        "face_rec": "Enabled",
        "open_world": "Disabled"
    }
}


# --- Determine which YOLO weights to use for the general model ---
_yolo_general_needed = MODEL_SELECT in (1, 5, 6, 7, 8, 9, 10, 11, 12)
ACTIVE_YOLO_WEIGHTS_PATH = None
if _yolo_general_needed:
    if MODEL_SELECT == 8:
        weights_path = str(REPO_ROOT / "models" / "yolo" / "yolov8s-worldv2.pt")
    elif MODEL_SELECT in _PRODUCTION_CONFIGS:
        config = _PRODUCTION_CONFIGS[MODEL_SELECT]
        prod_weights = config["weights"]

        # Resolve path
        if not os.path.isabs(prod_weights):
            resolved_weights_path = REPO_ROOT / prod_weights
        else:
            resolved_weights_path = Path(prod_weights)

        # Fail fast if it does not exist
        if not resolved_weights_path.exists():
            print("ERROR: Production model not found\n")
            print(prod_weights)
            print("\nPlease update MODEL_SELECT or restore the model file.")
            sys.exit(1)

        # Print startup banner
        device_str = "CUDA" if use_cuda else "CPU"
        fp16_str = "Enabled" if YOLO_ENABLE_FP16 else "Disabled"

        print("==========================================")
        print("SecureVU Detection Configuration")
        print("==========================================")
        print(f"MODEL_SELECT      : {MODEL_SELECT}")
        print(f"Mode              : {config['mode']}")
        print(f"Variant           : {config['variant']}")
        print(f"Weights           : {config['weights']}")
        print(f"Specialized       : {config['specialized']}")
        print(f"Face Recognition  : {config['face_rec']}")
        print(f"Open World        : {config['open_world']}")
        print(f"Device            : {device_str}")
        print(f"FP16              : {fp16_str}")
        print("==========================================")

        weights_path = str(resolved_weights_path)
    else:
        weights_path = os.environ.get(
            "YOLO_WEIGHTS", str(REPO_ROOT / "models" / "yolo" / "secure_cv_best.pt")
        )
    ACTIVE_YOLO_WEIGHTS_PATH = weights_path

    # TensorRT vs PyTorch runtime selection and automatic fallback
    base_weights_path = weights_path
    model_runtime = os.environ.get("MODEL_RUNTIME", "pytorch").lower()
    yolo_model = None

    if model_runtime == "tensorrt":
        engine_path = Path(base_weights_path).with_suffix(".engine")
        if engine_path.exists():
            print(f"⚡ TensorRT mode selected. Trying engine: {engine_path}")
            try:
                weights_path = str(engine_path)
                yolo_model = _load_yolo_model(weights_path, "YOLO-General")
                if yolo_model is not None:
                    CURRENT_YOLO_RUNTIME = "tensorrt"
            except Exception as e:
                print(f"⚠️ WARNING: Failed to load TensorRT engine {engine_path.name}: {e}")
                print("Falling back to PyTorch (.pt)...")
                yolo_model = None
        else:
            print(f"⚠️ WARNING: TensorRT mode selected, but engine {engine_path.name} not found. Falling back to PyTorch.")

    if yolo_model is None:
        weights_path = base_weights_path
        yolo_model = _load_yolo_model(weights_path, "YOLO-General")
        CURRENT_YOLO_RUNTIME = "pytorch"

    # Print SecureVU Runtime banner
    device_str = "CUDA" if use_cuda else "CPU"
    banner_runtime = "TensorRT" if CURRENT_YOLO_RUNTIME == "tensorrt" else "PyTorch"
    banner_precision = "FP16" if (CURRENT_YOLO_RUNTIME == "tensorrt" or YOLO_ENABLE_FP16) else "FP32"
    banner_model_name = Path(weights_path).stem
    banner_engine = os.path.basename(weights_path) if CURRENT_YOLO_RUNTIME == "tensorrt" else "N/A"

    print("==========================================")
    print("SecureVU Runtime")
    print("==========================================")
    print(f"Model           : {banner_model_name}")
    print(f"Runtime         : {banner_runtime}")
    print(f"Precision       : {banner_precision}")
    print(f"Device          : {device_str}")
    if banner_runtime == "TensorRT":
        print(f"Engine          : {banner_engine}")
    print("==========================================")
else:
    print(f"ℹ️ General YOLO model not loaded (MODEL_SELECT={MODEL_SELECT})")

# --- Face Detection (yolov8n-face) ---
if MODEL_SELECT in (2, 5, 7, 11, 12):
    face_det_model = _load_yolo_model(
        str(REPO_ROOT / "models" / "face" / "yolov8n-face.pt"), "YOLO-Face"
    )

# --- Fire & Smoke ---
if MODEL_SELECT in (3, 5, 7, 11, 12):
    fire_model = _load_yolo_model(
        str(REPO_ROOT / "models" / "fire" / "fire_smoke.pt"), "Fire-Smoke"
    )

# --- License Plate Detection (LPD) ---
if MODEL_SELECT in (4, 5, 7, 11, 12):
    lpd_model = _load_yolo_model(
        str(REPO_ROOT / "models" / "lpd" / "model.pt"), "LPD"
    )

# --- Production/Full mode (6, 7, 9, 10, 11, 12): InsightFace face recognition ---
if MODEL_SELECT in (6, 7, 9, 10, 11, 12):
    FACE_ENABLE = True
    print(f"✅ Full/Production mode: InsightFace recognition enabled (MODEL_SELECT={MODEL_SELECT})")

# Print summary of loaded models
_loaded = []
if yolo_model is not None:
    _loaded.append("YOLO-General")
if face_det_model is not None:
    _loaded.append("YOLO-Face")
if fire_model is not None:
    _loaded.append("Fire-Smoke")
if lpd_model is not None:
    _loaded.append("LPD")
print(f"📦 Loaded models: {', '.join(_loaded) if _loaded else 'NONE'}")

try:
    from app import ml_tracking

    ml_tracking.set_runtime_context(
        yolo_weights_path=ACTIVE_YOLO_WEIGHTS_PATH,
        yolo_runtime=CURRENT_YOLO_RUNTIME,
        model_select=MODEL_SELECT,
    )
except Exception:
    ml_tracking = None  # type: ignore

# Test primary YOLO inference
_primary_model = yolo_model or face_det_model or fire_model or lpd_model
if _primary_model is not None:
    try:
        test_input = torch.zeros(1, 3, 640, 640, device=device)
        amp_enabled = bool(use_cuda and YOLO_ENABLE_FP16)
        with torch.inference_mode():
            with torch.cuda.amp.autocast(enabled=amp_enabled):
                _ = _primary_model(test_input, verbose=False)
        print(f"✅ Primary model inference OK on {device}")
    except Exception as e:
        print(f"⚠️ Primary model GPU test failed, continuing on CPU: {e}")
        try:
            _primary_model.to("cpu")
        except Exception:
            pass
        device = torch.device("cpu")

# If CUDA is available, enable GPU-friendly settings
if use_cuda:
    try:
        torch.backends.cudnn.benchmark = True
        print("⚡ cuDNN benchmark enabled for faster convolutions")
    except Exception as e:
        print(f"⚠️ Could not enable cuDNN benchmark: {e}")

    try:
        torch.backends.cudnn.enabled = True
    except Exception as e:
        print(f"⚠️ Could not enable cuDNN runtime: {e}")

    # Warm up whichever model is primary
    if _primary_model is not None:
        try:
            with torch.no_grad():
                dummy = torch.zeros(1, 3, 640, 640, device=device)
                for _ in range(10):
                    _ = _primary_model(dummy, verbose=False)
            print("✅ GPU warmed up")
        except Exception as e:
            print(f"⚠️ GPU warm-up failed: {e}")

    # Optional: torch.compile for ~20-40% extra GPU throughput (PyTorch ≥ 2.0).
    if hasattr(torch, "compile") and yolo_model is not None:
        try:
            yolo_model.model = torch.compile(
                yolo_model.model, mode="reduce-overhead", fullgraph=False
            )
            print("⚡ YOLO model compiled with torch.compile (reduce-overhead)")
        except Exception as _ce:
            print(f"⚠️ torch.compile skipped: {_ce}")

# Prepare InsightFace now that we know whether CUDA is available
insightface_ctx_id = -1
try:
    ort_has_cuda_ep = False
    available_providers = []
    try:
        import onnxruntime as ort

        available_providers = ort.get_available_providers() or []
    except Exception:
        available_providers = []
    ort_has_cuda_ep = "CUDAExecutionProvider" in available_providers

    insightface_ctx_id = (
        0 if (use_cuda and (not FORCE_INSIGHTFACE_CPU) and ort_has_cuda_ep) else -1
    )
    print(f"🔍 Preparing InsightFace with ctx_id={insightface_ctx_id}")
    print("   (0=GPU, -1=CPU)")
    print(f"   InsightFace ctx_id: {insightface_ctx_id}")
    print(f"   ONNX providers: {available_providers}")
    face_app.prepare(ctx_id=insightface_ctx_id)
    face_app_prepared = True
    print(
        f"✅ InsightFace prepared on {'GPU' if insightface_ctx_id == 0 else 'CPU'} (ctx_id={insightface_ctx_id})"
    )
except Exception as e:
    print(f"⚠️ InsightFace prepare failed: {e}")
    # Try fallback to CPU
    if use_cuda:
        try:
            face_app.prepare(ctx_id=-1)
            face_app_prepared = True
            insightface_ctx_id = -1
            print("✅ InsightFace prepared on CPU (fallback)")
        except Exception as e2:
            print(f"❌ InsightFace prepare on CPU failed: {e2}")

print("InsightFace ctx_id:", insightface_ctx_id)

# --------------------------------------------------
# FACEID — SAFE INIT (AUTO GPU WHEN ENV FIXED)
# --------------------------------------------------
print("\n" + "=" * 60)
print("FaceID SAFE MODE (auto GPU when available)")
print("=" * 60)

FACE_DB_FILE = REPO_ROOT / "models" / "arcface" / "face_db" / "face_db.npz"

faceid_ctx = 0 if use_cuda else -1

faceid = None
try:
    # FACE_RECOGNITION_THRESHOLD: lower = more sensitive, higher = more strict
    # Default 0.25 gives good balance for database with good embeddings
    face_threshold = float(os.getenv("FACE_RECOGNITION_THRESHOLD", "0.25"))
    faceid = FaceIDManager(
        db_path=FACE_DB_FILE,  # ✅ FILE PATH
        threshold=face_threshold,
        ctx_id=faceid_ctx,
    )
    logger.info(
        "✅ FaceID loaded from %s with threshold %.3f", FACE_DB_FILE, face_threshold
    )
except Exception as e:
    logger.error("❌ FaceID disabled: %s", e)
    faceid = None


def _reload_face_db_and_track(source: str = "face_db") -> None:
    if not faceid:
        return
    faceid.load()
    try:
        from app import ml_tracking

        ml_tracking.schedule_tracking(
            ml_tracking.log_config_change,
            source=source,
            changed_keys=["face_db.npz"],
            artifact_paths=[FACE_DB_FILE],
        )
    except Exception:
        pass


# --------------------------------------------------
# ROI SETUP
# --------------------------------------------------
# WEB ROI (preferred method)
web_roi_file = REPO_ROOT / "models" / "roi" / "web_roi.json"
web_roi = None

if web_roi_file.exists():
    try:
        with open(web_roi_file, "r") as f:
            web_roi = json.load(f)
        if isinstance(web_roi, dict) and "enabled" not in web_roi:
            web_roi["enabled"] = False
            try:
                with open(web_roi_file, "w") as f:
                    json.dump(web_roi, f, indent=2)
            except Exception:
                pass
        logger.info(f"Loaded WEB ROI: {web_roi}")
    except Exception as e:
        logger.warning(f"WEB ROI load error: {e}")
else:
    logger.warning("web_roi.json file does not exist")
    # Create default if file doesn't exist
    web_roi = {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4, "enabled": False}
    try:
        with open(web_roi_file, "w") as f:
            json.dump(web_roi, f, indent=2)
        logger.info(f"Created default WEB ROI: {web_roi}")
    except Exception as e:
        logger.error(f"Failed to create default ROI: {e}")

# --------------------------------------------------
# CAMERA RULES (PER CAMERA, NO TRAINING)
# --------------------------------------------------
RULES_FILE = REPO_ROOT / "config" / "camera_rules.json"
RULES_LOCK = threading.Lock()
camera_states = {}
camera_states_lock = threading.Lock()

RULES_SCHEMA = {
    "version": 1,
    "camera_rule": {
        "active": True,
        "active_hours": [
            {"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "23:59"}
        ],
        "max_people": {"enabled": False, "value": 5},
        "roi_intrusion": {
            "enabled": False,
            "zones": [
                {
                    "id": "roi1",
                    "points": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]],
                    "classes": ["person"],
                }
            ],
        },
        "virtual_lines": {
            "enabled": False,
            "lines": [
                {
                    "id": "line1",
                    "p1": [0.1, 0.5],
                    "p2": [0.9, 0.5],
                    "direction": "both",
                    "classes": ["person", "car", "truck", "bus", "motorcycle"],
                }
            ],
        },
        "unknown_person": {"enabled": False},
        "vehicle_rules": {
            "enabled": False,
            "entry_line_id": "entry",
            "exit_line_id": "exit",
            "classes": ["car", "truck", "bus", "motorcycle"],
        },
        "parking_rules": {
            "enabled": False,
            "zones": [
                {
                    "id": "park1",
                    "points": [[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]],
                    "max_seconds": 600,
                    "classes": ["car", "truck", "bus", "motorcycle"],
                }
            ],
        },
    },
}


def _camera_key(camera_id) -> str:
    if camera_id is None:
        return "device"
    if isinstance(camera_id, str):
        s = camera_id.strip().lower()
        if s in ("device", "usb", "local"):
            return "device"
    try:
        return str(int(camera_id))
    except Exception:
        return "device"


def _parse_camera_id_value(val):
    if val is None:
        return None
    if isinstance(val, str):
        s = val.strip().lower()
        if s in ("device", "usb", "local"):
            return None
    try:
        return int(val)
    except Exception:
        return None


def _default_camera_rules() -> dict:
    return deepcopy(RULES_SCHEMA["camera_rule"])


def _load_rules_file() -> dict:
    if RULES_FILE.exists():
        try:
            data = json.loads(RULES_FILE.read_text())
            if not isinstance(data, dict):
                return {"version": 1, "cameras": {}}
            data.setdefault("version", 1)
            data.setdefault("cameras", {})
            if not isinstance(data.get("cameras"), dict):
                data["cameras"] = {}
            return data
        except Exception:
            pass
    return {"version": 1, "cameras": {}}


def _save_rules_file(data: dict, camera_id=None) -> None:
    try:
        RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        RULES_FILE.write_text(json.dumps(data, indent=2))
        try:
            from app import ml_tracking

            extra = {}
            if camera_id is not None:
                extra["camera_id"] = _camera_key(camera_id)
            ml_tracking.schedule_tracking(
                ml_tracking.log_config_change,
                source="camera_rules",
                changed_keys=["camera_rules.json"],
                extra_params=extra,
                artifact_paths=[RULES_FILE],
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Failed to save camera rules: {e}")


def _clamp01(val: float) -> float:
    try:
        return max(0.0, min(1.0, float(val)))
    except Exception:
        return 0.0


def _normalize_points(points) -> list:
    out = []
    for pt in points or []:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        out.append([_clamp01(pt[0]), _clamp01(pt[1])])
    return out


def _normalize_camera_rules(rules: dict | None) -> dict:
    base = _default_camera_rules()
    if not isinstance(rules, dict):
        return base

    base["active"] = bool(rules.get("active", base["active"]))

    hours = []
    for win in rules.get("active_hours", base.get("active_hours", [])) or []:
        if not isinstance(win, dict):
            continue
        days = [
            int(d)
            for d in (win.get("days") or [])
            if str(d).isdigit() and 0 <= int(d) <= 6
        ]
        start = str(win.get("start", "00:00"))
        end = str(win.get("end", "23:59"))
        hours.append({"days": days, "start": start, "end": end})
    base["active_hours"] = hours

    max_people = rules.get("max_people", {})
    base["max_people"]["enabled"] = bool(
        max_people.get("enabled", base["max_people"]["enabled"])
    )
    try:
        base["max_people"]["value"] = max(
            0, int(max_people.get("value", base["max_people"]["value"]))
        )
    except Exception:
        base["max_people"]["value"] = base["max_people"]["value"]

    roi = rules.get("roi_intrusion", {})
    base["roi_intrusion"]["enabled"] = bool(
        roi.get("enabled", base["roi_intrusion"]["enabled"])
    )
    zones = []
    for zone in roi.get("zones", []) or []:
        if not isinstance(zone, dict):
            continue
        zone_id = str(zone.get("id") or f"roi{len(zones) + 1}")
        points = _normalize_points(zone.get("points", []))
        classes = zone.get("classes") or ["person"]
        zones.append({"id": zone_id, "points": points, "classes": classes})
    base["roi_intrusion"]["zones"] = zones

    vlines = rules.get("virtual_lines", {})
    base["virtual_lines"]["enabled"] = bool(
        vlines.get("enabled", base["virtual_lines"]["enabled"])
    )
    lines = []
    for line in vlines.get("lines", []) or []:
        if not isinstance(line, dict):
            continue
        line_id = str(line.get("id") or f"line{len(lines) + 1}")
        p1 = _normalize_points([line.get("p1", [0.1, 0.5])])
        p2 = _normalize_points([line.get("p2", [0.9, 0.5])])
        p1 = p1[0] if p1 else [0.1, 0.5]
        p2 = p2[0] if p2 else [0.9, 0.5]
        direction = str(line.get("direction", "both"))
        classes = line.get("classes") or ["person"]
        lines.append(
            {
                "id": line_id,
                "p1": p1,
                "p2": p2,
                "direction": direction,
                "classes": classes,
            }
        )
    base["virtual_lines"]["lines"] = lines

    unk = rules.get("unknown_person", {})
    base["unknown_person"]["enabled"] = bool(
        unk.get("enabled", base["unknown_person"]["enabled"])
    )

    vehicle = rules.get("vehicle_rules", {})
    base["vehicle_rules"]["enabled"] = bool(
        vehicle.get("enabled", base["vehicle_rules"]["enabled"])
    )
    base["vehicle_rules"]["entry_line_id"] = str(
        vehicle.get("entry_line_id", base["vehicle_rules"]["entry_line_id"])
    )
    base["vehicle_rules"]["exit_line_id"] = str(
        vehicle.get("exit_line_id", base["vehicle_rules"]["exit_line_id"])
    )
    base["vehicle_rules"]["classes"] = (
        vehicle.get("classes") or base["vehicle_rules"]["classes"]
    )

    parking = rules.get("parking_rules", {})
    base["parking_rules"]["enabled"] = bool(
        parking.get("enabled", base["parking_rules"]["enabled"])
    )
    pzones = []
    for zone in parking.get("zones", []) or []:
        if not isinstance(zone, dict):
            continue
        zone_id = str(zone.get("id") or f"park{len(pzones) + 1}")
        points = _normalize_points(zone.get("points", []))
        classes = zone.get("classes") or base["parking_rules"]["zones"][0]["classes"]
        try:
            max_seconds = max(1, int(zone.get("max_seconds", 600)))
        except Exception:
            max_seconds = 600
        pzones.append(
            {
                "id": zone_id,
                "points": points,
                "classes": classes,
                "max_seconds": max_seconds,
            }
        )
    base["parking_rules"]["zones"] = pzones

    return base


def _get_camera_rules(camera_id) -> dict:
    cam_key = _camera_key(camera_id)
    with RULES_LOCK:
        data = _load_rules_file()
        cam_rules = data.get("cameras", {}).get(cam_key)
    return _normalize_camera_rules(cam_rules)


def _set_camera_rules(camera_id, rules: dict) -> dict:
    cam_key = _camera_key(camera_id)
    normalized = _normalize_camera_rules(rules)
    with RULES_LOCK:
        data = _load_rules_file()
        data.setdefault("cameras", {})
        data["cameras"][cam_key] = normalized
        _save_rules_file(data, camera_id=camera_id)
    return normalized


def _get_camera_state(camera_id):
    cam_key = _camera_key(camera_id)
    with camera_states_lock:
        state = camera_states.get(cam_key)
        if state is None:
            state = {
                "roi_inside": {},
                "line_side": {},
                "parking": {},
                "linger": {},
                "alert_last": {},
                "lock": threading.Lock(),
            }
            camera_states[cam_key] = state
        return state


def _parse_hhmm(val: str) -> int | None:
    try:
        parts = val.split(":")
        if len(parts) != 2:
            return None
        h = int(parts[0])
        m = int(parts[1])
        if h < 0 or h > 23 or m < 0 or m > 59:
            return None
        return h * 60 + m
    except Exception:
        return None


def _is_active_now(active_hours) -> bool:
    if not active_hours:
        return True
    now = datetime.now()
    now_day = now.weekday()
    now_minutes = now.hour * 60 + now.minute
    for win in active_hours:
        days = win.get("days") or []
        if days and now_day not in days:
            continue
        start = _parse_hhmm(str(win.get("start", "00:00")))
        end = _parse_hhmm(str(win.get("end", "23:59")))
        if start is None or end is None:
            continue
        if start <= end:
            if start <= now_minutes <= end:
                return True
        else:
            # Overnight window
            if now_minutes >= start or now_minutes <= end:
                return True
    return False


def _point_in_poly(px: float, py: float, poly) -> bool:
    if not poly or len(poly) < 3:
        return False
    inside = False
    j = len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        intersect = ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _line_side(p1, p2, p) -> float:
    return (p2[0] - p1[0]) * (p[1] - p1[1]) - (p2[1] - p1[1]) * (p[0] - p1[0])


def _classify_label(label: str, cls_id: int | None) -> dict:
    lbl = (label or "").lower()
    is_person = "person" in lbl
    if PERSON_CLASS_IDS and cls_id is not None and cls_id in PERSON_CLASS_IDS:
        is_person = True
    vehicle_labels = {
        "car",
        "truck",
        "bus",
        "motorcycle",
        "motorbike",
        "bicycle",
        "van",
    }
    is_vehicle = lbl in vehicle_labels
    animal_labels = {"dog", "cat", "horse", "cow", "sheep", "bird"}
    is_animal = lbl in animal_labels
    plate_labels = {"license plate", "plate", "number plate"}
    is_plate = lbl in plate_labels
    fire_labels = {"fire", "smoke", "flame", "fire_smoke"}
    is_fire = lbl in fire_labels
    face_labels = {"face"}
    is_face = lbl in face_labels or "face" in lbl
    return {
        "is_person": is_person,
        "is_vehicle": is_vehicle,
        "is_animal": is_animal,
        "is_plate": is_plate,
        "is_fire": is_fire,
        "is_face": is_face,
    }


def _class_matches(det, classes) -> bool:
    if not classes:
        return True
    label = (det.get("label") or "").lower()
    for cls in classes:
        key = str(cls).lower().strip()
        if not key:
            continue
        if key == "person" and det.get("is_person"):
            return True
        if key == "vehicle" and det.get("is_vehicle"):
            return True
        if key == "animal" and det.get("is_animal"):
            return True
        if key in ("plate", "license_plate", "license plate") and det.get("is_plate"):
            return True
        if key in ("fire", "smoke") and det.get("is_fire"):
            return True
        if key == "face" and det.get("is_face"):
            return True
        if key == label or key in label:
            return True
    return False


def _state_throttle(state: dict, key: str, min_gap: float) -> bool:
    now = time.time()
    last = state.get("alert_last", {}).get(key, 0)
    if now - last >= min_gap:
        state.setdefault("alert_last", {})[key] = now
        return True
    return False


def evaluate_camera_rules(camera_id, frame_shape, det_items: list, ts: float) -> None:
    rules = _get_camera_rules(camera_id)
    if not rules or not rules.get("active", True):
        return
    if not _is_active_now(rules.get("active_hours")):
        return

    cam_key = _camera_key(camera_id)
    state = _get_camera_state(camera_id)

    with state["lock"]:
        # Max people
        max_people = rules.get("max_people", {})
        if max_people.get("enabled"):
            try:
                limit = int(max_people.get("value", 0))
            except Exception:
                limit = 0
            count = sum(1 for d in det_items if d.get("is_person"))
            if count > limit and _state_throttle(state, "max_people", 4.0):
                send_alert(
                    "SYSTEM", f"P2 | CAM{cam_key} | MAX_PEOPLE | {count}>{limit}"
                )

        # Unknown person alert
        if rules.get("unknown_person", {}).get("enabled"):
            for det in det_items:
                if det.get("is_person") and det.get("name") == "Unknown":
                    token = _unknown_once_key(det, cam_key)
                    if _should_emit_unknown_once(token, ts):
                        send_alert(
                            _alert_subject(det),
                            f"P2 | CAM{cam_key} | UNKNOWN_PERSON_FIRST_SEEN",
                        )

        # ROI intrusion
        roi = rules.get("roi_intrusion", {})
        if roi.get("enabled"):
            for zone in roi.get("zones", []) or []:
                zone_id = zone.get("id") or "roi"
                points = zone.get("points", [])
                if not points:
                    continue
                pid_map = state["roi_inside"].setdefault(zone_id, {})
                for det in det_items:
                    if not _class_matches(det, zone.get("classes")):
                        continue
                    cx, cy = det.get("center", (0, 0))
                    inside = _point_in_poly(
                        cx / frame_shape[1], cy / frame_shape[0], points
                    )
                    entity = det.get("work_key") or f"pid:{det.get('pid')}"
                    was_inside = pid_map.get(entity, False)
                    if inside and not was_inside:
                        if _state_throttle(
                            state,
                            f"zone:{zone_id}:{entity}:enter",
                            ALERT_LINE_ZONE_MIN_GAP,
                        ):
                            ev = f"P1 | CAM{cam_key} | ZONE {zone_id} | ENTER"
                            send_alert(_alert_subject(det), ev)
                            _queue_event_clip(
                                camera_id,
                                ev,
                                _alert_subject(det),
                                ts,
                                {"zone_id": zone_id, "transition": "enter"},
                            )
                        _set_cross_overlay(
                            camera_id, entity, f"ZONE {zone_id} ENTER", ts
                        )
                    elif (not inside) and was_inside:
                        if _state_throttle(
                            state,
                            f"zone:{zone_id}:{entity}:exit",
                            ALERT_LINE_ZONE_MIN_GAP,
                        ):
                            ev = f"P1 | CAM{cam_key} | ZONE {zone_id} | EXIT"
                            send_alert(_alert_subject(det), ev)
                            _queue_event_clip(
                                camera_id,
                                ev,
                                _alert_subject(det),
                                ts,
                                {"zone_id": zone_id, "transition": "exit"},
                            )
                        _set_cross_overlay(
                            camera_id, entity, f"ZONE {zone_id} EXIT", ts
                        )
                    pid_map[entity] = inside

        # Virtual lines + vehicle entry/exit
        vlines = rules.get("virtual_lines", {})
        vehicle_rules = rules.get("vehicle_rules", {})
        entry_line_id = (
            vehicle_rules.get("entry_line_id") if vehicle_rules.get("enabled") else None
        )
        exit_line_id = (
            vehicle_rules.get("exit_line_id") if vehicle_rules.get("enabled") else None
        )
        vehicle_classes = vehicle_rules.get("classes") or [
            "car",
            "truck",
            "bus",
            "motorcycle",
        ]

        if vlines.get("enabled"):
            for line in vlines.get("lines", []) or []:
                line_id = line.get("id") or "line"
                p1 = line.get("p1", [0.1, 0.5])
                p2 = line.get("p2", [0.9, 0.5])
                direction = (line.get("direction") or "both").lower()
                pid_sides = state["line_side"].setdefault(line_id, {})
                for det in det_items:
                    if not _class_matches(det, line.get("classes")):
                        continue
                    cx, cy = det.get("center", (0, 0))
                    side = _line_side(
                        p1, p2, (cx / frame_shape[1], cy / frame_shape[0])
                    )
                    entity = det.get("work_key") or f"pid:{det.get('pid')}"
                    prev_side = pid_sides.get(entity)
                    if (
                        prev_side is not None
                        and side != 0
                        and prev_side != 0
                        and (side > 0) != (prev_side > 0)
                    ):
                        direction_tag = (
                            "A->B" if (prev_side > 0 and side < 0) else "B->A"
                        )
                        cross_ok = (
                            direction == "both"
                            or (
                                direction in ("a->b", "a2b")
                                and prev_side > 0
                                and side < 0
                            )
                            or (
                                direction in ("b->a", "b2a")
                                and prev_side < 0
                                and side > 0
                            )
                        )
                        if cross_ok:
                            if _state_throttle(
                                state,
                                f"line:{line_id}:{entity}:{direction_tag}",
                                ALERT_LINE_ZONE_MIN_GAP,
                            ):
                                ev = f"P1 | CAM{cam_key} | LINE {line_id} | CROSS {direction_tag}"
                                send_alert(_alert_subject(det), ev)
                                _queue_event_clip(
                                    camera_id,
                                    ev,
                                    _alert_subject(det),
                                    ts,
                                    {"line_id": line_id, "direction": direction_tag},
                                )

                        if (
                            entry_line_id
                            and line_id == entry_line_id
                            and _class_matches(det, vehicle_classes)
                        ):
                            if _state_throttle(
                                state,
                                f"veh_entry:{line_id}:{entity}",
                                ALERT_LINE_ZONE_MIN_GAP,
                            ):
                                ev = f"P1 | CAM{cam_key} | VEHICLE | ENTRY | LINE {line_id}"
                                send_alert(_alert_subject(det), ev)
                                _queue_event_clip(
                                    camera_id,
                                    ev,
                                    _alert_subject(det),
                                    ts,
                                    {"line_id": line_id, "vehicle": "entry"},
                                )
                        if (
                            exit_line_id
                            and line_id == exit_line_id
                            and _class_matches(det, vehicle_classes)
                        ):
                            if _state_throttle(
                                state,
                                f"veh_exit:{line_id}:{entity}",
                                ALERT_LINE_ZONE_MIN_GAP,
                            ):
                                ev = f"P1 | CAM{cam_key} | VEHICLE | EXIT | LINE {line_id}"
                                send_alert(_alert_subject(det), ev)
                                _queue_event_clip(
                                    camera_id,
                                    ev,
                                    _alert_subject(det),
                                    ts,
                                    {"line_id": line_id, "vehicle": "exit"},
                                )

                    pid_sides[entity] = side

        # Parking rules
        parking = rules.get("parking_rules", {})
        if parking.get("enabled"):
            for zone in parking.get("zones", []) or []:
                zone_id = zone.get("id") or "park"
                points = zone.get("points", [])
                if not points:
                    continue
                pid_map = state["parking"].setdefault(zone_id, {})
                max_seconds = int(zone.get("max_seconds", 600))
                seen_pids = set()
                for det in det_items:
                    if not _class_matches(det, zone.get("classes")):
                        continue
                    cx, cy = det.get("center", (0, 0))
                    inside = _point_in_poly(
                        cx / frame_shape[1], cy / frame_shape[0], points
                    )
                    pid = det.get("pid")
                    if not inside:
                        continue
                    seen_pids.add(pid)
                    rec = pid_map.get(pid)
                    if rec is None:
                        pid_map[pid] = {"since": ts, "alerted": False}
                    else:
                        elapsed = ts - rec.get("since", ts)
                        if elapsed >= max_seconds and not rec.get("alerted"):
                            ev = f"P2 | CAM{cam_key} | PARKING_LIMIT {zone_id}"
                            throttled_alert(_alert_subject(det), ev, pid, min_gap=10.0)
                            _queue_event_clip(
                                camera_id,
                                ev,
                                _alert_subject(det),
                                ts,
                                {"zone_id": zone_id, "parking_limit": max_seconds},
                            )
                            rec["alerted"] = True
                for pid in list(pid_map.keys()):
                    if pid not in seen_pids:
                        pid_map.pop(pid, None)

        # Loitering — person dwell inside ROI intrusion zones
        roi_loiter = rules.get("roi_intrusion", {})
        if roi_loiter.get("enabled"):
            linger_max = max(1, int(roi_loiter.get("linger_seconds", LINGER_SECONDS)))
            for zone in roi_loiter.get("zones", []) or []:
                zone_id = zone.get("id") or "roi"
                points = zone.get("points", [])
                if not points:
                    continue
                entity_map = state["linger"].setdefault(zone_id, {})
                seen_entities = set()
                for det in det_items:
                    if not _class_matches(det, zone.get("classes") or ["person"]):
                        continue
                    cx, cy = det.get("center", (0, 0))
                    inside = _point_in_poly(
                        cx / frame_shape[1], cy / frame_shape[0], points
                    )
                    if not inside:
                        continue
                    entity = det.get("work_key") or f"pid:{det.get('pid')}"
                    seen_entities.add(entity)
                    rec = entity_map.get(entity)
                    if rec is None:
                        entity_map[entity] = {"since": ts, "alerted": False}
                    else:
                        elapsed = ts - rec.get("since", ts)
                        if elapsed >= linger_max and not rec.get("alerted"):
                            if _state_throttle(
                                state,
                                f"linger:{zone_id}:{entity}",
                                ALERT_LINE_ZONE_MIN_GAP,
                            ):
                                ev = f"P2 | CAM{cam_key} | LOITERING | {zone_id}"
                                send_alert(_alert_subject(det), ev)
                                _queue_event_clip(
                                    camera_id,
                                    ev,
                                    _alert_subject(det),
                                    ts,
                                    {
                                        "zone_id": zone_id,
                                        "linger_seconds": linger_max,
                                    },
                                )
                            rec["alerted"] = True
                for entity in list(entity_map.keys()):
                    if entity not in seen_entities:
                        entity_map.pop(entity, None)


# --------------------------------------------------
# ALERT SYSTEM (USE OLD VERSION)
# --------------------------------------------------
alert_channels = set()
last_alert_time = {}  # Per-person+event cooldown
unknown_alert_once = {}
unknown_alert_lock = threading.Lock()
# ── In-memory recognition log (ring buffer, survives only during uptime) ──
recognition_log = deque(maxlen=500)
recognition_log_lock = threading.Lock()
known_detect_last = {}
known_detect_lock = threading.Lock()
presence_alert_lock = threading.Lock()
presence_alert_state = {}
event_clip_lock = threading.Lock()
event_clip_buffers = {}
event_clip_last_push = {}
event_clip_pending = {}
event_clip_last_fs_cleanup = 0.0
cross_overlay_lock = threading.Lock()
cross_overlay_state = {}


def broadcast_payload(payload):
    success_count = 0
    dead_channels = []
    for ch in list(alert_channels):
        try:
            if hasattr(ch, "readyState") and ch.readyState == "open":
                ch.send(payload)
                success_count += 1
            else:
                dead_channels.append(ch)
        except Exception:
            dead_channels.append(ch)
    for ch in dead_channels:
        alert_channels.discard(ch)
    return success_count


def send_enrollment_alert(message):
    if not message:
        return
    payload = json.dumps(
        {"person": "SYSTEM", "event": message, "timestamp": time.strftime("%H:%M:%S")}
    )
    broadcast_payload(payload)


def send_session_guidance(session, message):
    if not session or not message:
        return
    last_message = session.get("last_guidance")
    now = time.time()
    if last_message == message and now - session.get("last_guidance_time", 0) < 1.0:
        return
    session["last_guidance"] = message
    session["last_guidance_time"] = now
    send_enrollment_alert(message)


def has_active_alert_channel():
    return any(
        hasattr(ch, "readyState") and ch.readyState == "open" for ch in alert_channels
    )


def _parse_alert_event(event: str) -> tuple[int | None, int | None]:
    priority = None
    camera_id = None
    for part in (event or "").split("|"):
        token = part.strip()
        m_pri = re.match(r"^P(\d+)$", token, re.I)
        if m_pri:
            try:
                priority = int(m_pri.group(1))
            except Exception:
                pass
            continue
        m_cam = re.match(r"^CAM(\d+)$", token, re.I)
        if m_cam:
            try:
                camera_id = int(m_cam.group(1))
            except Exception:
                pass
    return priority, camera_id


def _enqueue_db_persist(job: dict) -> None:
    try:
        db_persist_queue.put_nowait(job)
    except Exception:
        pass


def _enqueue_segment_persist(info: dict) -> None:
    path = Path(info.get("path", ""))
    try:
        rel = str(path.relative_to(RECORDINGS_DIR))
    except Exception:
        rel = str(path)
    _enqueue_db_persist(
        {
            "type": "segment",
            "camera_id": info.get("camera_id"),
            "path": rel.replace("\\", "/"),
            "start_ts": info.get("start_ts"),
            "end_ts": info.get("end_ts"),
            "size_bytes": info.get("size_bytes", 0),
        }
    )


def _get_segment_writer(camera_id):
    if not CONTINUOUS_RECORDING_ENABLE or camera_id is None:
        return None
    with _segment_writers_lock:
        writer = _segment_writers.get(camera_id)
        if writer is None:
            seg_fps = max(1, min(15, int(PROCESSING_FPS)))
            writer = SegmentWriter(
                camera_id,
                RECORDINGS_DIR,
                segment_secs=CONTINUOUS_SEGMENT_SECS,
                fps=seg_fps,
            )
            writer.set_on_segment_closed(_enqueue_segment_persist)
            _segment_writers[camera_id] = writer
        return writer


def _check_motion_detected(camera_id, frame, person_count: int = 0) -> None:
    if not MOTION_ENABLE or camera_id is None:
        return
    if MOTION_ONLY_WHEN_NO_PERSONS and person_count > 0:
        return
    try:
        cs = _cs(camera_id)
        small = cv2.resize(frame, (320, 180))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        bg = cs.get("motion_bg")
        if bg is None:
            cs["motion_bg"] = gray.astype(np.float32)
            return
        diff = cv2.absdiff(gray, bg.astype(np.uint8))
        cs["motion_bg"] = (0.95 * bg + 0.05 * gray.astype(np.float32))
        motion_pct = float(np.count_nonzero(diff > 25)) / float(diff.size)
        if motion_pct <= MOTION_THRESH:
            return
        now = time.time()
        last = float(cs.get("motion_last_alert", 0.0))
        if now - last < MOTION_ALERT_GAP_SEC:
            return
        cs["motion_last_alert"] = now
        cam_key = _camera_key(camera_id)
        send_alert("SYSTEM", f"P2 | CAM{cam_key} | MOTION_DETECTED")
    except Exception:
        pass


def send_alert(person, event, clip_url: str | None = None, meta: dict | None = None):
    """Thread-safe alert sending"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    # Always log to recognition_log ring buffer (regardless of active channel)
    log_entry = {
        "person": person,
        "event": event,
        "timestamp": ts,
        "clip_url": clip_url,
        "meta": meta,
    }
    with recognition_log_lock:
        recognition_log.appendleft(log_entry)

    priority, camera_id = _parse_alert_event(event)
    client_id = None
    if isinstance(meta, dict) and meta.get("client_id") is not None:
        try:
            client_id = int(meta.get("client_id"))
        except Exception:
            client_id = None
    _enqueue_db_persist(
        {
            "type": "alert",
            "client_id": client_id,
            "camera_id": camera_id,
            "person": person,
            "event": event,
            "priority": priority,
            "clip_url": clip_url,
            "meta": meta,
        }
    )

    logger.info(f"📨 Queueing alert: {person} - {event}")
    payload = {
        "person": person,
        "event": event,
        "timestamp": ts,
    }
    if clip_url:
        payload["clip_url"] = clip_url
    if meta:
        payload["meta"] = meta
    alert_queue.put(payload)


def throttled_alert(name, event, pid, min_gap=2.0, stable_key: str | None = None):
    """Per-person+event cooldown (OLD VERSION)"""
    key = f"{stable_key if stable_key is not None else pid}:{event}"
    now = time.time()
    last = last_alert_time.get(key, 0)

    if now - last >= min_gap:
        send_alert(name, event)
        last_alert_time[key] = now
        return True
    return False


def _alert_subject(det: dict) -> str:
    return str(
        det.get("display_name") or det.get("name") or det.get("label") or "Object"
    )


def _unknown_once_key(det: dict, cam_key: str) -> str:
    wk = det.get("work_key")
    if wk:
        return f"cam:{cam_key}|wk:{wk}"
    cx, cy = det.get("center", (0, 0))
    qx = int(cx // 40)
    qy = int(cy // 40)
    return f"cam:{cam_key}|u:{qx}:{qy}"


def _should_emit_unknown_once(token: str, now_ts: float) -> bool:
    with unknown_alert_lock:
        last = float(unknown_alert_once.get(token, 0.0))
        if now_ts - last < max(1.0, ALERT_UNKNOWN_ONCE_TTL_SEC):
            return False
        unknown_alert_once[token] = now_ts
        return True


def _should_emit_known_detect(key: str, now_ts: float) -> bool:
    with known_detect_lock:
        last = float(known_detect_last.get(key, 0.0))
        if now_ts - last < max(0.0, ALERT_KNOWN_DETECT_MIN_GAP):
            return False
        known_detect_last[key] = now_ts
        return True


def _event_cam_key(camera_id) -> int:
    try:
        return int(camera_id) if camera_id is not None else -1
    except Exception:
        return -1


def _event_buffer_maxlen() -> int:
    return max(20, int((EVENT_CLIP_SECONDS + 3.0) * EVENT_CLIP_FPS) * 2)


def _cleanup_event_clip_files(now_ts: float | None = None) -> None:
    global event_clip_last_fs_cleanup
    if not EVENT_CLIP_ENABLE:
        return
    now_ts = now_ts or time.time()
    if now_ts - event_clip_last_fs_cleanup < 600.0:
        return
    event_clip_last_fs_cleanup = now_ts
    cutoff = now_ts - (EVENT_CLIP_RETENTION_HOURS * 3600)
    try:
        base = EVENT_CLIP_DIR
        if not base.exists():
            return
        for p in base.rglob("*"):
            try:
                if p.is_file() and p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        pass


def _persist_runtime_flags() -> None:
    """Persist runtime feature flags (best-effort)."""
    try:
        RUNTIME_FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "event_clip_enable": bool(EVENT_CLIP_ENABLE),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        RUNTIME_FLAGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        return


def _set_event_clips_enabled(enabled: bool, *, persist: bool = True) -> bool:
    """Enable/disable clip capture. When disabled, pending/buffered clip state is cleared."""
    global EVENT_CLIP_ENABLE
    EVENT_CLIP_ENABLE = bool(enabled)
    if not EVENT_CLIP_ENABLE:
        try:
            with event_clip_lock:
                event_clip_pending.clear()
                event_clip_buffers.clear()
                event_clip_last_push.clear()
        except Exception:
            pass
    if persist:
        _persist_runtime_flags()
    try:
        from app import ml_tracking

        ml_tracking.schedule_tracking(
            ml_tracking.log_config_change,
            source="event_clips_toggle",
            changed_keys=["event_clip_enable"],
            extra_params={"event_clip_enable": bool(EVENT_CLIP_ENABLE)},
        )
    except Exception:
        pass
    return bool(EVENT_CLIP_ENABLE)


async def event_clips_get_settings(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    # If RBAC is enabled, require permission to connect to the CCTV UI anyway.
    if AUTH_READY and can and not can(user, "alerts", "view"):
        return web.Response(status=403)
    return web.json_response({"enabled": bool(EVENT_CLIP_ENABLE)})


async def event_clips_set_settings(request):
    user = request.get("user") or {}
    require_role(user, ["admin"])
    if AUTH_READY and can and not can(user, "rules", "manage"):
        return web.Response(status=403)
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    enabled = bool((body or {}).get("enabled", True))
    final = _set_event_clips_enabled(enabled, persist=True)
    return web.json_response({"enabled": bool(final)})


def _queue_event_clip(
    camera_id,
    event_text: str,
    subject: str,
    event_ts: float | None = None,
    extra: dict | None = None,
) -> None:
    if not EVENT_CLIP_ENABLE:
        return
    ts = float(event_ts or time.time())
    cam = _event_cam_key(camera_id)
    job = {
        "camera_id": cam,
        "event": str(event_text),
        "subject": str(subject or "SYSTEM"),
        "event_ts": ts,
        "start_ts": max(0.0, ts - EVENT_CLIP_PRE_SECONDS),
        "end_ts": ts + EVENT_CLIP_POST_SECONDS,
        "save_at": ts + EVENT_CLIP_POST_SECONDS,
        "extra": dict(extra or {}),
    }
    with event_clip_lock:
        event_clip_pending.setdefault(cam, []).append(job)
    _cleanup_event_clip_files(ts)


def _save_event_clip(job: dict, frames: list[tuple[float, bytes]]) -> None:
    if not frames:
        return
    imgs = []
    for _ts, jpg in frames:
        try:
            arr = np.frombuffer(jpg, dtype=np.uint8)
            fr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if fr is not None:
                imgs.append(fr)
        except Exception:
            continue
    if not imgs:
        return

    cam = job.get("camera_id", -1)
    event_name = str(job.get("event", "EVENT")).replace(" ", "_").replace("|", "_")[:80]
    stamp = datetime.fromtimestamp(float(job.get("event_ts", time.time()))).strftime(
        "%Y%m%d_%H%M%S"
    )
    token = secrets.token_hex(4)
    day_dir = (
        EVENT_CLIP_DIR
        / datetime.fromtimestamp(float(job.get("event_ts", time.time()))).strftime(
            "%Y-%m-%d"
        )
        / f"cam{cam}"
    )
    day_dir.mkdir(parents=True, exist_ok=True)
    video_path = day_dir / f"{stamp}_{event_name}_{token}.mp4"
    meta_path = day_dir / f"{stamp}_{event_name}_{token}.json"

    h, w = imgs[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(
        str(video_path), fourcc, float(EVENT_CLIP_FPS), (int(w), int(h))
    )
    try:
        for fr in imgs:
            if fr.shape[:2] != (h, w):
                fr = cv2.resize(fr, (w, h))
            writer.write(fr)
    finally:
        writer.release()

    meta = {
        "camera_id": cam,
        "subject": job.get("subject"),
        "event": job.get("event"),
        "event_ts": float(job.get("event_ts", 0.0)),
        "start_ts": float(job.get("start_ts", 0.0)),
        "end_ts": float(job.get("end_ts", 0.0)),
        "duration_sec": float(job.get("end_ts", 0.0)) - float(job.get("start_ts", 0.0)),
        "frame_count": len(imgs),
        "video_file": str(video_path),
        "extra": job.get("extra", {}),
    }
    try:
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Notify UI that the clip is ready and clickable.
    try:
        rel = video_path.relative_to(EVENT_CLIP_DIR)
        clip_url = "/event-clips/" + quote(rel.as_posix())
        send_alert(
            "SYSTEM",
            f"P1 | CAM{cam} | CLIP_SAVED | {job.get('event', 'EVENT')}",
            clip_url=clip_url,
            meta={
                "camera_id": cam,
                "event": job.get("event"),
                "event_ts": job.get("event_ts"),
            },
        )
    except Exception:
        pass


def _draw_event_clip_overlays(frame, camera_id) -> None:
    try:
        h, w = frame.shape[:2]
    except Exception:
        return

    # WEB ROI (global drag ROI)
    try:
        if web_roi and bool(web_roi.get("enabled")):
            wx1 = int(float(web_roi.get("x", 0.0)) * w)
            wy1 = int(float(web_roi.get("y", 0.0)) * h)
            wx2 = int((float(web_roi.get("x", 0.0)) + float(web_roi.get("w", 0.0))) * w)
            wy2 = int((float(web_roi.get("y", 0.0)) + float(web_roi.get("h", 0.0))) * h)
            cv2.rectangle(frame, (wx1, wy1), (wx2, wy2), (0, 165, 255), 2)
            cv2.putText(
                frame,
                "WEB ROI",
                (wx1 + 4, max(16, wy1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 165, 255),
                2,
            )
    except Exception:
        pass

    # Per-camera rules: ROI zones + virtual lines + parking zones
    try:
        rules = _get_camera_rules(camera_id)
    except Exception:
        return

    try:
        roi = rules.get("roi_intrusion", {})
        if roi.get("enabled"):
            for zone in roi.get("zones", []) or []:
                pts = []
                for p in zone.get("points", []) or []:
                    if not isinstance(p, (list, tuple)) or len(p) < 2:
                        continue
                    px = int(_clamp01(p[0]) * w)
                    py = int(_clamp01(p[1]) * h)
                    pts.append([px, py])
                if len(pts) >= 2:
                    arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(
                        frame, [arr], isClosed=True, color=(0, 255, 255), thickness=2
                    )
                    zx, zy = pts[0]
                    zid = str(zone.get("id") or "roi")
                    cv2.putText(
                        frame,
                        f"ZONE {zid}",
                        (zx + 4, max(16, zy - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 255),
                        2,
                    )
    except Exception:
        pass

    try:
        vlines = rules.get("virtual_lines", {})
        if vlines.get("enabled"):
            for line in vlines.get("lines", []) or []:
                p1 = line.get("p1") or [0.1, 0.5]
                p2 = line.get("p2") or [0.9, 0.5]
                x1 = int(_clamp01(p1[0]) * w)
                y1 = int(_clamp01(p1[1]) * h)
                x2 = int(_clamp01(p2[0]) * w)
                y2 = int(_clamp01(p2[1]) * h)
                cv2.line(frame, (x1, y1), (x2, y2), (255, 80, 80), 2)
                lid = str(line.get("id") or "line")
                cv2.putText(
                    frame,
                    f"LINE {lid}",
                    (x1 + 4, max(16, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 80, 80),
                    2,
                )
    except Exception:
        pass

    try:
        parking = rules.get("parking_rules", {})
        if parking.get("enabled"):
            for zone in parking.get("zones", []) or []:
                pts = []
                for p in zone.get("points", []) or []:
                    if not isinstance(p, (list, tuple)) or len(p) < 2:
                        continue
                    px = int(_clamp01(p[0]) * w)
                    py = int(_clamp01(p[1]) * h)
                    pts.append([px, py])
                if len(pts) >= 2:
                    arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.polylines(
                        frame, [arr], isClosed=True, color=(180, 0, 255), thickness=2
                    )
                    zx, zy = pts[0]
                    zid = str(zone.get("id") or "park")
                    cv2.putText(
                        frame,
                        f"PARK {zid}",
                        (zx + 4, max(16, zy - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (180, 0, 255),
                        2,
                    )
    except Exception:
        pass


def _event_clip_on_frame(camera_id, frame, ts: float) -> None:
    if not EVENT_CLIP_ENABLE:
        return
    cam = _event_cam_key(camera_id)
    min_dt = 1.0 / float(EVENT_CLIP_FPS)

    should_push = False
    with event_clip_lock:
        last_ts = float(event_clip_last_push.get(cam, 0.0))
        if (ts - last_ts) >= min_dt:
            event_clip_last_push[cam] = ts
            should_push = True

    if should_push:
        try:
            enc_frame = frame
            if EVENT_CLIP_DRAW_OVERLAYS:
                try:
                    enc_frame = frame.copy()
                    _draw_event_clip_overlays(enc_frame, camera_id)
                except Exception:
                    enc_frame = frame
            ok, enc = cv2.imencode(
                ".jpg",
                enc_frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(EVENT_CLIP_JPEG_QUALITY)],
            )
            if ok:
                jpg = enc.tobytes()
                with event_clip_lock:
                    buf = event_clip_buffers.get(cam)
                    if buf is None:
                        buf = deque(maxlen=_event_buffer_maxlen())
                        event_clip_buffers[cam] = buf
                    buf.append((ts, jpg))
        except Exception:
            pass

    due = []
    snapshot = []
    with event_clip_lock:
        pending = event_clip_pending.get(cam, [])
        keep = []
        for job in pending:
            if float(job.get("save_at", 0.0)) <= ts:
                due.append(job)
            else:
                keep.append(job)
        event_clip_pending[cam] = keep
        buf = event_clip_buffers.get(cam)
        if buf is not None:
            snapshot = list(buf)

    if due:
        for job in due:
            s = float(job.get("start_ts", 0.0))
            e = float(job.get("end_ts", ts))
            frames = [(t, b) for (t, b) in snapshot if s <= t <= e]
            if not frames and snapshot:
                # Fallback for sparse buffers/time jitter: save nearest recent frames
                # instead of silently dropping the clip.
                keep_n = max(4, int(EVENT_CLIP_FPS * max(1.0, EVENT_CLIP_SECONDS)))
                frames = snapshot[-keep_n:]
            _save_event_clip(job, frames)

    _cleanup_event_clip_files(ts)


def _set_cross_overlay(
    camera_id, entity_key: str, label: str, ts: float | None = None
) -> None:
    cam = _camera_key(camera_id)
    key = (str(cam), str(entity_key))
    with cross_overlay_lock:
        cross_overlay_state[key] = {
            "ts": float(ts or time.time()),
            "label": str(label),
        }


def _get_cross_overlay(camera_id, entity_key: str, now_ts: float) -> str | None:
    cam = _camera_key(camera_id)
    key = (str(cam), str(entity_key))
    with cross_overlay_lock:
        rec = cross_overlay_state.get(key)
        if not rec:
            return None
        if (now_ts - float(rec.get("ts", 0.0))) > CROSS_OVERLAY_TTL_SEC:
            cross_overlay_state.pop(key, None)
            return None
        return str(rec.get("label") or "") or None


def _emit_presence_alert(camera_id, det_items: list, ts: float) -> None:
    if not FEED_PRESENCE_ALERT_ENABLE:
        return
    if not has_active_alert_channel():
        return

    cam_key = _camera_key(camera_id)
    current = {}
    for d in det_items or []:
        if not d.get("is_person"):
            continue
        nm = str(d.get("display_name") or d.get("name") or "Person")
        raw_name = str(d.get("name") or "")
        wk = d.get("work_key")
        # Use known identity as stable key; for unknown-like labels use work_key/position.
        if (
            raw_name
            and raw_name != "Unknown"
            and not raw_name.lower().startswith("person-")
        ):
            k = f"name:{raw_name.lower()}"
        elif wk:
            k = f"wk:{wk}"
        else:
            cx, cy = d.get("center", (0, 0))
            k = f"u:{int(cx // 60)}:{int(cy // 60)}"
        current[k] = nm

    if not current:
        with presence_alert_lock:
            st = presence_alert_state.get(cam_key)
            if st:
                st["active"] = set()
                st["pending"] = {}
                presence_alert_state[cam_key] = st
        return

    newcomers = []
    with presence_alert_lock:
        st = presence_alert_state.get(
            cam_key, {"active": set(), "pending": {}, "last_emit": {}}
        )
        active = set(st.get("active", set()))
        pending = dict(st.get("pending", {}))
        last_emit = dict(st.get("last_emit", {}))

        # remove vanished identities
        for k in list(active):
            if k not in current:
                active.discard(k)
        for k in list(pending.keys()):
            if k not in current:
                pending.pop(k, None)

        for k, nm in current.items():
            if k in active:
                continue
            rec = pending.get(k, {"count": 0, "name": nm})
            rec["count"] = int(rec.get("count", 0)) + 1
            rec["name"] = nm
            pending[k] = rec

            enough_hits = rec["count"] >= max(1, FEED_NEW_PERSON_MIN_HITS)
            can_realert = (ts - float(last_emit.get(k, 0.0))) >= max(
                0.2, FEED_NEW_PERSON_REALERT_SEC
            )
            if enough_hits and can_realert:
                newcomers.append(nm)
                active.add(k)
                last_emit[k] = ts
                pending.pop(k, None)

        st["active"] = active
        st["pending"] = pending
        st["last_emit"] = last_emit
        presence_alert_state[cam_key] = st

    if newcomers:
        uniq = []
        seen_names = set()
        for n in newcomers:
            if n in seen_names:
                continue
            seen_names.add(n)
            uniq.append(n)
        send_alert("SYSTEM", f"P0 | CAM{cam_key} | NEW_PERSON_SEEN | {', '.join(uniq)}")


def _cache_pid_name(pid: int, candidate_name: str, timestamp: float) -> str:
    with pid_identity_lock:
        info = pid_identity.get(pid)
        if info is None:
            info = {"name": "Unknown", "ts": timestamp}
            pid_identity[pid] = info

        if candidate_name != "Unknown":
            pid_identity[pid] = {"name": candidate_name, "ts": timestamp}
            return candidate_name
        return info.get("name", "Unknown")


def _format_timer(seconds: float) -> str:
    try:
        total = max(0, round(seconds))
    except Exception:
        total = 0
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"




def _update_work_timer(pid: str | int, timestamp: float, active: bool) -> float:
    if not WORK_TIMER_ENABLE:
        return 0.0

    with work_timer_lock:
        rec = work_timer_state.get(pid)
        if rec is None:
            rec = {
                "accumulated": 0.0,
                "started_at": None,
                "last_seen": timestamp,
            }
            work_timer_state[pid] = rec

        rec["last_seen"] = timestamp
        started_at = rec.get("started_at")

        if active:
            if started_at is None:
                rec["started_at"] = timestamp
                started_at = timestamp
            return float(rec.get("accumulated", 0.0)) + max(
                0.0, timestamp - float(started_at)
            )

        if started_at is not None:
            rec["accumulated"] = float(rec.get("accumulated", 0.0)) + max(
                0.0, timestamp - float(started_at)
            )
            rec["started_at"] = None
        return float(rec.get("accumulated", 0.0))


def _peek_work_timer(pid: str | int, timestamp: float) -> float:
    if not WORK_TIMER_ENABLE:
        return 0.0
    with work_timer_lock:
        rec = work_timer_state.get(pid)
        if rec is None:
            return 0.0
        accumulated = float(rec.get("accumulated", 0.0))
        started_at = rec.get("started_at")
        if started_at is None:
            return accumulated
        return accumulated + max(0.0, timestamp - float(started_at))


def _get_or_create_work_display_id(work_key: str) -> int:
    global work_display_counter
    with work_display_lock:
        val = work_display_map.get(work_key)
        if val is None:
            work_display_counter += 1
            val = work_display_counter
            work_display_map[work_key] = val
        return int(val)


def _resolve_work_key(
    pid: int,
    bbox: tuple[float, float, float, float],
    ts: float,
    name: str,
    camera_id: int | None,
    used_keys: set[str] | None = None,
) -> str:
    x1, y1, x2, y2 = bbox
    cx = (float(x1) + float(x2)) * 0.5
    cy = (float(y1) + float(y2)) * 0.5
    candidate_name = (name or "").strip()
    named_key = None
    if candidate_name and candidate_name.lower() != "unknown":
        named_key = f"name:{candidate_name.lower()}"

    with work_key_lock:
        existing = work_key_by_pid.get(pid)
        if existing is not None:
            st = work_track_state.get(existing, {})
            if (
                ts - float(st.get("last_seen", 0.0))
                <= max(WORK_KEY_MAX_GAP_SEC, 0.1) * 4
            ):
                st["center"] = (cx, cy)
                st["last_seen"] = ts
                st["last_pid"] = pid
                st["name"] = candidate_name or st.get("name", "Unknown")
                work_track_state[existing] = st
                return existing

        if named_key is not None:
            work_key_by_pid[pid] = named_key
            work_track_state[named_key] = {
                "center": (cx, cy),
                "last_seen": ts,
                "last_pid": pid,
                "name": candidate_name,
                "camera_id": camera_id,
            }
            return named_key

        best_key = None
        best_dist = None
        for key, st in list(work_track_state.items()):
            if used_keys and key in used_keys:
                continue
            last_seen = float(st.get("last_seen", 0.0))
            if ts - last_seen > max(WORK_KEY_MAX_GAP_SEC, 0.1):
                continue
            prev = st.get("center")
            if not prev:
                continue
            px, py = prev
            dx = float(cx) - float(px)
            dy = float(cy) - float(py)
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= WORK_KEY_MATCH_DISTANCE_PX and (
                best_dist is None or dist < best_dist
            ):
                best_key = key
                best_dist = dist

        if best_key is None:
            best_key = f"anon:{secrets.token_hex(6)}"

        work_key_by_pid[pid] = best_key
        work_track_state[best_key] = {
            "center": (cx, cy),
            "last_seen": ts,
            "last_pid": pid,
            "name": candidate_name or "Unknown",
            "camera_id": camera_id,
        }
        return best_key


def _touch_work_key(
    work_key: str,
    pid: int,
    bbox: tuple[float, float, float, float],
    ts: float,
    name: str,
    camera_id: int | None,
    face_emb: np.ndarray | None = None,
) -> str:
    x1, y1, x2, y2 = bbox
    cx = (float(x1) + float(x2)) * 0.5
    cy = (float(y1) + float(y2)) * 0.5
    with work_key_lock:
        work_key_by_pid[pid] = work_key
        work_track_state[work_key] = {
            "center": (cx, cy),
            "last_seen": ts,
            "last_pid": pid,
            "name": (name or "Unknown"),
            "camera_id": camera_id,
        }
    with work_handoff_lock:
        rec = work_handoff_pool.get(work_key) or {}
        rec["center"] = (cx, cy)
        rec["last_seen"] = ts
        rec["camera_id"] = camera_id
        rec["name"] = name or rec.get("name") or "Unknown"
        if face_emb is not None:
            rec["embedding"] = face_emb
        work_handoff_pool[work_key] = rec
    return work_key


def _match_or_create_face_work_key(
    face_emb: np.ndarray | None,
    ts: float,
    center: tuple[float, float] | None,
    camera_id: int | None,
    used_keys: set[str] | None = None,
) -> str | None:
    if not WORK_EMBED_REID_ENABLE or face_emb is None:
        return None
    emb = np.asarray(face_emb, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(emb))
    if n <= 1e-8:
        return None
    emb = emb / n

    global work_face_profile_counter
    with work_face_reid_lock:
        best_key = None
        best_score = -1.0
        for key, rec in list(work_face_profiles.items()):
            if used_keys and key in used_keys:
                continue
            vec = rec.get("vec")
            if vec is None:
                continue
            try:
                face_sim = float(np.dot(vec, emb))
            except Exception:
                continue
            motion_sim = _motion_similarity(
                rec.get("center"), center, WORK_HANDOFF_MAX_DIST_PX
            )
            score = _hybrid_face_motion_score(face_sim, motion_sim)
            if score > best_score:
                best_score = score
                best_key = key

    # Camera handoff memory pool: recent face embeddings from all cameras.
    with work_handoff_lock:
        for key, rec in list(work_handoff_pool.items()):
            if used_keys and key in used_keys:
                continue
            if (ts - float(rec.get("last_seen", 0.0))) > max(
                1.0, WORK_HANDOFF_POOL_SEC
            ):
                continue
            vec = rec.get("embedding")
            if vec is None:
                continue
            try:
                face_sim = float(np.dot(vec, emb))
            except Exception:
                continue
            motion_sim = _motion_similarity(
                rec.get("center"), center, WORK_HANDOFF_MAX_DIST_PX
            )
            score = _hybrid_face_motion_score(face_sim, motion_sim)
            if score > best_score:
                best_score = score
                best_key = key

    if best_key is not None and best_score >= WORK_EMBED_MATCH_THRESHOLD:
        with work_face_reid_lock:
            rec = work_face_profiles.get(best_key) or {}
            old = rec.get("vec")
            if old is not None:
                a = max(0.0, min(1.0, float(WORK_EMBED_ROLLING_ALPHA)))
                mixed = ((1.0 - a) * old) + (a * emb)
                mixed_norm = float(np.linalg.norm(mixed))
                rec["vec"] = (mixed / mixed_norm) if mixed_norm > 1e-8 else emb
            else:
                rec["vec"] = emb
            rec["last_seen"] = ts
            rec["center"] = center
            rec["camera_id"] = camera_id
            work_face_profiles[best_key] = rec
        with work_handoff_lock:
            h = work_handoff_pool.get(best_key) or {}
            h["embedding"] = rec.get("vec", emb)
            h["last_seen"] = ts
            h["center"] = center
            h["camera_id"] = camera_id
            h["name"] = name or rec.get("name") or "Unknown"
            work_handoff_pool[best_key] = h
        return best_key

    with work_face_reid_lock:
        work_face_profile_counter += 1
        new_key = f"face:{work_face_profile_counter}"
        work_face_profiles[new_key] = {
            "vec": emb,
            "last_seen": ts,
            "center": center,
            "camera_id": camera_id,
        }
    with work_handoff_lock:
        work_handoff_pool[new_key] = {
            "embedding": emb,
            "last_seen": ts,
            "center": center,
            "camera_id": camera_id,
            "name": "Unknown",
        }
    return new_key


def _handle_roi_events(
    pid: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    roi_box: tuple[int, int, int, int],
    name: str,
    camera_id=None,
    stable_key: str | None = None,
) -> None:
    wx1, wy1, wx2, wy2 = roi_box
    # Make touch detection more tolerant: expand bbox a little so partial edge
    # touches still count as ROI contact.
    ex1 = float(x1) - ROI_TOUCH_MARGIN_PX
    ey1 = float(y1) - ROI_TOUCH_MARGIN_PX
    ex2 = float(x2) + ROI_TOUCH_MARGIN_PX
    ey2 = float(y2) + ROI_TOUCH_MARGIN_PX
    x_overlap = max(0.0, min(ex2, float(wx2)) - max(ex1, float(wx1)))
    y_overlap = max(0.0, min(ey2, float(wy2)) - max(ey1, float(wy1)))
    inside = (
        x_overlap >= ROI_TOUCH_MIN_OVERLAP_PX and y_overlap >= ROI_TOUCH_MIN_OVERLAP_PX
    )

    roi_entity = stable_key or f"pid:{pid}"

    with roi_state_lock:
        state = roi_state.setdefault(roi_entity, set())
        inside_state = "WEBROI" in state

    if inside and not inside_state:
        logger.info("🔔 %s entered WEBROI", roi_entity)
        cam = _camera_key(camera_id)
        ev = f"P1 | CAM{cam} | WEBROI | ENTER"
        alerted = throttled_alert(
            name,
            ev,
            pid,
            min_gap=max(0.1, ALERT_WEBROI_MIN_GAP),
            stable_key=f"webroi:{cam}:{roi_entity}:enter",
        )
        if alerted:
            _queue_event_clip(
                camera_id,
                ev,
                name,
                time.time(),
                {"transition": "enter", "roi": "WEBROI"},
            )
        _set_cross_overlay(camera_id, roi_entity, "WEBROI ENTER", time.time())
        with roi_state_lock:
            roi_state[roi_entity].add("WEBROI")
    elif not inside and inside_state:
        logger.info("🔕 %s exited WEBROI", roi_entity)
        cam = _camera_key(camera_id)
        ev = f"P1 | CAM{cam} | WEBROI | EXIT"
        alerted = throttled_alert(
            name,
            ev,
            pid,
            min_gap=max(0.1, ALERT_WEBROI_MIN_GAP),
            stable_key=f"webroi:{cam}:{roi_entity}:exit",
        )
        if alerted:
            _queue_event_clip(
                camera_id,
                ev,
                name,
                time.time(),
                {"transition": "exit", "roi": "WEBROI"},
            )
        _set_cross_overlay(camera_id, roi_entity, "WEBROI EXIT", time.time())
        with roi_state_lock:
            roi_state[roi_entity].discard("WEBROI")


def cleanup_old_pids(max_age=PID_STATE_TTL, active_pids_override=None) -> None:
    global last_active_alert_keys
    now = time.time()
    if active_pids_override is not None:
        active_pids = set(active_pids_override)
    else:
        active_pids = set()
    active_entities = set(active_pids)
    try:
        active_entities.update(last_active_alert_keys)
    except Exception:
        pass

    with pid_smooth_lock:
        stale = [pid for pid in pid_smooth.keys() if pid not in active_pids]
        for pid in stale:
            pid_smooth.pop(pid, None)

    with pid_identity_lock:
        stale = [
            pid
            for pid, info in pid_identity.items()
            if now - info.get("ts", 0) > max_age
        ]
        for pid in stale:
            pid_identity.pop(pid, None)

    with roi_state_lock:
        stale = [pid for pid in list(roi_state.keys()) if pid not in active_entities]
        for pid in stale:
            roi_state.pop(pid, None)

    with pid_display_lock:
        stale = [pid for pid in list(pid_display_map.keys()) if pid not in active_pids]
        for pid in stale:
            pid_display_map.pop(pid, None)

    with work_timer_lock:
        if WORK_TIMER_STALE_SEC > 0:
            stale_by_time = [
                key
                for key, rec in list(work_timer_state.items())
                if (now - float(rec.get("last_seen", 0))) > WORK_TIMER_STALE_SEC
            ]
            for key in stale_by_time:
                work_timer_state.pop(key, None)

    with work_key_lock:
        stale_pid_keys = [
            pid for pid in list(work_key_by_pid.keys()) if pid not in active_pids
        ]
        for pid in stale_pid_keys:
            work_key_by_pid.pop(pid, None)
        stale_track_keys = [
            key
            for key, st in list(work_track_state.items())
            if (now - float(st.get("last_seen", 0.0))) > max(1.0, WORK_TIMER_STALE_SEC)
        ]
        for key in stale_track_keys:
            work_track_state.pop(key, None)

    with work_face_reid_lock:
        stale_face = [
            key
            for key, rec in list(work_face_profiles.items())
            if (now - float(rec.get("last_seen", 0.0)))
            > max(1.0, WORK_HANDOFF_POOL_SEC)
        ]
        for key in stale_face:
            work_face_profiles.pop(key, None)

    with work_handoff_lock:
        stale_handoff = [
            key
            for key, rec in list(work_handoff_pool.items())
            if (now - float(rec.get("last_seen", 0.0)))
            > max(1.0, WORK_HANDOFF_POOL_SEC)
        ]
        for key in stale_handoff:
            work_handoff_pool.pop(key, None)

    with work_display_lock:
        valid_keys = set(work_track_state.keys())
        stale_display = [
            k for k in list(work_display_map.keys()) if k not in valid_keys
        ]
        for k in stale_display:
            work_display_map.pop(k, None)

    # Clean per-camera rule state
    with camera_states_lock:
        for state in camera_states.values():
            lock = state.get("lock")
            if lock:
                lock.acquire()
            try:
                for zone_id, pid_map in (state.get("roi_inside") or {}).items():
                    for pid in list(pid_map.keys()):
                        if pid not in active_entities:
                            pid_map.pop(pid, None)
                for line_id, pid_map in (state.get("line_side") or {}).items():
                    for pid in list(pid_map.keys()):
                        if pid not in active_entities:
                            pid_map.pop(pid, None)
                for zone_id, pid_map in (state.get("parking") or {}).items():
                    for pid in list(pid_map.keys()):
                        if pid not in active_entities:
                            pid_map.pop(pid, None)
                alert_last = state.get("alert_last") or {}
                cutoff = now - 300.0
                for key, t in list(alert_last.items()):
                    if t < cutoff:
                        alert_last.pop(key, None)
            finally:
                if lock:
                    lock.release()

    cutoff_alert = now - 300.0
    stale_alerts = [k for k, t in last_alert_time.items() if t < cutoff_alert]
    for k in stale_alerts:
        last_alert_time.pop(k, None)

    with unknown_alert_lock:
        stale_unknown = [
            k
            for k, t in unknown_alert_once.items()
            if (now - float(t)) > max(1.0, ALERT_UNKNOWN_ONCE_TTL_SEC)
        ]
        for k in stale_unknown:
            unknown_alert_once.pop(k, None)

    with known_detect_lock:
        stale_known = [
            k
            for k, t in known_detect_last.items()
            if (now - float(t)) > max(30.0, ALERT_KNOWN_DETECT_MIN_GAP * 5.0)
        ]
        for k in stale_known:
            known_detect_last.pop(k, None)

    with presence_alert_lock:
        for cam, st in list(presence_alert_state.items()):
            if not isinstance(st, dict):
                continue
            last_emit = dict(st.get("last_emit", {}))
            stale_le = [
                k
                for k, t in last_emit.items()
                if (now - float(t)) > max(60.0, FEED_NEW_PERSON_REALERT_SEC * 4.0)
            ]
            for k in stale_le:
                last_emit.pop(k, None)
            st["last_emit"] = last_emit
            presence_alert_state[cam] = st

    with event_clip_lock:
        for cam, jobs in list(event_clip_pending.items()):
            event_clip_pending[cam] = [
                j
                for j in jobs
                if (now - float(j.get("event_ts", now)))
                <= max(5.0, EVENT_CLIP_SECONDS * 4.0)
            ]


# --------------------------------------------------
# FRAME PROCESSING (OPTIMIZED)
# --------------------------------------------------
def _get_semantic_color_and_label(det: dict, is_in_roi: bool, work_seconds: float = 0.0) -> tuple[tuple[int, int, int], str]:
    is_person = bool(det.get("is_person"))
    raw_name = det.get("name", "Unknown")
    is_known = is_person and raw_name != "Unknown"
    is_vehicle = bool(det.get("is_vehicle")) or det.get("label") in ["car", "truck", "bus", "motorcycle"]
    is_fire = bool(det.get("is_fire"))
    is_face = bool(det.get("is_face"))
    is_plate = bool(det.get("is_plate"))
    det_source = det.get("source")
    
    color = (0, 255, 0)  # Default: Green
    draw_label = raw_name if is_known else ""

    if is_person:
        if is_known:
            color = (255, 0, 255)  # Purple: Known Face
            draw_label = raw_name
        elif is_in_roi:
            # Check loitering vs intrusion
            if work_seconds >= 10.0:
                color = (0, 165, 255)  # Orange: Loitering
                draw_label = "Loitering"
            else:
                color = (0, 0, 255)  # Red: Intrusion
                draw_label = "Intrusion"
        else:
            color = (255, 0, 0)  # Blue: Unknown Person
            draw_label = "Unknown Person"
    elif is_vehicle:
        color = (255, 255, 0)  # Cyan: Vehicle
        draw_label = (det.get("label") or "Vehicle").capitalize()
    elif is_fire:
        color = (0, 80, 255)  # Fire orange-red
        draw_label = f"🔥 {det.get('label', 'FIRE').upper()}"
    elif is_face and det_source == "face_det":
        color = (255, 0, 255)  # Purple: Face
        draw_label = "Face"
    elif is_plate or det_source == "lpd":
        color = (0, 255, 128)  # Plate
        draw_label = "Plate"
    else:
        # Fallback category
        color = (0, 255, 0)  # Green: Person/Other
        draw_label = (det.get("label") or "Object").capitalize()

    # Clean label format with confidence
    conf = det.get("conf")
    if conf:
        if not draw_label:
            draw_label = "Person" if is_person else (det.get("label") or "Object").capitalize()
        draw_label = f"{draw_label} {conf:.0%}"
        
    return color, draw_label


def _draw_det_bbox(frame, x1, y1, x2, y2, label, color, box_thickness=2):
    if DISABLE_DRAWING:
        return
    """
    High-quality bounding-box overlay:
      • Corner-bracket style (L-shapes at each corner) instead of a full rectangle
      • Semi-transparent filled label background (ROI-only alpha blend)
      • Two-layer text (dark shadow + white on top) for maximum readability
      • Clamps label position so it never runs off the frame edge
    """
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w - 1, x2)
    y2 = min(h - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return

    # ── Full rectangle ─────────────────────────────────────────────────────────
    bw = max(1, box_thickness)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, bw, lineType=cv2.LINE_AA)

    # ── Label background ──────────────────────────────────────────────────────
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.40
    font_thick = 1
    (txt_w, txt_h), baseline = cv2.getTextSize(label, font, font_scale, font_thick)
    pad = 3

    # Default: label above the box
    lbl_x1 = x1
    lbl_y2 = y1  # bottom of label rectangle = top of box
    lbl_y1 = lbl_y2 - txt_h - baseline - pad * 2

    # If label would go off the top, place it inside the box top instead
    if lbl_y1 < 0:
        lbl_y1 = y1
        lbl_y2 = y1 + txt_h + baseline + pad * 2

    # Clamp right edge
    lbl_x2 = min(w - 1, lbl_x1 + txt_w + pad * 2)
    lbl_x1 = max(0, lbl_x1)

    # Solid dark label background — fast, no alpha-blend copy needed.
    ry1 = max(0, lbl_y1)
    ry2 = min(h, lbl_y2)
    rx1 = max(0, lbl_x1)
    rx2 = min(w, lbl_x2)
    if ry2 > ry1 and rx2 > rx1:
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 0, 0), -1)

    # ── Text (shadow + foreground) ────────────────────────────────────────────
    txt_x = lbl_x1 + pad
    txt_y = lbl_y2 - baseline - pad
    # Shadow (dark offset for depth)
    cv2.putText(
        frame,
        label,
        (txt_x + 1, txt_y + 1),
        font,
        font_scale,
        (0, 0, 0),
        font_thick + 1,
        cv2.LINE_AA,
    )
    # Always use white text for maximum readability against colored label background
    cv2.putText(
        frame,
        label,
        (txt_x, txt_y),
        font,
        font_scale,
        (255, 255, 255),
        font_thick,
        cv2.LINE_AA,
    )


def _draw_cached_dets(frame, cached, roi_box, camera_id=None):
    now_ts = time.time()
    for det in cached or []:
        try:
            x1, y1, x2, y2 = det.get("box", (0, 0, 0, 0))
            is_person = bool(det.get("is_person"))
            entity_key = det.get("work_key") or f"pid:{det.get('pid')}"

            is_in_roi = False
            if roi_box and is_person:
                with roi_state_lock:
                    is_in_roi = (
                        entity_key in roi_state and "WEBROI" in roi_state[entity_key]
                    )

            work_seconds = float(det.get("work_seconds") or 0.0)
            if WORK_TIMER_ENABLE and is_person:
                work_key = det.get("work_key")
                if work_key is not None:
                    work_seconds = _peek_work_timer(str(work_key), now_ts)

            color, draw_label = _get_semantic_color_and_label(det, is_in_roi, work_seconds)

            cross_tag = (
                _get_cross_overlay(camera_id, entity_key, now_ts) if is_person else None
            )
            if cross_tag:
                draw_label = f"{draw_label} [{cross_tag}]"

            if WORK_TIMER_ENABLE and is_person:
                timer_txt = _format_timer(work_seconds)
                draw_label = f"{draw_label} {timer_txt}".strip()



            if cross_tag:
                flash_on = (CROSS_OVERLAY_FLASH_HZ <= 0.0) or (
                    int(now_ts * CROSS_OVERLAY_FLASH_HZ) % 2 == 0
                )
                color = (0, 0, 255) if flash_on else (0, 180, 255)
                thickness = 3 if flash_on else 2
            else:
                thickness = 2
            _draw_det_bbox(
                frame, x1, y1, x2, y2, draw_label, color, box_thickness=thickness
            )
        except Exception:
            continue


def process_frame(
    frame, yolo_input_resolution=None, no_pre_resize: bool = False, camera_id=None
):
    # Silence extremely verbose per-frame prints unless explicitly enabled.
    if not PROCESS_FRAME_DEBUG:

        def print(*args, **kwargs):  # type: ignore[no-redef]
            return

    if ENROLLMENT_ACTIVE:
        return frame
    t0 = time.perf_counter()
    t = t0
    global pid_display_counter, last_active_pids, last_active_alert_keys

    # Per-camera state (fixes ghost bboxes bleeding across cameras)
    cs = _cs(camera_id)

    now = time.time()
    orig_h, orig_w = frame.shape[:2]
    process_frame.frame_counter = getattr(process_frame, "frame_counter", 0) + 1
    # Per-camera counter — avoids all cameras triggering face-id simultaneously.
    cam_frame_counter = _get_cam_frame_counter(camera_id)

    if process_frame.frame_counter % 100 == 0:
        cleanup_old_pids(active_pids_override=last_active_pids)

    frame_times.append(now)
    if len(frame_times) >= 2 and process_frame.frame_counter % 30 == 0:
        duration = frame_times[-1] - frame_times[0]
        if duration > 0:
            fps = len(frame_times) / duration
            logger.info(f"🎬 Processing FPS: {fps:.1f}")

    roi_box = None
    if web_roi and bool(web_roi.get("enabled")):
        wx1 = int(web_roi["x"] * orig_w)
        wy1 = int(web_roi["y"] * orig_h)
        wx2 = int((web_roi["x"] + web_roi["w"]) * orig_w)
        wy2 = int((web_roi["y"] + web_roi["h"]) * orig_h)
        roi_box = (wx1, wy1, wx2, wy2)
        if PROCESS_FRAME_DEBUG or process_frame.frame_counter % 60 == 0:
            print(
                f"📏 ROI AREA: ({wx1},{wy1}) to ({wx2},{wy2}) [{wx2 - wx1}x{wy2 - wy1}px]"
            )

    cached_person_count = sum(
        1 for d in (cs.get("draw_dets") or []) if d.get("is_person")
    )
    _check_motion_detected(camera_id, frame, cached_person_count)

    should_process = (
        process_frame.frame_counter % YOLO_PROCESS_EVERY_N_FRAMES == 0
        or cs["yolo_frame"] is None
        or now - cs["yolo_time"] > 1.0
    )
    if not should_process:
        if cs["draw_dets"]:
            _draw_cached_dets(frame, cs["draw_dets"], roi_box, camera_id)
        try:
            _event_clip_on_frame(camera_id, frame, time.time())
        except Exception:
            pass
        # Never return a stale frame; it causes visible freezing/jitter.
        return frame

    cs["yolo_time"] = now
    target_w, target_h = yolo_input_resolution or YOLO_INPUT_RESOLUTION
    if no_pre_resize:
        small = frame
    else:
        try:
            small = cv2.resize(frame, (target_w, target_h))
        except Exception:
            fallback_w = min(max(64, frame.shape[1]), target_w)
            fallback_h = min(max(64, frame.shape[0]), target_h)
            small = cv2.resize(frame, (fallback_w, fallback_h))
    processed_h, processed_w = small.shape[:2]

    # Ensure contiguous memory for faster upload/preprocess.
    try:
        small = np.ascontiguousarray(small)
    except Exception:
        pass
    t = log_step("resize", t)
    t_resize = time.perf_counter()

    amp_enabled = bool(use_cuda and YOLO_ENABLE_FP16)
    yolo_imgsz = int(max(target_w, target_h))
    raw_dets = []
    yolo_names = getattr(yolo_model, "names", {})

    def _label_for(cls_id):
        try:
            if isinstance(yolo_names, dict):
                return str(yolo_names.get(cls_id, cls_id))
            if (
                isinstance(yolo_names, (list, tuple))
                and cls_id is not None
                and cls_id < len(yolo_names)
            ):
                return str(yolo_names[cls_id])
        except Exception:
            pass
        return str(cls_id) if cls_id is not None else "object"

    use_tiling = bool(YOLO_TILING and no_pre_resize)
    # Pass the ByteTracker low-threshold as the model-level NMS confidence floor.
    # This removes near-zero-confidence noise *inside* YOLO before it ever reaches
    # ByteTracker, keeping the tracker's state clean without throwing away the
    # low-confidence detections that ByteTracker needs for its rescue pool.
    # Default raised to 0.15 in sync with BT_TRACK_LOW_THRESH.
    _yolo_conf_thr = max(0.01, float(os.getenv("BT_TRACK_LOW_THRESH", "0.15")))

    # --- Run general YOLO model (MODEL_SELECT 1, 5, 6) ---
    results = None
    if yolo_model is not None:
        with torch.inference_mode():
            with torch.cuda.amp.autocast(enabled=amp_enabled):
                if use_tiling:
                    tile_w = max(1, orig_w // 2)
                    tile_h = max(1, orig_h // 2)
                    tiles = [
                        (0, 0, tile_w, tile_h),
                        (tile_w, 0, orig_w, tile_h),
                        (0, tile_h, tile_w, orig_h),
                        (tile_w, tile_h, orig_w, orig_h),
                    ]
                    for x0, y0, x1, y1 in tiles:
                        tile = frame[y0:y1, x0:x1]
                        if tile.size == 0:
                            continue
                        results = yolo_model(tile, imgsz=yolo_imgsz, verbose=False, conf=_yolo_conf_thr, iou=0.45)[0]
                        for b in results.boxes:
                            cls_id = None
                            conf = None
                            try:
                                cls_id = int(b.cls[0]) if hasattr(b, "cls") else None
                            except Exception:
                                cls_id = None
                            try:
                                conf = float(b.conf[0]) if hasattr(b, "conf") else None
                            except Exception:
                                conf = None
                            if (
                                PERSON_CLASS_IDS
                                and cls_id is not None
                                and cls_id not in PERSON_CLASS_IDS
                            ):
                                continue
                            if conf is not None and conf < YOLO_MIN_CONF:
                                continue
                            bx1, by1, bx2, by2 = b.xyxy[0].tolist()
                            raw_dets.append(
                                {
                                    "box": [bx1 + x0, by1 + y0, bx2 + x0, by2 + y0],
                                    "cls_id": cls_id,
                                    "conf": conf,
                                    "label": _label_for(cls_id),
                                }
                            )
                    processed_h, processed_w = orig_h, orig_w
                    results = None
                else:
                    results = yolo_model(small, imgsz=yolo_imgsz, verbose=False, conf=_yolo_conf_thr, iou=0.45)[0]
    # Note: torch.cuda.synchronize() removed — accessing tensor data (.tolist(),
    # .cls, .conf) already triggers an implicit sync.  The explicit call was
    # adding ~2-5 ms of pure wait per frame across all 4 camera threads.
    t = log_step("yolo", t)
    t_yolo = time.perf_counter()

    try:
        with stats_lock:
            stats_counters["detection_runs"] += 1
    except Exception:
        pass

    detections = len(results.boxes) if results is not None else len(raw_dets)
    if cam_frame_counter % 100 == 0:
        logger.debug(f"🔍 YOLO detected {detections} objects (cam {camera_id})")

    if results is not None:
        for b in results.boxes:
            cls_id = None
            conf = None
            try:
                cls_id = int(b.cls[0]) if hasattr(b, "cls") else None
            except Exception:
                cls_id = None
            try:
                conf = float(b.conf[0]) if hasattr(b, "conf") else None
            except Exception:
                conf = None

            if (
                PERSON_CLASS_IDS
                and cls_id is not None
                and cls_id not in PERSON_CLASS_IDS
            ):
                continue
            if conf is not None and conf < YOLO_MIN_CONF:
                continue

            x1, y1, x2, y2 = b.xyxy[0].tolist()
            scale_x = orig_w / processed_w if processed_w else 1.0
            scale_y = orig_h / processed_h if processed_h else 1.0
            x1 *= scale_x
            x2 *= scale_x
            y1 *= scale_y
            y2 *= scale_y
            raw_dets.append(
                {
                    "box": [x1, y1, x2, y2],
                    "cls_id": cls_id,
                    "conf": conf,
                    "label": _label_for(cls_id),
                    "source": "yolo",
                }
            )

    # --- Run specialized models based on MODEL_SELECT ---
    def _run_specialized_model(model, input_frame, model_name, scale_x=1.0, scale_y=1.0):
        """Run a specialized YOLO model and return raw detections."""
        spec_dets = []
        if model is None:
            return spec_dets
        try:
            spec_names = getattr(model, "names", {})
            spec_results = model(input_frame, imgsz=yolo_imgsz, verbose=False, conf=0.25, iou=0.45)[0]
            for b in spec_results.boxes:
                try:
                    cls_id = int(b.cls[0]) if hasattr(b, "cls") else None
                except Exception:
                    cls_id = None
                try:
                    conf = float(b.conf[0]) if hasattr(b, "conf") else None
                except Exception:
                    conf = None
                if conf is not None and conf < 0.20:
                    continue
                sx1, sy1, sx2, sy2 = b.xyxy[0].tolist()
                sx1 *= scale_x
                sx2 *= scale_x
                sy1 *= scale_y
                sy2 *= scale_y
                # Get label from model's class names
                spec_label = str(spec_names.get(cls_id, cls_id)) if isinstance(spec_names, dict) else str(cls_id)
                spec_dets.append({
                    "box": [sx1, sy1, sx2, sy2],
                    "cls_id": cls_id,
                    "conf": conf,
                    "label": spec_label,
                    "source": model_name,
                })
        except Exception as e:
            logger.warning(f"[{model_name}] inference error: {e}")
        return spec_dets

    _spec_scale_x = orig_w / processed_w if processed_w else 1.0
    _spec_scale_y = orig_h / processed_h if processed_h else 1.0

    with torch.inference_mode():
        with torch.cuda.amp.autocast(enabled=amp_enabled):
            # Face detection model (MODEL_SELECT 2, 5, 7, 11, 12)
            if face_det_model is not None:
                _run_face = (MODEL_SELECT in (2, 7, 11, 12)) or (cam_frame_counter % max(1, FACE_DET_EVERY_N_FRAMES) == 0)
                if _run_face:
                    raw_dets.extend(_run_specialized_model(
                        face_det_model, small, "face_det", _spec_scale_x, _spec_scale_y
                    ))

            # Fire/smoke model (MODEL_SELECT 3, 5, 7, 11, 12)
            if fire_model is not None:
                _run_fire = (MODEL_SELECT in (3, 7, 11, 12)) or (cam_frame_counter % max(1, FIRE_EVERY_N_FRAMES) == 0)
                if _run_fire:
                    raw_dets.extend(_run_specialized_model(
                        fire_model, small, "fire", _spec_scale_x, _spec_scale_y
                    ))

            # License plate model (MODEL_SELECT 4, 5, 7, 11, 12)
            if lpd_model is not None:
                _run_lpd = (MODEL_SELECT in (4, 7, 11, 12)) or (cam_frame_counter % max(1, LPD_EVERY_N_FRAMES) == 0)
                if _run_lpd:
                    raw_dets.extend(_run_specialized_model(
                        lpd_model, small, "lpd", _spec_scale_x, _spec_scale_y
                    ))

    t_pre_track = time.perf_counter()
    if USE_BYTETRACK:
        raw_dets = _apply_bytetrack(raw_dets, frame, camera_id, _label_for)
    t_track = time.perf_counter()
    track_ms_this = (t_track - t_pre_track) * 1000.0

    raw_dets = _dedupe_overlapping_dets(raw_dets, iou_thr=WORK_DEDUPE_IOU)

    ts = time.time()
    active_ids = []
    active_alert_keys = set()
    used_work_keys = set()
    active_track_ids = []
    pid_tracker = _get_pid_tracker(camera_id) if PID_ENABLE else None

    # ----------------------------------------------------------------
    # Batch face recognition — ONE GPU pass covers ALL people per frame.
    # Every FACE_EVERY_N_FRAMES-th frame we run recognize_batch on the
    # full frame; InsightFace detects all faces in one shot and we match
    # each result back to the YOLO box.  This avoids N sequential model
    # calls and keeps the feed smooth even with many people in view.
    # ----------------------------------------------------------------
    can_faceid = bool(
        FACE_ENABLE and faceid and faceid.app and faceid.embeddings is not None
    )
    should_faceid_now = cam_frame_counter % max(1, FACE_EVERY_N_FRAMES) == 0

    # Collect person boxes/indices for batch call (we need PIDs first, so
    # we do a lightweight first pass to resolve PIDs, then batch face-id).
    person_entries = []  # (list_index, pid, x1, y1, x2, y2)
    resolved_pids = []  # pid per raw_det index, filled in main loop below

    for i, det in enumerate(raw_dets):
        x1, y1, x2, y2 = det.get("box", (0, 0, 0, 0))
        track_id = det.get("track_id")
        try:
            if pid_tracker and track_id is not None:
                tid = int(track_id)
                with pid_tracker_op_lock:
                    pid = pid_tracker.assign_pid(
                        tid, (x1, y1, x2, y2), ts, window=PID_REUSE_WINDOW
                    )
                    pid_tracker.mark_active(pid, (x1, y1, x2, y2), ts)
                active_track_ids.append(tid)
            elif track_id is not None:
                pid = int(track_id)
            else:
                q = 10
                stable_id = (
                    int(round(x1 / q) * q),
                    int(round(y1 / q) * q),
                    int(round(x2 / q) * q),
                    int(round(y2 / q) * q),
                )
                pid = int(hash(stable_id) & 0x7FFFFFFF)
        except Exception:
            pid = i
        x1, y1, x2, y2 = smooth_bbox(pid, (x1, y1, x2, y2), confidence=det.get("conf", 1.0))
        resolved_pids.append((pid, x1, y1, x2, y2))
        class_flags = _classify_label(det.get("label"), det.get("cls_id"))
        if class_flags.get("is_person"):
            person_entries.append((i, pid, x1, y1, x2, y2))
        active_ids.append(pid)

    # Single batched face-id call (one GPU inference for all people).
    # Non-blocking lock: if another camera thread is already running InsightFace,
    # skip this frame — _cache_pid_name will return the last known name.
    batch_results: dict[int, tuple] = {}  # det_index -> (name, score, emb)
    if can_faceid and should_faceid_now and person_entries:
        face_lock_acquired = faceid_inference_lock.acquire(blocking=False)
        if face_lock_acquired:
            face_start = time.time()
            try:
                filtered_entries = [
                    entry
                    for entry in person_entries
                    if (entry[5] - entry[3]) >= FACE_MIN_BBOX_HEIGHT
                ]
                boxes_for_batch = [
                    (x1, y1, x2, y2) for _, _, x1, y1, x2, y2 in filtered_entries
                ]
                batch = faceid.recognize_batch(frame, boxes_for_batch)
                for (det_i, pid_i, *_), result in zip(filtered_entries, batch):
                    batch_results[det_i] = result
            except Exception as _face_err:
                logger.warning("[FACE] recognize_batch error: %s", _face_err)
            finally:
                faceid_inference_lock.release()
            face_time_total_ms = (time.time() - face_start) * 1000
            if cam_frame_counter % (max(1, FACE_EVERY_N_FRAMES) * 10) == 0:
                logger.info(
                    f"⏱️ Batch face recognition ({len(person_entries)} people): {face_time_total_ms:.1f}ms"
                )
            t = log_step("faceid", t)
        # else: lock busy — skip face-id this frame, use cached names
    else:
        face_time_total_ms = 0.0



    det_items = []
    for i, det in enumerate(raw_dets):
        pid, x1, y1, x2, y2 = resolved_pids[i]
        cls_id = det.get("cls_id")
        label = det.get("label")
        track_id = det.get("track_id")

        face_time_ms = None
        name = "Unknown"
        face_emb = None
        class_flags = _classify_label(label, cls_id)
        is_person = class_flags.get("is_person")
        is_vehicle = class_flags.get("is_vehicle")
        is_animal = class_flags.get("is_animal")
        is_plate = class_flags.get("is_plate")
        is_fire = class_flags.get("is_fire")
        is_face = class_flags.get("is_face")
        det_source = det.get("source", "yolo")

        if is_person and i in batch_results:
            name, _score, face_emb = batch_results[i]

        if is_person:
            name = _cache_pid_name(pid, name, now)
        else:
            name = label or "Object"

        work_key = None
        display_id = None
        if is_person:
            # Highest priority: known face name (cross-camera continuity).
            if WORK_CROSS_CAMERA_BY_NAME and name and name != "Unknown":
                work_key = _touch_work_key(
                    f"name:{name.lower()}",
                    pid,
                    (x1, y1, x2, y2),
                    ts,
                    name,
                    camera_id,
                    face_emb,
                )
            # Next: face-embedding re-id for unknowns across camera switches.
            elif face_emb is not None:
                emb_key = _match_or_create_face_work_key(
                    face_emb,
                    ts,
                    center=(
                        (float(x1) + float(x2)) * 0.5,
                        (float(y1) + float(y2)) * 0.5,
                    ),
                    camera_id=camera_id,
                    used_keys=used_work_keys,
                )
                if emb_key is not None:
                    work_key = _touch_work_key(
                        emb_key, pid, (x1, y1, x2, y2), ts, name, camera_id, face_emb
                    )

            # Then: tracker-anchored key when available to keep ID/timer stable.
            if work_key is None and track_id is not None:
                try:
                    work_key = _touch_work_key(
                        f"trk:{int(track_id)}",
                        pid,
                        (x1, y1, x2, y2),
                        ts,
                        name,
                        camera_id,
                        face_emb,
                    )
                except Exception:
                    work_key = _resolve_work_key(
                        pid,
                        (x1, y1, x2, y2),
                        ts,
                        name,
                        camera_id,
                        used_keys=used_work_keys,
                    )
            if work_key is None:
                work_key = _resolve_work_key(
                    pid, (x1, y1, x2, y2), ts, name, camera_id, used_keys=used_work_keys
                )
            used_work_keys.add(work_key)
            display_id = _get_or_create_work_display_id(work_key)

        display_name = name
        if is_person and display_id is not None and name == "Unknown":
            display_name = f"Person-{display_id}"

        alert_identity_key = work_key if (work_key is not None) else f"pid:{pid}"
        active_alert_keys.add(alert_identity_key)

        if PROCESS_FRAME_DEBUG:
            print(f"\n👤 DETECTION {i}:")
            print(f"  PID: {pid}, Name: {display_name}")
            print(f"  BBox: ({x1:.0f},{y1:.0f}) to ({x2:.0f},{y2:.0f})")

        # Keep detection alerts low-noise in production:
        # - Unknown person detection alerts are handled by UNKNOWN_PERSON_FIRST_SEEN in rules.
        # - Known person detection uses a wider cooldown.
        alert_sent = False
        if is_person and name != "Unknown":
            known_key = work_key or f"name:{name.lower()}" if name else f"pid:{pid}"
            if _should_emit_known_detect(str(known_key), ts):
                send_alert(
                    display_name, f"P3 | CAM{_camera_key(camera_id)} | PERSON_DETECTED"
                )
                alert_sent = True

        # Fire/smoke alerts — high priority (P0)
        if is_fire:
            _fire_alert_key = f"fire:{_camera_key(camera_id)}:{label}"
            if _should_emit_known_detect(_fire_alert_key, ts):
                _fire_conf = det.get("conf", 0)
                send_alert(
                    "FIRE_ALERT",
                    f"P0 | CAM{_camera_key(camera_id)} | {label.upper()} DETECTED | conf={_fire_conf:.0%}",
                )
                alert_sent = True

        if PROCESS_FRAME_DEBUG:
            print(f"  Alert sent: {alert_sent}")

        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)

        alert_entity_key = work_key or f"pid:{pid}"
        with roi_state_lock:
            is_in_roi = (
                alert_entity_key in roi_state
                and "WEBROI" in roi_state[alert_entity_key]
            )

        in_roi_now = False
        if roi_box and is_person:
            wx1, wy1, wx2, wy2 = roi_box
            x_overlap = max(0, min(x2, wx2) - max(x1, wx1))
            y_overlap = max(0, min(y2, wy2) - max(y1, wy1))
            in_roi_now = x_overlap > 0 and y_overlap > 0

        roi_required = bool(WORK_TIMER_REQUIRE_ROI)
        roi_enabled_now = bool(roi_box)
        if roi_required and not roi_enabled_now:
            roi_required = False

        work_active = bool(is_person) and (not roi_required or is_in_roi or in_roi_now)
        timer_key = work_key if (is_person and work_key is not None) else str(pid)
        work_seconds = _update_work_timer(timer_key, ts, work_active)
        work_timer_txt = _format_timer(work_seconds)

        color, draw_label = _get_semantic_color_and_label(det, is_in_roi, work_seconds)

        cross_tag = (
            _get_cross_overlay(camera_id, alert_entity_key, ts) if is_person else None
        )
        if cross_tag:
            draw_label = f"{draw_label} [{cross_tag}]"
            flash_on = (CROSS_OVERLAY_FLASH_HZ <= 0.0) or (
                int(ts * CROSS_OVERLAY_FLASH_HZ) % 2 == 0
            )
            color = (0, 0, 255) if flash_on else (0, 180, 255)

        if WORK_TIMER_ENABLE and is_person:
            draw_label = f"{draw_label} {work_timer_txt}".strip()

        thickness = (
            3
            if cross_tag
            and (
                (CROSS_OVERLAY_FLASH_HZ <= 0.0)
                or (int(ts * CROSS_OVERLAY_FLASH_HZ) % 2 == 0)
            )
            else 2
        )
        try:
            _draw_det_bbox(
                frame, x1, y1, x2, y2, draw_label, color, box_thickness=thickness
            )
        except Exception as e:
            print(f"[DRAW] Failed to draw bounding box: {e}")

        if PROCESS_FRAME_DEBUG:
            print(f"  Center: ({cx},{cy})")

        if roi_box and is_person:
            _handle_roi_events(
                pid,
                x1,
                y1,
                x2,
                y2,
                roi_box,
                display_name,
                camera_id=camera_id,
                stable_key=work_key,
            )

        det_items.append(
            {
                "pid": pid,
                "box": (x1, y1, x2, y2),
                "label": label,
                "cls_id": cls_id,
                "name": name,
                "display_name": display_name,
                "center": (cx, cy),
                "is_person": is_person,
                "is_vehicle": is_vehicle,
                "is_animal": is_animal,
                "is_plate": is_plate,
                "is_fire": is_fire,
                "is_face": is_face,
                "source": det_source,
                "work_seconds": work_seconds,
                "work_key": work_key,

            }
        )

    if pid_tracker and active_track_ids:
        with pid_tracker_op_lock:
            pid_tracker.sweep_inactive(active_track_ids)

    t = log_step("draw", t)
    t_draw = time.perf_counter()
    try:
        last_active_pids = set(active_ids)
        last_active_alert_keys = set(active_alert_keys)
    except Exception:
        pass

    try:
        cs["draw_dets"] = [
            {
                "pid": d.get("pid"),
                "box": d.get("box"),
                "name": d.get("name", "Unknown"),
                "display_name": d.get("display_name", d.get("name", "Unknown")),
                "is_person": d.get("is_person"),
                "work_seconds": d.get("work_seconds", 0.0),
                "work_key": d.get("work_key"),

            }
            for d in det_items
        ]
        cs["draw_time"] = now
    except Exception:
        pass

    try:
        evaluate_camera_rules(camera_id, frame.shape, det_items, ts)
    except Exception as e:
        if PROCESS_FRAME_DEBUG:
            print(f"[RULES] Evaluation failed: {e}")

    try:
        _emit_presence_alert(camera_id, det_items, ts)
    except Exception as e:
        if PROCESS_FRAME_DEBUG:
            print(f"[ALERTS] Presence emit failed: {e}")

    try:
        process_frame.last_processed = frame
        cs["yolo_frame"] = frame
    except Exception:
        pass
    if PERF_STATS:
        try:
            total_ms = (t_draw - t0) * 1000.0
            resize_ms = (t_resize - t0) * 1000.0
            yolo_ms = (t_yolo - t_resize) * 1000.0
            draw_ms = max(0.0, (t_draw - t_yolo) * 1000.0 - face_time_total_ms - track_ms_this)
            with perf_lock:
                perf_counters["frames"] += 1
                perf_counters["resize_ms"] += resize_ms
                perf_counters["yolo_ms"] += yolo_ms
                perf_counters["track_ms"] += track_ms_this
                perf_counters["faceid_ms"] += face_time_total_ms
                perf_counters["draw_ms"] += draw_ms
                perf_counters["total_ms"] += total_ms
        except Exception:
            pass
    if EVENT_CLIP_ENABLE:
        try:
            # Offload event clip encoding to a background thread so JPEG encode
            # does not block the processing thread and cause frame drops.
            import concurrent.futures as _cf

            _clip_pool = getattr(_event_clip_on_frame, "_pool", None)
            if _clip_pool is None:
                _clip_pool = _cf.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="clip"
                )
                _event_clip_on_frame._pool = _clip_pool
            _clip_pool.submit(_event_clip_on_frame, camera_id, frame.copy(), time.time())
        except Exception:
            pass
    return frame


async def process_alert_queue():
    """Process alerts from the queue in the main event loop"""
    logger.info("Alert queue processor started")
    try:
        while True:
            await asyncio.sleep(0.1)
            if not alert_queue.empty():
                item = alert_queue.get()
                if isinstance(item, dict):
                    payload_obj = dict(item)
                    person = payload_obj.get("person", "SYSTEM")
                    event = payload_obj.get("event", "")
                    payload_obj.setdefault(
                        "timestamp", time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                else:
                    try:
                        person, event = item
                    except Exception:
                        person, event = "SYSTEM", str(item)
                    payload_obj = {
                        "person": person,
                        "event": event,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }

                payload = json.dumps(payload_obj)
                logger.info(f"📤 Sending queued alert: {person} - {event}")
                success_count = broadcast_payload(payload)
                logger.info(f"   Result: {success_count} alert(s) sent")
                alert_queue.task_done()

    except asyncio.CancelledError:
        logger.info("Alert queue processor cancelled")
    except Exception as e:
        logger.error(f"Alert queue processor error: {e}")


async def persist_db_queue():
    """Persist alerts and recording segments to PostgreSQL."""
    logger.info("DB persist queue processor started")
    try:
        while True:
            await asyncio.sleep(0.1)
            while not db_persist_queue.empty():
                job = db_persist_queue.get()
                try:
                    if not isinstance(job, dict):
                        continue
                    job_type = job.get("type")
                    if job_type == "alert" and db_insert_alert:
                        client_id = job.get("client_id")
                        camera_id = job.get("camera_id")
                        if client_id is None and camera_id is not None and db_get_camera:
                            try:
                                cam_row = await db_get_camera(int(camera_id))
                                if cam_row:
                                    client_id = cam_row.get("client_id")
                            except Exception:
                                pass
                        await db_insert_alert(
                            client_id,
                            camera_id,
                            job.get("person", "SYSTEM"),
                            job.get("event", ""),
                            job.get("priority"),
                            job.get("clip_url"),
                            job.get("meta"),
                        )
                    elif job_type == "segment" and db_insert_recording_segment:
                        await db_insert_recording_segment(
                            job.get("camera_id"),
                            job.get("path"),
                            job.get("start_ts"),
                            job.get("end_ts"),
                            job.get("size_bytes"),
                        )
                except Exception as e:
                    logger.warning(f"DB persist job failed: {e}")
                finally:
                    db_persist_queue.task_done()
    except asyncio.CancelledError:
        logger.info("DB persist queue processor cancelled")
    except Exception as e:
        logger.error(f"DB persist queue processor error: {e}")

async def processing_loop(latest_holder, stop_event):
    """Legacy stub — kept for backward-compat import but never called."""
    pass


# --------------------------------------------------
# OUTGOING PROCESSED TRACK (optimized)
# --------------------------------------------------


class SharedServerCamera:
    """Shared server camera capture + processing loop.

    Source 'cctv' uses RTSP only. Source 'device' uses local indices only.
    """

    def __init__(self, camera_id: int | None = None, process: bool = True):
        self._lock = threading.Lock()
        self._clients = 0
        self._thread = None
        self._stop_evt = threading.Event()
        self._cap = None
        self._latest = np.zeros(
            (SERVER_CAMERA_HEIGHT, SERVER_CAMERA_WIDTH, 3), np.uint8
        )
        self._camera_id = camera_id
        self._rtsp_url = _get_rtsp_url(camera_id)
        self._last_open_fail = 0.0
        self._process = bool(process)
        use_pyav_env = os.getenv("RTSP_USE_PYAV", "0").strip() == "1"
        pyav_unsafe_ok = os.getenv("PYAV_UNSAFE_OK", "0").strip() == "1"
        # Guard against PyAV-related segfaults unless explicitly allowed.
        self._use_pyav = bool(use_pyav_env and pyav_unsafe_ok)
        self._av_container = None
        self._av_stream = None
        self._av_frames = None
        # Latest raw frame deposited by the capture thread for the processing
        # thread to consume.  Separating capture from inference means RTSP
        # reads are never stalled waiting for YOLO/face detection to finish.
        self._raw_frame = None
        self._raw_lock = threading.Lock()
        self._reconnect_count = 0

    def add_client(self):
        with self._lock:
            self._clients += 1
            if self._thread is None or not self._thread.is_alive():
                self._stop_evt.clear()
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()

    def remove_client(self):
        with self._lock:
            self._clients = max(0, self._clients - 1)
            should_stop = self._clients == 0
        if should_stop:
            self._stop_evt.set()
            # Best-effort join. Do not release capture concurrently while
            # _run() may still be inside native OpenCV/FFmpeg read calls.
            t = self._thread
            try:
                if t is not None:
                    t.join(timeout=3.0)
            except Exception:
                pass
            if t is not None and t.is_alive():
                logger.warning(
                    "⚠️ SharedServerCamera thread still alive after stop request; "
                    "deferring capture release to avoid native race"
                )
                return
            self._release_cap()
            with self._lock:
                self._thread = None

    def _release_cap(self):
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        self._cap = None
        try:
            if self._av_container is not None:
                self._av_container.close()
        except Exception:
            pass
        self._av_container = None
        self._av_stream = None
        self._av_frames = None
        self._opened_index = None

    def _make_cap(self):
        """Open the video source and return a ready cv2.VideoCapture, or None.

        IMPORTANT: The returned cap is owned by the CALLER.  This method never
        stores to self._cap so there is no shared mutable state to race on.
        """

        def _open_rtsp(url: str):
            cap = cv2.VideoCapture()
            try:
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(RTSP_OPEN_TIMEOUT_MS))
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, float(RTSP_READ_TIMEOUT_MS))
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FPS, 30)
            except Exception:
                pass
            try:
                cap.open(url, cv2.CAP_FFMPEG)
            except Exception:
                try:
                    cap.release()
                except Exception:
                    pass
                return None
            return cap if cap.isOpened() else None

        if not self._rtsp_url:
            return None
        cap = _open_rtsp(self._rtsp_url)
        if cap is None:
            return None
        ok, _ = cap.read()
        if ok:
            for _ in range(3):
                cap.grab()
            logger.info(f"✅ RTSP opened (camera {self._camera_id})")
            return cap
        try:
            cap.release()
        except Exception:
            pass
        return None

    def _capture_worker(self, cap_stop: threading.Event) -> None:
        """Dedicated capture thread.

        Owns its VideoCapture as a LOCAL variable — never stores to self._cap.
        This eliminates the segfault where _release_cap() called from
        remove_client() on the main thread would call cap.release() while
        this thread was blocked inside cap.read().
        """
        cap = None
        last_open_fail = 0.0
        last_ok = time.time()
        had_cap = False
        try:
            while not cap_stop.is_set() and not self._stop_evt.is_set():
                # ---- ensure open ----
                if cap is None:
                    if time.time() - last_open_fail > max(RTSP_RETRY_DELAY_SEC, 1.0):
                        cap = self._make_cap()
                        if cap is None:
                            last_open_fail = time.time()
                            update_camera_health(self._camera_id, last_frame_ts=0.0)
                        elif had_cap:
                            self._reconnect_count += 1
                            update_camera_health(
                                self._camera_id,
                                reconnect_count=self._reconnect_count,
                            )
                        had_cap = cap is not None
                    time.sleep(0.05)  # always yield after an open attempt
                    continue

                # ---- read one frame ----
                try:
                    ok, frame = cap.read()
                except Exception:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                    had_cap = False
                    last_open_fail = time.time()
                    continue

                if ok and frame is not None:
                    last_ok = time.time()
                    update_camera_health(
                        self._camera_id, last_frame_ts=last_ok
                    )
                    if CONTINUOUS_RECORDING_ENABLE and self._camera_id is not None:
                        try:
                            writer = _get_segment_writer(self._camera_id)
                            if writer is not None:
                                writer.write(frame, last_ok)
                        except Exception:
                            pass
                    with self._raw_lock:
                        self._raw_frame = frame
                else:
                    if time.time() - last_ok > RTSP_RETRY_DELAY_SEC:
                        try:
                            cap.release()
                        except Exception:
                            pass
                        cap = None
                        had_cap = False
                        last_open_fail = time.time()
                    else:
                        time.sleep(0.005)
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    def _run(self):
        # Target processing rate — capped by PROCESSING_FPS env var.
        target_fps = int(SERVER_CAMERA_FPS) if self._process else int(GRID_CAMERA_FPS)
        processing_fps = max(1, min(target_fps, int(PROCESSING_FPS)))
        target_dt = 1.0 / processing_fps
        out_w = FOCUS_CAMERA_WIDTH if self._process else GRID_CAMERA_WIDTH
        out_h = FOCUS_CAMERA_HEIGHT if self._process else GRID_CAMERA_HEIGHT

        # Start the dedicated capture thread so RTSP reads are never blocked
        # by YOLO or face-detection inference.  This is the primary fix for
        # frame drops: capture runs at camera speed, processing runs as fast
        # as the GPU allows, and _latest is always the most recent output.
        _cap_stop = threading.Event()
        cap_thread = threading.Thread(
            target=self._capture_worker,
            args=(_cap_stop,),
            daemon=True,
            name=f"cam{self._camera_id}-capture",
        )
        cap_thread.start()

        # Use monotonic clock with drift correction for jitter-free pacing.
        next_send_t = monotonic()

        try:
            while not self._stop_evt.is_set():
                now_m = monotonic()
                wait = next_send_t - now_m
                if wait > 0:
                    time.sleep(wait)
                # Advance to next slot; if we fell behind, skip to now
                # to avoid a burst of back-to-back frames.
                next_send_t = max(next_send_t + target_dt, monotonic())

                # Read the freshest raw frame from the capture thread.
                frame = None
                with self._raw_lock:
                    if self._raw_frame is not None:
                        frame = self._raw_frame
                        # Leave _raw_frame in place; capture thread overwrites
                        # it with the next camera frame automatically.

                if frame is None:
                    # Camera not ready yet — keep _latest unchanged.
                    continue

                if self._process:
                    try:
                        processed = process_frame(
                            frame,
                            yolo_input_resolution=FOCUS_YOLO_INPUT_RESOLUTION,
                            no_pre_resize=True,
                            camera_id=self._camera_id,
                        )
                    except Exception:
                        processed = frame
                else:
                    processed = frame

                try:
                    # Use high-quality interpolation for sharp output.
                    h_in, w_in = processed.shape[:2]
                    if w_in > out_w or h_in > out_h:
                        interp = cv2.INTER_AREA      # best for downscaling
                    else:
                        interp = cv2.INTER_LANCZOS4   # best for upscaling
                    processed = cv2.resize(processed, (out_w, out_h), interpolation=interp)
                except Exception:
                    pass

                with self._lock:
                    self._latest = processed
        finally:
            _cap_stop.set()
            cap_thread.join(timeout=2.0)
            self._release_cap()
            with self._lock:
                self._thread = None

    def get_latest(self):
        with self._lock:
            return self._latest


_shared_cctv_lock = threading.Lock()
_shared_server_cameras = {}
_background_analytics_cameras = []
_background_analytics_lock = threading.Lock()


def _get_shared_cctv_camera(
    camera_id: int | None, process: bool = True
) -> SharedServerCamera:
    try:
        cam_id = int(camera_id) if camera_id is not None else 1
    except Exception:
        cam_id = 1
    # Always use subtype=0 (main HD stream) for maximum quality on all views.
    # subtype=1 (sub-stream) was previously used for the grid but produced
    # a low-resolution / low-bitrate feed.  The main stream is used for both
    # focus (analytics) and grid (preview) views.
    rtsp_url = _get_rtsp_url(cam_id, subtype=0)
    key = (cam_id, bool(process))
    with _shared_cctv_lock:
        cam = _shared_server_cameras.get(key)
        if cam is None:
            cam = SharedServerCamera(camera_id=cam_id, process=process)
            _shared_server_cameras[key] = cam
        return cam


def _start_background_cctv_analytics() -> None:
    if not ANALYTICS_ALL_CCTV:
        logger.info("Background CCTV analytics disabled via ANALYTICS_ALL_CCTV=0")
        return

    cams = []
    for cid in ANALYTICS_CAMERA_IDS:
        if _get_rtsp_url(cid) is not None:
            cams.append(int(cid))

    if not cams:
        configured = [int(k) for k, v in RTSP_URLS.items() if v]
        cams = configured or ([1] if RTSP_URL else [])

    started = []
    with _background_analytics_lock:
        if _background_analytics_cameras:
            return
        for cid in cams:
            try:
                cam = _get_shared_cctv_camera(cid, process=True)
                cam.add_client()
                _background_analytics_cameras.append(cam)
                started.append(cid)
            except Exception as e:
                logger.warning(
                    f"Failed to start background analytics for camera {cid}: {e}"
                )

    if started:
        logger.info(f"✅ Background CCTV analytics enabled for cameras: {started}")
    else:
        logger.warning("⚠️ Background CCTV analytics did not start for any camera")


def _stop_background_cctv_analytics() -> None:
    with _background_analytics_lock:
        cams = list(_background_analytics_cameras)
        _background_analytics_cameras.clear()
    for cam in cams:
        try:
            cam.remove_client()
        except Exception:
            pass


# Standard RTP clock rate for jitter-free PTS spacing.
_VIDEO_CLOCK_RATE = 90000


class SharedServerCameraTrack(VideoStreamTrack):
    def __init__(
        self, fps=SERVER_CAMERA_FPS, camera_id: int | None = None, process: bool = True
    ):
        super().__init__()
        self.fps = int(fps)
        self.i = 0
        # Use the standard 90 kHz RTP clock for perfectly uniform PTS spacing.
        # Each frame advances by exactly (_VIDEO_CLOCK_RATE / fps) ticks,
        # which eliminates jitter regardless of when recv() is actually called.
        self.time_base = Fraction(1, _VIDEO_CLOCK_RATE)
        self._pts_step = _VIDEO_CLOCK_RATE // max(1, self.fps)
        self._closed = False
        self._camera_id = camera_id
        self._process = bool(process)
        self._shared_camera = _get_shared_cctv_camera(
            self._camera_id, process=self._process
        )
        self._shared_camera.add_client()
        # Tracks the ideal next-send wall-clock time so we don't drift when
        # focus/grid track.
        self._next_send_t = monotonic()

    async def recv(self):
        # Pace output at self.fps without accumulating drift.
        # If the event loop was late, skip the sleep and catch up immediately
        # rather than sleeping for a full extra interval.
        now = monotonic()
        wait = self._next_send_t - now
        if wait > 0:
            await asyncio.sleep(wait)
        self._next_send_t = max(
            self._next_send_t + (1.0 / max(1, self.fps)), monotonic()
        )

        frame = self._shared_camera.get_latest()
        vf = VideoFrame.from_ndarray(frame, format="bgr24")
        self.i += 1
        # Clock-aligned PTS: perfectly uniform spacing = no jitter.
        vf.pts = self.i * self._pts_step
        vf.time_base = self.time_base
        return vf

    def stop(self):
        if not self._closed:
            self._closed = True
            try:
                self._shared_camera.remove_client()
            except Exception:
                pass
        return super().stop()


# --------------------------------------------------
# HTTP ROUTES
# --------------------------------------------------
REACT_DIST = REPO_ROOT / "frontend" / "superadmin-react" / "dist"


async def _serve_react_spa(request):
    """Serve the React SPA.  First check if the request matches a real file
    inside the Vite dist directory (JS/CSS bundles, images, etc.).  If not,
    serve the SPA index.html so React Router handles the path client-side."""
    tail = (request.match_info.get("tail") or "").lstrip("/")
    if tail and REACT_DIST.exists():
        try:
            candidate = (REACT_DIST / tail).resolve()
            if (
                str(candidate).startswith(str(REACT_DIST.resolve()))
                and candidate.exists()
                and candidate.is_file()
            ):
                return web.FileResponse(candidate)
        except Exception:
            pass

    # Fallback to SPA entry for React Router paths.
    index_file = REACT_DIST / "index.html"
    if index_file.exists():
        return web.FileResponse(index_file)

    # Helpful fallback if build not generated yet.
    return web.Response(
        status=503,
        text=(
            "React build not found. "
            "Run 'npm install && npm run build' in frontend/superadmin-react, "
            "then reload."
        ),
    )


async def index(request):
    """Root '/' — serve the React Landing page (signup/login)."""
    return await _serve_react_spa(request)


# Keep as alias for backward compatibility with existing route registrations.
super_admin_dashboard_page = _serve_react_spa


# --------------------------------------------------
# MEMBER MANAGEMENT API (Admin only)
# --------------------------------------------------
async def list_members(request):
    user = request.get("user") or {}
    require_role(user, ["admin"])

    client_id = user.get("client_id")
    if client_id is None:
        return web.json_response({"error": "client_id missing"}, status=400)

    users = await db_list_users_by_client(client_id)
    # Filter to only return members
    members = [u for u in users if u["role"] == "member"]
    return web.json_response({"members": members})


async def update_member_permissions(request):
    user = request.get("user") or {}
    require_role(user, ["admin"])

    uid = int(request.match_info.get("id"))
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "invalid JSON"}, status=400)

    permissions = data.get("permissions")
    if not isinstance(permissions, list):
        return web.json_response({"error": "permissions must be a list"}, status=400)

    # Ensure the user being updated belongs to the same client
    target_user = await db_get_user_by_id(uid)
    if not target_user or target_user["client_id"] != user.get("client_id"):
        return web.json_response({"error": "access denied"}, status=403)

    if target_user["role"] != "member":
        return web.json_response({"error": "only members can be managed"}, status=400)

    await db_update_user_permissions(uid, permissions)
    return web.json_response({"status": "ok", "permissions": permissions})


async def api_list_alerts(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if not db_list_alerts:
        return web.json_response({"alerts": []})
    client_id = user.get("client_id")
    try:
        limit = int(request.query.get("limit", "50"))
    except Exception:
        limit = 50
    camera_q = request.query.get("camera_id")
    camera_id = int(camera_q) if camera_q not in (None, "") else None
    alerts = await db_list_alerts(
        client_id=client_id, camera_id=camera_id, limit=limit
    )
    return web.json_response({"alerts": alerts})


async def api_list_recordings(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if not db_list_recording_segments:
        return web.json_response({"recordings": []})
    try:
        limit = int(request.query.get("limit", "50"))
    except Exception:
        limit = 50
    camera_q = request.query.get("camera_id")
    camera_id = int(camera_q) if camera_q not in (None, "") else None
    segments = await db_list_recording_segments(camera_id=camera_id, limit=limit)
    for seg in segments:
        path = str(seg.get("path") or "").lstrip("/")
        seg["url"] = f"/recordings/{path}" if path else ""
    return web.json_response({"recordings": segments})


async def api_cameras_health(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    live = get_camera_health_snapshot()
    client_id = user.get("client_id")
    cameras = []
    if client_id is not None and db_list_cameras_for_client:
        try:
            cameras = await db_list_cameras_for_client(client_id)
        except Exception:
            cameras = []
    out = []
    for cam in cameras:
        cid = cam.get("id")
        h = live.get(
            cid,
            {
                "camera_id": cid,
                "status": "offline",
                "last_frame_ts": 0.0,
                "reconnect_count": 0,
            },
        )
        out.append({**cam, **h})
    return web.json_response({"cameras": out})


# SAVE WEB ROI
async def save_roi(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "rules", "manage"):
        return web.Response(status=403)
    global web_roi

    try:
        data = await request.json()
    except:
        return web.json_response(
            {"status": "error", "reason": "invalid json"}, status=400
        )

    for k in ("x", "y", "w", "h"):
        if k not in data:
            return web.json_response(
                {"status": "error", "reason": f"missing {k}"}, status=400
            )
        data[k] = max(0.0, min(1.0, float(data[k])))
    data["enabled"] = bool(data.get("enabled", True))

    # UPDATE GLOBAL VARIABLE
    web_roi = data
    # Reset ROI state so existing people inside will trigger ENTERED on next frame
    global roi_updated_at
    with roi_state_lock:
        roi_state.clear()
    roi_updated_at = time.time()

    # Save to file
    json.dump(data, open(web_roi_file, "w"))

    logger.info(f"✅ ROI UPDATED: {web_roi}")

    return web.json_response({"status": "saved", "roi": data})


# CAMERA RULES API
async def rules_schema(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "rules", "view"):
        return web.Response(status=403)
    return web.json_response(RULES_SCHEMA)


async def get_rules(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "rules", "view"):
        return web.Response(status=403)
    camera_id = request.query.get("camera_id") or request.query.get("cameraId")
    if camera_id is None:
        with RULES_LOCK:
            data = _load_rules_file()
        return web.json_response(data)
    parsed_id = _parse_camera_id_value(camera_id)
    try:
        if (
            AUTH_READY
            and user_can_access_camera
            and not await user_can_access_camera(request.get("user") or {}, parsed_id)
        ):
            return web.Response(status=403)
    except Exception:
        return web.Response(status=403)
    rules = _get_camera_rules(parsed_id)
    return web.json_response({"camera_id": _camera_key(parsed_id), "rules": rules})


async def save_rules(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "rules", "manage"):
        return web.Response(status=403)
    try:
        data = await request.json()
    except Exception:
        return web.json_response(
            {"status": "error", "reason": "invalid json"}, status=400
        )

    camera_id = (
        data.get("camera_id")
        or data.get("cameraId")
        or request.query.get("camera_id")
        or request.query.get("cameraId")
    )
    parsed_id = _parse_camera_id_value(camera_id)
    if camera_id is None:
        return web.json_response(
            {"status": "error", "reason": "camera_id required"}, status=400
        )

    try:
        if (
            AUTH_READY
            and user_can_access_camera
            and not await user_can_access_camera(request.get("user") or {}, parsed_id)
        ):
            return web.Response(status=403)
    except Exception:
        return web.Response(status=403)

    rules_payload = (
        data.get("rules") if isinstance(data, dict) and "rules" in data else data
    )
    normalized = _set_camera_rules(parsed_id, rules_payload)
    return web.json_response(
        {"status": "saved", "camera_id": _camera_key(parsed_id), "rules": normalized}
    )


# FACE ENROLL ENDPOINT
async def face_enroll(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "faces", "enroll"):
        return web.Response(status=403)
    global ENROLLMENT_ACTIVE
    data = await request.json()
    raw_name = data.get("name")
    if not raw_name:
        return web.json_response({"error": "name required"}, status=400)

    name = normalize_name(raw_name)

    if not name:
        return web.json_response({"error": "name required"}, status=400)

    ENROLLMENT_ACTIVE = True
    try:
        send_enrollment_alert(f"Starting face enrollment for {name} - look at camera")

        # capture frames (2 seconds, ~20 frames) using the device camera
        cap = cv2.VideoCapture(SERVER_CAMERA_INDEX)
        frames = []
        start = time.time()

        while time.time() - start < 2:  # Reduced to 2 seconds
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
            await asyncio.sleep(0.1)  # ~10 fps

        cap.release()

        send_enrollment_alert(f"Captured {len(frames)} frames - processing...")

        success, message = enroll_face(name, frames)
        if success and faceid:
            _reload_face_db_and_track("face_enroll")
            send_enrollment_alert(f"Database reloaded - {name} ready for recognition")

        return web.json_response(
            {"status": "ok" if success else "failed", "message": message}
        )
    finally:
        ENROLLMENT_ACTIVE = False


# BROWSER WEBCAM ENROLLMENT ENDPOINT
async def face_enroll_frames(request):
    """
    POST /api/face/enroll-frames

    Accepts base64-encoded JPEG frames captured by the admin dashboard webcam,
    runs liveness detection, extracts ArcFace embeddings, and saves to the
    client-scoped face database.

    Body: {"name": str, "frames": [base64_jpeg, ...]}
    Returns: {"status": "ok"|"failed", "message": str, "liveness_score": float, "frames_used": int}
    """
    import base64

    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(user, "faces", "enroll"):
        return web.Response(status=403)

    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"[ENROLL-FRAMES] JSON decode error: {e}")
        return web.json_response({"error": "invalid JSON", "details": str(e)}, status=400)

    raw_name = (body.get("name") or "").strip()
    if not raw_name:
        return web.json_response({"error": "name required"}, status=400)

    name = normalize_name(raw_name)
    if not name:
        return web.json_response({"error": "invalid name"}, status=400)

    b64_frames = body.get("frames") or []
    if not b64_frames:
        return web.json_response({"error": "frames required"}, status=400)

    client_id = user.get("client_id")

    # Decode base64 frames to BGR numpy arrays
    frames = []
    for b64 in b64_frames:
        try:
            # Strip data URI prefix if present
            if isinstance(b64, str) and "," in b64:
                b64 = b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(b64)
            arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                frames.append(img)
        except Exception as e:
            print(f"[ENROLL-FRAMES] Frame decode error: {e}")
            continue

    if not frames:
        return web.json_response({"error": "no valid frames decoded"}, status=400)

    # Detect faces in each frame for liveness check
    face_data_list = []
    for img in frames:
        try:
            if face_app:
                detected = face_app.get(img)
                if detected:
                    best = max(
                        detected,
                        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                    )
                    face_data_list.append(
                        {"bbox": best.bbox, "pose": getattr(best, "pose", None)}
                    )
                else:
                    face_data_list.append({"bbox": [0, 0, img.shape[1], img.shape[0]]})
            else:
                face_data_list.append({"bbox": [0, 0, img.shape[1], img.shape[0]]})
        except Exception:
            face_data_list.append({"bbox": [0, 0, img.shape[1], img.shape[0]]})

    # Liveness check
    liveness_score = 1.0
    if LIVENESS_ENABLED and face_data_list:
        is_live, liveness_score, liveness_details = check_frames_liveness(
            frames, face_data_list
        )
        print(
            f"[ENROLL-FRAMES] Liveness: {is_live} score={liveness_score:.3f} details={liveness_details}"
        )
        if not is_live:
            return web.json_response(
                {
                    "status": "failed",
                    "error": "liveness_failed",
                    "message": f"Liveness check failed (score={liveness_score:.2f}). Please use a live camera.",
                    "liveness_score": round(liveness_score, 3),
                },
                status=400,
            )

    # Enroll into client-scoped DB
    success, message = enroll_face(name, frames, client_id=client_id)
    if success and faceid:
        _reload_face_db_and_track("face_enroll_frames")
        send_enrollment_alert(f"[API] {name} enrolled via dashboard")

    return web.json_response(
        {
            "status": "ok" if success else "failed",
            "message": message,
            "liveness_score": round(liveness_score, 3),
            "frames_used": len(frames),
        }
    )


# LIST FACES ENDPOINT
async def face_list(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "faces", "view"):
        return web.Response(status=403)
    client_id = (request.get("user") or {}).get("client_id")
    db_path = _face_db_path(client_id)
    if not db_path.exists() and not FACE_DB.exists():
        return web.json_response({"faces": []})
    # Try client-scoped first, fallback to global legacy
    path = db_path if db_path.exists() else FACE_DB
    try:
        data = np.load(path, allow_pickle=True)
        labels = data["labels"]
        unique_faces = sorted(set(str(l) for l in labels))
    except Exception:
        unique_faces = []
    return web.json_response({"faces": unique_faces})


# RECOGNITION LOGS ENDPOINT (in-memory ring buffer)
async def recognition_logs_handler(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])

    # Build enrolled faces database from faces_raw subdirectories
    enrolled = []
    try:
        for entry in sorted(RAW_DIR.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            # Count image files
            images = [
                f
                for f in entry.iterdir()
                if f.is_file()
                and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
            ]
            if not images:
                # Check one level deeper (some have nested folders)
                for sub in entry.iterdir():
                    if sub.is_dir():
                        images += [
                            f
                            for f in sub.iterdir()
                            if f.is_file()
                            and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                        ]
            # Enrollment date = directory modification time
            import datetime

            mtime = entry.stat().st_mtime
            enrolled_at = datetime.datetime.fromtimestamp(mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            enrolled.append(
                {
                    "name": name,
                    "image_count": len(images),
                    "enrolled_at": enrolled_at,
                }
            )
    except Exception as e:
        logger.warning("Failed reading faces_raw: %s", e)

    return web.json_response({"enrolled": enrolled})


# DELETE FACE ENDPOINT
async def face_delete(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "faces", "delete"):
        return web.Response(status=403)
    payload = await request.json()
    name = payload.get("name")
    if not name:
        return web.json_response({"error": "name required"}, status=400)

    client_id = (request.get("user") or {}).get("client_id")
    db_path = _face_db_path(client_id)
    if not db_path.exists():
        db_path = FACE_DB  # fallback to global
    if not db_path.exists():
        return web.json_response({"error": "database not found"}, status=404)

    with face_db_lock:
        data = np.load(db_path, allow_pickle=True)
        embeddings = data["embeddings"]
        labels = data["labels"]
        mask = np.array([str(l) != str(name) for l in labels])
        new_embeddings = embeddings[mask]
        new_labels = labels[mask]
        if new_labels.shape[0] == labels.shape[0]:
            return web.json_response({"error": f"face '{name}' not found"}, status=404)
        np.savez(db_path, embeddings=new_embeddings, labels=new_labels)

    if faceid:
        _reload_face_db_and_track("face_delete")

    # Remove raw images for this client+person
    import shutil

    for raw_candidate in [
        RAW_DIR / str(client_id) / name if client_id else None,
        RAW_DIR / name,
    ]:
        if raw_candidate and raw_candidate.exists():
            shutil.rmtree(raw_candidate, ignore_errors=True)

    send_alert("SYSTEM", f"Face '{name}' deleted (client={client_id})")
    return web.json_response({"status": "deleted", "name": name})


# FACE RECOGNIZE ENDPOINT (for Corporate Access page)
async def face_recognize(request):
    """
    POST /api/face/recognize

    Accepts a single base64-encoded JPEG frame captured by the browser webcam,
    runs InsightFace face detection, and matches against enrolled face embeddings.

    Body: {"frame": "data:image/jpeg;base64,..."}
    Returns: {"status": "ok", "recognized": bool, "name": str, "confidence": float}
    """
    import base64

    user = request.get("user") or {}
    require_role(user, ["admin", "member"])

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)

    b64_frame = body.get("frame", "")
    if not b64_frame:
        return web.json_response({"error": "frame required"}, status=400)

    # Strip data URI prefix if present
    if isinstance(b64_frame, str) and "," in b64_frame:
        b64_frame = b64_frame.split(",", 1)[1]

    try:
        raw_bytes = base64.b64decode(b64_frame)
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        return web.json_response({"error": f"frame decode failed: {e}"}, status=400)

    if img is None:
        return web.json_response({"error": "invalid image data"}, status=400)

    # Detect faces using InsightFace
    if not face_app:
        return web.json_response(
            {"error": "face detection model not loaded"}, status=503
        )

    try:
        detected = face_app.get(img)
    except Exception as e:
        return web.json_response({"error": f"detection failed: {e}"}, status=500)

    if not detected:
        return web.json_response(
            {"status": "ok", "recognized": False, "name": None, "confidence": 0.0}
        )

    # Pick the largest face
    best_face = max(
        detected,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
    )
    box = tuple(int(v) for v in best_face.bbox)

    # Recognize using FaceIDManager
    if not faceid:
        return web.json_response(
            {"error": "face recognition model not loaded"}, status=503
        )

    try:
        results = faceid.recognize_batch(img, [box])
        name, score, _ = results[0] if results else ("Unknown", 0.0, None)
    except Exception as e:
        logger.warning("[RECOGNIZE] Error: %s", e)
        return web.json_response({"error": f"recognition failed: {e}"}, status=500)

    recognized = name != "Unknown" and score >= faceid.threshold
    return web.json_response(
        {
            "status": "ok",
            "recognized": recognized,
            "name": name if recognized else None,
            "confidence": round(float(score), 3),
        }
    )


# SUPER ADMIN: LIST CLIENTS METADATA
async def list_clients(request):
    user = request.get("user") or {}
    require_role(user, ["super_admin"])
    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id,
                   name,
                   email,
                   phone,
                   customer_type,
                   subscription_plan,
                   billing_cycle,
                   next_billing_date,
                   is_active,
                   created_at
            FROM clients
            ORDER BY created_at DESC
            """
        )

    def _serialize_value(val):
        try:
            import datetime

            if isinstance(val, (datetime.date, datetime.datetime)):
                return val.isoformat()
        except Exception:
            pass
        return val

    def _serialize_row(row):
        data = dict(row)
        return {k: _serialize_value(v) for k, v in data.items()}

    return web.json_response([_serialize_row(r) for r in rows])


# --------------------------------------------------
# AUTH/RBAC CAMERA ENDPOINTS (OPTIONAL)
# --------------------------------------------------
async def get_camera(request):
    if not AUTH_READY:
        return web.json_response({"error": "auth modules not available"}, status=503)

    user = request.get("user") or {}
    require_role(user, ["admin", "member"])

    try:
        camera_id = int(request.query["camera_id"])
    except Exception:
        return web.json_response({"error": "camera_id required"}, status=400)

    if can and not can(request.get("user") or {}, "cameras", "view"):
        return web.Response(status=403)
    try:
        if not await user_can_access_camera(request["user"], camera_id):
            return web.Response(status=403)
    except Exception:
        return web.Response(status=403)

    cam = await db_get_camera(camera_id)
    return web.json_response(cam)


async def get_me(request):
    if not AUTH_READY:
        return web.json_response({"error": "auth modules not available"}, status=503)
    user = request.get("user") or {}
    return web.json_response(
        {
            "user_id": user.get("user_id"),
            "role": user.get("role"),
            "client_id": user.get("client_id"),
            "permissions": user.get("permissions") or [],
        }
    )


# SUPER ADMIN: LIST CLIENTS METADATA
async def list_clients(request):
    user = request.get("user") or {}
    require_role(user, ["super_admin"])

    async with request.app["db"].acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id,
                   name,
                   email,
                   phone,
                   customer_type,
                   subscription_plan,
                   billing_cycle,
                   next_billing_date,
                   is_active,
                   created_at
            FROM clients
            ORDER BY created_at DESC
            """
        )

    def _serialize_value(val):
        try:
            import datetime

            if isinstance(val, (datetime.date, datetime.datetime)):
                return val.isoformat()
        except Exception:
            pass
        return val

    def _serialize_row(row):
        data = dict(row)
        return {k: _serialize_value(v) for k, v in data.items()}

    return web.json_response([_serialize_row(r) for r in rows])


# WEBSOCKET HANDLER
async def websocket_handler(request):
    user = request.get("user") or {}
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "alerts", "view"):
        return web.Response(status=403)
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async def _process_enrollment_session(ws_id):
        """Background task: collect good frames until quality target met."""
        target_embeddings = 6
        global ENROLLMENT_ACTIVE
        try:
            ENROLLMENT_ACTIVE = True
            while True:
                session = enroll_sessions.get(ws_id)
                if not session:
                    return
                target_met = len(session.get("good_frames", [])) >= target_embeddings
                if target_met:
                    break
                frames = session.get("frames", [])
                processed = session.setdefault("processed_frames", 0)
                good_frames = session.setdefault("good_frames", [])
                yaw_count = session.setdefault("yaw_count", {})
                while processed < len(frames) and len(good_frames) < target_embeddings:
                    frame = frames[processed]
                    processed += 1
                    session["processed_frames"] = processed
                    if not face_app:
                        continue
                    faces = face_app.get(frame)
                    if not faces:
                        send_session_guidance(session, "Move face into frame")
                        continue
                    face = faces[0]
                    h, w = frame.shape[:2]
                    face_w = face.bbox[2] - face.bbox[0]
                    face_h = face.bbox[3] - face.bbox[1]

                    face_area_ratio = (face_w * face_h) / (w * h) if w * h > 0 else 0

                    if face_area_ratio < 0.08:
                        send_session_guidance(session, "Move closer")
                        continue

                    if face_area_ratio > 0.35:
                        send_session_guidance(session, "Move slightly back")
                        continue
                    if cv2.Laplacian(frame, cv2.CV_64F).var() < 35:
                        send_session_guidance(session, "Hold still")
                        continue
                    yaw = face.pose[0]
                    yaw_bucket = int(yaw / 15) * 15
                    yaw_count[yaw_bucket] = yaw_count.get(yaw_bucket, 0) + 1
                    if yaw_count[yaw_bucket] > 3:
                        send_session_guidance(session, "Turn head slightly")
                    if len(good_frames) >= 6:
                        good_frames.append(frame)
                        count = len(good_frames)
                        send_enrollment_alert(
                            f"Good face captured ({count}/{target_embeddings})"
                        )
                        if count >= target_embeddings:
                            session["done"] = True
                            send_enrollment_alert("Enrollment complete")
                            break
                        continue
                    good_frames.append(frame)
                    count = len(good_frames)
                    send_enrollment_alert(
                        f"Good face captured ({count}/{target_embeddings})"
                    )
                    if count >= target_embeddings:
                        session["done"] = True
                        send_enrollment_alert("Enrollment complete")
                        break
                if len(good_frames) >= target_embeddings:
                    session["done"] = True
                    break
                await asyncio.sleep(0.25)
            session = enroll_sessions.pop(ws_id, None)
            if not session:
                return
            name = session.get("name")
            good_frames = session.get("good_frames", [])
            if not good_frames:
                send_enrollment_alert(
                    f"No valid faces captured for {name} - enrollment failed"
                )
                try:
                    aws = session.get("ws")
                    if aws and not aws.closed:
                        await aws.send_json(
                            {
                                "action": "enroll_face",
                                "status": "failed",
                                "error": "no_valid_faces",
                            }
                        )
                except Exception:
                    pass
                return
            success, message = enroll_face(name, good_frames)
            if success and faceid:
                faceid.load()
                send_enrollment_alert(
                    f"Database reloaded - {name} ready for recognition"
                )
            try:
                aws = session.get("ws")
                if aws and not aws.closed:
                    await aws.send_json(
                        {
                            "action": "enroll_face",
                            "status": "ok" if success else "failed",
                            **({"message": message} if success else {"error": message}),
                        }
                    )
            except Exception:
                pass
            if success:
                send_enrollment_alert("Enrollment complete. Face saved successfully.")
        except Exception as e:
            send_enrollment_alert(f"Enrollment background error: {e}")
        finally:
            ENROLLMENT_ACTIVE = False

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    action = data.get("action")

                    if action == "list_faces":
                        if (
                            AUTH_READY
                            and can
                            and not can(request.get("user") or {}, "faces", "view")
                        ):
                            await ws.send_json(
                                {"action": "list_faces", "error": "forbidden"}
                            )
                            continue
                        if not FACE_DB.exists():
                            faces = []
                        else:
                            with face_db_lock:
                                db_data = np.load(FACE_DB, allow_pickle=True)
                                labels = db_data["labels"]
                                faces = list(set(labels))
                        await ws.send_json({"action": "list_faces", "faces": faces})

                    elif action == "delete_face":
                        if (
                            AUTH_READY
                            and can
                            and not can(request.get("user") or {}, "faces", "delete")
                        ):
                            await ws.send_json(
                                {"action": "delete_face", "error": "forbidden"}
                            )
                            continue
                        name = data.get("name")
                        if not name:
                            await ws.send_json(
                                {"action": "delete_face", "error": "name required"}
                            )
                            continue

                        with face_db_lock:
                            if not FACE_DB.exists():
                                await ws.send_json(
                                    {
                                        "action": "delete_face",
                                        "error": "database not found",
                                    }
                                )
                                continue

                            db_data = np.load(FACE_DB, allow_pickle=True)
                            embeddings = db_data["embeddings"]
                            labels = db_data["labels"]

                            mask = labels != name
                            new_embeddings = embeddings[mask]
                            new_labels = labels[mask]

                            if len(new_labels) == len(labels):
                                await ws.send_json(
                                    {
                                        "action": "delete_face",
                                        "error": f"face '{name}' not found",
                                    }
                                )
                                continue

                            np.savez(
                                FACE_DB, embeddings=new_embeddings, labels=new_labels
                            )

                        if faceid:
                            faceid.load()

                        person_dir = RAW_DIR / name
                        if person_dir.exists():
                            import shutil

                            shutil.rmtree(person_dir)

                        send_alert("SYSTEM", f"Face '{name}' deleted from database")
                        await ws.send_json(
                            {"action": "delete_face", "status": "deleted"}
                        )

                    elif action == "enroll_face":
                        if (
                            AUTH_READY
                            and can
                            and not can(request.get("user") or {}, "faces", "enroll")
                        ):
                            await ws.send_json(
                                {"action": "enroll_face", "error": "forbidden"}
                            )
                            continue
                        raw_name = data.get("name")
                        if not raw_name:
                            await ws.send_json(
                                {"action": "enroll_face", "error": "name required"}
                            )
                            continue

                        name = normalize_name(raw_name)
                        if not name:
                            await ws.send_json(
                                {"action": "enroll_face", "error": "name required"}
                            )
                            continue

                        send_alert(
                            "SYSTEM",
                            f"Starting face enrollment for {name} - send frames now",
                        )
                        ws_id = id(ws)
                        enroll_sessions[ws_id] = {
                            "name": name,
                            "frames": [],
                            "ws": ws,
                            "processed_frames": 0,
                            "good_frames": [],
                            "done": False,
                        }
                        enroll_sessions[ws_id]["task"] = asyncio.create_task(
                            _process_enrollment_session(ws_id)
                        )
                        await ws.send_json(
                            {"action": "enroll_face", "status": "started"}
                        )

                    elif action == "enroll_frame":
                        image_data = data.get("image")
                        if not image_data:
                            continue
                        ws_id = id(ws)
                        session = enroll_sessions.get(ws_id)
                        if not session or session.get("done"):
                            continue

                        try:
                            _header, b64 = image_data.split(",", 1)
                            import base64

                            im_bytes = base64.b64decode(b64)
                            arr = np.frombuffer(im_bytes, dtype=np.uint8)
                            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                            if frame is not None:
                                session["frames"].append(frame)
                                person_dir = RAW_DIR / session["name"]
                                person_dir.mkdir(parents=True, exist_ok=True)
                                idx = len(session["frames"]) - 1
                                cv2.imwrite(str(person_dir / f"{idx}.jpg"), frame)
                        except Exception as e:
                            logger.exception("Failed to decode enroll_frame: %s", e)

                except Exception as e:
                    # During shutdown, the socket may already be closing.
                    try:
                        await ws.send_json({"error": str(e)})
                    except Exception:
                        pass

            elif msg.type == WSMsgType.ERROR:
                logger.error(f"WebSocket error {ws.exception()}")

    except asyncio.CancelledError:
        # Expected during server shutdown.
        pass
    finally:
        try:
            if not ws.closed:
                await ws.close()
        except Exception:
            pass

    return ws


# --------------------------------------------------
# WEBRTC OFFER HANDLER
# --------------------------------------------------
async def handle_offer(request):
    user = request.get("user") or {}
    # Members are allowed to connect to WebRTC stream (see ROLE_PERMISSIONS.webrtc.connect)
    require_role(user, ["admin", "member"])
    if AUTH_READY and can and not can(request.get("user") or {}, "webrtc", "connect"):
        return web.Response(status=403)
    params = await request.json()
    mode = params.get("mode", "test")
    analysis = _bool_param(params.get("analysis"), default=True)
    camera_id = params.get("cameraId") or params.get("camera_id")
    try:
        camera_id = int(camera_id) if camera_id is not None else None
    except Exception:
        camera_id = None
    if camera_id is not None:
        try:
            if AUTH_READY and user_can_access_camera:
                access = await user_can_access_camera(request.get("user") or {}, camera_id)
                if access is False:
                    # Camera may not exist in DB (env-var configured) — only block
                    # if the camera actually has a DB record the user lacks access to.
                    try:
                        from db import db_get_camera as _db_gc
                        cam = await _db_gc(camera_id)
                        if cam is not None:
                            return web.Response(status=403)
                        # Camera not in DB → env-var configured, allow
                    except Exception:
                        pass  # DB lookup failed, allow access
        except Exception:
            pass  # Don't block on DB errors

    # Strictly CCTV mode
    source = "cctv"

    sdp = params["sdp"]
    type_ = params["type"]

    server_camera_track = None

    # Log source selection inputs
    logger.info(
        "Offer received: request.mode=%s, request.source=%s, request.camera_id=%s, MODE=%s",
        mode,
        source,
        camera_id,
        MODE,
    )

    user_agent = request.headers.get("User-Agent", "")
    print(f"📱 CLIENT DETECTED: {user_agent[:50]}...")
    logger.info(f"=== New WebRTC offer received (mode: {mode}) ===")
    logger.info(f"📱 Client User-Agent: {user_agent}")

    # Check if iOS/Safari
    is_ios = "iPhone" in user_agent or "iPad" in user_agent
    is_safari = "Safari" in user_agent and "Chrome" not in user_agent
    # expose simple global flag so frame processing can adapt for iOS clients
    try:
        global latest_client_is_ios
        latest_client_is_ios = bool(is_ios)
    except Exception:
        pass
    # iOS detection - keep behavior minimal and just log
    if is_ios or is_safari:
        logger.info("🦁 iOS/Safari detected - applying compatibility fixes")
        # SIMPLIFY: Just log, don't modify SDP
        print("🦁 iOS/SAFARI DETECTED - Using H264 codec")

    # ICE servers configuration (CRITICAL for phones/NAT)
    # Use a simple, compatible list for this aiortc version
    config = RTCConfiguration(
        iceServers=[
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun2.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun3.l.google.com:19302"]),
        ]
    )

    logger.info(f"❄️ Using ICE configuration with {len(config.iceServers)} servers")

    # Create PeerConnection with proper RTCConfiguration
    pc = RTCPeerConnection(configuration=config)
    # Per-connection timeout hint (used by higher-level logic if needed)
    try:
        pc._connection_timeout = 30  # seconds
    except Exception:
        pass
    pcs.add(pc)

    # Store the DataChannel reference at PC level so it stays alive
    pc._alert_channel = None

    # ICE connection monitoring
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        state = pc.iceConnectionState
        # Provide clearer ICE status logs and basic handling for timeouts
        print(f"❄️ ICE: {state}")
        if state == "checking":
            print("🔄 ICE checking - this may take a moment...")
        elif state == "disconnected":
            print("⚠️ ICE disconnected - attempting to reconnect")

    @pc.on("icegatheringstatechange")
    async def on_icegatheringstatechange():
        logger.info(f"❄️ ICE Gathering State: {pc.iceGatheringState}")

    @pc.on("signalingstatechange")
    async def on_signalingstatechange():
        logger.info(f"📶 Signaling State: {pc.signalingState}")

    @pc.on("datachannel")
    def on_datachannel(channel):
        logger.info(f"📩 DataChannel received from client: {channel.label}")
        pc._alert_channel = channel

        # Store in global alert_channels
        alert_channels.add(channel)
        logger.info(f"📊 Added to alert_channels, now: {len(alert_channels)}")

        @channel.on("open")
        def on_open():
            logger.info(f"✅✅✅ Client DataChannel OPEN: {channel.label}")
            logger.info(f"📊 alert_channels count: {len(alert_channels)}")

            # Send immediate test alerts
            try:
                # Test 1
                channel.send(
                    json.dumps(
                        {
                            "person": "SERVER",
                            "event": "DATA_CHANNEL_CONNECTED",
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                )
                logger.info("✅ Test alert 1 sent")

                # Test 2 after 1 second
                async def send_delayed_test():
                    await asyncio.sleep(1)
                    if hasattr(channel, "readyState") and channel.readyState == "open":
                        channel.send(
                            json.dumps(
                                {
                                    "person": "SYSTEM",
                                    "event": "READY_FOR_DETECTIONS",
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                }
                            )
                        )
                        logger.info("✅ Test alert 2 sent")

                asyncio.create_task(send_delayed_test())
                # Notify client that face enrollment can start now
                channel.send(
                    json.dumps(
                        {
                            "person": "SYSTEM",
                            "event": "READY_FOR_FACE_ENROLLMENT",
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                )

            except Exception as e:
                logger.error(f"Failed to send test alert: {e}")

        @channel.on("close")
        def on_close():
            logger.info(f"❌❌❌ Client DataChannel CLOSE: {channel.label}")
            if channel in alert_channels:
                alert_channels.remove(channel)
            logger.info(f"📊 alert_channels now: {len(alert_channels)}")

        @channel.on("error")
        def on_error(error):
            logger.error(f"⚠️⚠️⚠️ DataChannel ERROR: {error}")

        @channel.on("message")
        def on_message(msg):
            logger.info(f"📨 Message from client: {msg}")
            try:
                msg_data = json.loads(msg)
                logger.info(f"Client message: {msg_data}")
            except:
                logger.info(f"Raw message: {msg}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state: {pc.connectionState}")
        if pc.connectionState in ("failed", "closed", "disconnected"):
            logger.info("Cleaning up connection...")
            # pass

            # Stop server camera track (decrements shared camera refcount)
            try:
                nonlocal server_camera_track
                if server_camera_track is not None:
                    server_camera_track.stop()
                    server_camera_track = None
            except Exception:
                pass

            # Clean up DataChannel
            if pc._alert_channel and pc._alert_channel in alert_channels:
                alert_channels.remove(pc._alert_channel)

            pcs.discard(pc)

    async def _setup_pc():
        nonlocal server_camera_track
        # Set remote description (client's offer)
        try:
            type_val = locals().get("type_", None)
            print(
                f"📡 Offer type: {type_val}, SDP length: {len(sdp) if sdp is not None else 0}"
            )
        except Exception:
            print("📡 Offer debug: could not determine type_/sdp length")
        if type_val is None:
            type_val = "offer"
        offer = RTCSessionDescription(sdp, type_val)
        await pc.setRemoteDescription(offer)
        logger.info("Remote description set")
        try:
            print(f"✅ Remote description set, SDP has H264: {'H264' in sdp}")
        except Exception:
            logger.info("Could not evaluate SDP H264 presence")

        # Check if client SDP has DataChannel
        if "m=application" in sdp or "webrtc-datachannel" in sdp:
            logger.info("✅ Client SDP includes DataChannel support")
        else:
            logger.warning("❌ Client SDP does NOT include DataChannel")

        # Add CCTV SharedServerCameraTrack (RTSP)
        logger.info(
            "📺 Using CCTV SharedServerCameraTrack (RTSP), camera_id=%s, analysis=%s",
            camera_id,
            analysis,
        )
        server_camera_track = SharedServerCameraTrack(
            fps=SERVER_CAMERA_FPS,
            camera_id=camera_id,
            process=analysis,
        )
        pc.addTrack(server_camera_track)

        # Prefer H264 for Safari/iOS clients to avoid black-screen on some devices
        try:
            force_h264(pc)
        except Exception as e:
            logger.debug(f"force_h264 skipped: {e}")

        # Create answer and inject HD bitrate hints into the video section so
        # aiortc's encoder targets the full WEBRTC_VIDEO_KBPS bitrate.
        answer = await pc.createAnswer()
        try:
            munged_sdp = _munge_sdp_bitrate(answer.sdp, WEBRTC_VIDEO_KBPS)
            answer = RTCSessionDescription(sdp=munged_sdp, type=answer.type)
            logger.info(f"📡 SDP bitrate set to {WEBRTC_VIDEO_KBPS} kbps for HD output")
        except Exception as _munge_err:
            logger.warning(f"SDP bitrate munge skipped: {_munge_err}")
        await pc.setLocalDescription(answer)
        print(f"✅ Answer ready, type: {pc.localDescription.type}")
        print(f"✅ WebRTC connection established with {user_agent[:30]}")

    try:
        await _setup_pc()

        # Allow connection to stabilize without blocking other offers.
        # await asyncio.sleep(0.25)

    except Exception as e:
        logger.error(f"Error during WebRTC setup: {e}")
        import traceback

        logger.error(traceback.format_exc())

        # Clean up on error
        if pc._alert_channel and pc._alert_channel in alert_channels:
            alert_channels.remove(pc._alert_channel)
        pcs.discard(pc)

        return web.json_response({"error": str(e)}, status=500)

    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args, _unknown = parser.parse_known_args()

    middlewares = [auth_middleware] if auth_middleware else []
    # Increase max request size to 100MB for base64 image uploads
    app = web.Application(middlewares=middlewares, client_max_size=1024**2 * 100)

    # --------------------------------------------------
    # STATIC FILES (Swagger, CSS, JS, etc.)
    # --------------------------------------------------
    STATIC_DIR = REPO_ROOT / "static"

    app.router.add_static("/static/", path=STATIC_DIR, name="static", show_index=False)

    async def init_db(app):
        logger.info("Initializing PostgreSQL pool...")
        app["db"] = await asyncpg.create_pool(
            user=os.getenv("DB_USER", "cctv_user"),
            password=os.getenv("DB_PASS", "StrongPassword123"),
            database=os.getenv("DB_NAME", "cctv_platform"),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "5432")),
            min_size=5,
            max_size=20,
        )
        if set_pool:
            set_pool(app["db"])
        logger.info("✅ PostgreSQL pool ready")

    async def close_db(app):
        logger.info("Closing PostgreSQL pool...")
        await app["db"].close()

    async def startup(app):
        logger.info("Server startup...")

        # Start alert queue processor
        app["alert_processor"] = asyncio.create_task(process_alert_queue())
        app["db_persist_processor"] = asyncio.create_task(persist_db_queue())
        logger.info("✅ Alert queue processor started")
        try:
            from app import ml_tracking

            async def _log_mlflow_deployment():
                await asyncio.to_thread(
                    ml_tracking.log_deployment_run, "server_startup"
                )

            app["mlflow_deployment"] = asyncio.create_task(_log_mlflow_deployment())
        except Exception as e:
            logger.debug("MLflow deployment tracking skipped: %s", e)
        try:
            _start_background_cctv_analytics()
        except Exception as e:
            logger.warning(f"Could not start background CCTV analytics: {e}")
        # Start stats reporter
        try:

            async def stats_reporter():
                INTERVAL = 5.0
                while True:
                    await asyncio.sleep(INTERVAL)
                    try:
                        with stats_lock:
                            dr = stats_counters.get("detection_runs", 0)
                            of = stats_counters.get("outgoing_frames", 0)
                            # reset counters
                            stats_counters["detection_runs"] = 0
                            stats_counters["outgoing_frames"] = 0
                        detections_per_sec = dr / INTERVAL
                        outgoing_fps = of / INTERVAL
                        perf_summary = ""
                        if PERF_STATS:
                            try:
                                with perf_lock:
                                    frames = perf_counters.get("frames", 0)
                                    resize_ms = perf_counters.get("resize_ms", 0.0)
                                    yolo_ms = perf_counters.get("yolo_ms", 0.0)
                                    track_ms = perf_counters.get("track_ms", 0.0)
                                    faceid_ms = perf_counters.get("faceid_ms", 0.0)
                                    draw_ms = perf_counters.get("draw_ms", 0.0)
                                    total_ms = perf_counters.get("total_ms", 0.0)
                                    perf_counters["frames"] = 0
                                    perf_counters["resize_ms"] = 0.0
                                    perf_counters["yolo_ms"] = 0.0
                                    perf_counters["track_ms"] = 0.0
                                    perf_counters["faceid_ms"] = 0.0
                                    perf_counters["draw_ms"] = 0.0
                                    perf_counters["total_ms"] = 0.0
                                if frames > 0:
                                    perf_summary = (
                                        f", avg_ms: total={total_ms / frames:.1f} "
                                        f"resize={resize_ms / frames:.1f} "
                                        f"yolo={yolo_ms / frames:.1f} "
                                        f"track={track_ms / frames:.1f} "
                                        f"faceid={faceid_ms / frames:.1f} "
                                        f"draw={draw_ms / frames:.1f}"
                                    )
                            except Exception:
                                perf_summary = ""
                        
                        hw = _get_hardware_stats()
                        hw_summary = f" | HW: cpu={hw['cpu_percent']}% ram={hw['ram_percent']}% gpu={hw['gpu_util']} gmem={hw['gpu_mem']}"

                        logger.info(
                            f"📈 Stats (last {int(INTERVAL)}s) [YOLO: {CURRENT_YOLO_RUNTIME.upper()}]: detections/s={detections_per_sec:.2f}, outgoing_fps={outgoing_fps:.2f}{perf_summary}{hw_summary}"
                        )
                    except Exception as e:
                        logger.warning(f"Stats reporter error: {e}")

            app["stats_reporter"] = asyncio.create_task(stats_reporter())
            logger.info("✅ Stats reporter started")
        except Exception as e:
            logger.warning(f"Failed to start stats reporter: {e}")

    async def logout(request):
        return web.json_response({"message": "Logged out"})

    async def cleanup(app):
        logger.info("Server cleanup...")
        # Cancel alert processor
        if "alert_processor" in app:
            app["alert_processor"].cancel()
            try:
                await app["alert_processor"]
            except asyncio.CancelledError:
                pass
        if "db_persist_processor" in app:
            app["db_persist_processor"].cancel()
            try:
                await app["db_persist_processor"]
            except asyncio.CancelledError:
                pass
        if "mlflow_deployment" in app:
            app["mlflow_deployment"].cancel()
            try:
                await app["mlflow_deployment"]
            except asyncio.CancelledError:
                pass
        # Cancel stats reporter
        if "stats_reporter" in app:
            app["stats_reporter"].cancel()
            try:
                await app["stats_reporter"]
            except asyncio.CancelledError:
                pass
        try:
            _stop_background_cctv_analytics()
        except Exception:
            pass
        logger.info("Cleanup completed")

    app.on_startup.append(init_db)
    app.on_startup.append(startup)

    app.on_cleanup.append(close_db)
    app.on_cleanup.append(cleanup)

    app.router.add_get("/", index)
    # React SPA catch-all routes — every user-facing path serves the React app
    app.router.add_get("/home", _serve_react_spa)
    app.router.add_get("/auth", _serve_react_spa)
    app.router.add_get("/super-admin/dashboard", _serve_react_spa)
    app.router.add_get("/super-admin/dashboard/{tail:.*}", _serve_react_spa)
    # Admin dashboard SPA (same React app, just different base path)
    app.router.add_get("/admin/dashboard", _serve_react_spa)
    app.router.add_get("/admin/dashboard/{tail:.*}", _serve_react_spa)
    # Serve Vite-built static assets (JS, CSS, images) from the React dist folder
    if REACT_DIST.exists() and (REACT_DIST / "assets").exists():
        app.router.add_static("/assets/", path=REACT_DIST / "assets", show_index=False)
    app.router.add_post("/login", login_handler)
    app.router.add_post("/signup", signup_handler)
    app.router.add_get("/me", get_me)
    app.router.add_post("/logout", logout)

    app.router.add_post("/offer", handle_offer)
    # app.router.add_post("/test-alert", test_alert)
    app.router.add_post("/save-roi", save_roi)
    app.router.add_get("/rules/schema", rules_schema)
    app.router.add_get("/rules", get_rules)
    app.router.add_post("/rules", save_rules)
    app.router.add_post("/face/enroll", face_enroll)
    app.router.add_get("/face/list", face_list)
    app.router.add_post("/face/delete", face_delete)
    # Browser webcam enrollment (dashboard CapturePanel → this endpoint)
    app.router.add_post("/api/face/enroll-frames", face_enroll_frames)
    app.router.add_get("/api/face/list", face_list)
    app.router.add_post("/api/face/delete", face_delete)
    app.router.add_get("/api/face/recognition-logs", recognition_logs_handler)
    app.router.add_post("/api/face/recognize", face_recognize)
    # Member Management API (Admin only)
    app.router.add_get("/api/admin/members", list_members)
    app.router.add_patch("/api/admin/members/{id}/permissions", update_member_permissions)
    app.router.add_get("/api/alerts", api_list_alerts)
    app.router.add_get("/api/recordings", api_list_recordings)
    app.router.add_get("/api/cameras/health", api_cameras_health)

    # Runtime toggle: when disabled, alerts still work but no video clips are captured.
    app.router.add_get("/api/event-clips/settings", event_clips_get_settings)
    app.router.add_post("/api/event-clips/settings", event_clips_set_settings)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/api/super-admin/clients", list_clients)
    app.router.add_post("/enroll/create", create_enroll_link)
    app.router.add_get("/api/enroll/{token}/validate", enroll_validate_token)
    app.router.add_post("/api/enroll/{token}/frames", enroll_token_frames)
    app.router.add_get("/enroll/{token}", enroll_page)
    app.router.add_post("/enroll/{token}", enroll_upload)
    try:
        EVENT_CLIP_DIR.mkdir(parents=True, exist_ok=True)
        app.router.add_static("/event-clips/", str(EVENT_CLIP_DIR), show_index=True)
    except Exception as e:
        logger.warning(f"Event clip static route disabled: {e}")
    try:
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        app.router.add_static("/recordings/", str(RECORDINGS_DIR), show_index=True)
    except Exception as e:
        logger.warning(f"Recording static route disabled: {e}")

    sslctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    sslctx.load_cert_chain(
        REPO_ROOT / "certs" / "cert.pem", REPO_ROOT / "certs" / "key.pem"
    )

    logger.info("=== Starting WebRTC YOLO Server ===")
    logger.info(f"WEB ROI: {web_roi}")
    logger.info(f"YOLO device: {yolo_model.device}")
    # User-friendly ready messages
    print("=== SERVER READY on wss://0.0.0.0:8000 ===")
    print("📱 For iPhone: Open Safari to https://YOUR-IP:8000")

    web.run_app(app, host=args.host, port=args.port, ssl_context=sslctx)


if __name__ == "__main__":
    main()
