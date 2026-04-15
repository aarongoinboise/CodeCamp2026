import asyncio
import argparse
import schedule
import time
import demo4

# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["sports-ref", "espn", "both"], default="both")
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()

    sites = ["sports-ref", "espn"] if args.site == "both" else [args.site]

    await demo4.run_job(sites)

    if args.schedule:
        def job():
            asyncio.run(demo4.run_job(sites))

        schedule.every(5).minutes.do(job)

        print("Running every 5 minutes")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())