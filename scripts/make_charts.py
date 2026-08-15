"""Generate submission charts from committed experiment artifacts.

Every series is loaded from experiments/ JSON where it exists. The
remote-probe points and the veto transcript are not stored as JSON
artifacts; they are embedded below as constants with citations to the
logbook entries that record them (EXP-004, EXP-005, finale transcript).

Usage: python scripts/make_charts.py [--outdir charts] [--usd-per-hour 0.65]
Writes PNG files sized for the Devpost gallery.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

# LOGBOOK.md, EXP-004 and EXP-005 (remote client via SSH tunnel), and the
# exploratory t12 locator addendum. gen_tok_s means, n=5 each.
REMOTE_TG = {8: 93.24, 12: 57.18, 15: 53.49, 16: 52.14}
# LOGBOOK.md, EXP-001 results: llama-bench generic t16 tg mean.
BENCH_T16_TG = 140.9
# WRITEUP.md finale transcript: per-call charged joules and the budget.
VETO_CHARGES = [6.65, 8.16, 4.41]
VETO_BUDGET = 30.0

QUANT_ORDER = ["Q4_0", "Q4_K_M", "Q8_0"]
QUANT_COLOR = {"Q4_0": "#1f77b4", "Q4_K_M": "#ff7f0e", "Q8_0": "#2ca02c"}
MODEL_BYTES = {"Q4_0": 1.066e9, "Q4_K_M": 1.117e9, "Q8_0": 1.895e9}


def load_exp002() -> dict[str, dict[int, dict[str, float]]]:
    path = REPO / "experiments" / "exp_002_axion_sweep" / "results.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    table: dict[str, dict[int, dict[str, float]]] = {}
    for entry in raw.values():
        quant = entry["condition"]["quant"]
        threads = int(entry["condition"]["threads"])
        table.setdefault(quant, {})[threads] = {
            "tg": entry["summary"]["gen_tok_s"]["mean"],
            "ttft": entry["summary"]["ttft_ms"]["mean"],
        }
    return table


def load_exp001() -> dict[str, dict[str, dict[str, float]]]:
    path = (
        REPO
        / "experiments"
        / "exp_001_kleidiai_ablation"
        / "exp001"
        / "results.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def load_exp003b() -> dict[str, dict]:
    path = REPO / "experiments" / "exp_003b_phone_v2" / "analysis.json"
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def fig_thread_scaling(table, outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    threads = [1, 2, 4, 8, 16]
    for quant in QUANT_ORDER:
        ys = [table[quant][t]["tg"] for t in threads]
        ax.plot(
            threads,
            ys,
            marker="o",
            color=QUANT_COLOR[quant],
            label=f"{quant} served (co-located client)",
        )
    remote_x = sorted(REMOTE_TG)
    ax.plot(
        remote_x,
        [REMOTE_TG[t] for t in remote_x],
        marker="D",
        linestyle="--",
        color="black",
        label="Q4_0 served (remote client, EXP-004/005)",
    )
    ax.scatter(
        [16],
        [BENCH_T16_TG],
        marker="*",
        s=220,
        color="#d62728",
        zorder=5,
        label="Q4_0 llama-bench t16 (no serving stack)",
    )
    ax.axvspan(9, 11, alpha=0.12, color="gray")
    ax.text(9.1, 20, "collapse onset\n(t9..t11)", fontsize=9, color="dimgray")
    ax.set_xscale("log", base=2)
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads])
    ax.set_xlabel("generation threads")
    ax.set_ylabel("token generation, tok/s")
    ax.set_title(
        "Served throughput peaks at t8; full-core serving collapses\n"
        "(Axion c4a-standard-16, Qwen2.5-1.5B, EXP-002/004/005)"
    )
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = outdir / "fig1_thread_scaling.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_kleidiai(cells, outdir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))
    combos = [("generic", 8), ("kleidiai", 8), ("generic", 16), ("kleidiai", 16)]
    labels = [f"{b}\nt{t}" for b, t in combos]
    colors = ["#1f77b4", "#9467bd", "#1f77b4", "#9467bd"]
    for ax, metric, title in (
        (axes[0], "pp", "prompt processing"),
        (axes[1], "tg", "token generation"),
    ):
        values = [cells[f"{b}_t{t}"][metric]["mean"] for b, t in combos]
        errors = [cells[f"{b}_t{t}"][metric]["stdev"] for b, t in combos]
        bars = ax.bar(labels, values, yerr=errors, color=colors, capsize=3)
        ax.bar_label(bars, fmt="%.0f", fontsize=8, padding=2)
        ax.set_title(title)
        ax.set_ylabel("tok/s")
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle(
        "KleidiAI ON vs OFF, llama-bench (EXP-001): generation is faster "
        "WITHOUT KleidiAI on this host"
    )
    fig.tight_layout()
    out = outdir / "fig2_kleidiai_ablation.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_cost(table, usd_per_hour: float, cpu_count: int, outdir: Path) -> Path:
    rows = []
    for quant, per_thread in table.items():
        for threads, metrics in per_thread.items():
            cost = usd_per_hour / 3600.0 / metrics["tg"] * 1e6
            rows.append((f"{quant} t{threads}", cost, threads >= cpu_count))
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(8, 5.5))
    names = [r[0] for r in rows]
    costs = [r[1] for r in rows]
    colors = [
        "#2ca02c" if i == 0 else ("#bbbbbb" if r[2] else "#1f77b4")
        for i, r in enumerate(rows)
    ]
    hatches = ["//" if r[2] else "" for r in rows]
    bars = ax.barh(names, costs, color=colors)
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)
    ax.bar_label(bars, fmt="$%.2f", fontsize=8, padding=2)
    ax.invert_yaxis()
    ax.set_xlabel(f"dollars per million generated tokens at ${usd_per_hour:.2f}/hour")
    ax.set_title(
        "Measured cost per configuration; green is the advisor pick,\n"
        "hatched full-core rows are excluded (EXP-002, EXP-004)"
    )
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out = outdir / "fig3_cost_per_mtok.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_burndown(outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    xs = [0]
    ys = [0.0]
    total = 0.0
    for i, charge in enumerate(VETO_CHARGES, start=1):
        total += charge
        xs.append(i)
        ys.append(total)
    ax.step(xs, ys, where="post", marker="o", color="#1f77b4", label="spent (predicted J)")
    ax.axhline(VETO_BUDGET, color="#d62728", linestyle="--", label=f"budget {VETO_BUDGET:.0f} J")
    ax.scatter([4], [ys[-1]], marker="x", s=160, color="#d62728", zorder=5)
    ax.annotate(
        "call 4: VETOED\nbefore dispatch",
        xy=(4, ys[-1]),
        xytext=(3.0, 24.5),
        fontsize=9,
        color="#d62728",
        arrowprops={"arrowstyle": "->", "color": "#d62728"},
    )
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_xlabel("governed model call")
    ax.set_ylabel("cumulative predicted joules")
    ax.set_ylim(0, 34)
    ax.set_title(
        "Governed agent on Arm: joule budget enforced before dispatch\n"
        "(finale transcript; TOML predictions, uncalibrated profile)"
    )
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = outdir / "fig4_budget_burndown.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_bandwidth(table, outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels, values, colors = [], [], []
    for quant in QUANT_ORDER:
        for threads in (8, 16):
            gbs = table[quant][threads]["tg"] * MODEL_BYTES[quant] / 1e9
            labels.append(f"{quant} t{threads}\nserved")
            values.append(gbs)
            colors.append(QUANT_COLOR[quant])
    labels.append("Q4_0 t16\nbench")
    values.append(BENCH_T16_TG * MODEL_BYTES["Q4_0"] / 1e9)
    colors.append("#d62728")
    bars = ax.bar(labels, values, color=colors)
    ax.bar_label(bars, fmt="%.0f", fontsize=8, padding=2)
    ax.axhline(150, color="black", linestyle=":", label="~150 GB/s observed maximum")
    ax.set_ylabel("weight-streaming bytes, GB/s")
    ax.set_title(
        "Decode byte throughput approaching the ~150 GB/s observed maximum\n"
        "(tok/s x model bytes; EXP-001/002, interpretation refined by EXP-003a)"
    )
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = outdir / "fig5_bandwidth_ceiling.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_phone_energy(cells, outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    threads = [1, 4, 8]
    width = 0.38
    for offset, quant in ((-width / 2, "Q4_0"), (width / 2, "Q8_0")):
        xs, ys, errs = [], [], []
        for i, t in enumerate(threads):
            cell = cells.get(f"{quant}_t{t}")
            if not cell:
                continue
            xs.append(i + offset)
            ys.append(cell["j_per_token_mean"])
            errs.append(cell["j_per_token_sd"])
        bars = ax.bar(
            xs, ys, width=width, yerr=errs, capsize=4,
            color=QUANT_COLOR[quant], label=quant,
        )
        ax.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
    ax.set_xticks(range(len(threads)))
    ax.set_xticklabels([f"t{t}" for t in threads])
    ax.set_xlabel("generation threads")
    ax.set_ylabel("energy per generated token, J (measured)")
    ax.set_title(
        "On-device energy rises with every added cluster\n"
        "(Pixel 8 Pro battery telemetry, Qwen2.5-1.5B, EXP-003b v2)"
    )
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = outdir / "fig6_phone_energy_per_token.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_phone_tradeoff(cells, outdir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for key, cell in sorted(cells.items()):
        s_tok = cell.get("s_per_token_bench") or 0.0
        if s_tok <= 0:
            continue
        x = 1.0 / s_tok
        y = cell["j_per_token_mean"]
        ax.errorbar(
            x, y, yerr=cell["j_per_token_sd"], fmt="o", capsize=4,
            color=QUANT_COLOR[cell["quant"]],
        )
        ax.annotate(
            f"{cell['quant']} t{cell['threads']}",
            (x, y), textcoords="offset points", xytext=(8, 4), fontsize=9,
        )
    ax.set_xlabel("decode speed, tok/s (llama-bench)")
    ax.set_ylabel("energy per token, J (measured)")
    ax.set_title(
        "The speed-energy tradeoff on Tensor G3: faster configurations\n"
        "cost more joules per token (EXP-003b v2)"
    )
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = outdir / "fig7_phone_speed_energy_tradeoff.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def fig_fastest_not_cheapest(table, cells, outdir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4))
    threads = [1, 2, 4, 8, 16]
    ys = [table["Q4_0"][t]["tg"] for t in threads]
    axes[0].plot(threads, ys, marker="o", color=QUANT_COLOR["Q4_0"])
    axes[0].scatter([8], [table["Q4_0"][8]["tg"]], marker="*", s=240,
                    color="#d62728", zorder=5, label="best throughput")
    axes[0].set_xscale("log", base=2)
    axes[0].set_xticks(threads)
    axes[0].set_xticklabels([str(t) for t in threads])
    axes[0].set_xlabel("threads")
    axes[0].set_ylabel("served tok/s")
    axes[0].set_title("Axion server: throughput peaks at t8\n(EXP-002)")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    p_threads = [1, 4, 8]
    p_ys = [cells[f"Q4_0_t{t}"]["j_per_token_mean"] for t in p_threads]
    p_err = [cells[f"Q4_0_t{t}"]["j_per_token_sd"] for t in p_threads]
    axes[1].errorbar(p_threads, p_ys, yerr=p_err, marker="o", capsize=4,
                     color=QUANT_COLOR["Q4_0"])
    axes[1].scatter([1], [p_ys[0]], marker="*", s=240, color="#2ca02c",
                    zorder=5, label="lowest energy")
    axes[1].set_xscale("log", base=2)
    axes[1].set_xticks(p_threads)
    axes[1].set_xticklabels([str(t) for t in p_threads])
    axes[1].set_xlabel("threads")
    axes[1].set_ylabel("J per token")
    axes[1].set_title("Pixel 8 Pro: energy lowest at t1\n(EXP-003b, Q4_0)")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.suptitle("Fastest is not cheapest: the optimum flips across Arm targets")
    fig.tight_layout()
    out = outdir / "fig8_fastest_not_cheapest.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default=str(REPO / "charts"))
    parser.add_argument("--usd-per-hour", type=float, default=0.65)
    parser.add_argument("--cpu-count", type=int, default=16)
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    table = load_exp002()
    cells = load_exp001()
    phone = load_exp003b()
    written = [
        fig_thread_scaling(table, outdir),
        fig_kleidiai(cells, outdir),
        fig_cost(table, args.usd_per_hour, args.cpu_count, outdir),
        fig_burndown(outdir),
        fig_bandwidth(table, outdir),
        fig_phone_energy(phone, outdir),
        fig_phone_tradeoff(phone, outdir),
        fig_fastest_not_cheapest(table, phone, outdir),
    ]
    for path in written:
        print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
