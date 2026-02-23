#!/usr/bin/env bash
# Start the superadmin React dev server from repository root
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1
npm --prefix frontend/superadmin-react run dev -- --host 0.0.0.0 --port 5173
