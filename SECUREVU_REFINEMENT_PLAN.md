# SecureVU — Accuracy Refinement & AI Improvement Plan

**Version:** 1.0 | **Date:** June 2026 | **Status:** Active

---

## Executive Summary

The SecureVU production model (`secure_cv_best.pt`) is a YOLO11m fine-tuned on the internal `secure_cv_v4` dataset. It achieves **88.1% mAP50** and **57.8% mAP50-95** on the validation split. The model detects a single class — `person` — and is paired with InsightFace ArcFace recognition for named-person identification.

This document identifies accuracy limitations and provides a prioritized roadmap to:

- **Reduce false zone intrusion alerts by ~30%** via temporal confirmation
- **Eliminate ID switches** during occlusion by switching from ByteTracker to BotSort
- **Extend detection to threat-relevant object classes** (bags, vehicles, weapons)
- **Improve mAP50-95 from 57.8% → 63–65%** via targeted retraining
- **Enable small-person detection** at distance via tiling (zero code change)
- **Enable natural-language object queries** via CLIP integration (future)

Improvements are organized into: **No Retraining Required** and **Retraining Required**.

---

## 2. Current Model Analysis

| Field | Value |
|---|---|
| Model | YOLO11m (`secure_cv_best.pt`) |
| Architecture | YOLO11 Medium — C3k2 + C2PSA blocks |
| Classes | **1 — `person` only** |
| Training Dataset | `secure_cv_v4` (internal) |
| Training Resolution | 640×640 |
| Epochs | 100 (patience 15, early stop) |
| Optimizer | AdamW, cosine LR |
| Base Weights | `yolo11m.pt` (pretrained on COCO) |
| AMP | Enabled |

---

## 3. Current Accuracy Metrics

| Metric | Value | Interpretation |
|---|---|---|
| Precision | 84.0% | 16% of detections are false positives |
| Recall | 84.2% | 16% of actual persons are missed |
| **mAP50** | **88.1%** | Strong at 50% IoU — detection quality is good |
| **mAP50-95** | **57.8%** | Drops sharply at tight IoU — bounding boxes are imprecise |
| F1 Score | ~0.841 | Balanced but improvable |
| Val Box Loss | 1.181 | Moderate localization error |
| Val Cls Loss | 0.576 | Classification is reliable (1-class model) |

The 30-point gap between mAP50 and mAP50-95 is the primary quality signal. It means the model **finds persons reliably** but **does not fit bounding boxes tightly**. This causes:
- Imprecise ROI zone entry/exit detection (box edge triggering instead of centroid)
- Weaker appearance-based re-ID matching
- Less reliable cropping for InsightFace input

---

## 4. Current Limitations

| Limitation | Severity | Fix Type |
|---|---|---|
| Single class — no bags, vehicles, weapons | Critical | Retraining |
| Imprecise bounding boxes (mAP50-95 gap) | High | Retraining |
| No confirmed night/low-light training data | High | Retraining |
| ID switches under occlusion (ByteTracker IoU-only) | High | No retraining |
| Zone false alarms from edge-grazing persons | Medium | No retraining |
| Small/distant person detection | Medium | No retraining (tiling) |
| Alert spam from repeated events | Medium | No retraining |
| No unknown object detection | Medium | No retraining (YOLO-World) |
| Fixed confidence threshold (not scene-adaptive) | Low | No retraining |

---

## 5. Refinements — No Retraining Required

---

### R-1 — Switch Tracker: ByteTracker → BotSort
**Priority: 🔴 HIGH | Effort: 4 hours | Expected Gain: Fewer ID switches under occlusion**

#### Problem
ByteTracker matches detections to tracks using **IoU (bounding box overlap) only**. When persons overlap or are occluded, IoU drops to zero and the tracker loses the track, assigning a new ID when the person reappears. This causes:
- Person work timers resetting incorrectly
- Duplicate alert triggers for "new person seen"
- False re-identification events in InsightFace

