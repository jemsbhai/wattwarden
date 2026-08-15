#!/data/data/com.termux/files/usr/bin/bash
# EXP-003b measurement block. Pre-registered protocol: LOGBOOK.md.
# One continuous 1 Hz sampler for the whole session plus an events file
# marking phase boundaries; analysis aligns windows offline.
# Cells: Q4_0 x t{1,4,8} and Q8_0 x t{4,8}; 5 reps each; llama-bench
# -p 0 -n 128 -r 1 so tokens per invocation are exactly 128.
# Refuses to start unless the battery reports discharging.
# Usage: bash exp003b_run.sh
set -euo pipefail

BASE="${HOME}/wwphone"
OUT="${BASE}/exp003b"
BENCH="${BASE}/llama.cpp/build/bin/llama-bench"
REPS=5
BASELINE_S=120
COOLDOWN_S=90

STATUS="$(termux-battery-status | python3 -c "import sys,json;print(json.load(sys.stdin).get('status',''))")"
if [ "${STATUS}" != "DISCHARGING" ] && [ "${STATUS}" != "NOT_CHARGING" ]; then
  echo "battery status is ${STATUS}: unplug the phone first (protocol)" >&2
  exit 1
fi

mkdir -p "${OUT}"
cp "${BASE}/environment.txt" "${OUT}/environment.txt" 2>/dev/null || true
SAMPLES="${OUT}/samples.csv"
EVENTS="${OUT}/events.csv"
echo "phase,start_ms,end_ms,note" > "${EVENTS}"

now_ms() { echo $(( $(date +%s%N) / 1000000 )); }
temp_now() {
  termux-battery-status | python3 -c "import sys,json;print(json.load(sys.stdin).get('temperature',0))"
}
mark() { echo "$1,$2,$3,$4" >> "${EVENTS}"; }

bash "$(dirname "$0")/exp003b_sampler.sh" "${SAMPLES}" &
SAMPLER_PID=$!
trap 'kill ${SAMPLER_PID} 2>/dev/null || true' EXIT
sleep 3

echo "== baseline (${BASELINE_S}s idle, screen on, do not touch) =="
T0=$(now_ms); sleep "${BASELINE_S}"; mark baseline "$T0" "$(now_ms)" pre

run_cell() {
  local quant="$1" threads="$2" model="$3"
  for rep in $(seq 1 "${REPS}"); do
    local t_start t_end temp_a temp_b
    temp_a="$(temp_now)"
    echo "== ${quant} t${threads} rep ${rep}/${REPS} (temp ${temp_a}C) =="
    t_start=$(now_ms)
    "${BENCH}" -m "${model}" -t "${threads}" -p 0 -n 128 -r 1 -o json \
      > "${OUT}/${quant}_t${threads}_rep${rep}.json"
    t_end=$(now_ms)
    temp_b="$(temp_now)"
    local note="rep${rep};temp_start=${temp_a};temp_end=${temp_b}"
    mark "cell_${quant}_t${threads}" "${t_start}" "${t_end}" "${note}"
    echo "cooldown ${COOLDOWN_S}s"
    local c0
    c0=$(now_ms); sleep "${COOLDOWN_S}"; mark cooldown "$c0" "$(now_ms)" "${quant}_t${threads}_rep${rep}"
  done
}

Q4="${BASE}/models/qwen2.5-1.5b-instruct-q4_0.gguf"
Q8="${BASE}/models/qwen2.5-1.5b-instruct-q8_0.gguf"
run_cell Q4_0 1 "${Q4}"
run_cell Q4_0 4 "${Q4}"
run_cell Q4_0 8 "${Q4}"
run_cell Q8_0 4 "${Q8}"
run_cell Q8_0 8 "${Q8}"

echo "== baseline (${BASELINE_S}s idle, post) =="
T1=$(now_ms); sleep "${BASELINE_S}"; mark baseline "$T1" "$(now_ms)" post

kill "${SAMPLER_PID}" 2>/dev/null || true
echo "EXP-003B BLOCK COMPLETE"
echo "Pack for transfer: tar czf ~/exp003b_raw.tgz -C ${BASE} exp003b environment.txt"
