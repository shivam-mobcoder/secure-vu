# SecureVU — YOLO11 Model Comparison (secure_cv_v4)

**Date:** July 2026  
**Hardware:** NVIDIA RTX 2080 Ti (11 GB VRAM)  
**Dataset:** `datasets/secure_cv_v4` — 1 class (`person`)  
**Production stack:** 4× Dahua RTSP cameras, TensorRT FP16 @ 960px, InsightFace, ByteTrack  

> **Training sources:** **YOLO11n** and **YOLO11s** were fine-tuned in this POC (`POC-SecureVU-updated`, 25 June 2026). **YOLO11m / 11l / 11x** were trained in the production `object-detection-main` project. All five variants use the same **secure_cv_v4** Roboflow export (1,905 / 181 / 92 split).

---

## 1. Dataset

| Split | Images |
|-------|--------|
| Train | 1,905 |
| Valid | 181 |
| Test | 92 |

All fine-tuned models below were trained on this same CCTV person dataset unless noted.

**Export note:** Roboflow pre-resized sources to 512×512; all training runs used **`imgsz=640`** at train time to match production inference letterboxing.

---

## 2. Model Size & Architecture

| Variant | Params | GFLOPs | Weights (.pt) | ONNX (POC) | TensorRT engine @ 960 |
|---------|--------|--------|---------------|------------|------------------------|
| YOLO11n | 2.6M | 6.5 | 16 MB (`yolo11n_securevu`) | 11 MB | — (not exported) |
| YOLO11s | 9.4M | 21.5 | 19 MB (`yolo11s_securevu`) | 37 MB | — (not exported) |
| YOLO11m | 20.0M | 67.6 | 39 MB (`secure_cv_best.pt`) | 77 MB | 90 MB |
| YOLO11l | 25.3M | 86.6 | 49 MB (`secure_cv_best_l.pt`) | — | 127 MB |
| YOLO11x | 56.9M | 194.9 | 110 MB (`secure_cv_best_x.pt`) | — | 274 MB |

**POC artifact paths**

- `models/yolo11n_securevu.onnx` ← `reports/training/yolo11n/weights/best.pt`
- `models/yolo11s_securevu.onnx` ← `reports/training/yolo11s/weights/best.pt`

---

## 3. Training Comparison

| Model | Trained on secure_cv_v4 | Resolution | Batch | Epochs (stopped) | Training time | Weights file | MODEL_SELECT |
|-------|-------------------------|------------|-------|------------------|---------------|--------------|--------------|
| 11n | ⚠️ Partial | 640 | 32 | 3 / 100 | ~1 min (stable) | `yolo11n_securevu` | POC tier only |
| 11s | ✅ Yes | 640 | 8 | 85 / 100 | ~60 min | `yolo11s_securevu` | POC tier only |
| 11m | ✅ Yes | 640 | 16 | 93 / 100 | ~57 min | `secure_cv_best.pt` | 6 |
| 11l | ✅ Yes | 960 | 4 | 102 / 150 | 3h 13m | `secure_cv_best_l.pt` | 9 |
| 11x | ✅ Yes | 960 | 4 | 76 / 150 | 4h 07m | `secure_cv_best_x.pt` | 10 |

### POC recipe (11n & 11s) — `scripts/train_person_yolo.py`

- Ultralytics YOLO11, **640px**, AMP on CUDA, **patience=20**
- Optimizer: auto (SGD-style defaults), **lr0=0.01**, mosaic + randaugment
- Sequential queue: **11n → 11s** (SecureVU stopped during training)
- **11n:** stable for ~3 epochs, then parallel resume runs collapsed (NaN losses); best checkpoint from early epoch exported
- **11s:** batch reduced **16 → 8** after GPU OOM; completed 85 epochs (~0.99 h) before early-stop/export

### Production recipe (11l & 11x)

AdamW, lr0=0.001, cosine LR, patience=20, mosaic/mixup/copy-paste augmentations, AMP on CUDA.

### Production recipe (11m)

Same optimizer/LR style as 11l, **640px**, batch 16, patience 15.

---

## 4. Accuracy (Validation — Best Epoch)

| Model | Best epoch | Precision | Recall | mAP50 | mAP50-95 | Test mAP50 |
|-------|------------|-----------|--------|-------|----------|------------|
| 11n | 2 | 0.789 | 0.661 | 0.740 | 0.393 | — |
| 11s | 90 | 0.865 | 0.804 | 0.878 | 0.566 | — |
| 11m | 47 | 0.840 | 0.821 | 0.891 | 0.561 | 0.886 |
| 11l | 95 | 0.848 | 0.848 | 0.896 | 0.593 | — |
| 11x | 62 | 0.866 | 0.838 | 0.898 | 0.582 | — |

