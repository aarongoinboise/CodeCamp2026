import demo3
import argparse

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["v1", "v2", "v3", "espn"], required=True)
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
    html = demo3.load_html(source_args)
    data = demo3.scrape_resilient(html)
    demo3.send_discord(data)