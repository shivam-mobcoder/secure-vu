# 🚀 AI Surveillance System (YOLO + ArcFace + WebRTC)

Real-time person & animal detection, face recognition, and ROI-based **Professional CCTV Monitoring** using YOLOv8, ArcFace, and WebRTC.

---

## ✨ Features

- **Real-time Detection**: *People + 17 animal types* (cat, dog, bird, snake, etc.)
- **Face Recognition**: ArcFace with persistent **PostgreSQL** identity database.
- **ROI Alerts**: Configurable zones with entry/exit logic handled on the edge.
- **WebRTC Streaming**: Ultra low-latency video via hardware-accelerated transcoding.
- **Modern Stack**: Fully containerized with **Docker** and managed by **uv**.

---

## 🏗️ Project Structure

```text
object-detection-main/
├── app/                        # Main Backend Logic
│   ├── server.py               # Core Aiohttp/FastAPI server
│   ├── db.py                   # Async PostgreSQL integration
│   └── auth.py                 # JWT & RBAC Authentication
├── static/                     # Legacy HTML Client (Internal use)
├── frontend/                   # Modern React Dashboards
├── models/                     # AI Model weights and databases
├── migrations/                 # Database Schema (Init SQL)
├── Dockerfile                  # App Container definition
└── docker-compose.yml          # Full-stack orchestration
```

---

## ⚡ Quick Start (The Docker Way)

The *fastest* and *most reliable* way to start the system is using Docker. This handles the database, Python environment, and GPU dependencies automatically.

### 1. Start the System
From the project root, run:

```bash
docker-compose up --build
```

### 2. Access the Dashboard
- **Main Interface**: `https://localhost:8000`
- **Super Admin**: `https://localhost:8000/super-admin/dashboard`

---

## 🛠️ Developer Setup (Local UV Mode)

If you prefer to run the application directly on your host machine for debugging:

### 1. Setup Environment
Ensure you have **uv** installed, then run:

```bash
# Sync all dependencies into a local venv
uv sync

# Initialize environment variables
cp .env.example .env  # Update with your DB credentials
```

### 2. Start PostgreSQL
Ensure a local Postgres instance is running or use the Docker DB:
```bash
docker-compose up -d db
```

### 3. Launch App
```bash
uv run python app/server.py
```

---

## ⚙️ Configuration

| Variable | Type | Description |
|----------|------|-------------|
| **`USE_GPU`** | *bool* | Enable NVIDIA acceleration (requires NVIDIA Docker Toolkit) |
| **`DB_HOST`** | *str* | Database address (use `db` if inside Docker) |
| **`PORT`** | *int* | Application port (default: `8000`) |

---

## 🔧 Maintenance Commands

- **Reset Database**: `docker-compose down -v` *(Warning: Deletes all data)*
- **Check Logs**: `docker-compose logs -f app`
- **Run Linting**: `uv run ruff check .`
- **Dead Code Audit**: `uv run vulture .`

---

## 📝 License

**Proprietary** – *Internal use only for Shivam Raina / SecureView project.*
