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

---

## Addendum (2026-08-11, before any execution), re: EXP-001

Oracle halved the Always Free Ampere A1 allowance to 2 OCPUs and 12 GB
effective 2026-06-15 (official docs updated; no announcement). EXP-001 was
planned against the old 4 OCPU / 24 GB assumption and has not yet run.
Protocol amendments, recorded here rather than by editing the entry:

- Instance for EXP-001 becomes the Always Free A1 at 2 OCPUs / 12 GB; the
  fixed thread condition changes from 4 to 2.
- The full thread-scaling sweep (1 through 16 threads) moves to a paid
  hourly Ampere Altra host (Hetzner CAX41 class, same Neoverse N1
  microarchitecture) and will be registered as its own experiment.
- The free A1 instance's role shifts to always-on judging endpoint.
- hosts section of configs/base.yaml updated accordingly on this date.

---

## Addendum (2026-08-11, before any execution), re: EXP-001 sweep host

Hetzner CAX capacity checked at provisioning time: out of stock in every
region that offers the type. Sweep host changes from Hetzner CAX41
(Neoverse N1) to GCP Axion c4a-standard-16 (Neoverse V2) on trial
credits, with c4a-standard-8 as the quota fallback. Consequences:

- The many-core sweep and the KleidiAI ON/OFF ablation now run on
  Neoverse V2, where i8mm and SVE2 kernel paths are available; N1 has
  dotprod only, so the ablation contrast is expected to differ by
  microarchitecture and both will be reported separately.
- The N1 data points come from the Always Free A1 endpoint (2 OCPUs).
- configs/base.yaml hosts section updated accordingly on this date.

---

## Addendum (2026-08-11, before any execution), re: EXP-001 final protocol

Consolidated protocol for execution on the GCP Axion session (declared
before the instance runs; supersedes thread-count language above):

- Host: GCP c4a-standard-16 (Neoverse V2), Ubuntu 24.04 arm64.
- Builds: llama.cpp at one recorded commit SHA, built twice:
  GGML_CPU_KLEIDIAI=ON and OFF, Release, all cores.
- Model: qwen2.5-1.5b-instruct-q4_0.gguf (single model for the
  ablation; the full quant grid belongs to the sweep, not EXP-001).
- Conditions: build flag {ON, OFF} x threads {8, 16}. Threads are a
  declared control set, not an independent variable claim.
- Tool: llama-bench, -p 512 -n 128, JSON output, 5 repetitions per
  cell, executed by scripts/exp001_kleidiai_ablation.sh.
- Recorded: commit SHA, compiler and OS versions, lscpu flags, raw
  llama-bench JSON per repetition.
- Report: mean and standard deviation of pp and tg tokens/s per cell.

---

## EXP-002: Quant x thread sweep, Axion c4a-standard-16

**Date:** planned 2026-08-11, executes in the same Axion session
**Researcher:** Muntaser Syed
**Type:** computational
**Status:** planned

### Hypothesis
Token generation throughput saturates below the full 16 threads because
decode is memory-bandwidth bound; prompt processing scales closer to
linearly. Q4_0 delivers the highest tg tokens/s; Q8_0 the lowest.
Directions predicted; magnitudes to be measured.

### Independent Variables
- Quantization: Q4_0, Q4_K_M, Q8_0 (fixed model: Qwen2.5-1.5B-Instruct)
- Threads: {1, 2, 4, 8, 16}

### Dependent Variables / Metrics
- TTFT ms, generation tokens/s, e2e s (client-side, wattwarden bench)

### Control Conditions
- KleidiAI build only; one llama-server cold start per condition;
  fixed prompt (prompt_index 0); n_predict 128; seed 42; 5 reps + 1
  unrecorded warmup per condition.

### Protocol
wattwarden sweep --exp-id exp_002_axion_sweep on the box; artifacts
per driver design (frozen config, environment snapshot, raw jsonl,
results.json).

### Environment
GCP c4a-standard-16, Ubuntu 24.04 arm64; llama.cpp SHA from
environment.txt; wattwarden at the current local commit.

### Results / Observations / Interpretation
Pending.

---

## Addendum (2026-08-14, at execution), re: EXP-001 and EXP-002 OS

Instance booted GCP's default image: Debian 13 (kernel 6.12 arm64), not
Ubuntu 24.04 as declared. No protocol impact (identical apt packages and
toolchain); environment.txt records the actual OS. Hostname: wattwarden.

---

## EXP-001: Results (completed 2026-08-14, Axion c4a-standard-16, Debian 13)

