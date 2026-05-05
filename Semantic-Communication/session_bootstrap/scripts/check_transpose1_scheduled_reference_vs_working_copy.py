#!/usr/bin/env python3
"""Local correctness compare for scheduled reference vs working copy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR_NAME = "fused_conv2d_transpose1_add9"
OPERATOR_CONFIGS = {
    "fused_conv2d_transpose1_add9": {
        "input_specs": [
            ("lv318", (1, 48, 64, 64)),
            ("param_0", (48, 24, 3, 3)),
            ("lv320", (1, 24, 1, 1)),
        ],
        "output_shape": (1, 24, 128, 128),
    },
    "fused_conv2d_transpose2_add12": {
        "input_specs": [
            ("lv332", (1, 24, 128, 128)),
            ("param_0", (24, 12, 3, 3)),
            ("lv334", (1, 12, 1, 1)),
        ],
        "output_shape": (1, 12, 256, 256),
    },
    "fused_conv2d_transpose_add6": {
        "input_specs": [
            ("lv304", (1, 96, 32, 32)),
            ("param_0", (96, 48, 3, 3)),
            ("lv306", (1, 48, 1, 1)),
        ],
        "output_shape": (1, 48, 64, 64),
    },
    "fused_conv2d3_add15": {
        "input_specs": [
            ("lv347", (1, 12, 262, 262)),
            ("param_0", (3, 12, 7, 7)),
            ("lv349", (1, 3, 1, 1)),
        ],
        "output_shape": (1, 3, 256, 256),
    },
    "fused_mean4_subtract4_divide4_multiply4_add14_relu3": {
        "input_specs": [
            ("lv335", (1, 12, 256, 256)),
            ("lv340", (1, 12, 1, 1)),
            ("lv342", (12, 1, 1)),
            ("lv344", (12, 1, 1)),
        ],
        "output_shape": (1, 12, 256, 256),
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the scheduled reference seed and the current working copy "
            "locally, then compare outputs on a fixed random seed."
        )
    )
    parser.add_argument(
        "--operator-name",
        choices=sorted(OPERATOR_CONFIGS),
        default=DEFAULT_OPERATOR_NAME,
        help=(
            "Operator preset that selects the packed function name and default "
            "input/output shapes."
        ),
    )
    parser.add_argument(
        "--reference-tir",
        type=Path,
        help="Checked-in frozen scheduled reference seed TIR. Defaults from the operator preset.",
    )
    parser.add_argument(
        "--candidate-tir",
        type=Path,
        help="Checked-in scheduled-form working copy TIR to compare. Defaults from the operator preset.",
    )
    parser.add_argument(
        "--target",
        default="llvm",
        help="Local build target for the correctness compare. Default: llvm.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260331,
        help="Frozen RNG seed for generated inputs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser.parse_args(argv)


def operator_dir(operator_name: str) -> Path:
    return (
        PROJECT_ROOT
        / "session_bootstrap"
        / "handwritten"
        / operator_name
    )


def default_reference_tir(operator_name: str) -> Path:
    return operator_dir(operator_name) / f"{operator_name}_post_db_scheduled_reference_seed_tir.py"


def default_candidate_tir(operator_name: str) -> Path:
    return operator_dir(operator_name) / f"{operator_name}_scheduled_form_candidate_v1_working_copy_tir.py"


def get_operator_config(operator_name: str) -> dict[str, Any]:
    try:
        return OPERATOR_CONFIGS[operator_name]
    except KeyError as exc:
        raise SystemExit(f"ERROR: unsupported operator preset: {operator_name}") from exc


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"ERROR: {label} not found: {resolved}")
    return resolved


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_native(path: Path) -> str:
    try:
        relative = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return str(path)
    return f"./{relative.as_posix()}"


def import_tvm():
    try:
        import tvm  # type: ignore
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "ERROR: python module `tvm` is required for the correctness compare"
        ) from exc
    return tvm


def load_python_module(module_path: Path, *, operator_name: str):
    module_name = f"{operator_name}_correctness_{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERROR: unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def load_ir_module(module_path: Path, *, operator_name: str):
    loaded = load_python_module(module_path, operator_name=operator_name)
    ir_module = getattr(loaded, "Module", None)
    if ir_module is None:
        raise SystemExit(f"ERROR: no `Module` IRModule found in {module_path}")
    return ir_module


def build_runtime(ir_module: Any, target: str):
    tvm = import_tvm()
    return tvm.build(ir_module, target=target)


def get_packed_func(runtime_module: Any, *, function_name: str):
    func = runtime_module.get_function(function_name)
    if func is None:
        raise SystemExit(
            f"ERROR: runtime module does not expose packed func {function_name!r}"
        )
    return func


def make_inputs(seed: int, *, input_specs: list[tuple[str, tuple[int, ...]]]) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        name: rng.uniform(-1.0, 1.0, size=shape).astype("float32")
        for name, shape in input_specs
    }


def run_module(
    runtime_module: Any,
    *,
    function_name: str,
    input_specs: list[tuple[str, tuple[int, ...]]],
    output_shape: tuple[int, ...],
    inputs: dict[str, np.ndarray],
) -> np.ndarray:
    tvm = import_tvm()
    func = get_packed_func(runtime_module, function_name=function_name)
    device = tvm.cpu(0)
    input_tensors = [
        tvm.runtime.tensor(inputs[name], device=device)
        for name, _shape in input_specs
    ]
    output = tvm.runtime.empty(output_shape, "float32", device=device)
    func(*input_tensors, output)
    return output.numpy()


def build_report(
    *,
    operator_name: str,
    reference_tir: Path,
    candidate_tir: Path,
    target: str,
    seed: int,
    input_specs: list[tuple[str, tuple[int, ...]]],
    output_shape: tuple[int, ...],
    reference_output: np.ndarray,
    candidate_output: np.ndarray,
) -> dict[str, Any]:
    diff = candidate_output - reference_output
    abs_diff = np.abs(diff)
    exact_equal = bool(np.array_equal(reference_output, candidate_output))
    max_abs_diff = float(abs_diff.max(initial=0.0))
    nonzero_diff_count = int(np.count_nonzero(abs_diff))

    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "operator": operator_name,
        "reference_tir": repo_native(reference_tir),
        "reference_tir_sha256": file_sha256(reference_tir),
        "candidate_tir": repo_native(candidate_tir),
        "candidate_tir_sha256": file_sha256(candidate_tir),
        "target": target,
        "seed": seed,
        "input_shapes": {
            name: list(shape) for name, shape in input_specs
        },
        "output_shape": list(output_shape),
        "exact_equal": exact_equal,
        "allclose_atol0_rtol0": bool(
            np.allclose(reference_output, candidate_output, atol=0.0, rtol=0.0)
        ),
        "allclose_atol1e-6_rtol1e-6": bool(
            np.allclose(reference_output, candidate_output, atol=1e-6, rtol=1e-6)
        ),
        "allclose_atol1e-5_rtol1e-5": bool(
            np.allclose(reference_output, candidate_output, atol=1e-5, rtol=1e-5)
        ),
        "max_abs_diff": max_abs_diff,
        "mean_abs_diff": float(abs_diff.mean()),
        "nonzero_diff_count": nonzero_diff_count,
        "reference_output_checksum": sha256(reference_output.tobytes()).hexdigest(),
        "candidate_output_checksum": sha256(candidate_output.tobytes()).hexdigest(),
    }


def maybe_write_json(payload: dict[str, Any], output_json: Path | None) -> None:
    if output_json is None:
        return
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    operator_name = args.operator_name
    operator_config = get_operator_config(operator_name)
    input_specs = operator_config["input_specs"]
    output_shape = operator_config["output_shape"]
    reference_tir = require_file(
        args.reference_tir or default_reference_tir(operator_name),
        "reference tir",
    )
    candidate_tir = require_file(
        args.candidate_tir or default_candidate_tir(operator_name),
        "candidate tir",
    )

    reference_module = load_ir_module(reference_tir, operator_name=operator_name)
    candidate_module = load_ir_module(candidate_tir, operator_name=operator_name)

    inputs = make_inputs(args.seed, input_specs=input_specs)
    reference_runtime = build_runtime(reference_module, args.target)
    candidate_runtime = build_runtime(candidate_module, args.target)
    reference_output = run_module(
        reference_runtime,
        function_name=operator_name,
        input_specs=input_specs,
        output_shape=output_shape,
        inputs=inputs,
    )
    candidate_output = run_module(
        candidate_runtime,
        function_name=operator_name,
        input_specs=input_specs,
        output_shape=output_shape,
        inputs=inputs,
    )

    report = build_report(
        operator_name=operator_name,
        reference_tir=reference_tir,
        candidate_tir=candidate_tir,
        target=args.target,
        seed=args.seed,
        input_specs=input_specs,
        output_shape=output_shape,
        reference_output=reference_output,
        candidate_output=candidate_output,
    )
    maybe_write_json(report, args.output_json)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
