#!/usr/bin/env python3
"""Local correctness compare for variance4 scheduled reference vs working copy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


OPERATOR_NAME = "fused_variance4_add13_tir_sqrt4"
INPUT_SPECS = [("lv335", (1, 12, 256, 256))]
OUTPUT_SHAPE = (1, 12, 1, 1)
DEFAULT_REFERENCE_TIR = (
    Path(__file__).resolve().parents[1]
    / "handwritten"
    / OPERATOR_NAME
    / f"{OPERATOR_NAME}_post_db_scheduled_reference_seed_tir.py"
)
DEFAULT_CANDIDATE_TIR = (
    Path(__file__).resolve().parents[1]
    / "handwritten"
    / OPERATOR_NAME
    / f"{OPERATOR_NAME}_scheduled_form_candidate_v6_working_copy_tir.py"
)


def _compare_helper():
    import check_transpose1_scheduled_reference_vs_working_copy as compare_helper

    return compare_helper


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the variance4 scheduled reference seed and a chosen working "
            "copy locally, then compare outputs on a fixed random seed."
        )
    )
    parser.add_argument(
        "--reference-tir",
        type=Path,
        default=DEFAULT_REFERENCE_TIR,
        help="Checked-in frozen variance4 scheduled reference seed TIR.",
    )
    parser.add_argument(
        "--candidate-tir",
        type=Path,
        default=DEFAULT_CANDIDATE_TIR,
        help="Checked-in variance4 scheduled-form working copy TIR to compare.",
    )
    parser.add_argument(
        "--target",
        default="llvm",
        help="Local build target for the correctness compare. Default: llvm.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260402,
        help="Frozen RNG seed for generated inputs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    compare_helper = _compare_helper()
    reference_tir = compare_helper.require_file(args.reference_tir, "reference tir")
    candidate_tir = compare_helper.require_file(args.candidate_tir, "candidate tir")

    reference_module = compare_helper.load_ir_module(
        reference_tir, operator_name=OPERATOR_NAME
    )
    candidate_module = compare_helper.load_ir_module(
        candidate_tir, operator_name=OPERATOR_NAME
    )

    inputs = compare_helper.make_inputs(args.seed, input_specs=INPUT_SPECS)
    reference_runtime = compare_helper.build_runtime(reference_module, args.target)
    candidate_runtime = compare_helper.build_runtime(candidate_module, args.target)
    reference_output = compare_helper.run_module(
        reference_runtime,
        function_name=OPERATOR_NAME,
        input_specs=INPUT_SPECS,
        output_shape=OUTPUT_SHAPE,
        inputs=inputs,
    )
    candidate_output = compare_helper.run_module(
        candidate_runtime,
        function_name=OPERATOR_NAME,
        input_specs=INPUT_SPECS,
        output_shape=OUTPUT_SHAPE,
        inputs=inputs,
    )

    report = compare_helper.build_report(
        operator_name=OPERATOR_NAME,
        reference_tir=reference_tir,
        candidate_tir=candidate_tir,
        target=args.target,
        seed=args.seed,
        input_specs=INPUT_SPECS,
        output_shape=OUTPUT_SHAPE,
        reference_output=reference_output,
        candidate_output=candidate_output,
    )
    compare_helper.maybe_write_json(report, args.output_json)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
