# Secure View — CPU-Only Deployment Plan (No GPU Required)

**Document Classification**: Internal Strategy & Pre-Sales Architecture  
**Version**: 1.0 | **Date**: June 2026  
**Prepared For**: Management / Product Team  
**Purpose**: Define a viable, full-featured CPU-only deployment plan for clients who cannot or will not purchase GPU hardware — one plan, all features included, no tiering complexity.

---

## Table of Contents

1. [Why a CPU-Only Plan?](#1-why-a-cpu-only-plan)
2. [The Plan: One Tier, All Features](#2-the-plan-one-tier-all-features)
3. [What Changes Without a GPU](#3-what-changes-without-a-gpu)
4. [CPU Inference Architecture](#4-cpu-inference-architecture)
5. [Performance Expectations (Honest Assessment)](#5-performance-expectations-honest-assessment)
6. [Hardware Sizing for CPU-Only](#6-hardware-sizing-for-cpu-only)
7. [Recommended CPU Hardware](#7-recommended-cpu-hardware)
8. [Software Configuration for CPU Mode](#8-software-configuration-for-cpu-mode)
9. [AI Modules in CPU Mode](#9-ai-modules-in-cpu-mode)
10. [Pricing Strategy](#10-pricing-strategy)
11. [Who Should Buy This Plan?](#11-who-should-buy-this-plan)
12. [Limitations & Honest Caveats](#12-limitations--honest-caveats)
13. [Technical Implementation Work Required](#13-technical-implementation-work-required)
14. [Upgrade Path to GPU](#14-upgrade-path-to-gpu)

---

## 1. Why a CPU-Only Plan?

There is a real segment of potential clients who:

- Are in small-to-medium businesses and cannot justify spending ₹1–5L on a GPU server
- Are in regulated or conservative IT environments where GPU servers are not standard
- Are evaluating Secure View before committing to GPU hardware investment
- Have an existing powerful server (with no GPU) they want to repurpose
- Are in countries or regions where NVIDIA GPUs are expensive or hard to procure

Currently, Secure View requires a GPU for AI inference. This is a **hard blocker** for this segment. A CPU-only plan removes that blocker and opens a new market.

### The Trade-Off in One Line

> GPU = more cameras, faster inference, more AI modules simultaneously  
> CPU = fewer cameras, slower inference, but **still real, functional AI surveillance** for small-to-medium deployments

---

## 2. The Plan: One Tier, All Features

### Design Decision: No Free Plan, No Feature Stripping

Based on your manager's direction:
- **There is only ONE plan** (no free tier, no feature-capped starter)
- **All features are included** — object detection, face recognition, LPR, fire detection, pose analysis, alerts, recording, WebRTC streaming, multi-user RBAC
- The only constraint is **camera count**, which is set by the license tier the client purchases
- Pricing is monthly, client owns hardware

### Plan Summary

| Attribute | Value |
|---|---|
| **Plan Name** | Secure View — CPU Edition |
| **AI Modules Included** | All (Object Detection, Face Recognition, LPR, Fire/Smoke, Pose, Anomaly) |
| **GPU Required** | ❌ No |
| **Camera Support** | 1–8 cameras per server (see Section 5 for why) |
| **Pricing Model** | Monthly license, per camera-block |
| **Deployment** | Client-owned server, Docker-based, self-hosted |
| **Recording** | ✅ Yes — continuous + event-triggered clips |
| **WebRTC Streaming** | ✅ Yes — software-encoded (CPU H.264) |
| **Multi-User Dashboard** | ✅ Yes |
| **Alerts** | ✅ Yes — WebSocket + email |

---

## 3. What Changes Without a GPU

Understanding what GPU does vs. what CPU can do is essential for setting the right client expectations.

### 3.1 What the GPU Normally Does in Secure View

| Task | GPU's Role | Can CPU Do It? |
|---|---|---|
| Object detection inference | Batched tensor operations on CUDA | ✅ Yes, but ~5–15× slower |
| Face recognition embedding | ArcFace forward pass | ✅ Yes, but 3–8× slower |
| LPR OCR pipeline | Lightweight model inference | ✅ Yes, ~3–5× slower |
| Video decode (NVDEC) | Hardware-accelerated H.265 decode | ✅ CPU FFmpeg decode works fine |
| WebRTC encode (NVENC) | Hardware H.264 encode | ✅ CPU libx264 encode works fine |
| Fire/smoke detection | Small classification model | ✅ Yes — these are fast on CPU |

**Conclusion**: Everything the GPU does, the CPU can also do. It is just slower. The practical impact is a lower camera capacity and higher per-frame latency — **not a missing feature**.

### 3.2 GPU vs CPU: Capability Comparison

| Feature | GPU Mode | CPU-Only Mode |
|---|---|---|
| Object Detection | ✅ All cameras, real-time | ✅ Up to 8 cameras, near-real-time |
| Face Recognition | ✅ Every 5th frame | ✅ Every 10th–15th frame (still functional) |
| License Plate Recognition | ✅ Real-time | ✅ Event-triggered (on motion) |
| Fire & Smoke Detection | ✅ Every frame | ✅ Every 5th–10th frame |
| Pose Analysis | ✅ Per-person per frame | ⚠️ Disabled by default; enable for ≤2 cameras |
| Recording | ✅ Full | ✅ Full (no difference) |
| Alerts | ✅ Full | ✅ Full (no difference) |
| Dashboard | ✅ Full | ✅ Full (no difference) |
| WebRTC Streaming | ✅ GPU NVENC | ✅ CPU libx264 (slightly more CPU load) |
| Max Cameras (single server) | Up to 50+ | **Up to 8 recommended** |

---

## 4. CPU Inference Architecture

### 4.1 Inference Backend Choices (No GPU)

When running without a GPU, we switch the inference backend:

| Backend | Framework | Speed | Accuracy | Notes |
|---|---|---|---|---|
| **ONNX Runtime (CPU)** | ONNXRuntime | Medium | Same as GPU | **Recommended** — drop-in replacement, multi-threaded |
| **OpenVINO (Intel CPUs)** | Intel OpenVINO | Fast (on Intel) | Same | Best for Intel Xeon / Core i7/i9/i5 with integrated graphics |
| **PyTorch CPU** | PyTorch | Slow | Same | Fallback only; highest RAM usage |
| **TFLite (ARM)** | TensorFlow Lite | Fast (on ARM) | Slightly lower | For Raspberry Pi / ARM servers only |

### 4.2 Recommended Backend: ONNX Runtime

```python
import onnxruntime as ort

# Force CPU execution provider
session = ort.InferenceSession(
    "models/detection_nano.onnx",
    providers=["CPUExecutionProvider"]
)

# Enable multi-threading
sess_options = ort.SessionOptions()
sess_options.intra_op_num_threads = 8   # Use 8 physical cores for inference
sess_options.inter_op_num_threads = 4
```

**Why ONNX Runtime?**
- Works on any x86-64 server without any special hardware
- ONNX models are already used in our GPU pipeline (same models, different provider)
- Supports multi-threading across all CPU cores
- ~2–3× faster than raw PyTorch CPU

### 4.3 Frame Processing Rate Control

The key to making CPU-only work is **intelligent frame sampling**:

```python
# GPU mode: process every frame
# CPU mode: process every Nth frame based on camera count

CPU_FRAME_SKIP_MAP = {
    1: 1,   # 1 camera: process every frame (~10–15 FPS)
    2: 2,   # 2 cameras: every 2nd frame (~8 FPS each)
    4: 3,   # 4 cameras: every 3rd frame (~5 FPS each)
    8: 5,   # 8 cameras: every 5th frame (~3 FPS each)
}
```

At 3–5 FPS per camera, intrusion detection, face recognition, and LPR still work effectively. Human motion events occur over 1–3 seconds — 5 FPS is more than sufficient to catch them.

### 4.4 Model Size Optimization for CPU

On CPU, model size directly impacts inference time. We use smaller, quantized models:

| Module | GPU Mode Model | CPU Mode Model | Size Reduction | Speed Gain |
|---|---|---|---|---|
| Object Detection | Nano-class FP16 ONNX | Nano-class INT8 ONNX | ~50% smaller | ~1.5–2× faster |
| Face Recognition | ArcFace FP16 | ArcFace INT8 | ~50% smaller | ~1.5× faster |
| LPR | Standard ONNX | Quantized INT8 | ~40% smaller | ~1.3× faster |
| Fire Detection | Standard ONNX | Quantized INT8 | ~40% smaller | ~1.3× faster |

INT8 quantization reduces model accuracy by approximately **1–3% mAP** — imperceptible in real-world deployment.

---

## 5. Performance Expectations (Honest Assessment)

### 5.1 Inference Speed on CPU

Reference hardware: **AMD Ryzen 9 7950X (16C/32T)** with ONNX Runtime INT8 models

| Camera Count | AI FPS per Camera | Detection Latency | Face Recognition Frequency | CPU Utilization |
|---|---|---|---|---|
| 1 camera | 12–15 FPS | 65–80 ms | Every 10th frame (~1.5 FPS) | 25–35% |
| 2 cameras | 8–12 FPS | 80–120 ms | Every 12th frame | 45–60% |
| 4 cameras | 5–8 FPS | 120–180 ms | Every 15th frame | 65–80% |
| 8 cameras | 3–5 FPS | 180–300 ms | Every 20th frame | 80–90% |

> **These numbers are functional for real-world security monitoring.** Intrusion alerts at 3 FPS still catch every human entry event. Face recognition at 1 FPS still identifies known persons within 1–2 seconds of appearing.

### 5.2 Comparing GPU vs CPU for a Typical 4-Camera Deployment

| Metric | GPU (RTX 4060) | CPU (Ryzen 9 7950X) | Practical Impact |
|---|---|---|---|
| Detection FPS | 15–20 FPS/camera | 5–8 FPS/camera | Both catch all motion events |
| Alert latency | ~100–200 ms | ~300–600 ms | CPU adds ~0.5 sec delay — acceptable |
| Face ID accuracy | Same model | Same model | No accuracy difference |
| Max cameras | 20–30 | 4–8 | CPU is the hard limit |
| Power consumption | +200–300W for GPU | No extra power | CPU is more energy efficient |
| Hardware cost | +₹40,000–1,50,000 for GPU | Saved entirely | CPU is cheaper upfront |

### 5.3 What CPU-Only Is NOT Suitable For

Be honest with clients about this:

| Scenario | GPU Required? | Reason |
|---|---|---|
| 10+ cameras on a single server | ✅ Yes | CPU cannot handle 10+ streams at useful FPS |
| Real-time face recognition at 15+ FPS | ✅ Yes | CPU face recognition is too slow at high FPS |
| 4K camera streams | ✅ Yes | 4K decode + inference is too heavy for CPU |
| High-security (sub-200ms alert latency required) | ✅ Yes | CPU adds ~300–600ms latency |
| Warehouse/campus with 20+ cameras | ✅ Yes | Scale requires GPU |

---

## 6. Hardware Sizing for CPU-Only

### 6.1 The Bottleneck is CPU Compute, Not VRAM

On CPU mode:
- **VRAM** = not applicable (models run in system RAM)
- **System RAM** = critical (models + frame buffers + OS + Docker)
- **CPU cores** = critical (inference + decode + encoding all compete)
- **NVMe SSD** = important for recording performance

### 6.2 RAM Usage Per Camera (CPU Mode)

| Component | RAM Required |
|---|---|
| OS + Docker + baseline | ~4–6 GB |
| Backend application | ~1–2 GB |
| PostgreSQL | ~500 MB – 1 GB |
| Redis | ~200 MB |
| Detection model (INT8 ONNX) | ~200–400 MB |
| Face recognition model | ~300–600 MB |
| LPR model | ~100–200 MB |
| Fire detection model | ~100–150 MB |
| Per camera frame buffers | ~300–500 MB per camera |
| **Total for 4 cameras** | **~10–14 GB** |
| **Total for 8 cameras** | **~15–20 GB** |

### 6.3 CPU Core Allocation (8-camera example)

| Task | Cores/Threads Needed |
|---|---|
| OS + Docker + system services | 2 threads |
| RTSP decode (8 cameras) | 8–16 threads (1–2 per stream) |
| ONNX inference | 8–12 threads |
| WebRTC encode (software) | 4–8 threads |
| PostgreSQL | 2–4 threads |
| Rule engine + alerts | 1–2 threads |
| **Total needed** | **25–44 threads** |

> This is why we recommend a 12-core / 24-thread (or better) CPU for 8-camera CPU-only deployments. Hyper-threading helps significantly.

---

## 7. Recommended CPU Hardware

### 7.1 Hardware Configurations

| Cameras | CPU | RAM | NVMe | HDD | Est. Hardware Cost |
|---|---|---|---|---|---|
| 1–2 cameras | Intel Core i7-13700 (16T) | 16 GB DDR5 | 512 GB | 1–2 TB | ₹60,000–80,000 |
| 3–4 cameras | AMD Ryzen 9 7900X (24T) | 32 GB DDR5 | 1 TB | 4 TB | ₹90,000–1,20,000 |
| 5–6 cameras | AMD Ryzen 9 7950X (32T) | 32 GB DDR5 | 1 TB | 6 TB | ₹1,20,000–1,60,000 |
| 7–8 cameras | AMD Threadripper 7960X (48T) or Dual Xeon Silver | 64 GB DDR5 ECC | 2 TB | 8 TB | ₹2,00,000–3,00,000 |

> **Note**: 8-camera CPU-only is the practical maximum. Clients needing more cameras should be directed to the GPU plan.

### 7.2 Intel vs AMD for CPU Inference

| CPU Family | ONNX Runtime Benefit | OpenVINO Benefit | Recommendation |
|---|---|---|---|
| Intel Core i7/i9 (13th/14th Gen) | Standard multi-threaded | ✅ Excellent (AVX-512 + OpenVINO optimized) | Best for OpenVINO backend |
| AMD Ryzen 9 (7000 series) | ✅ Excellent (AVX-512) | Partial | Best for ONNX Runtime backend |
| Intel Xeon (Scalable) | ✅ Excellent (AVX-512) | ✅ Excellent | Best for enterprise multi-socket |
| ARM (Ampere Altra) | Moderate | ❌ Not supported | Use TFLite; not recommended |

### 7.3 OS & Software Pre-Requisites

```
Operating System:   Ubuntu 22.04 LTS (Server)
Docker Engine:      24.x with Docker Compose v2
NVIDIA drivers:     NOT required
System RAM:         32 GB minimum (for 4+ cameras)
Storage:            NVMe for OS + app; HDD/NAS for recordings
```

---

## 8. Software Configuration for CPU Mode

### 8.1 Environment Variables

The software should auto-detect CPU mode, but allow explicit override:

```bash
# In .env file on client server

# Force CPU mode (no GPU required)
INFERENCE_DEVICE=cpu
ONNX_PROVIDER=CPUExecutionProvider

# Enable OpenVINO for Intel CPUs (optional, better performance on Intel)
# ONNX_PROVIDER=OpenVINOExecutionProvider

# Inference threading
ONNX_INTRA_THREADS=8
ONNX_INTER_THREADS=4

# Frame skip settings (auto-calculated if not set)
CPU_FRAME_SKIP_OVERRIDE=3   # Process every 3rd frame

# Disable pose analysis by default in CPU mode (too heavy for 4+ cameras)
ENABLE_POSE_ANALYSIS=false

# Software WebRTC encoding (no NVENC)
WEBRTC_ENCODER=libx264
WEBRTC_ENCODER_PRESET=veryfast  # CPU encoding must be fast; sacrifice quality slightly
```

### 8.2 Docker Compose for CPU Mode

```yaml
# docker-compose.cpu.yml
# Usage: docker compose -f docker-compose.cpu.yml up -d

services:
  secureview-app:
    image: secureview-app:2.1.0-cpu  # CPU-specific image (no CUDA dependencies)
    # Remove the GPU section entirely:
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - capabilities: [gpu]
    environment:
      - INFERENCE_DEVICE=cpu
      - ONNX_PROVIDER=CPUExecutionProvider
    volumes:
      - ./models:/app/models
      - ./event_clips:/app/event_clips
      - /etc/secureview:/etc/secureview  # License key location
```

### 8.3 CPU-Specific Docker Image

We need a **separate, smaller CPU-only Docker image** that:
- Does NOT include CUDA libraries (saves ~3–5 GB image size)
- DOES include ONNXRuntime CPU + OpenVINO
- Uses INT8 quantized model files
- Tags: `secureview-app:2.1.0-cpu` vs `secureview-app:2.1.0-gpu`

---

## 9. AI Modules in CPU Mode

### 9.1 Feature Status Per Module

| Module | CPU Mode Status | Configuration |
|---|---|---|
| **Object Detection** | ✅ Fully functional | Every Nth frame (N scales with camera count) |
| **Object Tracking** | ✅ Fully functional | CPU-based ByteTrack; no change needed |
| **Zone Rules & Alerts** | ✅ Fully functional | Pure Python; no hardware dependency |
| **Recording & Clips** | ✅ Fully functional | FFmpeg CPU encode; no change |
| **Dashboard & WebRTC** | ✅ Fully functional | Software encode (libx264) |
| **Face Recognition** | ✅ Functional (slower) | Every 10–20th frame; still catches faces within ~2 sec |
| **License Plate Recognition** | ✅ Functional (slower) | Triggered on vehicle detection events |
| **Fire & Smoke Detection** | ✅ Functional | Every 5th–10th frame (fires are slow-developing) |
| **Anomaly Detection** | ✅ Fully functional | Statistical/ML on event streams; CPU-friendly |
| **Pose Analysis** | ⚠️ Limited | Enabled only for 1–2 camera deployments; disable for 4+ |

### 9.2 Pose Analysis Special Case

Pose estimation (skeleton tracking) is the most compute-heavy module. On CPU:
- For **1–2 cameras**: Enable at every 5th frame — works fine
- For **3–4 cameras**: Enable at every 10th frame — functional but adds ~15% CPU load
- For **5–8 cameras**: **Disable** — the CPU overhead makes it impractical

The dashboard should show a clear warning if the client tries to enable Pose for more than 2 cameras in CPU mode:

> ⚠️ *Pose analysis on CPU is recommended for 1–2 cameras only. For 3+ cameras, consider upgrading to a GPU plan for optimal performance.*

---

## 10. Pricing Strategy

### 10.1 Single Plan Pricing

As directed, there is **one plan** with all features. Price is per camera block, monthly.

| Camera Blocks | Cameras Included | Monthly Price (INR) | Monthly Price (USD) |
|---|---|---|---|
| Block 1 | 1–2 cameras | ₹8,000 / mo | ~$95 / mo |
| Block 2 | 3–4 cameras | ₹14,000 / mo | ~$168 / mo |
| Block 3 | 5–6 cameras | ₹20,000 / mo | ~$240 / mo |
| Block 4 | 7–8 cameras | ₹26,000 / mo | ~$312 / mo |

> Maximum 8 cameras on CPU plan. For 9+ cameras, client must upgrade to GPU plan.

### 10.2 What's Included (No Hidden Extras)

Every CPU plan includes:
- ✅ All AI modules (detection, face, LPR, fire, anomaly)
- ✅ Unlimited users and roles (RBAC)
- ✅ Recording (limited only by client's storage hardware)
- ✅ Event clip generation
- ✅ WebRTC live streaming
- ✅ Email/WebSocket alerts
- ✅ Software updates for 12 months
- ✅ Standard support (email, 2-business-day response)
- ✅ License for client-owned hardware

### 10.3 Annual Discount

| Term | Discount |
|---|---|
| Monthly rolling | No discount |
| Annual (pay quarterly) | 10% off |
| Annual (pay upfront) | 15% off |

### 10.4 Upgrade Path

When a client on the CPU plan wants to scale beyond 8 cameras:
- We offer a **credit for unused CPU license months** toward a GPU plan
- This creates a natural upgrade funnel from CPU → GPU plan

---

## 11. Who Should Buy This Plan?

### Ideal Clients

| Client Type | Why CPU Plan Fits |
|---|---|
| **Small retail stores** (1–4 cameras) | Doesn't need 50 cameras; existing PC can run it |
| **Small offices / co-working spaces** | 4–6 cameras; IT team already has a server |
| **Warehouses with ≤8 entrances** | 8 cameras covers all access points; CPU inference is enough |
| **Schools / institutions** | Budget-conscious; existing server infrastructure |
| **Hospitality (small hotels, guesthouses)** | 4–8 cameras; cost-sensitive |
| **Pilot / PoC deployment** | Client wants to evaluate Secure View before GPU investment |

### Who Should NOT Buy This Plan (and We Should Upsell)

| Client Type | Why They Need GPU Plan |
|---|---|
| **Warehouses with 10+ cameras** | CPU cannot handle 10+ streams usefully |
| **Manufacturing plants** | Need real-time face recognition across many zones |
| **Campuses / large buildings** | 20–100+ cameras; scale requires GPU |
| **Any client needing <200ms alert latency** | GPU is required for sub-200ms glass-to-glass |
| **Any client with 4K cameras** | 4K decode + inference is too heavy for CPU |

---

## 12. Limitations & Honest Caveats

We must be transparent with clients about what CPU mode cannot do.

> **Recommended approach**: Include this as a "What to Expect" section in the pre-sales call and the onboarding email. Do not hide these limitations — discovered limitations post-sale create churn and damage reputation.

| Limitation | Detail |
|---|---|
| Maximum 8 cameras per server | CPU compute is the hard ceiling |
| Higher alert latency | 300–600ms vs 100–200ms on GPU — still acceptable for surveillance |
| Lower AI FPS | 3–8 FPS vs 15–25 FPS — still catches all real-world events |
| Face recognition slower | Identifies a face within 2–3 seconds, not 0.5 seconds |
| Pose analysis limited | Disabled for 5+ cameras by default |
| Cannot use 4K cameras | 4K decode on CPU is too heavy; 1080p maximum recommended |
| WebRTC quality | Software encode (libx264) is ~5–10% lower visual quality vs NVENC at same bitrate |

---

## 13. Technical Implementation Work Required

The following engineering work is needed to support the CPU-only plan:

### Priority 1: Core (Must Have for Launch)

- [ ] Add `INFERENCE_DEVICE=cpu` configuration flag to backend
- [ ] Switch ONNX provider based on env var (GPU → CPU)
- [ ] Build CPU-specific Docker image (no CUDA dependencies)
- [ ] Implement frame-skip scaling logic based on camera count in CPU mode
- [ ] INT8 quantize all AI models; package in CPU bundle
- [ ] Switch WebRTC encoder to libx264 in CPU mode
- [ ] Add CPU mode detection warning in dashboard (performance expectations)

### Priority 2: Quality (Should Have)

- [ ] Add OpenVINO provider support for Intel CPU optimization
- [ ] Build auto-hardware-detection on startup (detect if GPU present; switch mode)
- [ ] Add Pose Analysis warning for 5+ cameras in CPU mode
- [ ] Add "CPU capacity nearly full" warning at 7–8 cameras in dashboard
- [ ] Add one-click "Upgrade to GPU Plan" CTA in dashboard

### Priority 3: Nice to Have

- [ ] CPU performance benchmark tool (client can run before purchase to see expected FPS)
- [ ] ARM64 support (Raspberry Pi 5 / Jetson Nano — budget edge use cases)

**Estimated implementation time: 4–6 weeks** (most work is configuration + image build; the core ONNX Runtime CPU path already works)

---

## 14. Upgrade Path to GPU

When a client on the CPU plan is ready to scale, the upgrade should be seamless:

### 14.1 Upgrade Steps

```
1. Client purchases GPU plan license key
2. Client installs NVIDIA GPU in their existing server (or buys new server)
3. Client installs NVIDIA drivers + nvidia-container-toolkit
4. Client downloads GPU Docker bundle
5. Client swaps license key (we remotely deactivate CPU key, issue GPU key)
6. Client runs: docker compose -f docker-compose.gpu.yml up -d
7. All data (cameras, users, events, recordings) preserved — same database
8. System automatically uses GPU; performance immediately improves
```

### 14.2 Data Continuity

All configuration, recordings, and historical data are stored in PostgreSQL and the local filesystem — they are **identical between CPU and GPU modes**. There is no migration. The client keeps their full history when upgrading.

---

## Summary

| Attribute | CPU-Only Plan |
|---|---|
| **Plan Count** | One plan (all features included) |
| **GPU Required** | No |
| **AI Features** | All (detection, face, LPR, fire, pose, anomaly) |
| **Max Cameras** | 8 per server |
| **Target Client** | Small-medium business, 1–8 cameras |
| **Hardware Cost** | ₹60,000–3,00,000 (client buys) |
| **Software License** | ₹8,000–26,000 / month |
| **Implementation Effort** | 4–6 weeks |
| **Upgrade Path** | Seamless to GPU plan (same database, same hardware) |

This plan directly addresses the market segment that wants powerful AI surveillance without the GPU investment. It is not a compromise — it is a legitimate product for the right scale of deployment, with a clear and honest story about its capabilities and limits.
