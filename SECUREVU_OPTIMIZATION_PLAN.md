# SecureVU — Performance Optimization Plan

**Version:** 1.0 | **Date:** June 2026 | **Status:** Active

---

## Executive Summary

SecureVU runs YOLO11m + ByteTracker on an NVIDIA RTX 2080 Ti, processing **4 simultaneous RTSP streams** at **~45ms total frame latency**. The current pipeline uses native PyTorch FP16 with no TensorRT, sequential camera processing, and batch size 1.

This plan targets:
- **Reduce latency from ~45ms → 8–15ms** via TensorRT
- **Scale from 4 → 12+ simultaneous cameras** on the same GPU
- **Improve GPU throughput by 30–50%** via batch inference
- **Zero model retraining required**

---

## 1. Current Architecture

```
RTSP Cameras (1–4)
      ↓
Frame Buffer (per-camera thread)
      ↓
Resize → YOLO11m [PyTorch FP16, batch=1, 640px]
      ↓
Dedup → EMA BBox Smooth → ByteTracker
      ↓
InsightFace (every 5th frame) + MediaPipe Pose (every 3rd)
      ↓
ROI / Zone / Line Check → Alert Queue → WebSocket
      ↓
Draw Overlays → WebRTC H.264 → Browser
```

**Tech Stack:**

| Component | Technology |
|---|---|
| Model | YOLO11m `secure_cv_best.pt` (39 MB) |
| Runtime | PyTorch 2.7.1+cu126 |
| Tracker | Ultralytics BYTETracker |
| Face | InsightFace buffalo_l (ArcFace) |
| GPU | RTX 2080 Ti (11 GB VRAM) |
| CUDA | 12.6 / Driver 590.48 |
| TensorRT | ❌ Not enabled |

---

## 2. Current Performance Metrics (Baseline)

| Metric | Value |
|---|---|
| YOLO inference time | 15–25ms/frame |
| Tracking time | ~0.3ms/frame |
| Drawing time | ~0.7ms/frame |
| **Total frame latency** | **~45ms** |
| Processing FPS per camera | 20–33 FPS |
| GPU Utilization | 34–58% |
| GPU Memory (4 cameras) | ~2,400 MB / 11,264 MB |
| CPU Utilization | ~11% |
| Active cameras | 4 |
| Inference format | PyTorch .pt (FP16 AMP) |

---

## 3. Bottleneck Analysis

| # | Bottleneck | Impact | Root Cause |
|---|---|---|---|
| B-1 | YOLO native PyTorch runtime | HIGH | No TensorRT; Python dispatch overhead per call |
| B-2 | Sequential camera processing | HIGH | Single loop handles cameras one-by-one |
| B-3 | Batch size = 1 | MEDIUM | GPU SIMD underutilized (34–58% GPU util) |
| B-4 | Drawing on all cameras | LOW | Global `DISABLE_DRAWING=0` regardless of view |
| B-5 | Frame skip = 1 (every frame) | HIGH | 4 cameras × 30 FPS = 120 YOLO calls/sec at max load |

---

## 4. High Priority Optimizations

### O-1 — TensorRT Engine Export
**Effort: 2–3 hours | FPS Gain: 2–4× | No retraining**

TensorRT fuses CUDA kernels into a single optimized compute graph, eliminating Python dispatch overhead. It is the single largest performance improvement available.

**Export command:**
```python
from ultralytics import YOLO

model = YOLO("models/yolo/secure_cv_best.pt")
model.export(
    format="engine",
    half=True,       # FP16
    device=0,        # GPU 0
    imgsz=640,
    workspace=4,     # GB — reduce to 2 if OOM
)
# Output: models/yolo/secure_cv_best.engine
```

**`.env` change:**
```env
YOLO_WEIGHTS=models/yolo/secure_cv_best.engine
YOLO_ENABLE_FP16=1
YOLO_ENABLE_FUSE=0   # Not needed for TRT engines
```

No code change in `server.py` — `YOLO(path)` transparently handles `.engine` files.

**Expected results:**

| | Before | After |
|---|---|---|
| YOLO inference | 15–25ms | 8–12ms |
| Max cameras (30 FPS) | 4 | 7–8 |
| GPU util (4 cameras) | 34–58% | 20–35% |

**Risks:**
- Engine is GPU-architecture-specific — must re-export on new hardware
- Keep `.pt` file as fallback

---

### O-2 — Frame Skip (YOLO_PROCESS_EVERY_N_FRAMES)
**Effort: 15 minutes | Camera Capacity: +100% | No retraining**

