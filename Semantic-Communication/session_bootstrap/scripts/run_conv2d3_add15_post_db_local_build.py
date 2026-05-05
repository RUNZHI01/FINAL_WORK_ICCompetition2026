#!/usr/bin/env python3
"""Run the fused_conv2d3_add15 post-DB schedule-preserving local build path.

This is a thin operator-specific wrapper over
`probe_transpose1_schedule_preserving_seam.py`. It exists so the preferred local
workflow for `fused_conv2d3_add15` does not require the user to repeat
best-staging task-summary / DB paths by hand.

This helper is still local-only and diagnostic-only:
- it does not launch remote work
- it does not make runtime/performance claims
- it only produces build-level evidence for the post-db scheduled swap path
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

OPERATOR_NAME = "fused_conv2d3_add15"
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
    / "tmp"
    / "conv2d3_add15_post_db_swap_local_build"
)
DEFAULT_CANDIDATE_IMPL = (
    Path(__file__).resolve().parents[1]
    / "handwritten"
    / OPERATOR_NAME
    / f"{OPERATOR_NAME}_scheduled_form_candidate_v1.py"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Operator-specific wrapper for the fused_conv2d3_add15 post-db "
            "scheduled swap local build path."
        )
    )
    parser.add_argument(
        "--task-summary",
        type=Path,
        default=DEFAULT_TASK_SUMMARY,
        help="Best-staging task_summary.json for fused_conv2d3_add15.",
    )
    parser.add_argument(
        "--database-dir",
        type=Path,
        default=DEFAULT_DATABASE_DIR,
        help="Best-staging tuning_logs directory for fused_conv2d3_add15.",
    )
    parser.add_argument(
        "--candidate-impl",
        type=Path,
        default=DEFAULT_CANDIDATE_IMPL,
        help="Checked-in scheduled-form v1 candidate entrypoint for the local post-db path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the local swapped artifact and adjacent JSON report.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional extra JSON report output path.",
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
    report = capture_probe_output(
        python_executable=python_executable,
        argv=[
            "--task-summary",
            str(args.task_summary),
            "--database-dir",
            str(args.database_dir),
            "--operator",
            OPERATOR_NAME,
            "--candidate-impl",
            str(args.candidate_impl),
            "--build-standalone-scheduled-task",
            "--output-dir",
            str(args.output_dir),
        ],
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    adjacent_report_path = None
    local_build_output = report.get("local_build_output")
    if isinstance(local_build_output, dict):
        report_path = local_build_output.get("report_path")
        if isinstance(report_path, str) and report_path.strip():
            adjacent_report_path = Path(report_path)
    seam_probe.write_report_outputs(
        payload,
        output_json=args.output_json,
        adjacent_report_path=adjacent_report_path,
    )
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
