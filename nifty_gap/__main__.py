"""Entry point for running the package as a module."""

import sys

from nifty_gap.config import print_config


def main() -> None:
    if "--print-config" in sys.argv:
        print(print_config())
        return
    print("usage: python -m nifty_gap --print-config")


if __name__ == "__main__":
    main()