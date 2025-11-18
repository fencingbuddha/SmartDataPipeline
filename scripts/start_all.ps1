Param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[QR-6] Running SmartDataPipeline portable demo (Windows)"

# -------------------------
# 1) Backend setup
# -------------------------

# Create venv if missing
if (-Not (Test-Path ".venv")) {
    Write-Host "[QR-6] Creating Python venv at .venv…"
    python -m venv .venv
}

# Activate venv
$venvActivate = Join-Path ".venv" "Scripts\Activate.ps1"
. $venvActivate

Write-Host "[QR-6] Installing backend dependencies…"
pip install --upgrade pip
pip install -r "backend\requirements.txt"

# Ensure backend .env
if (-Not (Test-Path "backend\.env")) {
    Write-Host "[QR-6] backend\.env not found, copying env\backend.env.example"
    Copy-Item "env\backend.env.example" "backend\.env"
}

# Initialize SQLite DB if missing
Set-Location "backend"
if (-Not (Test-Path "smartdata.db")) {
    Write-Host "[QR-6] smartdata.db not found, running Alembic migrations…"
    alembic upgrade head
}
Set-Location $root

# -------------------------
# 2) Frontend setup
# -------------------------

Set-Location "frontend"

# Ensure frontend .env
if (-Not (Test-Path ".env") -and (Test-Path "..\env\frontend.env.example")) {
    Write-Host "[QR-6] .env not found, copying ..\env\frontend.env.example"
    Copy-Item "..\env\frontend.env.example" ".env"
}

Write-Host "[QR-6] Installing frontend dependencies…"
if (Test-Path "package-lock.json") {
    npm ci
} else {
    npm install
}

# -------------------------
# 3) Start backend + frontend
# -------------------------

Set-Location $root

Write-Host "[QR-6] Starting backend on http://localhost:8000…"
Start-Process -FilePath "uvicorn" `
    -ArgumentList "app.main:app","--host","0.0.0.0","--port","8000" `
    -WorkingDirectory "$root\backend"

Write-Host "[QR-6] Starting frontend on http://localhost:5173…"
Set-Location "$root\frontend"
npm run dev