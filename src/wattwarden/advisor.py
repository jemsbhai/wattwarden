"""SLO-aware configuration advisor over measured sweep results.

Reads a sweep experiment directory (results.json plus environment.json),
applies latency and throughput constraints, prices tokens from an hourly
instance rate, and recommends the best measured configuration.

Honesty rules encoded here:
- Every number in the table is measured (client-side clock) except
  dollars, which are arithmetic on the supplied hourly rate.
- Conditions whose thread count reaches the host core count are flagged
  as contaminated in co-located serving mode (EXP-002 finding) and are
  excluded from the recommendation while remaining visible in the table.
- Energy columns are absent until profile calibration (EXP-003) lands;
  the advisor never prints an uncalibrated joule figure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConfigRow:
    key: str
    model_name: str
    quant: str
    threads: int
    tok_s: float
    ttft_ms: float
    contaminated: bool

    def usd_per_mtok(self, usd_per_hour: float) -> float:
        return usd_per_hour / 3600.0 / self.tok_s * 1e6


def load_rows(exp_dir: Path) -> list[ConfigRow]:
    results = json.loads((exp_dir / "results.json").read_text(encoding="utf-8"))
    cpu_count = None
    env_path = exp_dir / "environment.json"
    if env_path.is_file():
        env = json.loads(env_path.read_text(encoding="utf-8"))
        cpu_count = env.get("cpu_count")
    rows: list[ConfigRow] = []
    for key, entry in results.items():
        condition = entry["condition"]
        summary = entry["summary"]
        threads = int(condition["threads"])
        contaminated = cpu_count is not None and threads >= int(cpu_count)
        rows.append(
            ConfigRow(
                key=key,
                model_name=condition["model_name"],
                quant=condition["quant"],
                threads=threads,
                tok_s=float(summary["gen_tok_s"]["mean"]),
                ttft_ms=float(summary["ttft_ms"]["mean"]),
                contaminated=contaminated,
            )
        )
    if not rows:
        raise ValueError(f"no conditions found in {exp_dir / 'results.json'}")
    return rows


def recommend(
    rows: list[ConfigRow],
    *,
    slo_ttft_ms: float | None = None,
    min_tok_s: float | None = None,
) -> ConfigRow | None:
    """Best eligible configuration by measured throughput.

    With a fixed hourly rate, maximum tokens/s and minimum dollars per
    million tokens select the same row, so throughput is the sort key.
    """
    eligible = [r for r in rows if not r.contaminated]
    if slo_ttft_ms is not None:
        eligible = [r for r in eligible if r.ttft_ms <= slo_ttft_ms]
    if min_tok_s is not None:
        eligible = [r for r in eligible if r.tok_s >= min_tok_s]
    if not eligible:
        return None
    return max(eligible, key=lambda r: r.tok_s)


def render(
    rows: list[ConfigRow],
    best: ConfigRow | None,
    *,
    usd_per_hour: float | None = None,
    slo_ttft_ms: float | None = None,
    min_tok_s: float | None = None,
) -> str:
    lines = []
    header = "| config | quant | threads | tok/s | TTFT ms |"
    divider = "|---|---|---|---|---|"
    if usd_per_hour is not None:
        header += " $/Mtok |"
        divider += "---|"
    header += " note |"
    divider += "---|"
    lines.append(header)
    lines.append(divider)
    for row in sorted(rows, key=lambda r: (-r.tok_s)):
        cells = (
            f"| {row.key} | {row.quant} | {row.threads} "
            f"| {row.tok_s:.1f} | {row.ttft_ms:.1f} |"
        )
        if usd_per_hour is not None:
            cells += f" {row.usd_per_mtok(usd_per_hour):.2f} |"
        note = ""
        if row.contaminated:
            note = "co-located full-core: excluded (EXP-002)"
        elif best is not None and row.key == best.key:
            note = "RECOMMENDED"
        cells += f" {note} |"
        lines.append(cells)
    lines.append("")
    constraints = []
    if slo_ttft_ms is not None:
        constraints.append(f"TTFT <= {slo_ttft_ms:g} ms")
    if min_tok_s is not None:
        constraints.append(f"tok/s >= {min_tok_s:g}")
    lines.append(
        "constraints: " + (", ".join(constraints) if constraints else "none")
    )
    if best is None:
        lines.append("no configuration satisfies the constraints")
    else:
        summary = (
            f"recommended: {best.key} at {best.tok_s:.1f} tok/s, "
            f"TTFT {best.ttft_ms:.1f} ms"
        )
        if usd_per_hour is not None:
            summary += f", {best.usd_per_mtok(usd_per_hour):.2f} $/Mtok"
        lines.append(summary)
    lines.append(
        "all performance figures measured (client-side clock); energy "
        "columns arrive with profile calibration (EXP-003)"
    )
    return "\n".join(lines)
