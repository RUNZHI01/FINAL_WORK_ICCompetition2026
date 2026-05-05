"""Checked-in local post-db candidate wrapper for fused_conv2d_transpose1_add9 v5.

This module points the local schedule-preserving seam at a v5 working copy that
keeps the winning transpose1 v4 staging-hoist structure intact while flipping
the consumer order from `c_1 -> h_1/w_1` to `h_1/w_1 -> c_1` so each staged
spatial subtile is consumed across all three output-channel groups before the
next subtile is touched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


OPERATOR_NAME = "fused_conv2d_transpose1_add9"
WORKING_COPY_TIR_FILENAME = (
    f"{OPERATOR_NAME}_scheduled_form_candidate_v5_working_copy_tir.py"
)
WORKING_COPY_MANIFEST_FILENAME = "scheduled_form_candidate_v5_working_copy_manifest.json"
CANDIDATE_VERSION = "v5_working_copy"
DEFAULT_EVALUATION_CONTRACT = {
    "path_kind": "diagnostic_post_db_scheduled_primfunc_swap",
    "schedule_context_guarantee": "post_db_scheduled_form_expected",
    "performance_evaluable": False,
    "comparison_semantics": "local_build_structural_only",
    "reason": (
        "This wrapper only points the local post-db scheduled swap seam at the "
        "checked-in scheduled-form v5 working copy, so resulting evidence is "
        "local-only build/probe evidence for this narrow transpose1 follow-up "
        "on top of the winning v4 staging-hoist lane."
    ),
    "notes": [
        "Use this path to confirm that the scheduled-form v5 working copy can be consumed by the existing local schedule-preserving seam.",
        "The checked-in v5 file keeps v4's materialized data/kernel staging and stage-once tile reuse across c_1 groups.",
        "The only new operator-side edit is to consume each staged h_1/w_1 spatial subtile across all three c_1 groups before advancing.",
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
        if isinstance(raw_sha, str) and raw_sha.strip() and raw_sha != "PENDING_SHA256":
            expected_sha = raw_sha.strip().lower()
    actual_sha = _file_sha256(working_copy_tir_path)
    if expected_sha is not None and actual_sha != expected_sha:
        raise ValueError(
            "working copy manifest SHA does not match the checked-in v5 TIR: "
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
    return {
        "operator": OPERATOR_NAME,
        "candidate_version": CANDIDATE_VERSION,
        "candidate_status": None
        if not isinstance(current_edit_state, dict)
        else current_edit_state.get("status"),
        "working_copy_tir": str(_working_copy_tir_path()),
        "working_copy_manifest": str(_working_copy_manifest_path()),
        "accepted_baseline": manifest.get("accepted_baseline"),
        "current_edit_state": current_edit_state,
        "placeholder_only": False,
        "hook_target": False,
        "schedule_preserving_override_available": True,
        "validation_scope": "local_only_post_db_scheduled_swap",
        "evaluation_contract": dict(DEFAULT_EVALUATION_CONTRACT),
        "next_step": (
            "Take this exact v5 working copy through the existing local proof "
            "path, then benchmark the resulting swapped artifact on the board "
            "without mutating the frozen v4 or older accepted transpose1 files."
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
        "candidate_status": None
        if not isinstance(current_edit_state, dict)
        else current_edit_state.get("status"),
        "working_copy_tir": str(_working_copy_tir_path()),
        "working_copy_manifest": str(_working_copy_manifest_path()),
        "accepted_baseline": manifest.get("accepted_baseline"),
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
            "The checked-in scheduled-form v5 working copy is consumed only through the local post-db scheduled swap seam here.",
            "This narrow v5 follow-up keeps v4's stage-once data-tile reuse and only changes the compute consumer order to h_1/w_1 before c_1.",
            "This path stays diagnostic-only and does not make performance claims.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(describe_placeholder(), indent=2, ensure_ascii=False))
