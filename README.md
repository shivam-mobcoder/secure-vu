# � SecureVu — AI-Powered CCTV Surveillance Platform

Real-time person detection, face recognition, and rule-based alerting using **YOLOv8**, **ArcFace (InsightFace)**, and **WebRTC** — all served over a single HTTPS endpoint.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Real-time Detection** | YOLOv8 single-class person model with optional multi-class support |
| **Face Recognition** | ArcFace / InsightFace with per-client scoped face databases |
| **Persistent Tracking** | ByteTrack + EMA smoothing for stable, flicker-free bounding boxes |
| **Work Timers** | Per-person timers with cross-camera handoff via face embeddings |
| **ROI / Zone / Line Rules** | Configurable intrusion zones, virtual lines, parking rules |
| **Event Clips** | Automatic MP4 clip capture on rule violations |
| **WebRTC Streaming** | Ultra low-latency HD video (1280×720 @ 30 fps) |
| **Multi-tenant RBAC** | Super Admin → Admin → Member role hierarchy with JWT auth |
| **React Dashboard** | Modern Vite + React SPA for all user roles |

---

## 🏗️ Project Structure

```text
secure-vu/
├── app/                        # Backend (Python / aiohttp)
│   ├── server.py               # Main server — routes, WebRTC, YOLO, drawing
│   ├── db.py                   # Async PostgreSQL (asyncpg)
│   ├── auth.py                 # JWT token creation & validation
│   ├── rbac.py                 # Role-based access control
│   ├── faceid.py               # FaceID manager (InsightFace wrapper)
│   ├── liveness.py             # Anti-spoofing liveness detection
│   ├── tracking.py             # PIDTracker — persistent object IDs
│   └── middleware.py           # Auth middleware for aiohttp
├── frontend/
│   └── superadmin-react/       # Vite + React + TailwindCSS dashboard
├── models/
│   ├── yolo/                   # YOLO weights (secure_cv_best.pt)
│   └── arcface/face_db/        # Per-client face embedding databases
├── pre_trained/insightface/    # InsightFace model pack (buffalo_l)
├── migrations/
│   └── 001_init.sql            # PostgreSQL schema (clients, users, cameras)
├── certs/                      # Self-signed TLS certs for HTTPS/WebRTC
├── config/                     # Runtime flags (JSON, auto-generated)
├── static/                     # Legacy HTML client
├── scripts/                    # Utility / test scripts
├── docker-compose.yml          # Full-stack orchestration (DB + App)
├── Dockerfile                  # App container
├── pyproject.toml              # Python project & uv config
└── .env                        # Environment variables (secrets, tuning)
```

---

## 📋 Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Python** | 3.10.x | Backend runtime (must be `>=3.10, <3.11`) |
| **uv** | latest | Python package manager (replaces pip/venv) |
| **Node.js** | 18+ | Frontend build toolchain |
| **PostgreSQL** | 15+ | Primary database |
| **NVIDIA GPU + CUDA** | 12.x | GPU acceleration (optional, falls back to CPU) |
| **Docker & Docker Compose** | latest | For containerized deployment |

---

## 🚀 Setup from Scratch (Local Development)

### Step 1 — Clone the Repository

```bash
git clone <repo-url> secure-vu
cd secure-vu
```

### Step 2 — Configure Environment Variables

```bash
cp .env.example .env   # if .env.example exists, otherwise edit .env directly
```

Edit `.env` with your values:

```dotenv
# PostgreSQL
DB_USER=cctv_user
DB_PASS=StrongPassword123
DB_NAME=cctv_platform
DB_HOST=127.0.0.1

# JWT Secret (generate a new one for production)
JWT_SECRET=<your-random-64-byte-hex>

# Default accounts (created on first startup)
SUPER_EMAIL=super@platform.com
SUPER_PASSWORD=SuperAdmin@123
ADMIN_EMAIL=admin@internal.com
ADMIN_PASSWORD=AdminStrong123

# RTSP Camera URLs (comma-separated per camera ID)
# RTSP_URL_1=rtsp://admin:pass@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
# RTSP_URL_2=rtsp://admin:pass@192.168.1.101:554/cam/realmonitor?channel=1&subtype=0
```

### Step 3 — Start PostgreSQL

**Option A — Docker (recommended):**

```bash
docker-compose up -d db
```

**Option B — Local Postgres:**

Ensure PostgreSQL 15+ is running on `localhost:5432`.

### Step 4 — Run Database Migrations

```bash
psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/001_init.sql
```

> **Note:** If using Docker Compose, the migration runs automatically on the first `docker-compose up` via the `docker-entrypoint-initdb.d` mount. You only need to run this manually for a standalone Postgres instance.

