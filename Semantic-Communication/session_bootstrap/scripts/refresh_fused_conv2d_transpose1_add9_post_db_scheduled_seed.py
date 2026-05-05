#!/usr/bin/env python3
"""Refresh the checked-in post-db scheduled reference seed for transpose1.

This helper stays intentionally narrow:
- it is local-only and diagnostic-only
- it reuses the existing post-db schedule-preserving seam
- it writes a clearly named scheduled-form reference/edit seed beside the older
  raw pre-compile seed without launching remote work
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

import probe_transpose1_schedule_preserving_seam as seam_probe

DEFAULT_PYTHON_EXECUTABLE = Path("/home/tianxing/.venvs/tvm-ms/bin/python")

DEFAULT_TASK_SUMMARY = (
    Path(__file__).resolve().parents[1]
    / "tmp"
    / "phytium_runtime_joint_top6_targeted_staging_search_20260330_2315"
    / "task_summary.json"
)
DEFAULT_DATABASE_DIR = (
    Path(__file__).resolve().parents[1]
    / "tmp"
    / "phytium_runtime_joint_top6_targeted_staging_search_20260330_2315"
    / "tuning_logs"
)
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "handwritten"
    / seam_probe.DEFAULT_OPERATOR
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the checked-in post-db scheduled reference seed for "
            f"{seam_probe.DEFAULT_OPERATOR}."
        )
    )
    parser.add_argument(
        "--task-summary",
        type=Path,
        default=DEFAULT_TASK_SUMMARY,
        help="Best-staging task_summary.json for transpose1.",
    )
    parser.add_argument(
        "--database-dir",
        type=Path,
        default=DEFAULT_DATABASE_DIR,
        help="Best-staging tuning_logs directory for transpose1.",
    )
    parser.add_argument(
        "--candidate-impl",
        type=Path,
        default=seam_probe.DEFAULT_CANDIDATE_IMPL,
        help="Checked-in handwritten candidate entrypoint used by the seam probe.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Checked-in handwritten directory that will receive the scheduled seed files.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional extra JSON summary output path.",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow overwriting the existing checked-in post-db scheduled seed files.",
    )
    parser.add_argument(
        "--python-executable",
        type=Path,
        default=DEFAULT_PYTHON_EXECUTABLE,
        help=(
            "Python executable used to run the underlying schedule-preserving seam probe. "
            "Defaults to the repo's TVM-enabled virtualenv interpreter."
        ),
    )
    return parser.parse_args(argv)


def ensure_clean_outputs(paths: list[Path], allow_overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not allow_overwrite:
        joined = "\n  ".join(str(path) for path in existing)
        raise SystemExit(
            "ERROR: output already exists. Re-run with --allow-overwrite to refresh.\n"
            f"  {joined}"
        )


def write_output_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")


def resolve_python_executable(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.is_file():
        return candidate
    fallback = Path(sys.executable).resolve()
    if fallback.is_file():
        return fallback
    raise SystemExit(f"ERROR: python executable not found: {path}")


def capture_probe_output(*, python_executable: Path, argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [str(python_executable), str(Path(seam_probe.__file__).resolve()), *argv],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise SystemExit(
            "ERROR: probe_transpose1_schedule_preserving_seam.py exited with status "
            f"{completed.returncode}: {stderr or completed.stdout.strip()}"
        )

    payload = completed.stdout.strip()
    if not payload:
        raise SystemExit("ERROR: probe_transpose1_schedule_preserving_seam.py produced no JSON output")

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"ERROR: probe_transpose1_schedule_preserving_seam.py did not emit valid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise SystemExit("ERROR: probe_transpose1_schedule_preserving_seam.py emitted a non-object JSON payload")
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    python_executable = resolve_python_executable(args.python_executable)
    seed_layout = seam_probe.build_post_db_scheduled_seed_layout(
        seam_probe.DEFAULT_OPERATOR,
        args.output_dir,
    )
    guarded_paths = [
        Path(str(seed_layout["reference_tir_path"])),
        Path(str(seed_layout["manifest_path"])),
    ]
    if args.output_json is not None:
        guarded_paths.append(args.output_json)
    ensure_clean_outputs(guarded_paths, args.allow_overwrite)

    report = capture_probe_output(
        python_executable=python_executable,
        argv=[
            "--task-summary",
            str(args.task_summary),
            "--database-dir",
            str(args.database_dir),
            "--candidate-impl",
            str(args.candidate_impl),
            "--build-standalone-scheduled-task",
            "--scheduled-seed-dir",
            str(args.output_dir),
        ],
    )
    scheduled_seed = report.get("post_db_scheduled_seed")
    if not isinstance(scheduled_seed, dict):
        raise SystemExit("ERROR: seam probe did not return post_db_scheduled_seed details")
    if scheduled_seed.get("status") != "written":
        raise SystemExit(
            "ERROR: failed to write the post-db scheduled seed: "
            f"{scheduled_seed.get('status')} "
            f"{scheduled_seed.get('error') or ''}".rstrip()
        )

    summary = {
        "status": "ok",
        "operator": report["operator"],
        "task_summary_json": report["task_summary_json"],
        "database_dir": report["database_dir"],
        "recommended_seam": report["recommended_seam"],
        "standalone_scheduled_task_build": report["standalone_scheduled_task_build"],
        "post_database_apply": report["post_database_apply"],
        "post_db_scheduled_seed": scheduled_seed,
        "diagnostic_only": True,
        "local_only": True,
    }
    payload = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        write_output_json(args.output_json, payload)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
