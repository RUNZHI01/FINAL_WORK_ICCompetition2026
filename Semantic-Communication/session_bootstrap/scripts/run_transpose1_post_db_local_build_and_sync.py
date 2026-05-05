#!/usr/bin/env python3
"""Run the transpose1 local post-DB build path and sync its result.

This helper is intentionally narrow and operator-specific:
- it only targets the handwritten transpose1 scaffold workflow
- it runs the preferred local-only post-db scheduled swap build wrapper
- it immediately syncs the resulting artifact/report facts into the scaffold
- it prints a concise final JSON summary for diagnostic bookkeeping only

It does not launch remote work and it does not make runtime/performance claims.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_transpose1_post_db_local_build as local_build
import sync_transpose1_post_db_local_build_result as sync_result

DEFAULT_PYTHON_EXECUTABLE = Path("/home/tianxing/.venvs/tvm-ms/bin/python")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot local-only wrapper for the transpose1 post-db scheduled "
            "swap build plus scaffold sync."
        )
    )
    parser.add_argument(
        "--scaffold-dir",
        type=Path,
        default=sync_result.DEFAULT_SCAFFOLD_DIR,
        help="Existing handwritten scaffold directory to sync in place.",
    )
    parser.add_argument(
        "--task-summary",
        type=Path,
        default=local_build.DEFAULT_TASK_SUMMARY,
        help="Best-staging task_summary.json for transpose1.",
    )
    parser.add_argument(
        "--database-dir",
        type=Path,
        default=local_build.DEFAULT_DATABASE_DIR,
        help="Best-staging tuning_logs directory for transpose1.",
    )
    parser.add_argument(
        "--candidate-impl",
        type=Path,
        default=local_build.DEFAULT_CANDIDATE_IMPL,
        help="Checked-in scheduled-form v1 candidate entrypoint for the local post-db path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=local_build.DEFAULT_OUTPUT_DIR,
        help="Directory for the local swapped artifact and adjacent JSON report.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional extra output path for the concise final JSON summary.",
    )
    parser.add_argument(
        "--python-executable",
        type=Path,
        default=DEFAULT_PYTHON_EXECUTABLE,
        help=(
            "Python executable used to run the underlying local build and sync helpers. "
            "Defaults to the repo's TVM-enabled virtualenv interpreter."
        ),
    )
    return parser.parse_args(argv)


def resolve_python_executable(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.is_file():
        return candidate
    fallback = Path(sys.executable).resolve()
    if fallback.is_file():
        return fallback
    raise SystemExit(f"ERROR: python executable not found: {path}")


def capture_json_output(
    *,
    label: str,
    python_executable: Path,
    script_path: Path,
    argv: list[str],
) -> dict[str, Any]:
    completed = subprocess.run(
        [str(python_executable), str(script_path), *argv],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise SystemExit(
            f"ERROR: {label} exited with status {completed.returncode}: {stderr or completed.stdout.strip()}"
        )

    payload = completed.stdout.strip()
    if not payload:
        raise SystemExit(f"ERROR: {label} produced no JSON output")

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: {label} did not emit valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"ERROR: {label} emitted a non-object JSON payload")
    return parsed


def repo_native_optional(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    return sync_result.repo_native(Path(raw))


def summarize(
    *,
    args: argparse.Namespace,
    build_payload: dict[str, Any],
    sync_payload: dict[str, Any],
) -> dict[str, Any]:
    local_build_output = build_payload.get("local_build_output")
    if not isinstance(local_build_output, dict):
        local_build_output = {}

    artifact_path = sync_payload.get("artifact_path")
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        artifact_path = repo_native_optional(local_build_output.get("artifact_path"))

    report_json = repo_native_optional(sync_payload.get("report_json"))
    if report_json is None:
        report_json = repo_native_optional(local_build_output.get("report_path"))

    output_dir = repo_native_optional(local_build_output.get("output_dir"))
    bookkeeping_json = repo_native_optional(sync_payload.get("bookkeeping_json"))
    validation_report_template = repo_native_optional(
        sync_payload.get("validation_report_template")
    )
    latest_local_build_sync_snapshot = repo_native_optional(
        sync_payload.get("latest_local_build_sync_snapshot")
    )

    return {
        "status": "ok",
        "operator": build_payload.get("operator", local_build.seam_probe.DEFAULT_OPERATOR),
        "diagnostic_only": bool(sync_payload.get("diagnostic_only", True)),
        "local_only": True,
        "scaffold_dir": sync_result.repo_native(args.scaffold_dir),
        "build_output_dir": output_dir or sync_result.repo_native(args.output_dir),
        "artifact_path": artifact_path,
        "report_json": report_json,
        "artifact_sha256": sync_payload.get("artifact_sha256"),
        "bookkeeping_json": bookkeeping_json,
        "validation_report_template": validation_report_template,
        "latest_local_build_sync_snapshot": latest_local_build_sync_snapshot,
        "scaffold_readme": sync_result.repo_native(args.scaffold_dir / "README.md"),
        "report_id": build_payload.get("report_id"),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    python_executable = resolve_python_executable(args.python_executable)

    build_payload = capture_json_output(
        label="run_transpose1_post_db_local_build.py",
        python_executable=python_executable,
        script_path=Path(local_build.__file__).resolve(),
        argv=[
            "--task-summary",
            str(args.task_summary),
            "--database-dir",
            str(args.database_dir),
            "--candidate-impl",
            str(args.candidate_impl),
            "--output-dir",
            str(args.output_dir),
        ],
    )
    sync_payload = capture_json_output(
        label="sync_transpose1_post_db_local_build_result.py",
        python_executable=python_executable,
        script_path=Path(sync_result.__file__).resolve(),
        argv=[
            "--scaffold-dir",
            str(args.scaffold_dir),
            "--output-dir",
            str(args.output_dir),
        ],
    )
    payload = json.dumps(
        summarize(args=args, build_payload=build_payload, sync_payload=sync_payload),
        ensure_ascii=False,
    )
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
