# Secure View — Deployment Summary

**Version**: 2.0.0 | **Date**: May 2026

---

## What It Is

Secure View is a self-hosted, AI-powered CCTV analytics platform. All processing — video, AI inference, storage — happens on the client's own hardware. No cloud, no data egress.

---

## Deployment Models

| Model | Cameras | Best For |
|---|---|---|
| **Edge** | 1–8 | Retail, ATMs, gates |
| **On-Premise Server** | 1–100+ | Warehouses, campuses |
| **Hybrid** | 1–500+ | Multi-site enterprise |
| **Private Cloud** | 1–1000+ | IT-mature orgs with private DC |

---

## AI Tiers

| Tier | Modules | AI FPS / Camera |
|---|---|---|
| **Basic** | Nano detection @ 640 | 5–10 FPS |
| **Advanced** | Medium detection @ 640 + Face Recognition + Tracking | 10–15 FPS |
| **Professional** | Medium detection @ 1280 + Face + Pose + LPR + Fire + Anomaly | 15–25 FPS |

---

## Hardware Sizing — Quick Reference

### Basic Tier (detection only)

| Cameras | GPU | RAM | NVMe | HDD |
|---|---|---|---|---|
| 1 | RTX 4060 (8 GB) | 8–16 GB | 128–256 GB | 1 TB |
| 10 | RTX 4060–4070 | 16–32 GB | 512 GB–1 TB | 4–8 TB |
| 25 | RTX 4070–4080 | 32–64 GB | 1–2 TB | 8–20 TB RAID-6 |
| 50 | RTX 4080–4090 | 64–128 GB | 2–4 TB | 16–40 TB RAID-6 |
| 100 | 2× RTX 4090 | 128–256 GB | 4–8 TB | 32–80 TB RAID-6 |

### Advanced Tier (detection + face recognition)

| Cameras | GPU | RAM | NVMe | HDD |
|---|---|---|---|---|
| 1 | GTX 1660 Super+ | 16–32 GB | 256–512 GB | 1–2 TB |
| 10 | RTX 4070–4080 | 32–64 GB | 1–2 TB | 8–16 TB RAID-6 |
| 25 | RTX 4080–4090 | 64–128 GB | 2–4 TB | 20–40 TB RAID-6 |
| 50 | RTX 4090 / A5000 | 128–256 GB | 4–8 TB | 40–80 TB RAID-6 |
| 100 | 2× RTX 4090 | 256–512 GB | 8–16 TB | 80–160 TB RAID-6 |

### Professional Tier (full pipeline)

| Cameras | GPU | RAM | NVMe | HDD |
|---|---|---|---|---|
| 1 | RTX 3060+ (12 GB) | 16–32 GB | 256–512 GB | 2–4 TB |
| 10 | RTX 4080–4090 | 64–128 GB | 2–4 TB | 16–32 TB RAID-6 |
| 25 | RTX 4090 / A6000 | 128–256 GB | 4–8 TB | 40–80 TB RAID-6 |
| 50 | 2× RTX 4090 | 256–512 GB | 8–16 TB | 80–160 TB RAID-6 |
| 100 | 4× RTX 4090 or 2× H100 | 512 GB–1 TB | 16–32 TB | 160–320 TB RAID-6 |

> **All VRAM figures are minimum baselines** calculated from compact reference-class models. Measure your actual `Model_Base_VRAM` with `nvidia-smi` after loading your model files, then use: `Total VRAM = Model_Base_VRAM + (N_cameras × per-camera buffer)`.

---

## VRAM Sizing Formula

```
GPU_VRAM_Capacity = floor((Total_VRAM_MB - 512 - Model_Base_VRAM_MB) / Per_Camera_Buffer_MB)

Per_Camera_Buffer_MB:
  Basic tier      → ~100 MB
  Advanced tier   → ~150 MB
  Professional    → ~200–300 MB

Model_Base_VRAM minimums (sum of enabled modules):
  Detection (nano)      → 300–600 MB
  Detection (medium)    → 400–700 MB
  Face recognition      → 400–800 MB  (if enabled)
  LPR                   → 200–400 MB  (if enabled)
  Fire/Smoke            → 100–250 MB  (if enabled)
  Pose                  → 50–200 MB   (if enabled)
```

GPU compute is almost always the first bottleneck — not VRAM.

---

## GPU Compute Formula

```
Max Cameras = floor(1000 / (Inference_Time_ms × Target_FPS))

Typical inference times (mid-range GPU, PyTorch):
  Nano @ 640     → ~5 ms   (TensorRT: ~2 ms)
  Medium @ 640   → ~10 ms  (TensorRT: ~4–5 ms)
  Medium @ 1280  → ~20 ms  (TensorRT: ~8–10 ms)
```

TensorRT FP16 gives 2–3× speedup at no accuracy cost — always use it in production.

---

## Storage Formula

```
Storage (GB/day/camera) = Bitrate_Mbps × 86400 / 8 / 1000
  1080p H.265 @ 2 Mbps = 21.6 GB/camera/day
  1080p H.264 @ 4 Mbps = 43.2 GB/camera/day

Provision with 1.25× overhead (filesystem, DB, clips, logs).
```

