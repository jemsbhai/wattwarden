"""Tests for llama-bench JSON parsing, built from the observed schema of
the real EXP-001 output (build 6fed9f6ff, 2026-08-14)."""

import json

import pytest

from wattwarden.benchparse import (
    aggregate_cells,
    kleidiai_speedups,
    parse_bench_file,
    parse_cell_name,
    render_markdown,
)


def _invocation(pp_ts, tg_ts, commit="6fed9f6ff", threads=8):
    common = {
        "build_commit": commit,
        "n_threads": threads,
        "model_size": 1060276736,
        "model_n_params": 1777088000,
    }
    return [
        {**common, "n_prompt": 512, "n_gen": 0, "avg_ts": pp_ts},
        {**common, "n_prompt": 0, "n_gen": 128, "avg_ts": tg_ts},
    ]


def _write(tmp_path, name, payload):
    (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")


def test_parse_cell_name():
    assert parse_cell_name("kleidiai_t8_rep1.json") == ("kleidiai", 8, 1)
    assert parse_cell_name("generic_t16_rep5.json") == ("generic", 16, 5)
    with pytest.raises(ValueError):
        parse_cell_name("notes.txt")


def test_parse_bench_file_extracts_both_tests(tmp_path):
    _write(tmp_path, "kleidiai_t8_rep1.json", _invocation(315.9, 88.4))
    parsed = parse_bench_file(tmp_path / "kleidiai_t8_rep1.json")
    assert parsed["pp_ts"] == pytest.approx(315.9)
    assert parsed["tg_ts"] == pytest.approx(88.4)
    assert parsed["build_commit"] == "6fed9f6ff"
    assert parsed["model_size_bytes"] == 1060276736


def test_parse_bench_file_rejects_missing_tests(tmp_path):
    _write(tmp_path, "kleidiai_t8_rep1.json", [{"n_prompt": 512, "n_gen": 0, "avg_ts": 1.0}])
    with pytest.raises(ValueError, match="missing pp or tg"):
        parse_bench_file(tmp_path / "kleidiai_t8_rep1.json")


def test_aggregate_and_speedups(tmp_path):
    _write(tmp_path, "kleidiai_t8_rep1.json", _invocation(320.0, 90.0))
    _write(tmp_path, "kleidiai_t8_rep2.json", _invocation(310.0, 86.0))
    _write(tmp_path, "generic_t8_rep1.json", _invocation(200.0, 60.0))
    _write(tmp_path, "generic_t8_rep2.json", _invocation(210.0, 62.0))

    result = aggregate_cells(tmp_path)
    assert result["cells"]["kleidiai_t8"]["pp"]["mean"] == pytest.approx(315.0)
    assert result["cells"]["kleidiai_t8"]["tg"]["n"] == 2
    assert result["build_commits"] == ["6fed9f6ff"]

    speedups = kleidiai_speedups(result)
    assert speedups["t8"]["pp"] == pytest.approx(315.0 / 205.0)
    assert speedups["t8"]["tg"] == pytest.approx(88.0 / 61.0)


def test_render_markdown_warns_on_mixed_commits(tmp_path):
    _write(tmp_path, "kleidiai_t8_rep1.json", _invocation(320.0, 90.0, commit="aaa"))
    _write(tmp_path, "generic_t8_rep1.json", _invocation(200.0, 60.0, commit="bbb"))
    text = render_markdown(aggregate_cells(tmp_path))
    assert "WARNING: mixed llama.cpp commits" in text
    assert "| kleidiai | 8 |" in text


def test_aggregate_rejects_empty_dir(tmp_path):
    with pytest.raises(ValueError, match="no llama-bench JSON"):
        aggregate_cells(tmp_path)