#### Solution
BotSort adds **appearance embedding matching** alongside IoU. Even if two bounding boxes don't overlap, tracks can be re-linked using visual similarity.

Note: The training config already specified `tracker: botsort.yaml` — the infrastructure is in place.

#### Implementation
```python
# In server.py — _get_bytetracker(), replace BYTETracker with BotSort
from ultralytics.trackers.bot_sort import BOTSORT

def _get_tracker(camera_id: int, frame_rate: int = 30):
    with bytetrack_lock:
        tracker = bytetrackers.get(camera_id)
        if tracker is None:
            args = _load_bytetrack_args()
            tracker = BOTSORT(args, frame_rate=frame_rate)
            bytetrackers[camera_id] = tracker
    return tracker
```

BotSort configuration (`.env`):
```env
BT_TRACK_HIGH_THRESH=0.35
BT_TRACK_LOW_THRESH=0.15
BT_NEW_TRACK_THRESH=0.35
BT_TRACK_BUFFER=90
BT_MATCH_THRESH=0.85
# BotSort additional
BT_WITH_REID=1           # Enable appearance re-ID
BT_PROXIMITY_THRESH=0.5
BT_APPEARANCE_THRESH=0.25
```

**Performance impact:** +2–5ms per frame for appearance feature extraction.

---

### R-2 — Multi-Frame Zone Confirmation
**Priority: 🔴 HIGH | Effort: 4 hours | Expected Gain: ~30% fewer false zone alerts**

#### Problem
Zone intrusion alerts fire on the **first frame** a bounding box edge enters a polygon. A person walking near a zone boundary can trigger multiple false intrusion alerts as their box edge briefly crosses the polygon due to YOLO box jitter.

#### Solution
Require the person to be inside the zone for **N consecutive frames** before firing the intrusion alert. Reset the counter if they exit mid-confirmation.

#### Implementation
```python
# In _apply_camera_rules() — add per-entity confirmation counter
zone_confirm_counts = {}  # {(zone_id, entity): int}
ZONE_CONFIRM_FRAMES = int(os.getenv("ZONE_CONFIRM_FRAMES", "3"))

# In zone intrusion check loop:
key = (zone_id, entity)
if inside:
    zone_confirm_counts[key] = zone_confirm_counts.get(key, 0) + 1
    if zone_confirm_counts[key] == ZONE_CONFIRM_FRAMES:
        # Fire alert — person has been inside for N consecutive frames
        send_alert(_alert_subject(det), ev)
else:
    zone_confirm_counts.pop(key, None)  # Reset on exit
```

```env
ZONE_CONFIRM_FRAMES=3   # Require 3 consecutive frames inside zone
```

---

### R-3 — Enable YOLO Tiling for Distant/Small Persons
**Priority: 🟡 MEDIUM | Effort: 0 minutes (env var) | Expected Gain: +15–25% recall at distance**

#### Problem
At 640px input, a person 10 meters from the camera may occupy only 20–40 pixels height. YOLO11m's feature pyramid handles small objects, but its effective minimum detection size is ~16px. Many distant persons are missed.

#### Solution
Tiling splits the frame into 4 overlapping quadrants and runs YOLO on each at full resolution — effectively giving the model a 1280px view.

```env
YOLO_TILING=1   # Enable 2×2 tile split
```

**Performance impact:** 4× YOLO inference calls per frame. Use with frame skipping:
```env
YOLO_TILING=1
YOLO_PROCESS_EVERY_N_FRAMES=2   # Compensate for 4× YOLO cost
```

---

### R-4 — Confidence-Weighted Temporal BBox Smoothing
**Priority: 🟡 MEDIUM | Effort: 2 hours | Expected Gain: Less flicker, more precise ROI triggering**

#### Problem
Current EMA smoothing uses a fixed alpha=0.75 for all frames. When a high-confidence detection arrives after several low-confidence noisy frames, the smoothed position takes several frames to converge to the true position, causing delayed ROI entry detection.

