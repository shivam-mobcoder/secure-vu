# SecureVu — Developer Handoff Guide

> **Branch:** `POC`  
> **Repo:** https://github.com/shivam-mobcoder/secure-vu

Welcome guide for taking over the SecureVu POC stack (WebRTC, YOLO, InsightFace, Postgres alerts, recording, MLflow).

---

## Quick start (with owner USB package)

```bash
git clone https://github.com/shivam-mobcoder/secure-vu.git
cd secure-vu
git checkout POC

# Copy owner USB files into handoff/:
#   secure_cv_best.pt, face_db.npz (optional), env-template.txt (optional)

bash handoff/install-from-handoff.sh
bash scripts/download_buffalo.sh
# Edit .env — RTSP_URL_1..4

uv sync --group mlops
docker compose up -d db
# Fresh DB: migrations auto-apply. Existing volume:
# psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/002_poc.sql

mkdir -p certs && openssl req -x509 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=localhost"

cd frontend/superadmin-react && npm install && npm run build && cd ../..
uv run python scripts/seed_admin.py
uv run python app/server.py
```

| URL | Purpose |
|-----|---------|
| `https://localhost:8000` | Login |
| `https://localhost:8000/admin/dashboard/live-feed` | Live feed + alerts |
| `https://localhost:8000/admin/dashboard/playback` | Recording segments |
| `http://localhost:5000` | MLflow UI (`docker compose up mlflow`) |

---

## Owner supplies vs you install

### Owner must provide (or include on USB in `handoff/`)

| Item | Target path after `install-from-handoff.sh` |
|------|-----------------------------------------------|
| `secure_cv_best.pt` | `models/yolo/secure_cv_best.pt` |
| RTSP credentials | `.env` → `RTSP_URL_1` … `RTSP_URL_4` |
| Secrets | `.env` (or `handoff/env-template.txt`) |
| `face_db.npz` *(optional)* | `models/arcface/face_db/face_db.npz` |

See [OWNER-SUPPLIES.txt](OWNER-SUPPLIES.txt).

### You install / auto-setup

| Item | Command |
|------|---------|
| Python deps + MLflow | `uv sync --group mlops` |
| Postgres + schema | `docker compose up -d db` (+ `002_poc.sql` if needed) |
| Full Docker stack | `docker compose up --build` |
| Frontend | `npm install && npm run build` |
| InsightFace `buffalo_l` | Auto-downloads on first server start (internet) |
| TLS (dev) | `openssl` (see CHECKLIST.md) |
| Users | `uv run python scripts/seed_admin.py` |

---

## Hardware reference (4-cam POC)

| Component | Spec |
|-----------|------|
| GPU | NVIDIA RTX 2080 Ti (11 GB) recommended |
| RAM | 64 GB (reference) |
| OS | Ubuntu 22.04 + CUDA for GPU inference |
| macOS | CPU or Docker/Linux for `onnxruntime-gpu` |

---

## Step-by-step (no USB script)

### 1. Clone

```bash
git clone https://github.com/shivam-mobcoder/secure-vu.git
cd secure-vu
git checkout POC
```

### 2. Environment

```bash
cp .env.example .env
# Or: cp handoff/env-template.example.txt .env
```

Required fields: `DB_PASS`, `JWT_SECRET`, account passwords, `ADMIN_CUSTOMER` (for seed script), `RTSP_URL_*`.

Generate JWT:

```bash
python3 -c "import secrets; print(secrets.token_hex(64))"
```

### 3. YOLO weights

```bash
mkdir -p models/yolo
cp handoff/secure_cv_best.pt models/yolo/
```

Server **exits** if this file is missing.

### 4. Optional face database

```bash
mkdir -p models/arcface/face_db
cp handoff/face_db.npz models/arcface/face_db/
```

### 5. TLS certificates

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -nodes -subj "/CN=localhost"
```

### 6. Database

```bash
docker compose up -d db
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/001_init.sql
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/002_poc.sql
```

Docker applies both migrations on **first** Postgres volume only.

### 7. Dependencies & UI

```bash
uv sync --group mlops
cd frontend/superadmin-react && npm install && npm run build && cd ../..
uv run python scripts/seed_admin.py
uv run python app/server.py
```

First start downloads InsightFace `buffalo_l` to `pre_trained/insightface/models/buffalo_l/` (~326 MB).

---

## Docker full stack

```bash
bash handoff/install-from-handoff.sh
docker compose up --build
```

`docker-compose.yml` runs **db**, **mlflow** (:5000), and **app** (:8000).  
Mount `./models` for YOLO; `buffalo_l` downloads inside the container unless you add a `pre_trained/` volume.

---

## POC features (branch `POC`)

- Loitering + motion alerts  
- Postgres alert history (`GET /api/alerts`)  
- Continuous recording (`GET /api/recordings`) + Playback UI  
- Camera health API  
- MLflow config tracking — see [docs/MLFLOW.md](../docs/MLFLOW.md)  
- Demo script — [docs/DEMO_SCRIPT.md](../docs/DEMO_SCRIPT.md)

---

## Key `.env` variables (POC default)

| Variable | Default | Notes |
|----------|---------|-------|
| `MODEL_SELECT` | `6` | YOLO11m + InsightFace |
| `YOLO_INPUT_WIDTH/HEIGHT` | `1280` | POC accuracy profile |
| `FACE_EVERY_N_FRAMES` | `3` | |
| `FACE_RECOGNITION_THRESHOLD` | `0.25` | |
| `MOTION_ENABLE` | `1` | OpenCV motion gate |
| `LINGER_SECONDS` | `30` | Loitering |
| `CONTINUOUS_RECORDING_ENABLE` | `1` | 5-min segments |
| `MLFLOW_ENABLE` | `1` | Set `0` if no MLflow server |

---

## Common issues

| Problem | Fix |
|---------|-----|
| Server exits at startup | Missing `models/yolo/secure_cv_best.pt` |
| InsightFace errors | First run needs internet for `buffalo_l` |
| Alerts don't persist | Apply `migrations/002_poc.sql` |
| Blank admin UI | `npm run build` in `frontend/superadmin-react` |
| `seed_admin.py` fails | Set `ADMIN_CUSTOMER` in `.env` |
| WebRTC fails | Check `certs/cert.pem` and `certs/key.pem` |

---

## Useful commands

```bash
uv run --group mlops scripts/benchmark_config.py --preset all
uv run --group mlops scripts/train_yolo.py
docker compose logs -f app
uv run ruff check .
```

---

## More documentation

- [../README.md](../README.md) — project quick start  
- [CHECKLIST.md](CHECKLIST.md) — tick-list setup  
- [../docs/README.md](../docs/README.md) — full doc index  

Contact repo owner for `secure_cv_best.pt`, production RTSP URLs, and filled `env-template.txt` on USB.
