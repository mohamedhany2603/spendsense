"""Background / cron jobs with APScheduler.

Two jobs, both off the request path:
  1. Auto-categorize: picks up pending transactions and runs the LLM/rule
     categorizer in the background (runs every N minutes).
  2. Monthly report: on the 1st of each month at the configured time, generate
     the previous month's PDF report for every user.

The scheduler is only started when ENABLE_SCHEDULER is true — tests and one-off
runs keep it off.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import get_settings
from ..database import SessionLocal
from ..models import Transaction, TransactionStatus, User

logger = logging.getLogger("spendsense.scheduler")


def auto_categorize_job() -> None:
    """Categorize pending transactions in the background, one batch per run."""
    settings = get_settings()
    db = SessionLocal()
    try:
        pending = (
            db.query(Transaction)
            .filter(Transaction.status == TransactionStatus.pending)
            .limit(50)
            .all()
        )
        if not pending:
            return
        # Imported lazily to avoid a circular import at module load.
        from .categorizer import classify_merchant

        for tx in pending:
            try:
                result = classify_merchant(db, tx.merchant, tx.description)
                tx.category_id = result.category_id
                tx.status = TransactionStatus.categorized
                tx.source = result.source
                tx.categorized_at = datetime.utcnow()
            except Exception as exc:  # noqa: BLE001 - job must not die on one row
                tx.status = TransactionStatus.failed
                logger.warning("auto-categorize failed for tx %s: %s", tx.id, exc)
        db.commit()
        logger.info("auto-categorize: processed %d pending transactions", len(pending))
    finally:
        db.close()


def monthly_report_job() -> None:
    """Generate last month's PDF report for every user."""
    db = SessionLocal()
    try:
        from .reports import generate_report_pdf

        last_month = (datetime.utcnow().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        users = db.query(User).all()
        for user in users:
            try:
                generate_report_pdf(db, user.id, last_month, user.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("monthly report failed for user %s: %s", user.id, exc)
        logger.info("monthly report job: %d users handled for %s", len(users), last_month)
    finally:
        db.close()


_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        auto_categorize_job,
        "interval",
        minutes=settings.auto_categorize_interval_minutes,
        id="auto_categorize",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        monthly_report_job,
        "cron",
        day="1",
        hour=settings.report_cron_hour,
        minute=settings.report_cron_minute,
        id="monthly_report",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler started: %s", [job.id for job in scheduler.get_jobs()])
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None