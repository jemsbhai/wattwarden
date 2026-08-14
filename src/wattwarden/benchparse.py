"""Parse and aggregate llama-bench JSON output (EXP-001 style).

Schema ground truth: a llama-bench invocation with -o json emits an array
of test objects; the prompt-processing test has n_prompt > 0 and
n_gen == 0, the generation test has n_gen > 0 and n_prompt == 0. Each
object carries avg_ts (tokens/s), its own internal samples, and the
build_commit of the binary that produced it.

Aggregation unit: one file (one invocation) is one observation; the
per-invocation avg_ts values are averaged across repetitions with a
sample standard deviation. Internal samples stay archived in the raw
files and are not double-counted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import stdev
from typing import Any

_CELL_RE = re.compile(r"(?P<build>[A-Za-z0-9]+)_t(?P<threads>\d+)_rep(?P<rep>\d+)\.json$")


def parse_bench_file(path: Path) -> dict[str, Any]:
    """Extract pp and tg tokens/s plus provenance from one invocation."""
    tests = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(tests, list) or not tests:
        raise ValueError(f"{path}: expected a non-empty JSON array")
    pp = next((t for t in tests if t.get("n_prompt", 0) > 0 and t.get("n_gen", 0) == 0), None)
    tg = next((t for t in tests if t.get("n_gen", 0) > 0 and t.get("n_prompt", 0) == 0), None)
    if pp is None or tg is None:
        raise ValueError(f"{path}: missing pp or tg test object")
    return {
        "pp_ts": float(pp["avg_ts"]),
        "tg_ts": float(tg["avg_ts"]),
        "build_commit": str(pp.get("build_commit", "unknown")),
        "n_threads": int(pp.get("n_threads", 0)),
        "model_size_bytes": int(pp.get("model_size", 0)),
        "model_n_params": int(pp.get("model_n_params", 0)),
    }


def parse_cell_name(filename: str) -> tuple[str, int, int]:
    match = _CELL_RE.search(filename)
    if match is None:
        raise ValueError(f"unrecognized cell filename: {filename}")
    return match["build"], int(match["threads"]), int(match["rep"])


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": sum(values) / len(values),
        "stdev": stdev(values) if len(values) > 1 else 0.0,
        "n": len(values),
    }


def aggregate_cells(exp_dir: Path) -> dict[str, Any]:
    """Group per-invocation observations into (build, threads) cells."""
    observations: dict[tuple[str, int], dict[str, list[float]]] = {}
    commits: set[str] = set()
    model_size = 0
    model_n_params = 0
    for path in sorted(exp_dir.glob("*.json")):
        build, threads, _rep = parse_cell_name(path.name)
        parsed = parse_bench_file(path)
        commits.add(parsed["build_commit"])
        model_size = parsed["model_size_bytes"] or model_size
        model_n_params = parsed["model_n_params"] or model_n_params
        cell = observations.setdefault((build, threads), {"pp": [], "tg": []})
        cell["pp"].append(parsed["pp_ts"])
        cell["tg"].append(parsed["tg_ts"])
    if not observations:
        raise ValueError(f"no llama-bench JSON files found in {exp_dir}")
    cells = {
        f"{build}_t{threads}": {
            "build": build,
            "threads": threads,
            "pp": _stats(values["pp"]),
            "tg": _stats(values["tg"]),
        }
        for (build, threads), values in sorted(observations.items())
    }
    return {
        "cells": cells,
        "build_commits": sorted(commits),
        "model_size_bytes": model_size,
        "model_n_params": model_n_params,
    }


def kleidiai_speedups(aggregate: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Per-thread-level KleidiAI/generic ratios for pp and tg."""
    cells = aggregate["cells"]
    by_thread: dict[int, dict[str, Any]] = {}
    for cell in cells.values():
        by_thread.setdefault(cell["threads"], {})[cell["build"]] = cell
    speedups: dict[str, dict[str, float]] = {}
    for threads, builds in sorted(by_thread.items()):
        if "kleidiai" in builds and "generic" in builds:
            speedups[f"t{threads}"] = {
                "pp": builds["kleidiai"]["pp"]["mean"] / builds["generic"]["pp"]["mean"],
                "tg": builds["kleidiai"]["tg"]["mean"] / builds["generic"]["tg"]["mean"],
            }
    return speedups


def render_markdown(aggregate: dict[str, Any]) -> str:
    lines = []
    if len(aggregate["build_commits"]) > 1:
        lines.append(
            "WARNING: mixed llama.cpp commits in one experiment: "
            + ", ".join(aggregate["build_commits"])
        )
        lines.append("")
    lines.append("| build | threads | pp tok/s (mean, sd, n) | tg tok/s (mean, sd, n) |")
    lines.append("|---|---|---|---|")
    for key, cell in aggregate["cells"].items():
        pp, tg = cell["pp"], cell["tg"]
        lines.append(
            f"| {cell['build']} | {cell['threads']} "
            f"| {pp['mean']:.1f}, {pp['stdev']:.2f}, {pp['n']} "
            f"| {tg['mean']:.1f}, {tg['stdev']:.2f}, {tg['n']} |"
        )
    speedups = kleidiai_speedups(aggregate)
    if speedups:
        lines.append("")
        lines.append("| threads | KleidiAI pp speedup | KleidiAI tg speedup |")
        lines.append("|---|---|---|")
        for label, ratio in speedups.items():
            lines.append(f"| {label} | {ratio['pp']:.3f}x | {ratio['tg']:.3f}x |")
    lines.append("")
    lines.append(
        f"llama.cpp commit(s): {', '.join(aggregate['build_commits'])}; "
        f"model_size_bytes={aggregate['model_size_bytes']}; "
        f"model_n_params={aggregate['model_n_params']}"
    )
    return "\n".join(lines)
