#!/usr/bin/env python3
"""Diagnose the transpose1 h_1 overlap boundary locally.

This helper is local-only. It makes no performance claim.

It answers three narrow questions for
`fused_conv2d_transpose1_add9` on top of the checked-in `v7` working copy:

1. What semantic edit did the dropped `v8` follow-up actually make?
2. Do the staged boundary rows around the `h_1` transition match exactly at the
   row-value level?
3. Does that row-level exactness justify producer-only carry, consumer carry, or
   does the scheduled TIR still need a sharper boundary condition?
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import linecache
import marshal
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPERATOR_NAME = "fused_conv2d_transpose1_add9"
HANDWRITTEN_DIR = PROJECT_ROOT / "session_bootstrap" / "handwritten" / OPERATOR_NAME
V7_TIR_PATH = HANDWRITTEN_DIR / f"{OPERATOR_NAME}_scheduled_form_candidate_v7_working_copy_tir.py"
V8_PYC_PATH = (
    HANDWRITTEN_DIR
    / "__pycache__"
    / f"{OPERATOR_NAME}_scheduled_form_candidate_v8_working_copy_tir.cpython-312.pyc"
)
PRESERVED_V8_VS_V7_REPORT = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "tmp"
    / "transpose1_v8_vs_v7_correctness_20260402"
    / "check_report.json"
)
CHECK_SCRIPT_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose the transpose1 h_1 overlap boundary from local artifacts."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260331,
        help="Frozen RNG seed used by the local correctness helper.",
    )
    parser.add_argument(
        "--target",
        default="llvm",
        help="Local target for the v7 vs reconstructed-v8 build probe.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output JSON path.",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"ERROR: {label} not found: {resolved}")
    return resolved


def repo_native(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        return str(resolved)
    return f"./{relative.as_posix()}"


def load_pyc_top_level(path: Path) -> types.CodeType:
    with require_file(path, "v8 pyc").open("rb") as infile:
        infile.read(16)
        return marshal.load(infile)


def find_transpose1_func_code(top_level: types.CodeType) -> types.CodeType:
    for obj in top_level.co_consts:
        if isinstance(obj, types.CodeType) and obj.co_name == "Module":
            for sub in obj.co_consts:
                if isinstance(sub, types.CodeType) and sub.co_name == OPERATOR_NAME:
                    return sub
    raise SystemExit("ERROR: unable to locate transpose1 function code object")


def normalized_instruction_stream(code: types.CodeType) -> list[str]:
    import dis

    normalized: list[str] = []
    for instr in dis.Bytecode(code):
        if instr.opname in {"RESUME", "CACHE", "EXTENDED_ARG", "NOP", "PUSH_NULL", "COPY", "SWAP"}:
            continue
        normalized.append(f"{instr.opname} {instr.argrepr}".rstrip())
    return normalized


def reconstruct_v8_source_from_v7(v7_text: str) -> str:
    needle = """\
                                        and b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16)
                                        * T.int64(8)
                                        + ax2_ax3_fused % T.int64(10)
                                        < T.int64(128)
                                    )
"""
    replacement = """\
                                        and b_0_c_0_h_0_w_0_fused_fused_fused % T.int64(16)
                                        * T.int64(8)
                                        + ax2_ax3_fused % T.int64(10)
                                        < T.int64(128)
                                        and (h_1 == T.int64(0) or T.int64(2) <= ax2)
                                    )
