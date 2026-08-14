"""Command-line entry point: sweep, probe, and version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wattwarden",
        description="Energy-governed AI agents on Arm CPUs.",
    )
    parser.add_argument(
        "--version", action="version", version=f"wattwarden {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command")

    sweep_parser = subparsers.add_parser(
        "sweep", help="run the full configuration grid and write lab artifacts"
    )
    sweep_parser.add_argument("--config", default="configs/base.yaml")
    sweep_parser.add_argument("--exp-id", required=True)
    sweep_parser.add_argument("--server-bin", required=True)
    sweep_parser.add_argument("--repo-root", default=".")

    probe_parser = subparsers.add_parser(
        "probe", help="measure an already-running OpenAI-compatible endpoint"
    )
    probe_parser.add_argument("--url", required=True)
    probe_parser.add_argument("--model", required=True)
    probe_parser.add_argument("--reps", type=int, default=5)
    probe_parser.add_argument("--max-tokens", type=int, default=128)
    probe_parser.add_argument("--seed", type=int, default=42)
    probe_parser.add_argument(
        "--prompt",
        default="Explain the difference between a process and a thread.",
    )

    args = parser.parse_args(argv)

    if args.command == "sweep":
        from .sweep import run_sweep

        results = run_sweep(
            Path(args.repo_root).resolve(),
            Path(args.config),
            args.exp_id,
            args.server_bin,
        )
        print(json.dumps(results, indent=2))
        print(f"artifacts: experiments/{args.exp_id}/")
        return 0

    if args.command == "probe":
        from .sweep import probe_endpoint

        summary = probe_endpoint(
            args.url,
            args.model,
            repetitions=args.reps,
            max_tokens=args.max_tokens,
            seed=args.seed,
            prompt=args.prompt,
        )
        print(json.dumps(summary, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
