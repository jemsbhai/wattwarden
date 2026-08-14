"""Run the EXP-003a time-structure fit against committed artifacts.

Usage: python scripts/fit_exp003.py
Writes experiments/exp_003_time_fit/fit.json and fit.md, then prints
the markdown tables.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wattwarden.calibrate import run_fit  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    out_dir = REPO / "experiments" / "exp_003_time_fit"
    payload = run_fit(REPO / "experiments" / "exp_002_axion_sweep", out_dir)
    print((out_dir / "fit.md").read_text(encoding="utf-8"))
    del payload
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
