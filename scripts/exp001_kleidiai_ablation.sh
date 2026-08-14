#!/usr/bin/env bash
# EXP-001: KleidiAI ON vs OFF ablation on one recorded llama.cpp commit.
# Pre-registered protocol: LOGBOOK.md, EXP-001 final addendum.
# Cells: build {kleidiai, generic} x threads {8, 16}; 5 reps per cell;
# llama-bench -p 512 -n 128, JSON output.
# Run after provision_axion.sh: bash exp001_kleidiai_ablation.sh
set -euo pipefail

BASE="${HOME}/wwbench"
MODEL="${BASE}/models/qwen2.5-1.5b-instruct-q4_0.gguf"
OUT="${BASE}/exp001"
REPS=5
THREADS_SET=(8 16)
BUILDS=(kleidiai generic)

mkdir -p "${OUT}"
cp "${BASE}/environment.txt" "${OUT}/environment.txt"

for build in "${BUILDS[@]}"; do
  BENCH="${BASE}/llama.cpp/build-${build}/bin/llama-bench"
  if [ ! -x "${BENCH}" ]; then
    echo "missing ${BENCH}; run provision_axion.sh first" >&2
    exit 1
  fi
  for threads in "${THREADS_SET[@]}"; do
    for rep in $(seq 1 "${REPS}"); do
      echo "== ${build} t=${threads} rep=${rep}/${REPS} =="
      "${BENCH}" -m "${MODEL}" -t "${threads}" -p 512 -n 128 -o json \
        > "${OUT}/${build}_t${threads}_rep${rep}.json"
    done
  done
done

echo "EXP-001 COMPLETE. Raw files:"
ls -l "${OUT}"
echo
echo "Pack for transfer:"
echo "  tar czf ~/exp001_raw.tgz -C ${BASE} exp001 environment.txt"
