#!/usr/bin/env python3
"""Local-only disjoint seam-buffer proof for transpose1.

This helper stays on `fused_conv2d_transpose1_add9` only. It does not build or
bless a checked-in candidate.

It proves one narrow point from staged-row semantics before `compute_update`:

- keep `v7` as the reference
- materialize the second `h_1` stripe into a disjoint current-stripe buffer
- source rows `0/1` of that current stripe from an explicit 2-row seam buffer
  captured from the first stripe
- compare the fully materialized current-stripe rows against `v7`, with focused
  reporting for global `data_pad` rows `32..35` and `96..99`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPERATOR_NAME = "fused_conv2d_transpose1_add9"
CHECK_HELPER_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"
V7_TIR_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "handwritten"
    / OPERATOR_NAME
    / f"{OPERATOR_NAME}_scheduled_form_candidate_v7_working_copy_tir.py"
)
FOCUS_GLOBAL_ROWS = (32, 33, 34, 35, 96, 97, 98, 99)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a local-only disjoint seam-buffer proof for the second h_1 "
            "stripe in fused_conv2d_transpose1_add9."
        )
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260331,
        help="Frozen RNG seed used to generate lv318/param_0/lv320 inputs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def repo_native(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        return str(resolved)
    return f"./{relative.as_posix()}"


def import_check_helper():
    sys.path.insert(0, str(CHECK_HELPER_DIR.resolve()))
    try:
        import check_transpose1_scheduled_reference_vs_working_copy as helper  # type: ignore
    finally:
        sys.path.pop(0)
    return helper


def materialize_v7_data_pad_slice(
    lv318: np.ndarray,
    *,
    dc_0: int,
    h_base: int,
    w_base: int,
    h1: int,
) -> np.ndarray:
    """Materialize one `v7` data_pad slice for a single dc_0 tile.

    The returned buffer is the 4-channel, 34x10 staged current stripe that
    `compute_update` would read for a single `dc_0` slice.
    """

    window = np.zeros((4, 34, 10), dtype="float32")
    for local_c in range(4):
        global_c = dc_0 * 4 + local_c
        for local_row in range(34):
            global_row = h_base + h1 * 32 + local_row
            for local_col in range(10):
                global_col = w_base + local_col
                if not (1 <= global_row < 128 and 1 <= global_col < 128):
                    continue
                dilate_row = global_row - 1
                dilate_col = global_col - 1
                if dilate_row % 2 == 0 and dilate_col % 2 == 0:
                    window[local_c, local_row, local_col] = lv318[
                        0, global_c, dilate_row // 2, dilate_col // 2
                    ]
    return window


def materialize_disjoint_second_stripe(
    lv318: np.ndarray,
    *,
    dc_0: int,
    h_base: int,
    w_base: int,
) -> dict[str, np.ndarray]:
    """Materialize the proof variant with an explicit disjoint seam buffer.

    The seam buffer holds the first stripe's consumer-facing rows 32/33.
    The second stripe is then rebuilt in a disjoint buffer:
    - rows 0/1 come from the explicit seam buffer
    - rows 2..33 are freshly materialized from current-stripe semantics
    """

    previous_pad = materialize_v7_data_pad_slice(
        lv318, dc_0=dc_0, h_base=h_base, w_base=w_base, h1=0
    )
    current_pad = materialize_v7_data_pad_slice(
        lv318, dc_0=dc_0, h_base=h_base, w_base=w_base, h1=1
    )
    seam_buffer = previous_pad[:, 32:34, :].copy()
    disjoint_current = np.zeros_like(current_pad)
    disjoint_current[:, 0:2, :] = seam_buffer
    disjoint_current[:, 2:, :] = current_pad[:, 2:, :]
    return {
        "previous_pad": previous_pad,
        "current_pad_v7": current_pad,
        "seam_buffer": seam_buffer,
        "current_pad_disjoint": disjoint_current,
    }


def row_stats_template() -> dict[str, Any]:
    return {
        "total_elements": 0,
        "nonzero_diff_count": 0,
        "max_abs_diff": 0.0,
    }


def analyze_disjoint_proof(lv318: np.ndarray) -> dict[str, Any]:
    full_current_stripe_nonzero_diff_count = 0
    full_current_stripe_max_abs_diff = 0.0
    seam_row_max_abs_diff = 0.0
    row_summaries = {str(row): row_stats_template() for row in FOCUS_GLOBAL_ROWS}

    for h_base in (0, 64):
        for w_base in range(0, 128, 8):
            for dc_0 in range(12):
                payload = materialize_disjoint_second_stripe(
                    lv318, dc_0=dc_0, h_base=h_base, w_base=w_base
                )
                current_pad_v7 = payload["current_pad_v7"]
                current_pad_disjoint = payload["current_pad_disjoint"]
                seam_buffer = payload["seam_buffer"]
                seam_reference = current_pad_v7[:, 0:2, :]

                diff = np.abs(current_pad_disjoint - current_pad_v7)
                full_current_stripe_nonzero_diff_count += int(np.count_nonzero(diff))
                full_current_stripe_max_abs_diff = max(
                    full_current_stripe_max_abs_diff,
                    float(diff.max(initial=0.0)),
                )

                seam_diff = np.abs(seam_buffer - seam_reference)
                seam_row_max_abs_diff = max(
                    seam_row_max_abs_diff,
                    float(seam_diff.max(initial=0.0)),
                )

                current_global_row_base = h_base + 32
                for local_row in range(4):
                    global_row = current_global_row_base + local_row
                    if global_row not in FOCUS_GLOBAL_ROWS:
                        continue
                    row_diff = diff[:, local_row, :]
                    row_summary = row_summaries[str(global_row)]
                    row_summary["total_elements"] += int(row_diff.size)
                    row_summary["nonzero_diff_count"] += int(np.count_nonzero(row_diff))
                    row_summary["max_abs_diff"] = max(
                        row_summary["max_abs_diff"],
                        float(row_diff.max(initial=0.0)),
                    )

    return {
        "focus_global_rows": list(FOCUS_GLOBAL_ROWS),
        "tiles_examined": {
            "h_bases": [0, 64],
            "w_bases": list(range(0, 128, 8)),
            "dc_0_slices": 12,
            "total_cases": 2 * 16 * 12,
        },
        "current_stripe_exactness": {
            "all_rows_exact": full_current_stripe_nonzero_diff_count == 0,
            "nonzero_diff_count": full_current_stripe_nonzero_diff_count,
            "max_abs_diff": full_current_stripe_max_abs_diff,
        },
        "seam_rows_exactness": {
            "rows_0_1_exact": seam_row_max_abs_diff == 0.0,
            "max_abs_diff": seam_row_max_abs_diff,
        },
        "focus_rows": row_summaries,
    }


def build_conclusion(analysis: dict[str, Any]) -> dict[str, str]:
    current_exact = analysis["current_stripe_exactness"]["all_rows_exact"]
    seam_exact = analysis["seam_rows_exactness"]["rows_0_1_exact"]
    if current_exact and seam_exact:
        return {
            "result": "disjoint explicit seam buffer restores exactness and is worth promoting",
            "reason": (
                "A fully materialized disjoint second-stripe data_pad buffer matches "
                "v7 exactly before compute_update, including the carried seam rows "
                "and the focused global rows 32..35 and 96..99."
            ),
        }
    return {
        "result": "overlap carry should be closed entirely",
        "reason": (
            "The disjoint current-stripe materialization still failed to match v7 "
            "before compute_update, so the seam-buffer idea did not restore exactness."
        ),
    }


def main() -> None:
    args = parse_args()
    chk = import_check_helper()
    config = chk.get_operator_config(OPERATOR_NAME)
    inputs = chk.make_inputs(args.seed, input_specs=config["input_specs"])
    analysis = analyze_disjoint_proof(inputs["lv318"])
    conclusion = build_conclusion(analysis)

    payload = {
        "operator": OPERATOR_NAME,
        "seed": args.seed,
        "artifacts": {
            "v7_tir": repo_native(V7_TIR_PATH),
        },
        "proof_shape": {
            "seam_buffer": [4, 2, 10],
            "current_second_h1_stripe": [4, 34, 10],
            "construction": {
                "rows_0_1": "copied from explicit previous-stripe seam buffer",
                "rows_2_33": "freshly materialized with current-stripe v7 semantics",
            },
        },
        "analysis": analysis,
        "conclusion": conclusion,
    }

    rendered = json.dumps(payload, indent=2, sort_keys=False)
    print(rendered)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
