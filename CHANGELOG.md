# Changelog

All notable changes to this project are documented in this file.
Format follows Keep a Changelog; versioning follows SemVer.

## [Unreleased]

### Added
- Phone charts (fig6..fig8): measured J/token with error bars, the
  speed-energy tradeoff scatter, and the two-panel fastest-is-not-
  cheapest contrast between Axion throughput and Pixel energy; all
  rendered from the committed EXP-003b v2 analysis artifact.
- EXP-003b completed: first calibrated ArmCpuProfile (tensor-g3,
  Pixel 8 Pro battery telemetry; e_byte 88.3 pJ, e_mac 84.6 pJ,
  system-level). Analyzer v2 with boundary-extended integration and
  per-window coverage after the audit exposed a v1 undercount;
  coverage audit and part-merge scripts committed.
- EXP-003b phone tooling: Termux battery sampler and measurement
  block (protocol-enforcing: refuses while charging, thermal readings
  per rep), provisioning script, and the battery-energy analyzer
  (phone_energy.py) with locked unit rules from the Pixel 8 Pro
  calibration paste, trapezoid integration, baseline netting,
  charging-sample flagging, and 2- and 3-parameter energy fits.
- EXP-003a time-structure calibration (calibrate.py): closed-form
  fits of decode time against model bytes (effective bandwidth per
  thread level) and against inverse threads (per-quant floor vs the
  observed ceiling), pre-registered predictions in the logbook,
  outputs under experiments/exp_003_time_fit/.
- Submission charts (scripts/make_charts.py): five figures generated
  from committed artifacts with cited constants for logbook-only
  numbers; smoke-tested.
- Governed-agent finale (examples/governed_agent.py): a pollard run on
  a live Arm llama-server with TomlCpuMeter charging predicted joules
  per call and Budget(extra={"joules": ...}) refusing an oversized
  request before dispatch. Integration-tested against installed
  pollard 1.5.1 with a fake model function, including the veto path.
- Sweep orchestrator (sweep.py): launches one cold llama-server per
  condition, walks the models x threads grid with warmup exclusion,
  enforces append-only experiment directories, and writes frozen
  configs, environment snapshots, raw per-request records, and summary
  results. probe subcommand for quick measurements against an already
  running endpoint; CLI grows sweep and probe subcommands.
- Sweep host pivot: GCP Axion c4a-standard-16 (Neoverse V2) replaces
  Hetzner CAX41 after a full CAX stock-out across regions; logbook
  addendum records the change and its ablation consequences.
- Measurement core (bench.py): streamed chat completions against any
  OpenAI-compatible endpoint with client-side TTFT and throughput
  measurement, SSE parsing that fails loudly on malformed data, token
  accounting with server-usage override and chunk-count fallback, and
  per-metric summary statistics. Fixed prompt set for deterministic
  benchmark inputs (configs/prompts.txt).
- TomlCpuMeter (meter.py): pollard 1.5.1 meter adapter with post-call
  charging in predicted joules, pre-dispatch estimation for
  Budget(extra={"joules": ...}) admission control, optional strict mode
  raising an auditable MeterPrecheckRefusal for unknown architectures,
  pluggable token estimators, and a leaf-walking character heuristic
  aligned with pollard's OpenAITokenEstimator traversal.
- TOML energy model core (toml_model.py): GQA and SwiGLU aware operation
  counts, prefill and decode phase split, DRAM traffic model, Neoverse N1
  and V2 placeholder profiles with explicit uncalibrated flags, Qwen2.5
  0.5B and 1.5B specs verified against published parameter counts.
- Hosts plan reflecting the June 2026 Oracle free tier reduction: free A1
  (2 OCPU / 12 GB) as always-on endpoint, Hetzner CAX41 as sweep host,
  GCP Axion C4A as the Neoverse V2 validation session.
- Repository scaffold: package skeleton, test skeleton, configs, logbook,
  findings, prose scanner, license, environment template.
