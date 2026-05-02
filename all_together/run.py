from all_together import job
import asyncio
import argparse
import schedule
import time

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