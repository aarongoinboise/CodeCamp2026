import demo4
import asyncio
import argparse
import schedule
import time

SITES = {
    "sports-ref": {
        "name": "Sports Reference",
        "url": "https://www.sports-reference.com/cbb/boxscores/2026-04-06-20-michigan.html",
    },
    "espn": {
        "name": "ESPN Box Score",
        "url": "https://www.espn.com/mens-college-basketball/boxscore/_/gameId/401856600",
    },
}

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", nargs="+", choices=list(SITES.keys()), default=list(SITES.keys()))
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()

    asyncio.run(demo4.run_job(args.sites))

    if args.schedule:
        schedule.every(5).minutes.do(lambda: asyncio.run(demo4.run_job(args.sites)))
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)