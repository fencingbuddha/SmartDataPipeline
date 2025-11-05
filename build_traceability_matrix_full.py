#!/usr/bin/env python3
"""
Build a full traceability matrix by auto-discovering tests/specs and inferring ReqIDs.
Run from REPO ROOT (contains backend/ and frontend/).

Outputs:
  docs/week11/traceability_matrix.xlsx
  docs/week11/traceability_matrix.csv
"""

import re
import subprocess
from pathlib import Path

# Deps: pandas, XlsxWriter or openpyxl
try:
    import pandas as pd
except ImportError as e:
    raise SystemExit("Please `pip install pandas XlsxWriter openpyxl` before running.") from e

REPO = Path.cwd()

# ---------- Discovery globs ----------
DISCOVERY = [
    "backend/tests/**/*.py",
    "frontend/cypress/e2e/**/*.cy.ts",
    "frontend/src/components/**/*Reliability*.tsx",
]

# ---------- Req inference via filename patterns ----------
# Ordered; first match wins. We match against a lowercased path.
REQ_RULES = [
    # Reliability / Forecast reliability & related coverage bumps
    (r"(reliability_drawer|reliabilitybadge|detailsdrawer|/reliability(\.|/|_)|forecast_reliability|test_cov_bump_forecast)", "FR-11"),

    # Forecasting features (API + UI)
    (r"(forecast_overlay|/forecast(\.|/|_)|test_forecast_|forecast\.cy\.)", "FR-5"),

    # Upload / Ingestion / Sources (API + services + UAT)
    (r"(/upload(\.|/|_)|test_upload(_|\.))", "FR-1"),
    (r"(ingest|ingestion|test_ingest_|test_ingestion_)", "FR-2"),
    (r"(sources|test_sources_)", "FR-2"),

    # Metrics & KPI (API + services + UAT)
    (r"(metrics_daily|metrics_service|metrics_api|metric_names|test_metrics_|test_metric_)", "FR-3"),
    (r"(kpi|test_kpi_)", "FR-3"),

    # UI features (Cypress)
    (r"(ui_foundation|controls|layout)", "FR-6A"),
    (r"(ui_reset|reset_functionality)", "FR-6C"),
    (r"(ui_filters|perf\.demo|perf_demo|filters\.cy\.)", "FR-7"),
    (r"(dashboard\.visual|visual\.cy\.)", "FR-UI-VIS"),

    # Error handling / Non-functional health & smoke
    (r"(envelopes_and_errors|error(_|/)|errors?\.py)", "FR-12"),
    (r"(health_smoke|smoke_and_util)", "NFR-HEALTH"),

    # DB infra (bootstrap, session config, import/touch)
    (r"(db_bootstrap|db_session_config|db_import|import_db_touch)", "AR-DB"),

    # Keep for completeness
    (r"(auth|authentication|login)", "FR-10"),
    (r"(export_csv|export-?kpi|/export(\.|/|_))", "FR-8"),
    (r"(logging|monitor|observability|metrics_log)", "FR-11-LOG"),

    # Test infrastructure / general support (catch-all)
    (r"(conftest\.py|_helpers\.py|/tests/uat/|/tests/unit/|/tests/.*\.py$|/cypress/.*\.cy\.)", "AR-TESTINFRA"),
]

def infer_req(file_path: str) -> str:
    name = file_path.replace("\\", "/").lower()
    for pattern, req in REQ_RULES:
        if re.search(pattern, name):
            return req
    return "UNMAPPED"

def git(*args) -> str:
    return subprocess.check_output(["git", *args], cwd=str(REPO)).decode().strip()

def first_commit_sha_date(path: Path):
    try:
        sha = git("log", "--diff-filter=A", "--format=%H", "--", str(path)).splitlines()
        sha = sha[0] if sha else ""
        date = git("log", "--diff-filter=A", "--format=%cI", "-1", "--", str(path)) if sha else ""
        return sha, date
    except subprocess.CalledProcessError:
        return "", ""

def last_commit_sha_date(path: Path):
    try:
        sha = git("log", "-1", "--format=%H", "--", str(path)).strip()
        date = git("log", "-1", "--format=%cI", "--", str(path)) if sha else ""
        return sha, date
    except subprocess.CalledProcessError:
        return "", ""

def pr_or_short(sha: str) -> str:
    if not sha:
        return ""
    msg = git("log", "-1", "--format=%s%n%b", sha)
    m = re.search(r"#(\d{2,6})", msg)
    return f"PR #{m.group(1)}" if m else sha[:8]

def main():
    out_dir = REPO / "docs" / "week11"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for pattern in DISCOVERY:
        files.extend([p for p in REPO.glob(pattern) if p.is_file()])

    rows = []
    for p in sorted(files):
        first_sha, first_date = first_commit_sha_date(p)
        last_sha, last_date = last_commit_sha_date(p)
        rows.append({
            "ReqID": infer_req(str(p)),
            "TestID": p.stem,
            "File/Spec": str(p.relative_to(REPO)),
            "FirstCommit": first_sha[:8],
            "FirstCommitDate": first_date,
            "LastCommit": last_sha[:8],
            "LastCommitDate": last_date,
            "PR/Commit": pr_or_short(last_sha) or pr_or_short(first_sha),
            "Type": "Cypress" if p.suffix==".ts" else ("Unit" if "/unit/" in str(p) else ("UAT" if "/uat/" in str(p) else "Other")),
            "Result": "",
        })

    df = pd.DataFrame(rows, columns=[
        "ReqID","TestID","File/Spec","FirstCommit","FirstCommitDate",
        "LastCommit","LastCommitDate","PR/Commit","Type","Result"
    ])

    unmapped = df[df["ReqID"]=="UNMAPPED"].copy()
    mapped = df[df["ReqID"]!="UNMAPPED"].copy().sort_values(["ReqID","File/Spec"])

    xlsx_path = out_dir / "traceability_matrix.xlsx"
    csv_path  = out_dir / "traceability_matrix.csv"

    with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
        mapped.to_excel(writer, index=False, sheet_name="Traceability")
        if not unmapped.empty:
            unmapped.to_excel(writer, index=False, sheet_name="Unmapped")
        ws = writer.sheets["Traceability"]
        ws.set_column("A:A", 16)
        ws.set_column("B:B", 34)
        ws.set_column("C:C", 64)
        ws.set_column("D:G", 18)
        ws.set_column("H:I", 14)
        ws.set_column("J:J", 10)

    df.to_csv(csv_path, index=False)
    print(f"Wrote {xlsx_path} and {csv_path}")
    if not unmapped.empty:
        print(f"Note: {len(unmapped)} rows need manual ReqID tagging (see 'Unmapped' sheet).")

if __name__ == "__main__":
    main()
