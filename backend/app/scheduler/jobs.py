from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def run_daily_kpis() -> None:
    """
    Nightly KPI job (FR-9).

    For now this is a lightweight placeholder that proves the scheduler wiring works
    without depending on any unfinished metrics services. It simply logs a start/end
    marker with a UTC timestamp so we can verify execution in the logs.
    """
    started = datetime.now(timezone.utc)
    logger.info("kpi_job.start", extra={"started": started.isoformat()})
    try:
        # TODO: integrate with the real KPI computation service once available.
        # e.g., compute_daily_kpis(db_session, window="yesterday")
        logger.info("kpi_job.done", extra={"upserts": 0})
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("kpi_job.error", extra={"error": str(exc)})


def weekly_retrain_models() -> None:
    """
    Weekly model retraining job.

    Currently a stub that only logs start/end. This gives us a safe entry point to
    hook in the anomaly/forecast model retraining pipeline later.
    """
    logger.info("weekly_retrain.start")
    try:
        # TODO: call into your retraining/backtesting pipeline here.
        logger.info("weekly_retrain.done")
    except Exception as exc:  # pragma: no cover
        logger.exception("weekly_retrain.error", extra={"error": str(exc)})


def housekeeping() -> None:
    """
    Daily housekeeping job.

    Placeholder that logs execution; later this can clean temp files, prune old demo
    data, or rotate artifacts related to the Smart Data Pipeline.
    """
    logger.info("housekeeping.start")
    try:
        # TODO: implement actual cleanup tasks here.
        logger.info("housekeeping.done")
    except Exception as exc:  # pragma: no cover
        logger.exception("housekeeping.error", extra={"error": str(exc)})