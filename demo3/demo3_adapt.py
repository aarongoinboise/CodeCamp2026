import argparse
import asyncio
import time
import schedule

from demo3 import parse_args, load_html, scrape_resilient, save_csv


async def run_job(source_args, out_path="output.csv"):
    html = load_html(source_args)
    data = scrape_resilient(html)
    save_csv(data, out_path)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["v1", "v2", "v3", "espn"], required=True)
    parser.add_argument("--file", help="local file path for v1/v2/v3")
    parser.add_argument("--out", default="output.csv")
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

    await run_job(source_args, args.out)

    if args.schedule:
        def job():
            asyncio.run(run_job(source_args, args.out))

        schedule.every(5).minutes.do(job)

        print("Running every 5 minutes")
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())