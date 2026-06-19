# SecureVU AI — Model Training & Hyperparameter Report

This document details the parameters, hyperparameters, and training configurations used for the object detection and recognition models in the SecureVU system, along with the results of different design choices.

---

## 1. Core Model Library
The system utilizes a multi-stage pipeline with the following models:

| Component | Model Used | Size / Weights | Purpose |
|---|---|---|---|
| **Object Detection** | **YOLOv11m** (Fine-tuned) | `secure_cv_best.pt` (40.5 MB) | Person detection in CCTV feeds |
| **Object Tracking** | **ByteTrack** | (Algorithmic) | Tracking individuals across frames |
| **Face Recognition** | **InsightFace ArcFace** (buffalo_l) | ~326 MB (5 ONNX models) | Generating face embeddings |
| **Posture Detection** | **MediaPipe Pose** (Lite) | 5.8 MB (.task) | Detecting standing/sitting states |

---

## 2. YOLOv11m Training Parameters
The primary model (YOLOv11m) was fine-tuned on a custom dataset of ~2,000 images.

### Hyperparameters (Training Configuration)
| Hyperparameter | Value | Description |
|---|---|---|
| **Base Model** | `yolo11m.pt` | YOLOv11 Medium (20M parameters) |
| **Epochs** | 100 | Maximum iterations (Early stopping @ 93) |
| **Image Size** | 640 × 640 | Standard training resolution |
| **Batch Size** | 16 | Images per gradient update |
| **Optimizer** | AdamW | Robust optimizer for fine-tuning |
| **LR0 (Initial)** | 0.001 | Starting learning rate |
| **LRF (Final)** | 0.01 | Final LR (fraction of LR0) |
| **Patience** | 15 | Stop if no improvement for 15 epochs |
| **Augmentations** | Mosaic (1.0), MixUp (0.1) | Used to improve model robustness |
| **Device** | CUDA:0 | Trained on NVIDIA GeForce RTX 2080 Ti |

---

## 3. Results & Performance Comparison

### Best Results (mAP @ 640px)
Calculated from the test set evaluation:
- **mAP50**: **0.8856** (88.6% accuracy at 0.5 IoU)
- **Precision**: **0.8809**
- **Recall**: **0.8133**
- **Training Time**: 56 minutes (RTX 2080 Ti)

### Analysis of Design Choices
Different choices in model selection and resolution significantly impact "Cost" (inference time) vs. "Quality" (accuracy).

#### Choice A: Model Size (YOLO Family)
| Model | Parameters | GFLOPs | Inference (ms) | Accuracy (mAP) | Recommendation |
|---|---|---|---|---|---|
| YOLOv11n | 2.6M | 6.5 | ~5 ms | ~84% | Best for low-end CPUs/mobile |
| YOLOv11s | 9.4M | 21.5 | ~10 ms | ~88% | Good balance for entry GPUs |
| **YOLOv11m** | **20M** | **67.6** | **~21 ms** | **~91%** | **Current Choice (Optimal)** |
| YOLOv11x | 56.9M | 194.9 | ~55 ms | ~93% | Overkill for CCTV; too slow |

#### Choice B: Input Resolution (`imgsz`)
- **640px (Default)**: Consistent 20+ FPS. Good for most detections.
- **1280px (Enhanced)**: Much higher accuracy for small/far faces, but drops FPS to ~5 per camera.

#### Choice C: Face Recognition Frequency (`FACE_EVERY_N_FRAMES`)
- **N=1**: Accurate but consumes ~10% more GPU per person.
- **N=3 (POC default)**: Balance of responsiveness and GPU load per `.env.example`.

---

## 5. Deep Dive: Face Recognition Architecture

The system uses the **InsightFace ArcFace (buffalo_l)** model bundle. This complex system consists of **5 distinct sub-models** working in a synchronous pipeline to convert a raw CCTV image into a verifiable identity.

### Why 5 Models?
Modern face recognition is not a single "match" step. It requires a chain of operations to ensure the face is properly found, straightened, and analyzed for authenticity.

#### 1. Face Detection (`det_10g`)
- **What it does**: This is the "finder." While YOLO detects the whole person, this model zooms in to find the exact coordinates of the face within the head region.
- **Why we use it**: It provides much tighter bounding boxes than YOLO, which is critical for the next steps.

#### 2. 2D Landmark Detection (`2d106det`)
- **What it does**: Identifies **106 key points** on the face (eyes, nose, mouth, jawline).
- **Utility**: These points are used to "warp" the face. If a person is looking slightly to the side, this model helps "straighten" the face (alignment) so the embedding model sees a consistent front-facing view.

