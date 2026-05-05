from __future__ import annotations

from pathlib import Path
from typing import Any

OPERATOR_NAME = "fused_conv2d_transpose_add6"
CANDIDATE_VERSION = "acl_packed_shim_v1"
WORKING_COPY_TIR_FILENAME = (
    "fused_conv2d_transpose_add6_scheduled_form_candidate_acl_packed_working_copy_tir.py"
)

def _module_dir() -> Path:
    return Path(__file__).resolve().parent

def _working_copy_tir_path() -> Path:
    return _module_dir() / WORKING_COPY_TIR_FILENAME

def _select_task_row(task_stages: Any) -> dict[str, Any] | None:
    if not isinstance(task_stages, dict):
        return None
    for stage_name, payload in task_stages.items():
        for row in payload.get("tasks") or []:
            if row.get("task_name") == OPERATOR_NAME:
                candidate = dict(row)
                candidate["stage_name"] = stage_name
                return candidate
    return None

def _override_target_global_vars(task_row: dict[str, Any] | None) -> list[str]:
    candidates: list[str] = []
    for raw_name in (task_row or {}).get("prim_funcs") or []:
        name = str(raw_name or "").strip()
        if name and name != "main" and name not in candidates:
            candidates.append(name)
    if OPERATOR_NAME not in candidates:
        candidates.append(OPERATOR_NAME)
    return candidates

def describe_placeholder(context: dict[str, Any] | None = None) -> dict[str, object]:
    del context
    return {
        "operator": OPERATOR_NAME,
        "candidate_version": CANDIDATE_VERSION,
        "candidate_status": "acl_packed_shim_ready",
        "working_copy_tir": str(_working_copy_tir_path()),
        "placeholder_only": False,
        "hook_target": True,
        "schedule_preserving_override_available": True,
        "validation_scope": "post_db_scheduled_swap_with_packed_call_shim",
    }

def build_manual_impl(context: dict[str, Any] | None = None) -> dict[str, object]:
    task_row = None if context is None else _select_task_row(context.get("task_stages"))
    return {
        "operator": OPERATOR_NAME,
        "phase": None if context is None else context.get("phase"),
        "task_row": task_row,
        "candidate_version": CANDIDATE_VERSION,
        "candidate_status": "acl_packed_shim_ready",
        "working_copy_tir": str(_working_copy_tir_path()),
        "validation_scope": "post_db_scheduled_swap_with_packed_call_shim",
        "override": {
            "kind": "replace_prim_func_from_source",
            "source_path": str(_working_copy_tir_path()),
            "source_module_attr": "Module",
            "source_func_name": OPERATOR_NAME,
            "target_global_vars": _override_target_global_vars(task_row),
            "candidate_version": CANDIDATE_VERSION,
            "local_only": False,
            "validation_scope": "post_db_scheduled_swap_with_packed_call_shim",
        },
        "notes": [
            "This candidate replaces fused_conv2d_transpose_add6 with a T.call_packed shim.",
            "It requires TVM_RUNTIME_PRELOAD_PY to register jscc.acl.transpose_add6 at runtime.",
        ],
    }
