# Findings

## Gains Ledger (all measured, all one-line configuration changes)

| optimization | baseline | optimized | gain | evidence |
|---|---|---|---|---|
| Serving thread count (t16 to t8) | 52.4 tok/s | 92.8 tok/s | +77% throughput | EXP-002, EXP-004 |
| Cost at recommended config | 3.45 $/Mtok (t16) | 1.94 $/Mtok (t8) | -44% cost | EXP-002 + advisor |
| Build flag for decode (KleidiAI to generic, t16 bench) | 120.1 tok/s | 140.9 tok/s | +17% | EXP-001 |
| Quantization for throughput (Q8_0 to Q4_0, t8 served) | 79.6 tok/s | 92.8 tok/s | +17%, quality tradeoff unmeasured here | EXP-002 |
| Model bytes on disk and in memory (Q8_0 to Q4_0) | 1.89 GB | 1.07 GB | -44% size | GGUF file sizes |

Every row is a decision wattwarden's sweep and advisor surface
automatically; none required code changes to llama.cpp.

## Curated Summary

On Google Axion (Neoverse V2, c4a-standard-16, Debian 13), llama.cpp
commit 6fed9f6ff, Qwen2.5-1.5B-Instruct Q4_0: the KleidiAI build is not
the fast configuration for single-stream decode. Token generation
regresses 6.5% at 8 threads (87.6 vs 93.7 tok/s) and 14.7% at 16
threads (120.1 vs 140.9 tok/s) relative to the generic aarch64 build,
while prompt processing gains only ~1.3% (EXP-001, pre-registered,
refuted hypothesis). Decode operates near the memory bandwidth ceiling
(~99 GB/s of weight streaming at t8, ~149 GB/s at t16), and doubling
threads from 8 to 16 buys only 1.50x generation throughput, an early
signature of bandwidth saturation. Practical conclusion, and the tool's
thesis: the right build flag is workload-, model-, and silicon-specific
and must be measured, not assumed.

One modeling correction surfaced by the data: this GGUF stores the
output head untied (1.777B stored parameters vs 1.543B architectural),
so bandwidth-priced decode energy must use measured model bytes
(model_size), not architectural parameter counts.

Serving configuration on this host (EXP-002, EXP-004): best is Q4_0 at
8 threads, 92.8 tok/s with 14.8 ms TTFT. Setting generation threads to
the full core count collapses served throughput ~40% below t8 across
all quants, and EXP-004 shows the collapse is server-side: it
reproduces identically with a remote client (52.1 vs 52.4 tok/s), so
client co-location is not the cause. The candidate mechanism under
test (EXP-005) is oversubscription by the server's own serving threads
on a fully loaded core set; llama-bench, with exactly N compute
threads and no serving stack, scales to t16 on the same binary.
Practical rule, already quantified: keep generation threads below the
core count when serving. On byte throughput: ~150 GB/s is the highest
observed weight-streaming rate (Q8_0 t8 served; Q4_0 t16 bench), an
approached upper range. EXP-003a shows the data through t8 fit a
quant-independent serial floor plus parallel term (time = A + B/t,
R^2 >= 0.999) with no ceiling term required, so 150 GB/s is
consistent with a ceiling but not demonstrated as one below t16.

On-device energy (EXP-003b, Pixel 8 Pro, Tensor G3): the TOML meter
now carries its first calibrated profile, fitted from battery
telemetry: 88.3 pJ per DRAM byte and 84.6 pJ per MAC at system level.
Measured cost sits near 0.2 J per generated token for Qwen2.5-1.5B
Q4_0, and energy per token rises monotonically with thread count
(resolved at t8): on big.LITTLE silicon, the fastest configuration is
not the cheapest, the mirror image of the Axion serving story where
t8 was the throughput and cost winner.

---

## Raw Findings Log

### 2026-08-14 -- EXP-001: KleidiAI ON vs OFF, Axion V2

**Key result:** KleidiAI tg 0.935x (t8) and 0.853x (t16) vs generic;
pp 1.015x and 1.012x. Hypothesis refuted for generation.

