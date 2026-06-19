# SecureVU AI — Model Resource Consumption & Minimum Instance Report

> **Date**: 2026-03-13 | **Environment**: RTX 2080 Ti, 64 GB RAM, Linux  
> **Test**: 1 CCTV camera (RTSP), Face Recognition enabled  
> **Duration**: ~2 minutes sustained load, 20 hardware samples @ 3s interval

---

## Page 1 — Live Measured Stats (1 Camera + Face Recognition)

### Test Configuration

| Parameter | Value |
|---|---|
| Camera | 1× RTSP (1080p substream) |
| YOLO Model | YOLOv11m (fine-tuned, `secure_cv_best.pt`, 40 MB) |
| YOLO Input | 1280×1280, FP16, fused, torch.compiled |
| Face Recognition | InsightFace buffalo_l (ArcFace) via ONNX on CUDA |
| Face Frequency | Every 5th frame (`FACE_EVERY_N_FRAMES=5`) |
| Tracker | ByteTrack |
| Posture Detection | MediaPipe Pose Landmark (Lite) |

### Per-Frame Inference Breakdown (Averaged over 60s steady-state)

| Pipeline Stage | Avg Latency (ms) | Notes |
|---|---|---|
| **Resize/Preprocess** | 0.0 | Negligible — GPU-accelerated |
| **YOLO Detection** | 21.2 | Dominant cost, runs every frame |
| **ByteTrack Tracking** | 0.4 | CPU-based, very lightweight |
| **Face Recognition** | 0.3–0.5 (avg), 3.2–3.8 (when active) | Only runs every 5th frame |
| **Drawing/Overlay** | 0.3 | Bounding boxes, labels, timers |
| **Total per Frame** | **22.1–22.9** | — |

> **Effective Processing FPS**: **~20 FPS** sustained (1 camera)  
> **Detections/second**: ~20 (processing every frame, `YOLO_PROCESS_EVERY_N_FRAMES=1`)

### Hardware Resource Consumption (20 samples over 60s)

| Resource | Average | Min | Max |
|---|---|---|---|
| **CPU** | 4.7% | 3.4% | 8.7% |
| **RAM Used** | 12,389 MB (~12.1 GB) | 12,344 MB | 12,457 MB |
| **RAM %** | 19.3% | 19.2% | 19.4% |
| **GPU Utilization** | 37.5% | 34% | 40% |
| **GPU VRAM** | 2,387 MB (~2.3 GB) | 2,384 MB | 2,396 MB |
| **GPU Temperature** | 55.9°C | 51°C | 60°C |
| **GPU Power Draw** | 118 W | 83.9 W | 147.8 W |
| **GPU Clock** | 1350–1905 MHz | — | — |

### Key Takeaways (1 Camera)

- GPU is only **37.5%** utilized → significant headroom for more cameras or models
- VRAM usage is **2.4 GB / 11.3 GB** → only ~21% consumed
- YOLO is the dominant workload (**96%** of inference time)
- Face recognition is very light when amortized (**~1.5%** of total time)
- CPU is barely utilized (**4.7%**) — bottleneck is GPU compute, not CPU

---

## Page 2 — Resource Consumption of All Models

### Model Breakdown

Based on measured stats and model architecture research:

#### 1. YOLOv11m (Person Detection)

| Metric | Value |
|---|---|
| Model Size | 40 MB (PyTorch .pt) |
| Parameters | 20,030,803 (20M) |
| GFLOPs | 67.6 |
| VRAM (loaded) | ~800 MB |
| Inference Time | **21 ms/frame** @ 1280×1280 FP16 |
| GPU Utilization | ~35% (single camera, every frame) |
| CPU Impact | Minimal (< 2%) |
| Runs | Every frame (`YOLO_PROCESS_EVERY_N_FRAMES=1`) |

#### 2. InsightFace buffalo_l (Face Recognition — ArcFace)

The buffalo_l bundle contains 5 ONNX sub-models:

