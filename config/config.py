"""
config.py — Centralized configuration loader
Reads from .env file and provides typed settings throughout the app.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── User Location ─────────────────────────────────────────────────────
USER_LOCALITY: str  = os.getenv("USER_LOCALITY", "Salt Lake Sector V")
USER_LAT: float     = float(os.getenv("USER_LAT", "22.5804"))
USER_LON: float     = float(os.getenv("USER_LON", "88.4183"))
SEARCH_RADIUS_KM: float = float(os.getenv("SEARCH_RADIUS_KM", "7"))

# ── Scheduler ─────────────────────────────────────────────────────────
NOTIFY_HOUR: int    = int(os.getenv("NOTIFY_HOUR", "18"))
NOTIFY_MINUTE: int  = int(os.getenv("NOTIFY_MINUTE", "0"))

# ── Scraper ───────────────────────────────────────────────────────────
TOP_DEALS_COUNT: int         = int(os.getenv("TOP_DEALS_COUNT", "10"))
MIN_DISCOUNT_PERCENT: int    = int(os.getenv("MIN_DISCOUNT_PERCENT", "10"))
REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))

# ── Paths ─────────────────────────────────────────────────────────────
# config/ is one level deep — go up to project root
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(BASE_DIR, "db", "deals.db")
LOG_PATH  = os.path.join(BASE_DIR, "logs", "app.log")

# ── Kolkata Zomato City ID ────────────────────────────────────────────
ZOMATO_CITY_ID = 4   # Kolkata's city ID on Zomato

# ── Zomato session cookies (from browser DevTools) ───────────────────
ZOMATO_COOKIES: str = os.getenv("ZOMATO_COOKIES", "")

# ── Swiggy Kolkata lat/lon (used in API requests) ────────────────────
SWIGGY_LAT = USER_LAT
SWIGGY_LON = USER_LON

def validate():
    """Call at startup to catch missing critical config."""
    missing = []
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise EnvironmentError(
            f"Missing required env vars: {', '.join(missing)}\n"
            f"Please fill in your .env file (copy from .env.example)"
        )