#### Solution
Make alpha confidence-dependent:
- High-confidence detection (conf > 0.70): alpha = 0.40 → respond quickly
- Medium-confidence (0.40–0.70): alpha = 0.65 → balanced
- Low-confidence (< 0.40): alpha = 0.80 → very stable, trust history

```python
def _adaptive_smooth_alpha(conf: float) -> float:
    if conf >= 0.70:
        return 0.40
    elif conf >= 0.40:
        return 0.65
    else:
        return 0.80
```

```env
BBOX_SMOOTH_ALPHA=0.75   # Current fixed value — replaced by adaptive logic
```

---

### R-5 — YOLO-World Parallel Run for Object Classes
**Priority: 🟡 MEDIUM | Effort: 1 day | No retraining — leverages existing model**

The `yolov8s-worldv2.pt` model (25 MB) is already in the `models/yolo/` directory. YOLO-World is an open-vocabulary detector — it can detect any textual class description without retraining.

#### Use Case
Run YOLO-World on a **low-cadence secondary pass** (every 10th frame) for threat-class detection:
```python
WORLD_CLASSES = ["person with bag", "unattended bag", "vehicle", "motorcycle"]
world_model.set_classes(WORLD_CLASSES)
```

#### Implementation Strategy
```env
MODEL_SELECT=8     # YOLO-World primary (experimental)
# OR
MODEL_SELECT=6     # Keep secure_cv_best.pt primary + run world model secondary
```

Add a secondary model slot in `server.py`:
```python
world_model = None
if os.getenv("WORLD_MODEL_ENABLE", "0") == "1":
    world_model = _load_yolo_model(
        "models/yolo/yolov8s-worldv2.pt", "YOLO-World"
    )
    WORLD_CLASSES = os.getenv("WORLD_CLASSES", "person,bag,vehicle").split(",")
    world_model.set_classes(WORLD_CLASSES)
```

**Performance impact:** +15–25ms every 10th frame.

---

### R-6 — ROI Entry Logic: Centroid-Based vs Edge-Based
**Priority: 🟡 MEDIUM | Effort: 2 hours | Expected Gain: ~20% fewer edge-case false alarms**

#### Problem
Current ROI check uses the **bounding box edges** with a 6px margin. A tall person walking alongside a zone boundary will trigger an intrusion alert even though their center is outside the zone.

#### Solution
Change zone intrusion to use the **foot-point** (bottom center of bounding box) — more semantically correct for person position:

```python
# Current: box edge
cx, cy = det.get("center", (0, 0))  # center of box

# Improved: foot point (bottom center)
x1, y1, x2, y2 = det.get("box", (0, 0, 0, 0))
cx = (x1 + x2) / 2
cy = y2   # Bottom edge = foot contact point
```

```env
ROI_USE_FOOT_POINT=1   # 1 = use foot point, 0 = use box center (current)
```

---

### R-7 — Alert Deduplication Window
**Priority: 🟡 MEDIUM | Effort: 2 hours**

Current cooldowns per alert type:
- Zone/line: 0.30s
- Known person: 20s
- Unknown first-seen: 3600s

Add a **global cross-camera deduplication** window: if the same person triggers the same event type on two cameras within 5 seconds, suppress the duplicate.

```python
_cross_cam_alert_cache = {}   # {(person_key, event_type): timestamp}
CROSS_CAM_DEDUP_SEC = float(os.getenv("CROSS_CAM_DEDUP_SEC", "5.0"))
```

---

### R-8 — InsightFace Match Threshold Tuning
**Priority: 🟢 LOW | Effort: 30 minutes**

Current threshold: `WORK_EMBED_MATCH_THRESHOLD=0.50`

Too low → false watchlist matches (different persons matched to enrolled face).
Too high → real matches missed (enrolled person not recognized).

**Recommendation:** Evaluate on your enrolled face set. Typical optimal range for ArcFace w600k_r50: **0.55–0.65**.