**POC metrics source:** `reports/training/yolo11n/results.csv`, `reports/training/yolo11s/results.csv`, `reports/training/FINAL_METRICS.md`  
**Production metrics source:** `training_log.txt`, `training_log_11l.txt`, `training_log_11x.txt`, `runs/train/*/results.csv`

**Takeaway:** On secure_cv_v4, **11s reaches ~87.8% mAP50** — a solid POC result, but still **~1.3 pts below 11m** and **~1.8 pts below 11l**. **11n peaked at 74.0% mAP50 with only 66.1% recall** after an unstable short run; it is not competitive with m/l/x. The jump **11m → 11l** remains the largest practical gain; **11l → 11x** is marginal for mAP50 but costly for speed.

---

## 5. Live Runtime — 4 Cameras (RTX 2080 Ti)

Measured from production server logs with `ANALYTICS_ALL_CCTV=1`, TensorRT FP16, `imgsz=960`, 4 RTSP streams — **11m / 11l / 11x only**. POC **11n / 11s** use ONNX Runtime in SecureVU (CPU or CUDA), not TensorRT @ 960.

| Model | YOLO inference | Processing FPS (4 cams) | GPU util | VRAM (typical) | Grid UI feel |
|-------|----------------|-------------------------|----------|----------------|--------------|
| 11n | ~5–8 ms* | Fast* | Low* | ~1.5 GB* | Not live-tested (unstable weights) |
| 11s | ~10–15 ms* | Fast* | Low–med* | ~2 GB* | POC CPU ONNX — smooth; fixture F1 100% (13 frames) |
| 11m | ~30–55 ms | ~25–28 FPS | ~45–83% | ~2.5 GB | Stable baseline |
| 11l | ~29–34 ms | ~75–90 FPS | ~45–53% | ~3.2 GB | Smooth — current production choice |
| 11x | ~280–380 ms | ~10 FPS | 95–100% | ~7.0 GB | Laggy, tiles go black |

\*11n/11s TensorRT @ 960 not measured in production; speed estimates from architecture. POC **11s** deployed as **ONNX @ 640–768px** on CPU/GPU copy.

---

## 6. Known Issues by Model

### YOLO11n — ❌ Not suitable for production

| Issue | Detail |
|-------|--------|
| Unstable training | Only **3 stable epochs** before NaN collapse; no full 100-epoch fine-tune completed |
| Low validation recall | **66.1% recall**, **74.0% mAP50** — well below 11s/m/l/x |
| Small-person blind spots | Smallest backbone; misses distant, partial, or low-contrast people |
| Security risk | Missed detections = missed alerts, zone violations, and timer gaps |

**Verdict:** Fine-tune was **attempted** on secure_cv_v4 but **did not complete successfully**. Do not deploy. Re-run a clean single-process 11n training if a mobile tier is needed.

---

### YOLO11s — ⚠️ Trained in POC; below production m/l tier

| Issue | Detail |
|-------|--------|
| Validation gap vs 11m/l | **87.8% mAP50** vs **89.1% (11m)** / **89.6% (11l)** on same dataset |
| Recall gap | **80.4% recall** vs **82.1% (11m)** / **84.8% (11l)** |
| No TensorRT engine | POC exported **ONNX only** — not benchmarked on 4-cam TensorRT @ 960 |
| Trained at 640px | Less detail for small/distant persons than 960px 11l/x |
| Acceptable for 1–2 cams | Could work on edge/CPU if some misses are tolerable |

**Verdict:** **Successfully fine-tuned** in POC (`PERSON_MODEL_TIER=yolo11s`). Viable for CPU/low-GPU deployments; production TensorRT stack should stay on **11l**.

---

### YOLO11m — ✅ Original production baseline

| Issue | Detail |
|-------|--------|
| Lower recall than 11l/x | Test recall 81.3% vs 84.8% (11l) on same dataset |
| Trained at 640px | Less detail for small/distant persons than 960px models |
| Slightly imprecise boxes | mAP50-95 = 56.1% (vs 59.3% for 11l) |

**Verdict:** Solid, proven default. Superseded by 11l for accuracy without sacrificing speed.

---

### YOLO11l — ✅ Recommended production model

| Strength | Detail |
|----------|--------|
| Best accuracy/speed balance | mAP50 0.896, ~30 ms YOLO, ~75–90 FPS on 4 cams |
| Highest mAP50-95 | Tightest boxes among all trained variants (0.593) |
| Moderate VRAM | ~3.2 GB total pipeline vs ~7 GB for 11x |
| Stable grid UI | No black tiles or motion-induced lag observed |

