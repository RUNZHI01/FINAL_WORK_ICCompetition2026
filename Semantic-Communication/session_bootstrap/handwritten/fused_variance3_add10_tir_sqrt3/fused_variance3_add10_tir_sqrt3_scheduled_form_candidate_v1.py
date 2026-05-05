"""Checked-in local post-db candidate wrapper for variance3 v1.

This module applies the working set reduction + normalized-mean handoff principle
(proven in variance4 v18) to variance3, adapted for the [1,24,128,128] shape.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


OPERATOR_NAME = "fused_variance3_add10_tir_sqrt3"
WORKING_COPY_TIR_FILENAME = (
    f"{OPERATOR_NAME}_scheduled_form_candidate_v1_working_copy_tir.py"
)
WORKING_COPY_MANIFEST_FILENAME = (
    "scheduled_form_candidate_v1_working_copy_manifest.json"
)
CANDIDATE_VERSION = "v1_working_copy"
DEFAULT_EVALUATION_CONTRACT = {
    "path_kind": "diagnostic_post_db_scheduled_primfunc_swap",
    "schedule_context_guarantee": "post_db_scheduled_form_expected",
    "performance_evaluable": False,
    "comparison_semantics": "local_build_structural_only",
    "reason": (
        "This wrapper points the local post-db scheduled swap seam at the "
        "checked-in variance3 scheduled-form v1 working copy, applying "
        "the proven working set reduction + normalized-mean handoff from variance4 v18."
    ),
    "notes": [
        "Use this path to confirm variance3 v1 can be consumed by the existing local post-db path.",
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
            "working copy manifest SHA does not match the checked-in v1 TIR: "
            f"{expected_sha} != {actual_sha}"
        )

    return payload


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
    }


def build_manual_impl(context: dict[str, Any] | None = None) -> dict[str, object]:
    manifest = _load_working_copy_manifest()
    current_edit_state = manifest.get("current_edit_state")

    return {
        "operator": OPERATOR_NAME,
        "phase": None if context is None else context.get("phase"),
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
            "target_global_vars": [OPERATOR_NAME],
            "candidate_version": CANDIDATE_VERSION,
            "local_only": True,
            "validation_scope": "local_only_post_db_scheduled_swap",
            "evaluation_contract": dict(DEFAULT_EVALUATION_CONTRACT),
        },
        "notes": [
            "The checked-in variance3 v1 working copy applies the working set reduction + normalized-mean handoff principle from variance4 v18.",
            "Shape: [1,24,128,128] -> [1,24,1,1], spatial reduction 128*128=16384.",
            "This path stays diagnostic-only and does not make performance claims.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(describe_placeholder(), indent=2, ensure_ascii=False))
