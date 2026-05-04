"""
zomato_scraper.py — Scrapes restaurant deals from Zomato (Kolkata).

Strategy (in priority order):
  1. HTTP + session cookies (httpx) — fastest, works when Zomato session is valid.
     Targets both the dine-out page and delivery page.
  2. Playwright headful fallback — if HTTP is blocked, use a real (visible) browser
     window so Cloudflare can't detect headless mode. Scrolls to lazy-load all cards.

HTML selectors (verified from live zomato_page_html):
  - Restaurant wrapper    : div.jumbo-tracker
  - Name                  : h4.sc-1hp8d8a-0  (or any h4)
  - Offer (dine-out)      : .walkin-offer-value
  - Rating                : .sc-1q7bklc-1.cILgox  (or .sc-1q7bklc-1)
  - Cuisine               : p.sc-gggouf (first one without ₹)
  - Area                  : p.sc-cyQzhP
  - URL                   : href on nearest a[href^='/kolkata/']
"""

import logging
import re
import time
from typing import List, Dict
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    USER_LAT, USER_LON, MIN_DISCOUNT_PERCENT,
    ZOMATO_CITY_ID, ZOMATO_COOKIES, REQUEST_DELAY_SECONDS,
    SEARCH_RADIUS_KM
)
from scraper.base_scraper import parse_discount_from_text, classify_offer_type

logger = logging.getLogger(__name__)

# ─── URLs ─────────────────────────────────────────────────────────────────────
ZOMATO_DINEOUT_URL  = "https://www.zomato.com/kolkata/dine-out?dining_payment_enabled_flag=true"
ZOMATO_DELIVERY_URL = "https://www.zomato.com/kolkata/order-food-online"


