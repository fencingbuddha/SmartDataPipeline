# backend/tests/test_sources_smoke.py
def test_sources_list(client):
    r = client.get("/api/sources")
    assert r.status_code == 200
    payload = r.json()

    # Accept both enveloped and bare-list responses
    items = payload if isinstance(payload, list) else payload.get("data", [])
    assert isinstance(items, list)

    # Optional: light sanity on shape if any sources exist
    if items:
        assert all(isinstance(x, dict) for x in items)
        assert all(("id" in x and "name" in x) for x in items)
