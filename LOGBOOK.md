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
Recorded in the completed-results block below (2026-08-14).

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

### Interpretation (superseded in part by EXP-004; see below)
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

---

## Addendum (2026-08-14): kernel identity attested by sampling profile

perf record, 999 Hz, 43,490 samples over llama-bench Q4_0 t8 decode
(-p 0 -n 128 -r 4), generic build:

- 60.37% self time in ggml_gemv_q4_0_4x8_q8_0 (libggml-cpu.so.0.20.0),
  invoked via ggml::cpu::repack::tensor_traits<block_q4_0, 8, 4>::
  compute_forward.
- Confirms the EXP-001 interpretation directly: the generic build's
  runtime-repack path with an arch-dispatched Q4_0 GEMV dominates
  decode. Single-kernel weight streaming also matches the TOML model's
  bandwidth-priced decode structure.
- Tool note: Arm Performix code_hotspots (runs 5594a28de43e,
  1df83bc0482a) attested the silicon (Neoverse-V2, MIDR 0x410fd4f1)
  and produced exportable artifacts, but could not symbolize the
  dlopen'd libggml-cpu module, leaving the dominant frame anonymous
  (53.8%) with sample bleed onto one-time init symbols. Documented as
  a limitation for this workload shape; memory_access recipe is
  unavailable on this VM (no SPE exposure from the hypervisor).

---

## EXP-004: Remote-client separation test of the t16 collapse

**Date:** planned 2026-08-14, executes in the same Axion session
**Researcher:** Muntaser Syed
**Type:** computational
**Status:** completed

### Hypothesis
The EXP-002 t16 collapse is caused by client-server co-location on a
fully subscribed core set. Prediction: with the measuring client moved
off-box (laptop, via SSH tunnel), served tg at t16 recovers
substantially above the co-located 52.4 tok/s, toward the pure-bench
140.9; served tg at t8 stays approximately 93 tok/s (control),
because at t8 free cores existed either way.

### Independent Variables
- Client location: co-located (EXP-002 data) vs remote (this run)
- Threads: 16 (treatment), 8 (control)

### Dependent Variables / Metrics
- gen_tok_s via wattwarden probe, 5 reps. TTFT is recorded but carries
  one WAN round trip and SSH overhead; it is not compared against
  co-located TTFT.

### Control Conditions
- Same binary (generic), model (Q4_0), port, context, prompt, seed,
  n_predict as EXP-002; server foregrounded with no other load.

### Protocol
1. Box: llama-server -t 16. Laptop: ssh -L tunnel; wattwarden probe,
   5 reps.
2. Box: restart llama-server -t 8. Laptop: probe again.
3. Record both summaries here.

### Results / Observations / Interpretation
Condition A completed 2026-08-14 (t16, remote client via SSH tunnel):
gen_tok_s 52.14 (sd 0.025, n 5) vs co-located 52.4. TTFT 120.6 ms
carries the WAN plus tunnel round trip, excluded from comparison as
pre-registered. Protocol deviation, immaterial to tg: the probe used
its default prompt (near-identical to sweep prompt_index 0) and ran
the full 128 tokens.

Condition B completed 2026-08-14 (t8, remote client, control):
gen_tok_s 93.24 (sd 0.240, n 5) vs co-located 92.8. Control passes:
the tunnel and remote client do not distort tg.

HYPOTHESIS REFUTED: client location does not move served t16
throughput. The collapse is server-side. Revised candidate mechanism:
llama-server's own serving threads (HTTP accept loop plus a per-token
SSE writer) oversubscribe a fully loaded core set of busy-spinning
generation workers, forcing a context switch per token; llama-bench
runs exactly 16 compute threads and nothing else. Tested next as
EXP-005.

---

## EXP-005: One spare core for the serving machinery

**Date:** planned 2026-08-14, same session
**Researcher:** Muntaser Syed
**Type:** computational
**Status:** completed

### Hypothesis
If the t16 collapse is serving-thread oversubscription, then
llama-server with 15 generation threads (one core left for HTTP and
the SSE writer) recovers most of the gap: prediction tg > 120 tok/s
(remote client, same protocol as EXP-004). If tg stays near 52, the
mechanism is something else and will be reported as unexplained.

### Variables and Controls
- IV: generation threads 15 vs 16 (remote client held fixed).
- DV: gen_tok_s, 5 reps, wattwarden probe via tunnel.
- Controls: same binary, model, port, context; EXP-004 t16 remote is
  the direct baseline.

### Results / Observations / Interpretation
Completed 2026-08-14. t15 remote: gen_tok_s 53.49 (sd 0.051, n 5) vs
t16 remote 52.14. HYPOTHESIS REFUTED: one spare core recovers ~2.6%,
not the predicted majority of the gap. Per the pre-registered
alternative, the mechanism is recorded as UNEXPLAINED.

State of knowledge after EXP-002/004/005: served decode is
client-location-invariant and scales cleanly through t8 (93.2 remote,
92.8 co-located, within 1% of bench); a server-side collapse onsets
somewhere in t9..t14 (t15 and t16 both ~52-54); the identical
llama_decode path in llama-bench scales to t16 (140.9). Untested
conjecture, labeled as such: per-token threadpool sleep/wake storms in
the server's decode-sample-write loop, absent from bench's tight
loop, with wake cost scaling in thread count. Not pursued further in
this session; the operational rule (threads at or below 8 on this
host when serving) is empirical and does not depend on the mechanism.

