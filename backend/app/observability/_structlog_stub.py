"""Minimal structlog stand-in for offline environments."""
from __future__ import annotations

import contextvars
import datetime as _dt
import json
import logging
from typing import Any, Dict, Optional

_ctx: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "structlog_context", default={}
)


class _ContextVars:
    @staticmethod
    def bind_contextvars(**kwargs: Any) -> None:
        ctx = dict(_ctx.get())
        ctx.update(kwargs)
        _ctx.set(ctx)

    @staticmethod
    def clear_contextvars() -> None:
        _ctx.set({})

    @staticmethod
    def merge_contextvars(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict.update(_ctx.get())
        return event_dict


class _TimeStamper:
    def __init__(self, fmt: str = "iso") -> None:
        self.fmt = fmt

    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict["timestamp"] = _dt.datetime.utcnow().isoformat()
        return event_dict


class _JSONRenderer:
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> str:
        return json.dumps(event_dict)


class _Processors:
    TimeStamper = _TimeStamper
    JSONRenderer = _JSONRenderer

    @staticmethod
    def add_log_level(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event_dict["level"] = (method_name or "info").lower()
        return event_dict


class _BoundLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def bind(self, **kwargs: Any) -> "_BoundLogger":
        _ContextVars.bind_contextvars(**kwargs)
        return self

    def info(self, event: str, **kwargs: Any) -> None:
        self._log("info", event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self._log("exception", event, **kwargs)

    def _log(self, level: str, event: str, **kwargs: Any) -> None:
        payload = dict(_ctx.get())
        payload.update(kwargs)
        payload["event"] = event
        msg = json.dumps(payload)
        getattr(self.logger, level)(msg)


class _LoggerFactory:
    def __call__(self, *args: Any, **kwargs: Any) -> logging.Logger:
        return logging.getLogger(*args, **kwargs)


def configure(*args: Any, **kwargs: Any) -> None:  # pragma: no cover - noop
    # Stdlib logging is already configured elsewhere.
    return None


def get_logger(name: Optional[str] = None) -> _BoundLogger:
    return _BoundLogger(logging.getLogger(name or "app"))


contextvars = _ContextVars()
processors = _Processors()
stdlib = type("stdlib", (), {"LoggerFactory": _LoggerFactory, "BoundLogger": _BoundLogger})