| Sub-Model | File | Input Size | Purpose | VRAM |
|---|---|---|---|---|
| det_10g | `det_10g.onnx` | dynamic | Face Detection (RetinaFace) | ~400 MB |
| w600k_r50 | `w600k_r50.onnx` | 112×112 | Face Embedding (ArcFace R50) | ~200 MB |
| 1k3d68 | `1k3d68.onnx` | 192×192 | 3D Landmark (68-point) | ~100 MB |
| 2d106det | `2d106det.onnx` | 192×192 | 2D Landmark (106-point) | ~100 MB |
| genderage | `genderage.onnx` | 96×96 | Gender/Age Classification | ~50 MB |

| Metric | Value |
|---|---|
| Total Model Size | ~326 MB (5 ONNX models) |
| Total VRAM (loaded) | ~850 MB |
| Inference Time | **3.2–3.8 ms** per batch call (1–2 faces) |
| Amortized Time | **0.3–0.5 ms/frame** (runs every 5th frame) |
| GPU Utilization | ~2–3% (amortized) |
| CPU Impact | Minimal when on GPU |

#### 3. MediaPipe Pose Landmark (Posture Detection)

| Metric | Value |
|---|---|
| Model File | `pose_landmarker_lite.task` (5.8 MB) |
| VRAM | ~50–100 MB (TFLite, may use CPU) |
| Inference Time | **2–5 ms/frame** per person (estimated) |
| Runs | Every 3rd frame (`POSTURE_EVERY_N_FRAMES=3`) |
| GPU Utilization | ~1–2% |
| CPU Impact | **Higher** (~5–10%) if running on CPU |

#### 4. ByteTrack (Object Tracker)

| Metric | Value |
|---|---|
| Model Size | 0 (algorithmic, no neural network) |
| VRAM | 0 MB |
| Inference Time | **0.3–0.5 ms/frame** |
| GPU Utilization | 0% |
| CPU Impact | ~1% (Kalman filter + Hungarian algorithm) |

### Total Resource Budget (All Models Combined, 1 Camera)

| Resource | With Face Recognition | Without Face Recognition |
|---|---|---|
| **GPU VRAM** | ~2,400 MB | ~1,500 MB |
| **GPU Utilization** | 37–40% | 35% |
| **CPU** | 4–5% | 3–4% |
| **RAM** | ~12.4 GB | ~11.5 GB |
| **Power** | 118 W avg | ~100 W avg |

### Scaling Estimate (Multi-Camera)

| Cameras | GPU Util (est.) | VRAM (est.) | CPU (est.) | Can RTX 2080 Ti Handle? |
|---|---|---|---|---|
| 1 | 37% | 2.4 GB | 5% | ✅ Easily |
| 2 | 55–60% | 2.5 GB | 8% | ✅ Comfortable |
| 4 | 80–85% | 2.6 GB | 12–15% | ⚠️ Near limit |
| 6 | 95%+ | 2.7 GB | 18–20% | ❌ Over capacity |
| 8 | >100% | 2.8 GB | 25% | ❌ Need better GPU |

> **Note**: VRAM doesn't scale linearly with cameras — models are shared. GPU compute (inference time) is the scaling bottleneck. At 4 cameras, processing FPS drops to ~5 FPS per camera with current YOLO settings.

---

## Page 3 — Minimum Instance Configuration

### For 1 Camera (Face Recognition Only)

> Minimum viable deployment for a single security camera with face recognition.

| Component | Minimum | Recommended |
|---|---|---|
| **GPU** | GTX 1650 (4 GB VRAM) | RTX 3060 (6–8 GB VRAM) |
| **CPU** | 4-core (Intel i5 / AMD Ryzen 5) | 6-core |
| **RAM** | 16 GB | 32 GB |
| **Storage** | 20 GB SSD | 50 GB SSD |
| **CUDA Compute** | 7.5 | 8.6+ |
| **Est. FPS** | 10–15 FPS | 20+ FPS |

### For 4 Cameras (Full Pipeline)

> Standard deployment with YOLO + Face Recognition + Pose + ByteTrack on all cameras.

