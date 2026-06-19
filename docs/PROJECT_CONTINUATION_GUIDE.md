# 🚀 Project Continuation & Migration Guide

Use this guide to set up the project on a different machine while preserving progress.

**Active branch:** `POC`

## 💾 Files You MUST Move Manually

These are **not** in Git (too large or sensitive). Copy via USB or secure storage:

1. **`.env`** — secrets and RTSP URLs (copy from `.env.example`)
2. **`models/`** — YOLO weights (`secure_cv_best.pt`) and ArcFace `face_db/`
3. **`pre_trained/`** — InsightFace buffalo_l pack
4. **`datasets/`** — training images (if retraining)
5. **`certs/`** — TLS certs for HTTPS/WebRTC
6. **`recordings/`** — continuous recording segments (optional)
7. **`mlruns/`** — MLflow experiment data (optional)

## 🛠️ Step-by-Step Setup on New Machine

### 1. Clone the Repository

```bash
git clone <repo-url>
cd secure-vu
git checkout POC
```

### 2. Restore Manual Files

Place `models/`, `pre_trained/`, `.env`, and `certs/` in the repo root.

### 3. Install Dependencies

Requires **Python 3.10.x** and **uv** (or pip).

```bash
# Recommended (includes MLflow)
uv sync --group mlops

# Or pip
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

> On macOS, `onnxruntime-gpu` may not install — use Docker/Linux for GPU inference.

### 4. Setup Database

**Keep existing data** (export from old machine):

```bash
pg_dump -U cctv_user cctv_platform > db_backup.sql
# New machine:
psql -U cctv_user -d cctv_platform -f db_backup.sql
```

**Fresh install:**

```bash
docker compose up -d db
psql -U cctv_user -d cctv_platform -f migrations/001_init.sql
psql -U cctv_user -d cctv_platform -f migrations/002_poc.sql
```

Docker Compose runs both migrations on **first** Postgres boot only. Existing volumes need manual `002_poc.sql`.

### 5. Build Frontend

```bash
cd frontend/superadmin-react
npm install
npm run build
cd ../..
```

### 6. Run

**Docker (full stack — Postgres + MLflow + app):**

```bash
docker compose up --build
```

**Local dev:**

```bash
uv run python app/server.py
```

| URL | Purpose |
|-----|---------|
| `https://localhost:8000` | App |
| `http://localhost:5000` | MLflow UI |

## 🔍 Troubleshooting Checklist

- [ ] Python **3.10.x** (not 3.11+)
- [ ] NVIDIA drivers + CUDA if using GPU on Linux
- [ ] Write access to `event_clips/`, `recordings/`, `tracking/`
- [ ] `002_poc.sql` applied if alert history / playback APIs fail
- [ ] Frontend rebuilt after pulling UI changes
- [ ] `MLFLOW_ENABLE=0` if MLflow server is not running (optional)

See also [MLFLOW.md](MLFLOW.md) and [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
