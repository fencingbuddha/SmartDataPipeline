from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.middleware import (
    register_request_middleware,
    unhandled_exception_handler,
)


def _build_app():
    app = FastAPI()
    register_request_middleware(app)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    return app


def test_request_context_adds_request_id_header():
    app = _build_app()

    @app.get("/ok")
    def ok_route():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id")


def test_unhandled_exception_returns_request_id():
    from fastapi import Request
    from starlette.types import Scope

    scope: Scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.request_id = "abc-123"
    response = unhandled_exception_handler(request, RuntimeError("boom"))
    assert response.status_code == 500
    assert response.body
    assert b"abc-123" in response.body
