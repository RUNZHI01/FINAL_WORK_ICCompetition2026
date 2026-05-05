#!/usr/bin/env bash
# Build all Opus candidate TIR files into .so artifacts.
set -euo pipefail

TVMSRC="/home/tianxing/tvm-src"
TVM_PYTHON="/home/tianxing/.venvs/tvm-ms/bin/python"
PROJECT="/home/tianxing/tvm_metaschedule_execution_project"
OUTDIR="$PROJECT/session_bootstrap/tmp/opus_candidates_20260403"
HANDWRITTEN="$PROJECT/session_bootstrap/handwritten"

mkdir -p "$OUTDIR"

build_tir() {
    local name="$1"
    local tir_file="$2"
    local output="$3"
    echo "=== Building $name ==="
    "$TVM_PYTHON" <<PYEOF
import sys, os
sys.path.insert(0, '$TVMSRC/python')
os.environ['TVM_LIBRARY_PATH'] = '$TVMSRC/build'
os.environ['LD_LIBRARY_PATH'] = '$TVMSRC/build'

import tvm

tir_path = '$tir_file'
output_path = '$output'

# @I.ir_module needs: (1) __file__ in globals, (2) sys.modules[mod.__module__] exists
# We register the module under a unique name.
mod_name = '_tir_build_' + os.path.basename(tir_path).replace('.py','').replace('-','_')

with open(tir_path) as f:
    src = f.read()

ns = {"__file__": os.path.abspath(tir_path), "__name__": mod_name}
# Register in sys.modules BEFORE exec so @I.ir_module can find it
sys.modules[mod_name] = type(sys)('tir_loader')
sys.modules[mod_name].__file__ = os.path.abspath(tir_path)
exec(compile(src, tir_path, 'exec'), ns)

ir_mod = ns.get('Module')
if ir_mod is None:
    print(f"ERROR: No 'Module' found in {tir_path}")
    sys.exit(1)

target = tvm.target.Target({"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4})

with tvm.transform.PassContext(opt_level=3):
    rt = tvm.build(ir_mod, target=target)

os.makedirs(os.path.dirname(output_path), exist_ok=True)
rt.export_library(output_path)
print(f"  Exported: {output_path} ({os.path.getsize(output_path)} bytes)")
print("BUILD_SUCCESS")
PYEOF
    echo "=== $name: done ==="
}

build_tir "variance3_v1.1" \
    "$HANDWRITTEN/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py" \
    "$OUTDIR/variance3_v1_1.so"

build_tir "variance3_v2_welford" \
    "$HANDWRITTEN/fused_variance3_add10_tir_sqrt3/fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v2_working_copy_tir.py" \
    "$OUTDIR/variance3_v2_welford.so"

build_tir "variance1_v1_welford" \
    "$HANDWRITTEN/fused_variance1_add3_tir_sqrt1/fused_variance1_add3_tir_sqrt1_scheduled_form_candidate_v1_working_copy_tir.py" \
    "$OUTDIR/variance1_v1_welford.so"

build_tir "mean1_v1" \
    "$HANDWRITTEN/fused_mean1_subtract1_divide1_multiply1_add4/fused_mean1_subtract1_divide1_multiply1_add4_scheduled_form_candidate_v1_working_copy_tir.py" \
    "$OUTDIR/mean1_v1.so"

echo ""
echo "=== All builds complete ==="
ls -la "$OUTDIR/"
