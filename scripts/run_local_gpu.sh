#!/usr/bin/env bash
# Run object-detection-main (SecureVU WebRTC) on GPU — port 8000.
# Isolated from POC-SecureVU-updated-gpu which uses port 8004.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

THIS_PORT="${PORT:-8000}"
OTHER_PORT=8004

if ss -tlnp 2>/dev/null | grep -q ":${OTHER_PORT} "; then
  echo "ERROR: POC-SecureVU-updated-gpu is listening on port ${OTHER_PORT}."
  echo "       Stop it first (both projects share the same GPU and RTSP cameras):"
  echo "         pkill -f 'securevu.main' || true"
  echo "       Or run only one SecureVU stack at a time."
  exit 1
fi

if ss -tlnp 2>/dev/null | grep -q ":${THIS_PORT} "; then
  echo "Port ${THIS_PORT} already in use. Stop the existing server or set PORT=..."
  ss -tlnp 2>/dev/null | grep ":${THIS_PORT} " || true
  exit 1
fi

echo "=== object-detection-main (GPU) ==="
echo "Backend : https://localhost:${THIS_PORT}"
echo "Frontend: cd frontend/superadmin-react && npm run dev  →  http://localhost:5173"
echo "Note    : POC copy on Desktop uses port 8004 — keep it stopped while this runs."
echo ""

exec uv run python app/server.py
