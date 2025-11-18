#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (one level above scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[QR-6] Setting up backend (venv + deps + SQLite)…"

# 1) Create venv at repo root if missing
if [ ! -d ".venv" ]; then
  echo "[QR-6] Creating Python virtualenv at .venv"
  python3 -m venv .venv
fi

# 2) Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# 3) Install backend dependencies
echo "[QR-6] Installing backend dependencies…"
pip install --upgrade pip
pip install -r backend/requirements.txt

# 4) Ensure backend/.env exists (copy from env/backend.env.example if not)
if [ ! -f "backend/.env" ]; then
  echo "[QR-6] backend/.env not found, copying env/backend.env.example"
  cp env/backend.env.example backend/.env
fi

# 5) Initialize SQLite DB via Alembic if it doesn't exist yet
cd backend

if [ ! -f "smartdata.db" ]; then
  echo "[QR-6] smartdata.db not found, running Alembic migrations…"
  alembic upgrade head || {
    echo "ERROR: Alembic failed. Check alembic.ini and DB config for SQLite."
    exit 1
  }

  # Optional: seed demo data here if you have a script
  # python -m app.scripts.seed_demo_data
else
  echo "[QR-6] smartdata.db already exists, skipping migrations."
fi

echo "[QR-6] Backend setup complete."
