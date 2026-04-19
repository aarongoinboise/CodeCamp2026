"""
DEMO FALLBACK — Try demo2 first, fall back to demo3 (ESPN) if it fails.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import argparse
import schedule
import time
from demo2 import demo2
from demo3 import demo3


# ── Job ───────────────────────────────────────────────────────────────────────

async def job():
    # Try demo2 first
    try:
        print("=" * 58)
        print("  Trying demo2 (Playwright stealth scraper)...")
        print("=" * 58)
        await demo2.evade_and_scrape()
        print("  ✓  demo2 succeeded.")
        return
    except Exception as e:
        print(f"  ✗  demo2 failed: {e}")
        print("  → Falling back to demo3 (AI extraction, ESPN)...")

    # Fall back to demo3 ESPN only
    try:
        print("=" * 58)
        print("  Trying demo3 (adapt ESPN)...")
        print("=" * 58)
        demo3.run_espn()
        print("  ✓  demo3 succeeded.")
        return
    except Exception as e:
        print(f"  ✗  demo3 failed: {e}")
        

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