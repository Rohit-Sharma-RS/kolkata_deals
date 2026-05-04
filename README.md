# 🍽️ KolkataDealBot — Restaurant Deal Tracker

Automatically scrapes **Zomato** and **Swiggy** for the best restaurant deals **in your given location**, ranks them by discount %, stores them daily, and sends a **Telegram notification at your specified time** every day.

---

## 📁 Project Structure

```
kolkata_deals/
├── .env
├── requirements.txt
├── pipeline.py           ← Main orchestration (scrape → rank → store → notify)
├── scheduler.py          ← APScheduler daemon (run this to start the bot)
├── cli.py                ← Command-line tool for manual control
│
├── config/
│   └── config.py         ← All settings loaded from .env
│
├── scraper/
│   ├── base_scraper.py   ← HTTP utilities, retry logic, offer parsers
│   ├── swiggy_scraper.py ← Swiggy deal scraper
│   ├── zomato_scraper.py ← Zomato deal scraper
│   └── ranker.py         ← Scoring + deduplication engine
│
├── db/
│   ├── database.py       ← SQLite storage layer
│   └── deals.db          ← Auto-created on first run
│
├── notifier/
│   └── telegram_notifier.py  ← Telegram Bot sender
│
└── logs/
    └── app.log           ← Auto-created on first run
```

---

## ⚡ Quick Start (5 minutes)

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Create a Telegram Bot

1. Open Telegram → search **@BotFather** → send `/newbot`
2. Follow the prompts, give your bot a name like `KolkataDealBot`
3. Copy the **API token** it gives you (looks like `7123456789:AAFxxx...`)

### Step 3 — Get your Telegram Chat ID

1. Open Telegram → search **@userinfobot** → send `/start`
2. It replies with your **Chat ID** (a number like `987654321`)

### Step 4 — Configure .env

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=987654321
```

### Step 5 — Test the bot

```bash
python cli.py test-bot
```

You should receive a welcome message in Telegram. ✅

### Step 6 — Run once manually

```bash
python cli.py run
```

### Step 7 — Start the daily scheduler

```bash
python scheduler.py
```

Deals will arrive every day at **your specified time** automatically. 🎉

---

## 🛠️ CLI Commands

| Command                  | Description                            |
| ------------------------ | -------------------------------------- |
| `python cli.py run`      | Full pipeline: scrape + store + notify |
| `python cli.py scrape`   | Scrape only, no Telegram message       |
| `python cli.py notify`   | Send today's stored deals to Telegram  |
| `python cli.py top`      | Print today's top deals in terminal    |
| `python cli.py stats`    | Show database statistics               |
| `python cli.py test-bot` | Send a test Telegram message           |
| `python cli.py setup`    | Interactive setup wizard               |

---

## ⚙️ Configuration Options (.env)

| Variable                | Default            | Description                     |
| ----------------------- | ------------------ | ------------------------------- |
| `TELEGRAM_BOT_TOKEN`    | —                  | Required. From @BotFather       |
| `TELEGRAM_CHAT_ID`      | —                  | Required. From @userinfobot     |
| `USER_LOCALITY`         | Salt Lake Sector V | Your area name (display only)   |
| `USER_LAT`              | 22.5804            | Your latitude (for Swiggy API)  |
| `USER_LON`              | 88.4183            | Your longitude (for Swiggy API) |
| `NOTIFY_HOUR`           | 18                 | Notification hour (24h, IST)    |
| `NOTIFY_MINUTE`         | 0                  | Notification minute             |
| `TOP_DEALS_COUNT`       | 10                 | Number of deals in notification |
| `MIN_DISCOUNT_PERCENT`  | 10                 | Ignore deals below this %       |
| `REQUEST_DELAY_SECONDS` | 2                  | Delay between HTTP requests     |

---

## 🗄️ Database Schema

Deals are stored in SQLite (`db/deals.db`):

- `platform` — zomato / swiggy
- `restaurant_name`, `location`, `area`, `cuisine`, `rating`
- `discount_pct`, `offer_type`, `offer_title`
- `min_order`, `max_discount`, `restaurant_url`
- `scraped_date`, `scraped_at`, `is_notified`

Historical data accumulates over time — great for trend analysis!

---

## ⚠️ Notes

- Zomato and Swiggy occasionally change their internal API structures. If scraping breaks, the HTML fallback parser activates automatically.
- This tool is for personal use only. Use responsibly and respect the platforms' terms of service.
- Running on a Raspberry Pi or cheap VPS keeps it running 24/7 without leaving your PC on.
