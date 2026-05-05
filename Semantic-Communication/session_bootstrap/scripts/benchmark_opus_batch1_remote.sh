#!/usr/bin/env bash
# Remote benchmark for Opus candidates: variance3 v1.1, variance3 v2, variance1 v1, mean1 v1
# Each benchmark: upload TIR source -> compile on board -> correctness check -> 30-sample benchmark
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HANDWRITTEN="$PROJECT_DIR/session_bootstrap/handwritten"

HOST=100.121.87.73
USER=user
PASS=user
PORT=22
SSH_CMD="bash $SCRIPT_DIR/ssh_with_password.sh --host $HOST --user $USER --pass $PASS --port $PORT"
REMOTE_BASE="/home/user/Downloads/jscc-test/jscc_opus_candidates"

# Remote env setup
REMOTE_PY="/home/user/anaconda3/envs/tvm310_safe/bin/python"
REMOTE_ENV="TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages:/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages"

echo "=== Creating remote directory ==="
$SSH_CMD -- "mkdir -p $REMOTE_BASE"

# Function: run a benchmark for a TIR file with given reference info
run_benchmark() {
    local name="$1"
    local tir_file="$2"
    local func_name="$3"
    local input_shape="$4"      # e.g. "1,24,128,128"
    local output_shape="$5"     # e.g. "1,24,1,1"
    local baseline_us="$6"      # baseline median in us
    local extra_params="$7"     # extra Python dict params (e.g. weight/bias shapes)
    local n_samples="${8:-30}"

    echo ""
    echo "=== Benchmarking: $name ==="

    # Upload TIR source
    local remote_tir="$REMOTE_BASE/${name}_tir.py"
    $SSH_CMD -- "cat > $remote_tir" < "$tir_file"

    # Create and upload benchmark harness
    local remote_bench="$REMOTE_BASE/bench_${name}.py"

    cat > /tmp/bench_opus_${name}.py << BENCHEOF
#!/usr/bin/env python3
"""Benchmark $name"""
import sys, time, json
import numpy as np
import tvm

# Build from the TIR source
mod_name = '_tir_bench_${name}'
with open('${remote_tir}') as f:
    src = f.read()
ns = {"__file__": '${remote_tir}', "__name__": mod_name}
sys.modules[mod_name] = type(sys)('loader')
sys.modules[mod_name].__file__ = '${remote_tir}'
exec(compile(src, '${remote_tir}', 'exec'), ns)
ir_mod = ns.get('Module')
if ir_mod is None:
    print("ERROR: no Module found")
    sys.exit(1)

target = tvm.target.Target({"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4})
with tvm.transform.PassContext(opt_level=3):
    rt = tvm.build(ir_mod, target=target)

# Prepare inputs
np.random.seed(42)
input_shape = tuple([int(x) for x in "${input_shape}".split(",")])
output_shape = tuple([int(x) for x in "${output_shape}".split(",")])
input_np = np.random.randn(*input_shape).astype(np.float32)
output_np = np.zeros(output_shape, dtype=np.float32)

# Reference computation
$input_ref
$extra_params

dev = tvm.cpu(0)
input_tvm = tvm.nd.array(input_np, dev)
output_tvm = tvm.nd.array(output_np, dev)

# Check if function needs extra params
func = rt_mod['$func_name']
import inspect
sig = inspect.signature(func.__wrapped__) if hasattr(func, '__wrapped__') else None

# Warmup
for _ in range(5):
    rt(input_tvm, output_tvm)

# Benchmark
times = []
for _ in range($n_samples):
    t0 = time.perf_counter()
    rt(input_tvm, output_tvm)
    t1 = time.perf_counter()
    times.append((t1 - t0) * 1e6)

result = output_tvm.numpy()
max_diff = float(np.max(np.abs(result - expected)))
rel_diff = max_diff / (float(np.max(np.abs(expected))) + 1e-8)
median_us = float(np.median(times))

output = {
    "operator": "$func_name",
    "version": "$name",
    "correctness": {"max_abs_diff": max_diff, "relative_diff": rel_diff, "passed": max_diff < 1e-3},
    "performance_us": {
        "median": median_us, "mean": float(np.mean(times)),
        "min": float(np.min(times)), "max": float(np.max(times)),
        "std": float(np.std(times)), "samples": len(times)
    },
    "baseline_median_us": $baseline_us,
    "delta_pct": round((median_us - $baseline_us) / $baseline_us * 100, 2),
}
print("JSON_RESULT:" + json.dumps(output))
BENCHEOF

    $SSH_CMD -- "cat > $remote_bench" < /tmp/bench_opus_${name}.py

    echo "=== Running $name benchmark ==="
    $SSH_CMD -- "$REMOTE_ENV $REMOTE_PY $remote_bench 2>&1" 2>&1 | grep -E 'JSON_RESULT:|Error|Traceback' | sed 's/JSON_RESULT://' || echo "NO_RESULT"
}

# variance3 v1.1 (scope-fixed, two-pass baseline was 2736us -> 3562us on board)
# Actually variance3 v1 had -23.18% improvement, let's use the board-proven baseline
run_benchmark \
    "variance3_v1_1" \
    "$HANDWRITTEN/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py" \
    "fused_variance3_add10_tir_sqrt3" \
    "1,24,128,128" \
    "1,24,1,1" \
    3562 \
    "
input_mean = input_np.mean(axis=(2,3), keepdims=True)
centered = input_np - input_mean
variance = (centered ** 2).mean(axis=(2,3), keepdims=True)
expected = np.sqrt(variance + 9.9999997473787516e-06)"

run_benchmark \
    "variance3_v2_welford" \
    "$HANDWRITTEN/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v2_working_copy_tir.py" \
    "fused_variance3_add10_tir_sqrt3" \
    "1,24,128,128" \
    "1,24,1,1" \
    3562 \
    "
input_mean = input_np.mean(axis=(2,3), keepdims=True)
centered = input_np - input_mean
variance = (centered ** 2).mean(axis=(2,3), keepdims=True)
expected = np.sqrt(variance + 9.9999997473787516e-06)"

run_benchmark \
    "variance1_v1_welford" \
    "$HANDWRITTEN/fused_variance1_add3_tir_sqrt1/fused_variance1_add3_tir_sqrt1_scheduled_form_candidate_v1_working_copy_tir.py" \
    "fused_variance1_add3_tir_sqrt1" \
    "1,96,32,32" \
    "1,96,1,1" \
    5000 \
    "
input_mean = input_np.mean(axis=(2,3), keepdims=True)
centered = input_np - input_mean
variance = (centered ** 2).mean(axis=(2,3), keepdims=True)
expected = np.sqrt(variance + 9.9999997473787516e-06)"

echo ""
echo "=== All benchmarks complete ==="
