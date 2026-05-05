#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import shlex
import stat
import subprocess
import sys
import time
from hashlib import sha256


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REBUILD_ENV = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "config"
    / "rpc_tune_rebuild_current_safe.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
)
DEFAULT_RPC_TUNE = PROJECT_ROOT / "session_bootstrap" / "scripts" / "rpc_tune.py"
DEFAULT_PAYLOAD_RUNNER = (
    PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_remote_tvm_inference_payload.sh"
)
DEFAULT_REPORT_PREFIX = "baseline_export_bridge"
DEFAULT_EXPECTED_OUTPUT_SHAPE = [1, 3, 256, 256]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild a current-safe baseline replacement candidate from a supplied "
            "lineage DB/archive snapshot, package a standalone archive, run a local "
            "payload probe, and emit the remaining board-stage upload/probe script."
        )
    )
    parser.add_argument(
        "--rebuild-env",
        type=Path,
        default=DEFAULT_REBUILD_ENV,
        help="Current-safe rebuild env used for local builder/runtime settings.",
    )
    parser.add_argument(
        "--source-db",
        type=Path,
        help="Local tuning_logs directory to treat as the baseline lineage source.",
    )
    parser.add_argument(
        "--source-archive",
        type=Path,
        help=(
            "Local baseline archive snapshot root. The helper reads "
            "tuning_logs/database_*.json from this archive."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Output root for rebuilt files and the packaged baseline candidate "
            "archive. Defaults to session_bootstrap/tmp/<report_id>."
        ),
    )
    parser.add_argument(
        "--report-id",
        help=f"Report prefix. Defaults to {DEFAULT_REPORT_PREFIX}_<timestamp>.",
    )
    parser.add_argument(
        "--target",
        help="Override the current-safe target JSON from the rebuild env.",
    )
    parser.add_argument(
        "--entry",
        default="main",
        help="Relax VM entry to probe. Default: main.",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=0,
        help="Local payload probe warmup count. Default: 0.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Local payload probe repeat count. Default: 1.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Local payload probe device. Default: cpu.",
    )
    parser.add_argument(
        "--expected-output-shape",
        default="1,3,256,256",
        help=(
            "Comma-separated expected current-safe output contract. "
            "Default: 1,3,256,256."
        ),
    )
    parser.add_argument(
        "--remote-archive-dir",
        help=(
            "Override the remote archive dir used by the generated board-stage "
            "script. Defaults to a separate baseline_current_safe_bridge dir."
        ),
    )
    parser.add_argument(
        "--rpc-tune-script",
        type=Path,
        default=DEFAULT_RPC_TUNE,
        help="Override rpc_tune.py path.",
    )
    parser.add_argument(
        "--payload-runner",
        type=Path,
        default=DEFAULT_PAYLOAD_RUNNER,
        help="Override payload runner path.",
    )
    args = parser.parse_args(argv)
    if args.warmup_runs < 0:
        raise SystemExit("ERROR: --warmup-runs must be >= 0.")
    if args.repeat < 0:
        raise SystemExit("ERROR: --repeat must be >= 0.")
    return args


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def require_dir(path: Path, label: str) -> Path:
    if not path.is_dir():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def parse_shell_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def resolve_project_path(raw_path: str | None) -> Path:
    if not raw_path:
        return Path()
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def require_db_dir(path: Path, label: str) -> Path:
    directory = require_dir(path, label)
    for file_name in ("database_workload.json", "database_tuning_record.json"):
        require_file(directory / file_name, f"{label} file")
    return directory


