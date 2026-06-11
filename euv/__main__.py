"""Entry point: python3 -m euv"""
import argparse


def cli():
    ap = argparse.ArgumentParser(
        prog="euv",
        description="EUV: a terminal grand strategy game set in the "
                    "fictional world of Eryndor.")
    ap.add_argument("--seed", type=int, default=None,
                    help="world seed (default: random)")
    args = ap.parse_args()
    from .app import run
    run(args.seed)


if __name__ == "__main__":
    cli()
