"""
scheduler.py — APScheduler daemon that runs the pipeline daily at 6 PM.
Run this as a background process: python scheduler.py
"""

import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from config.config import NOTIFY_HOUR, NOTIFY_MINUTE, validate, LOG_PATH
from db.database import init_db
from pipeline import run_pipeline
from notifier.telegram_notifier import send_startup_message

# ── Logging setup ──────────────────────────────────────────────────────
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def scheduled_job():
    """The job that runs every day at NOTIFY_HOUR:NOTIFY_MINUTE."""
    logger.info("⏰ Scheduled pipeline triggered")
    try:
        run_pipeline(notify=True)
    except Exception as e:
        logger.error("Pipeline error in scheduled run: %s", e, exc_info=True)


def main():
    # Validate config before starting
    try:
        validate()
    except EnvironmentError as e:
        logger.error("Configuration error:\n%s", e)
        sys.exit(1)

    # Initialise DB
    init_db()

    # Send startup confirmation to Telegram
    logger.info("Sending startup message to Telegram...")
    send_startup_message()

    # Set up scheduler
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        scheduled_job,
        trigger=CronTrigger(hour=NOTIFY_HOUR, minute=NOTIFY_MINUTE, timezone="Asia/Kolkata"),
        id="daily_deals",
        name="Daily Kolkata Restaurant Deals",
        max_instances=1,
        misfire_grace_time=300,  # Allow 5 min late
    )

    logger.info(
        "🕕 Scheduler started. Pipeline will run daily at %02d:%02d IST",
        NOTIFY_HOUR, NOTIFY_MINUTE
    )
    logger.info("Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
