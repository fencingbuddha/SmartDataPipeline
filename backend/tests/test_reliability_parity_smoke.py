import os
import math
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

SOURCE = "demo-source"
METRIC = "events_total"


def _generate_csv(days: int = 90) -> str:
    """Create a small deterministic-ish time series CSV (header included)."""
    import random
    random.seed(42)  # keep stable across DBs
    rows = ["timestamp,value,metric,source"]
    today = date.today()
    for d in range(days, 0, -1):
        ts = today - timedelta(days=d)
        # smooth seasonal-ish signal + tiny noise
        val = 100 + int(10 * math.sin(d / 7)) + random.randint(-3, 3)
        rows.append(f"{ts}T12:00:00Z,{val},{METRIC},{SOURCE}")
    return "\n".join(rows)


def _seed_and_compute(client: TestClient, days: int = 90):
    # 1) Ingest CSV (raw text/csv body)
    csv_body = _generate_csv(days)
    r = client.post(
        f"/api/ingest?source_name={SOURCE}&default_metric={METRIC}",
        data=csv_body,
        headers={"Content-Type": "text/csv"},
    )
    assert r.status_code == 200, r.text

    # 2) KPI over the same window
    start = (date.today() - timedelta(days=days)).isoformat()
    end = date.today().isoformat()
    r = client.post(
        f"/api/kpi/run?source_name={SOURCE}&metric={METRIC}&start={start}&end={end}",
        json={},
    )
    assert r.status_code == 200, r.text

    # 3) Backtest to compute & persist reliability (smaller params for speed)
    r = client.post(
        f"/api/forecast/backtest?source_name={SOURCE}&metric={METRIC}&window_n=60&folds=3&horizon=7"
    )
    assert r.status_code == 200, r.text


def _fetch_reliability(client: TestClient):
    r = client.get("/api/forecast/reliability", params={"source_name": SOURCE, "metric": METRIC})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    return body["data"], body.get("meta", {})


def _run_for_db(monkeypatch, db_url: str):
    # Set env BEFORE creating client so app/engine binds to this DB
    monkeypatch.setenv("DATABASE_URL", db_url)
    with TestClient(app) as client:
        _seed_and_compute(client)
        return _fetch_reliability(client)


def test_sqlite_vs_postgres_parity_smoke(monkeypatch):
    # SQLite run
    d_sqlite, m_sqlite = _run_for_db(monkeypatch, "sqlite:///./smartdata.db")
    assert d_sqlite["folds"] > 0

    # Postgres run
    d_pg, m_pg = _run_for_db(monkeypatch, "postgresql+psycopg2://postgres:postgres@localhost:5432/smartdata")

    # Keys match
    assert set(d_sqlite.keys()) == set(d_pg.keys())
    assert set(m_sqlite.keys()) == set(m_pg.keys())

    # Numeric values very close
    for k in ("avg_mae", "avg_rmse", "avg_mape", "avg_smape", "score"):
        va, vb = d_sqlite.get(k), d_pg.get(k)
        if va is None or vb is None:
            continue
        assert abs(float(va) - float(vb)) < 1e-4

    # Non-numeric exact matches
    for k in ("folds",):
        assert d_sqlite.get(k) == d_pg.get(k)

    # Meta stable (window/horizon typically equal here)
    for k in ("folds", "horizon", "window_n", "metric", "source_name"):
        assert m_sqlite.get(k) == m_pg.get(k)