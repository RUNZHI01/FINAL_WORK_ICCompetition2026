#!/usr/bin/env bash
# Upload benchmark scripts to Phytium Pi and run them sequentially.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST=100.121.87.73
USER=user
PASS=user
PORT=22
SSH="bash $SCRIPT_DIR/ssh_with_password.sh --host $HOST --user $USER --pass $PASS --port $PORT"
REMOTE_DIR="/home/user/Downloads/jscc-test/jscc_opus_candidates"
REMOTE_PY="/home/user/anaconda3/envs/tvm310_safe/bin/python"
REMOTE_ENV="TVM_FFI_DISABLE_TORCH_C_DLPACK=1 LD_LIBRARY_PATH=/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:/home/user/tvm_samegen_safe_20260309/build TVM_LIBRARY_PATH=/home/user/tvm_samegen_safe_20260309/build PYTHONPATH=/home/user/tvm_samegen_20260307/python:/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages:/home/user/anaconda3/envs/myenv/lib/python3.10/site-packages"

echo "=== Creating remote directory ==="
$SSH -- "mkdir -p $REMOTE_DIR"

BENCHMARKS=(
    "bench_variance3_v1_1_remote.py:variance3_v1.1"
    "bench_variance3_v2_welford_remote.py:variance3_v2_welford"
    "bench_variance1_v1_welford_remote.py:variance1_v1_welford"
)

echo ""
echo '{"opus_batch1_benchmarks":[' > /tmp/opus_batch1_results.json
FIRST=true

for item in "${BENCHMARKS[@]}"; do
    IFS=':' read -r script label <<< "$item"
    local_path="$SCRIPT_DIR/$script"
    remote_path="$REMOTE_DIR/$script"
    
    echo "=== Uploading $label ==="
    $SSH -- "cat > $remote_path" < "$local_path"
    
    echo "=== Running $label benchmark ==="
    result=$($SSH -- "$REMOTE_ENV $REMOTE_PY $remote_path 2>&1" 2>&1 | tail -1)
    echo "  Result: $result"
    
    if $FIRST; then FIRST=false; else echo "," >> /tmp/opus_batch1_results.json; fi
    echo "  $result" >> /tmp/opus_batch1_results.json
done

echo ']}' >> /tmp/opus_batch1_results.json
echo ""
echo "=== All benchmarks complete ==="
echo "Results saved to /tmp/opus_batch1_results.json"
cat /tmp/opus_batch1_results.json
