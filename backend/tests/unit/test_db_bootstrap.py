import os, sys, importlib
from sqlalchemy import text

def test_db_module_reload_and_connect(monkeypatch):
    # Ensure a valid URL is present before (re)import
    monkeypatch.setenv("DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///:memory:"))

    # Force a fresh import so module-level lines are executed under coverage
    if "app.db" in sys.modules:
        del sys.modules["app.db"]
    import app.db as db
    importlib.reload(db)

    # Touch everything exposed there
    assert hasattr(db, "engine") and hasattr(db, "SessionLocal")
    # Engine URL is parseable
    assert str(getattr(db.engine, "url", "")) != ""

    # Prove engine works
    with db.engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1

    # Prove SessionLocal works
    with db.SessionLocal() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1