def parse_shape_csv(raw_shape: str) -> list[int]:
    dims = [item.strip() for item in raw_shape.split(",") if item.strip()]
    if not dims or not all(item.isdigit() for item in dims):
        raise SystemExit(f"ERROR: invalid shape csv: {raw_shape}")
    return [int(item) for item in dims]


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_workload_record_json(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    record = json.loads(first_line)
    if not isinstance(record, list) or len(record) < 2 or not isinstance(record[1], str):
        raise SystemExit(f"ERROR: unexpected workload record format in {path}")
    payload = record[1]
    padding = "=" * ((4 - len(payload) % 4) % 4)
    raw = base64.b64decode(payload + padding)
    if len(raw) < 8:
        raise SystemExit(f"ERROR: decoded workload payload too short in {path}")
    return raw[8:].decode("utf-8", errors="replace")


def validate_source_db_compatibility(path: Path) -> None:
    workload_path = path / "database_workload.json"
    decoded = decode_workload_record_json(workload_path)
    if '"root_index"' in decoded:
        return
    if '"root"' in decoded:
        probe_script = (
            PROJECT_ROOT
            / "session_bootstrap"
            / "scripts"
            / "probe_legacy_baseline_db_bridge.py"
        )
        raise SystemExit(
            "ERROR: baseline lineage DB uses an older JSON object-graph format "
            "(decoded workload has `root` but not `root_index`), so current-safe "
            "rpc_tune.py cannot consume it directly. You need a format bridge or a "
            "different baseline export path before build_baseline_export_bridge.py can proceed.\n"
            f"Next: run /home/tianxing/.venvs/tvm-ms/bin/python {probe_script} "
            f"--source-db {path}"
        )
    raise SystemExit(
        "ERROR: unable to confirm current-safe JSONDatabase compatibility for source DB "
        f"{path}; decoded workload record lacks both `root_index` and legacy `root`."
    )


def extract_last_json_payload(path: Path) -> dict[str, object]:
    for raw_line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise SystemExit(f"ERROR: no JSON payload found in log: {path}")


def resolve_source_db(args: argparse.Namespace, env_vars: dict[str, str]) -> tuple[Path, Path | None]:
    if args.source_db is not None:
        return require_db_dir(args.source_db, "source db"), None

    if args.source_archive is not None:
        archive_root = require_dir(args.source_archive, "source archive")
        return require_db_dir(archive_root / "tuning_logs", "source archive tuning_logs"), archive_root

    hinted_archive = env_vars.get("REMOTE_TVM_PRIMARY_DIR")
    if hinted_archive:
        hinted_path = Path(hinted_archive)
        if hinted_path.is_dir():
            archive_root = require_dir(hinted_path, "baseline archive from rebuild env")
            return require_db_dir(
                archive_root / "tuning_logs",
                "baseline archive tuning_logs from rebuild env",
            ), archive_root

    message = (
        "ERROR: no local baseline lineage DB is available. Pass --source-db "
        "<local tuning_logs> or --source-archive <local baseline archive snapshot>. "
    )
    if hinted_archive:
        message += (
            "The rebuild env points at a remote-only baseline archive path: "
            f"{hinted_archive}"
        )
    raise SystemExit(message)


def resolve_remote_archive_dir(
    env_vars: dict[str, str],
    report_id: str,
    override: str | None,
) -> str:
    if override:
        return override
    primary_dir = env_vars.get("REMOTE_TVM_PRIMARY_DIR")
    current_dir = env_vars.get("REMOTE_TVM_JSCC_BASE_DIR")
    if primary_dir:
        base = PurePosixPath(primary_dir).parent
    elif current_dir:
        base = PurePosixPath(current_dir).parent
    else:
        base = PurePosixPath("/home/user/Downloads")
    return str(base / "baseline_current_safe_bridge" / report_id)


def run_and_log(
    cmd: list[str],
    *,
    log_path: Path,
    env: dict[str, str] | None = None,
) -> None:
    with log_path.open("w", encoding="utf-8") as logfile:
        completed = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=logfile,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode != 0:
        raise SystemExit(
            f"ERROR: command failed rc={completed.returncode}: {' '.join(shlex.quote(arg) for arg in cmd)}\n"
            f"See log: {log_path}"
        )


def build_candidate_archive(
    *,
    archive_root: Path,
    optimized_model_so: Path,
    tuning_logs_dir: Path,
) -> None:
    model_dir = archive_root / "tvm_tune_logs"
    candidate_db_dir = archive_root / "tuning_logs"
    model_dir.mkdir(parents=True, exist_ok=True)
    candidate_db_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(optimized_model_so, model_dir / "optimized_model.so")
    shutil.copy2(
        tuning_logs_dir / "database_workload.json",
        candidate_db_dir / "database_workload.json",
    )
    shutil.copy2(
        tuning_logs_dir / "database_tuning_record.json",
        candidate_db_dir / "database_tuning_record.json",
    )


def write_board_stage_script(
    *,
    output_path: Path,
    local_archive_root: Path,
    remote_archive_dir: str,
    env_vars: dict[str, str],
    input_shape: str,
    input_dtype: str,
    entry: str,
    warmup_runs: int,
    repeat: int,
    device: str,
    expected_sha256: str,
) -> None:
    remote_host = env_vars.get("REMOTE_HOST", "")
    remote_user = env_vars.get("REMOTE_USER", "")
    remote_pass = env_vars.get("REMOTE_PASS", "")
    remote_port = env_vars.get("REMOTE_SSH_PORT", "22")
    remote_tvm_python = env_vars.get("REMOTE_TVM_PYTHON", "")
    payload_runner = PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_remote_tvm_inference_payload.sh"
    ssh_wrapper = PROJECT_ROOT / "session_bootstrap" / "scripts" / "ssh_with_password.sh"

    lines = [
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "",
        f"PROJECT_ROOT={shlex.quote(str(PROJECT_ROOT))}",
        f"SSH_SCRIPT={shlex.quote(str(ssh_wrapper))}",
        f"PAYLOAD_RUNNER={shlex.quote(str(payload_runner))}",
        f"LOCAL_ARCHIVE_ROOT={shlex.quote(str(local_archive_root))}",
        f"REMOTE_ARCHIVE_DIR={shlex.quote(remote_archive_dir)}",
        f"REMOTE_HOST={shlex.quote(remote_host)}",
        f"REMOTE_USER={shlex.quote(remote_user)}",
        f"REMOTE_PASS={shlex.quote(remote_pass)}",
        f"REMOTE_PORT={shlex.quote(remote_port)}",
        f"REMOTE_TVM_PYTHON={shlex.quote(remote_tvm_python)}",
        f"INPUT_SHAPE={shlex.quote(input_shape)}",
        f"INPUT_DTYPE={shlex.quote(input_dtype)}",
        f"ENTRY_NAME={shlex.quote(entry)}",
        f"WARMUP_RUNS={warmup_runs}",
        f"REPEAT_COUNT={repeat}",
        f"DEVICE_NAME={shlex.quote(device)}",
        f"EXPECTED_SHA256={shlex.quote(expected_sha256)}",
        "",
        "shell_quote() {",
        "  printf \"'%s'\" \"$(printf '%s' \"$1\" | sed \"s/'/'\\\\''/g\")\"",
        "}",
        "",
        "upload_file() {",
        "  local src_path=\"$1\"",
        "  local dst_path=\"$2\"",
        "  bash \"$SSH_SCRIPT\" \\",
        "    --host \"$REMOTE_HOST\" \\",
        "    --user \"$REMOTE_USER\" \\",
        "    --pass \"$REMOTE_PASS\" \\",
        "    --port \"$REMOTE_PORT\" \\",
        "    -- \"mkdir -p $(shell_quote \"$(dirname \"$dst_path\")\") && cat > $(shell_quote \"$dst_path\")\" \\",
        "    <\"$src_path\"",
        "}",
        "",
        "upload_file \"$LOCAL_ARCHIVE_ROOT/tvm_tune_logs/optimized_model.so\" \"$REMOTE_ARCHIVE_DIR/tvm_tune_logs/optimized_model.so\"",
        "upload_file \"$LOCAL_ARCHIVE_ROOT/tuning_logs/database_workload.json\" \"$REMOTE_ARCHIVE_DIR/tuning_logs/database_workload.json\"",
        "upload_file \"$LOCAL_ARCHIVE_ROOT/tuning_logs/database_tuning_record.json\" \"$REMOTE_ARCHIVE_DIR/tuning_logs/database_tuning_record.json\"",
        "",
        "export REMOTE_MODE=ssh",
        "export REMOTE_HOST",
        "export REMOTE_USER",
        "export REMOTE_PASS",
        "export REMOTE_SSH_PORT=\"$REMOTE_PORT\"",
        "export REMOTE_TVM_PYTHON",
        "export INFERENCE_BASELINE_ARCHIVE=\"$REMOTE_ARCHIVE_DIR\"",
        "export INFERENCE_BASELINE_EXPECTED_SHA256=\"$EXPECTED_SHA256\"",
        "export TUNE_INPUT_SHAPE=\"$INPUT_SHAPE\"",
        "export TUNE_INPUT_DTYPE=\"$INPUT_DTYPE\"",
        "export INFERENCE_ENTRY=\"$ENTRY_NAME\"",
        "export INFERENCE_WARMUP_RUNS=\"$WARMUP_RUNS\"",
        "export INFERENCE_REPEAT=\"$REPEAT_COUNT\"",
        "export INFERENCE_DEVICE=\"$DEVICE_NAME\"",
        "",
        "bash \"$PAYLOAD_RUNNER\" --variant baseline",
        "",
        "echo",
        "echo \"If the baseline candidate reports [1,3,256,256], rerun the fair compare with this archive as baseline.\"",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    current_mode = output_path.stat().st_mode
    output_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_summary_markdown(
    *,
    output_path: Path,
    summary: dict[str, object],
) -> None:
    source = summary["source_lineage"]
    build = summary["local_build"]
    candidate = summary["candidate_archive"]
    probe = summary["local_current_safe_probe"]
    board = summary["board_stage"]
    output_path.write_text(
        "\n".join(
            [
                "# Baseline export bridge summary",
                "",
                f"- report_id: {summary['report_id']}",
                f"- rebuild_env: {summary['rebuild_env']}",
                f"- source_db: {source['source_db']}",
                f"- source_archive: {source['source_archive']}",
                f"- source_db_sha256_workload: {source['database_workload_sha256']}",
                f"- source_db_sha256_tuning_record: {source['database_tuning_record_sha256']}",
                "",
                "## Local build",
                "",
                f"- local_builder_python: {build['builder_python']}",
                f"- onnx_model: {build['onnx_model']}",
                f"- target: {build['target']}",
                f"- optimized_model_so: {build['optimized_model_so']}",
                f"- optimized_model_sha256: {build['optimized_model_sha256']}",
                f"- optimized_model_size_bytes: {build['optimized_model_size_bytes']}",
                f"- tune_report: {build['tune_report']}",
                f"- task_summary_json: {build['task_summary_json']}",
                "",
                "## Candidate archive",
                "",
                f"- archive_root: {candidate['archive_root']}",
                f"- artifact_path: {candidate['artifact_path']}",
                f"- artifact_sha256: {candidate['artifact_sha256']}",
                f"- artifact_size_bytes: {candidate['artifact_size_bytes']}",
                "",
                "## Local current-safe probe",
                "",
                f"- payload_log: {probe['payload_log']}",
                f"- status: {probe['status']}",
                f"- output_shape: {json.dumps(probe['output_shape'], ensure_ascii=False)}",
                f"- output_dtype: {probe['output_dtype']}",
                f"- expected_output_shape: {json.dumps(probe['expected_output_shape'], ensure_ascii=False)}",
                f"- output_contract_match: {probe['output_contract_match']}",
                "",
                "## Board stage",
                "",
                f"- remote_archive_dir: {board['remote_archive_dir']}",
                f"- board_stage_script: {board['board_stage_script']}",
                "",
                "## Next step",
                "",
                f"- {summary['next_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rebuild_env = require_file(args.rebuild_env, "rebuild env")
    rpc_tune_script = require_file(args.rpc_tune_script, "rpc tune script")
    payload_runner = require_file(args.payload_runner, "payload runner")
    env_vars = parse_shell_env(rebuild_env)

    source_db_dir, source_archive = resolve_source_db(args, env_vars)
    validate_source_db_compatibility(source_db_dir)

    local_builder_python = resolve_project_path(
        env_vars.get("LOCAL_TVM_PYTHON") or env_vars.get("TVM_PYTHON")
    )
    require_file(local_builder_python, "local builder python")
    onnx_model = require_file(
        resolve_project_path(env_vars.get("ONNX_MODEL_PATH")),
        "onnx model",
    )
    target = args.target or env_vars.get("TARGET")
    if not target:
        raise SystemExit("ERROR: TARGET missing from rebuild env; pass --target.")
    input_shape = env_vars.get("TUNE_INPUT_SHAPE")
    input_name = env_vars.get("TUNE_INPUT_NAME", "input")
    input_dtype = env_vars.get("TUNE_INPUT_DTYPE", "float32")
    if not input_shape:
        raise SystemExit("ERROR: TUNE_INPUT_SHAPE missing from rebuild env.")
    expected_output_shape = parse_shape_csv(args.expected_output_shape)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    report_id = args.report_id or f"{DEFAULT_REPORT_PREFIX}_{stamp}"
    output_root = args.output_dir or (
        PROJECT_ROOT / "session_bootstrap" / "tmp" / report_id
    )
    output_root.mkdir(parents=True, exist_ok=True)
    build_output_dir = output_root / "build_output"
    candidate_archive_root = output_root / "baseline_candidate_archive"

    logs_dir = PROJECT_ROOT / "session_bootstrap" / "logs"
    reports_dir = PROJECT_ROOT / "session_bootstrap" / "reports"
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    build_log = logs_dir / f"{report_id}.build.log"
    payload_log = logs_dir / f"{report_id}.local_probe.log"
    summary_json = reports_dir / f"{report_id}.json"
    summary_md = reports_dir / f"{report_id}.md"
    board_stage_script = reports_dir / f"{report_id}_board_stage.sh"

    build_cmd = [
        str(local_builder_python),
        str(rpc_tune_script),
        "--onnx-path",
        str(onnx_model),
        "--output-dir",
        str(build_output_dir),
        "--target",
        target,
        "--input-shape",
        input_shape,
        "--input-name",
        input_name,
        "--input-dtype",
        input_dtype,
        "--runner",
        "local",
        "--total-trials",
        "0",
        "--existing-db",
        str(source_db_dir),
        "--session-timeout",
        env_vars.get("TUNE_SESSION_TIMEOUT", "120"),
        "--num-trials-per-iter",
        env_vars.get("TUNE_NUM_TRIALS_PER_ITER", "64"),
    ]
    run_and_log(build_cmd, log_path=build_log)

    optimized_model_so = require_file(
        build_output_dir / "optimized_model.so",
        "rebuilt optimized_model.so",
    )
    tuning_logs_dir = require_db_dir(
        build_output_dir / "tuning_logs",
        "rebuilt tuning_logs",
    )
    build_candidate_archive(
        archive_root=candidate_archive_root,
        optimized_model_so=optimized_model_so,
        tuning_logs_dir=tuning_logs_dir,
    )

    candidate_artifact = require_file(
        candidate_archive_root / "tvm_tune_logs" / "optimized_model.so",
        "candidate archive optimized_model.so",
    )
    candidate_sha256 = file_sha256(candidate_artifact)

    probe_env = os.environ.copy()
    probe_env.update(
        {
            "REMOTE_MODE": "local",
            "REMOTE_TVM_PYTHON": str(local_builder_python),
            "INFERENCE_BASELINE_ARCHIVE": str(candidate_archive_root),
            "INFERENCE_BASELINE_EXPECTED_SHA256": candidate_sha256,
            "TUNE_INPUT_SHAPE": input_shape,
            "TUNE_INPUT_DTYPE": input_dtype,
            "INFERENCE_ENTRY": args.entry,
            "INFERENCE_WARMUP_RUNS": str(args.warmup_runs),
            "INFERENCE_REPEAT": str(args.repeat),
            "INFERENCE_DEVICE": args.device,
        }
    )
    run_and_log(
        ["bash", str(payload_runner), "--variant", "baseline"],
        log_path=payload_log,
        env=probe_env,
    )
    probe_payload = extract_last_json_payload(payload_log)
    probe_output_shape = probe_payload.get("output_shape")
    output_contract_match = probe_output_shape == expected_output_shape

    remote_archive_dir = resolve_remote_archive_dir(
        env_vars,
        report_id,
        args.remote_archive_dir,
    )
    write_board_stage_script(
        output_path=board_stage_script,
        local_archive_root=candidate_archive_root,
        remote_archive_dir=remote_archive_dir,
        env_vars=env_vars,
        input_shape=input_shape,
        input_dtype=input_dtype,
        entry=args.entry,
        warmup_runs=args.warmup_runs,
        repeat=args.repeat,
        device=args.device,
        expected_sha256=candidate_sha256,
    )

    tune_report_path = build_output_dir / "tune_report.json"
    task_summary_path = build_output_dir / "task_summary.json"
    tune_report = {}
    if tune_report_path.is_file():
        tune_report = json.loads(tune_report_path.read_text(encoding="utf-8"))

    summary: dict[str, object] = {
        "mode": "baseline_export_bridge_current_safe_local",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "report_id": report_id,
        "rebuild_env": str(rebuild_env),
        "source_lineage": {
            "source_db": str(source_db_dir),
            "source_archive": None if source_archive is None else str(source_archive),
            "database_workload_sha256": file_sha256(source_db_dir / "database_workload.json"),
            "database_tuning_record_sha256": file_sha256(
                source_db_dir / "database_tuning_record.json"
            ),
        },
        "local_build": {
            "builder_python": str(local_builder_python),
            "onnx_model": str(onnx_model),
            "target": target,
            "output_dir": str(build_output_dir),
            "optimized_model_so": str(optimized_model_so),
            "optimized_model_sha256": file_sha256(optimized_model_so),
            "optimized_model_size_bytes": optimized_model_so.stat().st_size,
            "tune_report": str(tune_report_path) if tune_report_path.is_file() else None,
            "task_summary_json": str(task_summary_path) if task_summary_path.is_file() else None,
            "tune_report_runner": tune_report.get("runner"),
            "tune_report_total_trials": tune_report.get("total_trials"),
            "rebuild_log": str(build_log),
        },
        "candidate_archive": {
            "archive_root": str(candidate_archive_root),
            "artifact_path": str(candidate_artifact),
            "artifact_sha256": candidate_sha256,
            "artifact_size_bytes": candidate_artifact.stat().st_size,
            "database_workload_json": str(candidate_archive_root / "tuning_logs" / "database_workload.json"),
            "database_tuning_record_json": str(
                candidate_archive_root / "tuning_logs" / "database_tuning_record.json"
            ),
        },
        "local_current_safe_probe": {
            "status": "current_safe_probe_succeeded",
            "payload_log": str(payload_log),
            "output_shape": probe_output_shape,
            "output_dtype": probe_payload.get("output_dtype"),
            "expected_output_shape": expected_output_shape,
            "output_contract_match": output_contract_match,
            "payload": probe_payload,
        },
        "board_stage": {
            "remote_archive_dir": remote_archive_dir,
            "board_stage_script": str(board_stage_script),
        },
        "next_step": (
            "Run the generated board-stage script to upload this candidate archive to "
            f"{remote_archive_dir} and probe it under the current-safe runtime on the Pi. "
            "If that probe still returns [1, 3, 256, 256], rerun the fair compare with "
            "this archive as baseline."
        ),
    }

    summary_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_summary_markdown(output_path=summary_md, summary=summary)

    if not output_contract_match:
        raise SystemExit(
            "ERROR: local current-safe probe completed but did not match the expected "
            f"output contract {expected_output_shape}. See {summary_json}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