Processing every 2nd frame halves GPU load. ByteTracker interpolates positions for skipped frames maintaining smooth overlays.

```env
# Current
YOLO_PROCESS_EVERY_N_FRAMES=1

# Recommended
YOLO_PROCESS_EVERY_N_FRAMES=2
```

**Per-scenario guide:**

| Use Case | Setting | Max Cameras (RTX 2080 Ti) |
|---|---|---|
| High-security, max accuracy | `=1` | 4 |
| Standard surveillance | `=2` | 8 |
| Low-security / many cameras | `=3` | 12 |

---

### O-3 — Inference Resolution Tuning
**Effort: 5 minutes | FPS Gain: +20–30% | No retraining**

YOLO inference scales quadratically with resolution. For grid view (4+ cameras), 480px is sufficient.

```env
# Grid view
YOLO_INPUT_WIDTH=480
YOLO_INPUT_HEIGHT=480

# Focus mode — keep full resolution
FOCUS_YOLO_INPUT_WIDTH=1280
FOCUS_YOLO_INPUT_HEIGHT=1280
```

| Resolution | Est. YOLO Time (TRT) | Small Object Recall |
|---|---|---|
| 1280px | ~30ms | Best |
| 640px | ~10ms | Good |
| 480px | ~6ms | Acceptable |
| 320px | ~3ms | Marginal |

---

## 5. Medium Priority Optimizations

### O-4 — Async Per-Camera Processing
**Effort: 1–2 days | Throughput Gain: +20–40%**

Currently sequential. Wrapping per-camera logic in `asyncio.gather()` lets cameras process independently.

```python
async def process_all_cameras(camera_ids, frame_buffer):
    tasks = [
        asyncio.create_task(process_camera_frame(cam_id, frame_buffer[cam_id]))
        for cam_id in camera_ids
        if frame_buffer.get(cam_id) is not None
    ]
    await asyncio.gather(*tasks)
```

> [!IMPORTANT]
> The shared `yolo_model` is not thread-safe for concurrent `.predict()` calls. Use a model-per-thread pool or a single inference thread with a queue feeding results to per-camera handlers.

---

### O-5 — Batch Inference
**Effort: 2–3 days | GPU Throughput: +30–50%**

Group frames from multiple cameras into a single YOLO call.

```python
batch_frames = [frame_buffer[c] for c in active_cameras if frame_buffer.get(c) is not None]

results_batch = yolo_model(
    batch_frames,
    imgsz=640,
    verbose=False,
    conf=_yolo_conf_thr,
    iou=0.45,
)

for cam_id, results in zip(active_cameras, results_batch):
    process_results(cam_id, results, frame_buffer[cam_id])
```

| Batch Size | GPU Util | Cameras @ 30 FPS |
|---|---|---|
| 1 (current) | 34–58% | 4 |
| 4 | 70–85% | 6–7 |
| 8 | 85–95% | 10–12 |

---

### O-6 — Per-Camera Drawing Toggle
**Effort: 4 hours | CPU Saving: ~30%**

Background cameras (not currently in focus view) do not need overlay rendering.

```python
ACTIVE_VIEW_CAMERA = None  # Updated by WebSocket from client

def should_draw(camera_id: int) -> bool:
    return ACTIVE_VIEW_CAMERA is None or ACTIVE_VIEW_CAMERA == camera_id
```

```env
DISABLE_DRAWING=0   # Current global setting
# Future: BACKGROUND_DRAW=0  (per-camera)
```

---

### O-7 — ByteTracker Parameter Tuning
**Effort: 30 minutes**

```env
# Standard (current)
BT_TRACK_HIGH_THRESH=0.35
BT_TRACK_LOW_THRESH=0.15
BT_NEW_TRACK_THRESH=0.35
BT_TRACK_BUFFER=90
BT_MATCH_THRESH=0.85

# Crowded / high-traffic cameras
BT_TRACK_HIGH_THRESH=0.45
BT_TRACK_BUFFER=60
BT_MATCH_THRESH=0.80

# Low-activity / corridor cameras
BT_TRACK_HIGH_THRESH=0.30
BT_TRACK_BUFFER=120
BT_MATCH_THRESH=0.88
```

---

## 6. Low Priority Optimizations

### O-8 — torch.compile()
**Effort: 1 hour | FPS Gain: +10–20%**

```python
# After model load in server.py
if use_cuda:
    try:
        yolo_model.model = torch.compile(
            yolo_model.model, mode="reduce-overhead"
        )
        print("✅ torch.compile() applied")
    except Exception as e:
        print(f"⚠️ torch.compile() skipped: {e}")
```

