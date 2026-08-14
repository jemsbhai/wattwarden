# Findings

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

Serving configuration on this host (EXP-002): best is Q4_0 at 8
threads, 92.8 tok/s with 14.8 ms TTFT. Setting generation threads to
the full core count collapses served throughput ~40% below t8 across
all quants, because ggml threads busy-spin and starve the HTTP path
and any co-located work; llama-bench (no serving stack) scales to t16
on the same binary. Practical rule, quantified: cap generation threads
below core count when serving. The platform's byte-throughput ceiling
is ~150 GB/s, reached by Q8_0 at t8 and by Q4_0 only in the pure-bench
setting at t16.

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
