"""Quick smoke test — parse the sample zomato_page_html file."""
import sys
sys.path.insert(0, ".")

from bs4 import BeautifulSoup
from scraper.zomato_scraper import _parse_cards_from_soup

with open("zomato_page_html", encoding="utf-8") as f:
    html = f.readline()  # first line is the HTML blob

soup = BeautifulSoup(html, "lxml")
deals = _parse_cards_from_soup(soup)

for d in deals:
    print(f"[{d['discount_pct']}%] {d['restaurant_name']} ({d['area']}) -- {d['offer_title']} | {d['rating']}")

print(f"\nTotal: {len(deals)} deals parsed from sample HTML")
