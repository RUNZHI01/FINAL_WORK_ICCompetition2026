#!/usr/bin/env python3
"""Orchestrate the minimal full-model A/B path for fused_conv2d_transpose_add6.

This wrapper stays deliberately narrow:
- build (or reuse) a full-model artifact produced by the existing post-db
  scheduled PrimFunc swap path for `fused_conv2d_transpose_add6`
- stage that artifact into a dedicated remote archive without touching Trusted Current
- run the existing payload and/or real-reconstruction A/B compare wrappers

It does not introduce a new runtime path. It only wires together the already
checked-in build/env/benchmark helpers around the smallest executable
full-model replacement experiment for transpose_add6.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_ROOT / "session_bootstrap" / "scripts"
TMP_DIR = PROJECT_ROOT / "session_bootstrap" / "tmp"
REPORT_DIR = PROJECT_ROOT / "session_bootstrap" / "reports"
LOG_DIR = PROJECT_ROOT / "session_bootstrap" / "logs"

DEFAULT_PYTHON_EXECUTABLE = Path("/home/tianxing/.venvs/tvm-ms/bin/python")
DEFAULT_TASK_SUMMARY = (
    TMP_DIR
    / "phytium_runtime_joint_top6_targeted_staging_search_20260330_2315"
    / "task_summary.json"
)
DEFAULT_DATABASE_DIR = (
    TMP_DIR
    / "phytium_runtime_joint_top6_targeted_staging_search_20260330_2315"
    / "tuning_logs"
)
DEFAULT_CANDIDATE_IMPL = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "handwritten"
    / "fused_conv2d_transpose_add6"
    / "fused_conv2d_transpose_add6_scheduled_form_candidate_v1.py"
)
DEFAULT_PAYLOAD_BASE_ENV = (
    TMP_DIR / "inference_compare_currentsafe_chunk4_refresh_20260313_1758.env"
)
DEFAULT_RECONSTRUCTION_BASE_ENV = (
    TMP_DIR
    / "inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.env"
)
DEFAULT_REMOTE_ARCHIVE_DIR = (
    "/home/user/Downloads/jscc-test/jscc_staging_handwritten_fused_conv2d_transpose_add6"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_report_prefix = f"transpose_add6_minimal_fullmodel_ab_{stamp}"
    default_work_dir = TMP_DIR / default_report_prefix
    default_local_build_output_dir = default_work_dir / "local_build"

    parser = argparse.ArgumentParser(
        description=(
            "Minimal full-model A/B path for fused_conv2d_transpose_add6: "
            "post-db local rebuild -> staged archive -> payload/reconstruction compare."
        )
    )
    parser.add_argument(
        "--candidate-impl",
        type=Path,
        default=DEFAULT_CANDIDATE_IMPL,
        help="Checked-in transpose_add6 post-db scheduled candidate wrapper.",
    )
    parser.add_argument(
        "--local-artifact",
        type=Path,
        help="Reuse an existing full-model artifact instead of rebuilding locally.",
    )
    parser.add_argument(
        "--task-summary",
        type=Path,
        default=DEFAULT_TASK_SUMMARY,
        help="Best-staging task_summary.json used by the local post-db rebuild helper.",
    )
    parser.add_argument(
        "--database-dir",
        type=Path,
        default=DEFAULT_DATABASE_DIR,
        help="Best-staging tuning_logs directory used for local rebuild and remote staging.",
    )
    parser.add_argument(
        "--local-build-output-dir",
        type=Path,
        default=default_local_build_output_dir,
        help="Output dir for the local full-model post-db swap artifact when --local-artifact is not supplied.",
    )
    parser.add_argument(
        "--payload-base-env",
        type=Path,
        default=DEFAULT_PAYLOAD_BASE_ENV,
        help="Payload A/B base env snapshot.",
    )
    parser.add_argument(
        "--reconstruction-base-env",
        type=Path,
        default=DEFAULT_RECONSTRUCTION_BASE_ENV,
        help="Real-reconstruction A/B base env snapshot.",
    )
    parser.add_argument(
        "--remote-archive-dir",
        default=DEFAULT_REMOTE_ARCHIVE_DIR,
        help="Dedicated remote staging archive for the transpose_add6 candidate.",
    )
    parser.add_argument(
        "--report-prefix",
        default=default_report_prefix,
        help="Prefix used for generated envs, logs, and compare reports.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=default_work_dir,
        help="Local work dir for generated envs and summary JSON.",
    )
    parser.add_argument(
        "--python-executable",
        type=Path,
        default=DEFAULT_PYTHON_EXECUTABLE,
        help="Python executable used for the existing local helper scripts.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Stop after local build + env preparation + exact next-command emission.",
    )
    parser.add_argument(
        "--skip-payload",
        action="store_true",
        help="Skip the payload A/B compare stage.",
    )
    parser.add_argument(
        "--skip-reconstruction",
        action="store_true",
        help="Skip the reconstruction A/B compare stage.",
    )
    return parser.parse_args(argv)


def require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"ERROR: {label} not found: {resolved}")
    return resolved


def require_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise SystemExit(f"ERROR: {label} not found: {resolved}")
    return resolved


def resolve_python_executable(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_file():
        return candidate
    fallback = Path(sys.executable).resolve()
    if fallback.is_file():
        return fallback
    raise SystemExit(f"ERROR: python executable not found: {path}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shell_join(argv: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def run_json_command(argv: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=str(cwd or PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise SystemExit(
            f"ERROR: command failed ({completed.returncode}): {shell_join(argv)}\n"
            f"{stderr or completed.stdout.strip()}"
        )
    payload = completed.stdout.strip()
    if not payload:
        raise SystemExit(f"ERROR: command produced no JSON output: {shell_join(argv)}")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as err:
        raise SystemExit(
            f"ERROR: command did not emit valid JSON: {shell_join(argv)}\n{payload}"
        ) from err
    if not isinstance(parsed, dict):
        raise SystemExit(f"ERROR: expected JSON object from: {shell_join(argv)}")
    return parsed


def run_streaming_command(argv: list[str], *, cwd: Path | None = None) -> None:
    completed = subprocess.run(
        argv,
        cwd=str(cwd or PROJECT_ROOT),
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"ERROR: command failed ({completed.returncode}): {shell_join(argv)}"
        )


def run_key_value_command(argv: list[str], *, cwd: Path | None = None) -> dict[str, str]:
    completed = subprocess.run(
        argv,
        cwd=str(cwd or PROJECT_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise SystemExit(
            f"ERROR: command failed ({completed.returncode}): {shell_join(argv)}\n"
            f"{stderr or completed.stdout.strip()}"
        )

    result: dict[str, str] = {}
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    if not result:
        raise SystemExit(f"ERROR: command produced no key=value output: {shell_join(argv)}")
    return result


def append_env_overrides(
    *,
    source_env: Path,
    output_env: Path,
    overrides: dict[str, str],
) -> None:
    text = source_env.read_text(encoding="utf-8")
    lines = [text.rstrip(), ""]
    for key, value in overrides.items():
        lines.append(f"{key}={shlex.quote(value)}")
    output_env.parent.mkdir(parents=True, exist_ok=True)
    output_env.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepared_report_path(run_id: str) -> Path:
    return REPORT_DIR / f"{run_id}.md"


def prepared_log_path(run_id: str) -> Path:
    return LOG_DIR / f"{run_id}.log"


def prepare_env(
    *,
    python_executable: Path,
    base_env: Path,
    output_env: Path,
    remote_archive_dir: str,
    expected_sha256: str,
) -> dict[str, Any]:
    return run_key_value_command(
        [
            str(python_executable),
            str(SCRIPT_DIR / "prepare_handwritten_fused_conv2d_transpose_add6_env.py"),
            "--base-env",
            str(base_env),
            "--output-env",
            str(output_env),
            "--staging-archive",
            remote_archive_dir,
            "--expected-sha256",
            expected_sha256,
        ]
    )


def build_or_resolve_artifact(args: argparse.Namespace, python_executable: Path) -> dict[str, Any]:
    if args.local_artifact is not None:
        artifact_path = require_file(args.local_artifact, "local artifact")
        return {
            "mode": "reuse_existing",
            "artifact_path": str(artifact_path),
            "artifact_sha256": file_sha256(artifact_path),
            "build_report": None,
        }

    candidate_impl = require_file(args.candidate_impl, "candidate impl")
    task_summary = require_file(args.task_summary, "task summary")
    database_dir = require_dir(args.database_dir, "database dir")

    build_payload = run_json_command(
        [
            str(python_executable),
            str(SCRIPT_DIR / "run_transpose_add6_post_db_local_build.py"),
            "--task-summary",
            str(task_summary),
            "--database-dir",
            str(database_dir),
            "--candidate-impl",
            str(candidate_impl),
            "--output-dir",
            str(args.local_build_output_dir.resolve()),
        ]
    )
    local_build_output = build_payload.get("local_build_output")
    if not isinstance(local_build_output, dict):
        raise SystemExit("ERROR: local build helper did not return local_build_output")
    artifact_path_raw = local_build_output.get("artifact_path")
    artifact_sha256 = local_build_output.get("artifact_sha256")
    if not isinstance(artifact_path_raw, str) or not artifact_path_raw.strip():
        raise SystemExit("ERROR: local build helper did not return artifact_path")
    artifact_path = require_file(Path(artifact_path_raw), "local build artifact")
    if not isinstance(artifact_sha256, str) or not artifact_sha256.strip():
        artifact_sha256 = file_sha256(artifact_path)

    return {
        "mode": "local_post_db_rebuild",
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256,
        "build_report": build_payload,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    python_executable = resolve_python_executable(args.python_executable)
    payload_base_env = require_file(args.payload_base_env, "payload base env")
    reconstruction_base_env = require_file(
        args.reconstruction_base_env,
        "reconstruction base env",
    )
    require_dir(args.database_dir, "database dir")
    args.work_dir = args.work_dir.expanduser().resolve()
    args.work_dir.mkdir(parents=True, exist_ok=True)

    artifact_info = build_or_resolve_artifact(args, python_executable)
    artifact_path = require_file(Path(artifact_info["artifact_path"]), "candidate artifact")
    artifact_sha256 = str(artifact_info["artifact_sha256"])

    payload_prepared_env = args.work_dir / "payload_prepared.env"
    payload_env_meta = prepare_env(
        python_executable=python_executable,
        base_env=payload_base_env,
        output_env=payload_prepared_env,
        remote_archive_dir=args.remote_archive_dir,
        expected_sha256=artifact_sha256,
    )
    reconstruction_prepared_env = args.work_dir / "reconstruction_prepared.env"
    reconstruction_env_meta = prepare_env(
        python_executable=python_executable,
        base_env=reconstruction_base_env,
        output_env=reconstruction_prepared_env,
        remote_archive_dir=args.remote_archive_dir,
        expected_sha256=artifact_sha256,
    )

    payload_run_id = f"{args.report_prefix}_payload_ab"
    payload_run_env = args.work_dir / "payload_compare.env"
    append_env_overrides(
        source_env=payload_prepared_env,
        output_env=payload_run_env,
        overrides={
            "INFERENCE_EXECUTION_ID": payload_run_id,
            "ALLOW_REPORT_OVERWRITE": "0",
        },
    )

    reconstruction_run_id = f"{args.report_prefix}_reconstruction_ab"
    reconstruction_run_env = args.work_dir / "reconstruction_compare.env"
    append_env_overrides(
        source_env=reconstruction_prepared_env,
        output_env=reconstruction_run_env,
        overrides={
            "INFERENCE_EXECUTION_ID": reconstruction_run_id,
            "INFERENCE_OUTPUT_PREFIX": reconstruction_run_id,
            "INFERENCE_LEGACY_OUTPUT_PREFIX": reconstruction_run_id,
            "ALLOW_REPORT_OVERWRITE": "0",
        },
    )

    upload_command = [
        "bash",
        str(SCRIPT_DIR / "run_transpose_add6_remote_payload_benchmark.sh"),
        "--inference-env",
        str(payload_run_env),
        "--local-artifact",
        str(artifact_path),
        "--database-dir",
        str(args.database_dir),
        "--remote-archive-dir",
        args.remote_archive_dir,
        "--upload-only",
    ]
    payload_compare_command = [
        "bash",
        str(SCRIPT_DIR / "run_inference_benchmark.sh"),
        "--env",
        str(payload_run_env),
    ]
    reconstruction_compare_command = [
        "bash",
        str(SCRIPT_DIR / "run_inference_benchmark.sh"),
        "--env",
        str(reconstruction_run_env),
    ]

    summary: dict[str, Any] = {
        "status": "prepared_only" if args.prepare_only else "prepared",
        "operator": "fused_conv2d_transpose_add6",
        "minimal_integration_path": [
            "post_db_scheduled_primfunc_swap_fullmodel_rebuild",
            "dedicated_remote_staging_archive_upload",
            "payload_ab_via_run_inference_benchmark",
            "reconstruction_ab_via_run_inference_benchmark",
        ],
        "artifact": {
            "mode": artifact_info["mode"],
            "path": str(artifact_path),
            "sha256": artifact_sha256,
        },
        "local_build_report": artifact_info["build_report"],
        "prepared_envs": {
            "payload_prepared_env": str(payload_prepared_env),
            "reconstruction_prepared_env": str(reconstruction_prepared_env),
            "payload_run_env": str(payload_run_env),
            "reconstruction_run_env": str(reconstruction_run_env),
            "payload_meta": payload_env_meta,
            "reconstruction_meta": reconstruction_env_meta,
        },
        "remote_archive_dir": args.remote_archive_dir,
        "expected_reports": {
            "payload": str(prepared_report_path(payload_run_id)),
            "reconstruction": str(prepared_report_path(reconstruction_run_id)),
        },
        "expected_logs": {
            "payload": str(prepared_log_path(payload_run_id)),
            "reconstruction": str(prepared_log_path(reconstruction_run_id)),
        },
        "commands": {
            "upload_only": shell_join(upload_command),
            "payload_compare": shell_join(payload_compare_command),
            "reconstruction_compare": shell_join(reconstruction_compare_command),
        },
        "acl_integration_blocker": (
            "The current executable seam can only replace a TVM PrimFunc inside the "
            "post-db applied full module. There is no checked-in extern/packed-func "
            "bridge that lets compile_relax or relax.build swap transpose_add6 to an "
            "ACL kernel while preserving the rest of the model ABI."
        ),
    }

    if not args.prepare_only:
        upload_result = run_json_command(upload_command)
        summary["upload_result"] = upload_result

        if not args.skip_payload:
            run_streaming_command(payload_compare_command)
            summary["payload_compare_status"] = "completed"
        else:
            summary["payload_compare_status"] = "skipped"

        if not args.skip_reconstruction:
            run_streaming_command(reconstruction_compare_command)
            summary["reconstruction_compare_status"] = "completed"
        else:
            summary["reconstruction_compare_status"] = "skipped"

        summary["status"] = "completed"

    summary_path = args.work_dir / "summary.json"
    summary["summary_json"] = str(summary_path)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
