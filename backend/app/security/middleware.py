from __future__ import annotations

from typing import Sequence

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Appends common security headers to every response."""

    def __init__(
        self,
        app,
        *,
        csp: str,
        hsts_max_age: int,
        enable_hsts: bool,
    ) -> None:
        super().__init__(app)
        self.csp = csp
        self.hsts_max_age = hsts_max_age
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        if self.enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self.hsts_max_age}; includeSubDomains; preload",
            )

        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )

        if self.csp:
            response.headers.setdefault("Content-Security-Policy", self.csp)

        return response