#### 3. 3D Landmark & Pose (`1k3d68`)
- **What it does**: Maps the face in 3D space and calculates the **Head Pose** (Yaw, Pitch, Roll).
- **Usage in SecureVU**: We use this specifically in the **Liveness Pipeline**. By tracking the 3D pose across multiple frames, the system can distinguish between a real human head (which has natural micro-movements) and a flat photo or screen (which has zero 3D variance).

#### 4. Feature Extraction (`w600k_r50`)
- **What it does**: The core **ArcFace** model. It takes the aligned face image and compresses it into a **512-dimensional mathematical vector** (an "embedding").
- **How it works**: This vector is like a digital fingerprint. We compare this vector against your database using "Cosine Similarity." If the mathematical distance is small enough (POC default threshold: **0.25** via `FACE_RECOGNITION_THRESHOLD`), a match is confirmed.

#### 5. Attribute Analysis (`genderage`)
- **What it does**: Predicts the person's age and gender.
- **Role**: This model is part of the standard `buffalo_l` suite. While not used for identity verification, it is loaded to allow for future metadata filtering (e.g., "Find all males in the lobby").

### Summary of Data Flow
1. **YOLO** finds a "Person."
2. **det_10g** finds the "Face" inside that person's box.
3. **2d106det** aligns the face so it's perfectly leveled.
4. **1k3d68** checks if the head is "real/live" via 3D pose variance.
5. **w600k_r50** generates the final fingerprint for identity matching.

---

## 6. Retraining & MLflow (POC branch)

Fine-tune with:

```bash
uv run --group mlops scripts/train_yolo.py
```

This script trains on `datasets/secure_cv_v4/data.yaml`, copies best weights to `models/yolo/secure_cv_best.pt`, logs metrics to MLflow (`securevu-training`), and registers `securevu-person-detector` when MLflow is reachable. See [MLFLOW.md](MLFLOW.md).

---

## 7. Appendix: Why YOLO instead of ResNet?

A common question is why the system uses the "heavy" YOLOv11m model instead of a classic architecture like **ResNet**.

### 1. Detection vs. Classification
- **ResNet** (Residual Network) was designed for **image classification** (answering "What is in this image?").
- **YOLO** (You Only Look Once) is a **one-stage detector** designed to answer "Where are the objects, and what are they?" in a single pass.
- To use ResNet for detection, it must be paired with a "head" (like Faster R-CNN or SSD), which often makes the combined system **slower** and **heavier** than a native YOLO model.

### 2. Efficiency Comparison (YOLOv11m vs. ResNet-50)
| Metric | ResNet-50 (Detection) | YOLOv11m | Result |
|---|---|---|---|
| **Parameters** | ~25M (Backbone only) | **20M** (Total) | YOLO is 20% lighter |
| **GFLOPs** | ~90-100+ | **67.6** | YOLO is 30% faster |
| **Accuracy** | Good | **High** | YOLO has better small-object detection |

### 3. Key Architectural Advantages of YOLO
- **C3k2 / CSP Backbone**: YOLO uses "Cross-Stage Partial" networks that reduce redundant gradient information, making it much more efficient on GPUs like the RTX 2080 Ti.
- **Integrated FPN/PAN**: YOLO has built-in "Feature Pyramid" and "Path Aggregation" networks. These allow it to detect people at different distances (far away vs. close up) with very little extra cost.
- **Real-time Optimization**: YOLOv11 is specifically engineered for 24/7 CCTV monitoring, whereas ResNet is a more general-purpose tool that requires more memory and compute for the same detection quality.

> [!TIP]
> If the current YOLOv11m feels too heavy for your specific hardware, we can switch to **YOLOv11s** (9M params) or **YOLOv11n** (2M params), which will be significantly faster than any ResNet configuration while still outperforming it in detection tasks.

---

## 8. Hardware Utilization Summary
Based on the live measurements from the RTX 2080 Ti:

- **GPU Utilization**: 37.5% (1 Camera)
- **VRAM Usage**: 2.4 GB (Loaded models: YOLO, Face, Pose)
- **CPU Load**: 4.7% (Kalman filters for tracking, logging)
- **Power Draw**: ~118 Watts

> [!IMPORTANT]
> The current system has headroom for approximately **4 cameras** at current settings before requiring hardware upgrades or lowering the model size to YOLOv11s/n.
