# 🔐 SecureVU — Developer Handoff Guide

> Prepared by: Shivam Raina  
> Date: June 2026  
> Branch: `feature/tensorrt-runtime`  
> Repo: https://github.com/shivam-mobcoder/secure-vu

---

## 👋 Welcome

You are taking over development of **SecureVU** — an AI-powered CCTV surveillance platform.

This guide tells you **exactly** what you need, what to install, and how to get it running in order.

---

## 🖥️ Hardware Used (Reference Machine)

| Component | Spec |
|-----------|------|
| CPU | AMD Ryzen 9 3950X (16C / 32T) |
| GPU | NVIDIA RTX 2080 Ti (11 GB VRAM) |
| RAM | 64 GB |
| OS | Ubuntu 22.04 LTS |
| NVIDIA Driver | 590.48.01 |
| CUDA Runtime | 13.1 |

> The app runs on CPU-only too — GPU just makes inference faster.

---

## 📦 What You Get From Owner vs What You Install Yourself

### ✅ Owner Must Give You (Cannot auto-download)

| # | File / Item | Why It's Required |
|---|-------------|-------------------|
| 1 | `models/yolo/secure_cv_best.pt` | Custom-trained YOLO model. **Server hard-fails without it.** |
| 2 | RTSP camera URLs | Your site's camera credentials — secret, site-specific |
| 3 | `.env` secrets | DB password, JWT secret, account passwords |

### 🔄 You Auto-Install (No Owner Needed)

| Item | How |
|------|-----|
| Python dependencies | `uv sync` |
| Node / frontend deps | `npm install` |
| PostgreSQL | `docker compose up -d db` |
| InsightFace `buffalo_l` model | **Auto-downloads on first server start** (needs internet) |
| Database schema | Auto-applied by Docker OR run migrations manually |
| TLS certificates | Generate with `openssl` (see Step 5 below) |
| JWT secret | Generate with Python one-liner (see Step 3) |

---

## 🚀 Setup — Step by Step

### Step 1 — Clone & Checkout

```bash
git clone https://github.com/shivam-mobcoder/secure-vu.git
cd secure-vu
git checkout feature/tensorrt-runtime
```

---

### Step 2 — Install Prerequisites

```bash
# Python 3.10.x (must be exactly 3.10.x, not 3.11+)
python3 --version   # verify

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # or restart terminal

# Node.js 18+
node --version   # verify
```

---

### Step 3 — Set Up Environment File

```bash
cp .env.example .env
```

Now open `.env` and fill in:

```dotenv
# ── Database ─────────────────────────────────────
DB_USER=cctv_user
DB_PASS=your_db_password_here
DB_NAME=cctv_platform
DB_HOST=127.0.0.1

# ── JWT Secret (generate once) ───────────────────
# Run: python -c "import secrets; print(secrets.token_hex(64))"
JWT_SECRET=paste_generated_hex_here

# ── Default Login Accounts ───────────────────────
SUPER_EMAIL=super@platform.com
SUPER_PASSWORD=choose_a_strong_password

ADMIN_EMAIL=admin@internal.com
ADMIN_PASSWORD=choose_a_strong_password

MEMBER_EMAIL=member@internal.com
MEMBER_PASSWORD=choose_a_strong_password

# ── RTSP Camera URLs (get from owner) ────────────
RTSP_URL_1=rtsp://user:pass@192.168.x.x:554/stream1
RTSP_URL_2=rtsp://user:pass@192.168.x.x:554/stream2

# ── Model Selection ───────────────────────────────
MODEL_SELECT=6       # 6 = Production (YOLO11m + InsightFace)
MODEL_RUNTIME=pytorch
```

Generate JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_hex(64))"
```

---

### Step 4 — Place the YOLO Model

Get `secure_cv_best.pt` from the owner and place it at:

```
models/yolo/secure_cv_best.pt
```

```bash
mkdir -p models/yolo
# copy secure_cv_best.pt here
```

> ⚠️ The server will **immediately exit** at startup if this file is missing.

---

### Step 5 — Generate TLS Certificates

WebRTC requires HTTPS. For local dev, self-signed certs are fine:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/key.pem \
  -out certs/cert.pem \
  -days 365 -nodes \
  -subj "/CN=localhost"
```

---

### Step 6 — Start PostgreSQL

```bash
# Option A — Docker (easiest)
docker compose up -d db

# Option B — Local Postgres already running on :5432
# Just make sure DB_HOST=127.0.0.1 in .env
```

---

### Step 7 — Run Database Migrations

```bash
# If using local Postgres (Docker handles this automatically):
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/001_init.sql
```

---

### Step 8 — Install Python Dependencies

```bash
uv sync
```

This creates a `.venv` folder automatically.

---

### Step 9 — Build the React Frontend

```bash
cd frontend/superadmin-react
npm install
npm run build
cd ../..
```

---

### Step 10 — Seed Admin Users

```bash
uv run python scripts/seed_admin.py
```

> Run this once after DB is up and `.env` is filled.

