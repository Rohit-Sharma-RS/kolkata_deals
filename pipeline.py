"""
pipeline.py — Main orchestration pipeline.
Run this to do a full scrape → rank → store → notify cycle.
"""

import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import TOP_DEALS_COUNT, MIN_DISCOUNT_PERCENT
from db.database import init_db, upsert_deals, get_top_deals_today, mark_notified, log_notification
from scraper.swiggy_scraper import scrape_swiggy
from scraper.zomato_scraper import scrape_zomato
from scraper.ranker import rank_deals, format_deal_summary
from notifier.telegram_notifier import send_deals

logger = logging.getLogger(__name__)


def run_pipeline(notify: bool = True) -> dict:
    """
    Full pipeline:
      1. Scrape Swiggy + Zomato
      2. Rank by discount %
      3. Store in SQLite
      4. Send Telegram notification
    Returns a result summary dict.
    """
    result = {
        "swiggy_deals": 0,
        "zomato_deals": 0,
        "total_scraped": 0,
        "stored": 0,
        "top_deals": 0,
        "notified": False,
    }

    logger.info("=" * 55)
    logger.info("🚀 Starting Kolkata Deals Pipeline")
    logger.info("=" * 55)

    # ── Step 1: Scrape ────────────────────────────────────────
    all_raw_deals = []

    try:
        swiggy_deals = scrape_swiggy()
        result["swiggy_deals"] = len(swiggy_deals)
        all_raw_deals.extend(swiggy_deals)
        logger.info("✅ Swiggy: %d deals scraped", len(swiggy_deals))
    except Exception as e:
        logger.error("❌ Swiggy scrape failed: %s", e)

    try:
        zomato_deals = scrape_zomato()
        result["zomato_deals"] = len(zomato_deals)
        all_raw_deals.extend(zomato_deals)
        logger.info("✅ Zomato: %d deals scraped", len(zomato_deals))
    except Exception as e:
        logger.error("❌ Zomato scrape failed: %s", e)

    result["total_scraped"] = len(all_raw_deals)
    logger.info("📦 Total raw deals collected: %d", result["total_scraped"])

    if not all_raw_deals:
        logger.warning("No deals found from any platform. Aborting pipeline.")
        return result

    # ── Step 2: Rank ──────────────────────────────────────────
    ranked = rank_deals(all_raw_deals, top_n=TOP_DEALS_COUNT)
    logger.info("🏆 Top %d deals after ranking:\n%s", len(ranked), format_deal_summary(ranked))

    # ── Step 3: Store ─────────────────────────────────────────
    init_db()
    stored = upsert_deals(all_raw_deals)   # Store ALL scraped, not just top
    result["stored"] = stored
    logger.info("💾 Stored %d new deals in database", stored)

    # ── Step 4: Notify ────────────────────────────────────────
    top_today = get_top_deals_today(limit=TOP_DEALS_COUNT, min_discount=MIN_DISCOUNT_PERCENT)
    result["top_deals"] = len(top_today)

    if notify and top_today:
        success = send_deals(top_today)
        result["notified"] = success
        if success:
            mark_notified([d["id"] for d in top_today])
            log_notification(len(top_today), f"Sent {len(top_today)} deals")
    elif not notify:
        logger.info("Notification skipped (notify=False)")

    logger.info("=" * 55)
    logger.info("✅ Pipeline complete: %s", result)
    logger.info("=" * 55)
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    run_pipeline(notify=True)
