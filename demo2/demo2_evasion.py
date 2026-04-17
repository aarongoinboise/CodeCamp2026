"""
DEMO 2 — Getting Blocked → Getting Around It
Part A: naive requests call → 403
Part B: Playwright with stealth → box score CSV + HTML
"""

import asyncio
import argparse
import demo2

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocked", action="store_true", help="Naive scraper (gets blocked)")
    parser.add_argument("--evade",   action="store_true", help="Playwright scraper (works)")
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
        asyncio.run(demo2.evade_and_scrape())

    else:
        print("Usage:")
        print("  python demo2_evasion.py --blocked")
        print("  python demo2_evasion.py --evade")