#!/data/data/com.termux/files/usr/bin/bash
# EXP-003b patch block (part 2): reruns the Q8_0 cells after the part-1
# session froze in a cooldown (Android Doze; wake lock arrived too late
# for that clone). Same protocol, same sampler, own pre and post
# baselines; outputs to exp003b_part2 so part 1 is never touched.
# Deviation recorded in the logbook at results time.
# Usage: bash exp003b_patch.sh
set -euo pipefail

BASE="${HOME}/wwphone"
OUT="${BASE}/exp003b_part2"
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
termux-wake-lock 2>/dev/null || true
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
trap 'kill ${SAMPLER_PID} 2>/dev/null || true; termux-wake-unlock 2>/dev/null || true' EXIT
sleep 3

echo "== baseline (${BASELINE_S}s idle, screen on, do not touch) =="
T0=$(now_ms); sleep "${BASELINE_S}"; mark baseline "$T0" "$(now_ms)" part2_pre

run_cell() {
  local quant="$1" threads="$2" model="$3"
  for rep in $(seq 1 "${REPS}"); do
    local t_start t_end temp_a temp_b
    temp_a="$(temp_now)"
    echo "== ${quant} t${threads} rep ${rep}/${REPS} (temp ${temp_a}C) =="
    t_start=$(now_ms)
    "${BENCH}" -m "${model}" -t "${threads}" -p 0 -n 512 -r 1 -o json \
      > "${OUT}/${quant}_t${threads}_rep${rep}.json"
    t_end=$(now_ms)
    temp_b="$(temp_now)"
    mark "cell_${quant}_t${threads}" "${t_start}" "${t_end}" "rep${rep};temp_start=${temp_a};temp_end=${temp_b}"
    echo "cooldown ${COOLDOWN_S}s"
    local c0
    c0=$(now_ms); sleep "${COOLDOWN_S}"; mark cooldown "$c0" "$(now_ms)" "${quant}_t${threads}_rep${rep}"
  done
}

Q8="${BASE}/models/qwen2.5-1.5b-instruct-q8_0.gguf"
run_cell Q8_0 4 "${Q8}"
run_cell Q8_0 8 "${Q8}"

echo "== baseline (${BASELINE_S}s idle, post) =="
T1=$(now_ms); sleep "${BASELINE_S}"; mark baseline "$T1" "$(now_ms)" part2_post

kill "${SAMPLER_PID}" 2>/dev/null || true
echo "EXP-003B PART 2 COMPLETE"
echo "Pack both parts: tar czf ~/exp003b_raw.tgz -C ${BASE} exp003b_part1 exp003b_part2 environment.txt"
