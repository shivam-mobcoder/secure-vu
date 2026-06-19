# SecureVu — AI-Powered CCTV Surveillance Platform

Real-time person detection, face recognition, rule-based alerting, and continuous recording using **YOLO**, **InsightFace (ArcFace)**, and **WebRTC** — served over a single HTTPS endpoint.

**Active branch:** `POC` — feature-complete demo stack with alert persistence, recording segments, and MLflow configuration tracking.

---

## Features

| Feature | Details |
|---------|---------|
| **Live multi-cam WebRTC** | 2–4 RTSP cameras, HD streaming (1280×720) |
| **Person detection** | Custom YOLO weights (`secure_cv_best.pt`) + ByteTrack |
| **Face recognition** | InsightFace ArcFace with per-client face databases |
| **Rules engine** | Zone intrusion, virtual lines, crowd limits, parking dwell, loitering |
| **Motion alerts** | OpenCV background-subtraction motion gate |
| **Event clips** | MP4 clips on rule violations with review links |
| **Alert history** | Postgres-backed alerts survive browser refresh |
| **Continuous recording** | 5-minute MP4 segments indexed in Postgres |
| **Camera health** | Online / stale / offline status API |
| **Work timers** | Per-person dwell time on bounding boxes |
| **MLflow tracking** | Env thresholds, model weights, rules JSON, training runs |
| **React dashboard** | Face enrollment, live feed, alerts sidebar, playback list |
| **Multi-tenant RBAC** | Super Admin → Admin → Member with JWT auth |

---

## Project Structure

```text
secure-vu/
├── app/
│   ├── server.py           # Main aiohttp server (WebRTC, YOLO, rules, APIs)
│   ├── db.py               # Async PostgreSQL helpers
│   ├── recording.py        # Continuous segment writer + camera health
│   ├── ml_tracking.py      # MLflow deployment/training snapshots
│   ├── faceid.py           # InsightFace wrapper
│   ├── tracking.py         # PIDTracker
│   ├── auth.py / rbac.py / middleware.py
├── frontend/superadmin-react/   # Vite + React admin UI
├── models/yolo/            # YOLO weights (not in git — place locally)
├── models/arcface/face_db/ # Face embedding databases
├── config/
│   ├── camera_rules.json   # Per-camera zones, lines, crowd rules
│   └── runtime_flags.json  # Runtime toggles (auto-generated)
├── migrations/
│   ├── 001_init.sql        # Core schema (clients, users, cameras)
│   └── 002_poc.sql         # Alerts + recording_segments tables
├── scripts/
│   ├── train_yolo.py       # YOLO fine-tuning + MLflow logging
│   ├── benchmark_config.py # Threshold profile benchmarks → MLflow
│   └── collect_stats.py    # GPU/CPU stats collector
├── docs/                   # Guides (see docs/README.md)
├── docker-compose.yml      # PostgreSQL + MLflow + app
├── Dockerfile
├── pyproject.toml          # uv project config (Python 3.10)
├── requirements.txt        # Pinned deps (uv export; pip-compatible)
├── uv.lock                 # uv lockfile
└── .env                    # Secrets and tuning (not committed)
```

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | 12-minute POC demo script |
| [docs/MLFLOW.md](docs/MLFLOW.md) | Experiment and config tracking |
| [docs/CCTV_INTEGRATION_GUIDE.md](docs/CCTV_INTEGRATION_GUIDE.md) | RTSP camera setup |
| [docs/DEPLOYMENT_GUIDE_SUMMARY.md](docs/DEPLOYMENT_GUIDE_SUMMARY.md) | Deployment quick reference |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.10.x (`>=3.10, <3.11`) | Backend runtime |
| **uv** | latest | Recommended package manager |
| **Node.js** | 18+ | Frontend build |
| **PostgreSQL** | 15+ | Database |
| **NVIDIA GPU + CUDA** | 12.x | Recommended for 4-cam POC |
| **Docker Compose** | latest | Full-stack deployment |

> **Platform note:** `onnxruntime-gpu` wheels are Linux/Windows x86_64 only. On macOS use CPU inference or develop inside Docker/Linux.

---

## Quick Start (Docker — recommended)