# ─── Haversine distance ────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two (lat, lon) points in kilometres.
    Used to validate/filter Swiggy restaurants by radius.
    """
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ─── HTTP Headers ─────────────────────────────────────────────────────────────

def _zomato_headers() -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }
    if ZOMATO_COOKIES:
        headers["Cookie"] = ZOMATO_COOKIES
    return headers


def _parse_cookie_string(cookie_str: str) -> List[dict]:
    """Convert 'key=val; key2=val2' into Playwright cookie dicts."""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        cookies.append({
            "name": key.strip(),
            "value": val.strip(),
            "domain": ".zomato.com",
            "path": "/",
        })
    return cookies


# ─── Offer parsing ────────────────────────────────────────────────────────────

def _parse_offer(offer_text: str) -> Dict:
    """Extract structured discount data from an offer string."""
    result = {
        "offer_title": offer_text.strip(),
        "discount_pct": parse_discount_from_text(offer_text),
        "offer_type": classify_offer_type(offer_text),
        "min_order": 0,
        "max_discount": 0,
    }
    mo = re.search(r"(?:above|over|min(?:imum)?) (?:order of )?[₹Rs.]?([\d,]+)", offer_text, re.I)
    if mo:
        result["min_order"] = int(mo.group(1).replace(",", ""))
    md = re.search(r"(?:upto?|max|maximum) [₹Rs.]?([\d,]+)", offer_text, re.I)
    if md:
        result["max_discount"] = int(md.group(1).replace(",", ""))
    return result


# ─── HTML card parser ─────────────────────────────────────────────────────────

def _parse_cards_from_soup(soup) -> List[Dict]:
    """
    Parse restaurant cards from a BeautifulSoup object.
    Works on both dine-out and delivery page HTML.
    Only returns restaurants from the Kolkata area.
    """
    deals = []
    cards = soup.select("div.jumbo-tracker")
    logger.info("Found %d restaurant cards in HTML", len(cards))

    for card in cards:
        try:
            # Name
            name_tag = card.select_one("h4.sc-1hp8d8a-0") or card.select_one("h4")
            name = name_tag.get_text(strip=True) if name_tag else "Unknown"

            # URL
            link_tag = card.select_one("a[href^='/kolkata/']")
            rest_url = ("https://www.zomato.com" + link_tag["href"]) if link_tag else ""

            # Rating
            rating_tag = card.select_one(".sc-1q7bklc-1")
            rating = 0.0
            if rating_tag:
                try:
                    rating = float(rating_tag.get_text(strip=True))
                except ValueError:
                    pass

            # Cuisine and cost_for_two — both come from p.sc-gggouf
            # Cuisine: no ₹ sign  |  Cost: has ₹ and "for two"
            cuisine = ""
            cost_for_two = ""
            for p in card.select("p.sc-gggouf"):
                txt = p.get_text(strip=True)
                if "₹" in txt and "for two" in txt.lower():
                    cost_for_two = txt  # e.g. "₹1,000 for two"
                elif "₹" not in txt and txt:
                    cuisine = ", ".join(txt.split(",")[:3]).strip()

            # Area — must contain "Kolkata" to be valid
            area_tag = card.select_one("p.sc-cyQzhP") or card.select_one(".min-basic-info-left p")
            area = area_tag.get_text(strip=True).strip(" ,") if area_tag else ""

            # ── Kolkata-only filter ─────────────────────────────────
            if area and "kolkata" not in area.lower():
                logger.debug("Skipping non-Kolkata restaurant: %s (%s)", name, area)
                continue

            # ── Distance filter (7 km radius) ──────────────────────
            # Zomato shows "1.2 km" or "500 m" in .min-basic-info-right p
            distance_km = None
            dist_tag = card.select_one(".min-basic-info-right p")
            if dist_tag:
                dist_txt = dist_tag.get_text(strip=True).lower()
                m = re.search(r"([\d.]+)\s*km", dist_txt)
                if m:
                    distance_km = float(m.group(1))
                else:
                    m2 = re.search(r"([\d.]+)\s*m\b", dist_txt)
                    if m2:
                        distance_km = float(m2.group(1)) / 1000.0

            if distance_km is not None and distance_km > SEARCH_RADIUS_KM:
                logger.debug("Skipping %s — %.1f km > %.1f km radius", name, distance_km, SEARCH_RADIUS_KM)
                continue

            # Offer — dine-out walkin offer badge
            offer_texts = []
            walkin_tag = card.select_one(".walkin-offer-value")
            if walkin_tag:
                offer_texts.append(walkin_tag.get_text(" ", strip=True))

            # Offer — delivery discount badge (various class patterns)
            if not offer_texts:
                for sel in ("[class*='discount']", "[class*='offer']", "[class*='Offer']"):
                    for el in card.select(sel):
                        txt = el.get_text(" ", strip=True)
                        if txt and "%" in txt:
                            offer_texts.append(txt)
                            break
                    if offer_texts:
                        break

            if not offer_texts:
                continue

            for offer_text in offer_texts:
                parsed = _parse_offer(offer_text)
                if parsed["discount_pct"] < MIN_DISCOUNT_PERCENT and parsed["offer_type"] not in ("bogo",):
                    continue

                deals.append({
                    "platform":        "zomato",
                    "restaurant_name": name,
                    "location":        area,
                    "area":            area,
                    "cuisine":         cuisine,
                    "rating":          rating,
                    "cost_for_two":    cost_for_two,
                    "discount_pct":    parsed["discount_pct"],
                    "offer_type":      parsed["offer_type"],
                    "offer_title":     parsed["offer_title"],
                    "min_order":       parsed["min_order"],
                    "max_discount":    parsed["max_discount"],
                    "restaurant_url":  rest_url,
                })

        except Exception as e:
            logger.debug("Error parsing card: %s", e)

    return deals


# ─── HTTP scraper (primary) ───────────────────────────────────────────────────

def _scrape_with_http(url: str) -> List[Dict]:
    """
    Fetch the Zomato page via plain HTTPX with session cookies.
    This is the primary method — fast and reliable when session is valid.
    """
    import httpx
    from bs4 import BeautifulSoup

    logger.info("Fetching via HTTP: %s", url)
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=25,
            http2=False,  # Disable HTTP/2 to avoid protocol errors
        ) as client:
            resp = client.get(url, headers=_zomato_headers())
            resp.raise_for_status()
            logger.info("HTTP %d, %.1f KB received", resp.status_code, len(resp.content) / 1024)

        soup = BeautifulSoup(resp.text, "lxml")

        # If Zomato returns a bot/captcha page, jumbo-tracker won't be present
        if not soup.select("div.jumbo-tracker"):
            logger.warning("No restaurant cards found — Zomato may have returned a captcha/block page")
            # Log a snippet so we can diagnose
            body_text = soup.get_text()[:300].strip()
            logger.debug("Page snippet: %s", body_text)
            return []

        return _parse_cards_from_soup(soup)

    except Exception as e:
        logger.error("HTTP scrape failed for %s: %s", url, e)
        return []


# ─── Playwright scraper (fallback for when HTTP is blocked) ──────────────────

def _scrape_with_playwright(url: str) -> List[Dict]:
    """
    Use a headful (non-headless) Playwright browser to bypass Cloudflare.
    Only called if the HTTP method fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: playwright install chromium")
        return []

    from bs4 import BeautifulSoup

    deals = []
    logger.info("Launching Playwright (headful mode) for: %s", url)

    with sync_playwright() as p:
        # headless=False bypasses Cloudflare bot detection
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-http2", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
        )
        if ZOMATO_COOKIES:
            context.add_cookies(_parse_cookie_string(ZOMATO_COOKIES))

        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)

            # Wait for restaurant cards
            try:
                page.wait_for_selector("div.jumbo-tracker", timeout=20_000)
            except Exception:
                logger.warning("Cards not found after 20s — parsing whatever is there")

            time.sleep(2)

            # Scroll to load lazy content
            prev_height = 0
            for scroll_n in range(15):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                curr_height = page.evaluate("document.body.scrollHeight")
                cards = page.query_selector_all("div.jumbo-tracker")
                logger.info("Scroll %d: %d cards loaded", scroll_n + 1, len(cards))
                if curr_height == prev_height:
                    break
                prev_height = curr_height

            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            deals = _parse_cards_from_soup(soup)

        except Exception as e:
            logger.error("Playwright error: %s", e)
        finally:
            browser.close()

    return deals


