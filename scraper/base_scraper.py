"""
base_scraper.py — Shared HTTP utilities, headers rotation, retry logic.
"""

import time
import random
import logging
import re
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)

# Rotating user-agent pool
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Android 14; Mobile; rv:124.0) Gecko/124.0 Firefox/124.0",
]


def random_headers(referer: str = "https://www.google.com") -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "DNT": "1",
        "Connection": "keep-alive",
    }


def polite_delay():
    """Sleep with a small random jitter to avoid rate-limiting."""
    t = REQUEST_DELAY_SECONDS + random.uniform(0.5, 1.5)
    time.sleep(t)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def fetch_json(url: str, headers: dict = None, params: dict = None, timeout: int = 15) -> Optional[dict]:
    """GET a URL and return parsed JSON, with retries."""
    headers = headers or random_headers()
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        polite_delay()
        return resp.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def fetch_html(url: str, headers: dict = None, timeout: int = 15) -> Optional[str]:
    """GET a URL and return HTML text, with retries."""
    headers = headers or random_headers()
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        polite_delay()
        return resp.text


def parse_discount_from_text(text: str) -> int:
    """
    Extract the highest discount percentage from an offer string.
    e.g. '40% off up to ₹120' → 40
         'Flat ₹100 off'       → 0  (rupee discount, not %)
         'Buy 1 Get 1 Free'    → 50 (BOGO treated as 50%)
         '60% off on orders'   → 60
    """
    if not text:
        return 0
    text_lower = text.lower()

    # BOGO
    if "buy 1 get 1" in text_lower or "bogo" in text_lower or "1+1" in text_lower:
        return 50

    # Free delivery only — small benefit, treat as 5%
    if "free delivery" in text_lower and "%" not in text_lower:
        return 5

    # % off
    matches = re.findall(r"(\d+)\s*%", text)
    if matches:
        return max(int(m) for m in matches)

    return 0


def classify_offer_type(text: str) -> str:
    if not text:
        return "discount"
    t = text.lower()
    if "free delivery" in t and "%" not in t:
        return "free_delivery"
    if "buy 1 get 1" in t or "bogo" in t or "1+1" in t:
        return "bogo"
    if "flat" in t and "₹" in t and "%" not in t:
        return "flat_rupee"
    if "%" in t:
        return "percent_off"
    return "discount"
