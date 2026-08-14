"""Integration test for the governed-agent demo core against the real
installed pollard: charges accrue, and the oversized final call is
vetoed before dispatch by the joule budget."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

from governed_agent import run_demo  # noqa: E402

from wattwarden.toml_model import (  # noqa: E402
    NEOVERSE_V2,
    QWEN25_1_5B,
    estimate_energy,
)

MODEL = "qwen2.5-1.5b-instruct-q4_0"
FAKE_IN, FAKE_OUT = 400, 150


def _fake_model_fn(dispatched):
    def fn(payload):
        dispatched.append(payload)
        return {
            "usage": {"input_tokens": FAKE_IN, "output_tokens": FAKE_OUT},
            "content": "ok",
        }

    return fn


def test_governed_loop_charges_and_vetoes(capsys):
    per_call = estimate_energy(
        QWEN25_1_5B, NEOVERSE_V2, "Q4_0", FAKE_IN, FAKE_OUT
    ).total_j
    budget = per_call * 2.6  # two calls fit; the third precheck cannot

    dispatched = []
    lines = []
    summary = run_demo(
        _fake_model_fn(dispatched),
        store=None,  # pollard coerces None to an in-memory store
        model_name=MODEL,
        joule_budget=budget,
        prompts=["p1", "p2"],
        max_tokens=160,
        veto_max_tokens=100_000,
        out=lines.append,
    )

    assert summary["completed"] == 2
    assert summary["vetoed"] is True
    # The veto never reached the model: only the two real calls dispatched.
    assert len(dispatched) == 2
    assert summary["charges"]["joules"] > 0
    assert summary["charges"]["steps"] == 2
    assert any("VETOED BEFORE DISPATCH" in line for line in lines)


def test_generous_budget_dispatches_everything():
    per_call = estimate_energy(
        QWEN25_1_5B, NEOVERSE_V2, "Q4_0", FAKE_IN, FAKE_OUT
    ).total_j
    dispatched = []
    summary = run_demo(
        _fake_model_fn(dispatched),
        store=None,
        model_name=MODEL,
        joule_budget=per_call * 1000,
        prompts=["p1"],
        max_tokens=160,
        veto_max_tokens=200,  # small enough to pass precheck
        out=lambda s: None,
    )
    assert summary["vetoed"] is False
    assert len(dispatched) == 2  # the real call and the would-be veto call
