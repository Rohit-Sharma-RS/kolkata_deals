"""
database.py — SQLite storage layer
Handles all DB operations: create tables, insert deals, query top deals,
deduplicate, and snapshot history.
"""

import sqlite3
import logging
from datetime import date, datetime
from typing import List, Dict, Optional
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS deals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            platform        TEXT NOT NULL,
            restaurant_name TEXT NOT NULL,
            location        TEXT,
            area            TEXT,
            cuisine         TEXT,
            rating          REAL DEFAULT 0.0,
            cost_for_two    TEXT DEFAULT '',
            discount_pct    INTEGER DEFAULT 0,
            offer_type      TEXT,
            offer_title     TEXT,
            min_order       INTEGER DEFAULT 0,
            max_discount    INTEGER DEFAULT 0,
            restaurant_url  TEXT,
            scraped_date    TEXT NOT NULL,
            scraped_at      TEXT NOT NULL,
            is_notified     INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at     TEXT NOT NULL,
            deals_count INTEGER,
            message     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_scraped_date ON deals(scraped_date);
        CREATE INDEX IF NOT EXISTS idx_discount     ON deals(discount_pct DESC);
        CREATE INDEX IF NOT EXISTS idx_platform     ON deals(platform);
        """)

    # Migrate existing DBs that don't have cost_for_two yet
    with get_connection() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(deals)").fetchall()]
        if "cost_for_two" not in cols:
            conn.execute("ALTER TABLE deals ADD COLUMN cost_for_two TEXT DEFAULT ''")
            logger.info("Migrated DB: added cost_for_two column")
    logger.info("Database initialised at %s", DB_PATH)


def upsert_deals(deals: List[Dict]) -> int:
    """
    Insert deals, skipping exact duplicates (same restaurant + offer + date).
    Returns count of newly inserted rows.
    """
    inserted = 0
    today = date.today().isoformat()
    now   = datetime.now().isoformat()

    with get_connection() as conn:
        for d in deals:
            # Check for duplicate
            exists = conn.execute("""
                SELECT 1 FROM deals
                WHERE restaurant_name = ?
                  AND offer_title     = ?
                  AND scraped_date    = ?
                  AND platform        = ?
                LIMIT 1
            """, (d.get("restaurant_name"), d.get("offer_title"),
                  today, d.get("platform"))).fetchone()

            if not exists:
                conn.execute("""
                    INSERT INTO deals
                        (platform, restaurant_name, location, area, cuisine,
                         rating, cost_for_two, discount_pct, offer_type, offer_title,
                         min_order, max_discount, restaurant_url,
                         scraped_date, scraped_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    d.get("platform", ""),
                    d.get("restaurant_name", "Unknown"),
                    d.get("location", ""),
                    d.get("area", ""),
                    d.get("cuisine", ""),
                    float(d.get("rating", 0)),
                    d.get("cost_for_two", ""),
                    int(d.get("discount_pct", 0)),
                    d.get("offer_type", "discount"),
                    d.get("offer_title", ""),
                    int(d.get("min_order", 0)),
                    int(d.get("max_discount", 0)),
                    d.get("restaurant_url", ""),
                    today,
                    now,
                ))
                inserted += 1

    logger.info("Upserted %d new deals into DB", inserted)
    return inserted


def get_top_deals_today(limit: int = 10, min_discount: int = 10) -> List[Dict]:
    """
    Fetch today's top deals ranked by discount_pct DESC.
    """
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM deals
            WHERE scraped_date = ?
              AND discount_pct >= ?
            ORDER BY discount_pct DESC, rating DESC
            LIMIT ?
        """, (today, min_discount, limit)).fetchall()
    return [dict(r) for r in rows]


def mark_notified(deal_ids: List[int]):
    if not deal_ids:
        return
    with get_connection() as conn:
        conn.execute(
            f"UPDATE deals SET is_notified=1 WHERE id IN ({','.join('?'*len(deal_ids))})",
            deal_ids
        )


def log_notification(deals_count: int, message: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO notification_log (sent_at, deals_count, message) VALUES (?,?,?)",
            (datetime.now().isoformat(), deals_count, message)
        )


def get_stats() -> Dict:
    with get_connection() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        today_c = conn.execute(
            "SELECT COUNT(*) FROM deals WHERE scraped_date=?",
            (date.today().isoformat(),)
        ).fetchone()[0]
        notifs  = conn.execute("SELECT COUNT(*) FROM notification_log").fetchone()[0]
    return {"total_deals": total, "today_deals": today_c, "notifications_sent": notifs}
