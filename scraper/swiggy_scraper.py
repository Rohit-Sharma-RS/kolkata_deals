"""
swiggy_scraper.py — Scrapes restaurant deals from Swiggy for Kolkata (Salt Lake).

Strategy:
  1. Hit Swiggy's internal restaurant listing API (used by their web app).
  2. Each restaurant entry contains an "offer" array — extract discount info.
  3. Parse, normalise, and return a list of deal dicts.

Swiggy API endpoint (no auth required, mimics the web app):
  https://www.swiggy.com/dapi/restaurants/list/v5
"""

import logging
import re
from typing import List, Dict
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import SWIGGY_LAT, SWIGGY_LON, MIN_DISCOUNT_PERCENT
from scraper.base_scraper import fetch_json, random_headers, parse_discount_from_text, classify_offer_type

logger = logging.getLogger(__name__)

SWIGGY_LIST_URL = "https://www.swiggy.com/dapi/restaurants/list/v5"

SWIGGY_HEADERS = {
    **random_headers("https://www.swiggy.com/"),
    "Content-Type": "application/json",
}


def _build_params(offset: int = 0) -> dict:
    return {
        "lat": SWIGGY_LAT,
        "lng": SWIGGY_LON,
        "is-seo-homepage": "false",
        "page_type": "DESKTOP_WEB_LISTING",
        "offset": offset,
    }


def _extract_offers_from_restaurant(rest: dict) -> List[str]:
    """Dig into nested Swiggy JSON to find offer strings."""
    offers = []
    # Path 1: info.aggregatedDiscountInfoV3
    try:
        disc = rest["info"]["aggregatedDiscountInfoV3"]
        header = disc.get("header", "")
        sub    = disc.get("subHeader", "")
        if header:
            offers.append(f"{header} {sub}".strip())
    except (KeyError, TypeError):
        pass

    # Path 2: info.aggregatedDiscountInfo
    try:
        disc2 = rest["info"]["aggregatedDiscountInfo"]
        if disc2:
            offers.append(str(disc2))
    except (KeyError, TypeError):
        pass

    # Path 3: info.offers
    try:
        for o in rest["info"].get("offers", []):
            if isinstance(o, dict):
                offers.append(o.get("offerLogo", "") + " " + o.get("header", ""))
            elif isinstance(o, str):
                offers.append(o)
    except (KeyError, TypeError):
        pass

    return [o.strip() for o in offers if o.strip()]


def _parse_restaurant(rest: dict) -> List[Dict]:
    """Convert a single Swiggy restaurant JSON blob into deal dicts."""
    deals = []
    try:
        info = rest.get("info", {})
        name = info.get("name", "Unknown")
        location = info.get("locality", "") or info.get("areaName", "")
        area = info.get("areaName", "")
        cuisine = ", ".join(info.get("cuisines", [])[:3])
        rating = float(info.get("avgRating", 0) or 0)
        rest_url = f"https://www.swiggy.com/restaurants/{name.lower().replace(' ', '-')}-{info.get('id','')}"

        # Note: Swiggy's listing API is already queried with your lat/lon
        # and returns restaurants naturally sorted by distance.
        # Per-restaurant coordinates are not reliably available in this API
        # response, so we trust the API's own proximity scoping.

        offers = _extract_offers_from_restaurant(rest)
        if not offers:
            return deals

        for offer_text in offers:
            discount_pct = parse_discount_from_text(offer_text)
            offer_type   = classify_offer_type(offer_text)

            # Filter out low/zero discount offers
            if discount_pct < MIN_DISCOUNT_PERCENT and offer_type not in ("bogo",):
                continue

            # Parse min order / max discount from offer text
            min_order, max_discount = 0, 0
            mo_match = re.search(r"on orders? above ₹?([\d,]+)", offer_text, re.I)
            if mo_match:
                min_order = int(mo_match.group(1).replace(",", ""))
            md_match = re.search(r"upto? ₹?([\d,]+)|max ₹?([\d,]+)", offer_text, re.I)
            if md_match:
                max_discount = int((md_match.group(1) or md_match.group(2)).replace(",", ""))

            deals.append({
                "platform":        "swiggy",
                "restaurant_name": name,
                "location":        location,
                "area":            area,
                "cuisine":         cuisine,
                "rating":          rating,
                "discount_pct":    discount_pct,
                "offer_type":      offer_type,
                "offer_title":     offer_text,
                "min_order":       min_order,
                "max_discount":    max_discount,
                "restaurant_url":  rest_url,
            })

    except Exception as e:
        logger.debug("Error parsing Swiggy restaurant: %s", e)

    return deals


def _walk_swiggy_response(data: dict) -> List[dict]:
    """Recursively find restaurant cards inside nested Swiggy JSON."""
    restaurants = []
    try:
        cards = data["data"]["cards"]
        for card in cards:
            # Different nesting depths depending on Swiggy API version
            try:
                rlist = card["card"]["card"]["gridElements"]["infoWithStyle"]["restaurants"]
                restaurants.extend(rlist)
                continue
            except (KeyError, TypeError):
                pass
            try:
                rlist = card["card"]["card"]["restaurants"]
                restaurants.extend(rlist)
            except (KeyError, TypeError):
                pass
    except (KeyError, TypeError) as e:
        logger.debug("Swiggy JSON structure traversal failed: %s", e)
    return restaurants


def scrape_swiggy(max_pages: int = 3) -> List[Dict]:
    """
    Main entry point. Scrapes up to max_pages of Swiggy listing.
    Returns list of normalised deal dicts.
    """
    all_deals: List[Dict] = []
    logger.info("🟠 Starting Swiggy scrape for Salt Lake / Kolkata...")

    for page in range(max_pages):
        offset = page * 15
        params = _build_params(offset)
        try:
            data = fetch_json(SWIGGY_LIST_URL, headers=SWIGGY_HEADERS, params=params)
            if not data:
                break

            restaurants = _walk_swiggy_response(data)
            if not restaurants:
                logger.info("No more Swiggy restaurants at offset %d", offset)
                break

            page_deals = []
            for rest in restaurants:
                page_deals.extend(_parse_restaurant(rest))

            logger.info("Swiggy page %d: %d restaurants → %d deals found",
                        page + 1, len(restaurants), len(page_deals))
            all_deals.extend(page_deals)

        except Exception as e:
            logger.error("Swiggy scrape error at page %d: %s", page + 1, e)
            break

    logger.info("🟠 Swiggy scrape complete: %d total deals", len(all_deals))
    return all_deals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    deals = scrape_swiggy()
    for d in deals[:5]:
        print(f"[{d['discount_pct']}%] {d['restaurant_name']} — {d['offer_title']}")
