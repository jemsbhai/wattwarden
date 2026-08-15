#!/data/data/com.termux/files/usr/bin/bash
# EXP-003b battery sampler: logs both telemetry sources at ~1 Hz, raw.
# Unit inference happens in analysis, not here; this script only records.
# Usage: bash exp003b_sampler.sh <outfile.csv>   (runs until killed)
set -u

OUT="${1:?usage: exp003b_sampler.sh <outfile.csv>}"
echo "epoch_ms,api_current,api_voltage_mV,api_temp_C,api_status,api_pct,sys_current_now,sys_voltage_now" > "$OUT"

SYS_I="/sys/class/power_supply/battery/current_now"
SYS_V="/sys/class/power_supply/battery/voltage_now"

while true; do
  TS=$(( $(date +%s%N) / 1000000 ))
  API_JSON="$(termux-battery-status 2>/dev/null || echo '{}')"
  API_I=$(printf '%s' "$API_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('current',''))" 2>/dev/null)
  API_V=$(printf '%s' "$API_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('voltage',''))" 2>/dev/null)
  API_T=$(printf '%s' "$API_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('temperature',''))" 2>/dev/null)
  API_S=$(printf '%s' "$API_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('status',''))" 2>/dev/null)
  API_P=$(printf '%s' "$API_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('percentage',''))" 2>/dev/null)
  SYS_IV="$(cat "$SYS_I" 2>/dev/null || echo '')"
  SYS_VV="$(cat "$SYS_V" 2>/dev/null || echo '')"
  echo "${TS},${API_I},${API_V},${API_T},${API_S},${API_P},${SYS_IV},${SYS_VV}" >> "$OUT"
  sleep 1
done