```bash
git clone <repo-url> secure-vu
cd secure-vu
git checkout POC

cp .env.example .env
# Edit .env: DB credentials, JWT_SECRET, RTSP_URL_1..4

mkdir -p certs models/yolo recordings mlruns
# Place models/yolo/secure_cv_best.pt and InsightFace pack locally

docker compose up --build
```

| Service | URL |
|---------|-----|
| App (HTTPS) | `https://localhost:8000` |
| MLflow UI | `http://localhost:5000` |
| PostgreSQL | `localhost:5432` |

Migrations `001_init.sql` and `002_poc.sql` run automatically on **first** Postgres boot. For an existing database volume:

```bash
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/002_poc.sql
```

Build the React UI before or after first Docker start:

```bash
cd frontend/superadmin-react && npm install && npm run build
```

---

## Local Development Setup

### 1. Environment

```bash
cp .env.example .env
```

Key POC profile variables (see `.env.example` for full list):

```dotenv
MODEL_SELECT=6
MODEL_RUNTIME=pytorch
YOLO_INPUT_WIDTH=1280
YOLO_INPUT_HEIGHT=1280
YOLO_MIN_CONF=0.18
FACE_RECOGNITION_THRESHOLD=0.25
ANALYTICS_CAMERA_IDS=1,2,3,4
PROCESSING_FPS=15
MLFLOW_ENABLE=1
MLFLOW_TRACKING_URI=http://localhost:5000
```

### 2. Install Python dependencies

**Option A — uv (recommended):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --group mlops    # includes MLflow; use Linux/GPU host for onnxruntime-gpu
```

**Option B — pip:**

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> `requirements.txt` is generated via `uv export --group mlops`. Regenerate after changing `pyproject.toml`:

```bash
uv export --format requirements-txt --no-dev --group mlops -o requirements.txt
```

### 3. Database

```bash
docker compose up -d db
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/001_init.sql
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/002_poc.sql
```

### 4. TLS certificates

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -nodes -subj "/CN=localhost"
```

### 5. Models

```text
models/yolo/secure_cv_best.pt
pre_trained/insightface/models/buffalo_l/
```

### 6. Frontend build

```bash
cd frontend/superadmin-react
npm install
npm run build
cd ../..
```

### 7. Start services

```bash
# Terminal 1 — MLflow (optional; or use docker compose up mlflow)
mlflow server --host 127.0.0.1 --port 5000 \
  --backend-store-uri ./mlruns --default-artifact-root ./mlruns

# Terminal 2 — Backend
uv run python app/server.py
```

### 8. Access

| URL | Purpose |
|-----|---------|
| `https://localhost:8000` | Landing / auth |
| `https://localhost:8000/admin/dashboard/live-feed` | Live feed + alerts |
| `https://localhost:8000/admin/dashboard/playback` | Recording segments |
| `http://localhost:5000` | MLflow experiment UI |

---

## MLflow (configuration tracking)

Tracks model weights, env thresholds, and `camera_rules.json` on every server start and config change.

```bash
# Training run + model registry
uv run --group mlops scripts/train_yolo.py

# Benchmark threshold profiles
uv run --group mlops scripts/benchmark_config.py --preset all
```

Set `MLFLOW_ENABLE=0` to disable tracking without affecting the VMS.

See [docs/MLFLOW.md](docs/MLFLOW.md) for details.

---

## Key API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/alerts` | GET | Alert history (Postgres) |
| `/api/recordings` | GET | Recording segment list |
| `/api/cameras/health` | GET | Camera online/stale/offline |
| `/rules` | GET/POST | Per-camera rule configuration |
| `/ws` | WebSocket | Live alert stream |
| `/offer` | POST | WebRTC signaling |

---

## Frontend Development (hot reload)

```bash
# Terminal 1
uv run python app/server.py

# Terminal 2
cd frontend/superadmin-react && npm run dev
```

Vite dev server: `https://localhost:5174` (proxies API to backend).

---

## Maintenance

| Task | Command |
|------|---------|
| Reset database | `docker compose down -v` (deletes all data) |
| Apply POC migration | `psql ... -f migrations/002_poc.sql` |
| Rebuild frontend | `cd frontend/superadmin-react && npm run build` |
| Regenerate requirements | `uv export --format requirements-txt --no-dev --group mlops -o requirements.txt` |
| App logs | `docker compose logs -f app` |
| Lint | `uv run ruff check .` |

---

## License

**Proprietary** — Internal use only for SecureVu project.
