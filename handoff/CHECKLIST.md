# SecureVu — New Developer Setup Checklist

Branch: **`POC`**. Work top to bottom.

---

## From owner (USB / `handoff/` folder)

- [ ] `handoff/secure_cv_best.pt` — **mandatory**
- [ ] `handoff/face_db.npz` — optional pre-enrolled faces
- [ ] `handoff/env-template.txt` — optional filled `.env` (secrets + RTSP)
- [ ] RTSP camera URLs if not in env file

---

## Repo setup

- [ ] `git clone https://github.com/shivam-mobcoder/secure-vu.git`
- [ ] `git checkout POC`
- [ ] `bash handoff/install-from-handoff.sh`  
      *(or manually copy `.pt` / `.npz` — see README-HANDOFF.md)*
- [ ] Edit `.env` — `RTSP_URL_1` … `RTSP_URL_4`, passwords

---

## Prerequisites

- [ ] Python **3.10.x** (`python3 --version`)
- [ ] `uv` — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Node.js **18+**
- [ ] Docker Compose (for Postgres / full stack)
- [ ] NVIDIA driver + CUDA (Linux GPU; optional on macOS)

---

## Install

- [ ] `uv sync --group mlops`
- [ ] TLS certs:
  ```bash
  mkdir -p certs
  openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem \
    -days 365 -nodes -subj "/CN=localhost"
  ```
- [ ] `docker compose up -d db` *(or `docker compose up --build` for full stack)*
- [ ] If DB volume already existed:  
      `psql -h 127.0.0.1 -U cctv_user -d cctv_platform -f migrations/002_poc.sql`
- [ ] `cd frontend/superadmin-react && npm install && npm run build`
- [ ] `uv run python scripts/seed_admin.py`  
      *(requires `ADMIN_CUSTOMER` in `.env`)*

---

## Launch

- [ ] `uv run python app/server.py`  
      *(first run downloads InsightFace `buffalo_l` — needs internet)*
- [ ] Open `https://localhost:8000` — accept self-signed cert
- [ ] Log in with `SUPER_EMAIL` / `SUPER_PASSWORD` from `.env`

---

## Verify POC

- [ ] Live feed: `/admin/dashboard/live-feed`
- [ ] RTSP streams + person bounding boxes
- [ ] Face recognition (pre-shipped `face_db.npz` or enroll in UI)
- [ ] Refresh browser — alerts still in sidebar (Postgres)
- [ ] Playback page shows recording segments
- [ ] MLflow UI at `http://localhost:5000` (if Docker mlflow running)

---

## Stuck?

→ [README-HANDOFF.md](README-HANDOFF.md)  
→ [../README.md](../README.md)  
→ [../docs/DEMO_SCRIPT.md](../docs/DEMO_SCRIPT.md)
