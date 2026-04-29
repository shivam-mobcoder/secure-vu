# SecureVu AI Surveillance — Comprehensive Project Progress Report

This document serves as a complete summary of the architectural migrations, infrastructure implementations, and multi-model optimizations performed to date.

---

## 1. Core Infrastructure & Historical Work

### **Model Migration & Assets**
Successfully identified and migrated specialized AI model weights from the legacy camera environment (`/home/mobcoder/camera`) into the localized `models/` directory for unified management:
*   `yolov8n-face.pt` (Face Detection)
*   `fire_smoke.pt` (Fire & Smoke Detection)
*   `model.pt` (License Plate Detection)
*   `secure_cv_best.pt` (High-Accuracy General YOLO)

### **Real-Time Detection Broadcasting**
Implemented a high-performance event broadcasting system to enable real-time UI overlays:
*   **Backend**: Detection metadata is published to **Redis** on every analyzed frame.
*   **Frontend**: The React dashboard connects via **WebSockets** to receive these events.
*   **Rendering**: Dynamic, scaled bounding boxes are rendered on the client side, significantly reducing the bandwidth required compared to baked-in overlays.

---

## 2. Multi-Model Detection Pipeline (`MODEL_SELECT`)

The system now features a unified selector in `.env` to control five different AI categories across seven operating modes.

| Option | Mode Name | Included Models | Use Case |
| :--- | :--- | :--- | :--- |
| **1** | **General YOLO** | YOLO-General | Standard object detection. |
| **2** | **Face Only** | YOLO-Face | Fast, detection-only face tracking. |
| **3** | **Fire & Smoke** | Fire-Smoke | specialized fire/safety monitoring. |
| **4** | **LPD Only** | License Plate (LPD) | specialized vehicle monitoring. |
| **5** | **Specialized Suite** | 1 + 2 + 3 + 4 | All detectors (No names). |
| **6** | **Production Mode** | 1 + InsightFace | High-accuracy Person Identification. |
| **7** | **The Full Package** | **1 + 2 + 3 + 4 + 6** | **Everything enabled simultaneously.** |

---

## 3. High-Performance Optimization Engine

To handle the heavy load of **Option 7** (running 5+ models at once), the following optimization toggles were implemented:

### **Resolution Presets**
*   **High Speed (640x640):** Reduces GPU math requirements by ~4x.
*   **High Accuracy (1280x1280):** Better for detecting small objects at long distances.
*   *Implementation:* Controlled via `YOLO_INPUT_WIDTH/HEIGHT` in `.env`.

### **Performance Mode (`DISABLE_DRAWING=1`)**
*   Bypasses the CPU-intensive `cv2` pixel drawing layer. 
*   **Impact:** Nearly doubles the server's internal frame rate (FPS) while still maintaining all alerts and database logging.

---

## 4. Comprehensive Performance Benchmarks

All tests were performed on an **11GB GPU** (11,264 MiB total VRAM).

| Mode | GPU VRAM (Used) | CPU Load (Avg) | Speed Notes |
| :--- | :--- | :--- | :--- |
| **Option 5** | ~2.6 GB | ~31% | All specialized detectors active. |
| **Option 6** | ~2.7 GB | ~32% | InsightFace recognition active. |
| **Option 7 (1280)** | ~2.9 GB | ~36% | Full Package (Heavy load). |
| **Option 7 (640)** | **~2.9 GB** | **~37%** | **Fastest (9.0 Detections/sec).** |

### **Key Benchmark Finding:** 
Reducing resolution from 1280 to 640 improved YOLO inference time from **1,200ms** down to **~140ms** without significantly increasing VRAM usage.

---

## 5. Deployment & Execution
The system is now fully standardized using the `uv` environment manager.

*   **To Start Server:** `uv run python app/server.py`
*   **To Check Logs:** `tail -f logs/...` (Internal `📈 Stats` report performance every 5 seconds).
*   **Resolution Preset:** Located at the bottom of `.env` for quick switching.
