from __future__ import annotations

import logging
import os
from typing import Any, Dict

try:  # pragma: no cover - fallback when structlog is unavailable
    import structlog
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    from . import _structlog_stub as structlog

DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging(level: str | None = None) -> None:
    """Configure stdlib + structlog to emit JSON logs to stdout."""
    log_level = level or DEFAULT_LEVEL

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _rename_event_key,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.stdlib.BoundLogger,
    )


def _rename_event_key(logger: Any, name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    if "event" in event_dict:
        return event_dict
    msg = event_dict.pop("msg", None)
    if msg is not None:
        event_dict["event"] = msg
    return event_dict
