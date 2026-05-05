#!/usr/bin/env bash
# Run all Opus candidate benchmarks on Phytium Pi, one at a time, collect results.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH="bash $SCRIPT_DIR/ssh_with_password.sh --host 100.121.87.73 --user user --pass user --"
REMOTE="/home/user/Downloads/jscc-test/jscc_opus_candidates"
PY="/home/user/anaconda3/envs/tvm310_safe/bin/python"
ENV="TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages:/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages"
RESULTS="/tmp/opus_bench_results.jsonl"

> "$RESULTS"

run_bench() {
    local so="$1" func="$2" ishape="$3" oshape="$4" label="$5" baseline="$6"
    echo "=== $label ==="
    $SSH -- "$ENV $PY $REMOTE/bench_so_module.py $REMOTE/$so $func $ishape $oshape $label $baseline 2>/dev/null" 2>&1 | sed 's/^JSON_RESULT://' >> "$RESULTS"
    # Print summary from last line
    tail -1 "$RESULTS" | python3 -c "
import sys,json
d=json.load(sys.stdin)
med=d['performance_us']['median']
delta=d.get('delta_pct','N/A')
ok=d['correctness']['passed']
print(f'  median={med:.0f}us  delta={delta}%  correct={ok}')
" 2>/dev/null || echo "  FAILED"
}

run_bench "variance3_v1_1.so"          "fused_variance3_add10_tir_sqrt3"             "1,24,128,128"  "1,24,1,1"       "v1.1_scope_fixed" 3562
run_bench "variance3_v2_welford.so"    "fused_variance3_add10_tir_sqrt3"             "1,24,128,128"  "1,24,1,1"       "v2_welford"       3562
run_bench "variance1_v1_welford.so"    "fused_variance1_add3_tir_sqrt1"              "1,96,32,32"    "1,96,1,1"       "v1_welford"       5000
run_bench "variance4_v20_welford.so"   "fused_variance4_add13_tir_sqrt4"             "1,12,256,256"  "1,12,1,1"       "v20_welford"      2700
run_bench "mean4_v4_fused.so"          "fused_mean4_subtract4_divide4_multiply4_add14_relu3" "1,12,256,256" "1,12,256,256" "v4_fused"     5000

echo ""
echo "=== Full results saved to $RESULTS ==="