```env
WORK_EMBED_MATCH_THRESHOLD=0.60   # Tighten from 0.50
```

---

## 6. Refinements — Retraining Required

---

### R-9 — Extend to Multi-Class Detection
**Priority: 🔴 HIGH | Effort: 2–4 weeks | Expected Gain: Threat-class detection**

#### Problem
The model detects only `person`. Common surveillance use cases require:
- Unattended bag detection
- Vehicle intrusion
- Weapon detection
- Animal presence

#### Dataset Strategy

| Class | Recommended Dataset | Size |
|---|---|---|
| Person | Current `secure_cv_v4` (retain) | Keep |
| Bag / Backpack | COCO val/train subset | ~8,000 images |
| Vehicle (car, motorcycle, truck) | COCO + VIRAT | ~15,000 images |
| Weapon (optional) | OpenImagesV7 subset | ~3,000 images |

#### Training Configuration
```yaml
# data.yaml
nc: 5
names: ['person', 'bag', 'vehicle', 'motorcycle', 'unattended_object']
```

```python
# Training command
model = YOLO("yolo11m.pt")  # Start from COCO pretrained
model.train(
    data="datasets/secure_cv_v5/data.yaml",   # Extended dataset
    epochs=120,
    batch=16,
    imgsz=640,
    optimizer="AdamW",
    cos_lr=True,
    patience=20,
    device=0,
)
```

**Estimated accuracy gain:** Adds 4 new detection classes. Person mAP minimally affected if original data is retained.
**Performance impact:** Minimal (class count increase is negligible for YOLO11m).

---

### R-10 — Improve mAP50-95 (Bounding Box Precision)
**Priority: 🔴 HIGH | Effort: 1–2 days training | Expected Gain: +3–6% mAP50-95**

#### Problem
Current mAP50-95 = 57.8% vs mAP50 = 88.1%. The 30-point gap means bounding boxes don't fit tightly. Root causes:
1. Training at 640px — small persons occupy fewer pixels → imprecise regression
2. DFL loss weight too low (1.5)
3. No copy-paste augmentation

#### Training Configuration Changes
```python
model.train(
    data="datasets/secure_cv_v4/data.yaml",
    imgsz=1280,        # ↑ from 640 — more pixels per person → tighter boxes
    batch=8,           # ↓ from 16 — 1280px needs more VRAM
    epochs=100,
    dfl=2.0,           # ↑ from 1.5 — stronger localization loss
    copy_paste=0.15,   # Add — improves small/occluded object precision
    hsv_v=0.5,         # ↑ from 0.4 — wider lighting variation
    optimizer="AdamW",
    cos_lr=True,
)
```

**Expected result:** mAP50-95 57.8% → 62–65%. mAP50 maintained at ~88%.

---

### R-11 — Night / Low-Light Dataset Expansion
**Priority: 🔴 HIGH | Effort: 1 week (data collection + 1 day training)**

#### Problem
Training set is `secure_cv_v4` — no nighttime data confirmed. Security cameras operate 24/7 and night performance is unmeasured.

#### Data Collection Plan

| Source | Method | Target Volume |
|---|---|---|
| Existing cameras (night) | Record RTSP stream 22:00–06:00, sample every 30s | 500–1,000 frames |
| Public datasets | ExDark, LLVIP (night person detection) | 2,000–3,000 frames |
| Synthetic augmentation | Apply heavy `hsv_v` + gamma to daytime frames | 1,000 augmented frames |

#### Training Changes
```python
model.train(
    data="datasets/secure_cv_v4_night/data.yaml",  # Extended with night frames
    hsv_v=0.6,          # ↑ from 0.4 — more aggressive brightness variation
    hsv_s=0.8,          # ↑ from 0.7 — saturation variation
    erasing=0.5,        # ↑ from 0.4 — simulate partial occlusion
)
```

---

