#!/usr/bin/env bash
# Provision an Arm64 Ubuntu 24.04 box for wattwarden benchmarking.
# Builds llama.cpp twice (KleidiAI ON and OFF) and downloads models.
# Run as a normal user with sudo rights: bash provision_axion.sh
set -euo pipefail

BASE="${HOME}/wwbench"
MODELS="${BASE}/models"
HF="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main"

echo "== [1/5] system packages =="
sudo apt-get update -y
sudo apt-get install -y build-essential cmake git curl \
  libcurl4-openssl-dev python3-pip python3-venv

mkdir -p "${BASE}" "${MODELS}"
cd "${BASE}"

echo "== [2/5] clone llama.cpp and record the commit =="
if [ ! -d llama.cpp ]; then
  git clone https://github.com/ggml-org/llama.cpp
fi
cd llama.cpp
LLAMA_SHA="$(git rev-parse HEAD)"
echo "llama.cpp commit: ${LLAMA_SHA}"

echo "== [3/5] build with KleidiAI ON =="
cmake -B build-kleidiai -DCMAKE_BUILD_TYPE=Release -DGGML_CPU_KLEIDIAI=ON
cmake --build build-kleidiai -j"$(nproc)" --target llama-server llama-bench

echo "== [4/5] build with KleidiAI OFF (generic Arm) =="
cmake -B build-generic -DCMAKE_BUILD_TYPE=Release -DGGML_CPU_KLEIDIAI=OFF
cmake --build build-generic -j"$(nproc)" --target llama-server llama-bench

echo "== [5/5] models =="
cd "${MODELS}"
for f in qwen2.5-1.5b-instruct-q4_0.gguf \
         qwen2.5-1.5b-instruct-q4_k_m.gguf \
         qwen2.5-1.5b-instruct-q8_0.gguf; do
  if [ ! -f "$f" ]; then
    echo "downloading $f"
    curl -fL -o "$f" "${HF}/$f"
  fi
done
ls -lh

ENV_FILE="${BASE}/environment.txt"
{
  echo "captured_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "llama_cpp_sha: ${LLAMA_SHA}"
  echo "uname: $(uname -a)"
  echo "gcc: $(gcc --version | head -1)"
  echo "cmake: $(cmake --version | head -1)"
  echo "nproc: $(nproc)"
  echo "-- lscpu --"
  lscpu
} > "${ENV_FILE}"
echo "environment recorded to ${ENV_FILE}"
echo "PROVISION COMPLETE"
