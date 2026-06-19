# Development & Optimization Log

This file is for the team to track major code changes, performance optimizations, and technical decisions. Please add new entries at the top with the date, the programmer's name, and a brief description of what was changed and why.

---

## [2026-03-09] GPU Performance Optimization (Antigravity AI)
**Objective**: Maximize hardware utilization for transition from Laptop to PC (RTX 2080 Ti).

### 🔍 Problems Solved
- **CPU Bottleneck**: Face recognition (InsightFace) was running on CPU because the GPU version of ONNX Runtime was missing.
- **Dependency Conflict**: Fixed a conflict between `opencv-python` and `opencv-python-headless` that was breaking imports.

### ⚡ Changes Made
- Switched to `onnxruntime-gpu` for CUDA acceleration.
- Enabled YOLO FP16 Precision and Model Fusing in `.env`.
- Enabled cuDNN benchmarking for faster convolutions.

### 📊 Results & Stats
- **GPU Usage**: Increased from ~36% to **80%** (Powering full AI load).
- **Processing**: Smoother real-time feed across 4 cameras simultaneously.
- **VRAM**: Appropriately utilizing 3.2GB / 11GB of the 2080 Ti.

---

## [2026-03-09] Superadmin Persona Flowchart (Antigravity AI)
**Objective**: Create a professional UI/UX flowchart prompt for Figma AI based on the frontend code.

- **Status**: Completed.
- **Artifact**: [figma_prompt.md](file:///home/mobcoder/.gemini/antigravity/brain/118d0611-43e3-44dd-9988-82a62f32281b/figma_prompt.md)
- **Flows Mapped**: Authentication, Client Management (Add/Edit/Suspend), Client Detail Deep-Dive, and Subscription/Billing Overview.

---

## [2026-03-09] Admin Persona Flowchart (Antigravity AI)
**Objective**: Create a professional UI/UX flowchart prompt for Figma AI for the Admin persona.

- **Status**: Completed.
- **Artifact**: [figma_prompt_admin.md](file:///home/mobcoder/.gemini/antigravity/brain/118d0611-43e3-44dd-9988-82a62f32281b/figma_prompt_admin.md)
- **Flows Mapped**: Live Monitoring (CCTV + Alerts), Face Enrollment (Internal/Remote), User Management (Granular Permissions), and System Device Settings.

---
