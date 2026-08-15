"""Merge the EXP-003b part-1 and part-2 raw sessions into the analyzer
input directory with explicit UTF-8 handling.

Exists because the first merge attempt used PowerShell redirection,
which re-encodes as UTF-16 on Windows PowerShell 5.1; this script is
the deviation-safe path and part of the documented two-part session
record. Expects exp003b_part1/ and exp003b_part2/ in the working
directory (as extracted from the phone tarball).
"""

from pathlib import Path

TARGET = Path("experiments") / "exp_003b_phone_raw"


def merge(name: str) -> None:
    first = Path("exp003b_part1", name).read_text(encoding="utf-8-sig").splitlines()
    second = Path("exp003b_part2", name).read_text(encoding="utf-8-sig").splitlines()
    merged = first + second[1:]
    (TARGET / name).write_text("\n".join(merged) + "\n", encoding="utf-8")
    print(f"merged {name}: {len(first)} + {len(second) - 1} rows")


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    merge("samples.csv")
    merge("events.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