Details: 2 builds x threads {8,16}, 5 llama-bench invocations per cell,
-p 512 -n 128, Q4_0. Generic t8 tg 93.7 (sd 0.42); t16 140.9 (sd 1.89).
KleidiAI t16 tg shows anomalous variance (sd 5.50). Raw:
experiments/exp_001_kleidiai_ablation/exp001/.

### 2026-08-14 -- EXP-001 side observation: untied output head in GGUF

**Key result:** gguf n_params 1,777,088,000 vs architectural 1.543e9
for Qwen2.5-1.5B; model_size 1,060,276,736 B implies 4.77 effective
bits/weight. Decode byte pricing switches to measured model_size.

### 2026-08-14 -- EXP-002: quant x thread sweep, served, Axion V2

**Key result:** Q4_0 t8 best served config: 92.8 tok/s (sd 0.33),
TTFT 14.8 ms. t16 collapses ~40% below t8 for every quant (52.4, 50.7,
48.4 tok/s) while llama-bench t16 reached 140.9: co-located client
plus busy-spin generation threads at full core count starve the
serving path. t8 cross-validates llama-bench within 1%.

Details: 3 quants x threads {1,2,4,8,16}, 5 reps + warmup, client-side
clock. Q8_0 t8 byte throughput 150.8 GB/s marks the platform ceiling.
Raw: experiments/exp_002_axion_sweep/.

### 2026-08-14 -- EXP-004: t16 collapse is server-side, not the client

**Key result:** remote client through an SSH tunnel, t16: 52.14 tok/s
(sd 0.025) vs co-located 52.4. Hypothesis (client co-location causes
the collapse) refuted. Revised mechanism, serving-thread
oversubscription, registered as EXP-005.

### 2026-08-14 -- EXP-005: one spare core does not fix it; unexplained

**Key result:** t15 remote 53.49 tok/s vs t16 remote 52.14: spare-core
hypothesis refuted. Collapse onset bounded to t9..t14; mechanism
recorded as unexplained; operational rule (t <= 8 serving on this
host) unaffected.

### 2026-08-14 -- EXP-003a: decode time law found; bandwidth probe refuted

**Key result:** per quant, decode time per token = A + B/t with R^2
0.999 to 1.0000 (t in 1..8). Floors A are quant-independent (4.0 to
4.6 ms): the serial component is per-token overhead, not weight
streaming. The cross-quant bytes regression is unidentifiable (R^2
0.41 to 0.87; pre-registered prediction refuted); Q4_K_M's positive
residual at every t confirms costlier kernels. The ~150 GB/s figure
downgrades from ceiling to approached upper range. Fit artifacts:
experiments/exp_003_time_fit/.

### 2026-08-15 -- EXP-003b: first calibrated profile, from a phone

**Key result:** on-device battery telemetry on the Pixel 8 Pro
(Tensor G3) yields the meter's first calibrated=True profile: e_byte
88.3 pJ/byte, e_mac 84.6 pJ/MAC (system-level, two-parameter fit,
round-trip coherent to ~1% at the t4 workload). Measured J/token,
Qwen2.5-1.5B: Q4_0 0.193 (t1), 0.213 (t4), 0.275 (t8); Q8_0 0.282
(t4), 0.317 (t8). Energy per token rises with every added cluster
(resolved at t8): fastest is not cheapest on this SoC. One prediction
was rescued from a false refutation by the coverage audit and
estimator correction; a third pre-registered prediction (t4 beats t1)
is refuted as stated, with t1 and t4 statistically indistinguishable.
Full narrative, deviations, and limitations: LOGBOOK EXP-003b.

### 2026-08-14 -- Kernel identity: repacked Q4_0 GEMV owns decode

**Key result:** perf sampling (999 Hz, 43,490 samples) attributes
60.37% of Q4_0 t8 decode self time to ggml_gemv_q4_0_4x8_q8_0 via the
ggml cpu repack path. The generic build's optimization is measured,
not assumed; single-kernel weight streaming matches bandwidth-priced
decode. Performix could not symbolize the dlopen'd backend (documented
limitation); it attested the silicon (Neoverse-V2, MIDR 0x410fd4f1).
