# ✅ SecureVU — New Developer Setup Checklist

Work through this list top to bottom. Check each item as you complete it.

---

## 📥 From Owner (Request These First)

- [ ] `models/yolo/secure_cv_best.pt` — custom YOLO model weights (**mandatory**)
- [ ] RTSP camera URLs (for the site cameras)
- [ ] DB password & JWT secret values (or generate your own for dev)
- [ ] *(Optional)* Pre-enrolled face database: `models/arcface/face_db/face_db.npz`
- [ ] *(Optional)* Production TLS certs

---

## 🛠️ One-Time Setup

### Environment
- [ ] `git clone https://github.com/shivam-mobcoder/secure-vu.git`
- [ ] `git checkout feature/tensorrt-runtime`
- [ ] `cp .env.example .env`
- [ ] Fill in `.env` — DB_PASS, JWT_SECRET, account passwords, RTSP URLs

### Prerequisites
- [ ] Python 3.10.x installed (`python3 --version`)
- [ ] `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [ ] Node.js 18+ installed (`node --version`)
- [ ] Docker & Docker Compose installed (for DB)

### Models
- [ ] `mkdir -p models/yolo` and copy `secure_cv_best.pt` into it
- [ ] *(Auto)* InsightFace `buffalo_l` — downloads on first server start

### Certificates
- [ ] Run `openssl` command to generate `certs/cert.pem` + `certs/key.pem`
  ```bash
  mkdir -p certs
  openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem \
    -days 365 -nodes -subj "/CN=localhost"
  ```

### Database
- [ ] `docker compose up -d db` (starts PostgreSQL)
- [ ] Migrations apply automatically on first Docker boot
- [ ] *(Manual only)* `psql ... -f migrations/001_init.sql`

### Python Dependencies
- [ ] `uv sync`

### Frontend
- [ ] `cd frontend/superadmin-react && npm install && npm run build`

### Seed Users
- [ ] `uv run python scripts/seed_admin.py`

---

## 🚀 Launch

- [ ] `uv run python app/server.py`
- [ ] Open `https://localhost:8000` in browser
- [ ] Accept self-signed cert warning
- [ ] Log in with `SUPER_EMAIL` / `SUPER_PASSWORD` from `.env`

---

## ✔️ Verify Everything Works

- [ ] Dashboard loads without errors
- [ ] RTSP camera streams appear in grid view
- [ ] Person detection bounding boxes appear
- [ ] Face enrollment works (Admin → Face Recognition → Enroll)
- [ ] Enrolled person is recognized in live feed

---

## 🆘 Still Stuck?

→ See `README-HANDOFF.md` in this folder for full detail  
→ See `../README.md` for full project documentation  
→ Contact Shivam Raina: `shivam.raina@mobcoder.com`
