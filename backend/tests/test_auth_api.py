from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_ok_and_protected_access():
    r = client.post("/api/auth/login", json={"email":"demo@example.com","password":"demo123"})
    assert r.status_code == 200, r.text
    access = r.json()["access_token"]

    # protected route requires token
    r2 = client.get("/api/metrics/daily", params={"source_name":"seeded-source","metric":"events_total"})
    assert r2.status_code in (401,403)

    # with token → OK (even if empty dataset, just asserting auth)
    r3 = client.get(
        "/api/metrics/daily",
        params={"source_name":"seeded-source","metric":"events_total"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r3.status_code == 200

def test_login_rejects_bad_password():
    r = client.post("/api/auth/login", json={"email":"demo@example.com","password":"wrong"})
    assert r.status_code in (400,401,403)

def test_refresh_ok_then_new_access():
    r = client.post("/api/auth/login", json={"email":"demo@example.com","password":"demo123"})
    refresh = r.json()["refresh_token"]
    r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    assert "access_token" in r2.json()

def test_refresh_rejects_garbage_token():
    r = client.post("/api/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert r.status_code in (400,401,403)