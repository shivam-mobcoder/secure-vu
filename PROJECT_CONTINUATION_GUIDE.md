# 🚀 Project Continuation & Migration Guide

Use this guide to set up the project on a different laptop while preserving all progress.

## 💾 Files You MUST Move Manually
These files are **NOT** in Git because they are too large or sensitive. You must copy them via a USB drive or cloud storage:

1.  **`.env`**: Your local configuration and secrets.
2.  **`models/`**: All pre-trained and custom YOLO weights.
3.  **`pre_trained/`**: InsightFace model packs (buffalo_l).
4.  **`datasets/`**: (If needed) Your captured training images. **Note**: You have created `datasets_backup.zip` (2.2GB) which is ready for Google Drive upload.
5.  **`certs/`**: Your self-signed TLS certificates for HTTPS/WebRTC.

## 🛠️ Step-by-Step Setup on New Machine

### 1. Clone the Repository
```bash
git clone <repo-url>
cd secure-vu
git checkout dev  # or mob-sr
```

### 2. Restore Manual Files
Paste the `models/`, `pre_trained/`, `.env`, and `certs/` folders into the root directory.

### 3. Install Dependencies
Ensure you have **Python 3.10** and **uv** installed.
```bash
uv sync
```

### 4. Setup Database
If you want to keep your existing data (users, cameras, history), you should export it from the old machine:
**Old Machine:**
```bash
pg_dump -U cctv_user cctv_platform > db_backup.sql
```
**New Machine:**
```bash
psql -U cctv_user -d cctv_platform -f db_backup.sql
```
Otherwise, run the fresh migration:
```bash
psql -U cctv_user -d cctv_platform -f migrations/001_init.sql
```

### 5. Build Frontend
```bash
cd frontend/superadmin-react
npm install
npm run build
cd ../..
```

### 6. Run
```bash
uv run python app/server.py
```

## 🔍 Troubleshooting Checklist
- [ ] **Python Version**: Must be 3.10.x.
- [ ] **CUDA**: Ensure NVIDIA drivers and Toolkit are installed if using GPU.
- [ ] **Permissions**: Ensure user has read/write access to `event_clips/` and `models/`.
- [ ] **Certs**: If browser gives "Insecure" error, you may need to regenerate certs or ignore the warning for local dev.
