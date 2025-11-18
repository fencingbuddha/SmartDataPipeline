#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (one level above scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

echo "[QR-6] Setting up frontend (npm deps)…"

# 1) Ensure .env exists (copy from ../env/frontend.env.example if not)
if [ ! -f ".env" ] && [ -f "../env/frontend.env.example" ]; then
  echo "[QR-6] .env not found, copying ../env/frontend.env.example"
  cp ../env/frontend.env.example .env
fi

# 2) Install Node deps
if command -v npm >/dev/null 2>&1; then
  if [ -f "package-lock.json" ]; then
    echo "[QR-6] Using npm ci (lockfile present)…"
    npm ci
  else
    echo "[QR-6] Using npm install (no lockfile)…"
    npm install
  fi
else
  echo "ERROR: npm not found. Install Node.js + npm to run the frontend."
  exit 1
fi

echo "[QR-6] Frontend setup complete."
