from __future__ import annotations

import importlib

from fastapi.testclient import TestClient
import pytest


def build_app(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("FORCE_HTTPS", "true")
    monkeypatch.setenv("DB_REQUIRE_SSL", "false")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-key")

    import app.config as config

    config.get_settings.cache_clear()
    import app.main as main
    from app.security.crypto import reset_crypto_state

    reset_crypto_state()

    importlib.reload(main)
    return main.create_app()


def test_security_headers_in_prod(monkeypatch):
    app = build_app(monkeypatch)
    client = TestClient(app, base_url="https://testserver")
    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.headers["Strict-Transport-Security"].startswith("max-age=")
    assert "Content-Security-Policy" in resp.headers
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_required_db_role_enforced(monkeypatch):
    monkeypatch.setenv("DB_APP_ROLE", "sdp_app")
    monkeypatch.setenv("DB_REQUIRE_SSL", "false")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-key")

    import app.config as config

    config.get_settings.cache_clear()

    import app.db.session as session
    from app.security.crypto import reset_crypto_state

    reset_crypto_state()

    importlib.reload(session)

    good_url = "postgresql+psycopg2://sdp_app:secret@localhost:5555/smartdata"
    assert session._enforce_ssl_requirements(good_url).startswith(
        "postgresql+psycopg2://sdp_app"
    )

    bad_url = "postgresql+psycopg2://other_role:secret@localhost:5555/smartdata"
    with pytest.raises(RuntimeError):
        session._enforce_ssl_requirements(bad_url)
