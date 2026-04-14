"""
DEMO FALLBACK — Try demo2 first, fall back to demo3 (ESPN) if it fails.
"""

import asyncio
import argparse
import schedule
import time
import demo2
import demo3

ESPN_SITE_KEY = "espn"

# ── Job ───────────────────────────────────────────────────────────────────────

async def job():
    # Try demo2 first
    try:
        print("=" * 58)
        print("  Trying demo2 (Playwright stealth scraper)...")
        print("=" * 58)
        await demo2.evade_and_scrape()
        demo2.push_to_github()
        print("  ✓  demo2 succeeded.")
        return
    except Exception as e:
        print(f"  ✗  demo2 failed: {e}")
        print("  → Falling back to demo3 (AI extraction, ESPN)...")

    # Fall back to demo3 ESPN only
    try:
        print("=" * 58)
        print("  Trying demo3 (AI-assisted, ESPN)...")
        print("=" * 58)
        data = await demo3.scrape_and_extract(ESPN_SITE_KEY)
        demo3.print_results(data, demo3.SITES[ESPN_SITE_KEY]["name"])
        if data:
            demo3.save_to_csv(data, "stats_espn.csv")
            demo3.save_html({ESPN_SITE_KEY: data}, "dashboard.html")
            demo3.push_to_github()
        print("  ✓  demo3 succeeded.")
    except Exception as e:
        print(f"  ✗  demo3 also failed: {e}")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", action="store_true", help="Run every 5 minutes")
    args = parser.parse_args()

    asyncio.run(job())

    if args.schedule:
        schedule.every(5).minutes.do(lambda: asyncio.run(job()))
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)