#!/usr/bin/env python3
"""Refresh the checked-in scheduled-form v1 working copy for transpose2.

This helper stays intentionally narrow:
- it derives the working copy from the checked-in post-db scheduled reference seed
- it keeps the reference seed frozen and clearly distinct from the editable copy
- it is local-only and diagnostic-only
- it does not launch remote work or make performance claims
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPERATOR_NAME = "fused_conv2d_transpose2_add12"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "session_bootstrap" / "handwritten" / OPERATOR_NAME
)
REFERENCE_TIR_FILENAME = f"{OPERATOR_NAME}_post_db_scheduled_reference_seed_tir.py"
REFERENCE_MANIFEST_FILENAME = "post_db_scheduled_reference_seed_manifest.json"
WORKING_COPY_TIR_FILENAME = (
    f"{OPERATOR_NAME}_scheduled_form_candidate_v1_working_copy_tir.py"
)
WORKING_COPY_MANIFEST_FILENAME = (
    "scheduled_form_candidate_v1_working_copy_manifest.json"
)
IMPORT_BLOCK = "from tvm.script import ir as I\nfrom tvm.script import tir as T\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the checked-in scheduled-form candidate v1 working copy for "
            f"{OPERATOR_NAME} from the checked-in scheduled reference seed."
        )
    )
    parser.add_argument(
        "--reference-tir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / REFERENCE_TIR_FILENAME,
        help="Checked-in post-db scheduled reference seed TIR.",
    )
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / REFERENCE_MANIFEST_FILENAME,
        help="Checked-in manifest for the post-db scheduled reference seed.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Checked-in handwritten directory that will receive the working copy files.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional extra JSON summary output path.",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow overwriting the existing checked-in working copy files.",
    )
    return parser.parse_args(argv)


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def as_abs(path: Path) -> Path:
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def repo_native(path: Path | str) -> str:
    value = Path(path)
    resolved = value if value.is_absolute() else (PROJECT_ROOT / value).resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return str(resolved)
    return f"./{relative.as_posix()}"


def ensure_clean_outputs(paths: list[Path], allow_overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not allow_overwrite:
        joined = "\n  ".join(str(path) for path in existing)
        raise SystemExit(
            "ERROR: output already exists. Re-run with --allow-overwrite to refresh.\n"
            f"  {joined}"
        )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_reference_manifest(reference_manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(reference_manifest_path.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise SystemExit(
            f"ERROR: expected reference manifest operator {OPERATOR_NAME!r}, "
            f"got {operator!r}"
        )
    return payload


def extract_tvm_script(reference_tir_path: Path) -> str:
    text = reference_tir_path.read_text(encoding="utf-8").replace(
        "# from tvm.script import ir as I\n# from tvm.script import tir as T\n",
        IMPORT_BLOCK,
        1,
    )
    start = text.find(IMPORT_BLOCK)
    if start < 0:
        raise SystemExit(
            "ERROR: could not find the TVM script import block in "
            f"{reference_tir_path}"
        )
    script = text[start:].strip()
    if not script:
        raise SystemExit(f"ERROR: extracted empty TVM script from {reference_tir_path}")
    return script + "\n"


def render_working_copy_tir(
    *,
    reference_tir_path: Path,
    reference_manifest_path: Path,
) -> str:
    script = extract_tvm_script(reference_tir_path)
    header = [
        f"# Editable scheduled-form candidate v1 working copy for {OPERATOR_NAME}.",
        "#",
        "# Derived from:",
        f"# - checked-in scheduled reference seed: {repo_native(reference_tir_path)}",
        f"# - checked-in scheduled reference manifest: {repo_native(reference_manifest_path)}",
        "#",
        "# Contract:",
        "# - local-only diagnostic working copy",
        "# - start here for transpose2 scheduled-form handwritten edits",
        "# - keep the scheduled reference seed frozen so this file can be refreshed",
        "# - do not treat this file as hook-facing or as performance evidence",
        "#",
        "# Current checked-in state:",
        "# - no operator-side handwritten edit has been applied yet",
        "# - this file is an editable scheduled-form clone of the checked-in reference seed",
        "",
    ]
    return "\n".join(header) + script


def build_working_copy_manifest(
    *,
    reference_manifest: dict[str, Any],
    reference_tir_path: Path,
    reference_manifest_path: Path,
    working_copy_tir_path: Path,
    working_copy_manifest_path: Path,
    working_copy_tir_sha256: str,
) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "operator": OPERATOR_NAME,
        "phase": "scheduled_form_candidate_v1_prep",
        "working_copy_role": "editable_scheduled_form_candidate_v1_working_copy",
        "working_copy_contract": {
            "path_kind": "diagnostic_scheduled_form_candidate_v1_working_copy",
            "local_only": True,
            "diagnostic_only": True,
            "hook_target": False,
            "performance_claims": False,
            "comparison_semantics": "edit_surface_only",
        },
        "source_reference_seed": {
            "reference_tir_path": repo_native(reference_tir_path),
            "reference_tir_sha256": file_sha256(reference_tir_path),
            "reference_manifest_path": repo_native(reference_manifest_path),
            "reference_seed_capture_kind": reference_manifest.get("seed_capture_kind"),
            "reference_phase": reference_manifest.get("phase"),
            "reference_source": reference_manifest.get("source"),
            "reference_task_rows": reference_manifest.get("task_rows"),
        },
        "current_edit_state": {
            "status": "seed_synced_unedited",
            "applied_at_utc": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "working_copy_tir_sha256": working_copy_tir_sha256,
            "concrete_change": (
                "No operator-side handwritten change yet. This working copy is an editable "
                "scheduled-form clone of the checked-in post-db scheduled reference seed "
                "for transpose2."
            ),
            "preserved_non_changes": [
                "the scheduled reference seed remains the frozen source of truth",
                "no tiling, buffer, or epilogue edits have been applied yet",
                "the file is still local-only, diagnostic-only, and not hook-facing",
            ],
        },
        "related_files": {
            "scheduled_reference_tir": repo_native(reference_tir_path),
            "scheduled_reference_manifest": repo_native(reference_manifest_path),
            "working_copy_tir": repo_native(working_copy_tir_path),
            "working_copy_manifest": repo_native(working_copy_manifest_path),
        },
        "notes": [
            "This working copy is derived from the checked-in post-db scheduled reference seed so the first transpose2 edits start from a scheduled form.",
            "Keep the scheduled reference seed frozen and refresh this working copy when the reference seed changes.",
            "The current checked-in working copy is intentionally unedited and only opens the local scheduled-form edit surface.",
            "This handoff is local-only and diagnostic-only; it does not make performance claims.",
        ],
    }


def write_output_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.reference_tir = require_file(
        as_abs(args.reference_tir), "checked-in scheduled reference seed tir"
    )
    args.reference_manifest = require_file(
        as_abs(args.reference_manifest),
        "checked-in scheduled reference seed manifest",
    )
    args.output_dir = as_abs(args.output_dir)

    working_copy_tir_path = args.output_dir / WORKING_COPY_TIR_FILENAME
    working_copy_manifest_path = args.output_dir / WORKING_COPY_MANIFEST_FILENAME
    guarded_paths = [working_copy_tir_path, working_copy_manifest_path]
    if args.output_json is not None:
        args.output_json = as_abs(args.output_json)
        guarded_paths.append(args.output_json)
    ensure_clean_outputs(guarded_paths, args.allow_overwrite)

    reference_manifest = load_reference_manifest(args.reference_manifest)
    working_copy_tir = render_working_copy_tir(
        reference_tir_path=args.reference_tir,
        reference_manifest_path=args.reference_manifest,
    )
    working_copy_tir_sha256 = text_sha256(working_copy_tir)
    working_copy_manifest = build_working_copy_manifest(
        reference_manifest=reference_manifest,
        reference_tir_path=args.reference_tir,
        reference_manifest_path=args.reference_manifest,
        working_copy_tir_path=working_copy_tir_path,
        working_copy_manifest_path=working_copy_manifest_path,
        working_copy_tir_sha256=working_copy_tir_sha256,
    )

    write_text(working_copy_tir_path, working_copy_tir)
    write_text(
        working_copy_manifest_path,
        json.dumps(working_copy_manifest, indent=2, ensure_ascii=False) + "\n",
    )

    summary = {
        "status": "ok",
        "operator": OPERATOR_NAME,
        "reference_tir_path": str(args.reference_tir),
        "reference_manifest_path": str(args.reference_manifest),
        "working_copy_tir_path": str(working_copy_tir_path),
        "working_copy_tir_sha256": file_sha256(working_copy_tir_path),
        "working_copy_manifest_path": str(working_copy_manifest_path),
        "working_copy_manifest_sha256": file_sha256(working_copy_manifest_path),
        "local_only": True,
        "diagnostic_only": True,
    }
    payload = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        write_output_json(args.output_json, payload)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