This creates the following tables:

| Table | Purpose |
|-------|---------|
| `clients` | Multi-tenant organizations |
| `users` | User accounts (super_admin, admin, member) |
| `cameras` | Camera records per client |
| `user_cameras` | Many-to-many user ↔ camera access |

### Step 5 — Generate TLS Certificates

WebRTC requires HTTPS. Generate self-signed certs for local development:

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -nodes -subj "/CN=localhost"
```

### Step 6 — Install Python Dependencies

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync all dependencies (creates .venv automatically)
uv sync
```

### Step 7 — Download / Place AI Models

Ensure the following model files are present:

```text
models/yolo/secure_cv_best.pt          # Custom YOLO weights
pre_trained/insightface/models/buffalo_l/   # InsightFace model pack
```

> If models are not in the repo, download them from your team's shared storage and place them in the paths above.

### Step 8 — Build the React Frontend

```bash
cd frontend/superadmin-react
npm install
npm run build
cd ../..
```

> The built assets are served directly by the Python backend — no separate frontend server needed in production.

### Step 9 — Start the Server

```bash
uv run python app/server.py
```

The server starts on `https://localhost:8000` by default.

### Step 10 — Access the Application

| URL | Purpose |
|-----|---------|
| `https://localhost:8000` | Landing page (Login / Signup) |
| `https://localhost:8000/admin/dashboard` | Admin dashboard |
| `https://localhost:8000/super-admin/dashboard` | Super Admin dashboard |

> **Browser:** Accept the self-signed certificate warning on first visit.

---

## ⚡ Quick Start (Docker — Full Stack)

If you just want everything running with one command:

```bash
docker-compose up --build
```

This starts both `db` (PostgreSQL) and `app` (Python server). Migrations run automatically on first boot.

---

## 🔄 Frontend Development (Hot Reload)

For frontend development with hot reload:

```bash
# Terminal 1 — Backend
uv run python app/server.py

# Terminal 2 — Vite dev server (proxies API calls to backend)
cd frontend/superadmin-react
npm run dev
```

The Vite dev server runs on `https://localhost:5174` and proxies `/offer`, `/ws`, `/api/*` to the backend.

---

## ⚙️ Key Configuration

### Detection & Tracking Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `YOLO_MIN_CONF` | `0.25` | Minimum YOLO detection confidence |
| `YOLO_PROCESS_EVERY_N_FRAMES` | `1` | Process every Nth frame (1 = every frame) |
| `YOLO_INPUT_WIDTH` / `HEIGHT` | `1280` | YOLO inference resolution |
| `FACE_EVERY_N_FRAMES` | `5` | Run face recognition every Nth frame |
| `BBOX_SMOOTH_ALPHA` | `0.75` | EMA smoothing weight (higher = smoother) |
| `BBOX_JUMP_THRESH` | `1.5` | Jump snap threshold (prevents sliding on ID swaps) |

### ByteTrack Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `BT_MATCH_THRESH` | `0.85` | IoU matching threshold for track association |
| `BT_TRACK_BUFFER` | `90` | Frames to keep lost tracks alive |
| `BT_TRACK_HIGH_THRESH` | `0.35` | Confidence to create new tracks |
| `BT_TRACK_LOW_THRESH` | `0.15` | Confidence floor for rescue pool |

### Server & Streaming

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `SERVER_CAMERA_FPS` | `30` | Target FPS for focus view |
| `GRID_CAMERA_FPS` | `30` | Target FPS for grid view |
| `WEBRTC_VIDEO_KBPS` | `6000` | WebRTC video bitrate (kbps) |

### Work Timer & Alerts

| Variable | Default | Description |
|----------|---------|-------------|
| `WORK_TIMER_ENABLE` | `1` | Enable per-person work timers |
| `WORK_TIMER_REQUIRE_ROI` | `0` | Only count time inside ROI |
| `EVENT_CLIP_ENABLE` | `1` | Enable event clip recording |
| `EVENT_CLIP_SECONDS` | `8` | Total clip length (seconds) |

---

## 🔧 Maintenance

| Task | Command |
|------|---------|
| **Reset database** | `docker-compose down -v` ⚠️ *deletes all data* |
| **Re-run migrations** | `psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/001_init.sql` |
| **Rebuild frontend** | `cd frontend/superadmin-react && npm run build` |
| **Check server logs** | `docker-compose logs -f app` |
| **Lint Python code** | `uv run ruff check .` |
| **Dead code audit** | `uv run vulture .` |

---

## 📝 License

**Proprietary** — Internal use only for SecureVu project.
