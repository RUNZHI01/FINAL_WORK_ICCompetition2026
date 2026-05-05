#!/usr/bin/env python3
"""
Integrate Opus candidate handwritten TIR into full model .so.

Uses the same build path as rpc_tune.py: ONNX → Relax → compile_relax.
Replaces target PrimFuncs in the Relax IRModule before compile_relax processes them.

Safety:
- NEVER modifies Trusted Current
- All output goes to timestamped independent directory
- Trusted Current SHA verified before and after
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ONNX_PATH = "/home/tianxing/TVM_LAST/finalWork/服务端/jscc-test/jscc/model.onnx"
INPUT_NAME = "input"
INPUT_SHAPE = [1, 32, 32, 32]
INPUT_DTYPE = {"input": "float32"}

TRUSTED_CURRENT_SO = (
    PROJECT_ROOT
    / "session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so"
)
TRUSTED_CURRENT_SHA = "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"

DATABASE_DIR = (
    PROJECT_ROOT
    / "session_bootstrap/tmp/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315/tuning_logs"
)

TARGET_STR = '{"kind":"llvm","mtriple":"aarch64-linux-gnu","mcpu":"cortex-a72","mattr":["+neon"],"num-cores":4}'

HANDWRITTEN = PROJECT_ROOT / "session_bootstrap/handwritten"

ALL_CANDIDATES = {
    "fused_variance3_add10_tir_sqrt3": HANDWRITTEN / "fused_variance3_add10_tir_sqrt3" / "fused_variance3_add10_tir_sqrt3_scheduled_form_candidate_v1_working_copy_tir.py",
    "fused_variance1_add3_tir_sqrt1": HANDWRITTEN / "fused_variance1_add3_tir_sqrt1" / "fused_variance1_add3_tir_sqrt1_scheduled_form_candidate_v1_working_copy_tir.py",
    "fused_mean4_subtract4_divide4_multiply4_add14_relu3": HANDWRITTEN / "fused_mean4_subtract4_divide4_multiply4_add14_relu3" / "fused_mean4_subtract4_divide4_multiply4_add14_relu3_scheduled_form_candidate_v4_working_copy_tir.py",
}

CANDIDATE_PRESETS = {
    # Historical three-op probe that includes the dropped variance1 branch.
    "legacy_three_op": [
        "fused_variance3_add10_tir_sqrt3",
        "fused_variance1_add3_tir_sqrt1",
        "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
    ],
    # This matches the repo's checked handwritten final route from the Opus report:
    # keep variance3 scope-fix + mean4 fused loop, drop variance1.
    "opus_final_v3_mean4": [
        "fused_variance3_add10_tir_sqrt3",
        "fused_mean4_subtract4_divide4_multiply4_add14_relu3",
    ],
}


def resolve_candidate_override(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            "candidate override must be formatted as operator_name=path/to/tir.py"
        )
    operator_name, raw_path = raw.split("=", 1)
    operator_name = operator_name.strip()
    raw_path = raw_path.strip()
    if not operator_name or not raw_path:
        raise argparse.ArgumentTypeError(
            "candidate override must include both operator name and path"
        )
    path = Path(raw_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return operator_name, path


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_tir_module(tir_path: Path, operator_name: str):
    """Load @I.ir_module TIR file using exec+sys.modules hack."""
    mod_name = f"_integrate_{operator_name}"
    with open(tir_path) as f:
        src = f.read()
    ns = {"__file__": str(tir_path.resolve()), "__name__": mod_name}
    sys.modules[mod_name] = type(sys)("tir_loader")
    sys.modules[mod_name].__file__ = str(tir_path.resolve())
    exec(compile(src, str(tir_path), "exec"), ns)
    ir_mod = ns.get("Module")
    if ir_mod is None:
        raise RuntimeError(f"No 'Module' found in {tir_path}")
    return ir_mod


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--preset",
        choices=sorted(CANDIDATE_PRESETS),
        default="legacy_three_op",
        help="Select which handwritten operator bundle to integrate.",
    )
    parser.add_argument(
        "--candidate-override",
        action="append",
        default=[],
        metavar="OPERATOR=PATH",
        help=(
            "Temporarily override a preset candidate TIR path without changing "
            "the checked-in default bundle."
        ),
    )
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    overrides: dict[str, Path] = {}
    for raw in args.candidate_override:
        operator_name, path = resolve_candidate_override(raw)
        if operator_name not in ALL_CANDIDATES:
            raise SystemExit(f"ERROR: unknown candidate override operator: {operator_name}")
        overrides[operator_name] = path

    # Safety check
    assert TRUSTED_CURRENT_SO.exists(), f"Trusted Current not found"
    assert file_sha256(TRUSTED_CURRENT_SO) == TRUSTED_CURRENT_SHA, "SHA mismatch"
    print(f"✓ Trusted Current verified: {TRUSTED_CURRENT_SHA[:16]}...")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = (args.output_dir or PROJECT_ROOT / "session_bootstrap/tmp" / f"opus_integrated_{ts}").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output dir: {output_dir}")

    # Setup TVM
    sys.path.insert(0, str(PROJECT_ROOT / "tvm-src/python"))
    os.environ["TVM_LIBRARY_PATH"] = str(PROJECT_ROOT / "tvm-src/build")
    os.environ["LD_LIBRARY_PATH"] = str(PROJECT_ROOT / "tvm-src/build")

    import tvm
    from tvm.s_tir.meta_schedule.relax_integration import compile_relax
    from tvm.s_tir.meta_schedule.database import JSONDatabase

    sys.path.insert(0, str(PROJECT_ROOT / "session_bootstrap/scripts"))
    from relax_ms_utils import load_onnx_to_relax

    # Load ONNX → Relax
    print("Loading ONNX model...")
    mod = load_onnx_to_relax(ONNX_PATH, INPUT_NAME, INPUT_SHAPE, INPUT_DTYPE)

    # Preprocess to expose PrimFuncs as GlobalVars
    print("Preprocessing (LegalizeOps → FuseOps → FuseTIR)...")
    from relax_ms_utils import preprocess_for_meta_schedule
    mod = preprocess_for_meta_schedule(mod)

    # Replace PrimFuncs
    selected_names = CANDIDATE_PRESETS[args.preset]
    candidates = {
        name: overrides.get(name, ALL_CANDIDATES[name]) for name in selected_names
    }
    replaced = []
    for op_name, tir_path in candidates.items():
        if not tir_path.exists():
            print(f"  SKIP {op_name}: file not found")
            continue
        try:
            new_tir_mod = load_tir_module(tir_path, op_name)
            new_gv = new_tir_mod.get_global_vars()[0]
            new_func = new_tir_mod[new_gv]

            # Find the matching GlobalVar in the Relax module
            # The Relax module may use different GV names; try exact match first
            target_gv = None
            for gv in mod.get_global_vars():
                if str(gv) == op_name or gv.name_hint == op_name:
                    target_gv = gv
                    break

            if target_gv is not None:
                # Replace the PrimFunc in the module's global map
                mod.update_func(target_gv, new_func)
                replaced.append(op_name)
                print(f"  ✓ Replaced {op_name}")
            else:
                print(f"  WARNING: {op_name} not found in Relax module globals")
                # Print available globals for debugging
                gvs = [str(gv) for gv in mod.get_global_vars()]
                matches = [gv for gv in gvs if 'variance' in gv.lower() or 'mean' in gv.lower()]
                print(f"    Similar globals: {matches[:5]}")
        except Exception as e:
            print(f"  ERROR {op_name}: {e}")

    print(f"✓ Replaced {len(replaced)}/{len(candidates)}: {replaced}")

    if args.skip_build:
        print("SKIP_BUILD requested, exiting")
        return

    # Build
    target = tvm.target.Target(json.loads(TARGET_STR))
    db = JSONDatabase(
        path_workload=str(DATABASE_DIR / "database_workload.json"),
        path_tuning_record=str(DATABASE_DIR / "database_tuning_record.json"),
    )
    print(f"Compiling with compile_relax (target={target})...")
    with tvm.transform.PassContext(opt_level=3):
        ex = compile_relax(
            database=db,
            mod=mod,
            target=target,
            params={},
            enable_warning=False,
        )

    so_path = output_dir / "optimized_model.so"
    ex.export_library(str(so_path))
    sha = file_sha256(so_path)
    size = so_path.stat().st_size

    print(f"✓ Built: {so_path}")
    print(f"  SHA-256: {sha}")
    print(f"  Size: {size:,} bytes")

    # Safety: verify Trusted Current unchanged
    assert file_sha256(TRUSTED_CURRENT_SO) == TRUSTED_CURRENT_SHA, "Trusted Current was modified!"
    print(f"✓ Trusted Current unchanged")

    # Report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "built",
        "output_dir": str(output_dir),
        "artifact_path": str(so_path),
        "artifact_sha256": sha,
        "artifact_size": size,
        "trusted_current_sha256": TRUSTED_CURRENT_SHA,
        "trusted_current_verified": True,
        "preset": args.preset,
        "candidate_overrides": {name: str(path) for name, path in overrides.items()},
        "replaced_operators": replaced,
        "skipped_operators": [op for op in candidates if op not in replaced],
        "next_steps": [
            "1. Upload .so to board",
            "2. Run correctness check (300 images, max_abs_diff < 1e-3)",
            "3. Run payload + e2e benchmark",
            "4. If ALL pass → generate upgrade report → human approval",
        ],
    }
    (output_dir / "integration_report.json").write_text(json.dumps(report, indent=2))
    print(f"✓ Report: {output_dir / 'integration_report.json'}")


if __name__ == "__main__":
    main()
