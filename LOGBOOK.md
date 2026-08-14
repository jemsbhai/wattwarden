# Experimental Logbook: wattwarden

Append-only. Entries are planned before execution and completed after.
Corrections are dated addenda; past entries are never edited.

---

## EXP-001: KleidiAI kernels vs generic build, Ampere A1 baseline

**Date:** planned (fill at execution, with timezone)
**Researcher:** Muntaser Syed
**Type:** computational
**Status:** planned

### Hypothesis
llama.cpp built with KleidiAI kernels (GGML_CPU_KLEIDIAI=ON) delivers higher
prompt-processing and token-generation throughput than the generic Arm build
on Ampere A1 (Neoverse N1) for Q4_0 quantized models, because KleidiAI
provides dotprod micro-kernels matched to N1. Expected direction: positive.
Magnitude: unknown, to be measured, no prior claim.

### Independent Variables
- Build flags: GGML_CPU_KLEIDIAI=ON vs OFF (same llama.cpp commit)

### Dependent Variables / Metrics
- Prompt processing tokens/s (llama-bench pp)
- Token generation tokens/s (llama-bench tg)
- TTFT ms via llama-server, measured by the sweep driver

### Control Conditions
- Same model file (Qwen2.5-1.5B-Instruct, Q4_0), same thread count (4),
  same instance, same llama.cpp commit SHA, same seed, same prompt set
- Repetitions: 5 per condition; report mean and standard deviation

### Protocol
1. Provision Oracle Ampere A1 (A1.Flex, 4 OCPU, 24 GB).
2. Record OS, kernel, compiler versions into environment snapshot.
3. Clone llama.cpp at a pinned commit; record SHA.
4. Build twice (KleidiAI ON, OFF); record both build logs.
5. Run llama-bench 5x per condition; record raw output.
6. Compute mean and standard deviation; write results here and in
   findings.md.

### Environment
- Hardware: Oracle A1.Flex, 4 OCPU Ampere Altra (Neoverse N1), 24 GB (fill
  exact shape and region at execution)
- Software: fill at execution (OS, gcc, cmake, llama.cpp SHA)
- Git commit: fill at execution
- Config file: configs/base.yaml (frozen copy into experiments/exp_001/)
- Seeds: 42

### Results
Pending.

### Observations
Pending.

### Interpretation
Pending.

### Artifacts
- experiments/exp_001_kleidiai_baseline/ (created at execution)