| Component | Minimum | Recommended |
|---|---|---|
| **GPU** | RTX 2080 Ti (11 GB) | RTX 3090 / 4080 (16+ GB) |
| **CPU** | 8-core (i7 / Ryzen 7) | 12-core |
| **RAM** | 32 GB | 64 GB |
| **Storage** | 50 GB SSD | 100 GB SSD (for clips) |
| **CUDA Compute** | 7.5 | 8.6+ |
| **Est. FPS** | 5 FPS/camera | 15+ FPS/camera |

### For 8+ Cameras (Enterprise)

> Large-scale deployment requiring dedicated GPU server.

| Component | Minimum | Recommended |
|---|---|---|
| **GPU** | RTX 4090 (24 GB) or A100 | 2× RTX 4090 or A100 |
| **CPU** | 16-core (Xeon / EPYC) | 32-core |
| **RAM** | 64 GB | 128 GB |
| **Storage** | 200 GB NVMe SSD | 500 GB+ NVMe |
| **Network** | 1 Gbps | 10 Gbps |
| **Est. FPS** | 10 FPS/camera (with optimizations) | 20+ FPS/camera |

### Cloud Instance Mapping

| Provider | 1 Camera | 4 Cameras | 8+ Cameras |
|---|---|---|---|
| **AWS** | g4dn.xlarge (T4 16GB) | g5.2xlarge (A10G 24GB) | g5.12xlarge (4×A10G) |
| **GCP** | n1-standard-4 + T4 | n1-standard-8 + A100 | a2-highgpu-2g (2×A100) |
| **Azure** | NC4as_T4_v3 | NC8as_T4_v3 | NC24ads_A100_v4 |
| **Monthly Est.** | ~$300–400/mo | ~$800–1200/mo | ~$3000–5000/mo |

---

## Page 4 — Optimization Strategies

### To Support More Cameras on Same Hardware

1. **Reduce YOLO resolution**: `YOLO_INPUT_WIDTH=640` reduces compute by ~4× (quality tradeoff)
2. **Skip frames**: `YOLO_PROCESS_EVERY_N_FRAMES=3` reduces GPU load by 3×
3. **Reduce face frequency**: `FACE_EVERY_N_FRAMES=15` for less critical deployments
4. **Disable posture detection**: `POSTURE_ENABLE=0` saves ~5% GPU per camera
5. **Use YOLO11n instead of YOLO11m**: 3× faster, smaller model (quality tradeoff)
6. **TensorRT export**: Can provide 2–3× faster inference over PyTorch

### Model Size Comparison (YOLO Family)

| Model | Params | GFLOPs | FP16 Inference (est.) | Accuracy (mAP50) |
|---|---|---|---|---|
| YOLOv11n | 2.6M | 6.5 | ~5 ms | ~84% |
| YOLOv11s | 9.4M | 21.5 | ~10 ms | ~88% |
| **YOLOv11m** (current) | **20M** | **67.6** | **~21 ms** | **~91%** |
| YOLOv11l | 25.3M | 86.9 | ~28 ms | ~92% |
| YOLOv11x | 56.9M | 194.9 | ~55 ms | ~93% |

---

## Summary for Seniors

> **Question**: What are the stats for 1 camera with face recognition?

- **Answer**: 1 camera with face recognition uses **37% GPU**, **2.4 GB VRAM**, **5% CPU**, **12 GB RAM**, achieving **20 FPS** detection with YOLO running at **21 ms/frame** and face recognition at **3.5 ms/batch**.

> **Question**: What are the consumptions of other models?

- **Answer**: YOLO (21 ms/frame, 800 MB VRAM) is the dominant cost. Face recognition (3.5 ms/batch, 850 MB VRAM) is lightweight when amortized. Pose detection (~3 ms, ~100 MB VRAM) and ByteTrack (0.4 ms, no VRAM) are negligible. See Page 2 for full breakdown.

> **Question**: What is the minimum instance configuration?

- **Answer**: For 1 camera: **GTX 1650 (4 GB) + 4-core CPU + 16 GB RAM** (~$300/mo cloud). For 4 cameras: **RTX 2080 Ti or better + 8-core + 32 GB RAM** (~$800/mo cloud). See Page 3 for detailed tiers.
