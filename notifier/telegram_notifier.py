"""
telegram_notifier.py — Sends formatted deal notifications via Telegram Bot API.
Uses python-telegram-bot v21 async interface.
"""

import asyncio
import logging
from typing import List, Dict
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, USER_LOCALITY

logger = logging.getLogger(__name__)

PLATFORM_EMOJI = {"swiggy": "🟠", "zomato": "🔴"}
OFFER_EMOJI    = {
    "percent_off":   "🏷️",
    "bogo":          "🎁",
    "flat_rupee":    "💰",
    "free_delivery": "🚚",
    "discount":      "✂️",
}


def _esc(text: str) -> str:
    """Escape HTML special chars for Telegram HTML parse mode."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _format_deal_message(deals: List[Dict]) -> str:
    """Build the full Telegram message (HTML formatted)."""
    today   = date.today().strftime("%A, %d %B %Y")
    locality = USER_LOCALITY

    header = (
        f"🍽️ <b>Top {len(deals)} Restaurant Deals Today</b>\n"
        f"📍 {locality} | 📅 {today}\n"
        f"{'─'*34}\n\n"
    )

    body_parts = []
    for i, deal in enumerate(deals, 1):
        p_emoji  = PLATFORM_EMOJI.get(deal["platform"], "🍴")
        o_emoji  = OFFER_EMOJI.get(deal["offer_type"], "✂️")
        name     = _esc(deal["restaurant_name"])
        disc     = deal["discount_pct"]
        offer    = _esc(deal["offer_title"])
        cuisine  = _esc(deal.get("cuisine", "") or "")
        rating   = deal.get("rating", 0)
        area     = _esc(deal.get("area", "") or deal.get("location", "") or "")
        url      = (deal.get("restaurant_url", "") or "").strip()
        min_ord  = deal.get("min_order", 0)
        max_disc = deal.get("max_discount", 0)
        cost_two = _esc(deal.get("cost_for_two", "") or "")

        # Build each deal block
        lines = [f"{i}. {p_emoji} <b>{name}</b>"]
        if area:
            lines.append(f"   📍 {area}")
        if cuisine:
            lines.append(f"   🍜 {cuisine}")
        if rating:
            lines.append(f"   ⭐ {rating}")
        if cost_two:
            lines.append(f"   👥 {cost_two}")
        lines.append(f"   {o_emoji} <b>{disc}% OFF</b> — {offer}")
        if min_ord:
            lines.append(f"   🛒 Min order: ₹{min_ord}")
        if max_disc:
            lines.append(f"   📉 Max discount: ₹{max_disc}")
        # Only add the link if URL is non-empty and looks valid
        if url and url.startswith("http"):
            safe_url = url.replace("&", "&amp;").replace("'", "%27").replace('"', "%22")
            lines.append(f'   🔗 <a href="{safe_url}">View</a>')

        body_parts.append("\n".join(lines))

    body = "\n\n".join(body_parts)

    footer = (
        f"\n\n{'─'*34}\n"
        f"💡 <i>Deals scraped from Zomato &amp; Swiggy</i>\n"
        f"🤖 <i>KolkataDealBot — Salt Lake Edition</i>"
    )

    return header + body + footer


async def _send_async(message: str) -> bool:
    """Send via Telegram Bot API async."""
    try:
        from telegram import Bot
        from telegram.constants import ParseMode
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        async with bot:
            # Telegram message max is 4096 chars — split if needed
            if len(message) <= 4096:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            else:
                # Split at deal boundaries
                chunks = _split_message(message)
                for chunk in chunks:
                    await bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=chunk,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
        return True
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        return False


def _split_message(message: str, max_len: int = 4000) -> List[str]:
    """Split long messages at newline boundaries."""
    chunks, current = [], ""
    for line in message.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)
    return chunks


def send_deals(deals: List[Dict]) -> bool:
    """
    Public interface. Build message and send via Telegram.
    Returns True on success.
    """
    if not deals:
        logger.warning("No deals to send")
        return False

    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN not set in .env!")
        return False

    message = _format_deal_message(deals)
    logger.info("Sending %d deals to Telegram chat %s", len(deals), TELEGRAM_CHAT_ID)

    success = asyncio.run(_send_async(message))
    if success:
        logger.info("✅ Telegram notification sent successfully")
    return success


def send_startup_message() -> bool:
    """Send a test/startup confirmation message."""
    msg = (
        "✅ <b>KolkataDealBot is now active!</b>\n\n"
        f"📍 Area: <b>{USER_LOCALITY}</b>\n"
        "🟠 Swiggy + 🔴 Zomato deals tracked\n"
        "🕕 Daily notification at 6:00 PM\n\n"
        "<i>You'll receive the top discount deals every evening. "
        "Stay hungry, save money! 🍛</i>"
    )
    return asyncio.run(_send_async(msg))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test with dummy data
    test_deals = [
        {
            "platform": "swiggy", "restaurant_name": "Arsalan", "area": "Salt Lake",
            "cuisine": "Biryani, Mughlai", "rating": 4.5, "discount_pct": 40,
            "offer_type": "percent_off", "offer_title": "40% off up to ₹80",
            "min_order": 199, "max_discount": 80, "restaurant_url": "https://swiggy.com"
        },
        {
            "platform": "zomato", "restaurant_name": "Barbeque Nation", "area": "Sector V",
            "cuisine": "BBQ, Grills", "rating": 4.2, "discount_pct": 30,
            "offer_type": "percent_off", "offer_title": "30% off on all orders",
            "min_order": 300, "max_discount": 150, "restaurant_url": "https://zomato.com"
        },
    ]
    print(_format_deal_message(test_deals))
