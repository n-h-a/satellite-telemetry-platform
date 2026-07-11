import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from app.database import SessionLocal
from app.services import run_los_check
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)

LOS_CHECK_INTERVAL_SECONDS = int(os.getenv("LOS_CHECK_INTERVAL_SECONDS", "60"))


def job():
    db = SessionLocal()
    try:
        alerts = run_los_check(db)
        db.add_all(alerts)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("LOS check failed")
    finally:
        db.close()


if __name__ == "__main__":
    configure_logging()
    scheduler = BlockingScheduler(timezone=timezone.utc)
    scheduler.add_job(job, "interval", seconds=LOS_CHECK_INTERVAL_SECONDS, next_run_time=datetime.now(timezone.utc))
    logger.info(f"Worker started, LOS check interval: {LOS_CHECK_INTERVAL_SECONDS}s")
    scheduler.start()
