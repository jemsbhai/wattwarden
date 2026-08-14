# Changelog

All notable changes to this project are documented in this file.
Format follows Keep a Changelog; versioning follows SemVer.

## [Unreleased]

### Added
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
- Repository scaffold: package skeleton, test skeleton, configs, logbook,
  findings, prose scanner, license, environment template.
