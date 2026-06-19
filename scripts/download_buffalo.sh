#!/usr/bin/env bash
# Download InsightFace buffalo_l into pre_trained/insightface/models/buffalo_l/
# Run from repo root:  bash scripts/download_buffalo.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${REPO_ROOT}/pre_trained/insightface/models"
ZIP="${TMPDIR:-/tmp}/buffalo_l.zip"
URL="https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"

mkdir -p "$DEST"

if [[ -f "${DEST}/buffalo_l/w600k_r50.onnx" ]]; then
  echo "buffalo_l already present at ${DEST}/buffalo_l/"
  exit 0
fi

echo "Downloading buffalo_l from InsightFace releases..."
curl -fL --progress-bar -o "$ZIP" "$URL"
unzip -o "$ZIP" -d "$DEST"
rm -f "$ZIP"

# Release zip unpacks *.onnx directly under models/; InsightFace expects models/buffalo_l/
if [[ ! -f "${DEST}/buffalo_l/w600k_r50.onnx" ]] && [[ -f "${DEST}/w600k_r50.onnx" ]]; then
  mkdir -p "${DEST}/buffalo_l"
  mv -f "${DEST}"/*.onnx "${DEST}/buffalo_l/"
fi

echo "OK: ${DEST}/buffalo_l/"
ls -lh "${DEST}/buffalo_l/"
