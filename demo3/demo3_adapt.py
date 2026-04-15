import demo3
import argparse
import schedule
import time
import asyncio

# =============================================================================
# JOB
# =============================================================================

async def run_job(source_args):
    html = demo3.load_html(source_args)
    data = demo3.scrape_resilient(html)
    demo3.send_email(data)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["v1", "v2", "v3", "espn"], required=True)
    parser.add_argument("--file",     help="local file path for v1/v2/v3")
    parser.add_argument("--schedule", action="store_true")
    args = parser.parse_args()

    class Args:
        v1 = v2 = v3 = espn = None

    source_args = Args()
    if args.source == "espn":
        source_args.espn = True
    elif args.source == "v1":
        source_args.v1 = args.file
    elif args.source == "v2":
        source_args.v2 = args.file
    elif args.source == "v3":
        source_args.v3 = args.file

    await run_job(source_args)

    if args.schedule:
        def job():
            demo3.asyncio.run(run_job(source_args))

        schedule.every(5).minutes.do(job)
        print("Running every 5 minutes. Press CTRL+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())