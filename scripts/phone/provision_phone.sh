#!/data/data/com.termux/files/usr/bin/bash
# EXP-003b provisioning for Termux on the Pixel 8 Pro.
# Clones and builds llama.cpp (llama-bench), downloads the two models,
# and records the environment. Run once: bash provision_phone.sh
set -euo pipefail

BASE="${HOME}/wwphone"
MODELS="${BASE}/models"
HF="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main"

mkdir -p "${BASE}" "${MODELS}"
cd "${BASE}"

echo "== [1/4] clone llama.cpp and record the commit =="
if [ ! -d llama.cpp ]; then
  git clone https://github.com/ggml-org/llama.cpp
fi
cd llama.cpp
LLAMA_SHA="$(git rev-parse HEAD)"
echo "llama.cpp commit: ${LLAMA_SHA}"

echo "== [2/4] build llama-bench (native Termux clang) =="
cmake -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF
cmake --build build -j"$(nproc)" --target llama-bench

echo "== [3/4] models (Q4_0 and Q8_0, ~3 GB total) =="
cd "${MODELS}"
for f in qwen2.5-1.5b-instruct-q4_0.gguf qwen2.5-1.5b-instruct-q8_0.gguf; do
  if [ ! -f "$f" ]; then
    echo "downloading $f"
    curl -fL -o "$f" "${HF}/$f"
  fi
done
ls -lh

echo "== [4/4] environment snapshot =="
ENV_FILE="${BASE}/environment.txt"
{
  echo "captured_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "llama_cpp_sha: ${LLAMA_SHA}"
  echo "device: $(getprop ro.product.model) / $(getprop ro.build.version.release)"
  echo "uname: $(uname -a)"
  echo "clang: $(clang --version | head -1)"
  echo "nproc: $(nproc)"
  echo "-- cpuinfo features --"
  grep -m1 Features /proc/cpuinfo || true
} > "${ENV_FILE}"
cat "${ENV_FILE}"
echo "PROVISION COMPLETE"
