from __future__ import annotations

import asyncio
import functools
import inspect
import time
from typing import Any, Callable, TypeVar

try:  # pragma: no cover
    import structlog
except ModuleNotFoundError:  # pragma: no cover
    from . import _structlog_stub as structlog

F = TypeVar("F", bound=Callable[..., Any])

logger = structlog.get_logger("job")


def _result_size(res: Any) -> int | None:
    try:
        if isinstance(res, (list, tuple, set, dict)):
            return len(res)
        if hasattr(res, "__len__"):
            return len(res)  # type: ignore[arg-type]
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def log_job(name: str) -> Callable[[F], F]:
    """Decorator to measure job duration and emit structured logs."""

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any):
                start = time.perf_counter()
                logger.info("job.start", job=name)
                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    duration = (time.perf_counter() - start) * 1000
                    logger.exception("job.error", job=name, duration_ms=round(duration, 2))
                    raise
                duration = (time.perf_counter() - start) * 1000
                logger.info(
                    "job.completed",
                    job=name,
                    duration_ms=round(duration, 2),
                    result_size=_result_size(result),
                )
                return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any):
            start = time.perf_counter()
            logger.info("job.start", job=name)
            try:
                result = func(*args, **kwargs)
            except Exception:
                duration = (time.perf_counter() - start) * 1000
                logger.exception("job.error", job=name, duration_ms=round(duration, 2))
                raise
            duration = (time.perf_counter() - start) * 1000
            logger.info(
                "job.completed",
                job=name,
                duration_ms=round(duration, 2),
                result_size=_result_size(result),
            )
            return result

        return sync_wrapper  # type: ignore[return-value]

    return decorator
