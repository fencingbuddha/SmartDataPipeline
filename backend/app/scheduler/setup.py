from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from pytz import timezone

from app.scheduler.jobs import run_daily_kpis, weekly_retrain_models, housekeeping
from app.config import get_settings


settings = get_settings()

# Global scheduler instance used for FR-9 job scheduling.
scheduler = AsyncIOScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(
            url=(settings.SCHEDULER_DB_URL or settings.DATABASE_URL)
        )
    },
    timezone=timezone(settings.SCHEDULER_TZ),
)


def configure_jobs() -> None:
    """
    Register all recurring jobs with the scheduler.

    - daily-kpis: nightly KPI computation
    - weekly-retrain: weekly model retraining
    - daily-housekeeping: daily cleanup tasks
    """
    scheduler.add_job(
        run_daily_kpis,
        "cron",
        id="daily-kpis",
        hour=2,
        minute=15,
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        weekly_retrain_models,
        "cron",
        id="weekly-retrain",
        day_of_week="sun",
        hour=3,
        minute=30,
        replace_existing=True,
        misfire_grace_time=7200,
        coalesce=True,
    )
    scheduler.add_job(
        housekeeping,
        "interval",
        id="daily-housekeeping",
        days=1,
        replace_existing=True,
        coalesce=True,
    )


async def init_scheduler(app) -> None:
    """
    FastAPI startup hook: initialize and start the APScheduler instance
    if SCHEDULER_ENABLED is true.
    """
    if not settings.SCHEDULER_ENABLED:
        return
    configure_jobs()
    scheduler.start()


async def shutdown_scheduler() -> None:
    """
    FastAPI shutdown hook: stop the scheduler cleanly.
    """
    if scheduler.running:
        scheduler.shutdown(wait=False)