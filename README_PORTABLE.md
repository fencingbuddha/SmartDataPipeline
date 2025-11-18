# SmartDataPipeline – Portable Demo (QR-6)

This archive contains a **self-contained SQLite demo** of SmartDataPipeline.

You only need:

- Python 3.12+ (with `python3` on your PATH)
- Node.js + npm
- A shell that can run `.sh` scripts (macOS / Linux)

No Docker, Postgres, or cloud services are required for the demo.

---

## 1. Quick Start (macOS / Linux)

1. Unzip the archive:

   ```bash
   unzip smartdata-portable-demo.zip
   cd SmartDataPipeline
   ```

2. Run the combined setup + start script:

   ```bash
   ./scripts/start_all.sh
   ```

3. Open the dashboard:
   - Frontend UI: <http://localhost:5173>
   - Backend API (for reference): <http://localhost:8000>

### Authentication Note
Most backend routes (such as `/api/sources`, `/api/metrics/...`, and `/api/forecast/...`) require a valid login session. To fully access the dashboard features, open the frontend at <http://localhost:5173> and use the built‑in **Sign Up / Log In** flow.

Once logged in, the frontend will automatically attach your access token to API requests.

Directly visiting backend routes in the browser (for example, `http://localhost:8000/api/sources`) will return `401 Not Authenticated`, which is expected behavior.

Swagger (`/docs`) may appear blank or limited until authenticated.

The first run may take a bit longer as dependencies are installed and the SQLite database is initialized via Alembic migrations.

---

## 2. Windows Instructions (PowerShell)

If running on Windows, use PowerShell:

```powershell
# Unzip the archive
Expand-Archive smartdata-portable-demo.zip -DestinationPath .
cd SmartDataPipeline

# Run the Windows launcher
scripts/start_all.ps1
```

Then open the dashboard:
- Frontend UI: <http://localhost:5173>
- Backend API: <http://localhost:8000>

The PowerShell script performs the same tasks as the `.sh` version: it sets up a Python virtual environment, installs backend and frontend dependencies, initializes the SQLite database if needed, and runs both servers.

---

## 3. What Each Script Does

### `scripts/setup_backend.sh`
- Creates and/or activates `.venv`.
- Installs backend dependencies from `backend/requirements.txt`.
- Copies `env/backend.env.example` → `backend/.env` if missing.
- Applies Alembic migrations to create `smartdata.db`.

### `scripts/setup_frontend.sh`
- Ensures `frontend/.env` exists by copying from `env/frontend.env.example`.
- Installs frontend Node dependencies using `npm ci` or `npm install`.

### `scripts/start_all.sh`
- Calls both setup scripts.
- Starts the FastAPI backend on port 8000.
- Starts the Vite frontend dev server on port 5173.

### `scripts/start_all.ps1` (Windows)
- Windows PowerShell equivalent of the above.
- Manages venv creation/activation, dependency installation, and server launch.

### `scripts/build_portable_zip.sh`
- Packages the project into a portable ZIP file containing:
  - Backend code
  - Frontend code
  - env templates
  - All setup/start scripts
  - The portable README
- Excludes unnecessary items like `node_modules`, `.venv`, and `.git`.

---

## 4. Environment Configuration Details

### Backend
Located at `env/backend.env.example` (copied to `backend/.env`).

Key variables:
- `DATABASE_URL` — Uses SQLite by default (`sqlite:///./smartdata.db`).
- `FRONTEND_ORIGIN` — Expected frontend origin (`http://localhost:5173`).
- `ALLOW_ORIGINS` — CORS allowlist.

### Frontend
Located at `env/frontend.env.example` (copied to `frontend/.env`).

Key variables:
- `VITE_API_BASE_URL=http://localhost:8000`
- `VITE_APP_ENV=demo`

---

## 5. Resetting the Demo

If you want a clean slate:

```bash
rm backend/smartdata.db
./scripts/start_all.sh
```

This forces Alembic to recreate the SQLite database.

---

## 6. Troubleshooting

### **Port Already In Use**
If port 5173 or 8000 is already running:
```bash
lsof -i :5173
lsof -i :8000
```
Stop the conflicting process and re-run the script.

### **Permission Denied on Scripts**
If a script refuses to run:
```bash
chmod +x scripts/*.sh
```

### **Python Not Found**
Make sure `python3` is installed and on your PATH:
```bash
python3 --version
```

### **npm Not Found**
Install Node.js from https://nodejs.org.

---

## 7. About the Portable ZIP

The ZIP is intended for demonstration and evaluation purposes. It is not optimized for production. SQLite is used for simplicity and portability. The frontend runs on the Vite development server for easy local use.

---

## 8. Regenerating the Portable ZIP (For Developers)

If you make changes to the backend, frontend, or scripts and want to rebuild the portable demo, run:

```bash
./scripts/build_portable_zip.sh
```

This will create a fresh archive at:

```
dist/smartdata-portable-demo.zip
```

The ZIP includes:
- Backend code (FastAPI)
- Frontend code (React/Vite)
- Environment templates (`env/`)
- All setup and start scripts (`scripts/`)
- This portable README

It excludes:
- `.venv` (Python virtual environment)
- `node_modules` (frontend dependencies)
- Git history
- macOS metadata files

This ensures a clean, lightweight archive that anyone can unzip and run locally.
