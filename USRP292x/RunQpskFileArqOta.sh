#!/usr/bin/env bash
set -euo pipefail

# File-level selective ARQ smoke:
#   round0 sends all chunks
#   later rounds send only missing chunks reported by decode_summary.json / merge_summary.json
#
# In the final system, the missing list should travel over Tailscale/control plane.
# This local orchestrator keeps the same file interface so the RF data plane can
# be tested before wiring it into the control service.

RUN_ID="${RUN_ID:-arq_$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="${RUN_DIR:-USRP292x/qpsk_arq_runs/${RUN_ID}}"
INPUT="${INPUT:-USRP292x/payloads/source_latent_wire_blob.bin}"
MAX_ARQ_ROUNDS="${MAX_ARQ_ROUNDS:-2}"

mkdir -p "${RUN_DIR}"

SUMMARY_ARGS=()
DECODED_ARGS=()
missing_csv=""
merge_status=2

merge_rounds() {
    local tag="$1"
    local merge_summary="${RUN_DIR}/merge_${tag}.json"
    local merge_log="${RUN_DIR}/merge_${tag}.log"
    local merged_bin="${RUN_DIR}/merged_${tag}.bin"

    set +e
    python3 USRP292x/QpskFileLink.py merge \
        --reference "${INPUT}" \
        --out-bin "${merged_bin}" \
        --summary-out "${merge_summary}" \
        "${SUMMARY_ARGS[@]}" \
        "${DECODED_ARGS[@]}" | tee "${merge_log}"
    merge_status="${PIPESTATUS[0]}"
    set -e

    missing_csv="$(python3 - "${merge_summary}" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding='utf-8'))
print(','.join(str(item) for item in summary['missing_chunks']))
PY
)"
    echo "merge_status=${merge_status}"
    echo "missing_csv=${missing_csv}"
}

run_round() {
    local round="$1"
    local only_chunks="$2"
    local round_dir="${RUN_DIR}/round${round}"

    echo "round=${round}"
    echo "only_chunks=${only_chunks:-ALL}"

    set +e
    RUN_DIR="${round_dir}" \
    INPUT="${INPUT}" \
    ONLY_CHUNKS="${only_chunks}" \
    ALLOW_DECODE_FAIL=1 \
    bash USRP292x/RunQpskFileOta.sh
    local round_status="$?"
    set -e
    echo "round_status=${round_status}"

    SUMMARY_ARGS+=(--summary-json "${round_dir}/decode_summary.json")
    DECODED_ARGS+=(--decoded-bin "${round_dir}/decoded_wire_blob.bin")
    merge_rounds "round${round}"
}

run_round 0 ""

round=1
while [[ -n "${missing_csv}" && "${round}" -le "${MAX_ARQ_ROUNDS}" ]]; do
    run_round "${round}" "${missing_csv}"
    round=$((round + 1))
done

if [[ "${merge_status}" == "0" ]]; then
    echo "arq_result=PASS"
    exit 0
fi

echo "arq_result=FAIL"
exit "${merge_status}"
