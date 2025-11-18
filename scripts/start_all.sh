#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[QR-6] Starting SmartDataPipeline portable demo"

# 1) Run setup (safe to re-run; it's idempotent)
./scripts/setup_backend.sh
./scripts/setup_frontend.sh

# 2) Activate venv for backend
# shellcheck disable=SC1091
source .venv/bin/activate

# 3) Start backend API
echo "[QR-6] Starting backend on http://localhost:8000…"
(
  cd backend
  uvicorn app.main:app --host 0.0.0.0 --port 8000
) &

BACKEND_PID=$!

# 4) Start frontend dev server
echo "[QR-6] Starting frontend on http://localhost:5173…"
(
  cd frontend
  npm run dev
) &

FRONTEND_PID=$!

echo ""
echo "-----------------------------------------------------------------"
echo " SmartDataPipeline portable demo is running."
echo ""
echo "  Backend API:  http://localhost:8000"
echo "  Frontend UI:  http://localhost:5173"
echo ""
echo " Press Ctrl+C to stop both."
echo "-----------------------------------------------------------------"
echo ""

# 5) On Ctrl+C, kill both child processes
cleanup() {
  echo ""
  echo "[QR-6] Stopping services…"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup INT TERM

# Wait for both processes (whichever exits first breaks the wait)
wait "$BACKEND_PID" "$FRONTEND_PID" || true
cleanup
