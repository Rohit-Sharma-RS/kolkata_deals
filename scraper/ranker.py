"""
ranker.py — Deal ranking and filtering engine.
Ranks deals by discount_pct DESC (primary), then by rating (secondary).
Deduplicates same restaurant appearing on both platforms.
"""

import logging
from typing import List, Dict
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import TOP_DEALS_COUNT, MIN_DISCOUNT_PERCENT

logger = logging.getLogger(__name__)

# Offer type priority multipliers (boosts effective score)
OFFER_TYPE_BOOST = {
    "bogo":          1.10,  # Buy 1 Get 1 is great
    "percent_off":   1.00,  # Standard
    "flat_rupee":    0.80,  # Rupee discounts are context-dependent
    "free_delivery": 0.50,  # Minor benefit
    "discount":      1.00,  # Generic
}


def compute_score(deal: Dict) -> float:
    """
    Composite score for ranking.
    Primary driver: discount_pct
    Secondary: rating (small weight)
    Tertiary: offer type quality boost
    """
    disc    = deal.get("discount_pct", 0)
    rating  = deal.get("rating", 0) or 0
    boost   = OFFER_TYPE_BOOST.get(deal.get("offer_type", "discount"), 1.0)

    # Base: discount % is king
    score = disc * boost

    # Rating adds a small tie-breaker (max ~2 points at rating 5.0)
    score += rating * 0.4

    return round(score, 3)


def deduplicate(deals: List[Dict]) -> List[Dict]:
    """
    Remove near-duplicate deals.
    Rule: keep the deal with the highest discount for each restaurant+offer_type combo.
    """
    seen = {}
    for deal in deals:
        key = (
            deal["restaurant_name"].lower().strip(),
            deal.get("offer_type", ""),
        )
        if key not in seen or deal["discount_pct"] > seen[key]["discount_pct"]:
            seen[key] = deal
    return list(seen.values())


def rank_deals(deals: List[Dict], top_n: int = None) -> List[Dict]:
    """
    Filter, deduplicate, score, and rank deals.
    Returns top_n deals sorted by score DESC.
    """
    top_n = top_n or TOP_DEALS_COUNT

    # Step 1: Filter out low-quality deals
    filtered = [
        d for d in deals
        if d.get("discount_pct", 0) >= MIN_DISCOUNT_PERCENT
        or d.get("offer_type") == "bogo"
    ]
    logger.info("Ranker: %d deals after min-discount filter", len(filtered))

    # Step 2: Deduplicate
    deduped = deduplicate(filtered)
    logger.info("Ranker: %d deals after deduplication", len(deduped))

    # Step 3: Score and sort
    for deal in deduped:
        deal["_score"] = compute_score(deal)

    ranked = sorted(deduped, key=lambda d: d["_score"], reverse=True)

    logger.info("Ranker: returning top %d of %d ranked deals", top_n, len(ranked))
    return ranked[:top_n]


def format_deal_summary(deals: List[Dict]) -> str:
    """
    Create a clean text summary of ranked deals (for logging/debugging).
    """
    lines = ["Rank | Disc% | Platform | Restaurant          | Offer"]
    lines.append("-" * 70)
    for i, d in enumerate(deals, 1):
        lines.append(
            f"{i:>4} | {d['discount_pct']:>5}% | {d['platform']:>8} | "
            f"{d['restaurant_name'][:20]:<20} | {d['offer_title'][:30]}"
        )
    return "\n".join(lines)
