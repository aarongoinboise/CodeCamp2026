"""
DEMO FALLBACK — Try demo2 first, fall back to demo3 (ESPN) if it fails.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import argparse
import importlib
import schedule
import time
from demo2 import demo2
from demo3 import demo3
from demo4 import demo4

DEMO3_COOLDOWN_UNTIL = 0
DEMO3_COOLDOWN_SECS  = 600


# ── Job ───────────────────────────────────────────────────────────────────────

async def job():
    global DEMO3_COOLDOWN_UNTIL
    importlib.reload(demo2)
    importlib.reload(demo3)
    importlib.reload(demo4)

    try:
        print("=" * 58)
        print("  Trying demo2 (Playwright stealth scraper)...")
        print("=" * 58)
        await demo2.evade_and_scrape(at=True)
        print("  ✓  demo2 succeeded.")
        return
    except Exception as e:
        print(f"  ✗  demo2 failed: {e}")

    if time.time() < DEMO3_COOLDOWN_UNTIL:
        print(f"  ⏭  demo3 skipped (quota cooldown), trying demo4...")
    else:
        try:
            print("=" * 58)
            print("  Trying demo3 (adapt ESPN)...")
            print("=" * 58)
            demo3.run_espn(at=True)
            print("  ✓  demo3 succeeded.")
            return
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                DEMO3_COOLDOWN_UNTIL = time.time() + DEMO3_COOLDOWN_SECS
                print(f"  ✗  demo3 quota hit, cooling down {DEMO3_COOLDOWN_SECS}s...")
            else:
                print(f"  ✗  demo3 failed: {e}")

    try:
        print("=" * 58)
        print("  Trying demo4 (no-AI fallback)...")
        print("=" * 58)
        demo4.run(at=True)
        print("  ✓  demo4 succeeded.")
        return
    except Exception as e:
        print(f"  ✗  demo4 failed: {e}")

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