---

### Step 11 — Start the Server

```bash
uv run python app/server.py
```

On **first start**, InsightFace will auto-download `buffalo_l` (~200 MB) from the internet.  
This only happens once — cached at `pre_trained/insightface/`.

---

### Step 12 — Access the App

| URL | Purpose |
|-----|---------|
| `https://localhost:8000` | Login / Landing page |
| `https://localhost:8000/admin/dashboard` | Admin dashboard |
| `https://localhost:8000/super-admin/dashboard` | Super Admin dashboard |

> **Browser:** Accept the self-signed certificate warning on first visit (click "Advanced → Proceed").

---

## ⚡ Docker Quick Start (Full Stack)

If you want everything in one command:

```bash
docker compose up --build
```

> ⚠️ Note: `buffalo_l` downloads inside the container on first run — needs internet.  
> After rebuild, it re-downloads unless you add a volume for `pre_trained/`.

---

## 🔄 Frontend Hot Reload (Development)

```bash
# Terminal 1 — Backend
uv run python app/server.py

# Terminal 2 — Vite dev server
cd frontend/superadmin-react
npm run dev
```

Vite runs on `https://localhost:5174` and proxies API calls to the backend.

---

## 🧠 Project Architecture

```
secure-vu/
├── app/
│   ├── server.py        ← Main server (6000+ lines) — routes, WebRTC, YOLO, face rec
│   ├── faceid.py        ← InsightFace wrapper for face recognition
│   ├── liveness.py      ← Anti-spoofing liveness detection
│   ├── tracking.py      ← ByteTrack-based persistent object ID tracking
│   ├── bbox_smoother.py ← EMA bounding box smoothing
│   ├── auth.py          ← JWT creation & validation
│   ├── rbac.py          ← Role-based access control
│   ├── db.py            ← Async PostgreSQL (asyncpg)
│   └── middleware.py    ← Auth middleware
├── frontend/superadmin-react/   ← Vite + React dashboard
├── models/yolo/                 ← YOLO weights (owner provides)
├── models/arcface/face_db/      ← Face embeddings (created at runtime)
├── pre_trained/insightface/     ← InsightFace buffalo_l (auto-downloaded)
├── migrations/                  ← PostgreSQL schema SQL files
├── scripts/                     ← Utility scripts (seed, benchmark, train)
├── certs/                       ← TLS certificates
├── config/                      ← Runtime JSON config (auto-generated)
└── static/                      ← Legacy HTML client (client.html)
```

---

## ⚙️ Key `.env` Variables to Know

| Variable | Default | What It Does |
|----------|---------|--------------|
| `MODEL_SELECT` | `6` | Which AI mode to run (6 = Production with face rec) |
| `MODEL_RUNTIME` | `pytorch` | `pytorch` or `tensorrt` |
| `YOLO_MIN_CONF` | `0.20` | Detection confidence threshold |
| `FACE_EVERY_N_FRAMES` | `5` | How often face recognition runs |
| `BBOX_SMOOTHING_MODE` | `fixed` | `fixed` or `adaptive` bbox smoothing |
| `EVENT_CLIP_ENABLE` | `1` | Record event clips on violations |
| `WORK_TIMER_ENABLE` | `1` | Per-person work time tracking |

---

## 🤖 MODEL_SELECT Reference

| Value | Mode | Models Used |
|-------|------|-------------|
| `1` | General detection | YOLO11m only |
| `2` | Face detection | YOLOv8n-face |
| `3` | Fire & smoke | fire_smoke.pt |
| `6` | **Production** (recommended) | YOLO11m + InsightFace |
| `7` | Full package | YOLO11m + all specialized + InsightFace |

---

## 🛑 Common Issues & Fixes

| Problem | Fix |
|---------|-----|
| Server exits immediately at startup | `secure_cv_best.pt` is missing from `models/yolo/` |
| `buffalo_l` not found error | Run with internet on first start — it auto-downloads |
| WebRTC won't connect | Check `certs/cert.pem` and `certs/key.pem` exist |
| "No faces detected" during enrollment | Ensure good lighting and face is front-facing |
| DB connection refused | Start Postgres: `docker compose up -d db` |
| Frontend shows blank/404 | Run `npm run build` inside `frontend/superadmin-react/` |
| `nvcc: command not found` | Not needed — CUDA Toolkit not required for inference |

---

## 🔧 Useful Commands

```bash
# Reset database (DELETES ALL DATA)
docker compose down -v

# Rebuild frontend
cd frontend/superadmin-react && npm run build

# Check server logs (Docker)
docker compose logs -f app

# Lint Python
uv run ruff check .

# Run benchmark
uv run python scripts/benchmark_runtime.py
```

---

## 📞 Contact / Questions

Reach out to **Shivam Raina** (`shivam.raina@mobcoder.com`) for:
- `secure_cv_best.pt` model weights
- RTSP camera credentials
- Production `.env` secrets
- Pre-enrolled face database backup (`face_db.npz`)
