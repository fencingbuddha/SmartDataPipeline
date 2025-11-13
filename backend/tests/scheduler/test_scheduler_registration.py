# backend/tests/scheduler/test_scheduler_registration.py

from app.scheduler.setup import scheduler, configure_jobs


def test_configure_jobs_registers_expected_jobs() -> None:
    """
    FR-9: ensure the scheduler registers the expected recurring jobs.

    This verifies that:
      - configure_jobs() can be called without errors
      - the global scheduler instance ends up with the three core jobs
        we expect: daily KPIs, weekly retrain, and housekeeping.
    """
    # Start from a clean slate so repeated test runs don't accumulate jobs
    scheduler.remove_all_jobs()

    # Register jobs under test
    configure_jobs()

    job_ids = {job.id for job in scheduler.get_jobs()}

    assert {"daily-kpis", "weekly-retrain", "daily-housekeeping"} <= job_ids