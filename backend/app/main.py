# app/main.py
from __future__ import annotations

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
try:  # pragma: no cover
    from fastapi_instrumentator import Instrumentator
except ModuleNotFoundError:  # pragma: no cover
    Instrumentator = None

# Import router objects explicitly to avoid module name collisions
from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.upload import router as upload_router
from app.routers.kpi import router as kpi_router
from app.routers.ingest import router as ingest_router
from app.routers.sources import router as sources_router
from app.routers.forecast import router as forecast_router
from app.routers.anomaly import router as anomaly_router
from app.routers.metrics import router as metrics_router
from app.routers.forecast_reliability import router as forecast_reliability_router
from app.db.session import get_engine
from app.db.base import Base
from app.core.security import get_current_user
from app.observability.logging import configure_logging
from app.observability.middleware import register_request_middleware, unhandled_exception_handler
from app.observability.metrics import router as observability_router
from app.security.middleware import SecurityHeadersMiddleware
from app.config import get_settings

configure_logging()

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Smart Data Pipeline", version="0.7.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=86400
    )

    if settings.TRUSTED_HOSTS:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)

    if settings.FORCE_HTTPS:
        app.add_middleware(HTTPSRedirectMiddleware)

    app.add_middleware(
        SecurityHeadersMiddleware,
        csp=settings.CONTENT_SECURITY_POLICY,
        hsts_max_age=settings.HSTS_MAX_AGE,
        enable_hsts=settings.FORCE_HTTPS,
    )

    register_request_middleware(app)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Ensure tables exist in dev/e2e so the UI and tests don't 500 on brand-new DBs
    @app.on_event("startup")
    def _ensure_tables() -> None:
        try:
            engine = get_engine()
            Base.metadata.create_all(bind=engine)
        except Exception as ex:  # defensive: don't block startup
            import logging
            logging.getLogger(__name__).exception("Failed to create tables on startup: %s", ex)

    # Public routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(observability_router)

    # Private routers share the same auth dependency
    require_auth = [Depends(get_current_user)]

    app.include_router(kpi_router, dependencies=require_auth)
    app.include_router(ingest_router, dependencies=require_auth)
    app.include_router(upload_router, dependencies=require_auth)
    app.include_router(metrics_router, dependencies=require_auth)
    app.include_router(forecast_router, dependencies=require_auth)
    app.include_router(forecast_reliability_router, dependencies=require_auth)
    app.include_router(anomaly_router, dependencies=require_auth)
    app.include_router(sources_router, dependencies=require_auth)

    if Instrumentator is not None:  # pragma: no cover - optional when pkg missing
        Instrumentator(should_group_status_codes=False).instrument(app)

    return app


app = create_app()