Warmup with a dummy inference at server startup to avoid first-frame latency spike.

### O-9 — ONNX for CPU-Only Deployments
**Effort: 1 hour | Use case: No GPU**

```python
model.export(format="onnx", simplify=True, opset=17, imgsz=640)
```

```env
YOLO_WEIGHTS=models/yolo/secure_cv_best.onnx
YOLO_ENABLE_FP16=0
YOLO_PROCESS_EVERY_N_FRAMES=4
```

Expected CPU inference: 150–400ms/frame on 8-core CPU.

---

## 7. Implementation Roadmap

### Phase 1 — Week 1 (No Code Changes Required)

| Task | Change | Gain |
|---|---|---|
| TensorRT export | `.env`: `YOLO_WEIGHTS=*.engine` | 2–4× FPS |
| Frame skip ×2 | `.env`: `YOLO_PROCESS_EVERY_N_FRAMES=2` | +100% cameras |
| Resolution 480px | `.env`: `YOLO_INPUT_WIDTH/HEIGHT=480` | +20–30% FPS |
| ByteTracker tune | `.env`: `BT_TRACK_BUFFER=60` | Stability |

### Phase 2 — Weeks 2–3 (Minor Code Changes)

| Task | Effort |
|---|---|
| Per-camera drawing toggle | 4 hours |
| torch.compile() warmup | 2 hours |
| ONNX export for CPU fallback | 1 hour |
| Load test 6–8 cameras | 1 day |

### Phase 3 — Month 1–2 (Architectural Changes)

| Task | Effort |
|---|---|
| Async per-camera processing | 3–5 days |
| Batch inference implementation | 3–5 days |
| Full 12-camera load test | 2 days |

---

## 8. Deployment Configuration Reference

### GPU (Production)
```env
MODEL_SELECT=6
YOLO_WEIGHTS=models/yolo/secure_cv_best.engine
YOLO_ENABLE_FP16=1
YOLO_ENABLE_FUSE=0
YOLO_INPUT_WIDTH=640
YOLO_INPUT_HEIGHT=640
FOCUS_YOLO_INPUT_WIDTH=1280
FOCUS_YOLO_INPUT_HEIGHT=1280
YOLO_PROCESS_EVERY_N_FRAMES=2
DISABLE_DRAWING=0
BT_TRACK_BUFFER=90
```

### CPU-Only
```env
MODEL_SELECT=6
YOLO_WEIGHTS=models/yolo/secure_cv_best.onnx
YOLO_ENABLE_FP16=0
YOLO_INPUT_WIDTH=480
YOLO_INPUT_HEIGHT=480
YOLO_PROCESS_EVERY_N_FRAMES=4
DISABLE_DRAWING=1
POSTURE_ENABLE=0
```

### High Camera Count (8+ cameras, GPU)
```env
YOLO_WEIGHTS=models/yolo/secure_cv_best.engine
YOLO_INPUT_WIDTH=480
YOLO_INPUT_HEIGHT=480
YOLO_PROCESS_EVERY_N_FRAMES=2
FACE_EVERY_N_FRAMES=10
POSTURE_EVERY_N_FRAMES=6
DISABLE_DRAWING=0
```

---

## 9. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| TensorRT engine GPU-locked | Medium | Medium | Keep `.pt` fallback; document re-export |
| Batch inference thread-safety | Medium | High | Use inference queue or model pool |
| Frame skip misses fast events | Low | High | Keep skip ≤ 2; validate zone intrusion alerts |
| torch.compile() regression | Low | Medium | Gate with try/except; test before prod |

---

## 10. Before vs After Summary

| Metric | Current | Phase 1 | Phase 3 |
|---|---|---|---|
| YOLO Latency | 15–25ms | 8–12ms | 5–8ms (batched) |
| Total Frame Latency | ~45ms | ~15–20ms | ~10–15ms |
| Max Cameras @ 30 FPS | 4 | 8–10 | 14–16 |
| GPU Utilization (4 cams) | 34–58% | 15–25% | Efficiently scaled |
| GPU Memory | ~2,400 MB | ~2,200 MB | ~2,800 MB |
| Deployment Formats | PyTorch .pt | TRT + .pt | TRT + ONNX + .pt |

---

*Source: Live system profiling + checkpoint analysis — June 2026*
*Hardware: NVIDIA RTX 2080 Ti (11 GB), PyTorch 2.7.1+cu126, CUDA 12.6*
