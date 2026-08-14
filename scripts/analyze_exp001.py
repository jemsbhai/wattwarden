"""Analyze EXP-001 raw llama-bench output.

Usage: python scripts/analyze_exp001.py <dir-with-json-files>
Prints the aggregated markdown table and writes results.json plus
results.md next to the raw files.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wattwarden.benchparse import aggregate_cells, kleidiai_speedups, render_markdown


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    exp_dir = Path(sys.argv[1])
    aggregate = aggregate_cells(exp_dir)
    aggregate["kleidiai_speedups"] = kleidiai_speedups(aggregate)
    markdown = render_markdown(aggregate)
    print(markdown)
    (exp_dir / "results.json").write_text(
        json.dumps(aggregate, indent=2) + "\n", encoding="utf-8"
    )
    (exp_dir / "results.md").write_text(markdown + "\n", encoding="utf-8")
    print(f"\nwritten: {exp_dir / 'results.json'} and results.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
