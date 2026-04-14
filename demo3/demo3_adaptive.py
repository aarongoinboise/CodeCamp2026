import json
import os
import sys
import csv
import argparse
import asyncio
import subprocess
import schedule
import time
import google.generativeai as genai
from datetime import datetime
import demo3

# ── Target sites ───────────────────────────────────────────────────────────────

SITES = {
    "sports-ref": {
        "name": "Sports Reference (CBB)",
        "url": "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html",
        "note": "Dense stats tables, Wikipedia-style HTML, minimal JS",
    },
    "espn": {
        "name": "ESPN Box Score",
        "url": "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600",
        "note": "React-rendered SPA, requires JS execution, ESPN proprietary classes",
    },
}

# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="AI-Assisted Adaptive Scraper — works across different sites without site-specific parsers."
    )
    parser.add_argument(
        "--site",
        choices=["sports-ref", "espn", "both"],
        default="both",
        help="Which site to scrape (default: both, to demonstrate cross-site resilience)"
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Run every 5 minutes"
    )
    args = parser.parse_args()

    print("=" * 58)
    print("  DEMO 3 — AI-Assisted Adaptive Scraper")
    print("  One extraction function. Two totally different sites.")
    print("=" * 58)

    if not os.environ.get("GEMINI_API_KEY"):
        print("\n  ⚠  GEMINI_API_KEY not set.")
        print("     Get a free key at: https://aistudio.google.com")
        print("     export GEMINI_API_KEY=your_key_here\n")
        sys.exit(1)

    sites_to_run = (
        ["sports-ref", "espn"] if args.site == "both"
        else [args.site]
    )

    async def job():
        all_results = {}
        for site_key in sites_to_run:
            try:
                data = await demo3.scrape_and_extract(site_key)
                all_results[site_key] = data
                demo3.print_results(data, SITES[site_key]["name"])
                if data:
                    csv_file = f"stats_{site_key.replace('-', '_')}.csv"
                    demo3.save_to_csv(data, csv_file)
            except Exception as e:
                print(f"\n  ✗  Failed to scrape {SITES[site_key]['name']}: {e}")
                all_results[site_key] = {}

        demo3.save_html(all_results, "dashboard.html")
        demo3.push_to_github()

        # ── The punchline ──────────────────────────────────────────────────────
        print("\n" + "=" * 58)
        print("  THE KEY INSIGHT")
        print("=" * 58)
        print("""
  Sports Reference:  Dense Wikipedia-style tables, static HTML,
                     class names like 'right', 'center', 'thead'.

  ESPN:              React SPA, JavaScript-rendered DOM, proprietary
                     class hashes like 'ScoreCell__Score--xxxx'.

  Traditional approach: Two separate scrapers. Constant maintenance.
                         Break every time either site updates.

  This approach: ONE extract_with_ai() function.
                 Describe WHAT you want. Not WHERE it is.
                 Same function works on any site you point it at.

  → To add a third site: just pass a new URL. Zero code changes.
""")

    await job()

    if args.schedule:
        def run_job():
            asyncio.run(job())
        schedule.every(5).minutes.do(run_job)
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())