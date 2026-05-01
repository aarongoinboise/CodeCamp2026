import demo3
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--v1",   action="store_true")
    group.add_argument("--v2",   action="store_true")
    group.add_argument("--v3",   action="store_true")
    group.add_argument("--espn", action="store_true")
    args = parser.parse_args()

    if args.v1:   demo3.run_v1()
    elif args.v2: demo3.run_v2()
    elif args.v3: demo3.run_v3()
    elif args.espn: demo3.run_espn()