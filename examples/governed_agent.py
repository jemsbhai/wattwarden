"""Governed agent finale: a pollard run whose energy is metered and
budgeted by wattwarden's TomlCpuMeter, against a live llama-server on
an Arm CPU.

What it demonstrates:
1. Every model call is charged predicted joules (TOML model, labeled).
2. The joule budget is enforced BEFORE dispatch: the final, oversized
   request is refused by precheck and never reaches the server. The
   NVML measured-energy meter cannot do this; a predictive meter can.
3. The whole run lands in a persistent pollard store for reports and
   tree exports (dashboard inputs).

Usage (on the Arm box, llama-server already running):
  python examples/governed_agent.py --url http://127.0.0.1:8091 \
      --model qwen2.5-1.5b-instruct-q4_0 --joules 30
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

from pollard import Budget, BudgetExceeded, Runtime, recompute_charges
from pollard.meters import StepMeter, TokenMeter

from wattwarden.meter import TomlCpuMeter

DEFAULT_PROMPTS = [
    "In two sentences: why can decode throughput on a CPU be limited by "
    "memory bandwidth rather than arithmetic?",
    "In two sentences: why should a benchmark distinguish prompt "
    "processing from token generation?",
    "In two sentences: why might a serving process behave differently "
    "from a pure benchmark loop on the same binary?",
]

VETO_PROMPT = (
    "Write an exhaustive multi-part treatise covering every topic above "
    "in maximal detail, sparing no length. "
) * 8


def run_demo(
    model_fn: Callable[[dict[str, Any]], Any],
    *,
    store: Any,
    model_name: str,
    joule_budget: float,
    profile: str = "neoverse-v2",
    prompts: list[str] | None = None,
    max_tokens: int = 160,
    veto_max_tokens: int = 100_000,
    out: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Drive the governed loop; return a summary dict (testable core)."""
    prompts = DEFAULT_PROMPTS if prompts is None else prompts
    meter = TomlCpuMeter(profile=profile)
    runtime = Runtime(
        store,
        meters=[StepMeter(), TokenMeter(), meter],
    )
    budget = Budget(steps=len(prompts) + 2, extra={"joules": joule_budget})
    completed = 0
    vetoed = False
    veto_message = ""

    with runtime.run("wattwarden-governed-agent", budget=budget) as run:
        out(f"budget: {joule_budget:.1f} J (predicted, TOML {profile}), "
            f"{len(prompts) + 2} steps")
        for index, prompt in enumerate(prompts, start=1):
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            }
            node = run.model_call(payload, fn=model_fn)
            completed += 1
            charges = node.meta.get("charges", {})
            spent = recompute_charges(run.store, run.root_id).get("joules", 0.0)
            precheck = meter.last_precheck.total_j if meter.last_precheck else 0.0
            out(
                f"call {index}: precheck {precheck:.2f} J, "
                f"charged {float(charges.get('joules', 0.0)):.2f} J, "
                f"spent {spent:.2f} / {joule_budget:.1f} J"
            )
        try:
            run.model_call(
                {
                    "model": model_name,
                    "messages": [{"role": "user", "content": VETO_PROMPT}],
                    "max_tokens": veto_max_tokens,
                },
                fn=model_fn,
            )
            out("veto call unexpectedly dispatched (budget too large?)")
        except BudgetExceeded as exc:
            vetoed = True
            veto_message = str(exc)
            out(f"VETOED BEFORE DISPATCH: {veto_message}")

    totals = recompute_charges(store if hasattr(store, "get") else runtime.store, run.root_id)
    out(f"final charges: {totals}")
    return {
        "completed": completed,
        "vetoed": vetoed,
        "veto_message": veto_message,
        "charges": totals,
        "root_id": run.root_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--joules", type=float, default=30.0)
    parser.add_argument("--store", default="runs/governed_agent.sqlite")
    parser.add_argument("--max-tokens", type=int, default=160)
    args = parser.parse_args()

    from openai import OpenAI
    from pollard.adapters.openai import make_chat_completions_fn

    client = OpenAI(base_url=args.url.rstrip("/") + "/v1", api_key="none")
    model_fn = make_chat_completions_fn(
        client, model=args.model, temperature=0.0, seed=42
    )

    Path(args.store).parent.mkdir(parents=True, exist_ok=True)
    summary = run_demo(
        model_fn,
        store=args.store,
        model_name=args.model,
        joule_budget=args.joules,
        max_tokens=args.max_tokens,
    )
    print()
    print("run store:", args.store)
    print("inspect:  pollard show", args.store, "--html run.html   (tree export)")
    print("          pollard report", args.store, "--json          (dashboard input)")
    print("note: joule figures are TOML-model predictions on an uncalibrated")
    print("profile; calibration is EXP-003. Throughput and step data are real.")
    return 0 if summary["vetoed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