### R-12 — Training Resolution Increase to 1280px
**Priority: 🟡 MEDIUM | Effort: 1 day training | Expected Gain: +5–8% small person recall**

Training at 1280px means the model learns to detect persons occupying as few as 10px at that scale — equivalent to persons 15–20m from camera.

```python
model.train(
    imgsz=1280,
    batch=8,         # Adjust for VRAM
    multi_scale=0.2, # Vary input size ±20% during training
)
```

Note: Inference resolution stays at 640px for speed. Training at 1280px improves feature representations, not inference resolution.

---

## 7. Tracking Improvement Summary

| Improvement | Tracker | Effort | Expected Gain |
|---|---|---|---|
| Switch to BotSort (R-1) | BotSort | 4 hours | Fewer ID switches under occlusion |
| Multi-frame zone confirm (R-2) | Any | 4 hours | –30% false zone alerts |
| Adaptive bbox smoothing (R-4) | Any | 2 hours | Better ROI precision, less flicker |

---

## 8. Alert Quality Improvements

| Improvement | Type | Effort | Expected Gain |
|---|---|---|---|
| Zone confirm (R-2) | No retrain | 4 hours | –30% edge-case false alarms |
| Foot-point ROI entry (R-6) | No retrain | 2 hours | –20% boundary false alarms |
| Cross-camera dedup (R-7) | No retrain | 2 hours | –40% duplicate cross-camera alerts |
| YOLO-World secondary (R-5) | No retrain | 1 day | New threat-class alerts |
| Multi-class retrain (R-9) | Retrain | 2–4 weeks | Bag/vehicle/weapon alerts |

---

## 9. Face Recognition Improvements

| Improvement | Effort | Expected Gain |
|---|---|---|
| Tighten match threshold to 0.60 (R-8) | 30 min | Fewer false watchlist matches |
| Higher-resolution InsightFace input crops | 2 hours | Better recognition at distance |
| Enroll more images per person (5+) | Operational | More robust embeddings |
| Rolling embedding average (already enabled, alpha=0.35) | — | Already implemented |

---

## 10. Small Object Detection Improvements

| Improvement | Method | Effort | Recall Gain |
|---|---|---|---|
| Tiling 2×2 (R-3) | `YOLO_TILING=1` | 0 minutes | +15–25% |
| Training at 1280px (R-12) | Retrain | 1 day | +5–8% |
| FPN layer addition | Architecture change | 1 week | +10–15% |

---

## 11. Open-Vocabulary & CLIP Integration (Future)

> [!NOTE]
> This section describes optional future enhancements not currently in the codebase. Clearly marked as **future roadmap**.

### Concept
After ByteTracker assigns a stable track, run a CLIP vision-language model on the cropped region. This enables:
- **Natural language queries**: "person with red jacket", "person carrying a bag"
- **Zero-shot event classification**: No class retraining needed
- **Semantic alert enrichment**: Alert text includes appearance description

### Implementation Sketch
```python
import clip
import torch

clip_model, clip_preprocess = clip.load("ViT-B/32", device="cuda")

CLIP_QUERIES = [
    "a person carrying a bag",
    "a person running",
    "an unattended bag on the floor",
    "a person in uniform",
]

def clip_classify_crop(crop_img):
    image = clip_preprocess(crop_img).unsqueeze(0).to("cuda")
    text_tokens = clip.tokenize(CLIP_QUERIES).to("cuda")
    with torch.no_grad():
        image_features = clip_model.encode_image(image)
        text_features = clip_model.encode_text(text_tokens)
        similarity = (image_features @ text_features.T).softmax(dim=-1)
    top_label = CLIP_QUERIES[similarity.argmax()]
    return top_label, similarity.max().item()
```

**Performance impact:** ~30–50ms per crop on RTX 2080 Ti. Run every 30 frames per track, not every frame.

**Recommended model:** `ViT-B/32` (150 MB) for speed; `ViT-L/14` for higher accuracy.

---

