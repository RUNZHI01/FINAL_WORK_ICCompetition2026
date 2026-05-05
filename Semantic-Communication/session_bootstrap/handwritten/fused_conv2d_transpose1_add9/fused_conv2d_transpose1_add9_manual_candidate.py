"""Checked-in hook-facing candidate for fused_conv2d_transpose1_add9.

Edit the sibling editable TIR file when shaping the first real manual candidate.
This module stays intentionally narrow:
- it is a repo-native TVM_HANDWRITTEN_IMPL_PATH target
- it reports the checked-in candidate through the existing rpc_tune.py hook
- it only exposes the v0 override through the local/staging handwritten path
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


OPERATOR_NAME = "fused_conv2d_transpose1_add9"
EDITABLE_TIR_FILENAME = f"{OPERATOR_NAME}_editable_seed_tir.py"
CHECKED_IN_CANDIDATE_FILENAME = f"{OPERATOR_NAME}_candidate_v0_tir.py"
CHECKED_IN_CANDIDATE_METADATA_FILENAME = f"{OPERATOR_NAME}_candidate_v0.json"
MANIFEST_FILENAME = "seed_manifest.json"
DEFAULT_EVALUATION_CONTRACT = {
    "path_kind": "diagnostic_raw_pre_compile_replacement",
    "schedule_context_guarantee": "not_guaranteed",
    "performance_evaluable": False,
    "comparison_semantics": "non_comparable_diagnostic_only",
    "future_path_kind": "schedule_context_preserving_evaluation",
    "future_path_status": "not_implemented",
    "reason": (
        "The current raw pre-compile handwritten replacement seam may miss the "
        "best staging schedule context, so any runtime number is diagnostic only."
    ),
    "notes": [
        "Use this path to confirm hook targeting, artifact identity, and structural integration only.",
        "Do not treat runtime measurements from this seam as candidate-performance evidence.",
    ],
}


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _editable_tir_path() -> Path:
    return _module_dir() / EDITABLE_TIR_FILENAME


def _checked_in_candidate_tir_path() -> Path:
    return _module_dir() / CHECKED_IN_CANDIDATE_FILENAME


def _checked_in_candidate_metadata_path() -> Path:
    return _module_dir() / CHECKED_IN_CANDIDATE_METADATA_FILENAME


def _manifest_path() -> Path:
    return _module_dir() / MANIFEST_FILENAME


def _load_manifest() -> dict[str, Any]:
    manifest_path = _manifest_path()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"seed manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise ValueError(
            f"expected manifest operator {OPERATOR_NAME!r}, got {operator!r}"
        )
    return payload


def _load_checked_in_candidate_metadata() -> dict[str, Any]:
    metadata_path = _checked_in_candidate_metadata_path()
    if not metadata_path.is_file():
        raise FileNotFoundError(f"candidate metadata not found: {metadata_path}")

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise ValueError(
            f"expected candidate operator {OPERATOR_NAME!r}, got {operator!r}"
        )
    return payload


def _evaluation_contract(candidate_metadata: dict[str, Any]) -> dict[str, Any]:
    payload = candidate_metadata.get("evaluation_contract")
    if isinstance(payload, dict):
        merged = dict(DEFAULT_EVALUATION_CONTRACT)
        merged.update(payload)
        return merged
    return dict(DEFAULT_EVALUATION_CONTRACT)


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
    manifest = _load_manifest()
    candidate_metadata = _load_checked_in_candidate_metadata()
    evaluation_contract = _evaluation_contract(candidate_metadata)
    return {
        "operator": OPERATOR_NAME,
        "candidate_version": candidate_metadata.get("candidate_version"),
        "candidate_status": candidate_metadata.get("status"),
        "reference_staging_sha256": manifest.get("reference_staging_sha256"),
        "reference_profile_json": manifest.get("reference_profile_json"),
        "argument_shapes": manifest.get("argument_shapes"),
        "seed_capture_kind": manifest.get("seed_capture_kind"),
        "candidate_tir": str(_checked_in_candidate_tir_path()),
        "editable_tir": str(_editable_tir_path()),
        "candidate_metadata": str(_checked_in_candidate_metadata_path()),
        "seed_manifest": str(_manifest_path()),
        "placeholder_only": False,
        "manual_override_applied": False,
        "manual_override_available": True,
        "validation_scope": "local_staging_only_pre_compile_override",
        "evaluation_contract": evaluation_contract,
        "next_step": (
            "Keep using this module as the handwritten-hook entrypoint only for "
            "contract-side diagnostics until a schedule-context-preserving "
            "evaluation path exists."
        ),
    }


def build_manual_impl(context: dict[str, Any] | None = None) -> dict[str, object]:
    manifest = _load_manifest()
    candidate_metadata = _load_checked_in_candidate_metadata()
    evaluation_contract = _evaluation_contract(candidate_metadata)
    candidate_tir_path = _checked_in_candidate_tir_path()
    if not candidate_tir_path.is_file():
        raise FileNotFoundError(
            f"checked-in candidate TIR not found: {candidate_tir_path}"
        )
    task_row = None if context is None else _select_task_row(context.get("task_stages"))

    return {
        "operator": OPERATOR_NAME,
        "phase": None if context is None else context.get("phase"),
        "task_row": task_row,
        "candidate_version": candidate_metadata.get("candidate_version"),
        "candidate_status": candidate_metadata.get("status"),
        "reference_staging_sha256": manifest.get("reference_staging_sha256"),
        "candidate_tir": str(candidate_tir_path),
        "editable_tir": str(_editable_tir_path()),
        "candidate_metadata": str(_checked_in_candidate_metadata_path()),
        "seed_manifest": str(_manifest_path()),
        "validation_scope": "local_staging_only_pre_compile_override",
        "evaluation_contract": evaluation_contract,
        "override": {
            "kind": "replace_prim_func_from_source",
            "source_path": str(candidate_tir_path),
            "source_module_attr": "Module",
            "source_func_name": "main",
            "target_global_vars": _override_target_global_vars(task_row),
            "candidate_version": candidate_metadata.get("candidate_version"),
            "staging_only": True,
            "validation_scope": "local_staging_only_pre_compile_override",
            "evaluation_contract": evaluation_contract,
        },
        "notes": [
            "The checked-in candidate v0 is exposed only through the local/staging handwritten hook.",
            "The current raw pre-compile replacement seam is diagnostic-only and non-comparable.",
            "rpc_tune.py must consume the returned override descriptor before compile_relax.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(describe_placeholder(), indent=2, ensure_ascii=False))