---

## Addendum (2026-08-14), re: EXP-005: exploratory cliff locator

Post-hoc single point, labeled exploratory (not pre-registered): t12
remote gen_tok_s 57.18 (sd 0.065, n 5). Served-throughput scan now
reads t8 93.2, t12 57.2, t15 53.5, t16 52.1: collapse onset is
between t9 and t11, with gentle decline beyond. Served throughput
peaks at or near t8 on this host.

---

## Editorial addendum (2026-08-14): logbook re-sequencing

Earlier today, file edits anchored on the ambiguous line "Pending."
spliced EXP-004 condition-A results and the EXP-005 entry into the
middle of the EXP-002 registration. This revision re-sequences the
blocks chronologically, adds the previously unfiled EXP-004 condition
B and the EXP-005 t12 locator, and marks EXP-002's interpretation as
partially superseded by EXP-004. No measured value, hypothesis,
refutation, or dated statement was altered or removed.

---

## EXP-003a: Time-structure calibration of the TOML decode model

**Date:** planned 2026-08-14, laptop analysis of committed artifacts
**Researcher:** Muntaser Syed
**Type:** computational (analysis of EXP-001/EXP-002 data; no new runs)
**Status:** planned

### Hypothesis
The TOML decode decomposition holds on Axion V2: at a fixed thread
count, decode time per token is approximately linear in model bytes
across quantizations (bandwidth term), with a positive intercept
(compute and overhead term). Predictions, made before fitting:

- At t8, the fitted slope inverts to an effective bandwidth in the
  130 to 170 GB/s range, consistent with the ~150 GB/s ceiling
  observed directly.
- Intercepts are positive at every t, and the Q4_K_M cell sits above
  the two-point line through Q4_0 and Q8_0 (its kernels cost more per
  byte), so the three-quant linear fit will show visible residual at
  t >= 4. If instead residuals are near zero everywhere, the
  quant-dependent compute claim is refuted.
- At t1 the compute term dominates and the bandwidth estimate is
  poorly identified (wide spread across t levels is expected there).

### Method
For each thread level t in {1,2,4,8,16}: ordinary least squares of
time-per-token (1/tg, from EXP-002 means) against model bytes (GGUF
file sizes) across the three quants; report slope, intercept,
implied GB/s, and R^2. Secondary per-quant view across t. Pure
Python closed-form regression; script scripts/fit_exp003.py; outputs
to experiments/exp_003_time_fit/.

### Scope
Time structure only. Energy constants remain uncalibrated until
EXP-003b anchors them against a host with power telemetry (Apple
Silicon powermetrics planned). The meter's calibrated flag does not
flip in EXP-003a.

### Results / Observations / Interpretation
Completed 2026-08-14. Fit outputs: experiments/exp_003_time_fit/.

Prediction outcomes:
1. REFUTED as posed: the per-thread cross-quant regression is not a
   usable bandwidth instrument. Effective GB/s swings 87 to 720
   non-monotonically with R^2 0.41 to 0.87. Cause: ill conditioning
   (Q4_0 and Q4_K_M bytes differ by only 51 MB) plus quant-dependent
   kernel cost dominating the byte signal.
2. CONFIRMED: Q4_K_M sits above the fitted line at every thread
   level (+4.41 ms at t1 shrinking to +0.30 ms at t16), the exact
   signature of costlier per-byte kernels predicted in advance.
3. CONFIRMED trivially; identification is poor at every t in this
   view, not only t1.

Post-hoc discovery, labeled exploratory: within each quant, decode
time per token obeys time = A + B/t over t in {1,2,4,8} with R^2
0.9990 to 1.0000. Floors A are quant-INDEPENDENT (4.44, 4.55, 3.95
ms) rather than proportional to model bytes: the serial component is
per-token overhead, not weight streaming. All byte and MAC work lives
in the parallel term B/t (54.7, 63.4, 68.2 ms). Q8_0 at t8 lies on
its own 1/t line (fit 12.47 ms vs measured 12.56 ms), so the data
through t8 do not require a binding bandwidth ceiling; the ~150 GB/s
figure is an approached upper range, consistent with a ceiling but
not demonstrated as one below t16. Findings and write-up wording
corrected accordingly on this date. Extrapolating the law to t16
predicts 127 tok/s for Q4_0 against the measured bench 140.9,
consistent with mild super-1/t scaling entering at high t.

Consequence for the TOML meter: on this host the calibrated TIME
model is A plus B_q/t; energy anchoring remains EXP-003b. The
calibrated flag stays False.

---

## Addendum (2026-08-14), re: EXP-003b instrument

The EXP-003a scope named Apple Silicon powermetrics as the planned
EXP-003b instrument. Corrected: no Mac exists in this lab. EXP-003b
will use an Android Arm SoC via the battery energy counter APIs
(BatteryManager ENERGY_COUNTER, or current times voltage where the
counter is absent), the same instrument the mobile entry's battery
governor uses. Device model to be recorded at registration time.
