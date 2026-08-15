"""Smoke test: the chart script runs against the committed experiment
artifacts and writes all five figures."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import make_charts  # noqa: E402


def test_all_figures_render(tmp_path):
    assert make_charts.main(["--outdir", str(tmp_path)]) == 0
    written = sorted(p.name for p in tmp_path.glob("*.png"))
    assert written == [
        "fig1_thread_scaling.png",
        "fig2_kleidiai_ablation.png",
        "fig3_cost_per_mtok.png",
        "fig4_budget_burndown.png",
        "fig5_bandwidth_ceiling.png",
        "fig6_phone_energy_per_token.png",
        "fig7_phone_speed_energy_tradeoff.png",
        "fig8_fastest_not_cheapest.png",
    ]
    for path in tmp_path.glob("*.png"):
        assert path.stat().st_size > 10_000  # a real rendered image, not a stub
