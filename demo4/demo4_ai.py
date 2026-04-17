import demo4
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", nargs="+", choices=list(demo4.SITES.keys()), default=list(demo4.SITES.keys()))
    args = parser.parse_args()

    demo4.run_job(args.sites)