# ─── Public entry point ────────────────────────────────────────────────────────

def scrape_zomato() -> List[Dict]:
    """
    Main entry point. Tries HTTP first (fast), falls back to Playwright if blocked.
    Returns list of normalised deal dicts.
    """
    all_deals: List[Dict] = []
    logger.info("Starting Zomato scrape for Kolkata...")

    for url in [ZOMATO_DINEOUT_URL, ZOMATO_DELIVERY_URL]:
        logger.info("--- Scraping: %s", url)

        # Try HTTP first
        page_deals = _scrape_with_http(url)

        # If HTTP got nothing, try Playwright as fallback
        if not page_deals:
            logger.info("HTTP returned 0 deals — trying Playwright fallback")
            page_deals = _scrape_with_playwright(url)

        logger.info("  -> %d deals from this page", len(page_deals))
        all_deals.extend(page_deals)
        time.sleep(REQUEST_DELAY_SECONDS)

    # Deduplicate by (restaurant_name, offer_title)
    seen = set()
    unique = []
    for d in all_deals:
        key = (d["restaurant_name"].lower(), d["offer_title"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(d)

    logger.info("Zomato scrape complete: %d unique deals", len(unique))
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    deals = scrape_zomato()
    for d in deals[:15]:
        print(f"[{d['discount_pct']}%] {d['restaurant_name']} ({d['area']}) -- {d['offer_title']}")
    print(f"\nTotal: {len(deals)} deals")
