#!/usr/bin/env bash
# Extract baseline TIR for a specific operator from the trusted current model on Phytium Pi.
# Usage: bash extract_operator_tir_remote.sh <operator_name>
set -euo pipefail

OPERATOR_NAME="${1:?Usage: $0 <operator_name>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load inference env
set -a
source "$PROJECT_DIR/session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
set +a

HOST="${REMOTE_HOST}"
USER="${REMOTE_USER}"
PASS="${REMOTE_PASS}"
PORT="${REMOTE_SSH_PORT:-22}"

REMOTE_PYTHON="${REMOTE_TVM_PYTHON}"
ONNX_MODEL="/home/user/Downloads/jscc-test/简化版latent/../temp_simp.onnx"

echo "Extracting TIR for operator: $OPERATOR_NAME"

# Create a Python script to extract TIR
EXTRACT_SCRIPT=$(cat << 'PYEOF'
import sys
import json

operator_name = sys.argv[1]

import tvm
from tvm import relay
from tvm.contrib import graph_executor
import numpy as np

# Load ONNX model
import onnx
onnx_model = onnx.load("/home/user/Downloads/temp_simp.onnx")

# Import to relay
target_str = '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'
target = tvm.target.Target(json.loads(target_str))

mod, params = relay.frontend.from_onnx(onnx_model, shape=None, freeze_params=True)

# Apply default passes
mod = relay.transform.InferType()(mod)
mod = relay.transform.FoldConstant()(mod)
mod = relay.transform.FuseOps(fuse_opt_level=0)(mod)
mod = relay.transform.InferType()(mod)

# Find the operator
found = False
for gv in mod.functions:
    func = mod[gv]
    name_str = str(gv.name_hint)
    if operator_name in name_str or name_str.endswith(operator_name):
        print(f"FOUND: {name_str}", file=sys.stderr)
        # Print TIR
        print(f"# Baseline TIR for {operator_name}")
        print(f"# Extracted from: {name_str}")
        print(str(func))
        found = True
        break

if not found:
    # List all functions for debugging
    print("ERROR: operator not found. Available functions:", file=sys.stderr)
    for gv in mod.functions:
        print(f"  {gv.name_hint}", file=sys.stderr)
    sys.exit(1)
PYEOF
)

bash "$SCRIPT_DIR/ssh_with_password.sh" \
    --host "$HOST" --user "$USER" --pass "$PASS" --port "$PORT" -- \
    "$REMOTE_PYTHON -c $(printf '%q' "$EXTRACT_SCRIPT") $OPERATOR_NAME" 2>&1
