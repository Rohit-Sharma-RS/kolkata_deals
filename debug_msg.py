"""Debug: show what the Telegram message looks like and find the broken URL."""
import sys
sys.path.insert(0, ".")
from config.config import TOP_DEALS_COUNT, MIN_DISCOUNT_PERCENT
from db.database import get_top_deals_today
from notifier.telegram_notifier import _format_deal_message

deals = get_top_deals_today(limit=TOP_DEALS_COUNT, min_discount=MIN_DISCOUNT_PERCENT)
msg = _format_deal_message(deals)

# Find byte offset 2400
encoded = msg.encode("utf-8")
print(repr(encoded[2380:2450]))
print("---")
# Print all URLs
for i, d in enumerate(deals, 1):
    url = d.get("restaurant_url", "")
    print(f"{i}. [{d['restaurant_name']}] url={repr(url)}")
