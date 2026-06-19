#!/usr/bin/env bash
# Copy owner-supplied binaries from handoff/ into repo paths expected by app/server.py.
# Run from repository root:  bash handoff/install-from-handoff.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HANDOFF="${REPO_ROOT}/handoff"

cd "$REPO_ROOT"

missing=0
if [[ ! -f "${HANDOFF}/secure_cv_best.pt" ]]; then
  echo "ERROR: missing ${HANDOFF}/secure_cv_best.pt"
  missing=1
fi
if [[ ! -f "${HANDOFF}/face_db.npz" ]]; then
  echo "WARN: missing ${HANDOFF}/face_db.npz (optional — enroll faces in UI instead)"
fi

mkdir -p models/yolo models/arcface/face_db certs recordings mlruns

if [[ -f "${HANDOFF}/secure_cv_best.pt" ]]; then
  cp -f "${HANDOFF}/secure_cv_best.pt" models/yolo/secure_cv_best.pt
  echo "OK: models/yolo/secure_cv_best.pt"
fi

if [[ -f "${HANDOFF}/face_db.npz" ]]; then
  cp -f "${HANDOFF}/face_db.npz" models/arcface/face_db/face_db.npz
  echo "OK: models/arcface/face_db/face_db.npz"
fi

if [[ -f "${HANDOFF}/env-template.txt" ]] && [[ ! -f "${REPO_ROOT}/.env" ]]; then
  cp "${HANDOFF}/env-template.txt" "${REPO_ROOT}/.env"
  echo "OK: copied handoff/env-template.txt -> .env (edit RTSP_URL_* before starting)"
elif [[ -f "${REPO_ROOT}/.env" ]]; then
  echo "SKIP: .env already exists (not overwritten)"
elif [[ -f "${HANDOFF}/env-template.example.txt" ]] && [[ ! -f "${REPO_ROOT}/.env" ]]; then
  cp "${HANDOFF}/env-template.example.txt" "${REPO_ROOT}/.env"
  echo "OK: copied env-template.example.txt -> .env (fill secrets and RTSP URLs)"
else
  echo "HINT: cp .env.example .env  OR  copy handoff/env-template.txt to .env"
fi

if [[ $missing -eq 1 ]]; then
  echo ""
  echo "Get secure_cv_best.pt from the repo owner and place it in handoff/ before re-running."
  exit 1
fi

echo ""
echo "Handoff install complete. Next:"
echo "  1. Edit .env — set RTSP_URL_1..4 and rotate dev passwords if needed"
echo "  2. uv sync --group mlops"
echo "  3. docker compose up -d db   # or: docker compose up --build"
echo "  4. psql ... -f migrations/002_poc.sql   # if DB volume already existed"
echo "  5. cd frontend/superadmin-react && npm install && npm run build"
echo "  6. uv run python scripts/seed_admin.py"
echo "  7. uv run python app/server.py"
