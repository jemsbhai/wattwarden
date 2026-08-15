# wattwarden: energy-governed AI agents on Arm CPUs

Track: Cloud AI. Repo: https://github.com/jemsbhai/wattwarden (MIT, license
visible in About). New work created during the submission period, built on
our previously published open source packages pollard (1.5.1) and jsonld-ex
(0.7.4), and on the TOML operation-level energy model (FLAIRS-39).

## The pitch

Arm sells performance per watt, but a developer on an Arm cloud box cannot
see watts: Graviton, Axion, and Ampere VMs expose no energy counters, and
pollard, our agent governance framework, documents that its only energy
meter is NVML for local GPUs. wattwarden closes that documented gap. It
gives pollard a predictive Arm CPU energy meter built on the TOML operation
model, a benchmark sweep driver with a lab-grade evidence trail, an SLO
advisor that recommends serving configurations from measured data, and the
capability no measured-energy meter can have: a joule budget that refuses an
oversized model call BEFORE it dispatches.

One afternoon of use on a Google Axion c4a-standard-16 produced five
measured optimizations, two refuted assumptions the ecosystem holds, and a
reproducible finding about llama-server that we could not find documented
anywhere.

## Measured results (every number traces to a logged experiment)

Gains ledger, all one-line configuration changes surfaced by the tool:

| optimization | baseline | optimized | gain | evidence |
|---|---|---|---|---|
| Serving thread count (t16 to t8) | 52.4 tok/s | 92.8 tok/s | +77% throughput | EXP-002, EXP-004 |
| Cost at recommended config | 3.45 $/Mtok | 1.94 $/Mtok | -44% cost | EXP-002 + advisor |
| Build flag for decode (KleidiAI to generic, t16) | 120.1 tok/s | 140.9 tok/s | +17% | EXP-001 |
| Quantization (Q8_0 to Q4_0, t8 served) | 79.6 tok/s | 92.8 tok/s | +17% | EXP-002 |
| Model size (Q8_0 to Q4_0) | 1.89 GB | 1.07 GB | -44% | file sizes |

Three findings judges can reproduce from our scripts:

1. KleidiAI is not automatically the fast path. Pre-registered ablation
   (EXP-001): on Axion V2 with llama.cpp commit 6fed9f6ff, the KleidiAI
   build LOSES token generation by 6.5% (t8) and 14.7% (t16) against the
   generic Arm build, because the generic path already runtime-repacks
   Q4_0 into arch-dispatched kernels. We attested this with a sampling
   profile: 60.4% of decode self time in ggml_gemv_q4_0_4x8_q8_0 via the
   repack path. The lesson is the product: measure per workload and
   silicon, do not assume the branded flag.
2. llama-server collapses at high thread counts while llama-bench does
   not. Served throughput peaks at t8 (92.8 tok/s) and falls ~40% by t16
   on the same binary that benches 140.9 tok/s at t16. We tested and
   refuted two mechanisms (client co-location, EXP-004; one-spare-core,
   EXP-005), bounded the onset to t9..t11, and recorded the cause as
   unexplained. The operational rule stands and the advisor enforces it.
3. Decode time on this host obeys a clean law: per quant, time per
   token = A + B/t with R^2 of 0.999 to 1.0000 (EXP-003a fit of the
   sweep data). The serial floor A is quant-INDEPENDENT (~4 to 4.6
   ms): per-token overhead, not weight streaming, sets the fast
   limit. The highest observed streaming rate is ~150 GB/s, an
   approached upper range consistent with the TOML model's
   bandwidth-priced decode but not yet a demonstrated wall. Our own
   pre-registered cross-quant bandwidth probe was refuted as
   ill-conditioned, and that refutation is in the logbook too.

## What the tool does

- sweep: launches one cold llama-server per condition, walks quant x
  threads, measures client-side TTFT and tokens/s, and writes frozen
  configs, environment snapshots, and raw per-request records.
- advise: recommends the best measured configuration under a TTFT SLO and
  prices it in dollars per million tokens. Our Axion run: Q4_0 at 8
  threads, 92.8 tok/s, 14.8 ms TTFT, 1.94 $/Mtok, with full-core rows
  visibly excluded and the exclusion cited to its experiments.
- meter: TomlCpuMeter speaks pollard's meter protocol, charging predicted
  joules per model call from GQA-aware operation counts, and implements
  precheck estimation so Budget(extra={"joules": N}) can refuse a call
  pre-dispatch, with an auditable MeterPrecheckRefusal strict mode.
- governed agent: examples/governed_agent.py runs a real agent loop
  against llama-server on Arm; calls accrue predicted joules until an
  oversized request is vetoed before it ever reaches the server.

Live transcript from the Axion box (c4a-standard-16, llama-server at
the advisor's own recommended config, Q4_0 t8):

```text
budget: 30.0 J (predicted, TOML neoverse-v2), 5 steps
call 1: precheck 6.83 J, charged 6.65 J, spent 6.65 / 30.0 J
call 2: precheck 6.83 J, charged 8.16 J, spent 14.80 / 30.0 J
call 3: precheck 6.84 J, charged 4.41 J, spent 19.21 / 30.0 J
VETOED BEFORE DISPATCH: budget exceeded for joules
final charges: {'joules': 19.212732359220713, 'steps': 3.0, 'tokens': 301.0}
note: joule figures are TOML-model predictions on an uncalibrated
profile; calibration is EXP-003. Throughput and step data are real.
```

The fourth request (an oversized treatise with max_tokens 100000) was
refused by the meter's precheck against the remaining budget and never
reached llama-server. The full run tree persists in a pollard SQLite
store for report and HTML export.

Honesty contract, enforced in code: measured values carry method and
uncertainty; predicted joules are labeled predicted; the energy profile
ships with calibrated=False until the calibration experiment (EXP-003)
fits its constants, and the advisor refuses to print an uncalibrated
joule column. Two of our own pre-registered hypotheses were refuted this
session; both refutations are in the public logbook.

## How it uses Arm

Built and evaluated on Google Axion (Neoverse V2, silicon-attested by Arm
Performix: MIDR 0x410fd4f1); KleidiAI built, benchmarked, and honestly
ablated against llama.cpp's generic Arm repack path; Arm Performix used
for hotspot profiling and exportable run artifacts (two runs committed),
with its dlopen symbolization limits documented; perf on Arm PMU counters
for kernel identity; the model registry and DRAM model are tuned to Arm
serving realities (dotprod, i8mm, SVE2 feature detection guided host
selection).

## Reproducibility and DX

Everything is a public MIT repo: 60 passing tests, an append-only
experimental logbook with pre-registered hypotheses, a findings file, a
banned-vocabulary prose gate, provisioning and experiment scripts that
took a fresh Arm VM to first data in under twenty minutes, and raw
artifacts (llama-bench JSON, Performix exports, perf tables) committed
next to the conclusions they support. Setup instructions live in the
README; the sweep, advisor, and governed agent each run with one command.

## What's next

EXP-003b calibrates the energy profile against a host with real power
telemetry: an Android Arm SoC (Pixel 8 Pro, Tensor G3) measured through
its battery telemetry, flipping predicted joules from relative to
absolute; the time-structure half,
EXP-003a, is already completed and committed. pollard 1.5.1 already ships an MCP registry
bridge (registry_from_mcp), so the governed agent's next milestone is
discovering jsonld-ex's 53-tool MCP server under the same joule budget.
An always-free Ampere A1 endpoint (Neoverse N1) extends the cross-silicon
story and gives judges a live target.
