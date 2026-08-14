# wattwarden

Energy-governed AI agents on Arm CPUs. wattwarden gives pollard a CPU-side
energy meter based on the TOML operation-level energy model, sweeps llama.cpp
configurations on Arm64 servers, and recommends the configuration that meets a
latency SLO at the lowest predicted energy and dollar cost. A live dashboard
shows token, dollar, and joule budgets burning down as a governed agent runs.

Built for the Arm Create: AI Optimization Challenge 2026, Cloud AI track.
This repository is new work created during the submission period, building on
our previously published open source packages:

- pollard 1.5.1 (governed execution trees for agents; MIT)
- jsonld-ex 0.7.4 (Subjective Logic MCP server, 53 tools; MIT)
- TOML: Transistor Operations for Machine Learning (FLAIRS-39)

pollard documents that its only energy meter is NVML for local GPUs and that
hosted and CPU inference energy is not measured. wattwarden fills exactly that
documented gap for Arm CPUs.

## Arm tooling used

- llama.cpp built with KleidiAI kernels, serving on Oracle Ampere A1
  (Neoverse N1)
- Cross-generation validation on a Neoverse V2 instance (GCP Axion C4A or
  AWS Graviton4), selected when the sweep driver is ready
- Arm Performix for independent benchmark cross-checks

## Components (build order)

1. meter: a pollard-compatible meter implementing the TOML energy model for
   Arm CPU inference. Predicted joules are always labeled as predicted.
2. sweep: a driver that benchmarks quantization x thread configurations
   against llama-server and records measured tokens/s and TTFT.
3. advisor: a CLI that takes a latency SLO and returns the configuration
   minimizing predicted J/token and dollars per Mtoken.
4. dashboard: a web view over pollard run reports with live budget gauges.

## Setup

Placeholder. Exact Ampere A1 build and run instructions land with the sweep.

## Reproducibility

Every number in this repository traces to an experiment logged in LOGBOOK.md
with a frozen config, an environment snapshot, and pinned versions. Measured
values carry method, units, and uncertainty. Modeled values are labeled.

## License

MIT. See LICENSE.