## 12. Retraining Roadmap

| Version | Changes | Timeline | Expected mAP50 | Expected mAP50-95 |
|---|---|---|---|---|
| `secure_cv_v4` (current) | Baseline | — | 88.1% | 57.8% |
| `secure_cv_v4.1` | DFL loss 2.0, copy-paste | 1 day | 88.5% | 61–63% |
| `secure_cv_v4.2` | Night data + v4.1 changes | 1 week | 88.5% | 62–64% |
| `secure_cv_v5` | Multi-class (person+bag+vehicle) | 3–4 weeks | ~85% (per class) | ~58–62% |
| `secure_cv_v5.1` | v5 + 1280px training | 1 week | ~86% | ~63–66% |

---

## 13. Dataset Expansion Plan

| Phase | Action | New Images | Training Duration |
|---|---|---|---|
| 1 | Collect nighttime RTSP frames | +1,000 | 1 day |
| 2 | Add COCO bag/vehicle subset | +8,000 | 2 days |
| 3 | Label synthetic hard negatives | +500 | 0.5 days |
| 4 | Add distant person crops (tiled) | +2,000 | 1 day |
| 5 | Weapon class (optional) | +3,000 | 2 days |

---

## 14. Before vs After Comparison

| Metric | Current | After No-Retrain | After Retrain (v5.1) |
|---|---|---|---|
| mAP50 | 88.1% | 88.1% | ~86–88% |
| mAP50-95 | 57.8% | 57.8% | ~63–66% |
| Classes Detected | 1 (person) | 1 + YOLO-World | 5 (person, bag, vehicle, etc.) |
| ID Switch Rate | Moderate | Low (BotSort) | Low (BotSort) |
| False Zone Alerts | Baseline | –30% (confirm) | –30% (confirm) |
| Night Detection | Unknown | Unknown | Validated |
| Small Person Recall | Baseline | +15–25% (tiling) | +20–30% (tiling + 1280 train) |
| Face Match False Pos | Moderate | Low (threshold 0.60) | Low |
| Alert Spam | Moderate | Low (cross-cam dedup) | Low |

---

## 15. Implementation Timeline

### Month 1 — No-Retrain Wins
| Week | Tasks |
|---|---|
| 1 | Switch to BotSort, multi-frame zone confirm, foot-point ROI |
| 2 | Tiling enable, adaptive bbox smoothing, alert dedup |
| 3 | YOLO-World secondary model integration |
| 4 | Testing, alert quality validation |

### Month 2 — Retrain Cycle 1
| Week | Tasks |
|---|---|
| 1–2 | Collect nighttime frames, label, merge into v4.1 dataset |
| 2 | Train `secure_cv_v4.1` (1 day GPU training) |
| 3 | Validate, deploy, A/B test vs current |
| 4 | Collect bag/vehicle labels (COCO subset annotation) |

### Month 3–4 — Retrain Cycle 2 (Multi-class)
| Week | Tasks |
|---|---|
| 1–2 | Finalize `secure_cv_v5` dataset |
| 2–3 | Train `secure_cv_v5` — 3–4 weeks for multi-class |
| 4 | Validate + deploy |

---

## 16. Risk & Complexity Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| BotSort appearance features slow inference | Medium | Low | Disable with env var if needed |
| Zone confirm adds latency to alert | Low | Medium | Use N=2 frames minimum |
| Multi-class retraining hurts person mAP | Medium | High | Use stratified sampling; keep original data ratio |
| Night data shifts model distribution | Low | Medium | Validate on existing val set before deploying |
| CLIP integration adds 30–50ms | High | Medium | Run only on new track init, not every frame |
| Increased dataset size slows training | Low | Low | Use gradient accumulation + batch=8 at 1280px |

---

*Document prepared from live model checkpoint inspection and system profiling — June 2026*
*Model: `secure_cv_best.pt` (YOLO11m, 39 MB, 1 class, trained on `secure_cv_v4`)*