"""
    if needle not in v7_text:
        raise SystemExit("ERROR: failed to find the v7 data_dilate boundary guard")
    return v7_text.replace(needle, replacement, 1)


def compile_source_text(source_text: str, filename: str) -> types.CodeType:
    return compile(source_text, filename, "exec")


def load_ir_module_from_source_text(
    source_text: str,
    *,
    module_name: str,
    filename: str,
):
    linecache.cache[filename] = (
        len(source_text),
        None,
        [line + "\n" for line in source_text.splitlines()],
        filename,
    )
    module = types.ModuleType(module_name)
    module.__file__ = filename
    sys.modules[module_name] = module
    try:
        exec(compile(source_text, filename, "exec"), module.__dict__)
    finally:
        sys.modules.pop(module_name, None)
    ir_module = getattr(module, "Module", None)
    if ir_module is None:
        raise SystemExit("ERROR: reconstructed source did not expose `Module`")
    return ir_module


def import_check_helper():
    sys.path.insert(0, str(CHECK_SCRIPT_DIR.resolve()))
    try:
        import check_transpose1_scheduled_reference_vs_working_copy as helper  # type: ignore
    finally:
        sys.path.pop(0)
    return helper


def materialize_data_dilate_window(
    lv318: np.ndarray,
    *,
    h_base: int,
    w_base: int,
    h1: int,
) -> tuple[np.ndarray, np.ndarray]:
    window = np.zeros((48, 34, 10), dtype="float32")
    valid = np.zeros((34, 10), dtype=bool)
    for ax2 in range(34):
        row_guard = 1 <= h_base + h1 * 32 + ax2 < 128
        global_row = h_base + h1 * 32 + ax2 - 1
        for ax3 in range(10):
            col_guard = 1 <= w_base + ax3 < 128
            valid[ax2, ax3] = row_guard and col_guard
            if not valid[ax2, ax3]:
                continue
            global_col = w_base + ax3 - 1
            if global_row % 2 == 0 and global_col % 2 == 0:
                window[:, ax2, ax3] = lv318[0, :, global_row // 2, global_col // 2]
    return window, valid


def materialize_data_pad_window(
    data_dilate_window: np.ndarray,
    *,
    h_base: int,
    w_base: int,
    h1: int,
) -> tuple[np.ndarray, np.ndarray]:
    window = np.zeros_like(data_dilate_window)
    valid = np.zeros((34, 10), dtype=bool)
    for ax2 in range(34):
        global_row = h_base + h1 * 32 + ax2
        for ax3 in range(10):
            global_col = w_base + ax3
            valid[ax2, ax3] = 1 <= global_row < 128 and 1 <= global_col < 128
            if valid[ax2, ax3]:
                window[:, ax2, ax3] = data_dilate_window[:, ax2, ax3]
    return window, valid


def masked_max_abs_diff(lhs: np.ndarray, rhs: np.ndarray, mask: np.ndarray) -> float:
    if not bool(mask.any()):
        return 0.0
    diff = np.abs(lhs - rhs)
    masked = diff[:, mask]
    return float(masked.max(initial=0.0))


def analyze_boundary_rows(lv318: np.ndarray) -> dict[str, Any]:
    h_bases = (0, 64)
    w_bases = tuple(range(0, 128, 8))
    cases: list[dict[str, Any]] = []
    dilate_boundary_max_abs_diff = 0.0
    pad_boundary_max_abs_diff = 0.0
    producer_only_pad_rewrite_max_abs_diff = 0.0
    consumer_pad_carry_max_abs_diff = 0.0

    for h_base in h_bases:
        for w_base in w_bases:
            prev_dilate, prev_dilate_valid = materialize_data_dilate_window(
                lv318, h_base=h_base, w_base=w_base, h1=0
            )
            curr_dilate, curr_dilate_valid = materialize_data_dilate_window(
                lv318, h_base=h_base, w_base=w_base, h1=1
            )
            prev_pad, prev_pad_valid = materialize_data_pad_window(
                prev_dilate, h_base=h_base, w_base=w_base, h1=0
            )
            curr_pad, curr_pad_valid = materialize_data_pad_window(
                curr_dilate, h_base=h_base, w_base=w_base, h1=1
            )

            boundary_prev_dilate = prev_dilate[:, 32:34, :]
            boundary_curr_dilate = curr_dilate[:, 0:2, :]
            boundary_prev_dilate_valid = prev_dilate_valid[32:34, :]
            boundary_curr_dilate_valid = curr_dilate_valid[0:2, :]
            dilate_mask = boundary_prev_dilate_valid & boundary_curr_dilate_valid
            dilate_boundary_diff = masked_max_abs_diff(
                boundary_prev_dilate, boundary_curr_dilate, dilate_mask
            )
            dilate_boundary_max_abs_diff = max(dilate_boundary_max_abs_diff, dilate_boundary_diff)

            carried_dilate = curr_dilate.copy()
            carried_dilate[:, 0:2, :] = boundary_prev_dilate
            producer_dilate_rewrite_diff = masked_max_abs_diff(
                carried_dilate[:, 0:2, :],
                curr_dilate[:, 0:2, :],
                boundary_curr_dilate_valid,
            )

            carried_from_dilate_pad, carried_from_dilate_pad_valid = materialize_data_pad_window(
                carried_dilate, h_base=h_base, w_base=w_base, h1=1
            )

            boundary_prev_pad = prev_pad[:, 32:34, :]
            boundary_curr_pad = curr_pad[:, 0:2, :]
            boundary_prev_pad_valid = prev_pad_valid[32:34, :]
            boundary_curr_pad_valid = curr_pad_valid[0:2, :]
            pad_mask = boundary_prev_pad_valid & boundary_curr_pad_valid
            pad_boundary_diff = masked_max_abs_diff(boundary_prev_pad, boundary_curr_pad, pad_mask)
            pad_boundary_max_abs_diff = max(pad_boundary_max_abs_diff, pad_boundary_diff)

            producer_only_pad_diff = masked_max_abs_diff(
                carried_from_dilate_pad,
                curr_pad,
                carried_from_dilate_pad_valid & curr_pad_valid,
            )
            producer_only_pad_rewrite_max_abs_diff = max(
                producer_only_pad_rewrite_max_abs_diff, producer_only_pad_diff
            )

            consumer_carried_pad = curr_pad.copy()
            consumer_carried_pad[:, 0:2, :] = boundary_prev_pad
            consumer_pad_diff = masked_max_abs_diff(
                consumer_carried_pad,
                curr_pad,
                curr_pad_valid,
            )
            consumer_pad_carry_max_abs_diff = max(
                consumer_pad_carry_max_abs_diff, consumer_pad_diff
            )

            cases.append(
                {
                    "h_base": h_base,
                    "w_base": w_base,
                    "data_dilate_boundary_rows": {
                        "previous_stripe_local_rows": [32, 33],
                        "current_stripe_local_rows": [0, 1],
                        "global_rows": [h_base + 31, h_base + 32],
                        "max_abs_diff": dilate_boundary_diff,
                        "producer_only_row_carry_max_abs_diff": producer_dilate_rewrite_diff,
                    },
                    "data_pad_boundary_rows": {
                        "previous_stripe_local_rows": [32, 33],
                        "current_stripe_local_rows": [0, 1],
                        "global_rows": [h_base + 32, h_base + 33],
                        "max_abs_diff": pad_boundary_diff,
                        "producer_only_pad_rewrite_max_abs_diff": producer_only_pad_diff,
                        "consumer_pad_row_carry_max_abs_diff": consumer_pad_diff,
                    },
                }
            )

    return {
        "h_bases": list(h_bases),
        "w_bases": list(w_bases),
        "max_abs_diff": {
            "data_dilate_boundary_rows": dilate_boundary_max_abs_diff,
            "data_pad_boundary_rows": pad_boundary_max_abs_diff,
            "producer_only_pad_rewrite": producer_only_pad_rewrite_max_abs_diff,
            "consumer_pad_row_carry": consumer_pad_carry_max_abs_diff,
        },
        "exactness": {
            "data_dilate_boundary_rows_exact": dilate_boundary_max_abs_diff == 0.0,
            "data_pad_boundary_rows_exact": pad_boundary_max_abs_diff == 0.0,
            "producer_only_pad_rewrite_exact": producer_only_pad_rewrite_max_abs_diff == 0.0,
            "consumer_pad_row_carry_exact": consumer_pad_carry_max_abs_diff == 0.0,
        },
        "cases": cases,
    }


def summarize_v8_reconstruction(v7_text: str) -> dict[str, Any]:
    reconstructed_text = reconstruct_v8_source_from_v7(v7_text)
    reconstructed_sha256 = hashlib.sha256(reconstructed_text.encode("utf-8")).hexdigest()
    pyc_func = find_transpose1_func_code(load_pyc_top_level(V8_PYC_PATH))
    reconstructed_func = find_transpose1_func_code(
        compile_source_text(reconstructed_text, "<transpose1_v8_reconstructed>")
    )
    stream_match = normalized_instruction_stream(pyc_func) == normalized_instruction_stream(
        reconstructed_func
    )
    diff_lines = list(
        difflib.unified_diff(
            normalized_instruction_stream(
                find_transpose1_func_code(compile_source_text(v7_text, "<v7>"))
            ),
            normalized_instruction_stream(pyc_func),
            fromfile="v7_norm",
            tofile="v8_norm",
            n=4,
        )
    )
    return {
        "reconstructed_sha256": reconstructed_sha256,
        "normalized_instruction_stream_match_pyc": stream_match,
        "normalized_diff_excerpt": diff_lines[:40],
        "semantic_change_summary": (
            "The dropped v8 follow-up added only one producer-side boundary guard "
            "inside data_dilate: when h_1 == 1, skip ax2 rows 0 and 1 so the "
            "global overlap rows 31/32 are carried from the previous stripe."
        ),
        "reconstructed_text": reconstructed_text,
    }


def run_current_local_probe(
    reconstructed_text: str,
    *,
    seed: int,
    target: str,
) -> dict[str, Any]:
    chk = import_check_helper()
    config = chk.get_operator_config(OPERATOR_NAME)
    inputs = chk.make_inputs(seed, input_specs=config["input_specs"])
    v7_module = chk.load_ir_module(V7_TIR_PATH, operator_name=OPERATOR_NAME)
    reconstructed_module = load_ir_module_from_source_text(
        reconstructed_text,
        module_name="transpose1_v8_reconstructed_runtime_probe",
        filename=str(Path("/tmp/transpose1_v8_reconstructed_runtime_probe.py").resolve()),
    )

    v7_output = chk.run_module(
        chk.build_runtime(v7_module, target),
        function_name=OPERATOR_NAME,
        input_specs=config["input_specs"],
        output_shape=config["output_shape"],
        inputs=inputs,
    )
    reconstructed_output = chk.run_module(
        chk.build_runtime(reconstructed_module, target),
        function_name=OPERATOR_NAME,
        input_specs=config["input_specs"],
        output_shape=config["output_shape"],
        inputs=inputs,
    )
    abs_diff = np.abs(reconstructed_output - v7_output)
    mismatched_rows = np.nonzero(abs_diff.max(axis=(0, 1, 3)))[0].tolist()
    return {
        "seed": seed,
        "target": target,
        "max_abs_diff": float(abs_diff.max(initial=0.0)),
        "nonzero_diff_count": int(np.count_nonzero(abs_diff)),
        "mismatched_output_rows": mismatched_rows,
        "candidate_output_checksum": hashlib.sha256(reconstructed_output.tobytes()).hexdigest(),
        "reference_output_checksum": hashlib.sha256(v7_output.tobytes()).hexdigest(),
    }


def load_preserved_report() -> dict[str, Any] | None:
    if not PRESERVED_V8_VS_V7_REPORT.is_file():
        return None
    return json.loads(PRESERVED_V8_VS_V7_REPORT.read_text(encoding="utf-8"))


def build_conclusion(
    *,
    boundary: dict[str, Any],
    current_probe: dict[str, Any],
) -> dict[str, str]:
    if (
        boundary["exactness"]["data_dilate_boundary_rows_exact"]
        and boundary["exactness"]["data_pad_boundary_rows_exact"]
        and boundary["exactness"]["producer_only_pad_rewrite_exact"]
        and boundary["exactness"]["consumer_pad_row_carry_exact"]
        and current_probe["nonzero_diff_count"] != 0
    ):
        return {
            "result": "another more precise boundary condition is required",
            "producer_only_overlap_viable": "row-level values say yes, but not yet as a scheduled TIR edit",
            "consumer_pad_overlap_viable": "row-level values also say yes, but only if the carried rows are made explicit and stable for the consumer",
            "reason": (
                "The overlapping producer rows and consumer-facing padded rows are "
                "bit-exact at the row-value level, but the actual producer-only TIR "
                "carry still breaks output rows 32/33 and 96/97. The boundary "
                "condition therefore is not 'producer-only vs consumer carry'; it is "
                "'make the carried boundary rows explicit enough that the current "
                "stripe consumes the exact preserved rows instead of relying on an "
                "implicit skipped write'."
            ),
        }
    if current_probe["nonzero_diff_count"] == 0:
        return {
            "result": "producer-only overlap carry is viable",
            "producer_only_overlap_viable": "yes",
            "consumer_pad_overlap_viable": "not needed for the proof",
            "reason": "The producer-only carry local probe matches v7 exactly.",
        }
    return {
        "result": "overlap carry should be abandoned for now",
        "producer_only_overlap_viable": "no",
        "consumer_pad_overlap_viable": "no",
        "reason": "The local evidence did not produce an exact boundary or a stable carry path.",
    }


def main() -> None:
    args = parse_args()
    v7_text = require_file(V7_TIR_PATH, "v7 TIR").read_text(encoding="utf-8")
    reconstruction = summarize_v8_reconstruction(v7_text)

    chk = import_check_helper()
    config = chk.get_operator_config(OPERATOR_NAME)
    inputs = chk.make_inputs(args.seed, input_specs=config["input_specs"])
    boundary = analyze_boundary_rows(inputs["lv318"])

    current_probe = run_current_local_probe(
        reconstruction["reconstructed_text"],
        seed=args.seed,
        target=args.target,
    )
    preserved = load_preserved_report()
    conclusion = build_conclusion(boundary=boundary, current_probe=current_probe)

    payload = {
        "operator": OPERATOR_NAME,
        "inputs_seed": args.seed,
        "target": args.target,
        "artifacts": {
            "v7_tir": repo_native(V7_TIR_PATH),
            "v8_pyc": repo_native(V8_PYC_PATH),
            "preserved_v8_vs_v7_report": (
                repo_native(PRESERVED_V8_VS_V7_REPORT) if PRESERVED_V8_VS_V7_REPORT.is_file() else None
            ),
        },
        "v8_reconstruction": {
            "reconstructed_sha256": reconstruction["reconstructed_sha256"],
            "normalized_instruction_stream_match_pyc": reconstruction[
                "normalized_instruction_stream_match_pyc"
            ],
            "semantic_change_summary": reconstruction["semantic_change_summary"],
            "normalized_diff_excerpt": reconstruction["normalized_diff_excerpt"],
        },
        "boundary_rows": boundary,
        "current_local_probe": current_probe,
        "preserved_v8_vs_v7_report": preserved,
        "conclusion": conclusion,
    }

    rendered = json.dumps(payload, indent=2, sort_keys=False)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
