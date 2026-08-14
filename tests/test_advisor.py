"""Tests for the SLO advisor: loading, contamination exclusion,
constraint filtering, and price arithmetic."""

import json

import pytest

from wattwarden.advisor import ConfigRow, load_rows, recommend, render


def _entry(model, quant, threads, tok_s, ttft_ms):
    return {
        "condition": {
            "model_name": model,
            "gguf_path": f"models/{model}.gguf",
            "quant": quant,
            "threads": threads,
        },
        "summary": {
            "n": 5,
            "gen_tok_s": {"mean": tok_s, "stdev": 0.1, "min": tok_s, "max": tok_s},
            "ttft_ms": {"mean": ttft_ms, "stdev": 0.1, "min": ttft_ms, "max": ttft_ms},
            "e2e_s": {"mean": 1.0, "stdev": 0.0, "min": 1.0, "max": 1.0},
            "output_tokens": {"mean": 99.0, "stdev": 0.0, "min": 99.0, "max": 99.0},
        },
    }


@pytest.fixture
def exp_dir(tmp_path):
    results = {
        "m-q4_0_t8": _entry("m-q4_0", "Q4_0", 8, 92.8, 14.8),
        "m-q4_0_t16": _entry("m-q4_0", "Q4_0", 16, 52.4, 23.2),
        "m-q8_0_t8": _entry("m-q8_0", "Q8_0", 8, 79.6, 17.0),
        "m-q4_0_t1": _entry("m-q4_0", "Q4_0", 1, 17.0, 62.7),
    }
    (tmp_path / "results.json").write_text(json.dumps(results), encoding="utf-8")
    (tmp_path / "environment.json").write_text(
        json.dumps({"cpu_count": 16}), encoding="utf-8"
    )
    return tmp_path


def test_load_rows_flags_full_core_contamination(exp_dir):
    rows = {r.key: r for r in load_rows(exp_dir)}
    assert rows["m-q4_0_t16"].contaminated is True
    assert rows["m-q4_0_t8"].contaminated is False
    assert len(rows) == 4


def test_recommend_excludes_contaminated_even_when_fastest(exp_dir):
    rows = load_rows(exp_dir)
    # Inflate the contaminated row artificially; it must still lose.
    rows = [
        ConfigRow(r.key, r.model_name, r.quant, r.threads, 999.0, r.ttft_ms, True)
        if r.key == "m-q4_0_t16"
        else r
        for r in rows
    ]
    best = recommend(rows)
    assert best is not None and best.key == "m-q4_0_t8"


def test_recommend_applies_slo_and_floor(exp_dir):
    rows = load_rows(exp_dir)
    best = recommend(rows, slo_ttft_ms=16.0)
    assert best.key == "m-q4_0_t8"
    best_strict = recommend(rows, slo_ttft_ms=10.0)
    assert best_strict is None
    best_floor = recommend(rows, min_tok_s=80.0)
    assert best_floor.key == "m-q4_0_t8"


def test_usd_per_mtok_arithmetic():
    row = ConfigRow("k", "m", "Q4_0", 8, 92.8, 14.8, False)
    assert row.usd_per_mtok(0.65) == pytest.approx(1.9457, rel=1e-3)


def test_render_marks_recommendation_and_exclusion(exp_dir):
    rows = load_rows(exp_dir)
    best = recommend(rows, slo_ttft_ms=50.0)
    text = render(rows, best, usd_per_hour=0.65, slo_ttft_ms=50.0)
    assert "RECOMMENDED" in text
    assert "co-located full-core: excluded" in text
    assert "$/Mtok" in text
    assert "measured" in text


def test_render_reports_unsatisfiable_constraints(exp_dir):
    rows = load_rows(exp_dir)
    text = render(rows, None, slo_ttft_ms=1.0)
    assert "no configuration satisfies" in text
