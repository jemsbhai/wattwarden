"""Command-line entry point. Subcommands land with each component:
sweep, advise, report."""

import argparse

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wattwarden",
        description="Energy-governed AI agents on Arm CPUs.",
    )
    parser.add_argument(
        "--version", action="version", version=f"wattwarden {__version__}"
    )
    parser.parse_args()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
