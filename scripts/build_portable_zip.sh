#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DIST_DIR="dist"
ZIP_NAME="smartdata-portable-demo.zip"

mkdir -p "$DIST_DIR"

echo "[QR-6] Building portable ZIP at $DIST_DIR/$ZIP_NAME"

# Clean old zip if present
if [ -f "$DIST_DIR/$ZIP_NAME" ]; then
  rm "$DIST_DIR/$ZIP_NAME"
fi

zip -r "$DIST_DIR/$ZIP_NAME" \
  backend \
  frontend \
  env \
  scripts \
  README_PORTABLE.md \
  -x "*/node_modules/*" \
     "*/.venv/*" \
     "*.pyc" \
     "*__pycache__/*" \
     ".DS_Store" \
     ".git/*" \
     "dist/*"

echo "[QR-6] Done. Created $DIST_DIR/$ZIP_NAME"
