"""Run the EXP-003b analysis on transferred phone raw data.

Usage: python scripts/analyze_exp003b.py
Expects the phone tarball extracted to experiments/exp_003b_phone_raw/
(samples.csv, events.csv, per-rep bench JSON), writes
experiments/exp_003b_phone/analysis.json, and prints the cell table.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wattwarden.phone_energy import run_analysis  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    raw = REPO / "experiments" / "exp_003b_phone_raw"
    out_name = sys.argv[1] if len(sys.argv) > 1 else "exp_003b_phone"
    out = REPO / "experiments" / out_name
    analysis = run_analysis(raw, out)
    print(f"baseline power: {analysis['baseline_power_w']:.3f} W")
    print("| cell | n | J/token mean | sd | duration s | min samples | coverage | flags |")
    print("|---|---|---|---|---|---|---|---|")
    for key in sorted(analysis["cells"]):
        c = analysis["cells"][key]
        flags = ";".join(sorted(set(c["flags"]))) if c["flags"] else ""
        print(
            f"| {key} | {c['n']} | {c['j_per_token_mean']:.4f} "
            f"| {c['j_per_token_sd']:.4f} | {c['mean_duration_s']:.1f} "
            f"| {c['min_rep_samples']} | {c['mean_coverage']:.2f} | {flags} |"
        )
    print(json.dumps(analysis["fit"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
