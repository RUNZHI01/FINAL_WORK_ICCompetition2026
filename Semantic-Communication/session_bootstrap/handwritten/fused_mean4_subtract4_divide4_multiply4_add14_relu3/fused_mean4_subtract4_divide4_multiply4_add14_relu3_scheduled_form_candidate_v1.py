"""Checked-in local post-db candidate wrapper for mean4.

This module is intentionally narrow:
- it points the existing local schedule-preserving seam at the checked-in
  scheduled-form v1 working copy
- it is local-only and diagnostic-only
- it does not introduce a raw pre-compile handwritten lane for mean4
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


OPERATOR_NAME = "fused_mean4_subtract4_divide4_multiply4_add14_relu3"
WORKING_COPY_TIR_FILENAME = (
    f"{OPERATOR_NAME}_scheduled_form_candidate_v1_working_copy_tir.py"
)
WORKING_COPY_MANIFEST_FILENAME = "scheduled_form_candidate_v1_working_copy_manifest.json"
CANDIDATE_VERSION = "v1_working_copy"
DEFAULT_EVALUATION_CONTRACT = {
    "path_kind": "diagnostic_post_db_scheduled_primfunc_swap",
    "schedule_context_guarantee": "post_db_scheduled_form_expected",
    "performance_evaluable": False,
    "comparison_semantics": "local_build_structural_only",
    "reason": (
        "This wrapper only points the local post-db scheduled swap seam at the "
        "checked-in mean4 scheduled-form v1 working copy, so resulting evidence "
        "is local-only build/probe evidence."
    ),
    "notes": [
        "Use this path to confirm that the mean4 scheduled-form v1 working copy can be consumed by the existing local post-db path.",
        "Do not treat this path as runtime or performance evidence.",
    ],
}


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _working_copy_tir_path() -> Path:
    return _module_dir() / WORKING_COPY_TIR_FILENAME


def _working_copy_manifest_path() -> Path:
    return _module_dir() / WORKING_COPY_MANIFEST_FILENAME


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_status(payload: dict[str, Any]) -> str:
    current_edit_state = payload.get("current_edit_state")
    if isinstance(current_edit_state, dict):
        raw_status = current_edit_state.get("status")
        if isinstance(raw_status, str) and raw_status.strip():
            return raw_status.strip()
    return "seed_synced_unedited"


def _load_working_copy_manifest() -> dict[str, Any]:
    manifest_path = _working_copy_manifest_path()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"working copy manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise ValueError(
            f"expected manifest operator {OPERATOR_NAME!r}, got {operator!r}"
        )

    working_copy_tir_path = _working_copy_tir_path()
    if not working_copy_tir_path.is_file():
        raise FileNotFoundError(f"working copy TIR not found: {working_copy_tir_path}")

    current_edit_state = payload.get("current_edit_state")
    expected_sha = None
    if isinstance(current_edit_state, dict):
        raw_sha = current_edit_state.get("working_copy_tir_sha256")
        if isinstance(raw_sha, str) and raw_sha.strip():
            expected_sha = raw_sha.strip().lower()
    actual_sha = _file_sha256(working_copy_tir_path)
    if expected_sha is not None and actual_sha != expected_sha:
        raise ValueError(
            "working copy manifest SHA does not match the checked-in v1 TIR: "
            f"{expected_sha} != {actual_sha}"
        )

    return payload


def _select_task_row(task_stages: Any) -> dict[str, Any] | None:
    if not isinstance(task_stages, dict):
        return None

    preferred = None
    fallback = None
    for stage_name, payload in task_stages.items():
        tasks = payload.get("tasks") or []
        for row in tasks:
            if row.get("task_name") != OPERATOR_NAME:
                continue
            candidate = dict(row)
            candidate["stage_name"] = stage_name
            if stage_name == "legalized_fused_tir":
                preferred = candidate
                break
            if fallback is None:
                fallback = candidate
        if preferred is not None:
            break
    return preferred or fallback


def _override_target_global_vars(task_row: dict[str, Any] | None) -> list[str]:
    candidates: list[str] = []
    for raw_name in (task_row or {}).get("prim_funcs") or []:
        name = str(raw_name or "").strip()
        if not name or name == "main" or name in candidates:
            continue
        candidates.append(name)
    if OPERATOR_NAME not in candidates:
        candidates.append(OPERATOR_NAME)
    return candidates


def describe_placeholder(context: dict[str, Any] | None = None) -> dict[str, object]:
    del context
    manifest = _load_working_copy_manifest()
    current_edit_state = manifest.get("current_edit_state")
    source_reference_seed = manifest.get("source_reference_seed")
    return {
        "operator": OPERATOR_NAME,
        "candidate_version": CANDIDATE_VERSION,
        "candidate_status": _candidate_status(manifest),
        "working_copy_tir": str(_working_copy_tir_path()),
        "working_copy_manifest": str(_working_copy_manifest_path()),
        "source_reference_seed": source_reference_seed,
        "current_edit_state": current_edit_state,
        "placeholder_only": False,
        "hook_target": False,
        "schedule_preserving_override_available": True,
        "validation_scope": "local_only_post_db_scheduled_swap",
        "evaluation_contract": dict(DEFAULT_EVALUATION_CONTRACT),
        "next_step": (
            "Use run_mean4_post_db_local_build.py to consume this checked-in "
            "mean4 v1 working copy through the local post-db path."
        ),
    }


def build_manual_impl(context: dict[str, Any] | None = None) -> dict[str, object]:
    manifest = _load_working_copy_manifest()
    current_edit_state = manifest.get("current_edit_state")
    task_row = None if context is None else _select_task_row(context.get("task_stages"))

    return {
        "operator": OPERATOR_NAME,
        "phase": None if context is None else context.get("phase"),
        "task_row": task_row,
        "candidate_version": CANDIDATE_VERSION,
        "candidate_status": _candidate_status(manifest),
        "working_copy_tir": str(_working_copy_tir_path()),
        "working_copy_manifest": str(_working_copy_manifest_path()),
        "source_reference_seed": manifest.get("source_reference_seed"),
        "current_edit_state": current_edit_state,
        "validation_scope": "local_only_post_db_scheduled_swap",
        "evaluation_contract": dict(DEFAULT_EVALUATION_CONTRACT),
        "override": {
            "kind": "replace_prim_func_from_source",
            "source_path": str(_working_copy_tir_path()),
            "source_module_attr": "Module",
            "source_func_name": OPERATOR_NAME,
            "target_global_vars": _override_target_global_vars(task_row),
            "candidate_version": CANDIDATE_VERSION,
            "local_only": True,
            "validation_scope": "local_only_post_db_scheduled_swap",
            "evaluation_contract": dict(DEFAULT_EVALUATION_CONTRACT),
        },
        "notes": [
            "The checked-in mean4 scheduled-form v1 working copy is consumed only through the local post-db scheduled swap seam here.",
            "This path stays diagnostic-only and does not make performance claims.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(describe_placeholder(), indent=2, ensure_ascii=False))
