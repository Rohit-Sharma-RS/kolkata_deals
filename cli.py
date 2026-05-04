"""
cli.py — Command-line interface for manual control and testing.

Usage:
  python cli.py run          # Full pipeline (scrape + store + notify)
  python cli.py scrape       # Scrape only, no notification
  python cli.py notify       # Send notification with today's stored deals
  python cli.py stats        # Show DB stats
  python cli.py top          # Print today's top deals to console
  python cli.py test-bot     # Send a test message to Telegram
  python cli.py setup        # Interactive setup wizard
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output on Windows so Rich can render emoji without crashing
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


def cmd_run():
    from pipeline import run_pipeline
    console.print("[bold green]🚀 Running full pipeline...[/]")
    result = run_pipeline(notify=True)
    console.print(f"\n[bold]Results:[/]")
    for k, v in result.items():
        console.print(f"  {k}: {v}")


def cmd_scrape():
    from pipeline import run_pipeline
    console.print("[bold yellow]🔍 Scraping only (no notification)...[/]")
    result = run_pipeline(notify=False)
    console.print(f"Scraped: {result['total_scraped']} deals stored: {result['stored']}")


def cmd_notify():
    from config.config import TOP_DEALS_COUNT, MIN_DISCOUNT_PERCENT
    from db.database import get_top_deals_today
    from notifier.telegram_notifier import send_deals
    deals = get_top_deals_today(limit=TOP_DEALS_COUNT, min_discount=MIN_DISCOUNT_PERCENT)
    if not deals:
        console.print("[red]No deals found for today. Run 'scrape' first.[/]")
        return
    send_deals(deals)
    console.print(f"[green]Sent {len(deals)} deals to Telegram.[/]")


def cmd_stats():
    from db.database import get_stats
    stats = get_stats()
    console.print("\n[bold cyan]📊 Database Stats[/]")
    for k, v in stats.items():
        console.print(f"  {k}: [bold]{v}[/]")


def cmd_top():
    from config.config import TOP_DEALS_COUNT, MIN_DISCOUNT_PERCENT
    from db.database import get_top_deals_today

    deals = get_top_deals_today(limit=TOP_DEALS_COUNT, min_discount=MIN_DISCOUNT_PERCENT)
    if not deals:
        console.print("[red]No deals found for today. Run 'scrape' first.[/]")
        return

    table = Table(title=f"Today's Top {len(deals)} Deals — Salt Lake, Kolkata")
    table.add_column("#",        style="cyan",    width=4)
    table.add_column("Disc%",    style="bold red", width=6)
    table.add_column("Platform", style="yellow",  width=8)
    table.add_column("Restaurant",               width=22)
    table.add_column("Offer",                    width=35)
    table.add_column("Rating",   style="green",   width=6)

    for i, d in enumerate(deals, 1):
        table.add_row(
            str(i),
            f"{d['discount_pct']}%",
            d["platform"],
            d["restaurant_name"],
            d["offer_title"][:35],
            str(d["rating"] or ""),
        )

    console.print(table)


def cmd_test_bot():
    from notifier.telegram_notifier import send_startup_message
    console.print("[yellow]Sending test message to Telegram...[/]")
    ok = send_startup_message()
    if ok:
        console.print("[bold green]✅ Test message sent! Check your Telegram.[/]")
    else:
        console.print("[bold red]❌ Failed. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env[/]")


def cmd_setup():
    """Interactive setup wizard."""
    console.print("\n[bold cyan]╔══════════════════════════════════╗[/]")
    console.print("[bold cyan]║   KolkataDealBot Setup Wizard    ║[/]")
    console.print("[bold cyan]╚══════════════════════════════════╝[/]\n")

    console.print("[bold]Step 1: Create your Telegram bot[/]")
    console.print("  1. Open Telegram, search [bold]@BotFather[/]")
    console.print("  2. Send: [bold]/newbot[/]")
    console.print("  3. Follow prompts, copy the [bold]API token[/]\n")

    console.print("[bold]Step 2: Get your Chat ID[/]")
    console.print("  1. Search [bold]@userinfobot[/] in Telegram")
    console.print("  2. Send [bold]/start[/] — it shows your Chat ID\n")

    console.print("[bold]Step 3: Fill in .env file[/]")
    console.print("  Edit the [bold].env[/] file in this folder:")
    console.print("  [green]TELEGRAM_BOT_TOKEN=your_token_here[/]")
    console.print("  [green]TELEGRAM_CHAT_ID=your_chat_id_here[/]\n")

    console.print("[bold]Step 4: Test the bot[/]")
    console.print("  Run: [bold]python cli.py test-bot[/]\n")

    console.print("[bold]Step 5: Start the scheduler[/]")
    console.print("  Run: [bold]python scheduler.py[/]")
    console.print("  (Keep terminal open, or use nohup/screen/systemd)\n")

    console.print("[bold green]That's it! Deals will arrive every day at 6 PM IST 🍽️[/]")


COMMANDS = {
    "run":      cmd_run,
    "scrape":   cmd_scrape,
    "notify":   cmd_notify,
    "stats":    cmd_stats,
    "top":      cmd_top,
    "test-bot": cmd_test_bot,
    "setup":    cmd_setup,
}


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        console.print("\n[bold]KolkataDealBot CLI[/]")
        console.print("Usage: [cyan]python cli.py <command>[/]\n")
        console.print("Commands:")
        console.print("  [green]run[/]       — Full pipeline (scrape + store + notify)")
        console.print("  [green]scrape[/]    — Scrape only, no notification")
        console.print("  [green]notify[/]    — Send today's deals to Telegram")
        console.print("  [green]stats[/]     — Show database statistics")
        console.print("  [green]top[/]       — Print today's top deals in terminal")
        console.print("  [green]test-bot[/]  — Send a test Telegram message")
        console.print("  [green]setup[/]     — Interactive setup wizard\n")
        sys.exit(0)

    COMMANDS[sys.argv[1]]()
