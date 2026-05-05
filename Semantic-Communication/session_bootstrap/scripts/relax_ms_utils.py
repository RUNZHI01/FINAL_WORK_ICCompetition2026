#!/usr/bin/env python3
"""Shared helpers for Relax MetaSchedule task visibility and preprocessing."""

from __future__ import annotations

import os
from typing import Any

RAW_STAGE_NAME = "raw_import"
TUNED_STAGE_NAME = "legalized_fused_tir"
TUNED_STAGE_PIPELINE = (
    "LegalizeOps -> AnnotateTIROpPattern -> FuseOps -> FuseTIR"
)


def load_onnx_to_relax(
    onnx_path: str,
    input_name: str,
    input_shape: list[int],
    input_dtype: str,
):
    """Load an ONNX model and convert it to Relax IR."""
    import onnx  # pylint: disable=import-outside-toplevel
    from tvm.relax.frontend.onnx import from_onnx  # pylint: disable=import-outside-toplevel

    if not os.path.isfile(onnx_path):
        raise SystemExit(f"ONNX file not found: {onnx_path}")

    onnx_model = onnx.load(onnx_path)
    return from_onnx(
        model=onnx_model,
        shape_dict={input_name: list(input_shape)},
        dtype_dict=input_dtype,
        opset=None,
        keep_params_in_input=False,
        sanitize_input_names=True,
    )


def preprocess_for_meta_schedule(mod):
    """Lower high-level Relax ops into fused TIR tasks before extraction/tuning."""
    import tvm  # pylint: disable=import-outside-toplevel
    from tvm import relax  # pylint: disable=import-outside-toplevel

    seq = tvm.transform.Sequential(
        [
            relax.transform.LegalizeOps(),
            relax.transform.AnnotateTIROpPattern(),
            relax.transform.FuseOps(),
            relax.transform.FuseTIR(),
        ]
    )
    with tvm.transform.PassContext(opt_level=3):
        return seq(mod)


def _sorted_task_rows(tasks: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, task in enumerate(
        sorted(tasks, key=lambda item: (-int(item.weight), item.task_name)),
        start=1,
    ):
        prim_funcs: list[str] = []
        for dispatched in task.dispatched:
            try:
                prim_funcs.extend(str(gv.name_hint) for gv in dispatched.get_global_vars())
            except Exception:  # pragma: no cover - best effort only
                continue
        rows.append(
            {
                "rank": idx,
                "task_name": task.task_name,
                "weight": int(task.weight),
                "dispatched_count": len(task.dispatched),
                "prim_funcs": sorted(set(prim_funcs)),
                "target": str(task.target),
            }
        )
    return rows


def summarize_task_stages(mod, target) -> tuple[Any, dict[str, Any]]:
    """Return raw-stage and tuned-stage task summaries for a Relax module."""
    import tvm  # pylint: disable=import-outside-toplevel
    from tvm.s_tir.meta_schedule.relax_integration import (  # pylint: disable=import-outside-toplevel
        extract_tasks,
    )

    if not isinstance(target, tvm.target.Target):
        target = tvm.target.Target(target)

    raw_rows = _sorted_task_rows(list(extract_tasks(mod, target)))
    tuned_mod = preprocess_for_meta_schedule(mod)
    tuned_rows = _sorted_task_rows(list(extract_tasks(tuned_mod, target)))

    return tuned_mod, {
        RAW_STAGE_NAME: {
            "stage_name": RAW_STAGE_NAME,
            "pipeline": None,
            "total_tasks": len(raw_rows),
            "tasks": raw_rows,
        },
        TUNED_STAGE_NAME: {
            "stage_name": TUNED_STAGE_NAME,
            "pipeline": TUNED_STAGE_PIPELINE,
            "total_tasks": len(tuned_rows),
            "tasks": tuned_rows,
        },
    }
