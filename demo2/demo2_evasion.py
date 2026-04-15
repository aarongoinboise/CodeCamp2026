"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → box score CSV + HTML
"""

import asyncio
import argparse
import schedule
import time
import demo2

# ── Entry point ───────────────────────────────────────────────────────────────

async def job():
    await demo2.evade_and_scrape()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocked",  action="store_true", help="Naive scraper (gets blocked)")
    parser.add_argument("--evade",    action="store_true", help="Playwright scraper (works)")
    parser.add_argument("--schedule", action="store_true", help="Run every 5 minutes")
    args = parser.parse_args()

    if args.blocked:
        print("=" * 58)
        print("  DEMO 2A — Naive requests call")
        print("=" * 58)
        demo2.naive_scrape()

    elif args.evade:
        print("=" * 58)
        print("  DEMO 2B — Playwright with stealth")
        print("=" * 58)
        asyncio.run(job())

    elif args.schedule:
        print("=" * 58)
        print("  DEMO 2B — Running on schedule (every 5 min)")
        print("=" * 58)
        asyncio.run(job())
        schedule.every(5).minutes.do(lambda: asyncio.run(job()))
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)

    else:
        print("Usage:")
        print("  python demo2_evasion.py --blocked")
        print("  python demo2_evasion.py --evade")
        print("  python demo2_evasion.py --schedule")