| Minor issue | Detail |
|-------------|--------|
| Longer training | ~3h vs ~1h for 11m |
| Larger engine | 127 MB vs 90 MB (11m) — negligible on disk |

**Verdict:** Current production choice (`MODEL_SELECT=9`).

---

### YOLO11x — ❌ Too heavy for 4 live streams

| Issue | Detail |
|-------|--------|
| GPU saturated | 95–100% utilization; YOLO alone ~280–380 ms/frame |
| Processing FPS collapse | ~10 FPS pipeline vs target 24 FPS |
| Grid lag under motion | Inference backlog causes stutter, delayed previews |
| Black screen tiles | 2 of 4 camera tiles intermittently black |
| VRAM pressure | ~7 GB for YOLO engine alone |
| Marginal accuracy gain | mAP50 0.898 vs 0.896 (11l) — not worth the cost |
| Training cost | 4h+ GPU time, 274 MB engine |

**Verdict:** Use 11x only for offline analysis, single-camera focus, or batch clip review — not 4-camera live analytics on RTX 2080 Ti.

---

## 7. Summary Matrix

| | 11n | 11s | 11m | 11l | 11x |
|--|-----|-----|-----|-----|-----|
| Trained on secure_cv_v4 | ⚠️ partial | ✅ | ✅ | ✅ | ✅ |
| mAP50 (measured) | 74.0% | 87.8% | 89.1% | 89.6% | 89.8% |
| 4-cam live ready | ❌ | ⚠️ ONNX/POC | ✅ | ✅ | ❌ |
| Detection quality | Poor | Good (POC) | Good | Best balance | Slightly better |
| Speed (TensorRT 4-cam) | — | — | Good | Fast | Too slow |
| Production fit | ❌ | ⚠️ POC/CPU | ✅ legacy | ✅ recommended | ❌ |

---

## 8. Deployment Quick Reference

### Production (TensorRT @ 960)

```bash
# Recommended (current)
MODEL_SELECT=9
YOLO_WEIGHTS=models/yolo/secure_cv_best_l.pt
MODEL_RUNTIME=tensorrt

# Legacy baseline
MODEL_SELECT=6
YOLO_WEIGHTS=models/yolo/secure_cv_best.pt

# Max accuracy — single cam / offline only
MODEL_SELECT=10
YOLO_WEIGHTS=models/yolo/secure_cv_best_x.pt
```

Export TensorRT engine after training:

```bash
uv run scripts/export_engine.py --weights models/yolo/secure_cv_best_l.pt --imgsz 960
```

Start server:

```bash
./scripts/run_local_gpu.sh
```

### POC SecureVU (`POC-SecureVU-updated`)

```bash
# Fine-tuned tiers (ONNX, 640px train resolution)
PERSON_MODEL_TIER=yolo11s   # or yolo11n (not recommended)
# models/person_medium → models/yolo11s_securevu.onnx
# models/person_mobile  → models/yolo11n_securevu.onnx

PYTHONPATH=src .venv/bin/python -m securevu.main   # port 8003 CPU
# GPU copy: POC-SecureVU-updated-gpu, port 8004, secure_cv_best (11m)
```

Retrain n/s in POC:

```bash
bash scripts/run_training.sh   # stops SecureVU, runs yolo11n → yolo11s
```

---

## 9. Recommendation

| Use case | Model |
|----------|-------|
| 4-camera live CCTV (production TensorRT) | **YOLO11l** |
| Legacy / lower VRAM systems | **YOLO11m** |
| POC / CPU ONNX, fine-tuned on site data | **YOLO11s** (trained here) |
| Offline clip re-analysis, max recall | **YOLO11x** (1 stream) |
| Edge / mobile after proper retrain | Re-run **YOLO11n** cleanly, or use **11s** |
| Avoid | **YOLO11n** as exported — incomplete training, low recall |

---

## Sources

| Scope | Files |
|-------|-------|
| POC 11n/11s training | `reports/training/FINAL_METRICS.md`, `reports/training/state.json`, `reports/training/yolo11n/results.csv`, `reports/training/yolo11s/results.csv`, `reports/training/training.log` |
| POC live eval (11s) | `reports/accuracy_eval/latest/REPORT.md`, `eval/fixtures/person/` |
| Production 11m/l/x | `training_log.txt`, `training_log_11l.txt`, `training_log_11x.txt`, `runs/train/*/results.csv`, `server.log`, `server_11l.log`, `server_11x_recall.log`, `MODEL_TRAINING_REPORT.md`, `SECUREVU_REFINEMENT_PLAN.md` |
