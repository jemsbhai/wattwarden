"""Coverage audit for EXP-003b: per cell window, compare actual sample
count against the expected 1 Hz rate and report the largest gap.

Read-only; exists because the part-1 session suffered a Doze freeze and
any sampling gaps inside cell windows must be known before results are
filed. Prints a table; changes nothing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wattwarden.phone_energy import load_events, load_samples  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "experiments" / "exp_003b_phone_raw"


def main() -> int:
    samples = load_samples(RAW / "samples.csv")
    events = load_events(RAW / "events.csv")
    times = [s["t_ms"] for s in samples]
    print("| window | note | duration s | samples | expected | coverage | max gap s |")
    print("|---|---|---|---|---|---|---|")
    for event in events:
        if event["phase"] == "cooldown":
            continue
        inside = [t for t in times if event["start_ms"] <= t <= event["end_ms"]]
        duration = (event["end_ms"] - event["start_ms"]) / 1000.0
        expected = max(1, int(duration))
        gaps = [
            (b - a) / 1000.0 for a, b in zip(inside, inside[1:])
        ]
        max_gap = max(gaps) if gaps else duration
        coverage = len(inside) / expected if expected else 0.0
        note = event["note"].split(";")[0]
        print(
            f"| {event['phase']} | {note} | {duration:.1f} | {len(inside)} "
            f"| {expected} | {coverage:.2f} | {max_gap:.1f} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