| Cameras | 7 Days | 30 Days | 90 Days |
|---|---|---|---|
| 10 | ~1.9 TB | ~8.1 TB | ~24 TB |
| 25 | ~4.7 TB | ~20 TB | ~61 TB |
| 50 | ~9.5 TB | ~41 TB | ~122 TB |
| 100 | ~19 TB | ~81 TB | ~243 TB |

Use surveillance-grade HDDs (SkyHawk AI / WD Purple Pro) for recording. SSDs for OS, DB, models, and event clips only.

---

## GPU Selection Guide

| Use Case | GPU |
|---|---|
| 1–4 cams, Basic | RTX 4060 |
| 1–4 cams, Advanced/Pro | RTX 4060 Ti 16 GB – RTX 4080 |
| 5–15 cams, Basic | RTX 4070 |
| 5–15 cams, Advanced/Pro | RTX 4080–4090 |
| 16–50 cams | RTX 4090 or A5000/A6000 |
| 50–100 cams | Multi-GPU: 2–4× RTX 4090 or 2× A6000 |
| 100+ cams | Multi-server cluster |
| Edge (low power) | Jetson AGX Orin / NVIDIA L4 |

> Multi-GPU requires AMD EPYC or Threadripper (128 / 64 PCIe lanes). Consumer Intel/AMD CPUs max out at 20–28 lanes — inadequate for 2+ GPUs at full bandwidth.

---

## Network Requirements

```
Total LAN Bandwidth = N_cameras × Bitrate_per_camera
Over-provision by 50% for I-frame bursts.

  8 cams  × 2 Mbps = 16 Mbps  → Gigabit switch
 25 cams  × 2 Mbps = 50 Mbps  → Managed Gigabit
 50 cams  × 2 Mbps = 100 Mbps → Gigabit + 10G uplink
100 cams  × 2 Mbps = 200 Mbps → 10G spine-leaf
```

Always VLAN-isolate cameras from user networks.

---

## Key Deployment Examples

### Small Retail (4 cameras, Advanced tier)
- GPU: RTX 4060 | CPU: i5-13400 | RAM: 32 GB | Storage: 512 GB NVMe + 2 TB HDD
- Retention: 15 days | Deployment: edge mini PC

### Warehouse (25 cameras, Professional tier)
- GPU: RTX 4090 | CPU: EPYC 7443P | RAM: 128 GB ECC | Storage: 2 TB NVMe + 6× 8 TB RAIDZ2
- Retention: 30 days | Deployment: rack server

### Apartment Complex (50 cameras, Advanced tier)
- GPU: 2× RTX 4090 | CPU: EPYC 7443P | RAM: 256 GB ECC | Storage: 2 TB NVMe + 8× 10 TB RAIDZ2
- Retention: 30 days | Deployment: server room

### Manufacturing Plant (100 cameras, Professional tier)
- GPU: 2× A6000 per node | CPU: 2× EPYC 9354 | RAM: 512 GB ECC | Storage: 4 TB NVMe + 12× 20 TB RAIDZ2
- Retention: 90 days | Deployment: 2-node HA cluster

---

## Top 10 Deployment Best Practices

1. **Always use H.265** — Halves bandwidth and storage vs H.264.
2. **Use TensorRT FP16** — 2–3× inference speedup, no accuracy loss, free performance.
3. **VLAN-isolate all cameras** — Camera firmware is commonly insecure; never share with user networks.
4. **Surveillance-grade HDDs only** — Desktop drives fail under 24/7 write. SkyHawk AI or WD Purple Pro.
5. **Use ZFS (RAIDZ2)** — Self-healing checksums, snapshots, compression. No hardware RAID controller needed.
6. **UPS for 30+ minutes** — Prevents database corruption on power loss.
7. **Monitor GPU temperature** — Alert at 80°C. Thermal throttling silently degrades AI FPS.
8. **Sub-stream for AI, main-stream for recording** — Process AI on 640×480, record 1080p. Doubles camera capacity.
9. **Back up PostgreSQL every 6 hours** — Database holds all config and events. Video is replaceable; database is not.
10. **Test disaster recovery quarterly** — Restore from backup; verify cameras and AI inference resume.

---

## Internet Requirement

Secure View is **offline-first**. Internet is only needed for:
- Remote dashboard access (VPN required)
- Email/SMS alerts
- Software updates

All AI models run locally. No video or metadata leaves the premises.

---

## Technology Stack

| Layer | Technology |
|---|---|
| AI Inference | PyTorch 2.5 / ONNX Runtime / TensorRT (CUDA 12.x) |
| Video | OpenCV 4.12 + FFmpeg |
| Backend | Python 3.10 + aiohttp + asyncpg |
| Database | PostgreSQL 15+ (local NVMe) |
| Cache | Redis 7+ |
| Proxy | NGINX (TLS 1.3) |
| Streaming | WebRTC (aiortc) |
| Frontend | React 18 (Vite + TailwindCSS) |
| Deployment | Docker Compose / Kubernetes / Bare Metal |
| Monitoring | Prometheus + Grafana + Loki |

---

*For full technical detail — sizing formulas, GPU scaling factors, HA architecture, Kubernetes specs, security hardening — refer to the complete [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).*