llama.cpp commit 6fed9f6ff (build 10436); qwen2.5-1.5b-instruct-q4_0
(model_size 1,060,276,736 B; gguf n_params 1,777,088,000: output head
stored untied). 5 invocations per cell; unit of analysis is the
per-invocation avg_ts.

| build | threads | pp tok/s (mean, sd) | tg tok/s (mean, sd) |
|---|---|---|---|
| generic  | 8  | 311.1, 0.18 | 93.7, 0.42 |
| generic  | 16 | 494.1, 1.25 | 140.9, 1.89 |
| kleidiai | 8  | 315.8, 0.07 | 87.6, 0.69 |
| kleidiai | 16 | 500.1, 2.05 | 120.1, 5.50 |

KleidiAI/generic ratios: pp 1.015x (t8), 1.012x (t16); tg 0.935x (t8),
0.853x (t16).

### Observations
- Hypothesis REFUTED for token generation: the KleidiAI build is 6.5%
  slower at t8 and 14.7% slower at t16. Prefill gain is ~1.3%, barely
  above noise.
- Variance signature: kleidiai t16 tg sd (5.50) is 3x to 13x every
  other cell, suggesting scheduling or threadpool interaction at full
  core count.
- Implied weight-streaming bandwidth (tg x model bytes): ~99 GB/s at
  t8, ~149 GB/s at t16 (generic). Thread doubling yields 1.50x tg:
  partial bandwidth saturation, consistent with the EXP-002 hypothesis.
- The GGUF stores the output head untied (n_params 1.777B vs 1.543B
  architectural): decode bandwidth pricing should use measured
  model_size bytes, not architectural parameter counts.

### Interpretation
The generic aarch64 path in this llama.cpp commit already runtime
repacks Q4_0 and uses i8mm/dotprod kernels; KleidiAI substitution
helps batched GEMM (prefill) marginally and hurts batch-1 GEMV
(decode) on this silicon at this commit. The correct production flag
on this host, for this workload, is KleidiAI OFF. Scope limits: one
model, one quant, one commit, one machine; no claim beyond that cell.
Consequence recorded for EXP-002 below.

---

## Addendum (2026-08-14, after EXP-001, before EXP-002 execution)

EXP-002 pre-registration said "KleidiAI build only." Informed by the
EXP-001 refutation, the sweep executes on the generic build (the
faster decode configuration on this host). This is a documented
sequential-design decision, not a post-hoc metric choice: the
dependent variables and grid are unchanged.

---

## EXP-002: Results (completed 2026-08-14, Axion c4a-standard-16, generic build)

Server-measured via wattwarden sweep (client-side clock), 5 reps + 1
warmup per condition, prompt_index 0, n_predict 128, seed 42.

tg tok/s (mean; sd in raw results.json):

| quant | t1 | t2 | t4 | t8 | t16 |
|---|---|---|---|---|---|
| Q4_0   | 17.0 | 30.5 | 55.4 | 92.8 | 52.4 |
| Q4_K_M | 14.7 | 27.4 | 48.8 | 81.5 | 50.7 |
| Q8_0   | 13.9 | 26.3 | 47.9 | 79.6 | 48.4 |

Best serving config on this host: Q4_0 t8, 92.8 tok/s, TTFT 14.8 ms.

### Observations
- t16 regresses ~40% below t8 for all quants, while EXP-001's
  llama-bench measured 140.9 tok/s at t16 on the same binary, model,
  and machine. The t8 cells cross-validate within 1% of llama-bench
  (92.8 vs 93.7), so the divergence is specific to the full-core
  condition, not the method.
- Byte-throughput ceiling ~150 GB/s appears consistently: Q8_0 t8
  streams 150.8 GB/s; llama-bench Q4_0 t16 streamed 149 GB/s. Q4_0 t8
  (99 GB/s) is below the ceiling, hence its continued scaling in the
  bench setting.
- Hypothesis check: saturation-below-16-threads confirmed in the bench
  setting via EXP-001 (1.50x from t8 to t16); in the serving setting
  the t16 condition is dominated by a different effect (below).
- Output lengths differ per quant at fixed seed (93, 110, 99 tokens):
  expected, throughput normalizes per token.

### Interpretation
The sweep co-locates llama-server and the measuring client on the same
16 vCPUs, and ggml generation threads busy-spin. At t16 no cores
remain for the HTTP path, the client, or the OS; scheduling
interference collapses throughput. This is a real deployment finding,
not an artifact to discard: on an N-core Arm host serving over HTTP
with any co-located work, cap generation threads below N. The advisor
must treat t equal to core count as contaminated in co-located mode.
Follow-up registered as EXP-004 (remote-client separation) when a
second host is available; scope of the present numbers is co-located
serving, stated as such.
