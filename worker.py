import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler

from app.database import SessionLocal
from app.services import run_los_check

logger = logging.getLogger(__name__)

LOS_CHECK_INTERVAL_SECONDS = int(os.getenv("LOS_CHECK_INTERVAL_SECONDS", "60"))


def job():
    db = SessionLocal()
    try:
        run_los_check(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("LOS check failed")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(levelname)s %(name)s %(message)s",
    )
    scheduler = BlockingScheduler()
    scheduler.add_job(job, "interval", seconds=LOS_CHECK_INTERVAL_SECONDS)
    logger.info(f"Worker started, LOS check interval: {LOS_CHECK_INTERVAL_SECONDS}s")
    scheduler.start()
