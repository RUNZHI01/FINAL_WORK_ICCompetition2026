#!/usr/bin/env python3
"""Task 5.1 operator-level profiling entrypoint for the trusted current path."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SESSION_DIR = SCRIPT_DIR.parent
PROJECT_DIR = SESSION_DIR.parent

DEFAULT_REPORT_DIR = SESSION_DIR / "reports"
DEFAULT_LOG_DIR = SESSION_DIR / "logs"
DEFAULT_HOTSPOT_ENV = (
    SESSION_DIR
    / "config"
    / "rpc_tune_current_safe.baseline_seeded_warm_start.recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
)
DEFAULT_TRUSTED_ENV = SESSION_DIR / "tmp" / "inference_real_reconstruction_compare_run_20260311_212301.env"
DEFAULT_HOTSPOT_JSON = DEFAULT_REPORT_DIR / "hotspot_tasks_20260311_0008.json"
DEFAULT_HOTSPOT_MD = DEFAULT_REPORT_DIR / "hotspot_tasks_20260311_0008.md"

EXTRACT_SCRIPT = SCRIPT_DIR / "extract_hotspot_tasks.py"
TRUSTED_RUNTIME_SCRIPT = SCRIPT_DIR / "run_remote_current_real_reconstruction.sh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Practical task-5.1 operator profiling wrapper. Separates task-stage hotspot extraction "
            "from a runtime profiling attempt on the trusted current TVM path."
        )
    )
    parser.add_argument("--run-id", help="Override the full run_id.")
    parser.add_argument(
        "--label",
        default="trusted_current",
        help="Short label embedded in the default run_id.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help="Directory for markdown/json reports.",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Directory for wrapper logs.",
    )
    parser.add_argument(
        "--hotspot-mode",
        choices=("auto", "extract", "reuse", "skip"),
        default="auto",
        help="How to obtain task-stage hotspot evidence.",
    )
    parser.add_argument(
        "--hotspot-env",
        default=str(DEFAULT_HOTSPOT_ENV),
        help="MetaSchedule env file used by extract_hotspot_tasks.py.",
    )
    parser.add_argument(
        "--hotspot-existing-json",
        default="",
        help="Existing hotspot JSON to reuse when extraction is skipped or unavailable.",
    )
    parser.add_argument(
        "--hotspot-existing-md",
        default="",
        help="Existing hotspot markdown to reuse alongside --hotspot-existing-json.",
    )
    parser.add_argument("--hotspot-top-k", type=int, default=8, help="Top-k hotspot tasks to keep.")
    parser.add_argument(
        "--runtime-mode",
        choices=("auto", "attempt", "skip"),
        default="auto",
        help="Whether to attempt runtime/operator profiling on the trusted path.",
    )
    parser.add_argument(
        "--trusted-env",
        default=str(DEFAULT_TRUSTED_ENV),
        help="Trusted inference env file used for the current TVM path.",
    )
    parser.add_argument(
        "--trusted-variant",
        choices=("current", "baseline"),
        default="current",
        help="Trusted runtime variant to execute.",
    )
    parser.add_argument(
        "--max-inputs",
        type=int,
        default=1,
        help="Number of latent inputs to process for the runtime attempt.",
    )
    parser.add_argument(
        "--profile-samples",
        type=int,
        default=1,
        help="How many samples request vm.profile inside the trusted runtime path.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Seed forwarded to the trusted runtime path.")
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow overwriting an existing run_id.",
    )
    args = parser.parse_args()
    if args.hotspot_top_k <= 0:
        raise SystemExit(f"ERROR: --hotspot-top-k must be > 0 (got: {args.hotspot_top_k})")
    if args.max_inputs < 0:
        raise SystemExit(f"ERROR: --max-inputs must be >= 0 (got: {args.max_inputs})")
    if args.profile_samples < 0:
        raise SystemExit(f"ERROR: --profile-samples must be >= 0 (got: {args.profile_samples})")
    return args


def load_shell_env(env_path: str) -> dict[str, str]:
    python_exe = shlex.quote(sys.executable)
    env_quoted = shlex.quote(env_path)
    cmd = (
        f"set -a; source {env_quoted} >/dev/null 2>&1; "
        f"{python_exe} - <<'PY'\n"
        "import json, os\n"
        "print(json.dumps(dict(os.environ), ensure_ascii=False))\n"
        "PY"
    )
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def resolve_python_from_env(env_vars: dict[str, str]) -> str:
    for key in ("LOCAL_TVM_PYTHON", "TVM_PYTHON", "PYTHON"):
        value = env_vars.get(key, "").strip()
        if value and os.path.exists(value.split()[0]):
            return value
    return sys.executable


def parse_last_json_line(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    for line in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        text = line.strip()
        if not text or not text.startswith("{"):
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


def latest_match(pattern: str) -> Path | None:
    matches = sorted(DEFAULT_REPORT_DIR.glob(pattern))
    return matches[-1] if matches else None


def recommend_hotspot_tasks(hotspot_json: dict[str, Any], top_k: int) -> list[str]:
    rows = hotspot_json.get("tasks")
    if not rows and isinstance(hotspot_json.get("stages"), dict):
        stage_name = hotspot_json.get("task_stage_used_for_recommendation")
        stage = hotspot_json["stages"].get(stage_name or "")
        rows = stage.get("tasks") if isinstance(stage, dict) else None
    rows = rows or []
    return [str(row.get("task_name")) for row in rows[:top_k] if row.get("task_name")]


def task_rows_from_hotspot(hotspot_json: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
    rows = hotspot_json.get("tasks")
    if not rows and isinstance(hotspot_json.get("stages"), dict):
        stage_name = hotspot_json.get("task_stage_used_for_recommendation")
        stage = hotspot_json["stages"].get(stage_name or "")
        rows = stage.get("tasks") if isinstance(stage, dict) else None
    return list(rows or [])[:top_k]


def ensure_clean_outputs(
    run_id: str,
    report_dir: Path,
    log_dir: Path,
    allow_overwrite: bool,
) -> tuple[Path, Path, Path]:
    summary_json = report_dir / f"{run_id}.json"
    summary_md = report_dir / f"{run_id}.md"
    raw_dir = report_dir / run_id
    log_file = log_dir / f"{run_id}.log"
    if allow_overwrite:
        return summary_json, summary_md, raw_dir

    existing = [path for path in (summary_json, summary_md, raw_dir, log_file) if path.exists()]
    if existing:
        raise SystemExit(
            "ERROR: run artifacts already exist for run_id="
            f"{run_id}\nRefusing to overwrite:\n  " + "\n  ".join(str(path) for path in existing)
        )
    return summary_json, summary_md, raw_dir


def make_logger(log_file: Path):
    def log(message: str) -> None:
        line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S%z')}] {message}"
        print(line)
        with log_file.open("a", encoding="utf-8") as outfile:
            outfile.write(line + "\n")

    return log


def run_hotspot_phase(
    args: argparse.Namespace,
    raw_dir: Path,
    log,
) -> dict[str, Any]:
    phase = {
        "requested_mode": args.hotspot_mode,
        "status": "skipped",
        "env_file": str(Path(args.hotspot_env).resolve()),
        "report_json": None,
        "report_md": None,
        "recommended_full_hotspot_tasks": [],
        "top_tasks": [],
        "error": None,
    }
    if args.hotspot_mode == "skip":
        phase["status"] = "skipped"
        return phase

    hotspot_json_path = raw_dir / "hotspot_tasks.json"
    hotspot_md_path = raw_dir / "hotspot_tasks.md"
    hotspot_stdout = raw_dir / "hotspot_extract.stdout.log"
    hotspot_stderr = raw_dir / "hotspot_extract.stderr.log"

    if args.hotspot_mode in {"auto", "extract"}:
        try:
            env_vars = load_shell_env(args.hotspot_env)
            python_exec = resolve_python_from_env(env_vars)
            log(
                "hotspot phase: running extract_hotspot_tasks.py "
                f"with python={python_exec} env={args.hotspot_env}"
            )
            cmd = [
                python_exec,
                str(EXTRACT_SCRIPT),
                "--env",
                str(Path(args.hotspot_env).resolve()),
                "--top-k",
                str(args.hotspot_top_k),
                "--output",
                str(hotspot_md_path),
                "--json-output",
                str(hotspot_json_path),
            ]
            proc = subprocess.run(
                cmd,
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            hotspot_stdout.write_text(proc.stdout, encoding="utf-8")
            hotspot_stderr.write_text(proc.stderr, encoding="utf-8")
            if proc.returncode == 0 and hotspot_json_path.is_file():
                hotspot_json = json.loads(hotspot_json_path.read_text(encoding="utf-8"))
                phase.update(
                    {
                        "status": "extracted",
                        "python_executable": python_exec,
                        "report_json": str(hotspot_json_path),
                        "report_md": str(hotspot_md_path),
                        "stdout_log": str(hotspot_stdout),
                        "stderr_log": str(hotspot_stderr),
                        "recommended_full_hotspot_tasks": recommend_hotspot_tasks(
                            hotspot_json, args.hotspot_top_k
                        ),
                        "top_tasks": task_rows_from_hotspot(hotspot_json, args.hotspot_top_k),
                    }
                )
                return phase
            phase["error"] = (
                "extract_hotspot_tasks.py failed with rc="
                f"{proc.returncode}; see {hotspot_stdout} and {hotspot_stderr}"
            )
            log(f"hotspot phase: extraction failed rc={proc.returncode}")
            if args.hotspot_mode == "extract":
                phase["status"] = "failed"
                return phase
        except Exception as err:
            phase["error"] = f"{type(err).__name__}: {err}"
            log(f"hotspot phase: extraction raised {type(err).__name__}: {err}")
            if args.hotspot_mode == "extract":
                phase["status"] = "failed"
                return phase

    reuse_json = Path(args.hotspot_existing_json).resolve() if args.hotspot_existing_json else None
    reuse_md = Path(args.hotspot_existing_md).resolve() if args.hotspot_existing_md else None
    if reuse_json is None:
        reuse_json = latest_match("hotspot_tasks_*.json") or DEFAULT_HOTSPOT_JSON
    if reuse_md is None:
        reuse_md = latest_match("hotspot_tasks_*.md") or DEFAULT_HOTSPOT_MD

    if reuse_json and reuse_json.is_file():
        copied_json = raw_dir / "hotspot_tasks_reused.json"
        shutil.copy2(reuse_json, copied_json)
        copied_md = None
        if reuse_md and reuse_md.is_file():
            copied_md = raw_dir / "hotspot_tasks_reused.md"
            shutil.copy2(reuse_md, copied_md)
        hotspot_json = json.loads(copied_json.read_text(encoding="utf-8"))
        phase.update(
            {
                "status": "reused",
                "report_json": str(copied_json),
                "report_md": str(copied_md) if copied_md else None,
                "source_report_json": str(reuse_json),
                "source_report_md": str(reuse_md) if reuse_md and reuse_md.is_file() else None,
                "recommended_full_hotspot_tasks": recommend_hotspot_tasks(hotspot_json, args.hotspot_top_k),
                "top_tasks": task_rows_from_hotspot(hotspot_json, args.hotspot_top_k),
            }
        )
        log(f"hotspot phase: reused existing report {reuse_json}")
        return phase

    phase["status"] = "failed"
    if not phase["error"]:
        phase["error"] = "no hotspot report could be extracted or reused"
    return phase


def run_runtime_phase(
    args: argparse.Namespace,
    run_id: str,
    raw_dir: Path,
    log,
) -> dict[str, Any]:
    phase = {
        "requested_mode": args.runtime_mode,
        "status": "skipped",
        "trusted_env": str(Path(args.trusted_env).resolve()),
        "trusted_variant": args.trusted_variant,
        "command": None,
        "command_log": None,
        "summary": None,
        "fallback_reason": None,
    }
    if args.runtime_mode == "skip":
        return phase

    command_log = raw_dir / "runtime_command.log"
    command_file = raw_dir / "runtime_command.sh"
    env_snapshot = raw_dir / "trusted_env_snapshot.env"

    try:
        env_vars = load_shell_env(args.trusted_env)
        shutil.copy2(args.trusted_env, env_snapshot)
    except Exception as err:
        phase.update(
            {
                "status": "failed",
                "fallback_reason": f"failed to load trusted env: {type(err).__name__}: {err}",
            }
        )
        return phase

    command = [
        "bash",
        str(TRUSTED_RUNTIME_SCRIPT),
        "--variant",
        args.trusted_variant,
        "--max-inputs",
        str(args.max_inputs),
        "--seed",
        str(args.seed),
    ]
    if args.profile_samples > 0:
        command.extend(["--profile-ops", "--profile-samples", str(args.profile_samples)])

    env = os.environ.copy()
    env.update({key: str(value) for key, value in env_vars.items()})
    env["INFERENCE_REAL_OUTPUT_PREFIX"] = run_id
    env["INFERENCE_OUTPUT_PREFIX"] = run_id

    phase.update(
        {
            "command": shlex.join(command),
            "command_log": str(command_log),
            "remote_host": env_vars.get("REMOTE_HOST"),
            "target": env_vars.get("TARGET"),
            "expected_artifact_sha256": env_vars.get("INFERENCE_CURRENT_EXPECTED_SHA256")
            or env_vars.get("INFERENCE_BASELINE_EXPECTED_SHA256")
            or env_vars.get("INFERENCE_EXPECTED_SHA256"),
        }
    )
    command_file.write_text(
        "# trusted task-5.1 runtime command\n"
        f"cd {shlex.quote(str(PROJECT_DIR))}\n"
        f"{phase['command']}\n",
        encoding="utf-8",
    )
    log(f"runtime phase: executing trusted path -> {phase['command']}")

    proc = subprocess.run(
        command,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
    )
    command_log.write_text(
        proc.stdout + ("\n" if proc.stdout and proc.stderr else "") + proc.stderr,
        encoding="utf-8",
    )
    parsed_summary = parse_last_json_line(command_log)
    phase["summary"] = parsed_summary
    phase["returncode"] = proc.returncode

    if proc.returncode != 0:
        phase["status"] = "failed"
        phase["fallback_reason"] = (
            f"trusted runtime command failed with rc={proc.returncode}; see {command_log}"
        )
        log(f"runtime phase: trusted command failed rc={proc.returncode}")
        return phase

    if parsed_summary is None:
        phase["status"] = "failed"
        phase["fallback_reason"] = f"trusted runtime command succeeded but no JSON summary was found in {command_log}"
        log("runtime phase: no JSON summary found in runtime log")
        return phase

    runtime_profiling = parsed_summary.get("runtime_profiling") or {}
    status = runtime_profiling.get("status", "unknown")
    if status == "profiled":
        phase["status"] = "profiled"
    elif status == "profiled_raw":
        phase["status"] = "profiled_raw"
    elif runtime_profiling.get("requested"):
        phase["status"] = "fallback_only"
        phase["fallback_reason"] = runtime_profiling.get("sample_results", [{}])[0].get("error") or (
            "trusted runtime executed but vm.profile did not yield per-op rows"
        )
    else:
        phase["status"] = "executed_without_profile"
        phase["fallback_reason"] = "runtime command executed without a profiling request"

    log(
        "runtime phase: "
        f"status={phase['status']} processed={parsed_summary.get('processed_count')} "
        f"run_median_ms={parsed_summary.get('run_median_ms')}"
    )
    return phase


def extract_top_ops_from_runtime_profile(runtime_profile: dict[str, Any], top_k: int = 8) -> list[dict[str, Any]]:
    top_ops = list(runtime_profile.get("top_ops") or [])
    if top_ops:
        return top_ops[:top_k]

    sample_results = runtime_profile.get("sample_results") or []
    if not sample_results:
        return []

    report_json = sample_results[0].get("report_json") or {}
    calls = report_json.get("calls") or []
    rows: list[dict[str, Any]] = []
    for call in calls:
        name_payload = call.get("Name") or {}
        duration_payload = call.get("Duration (us)") or {}
        percent_payload = call.get("Percent") or {}
        count_payload = call.get("Count") or {}
        device_payload = call.get("Device") or {}
        name = name_payload.get("string") if isinstance(name_payload, dict) else None
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "mean_duration_us": duration_payload.get("microseconds") if isinstance(duration_payload, dict) else None,
                "mean_percent": percent_payload.get("percent") if isinstance(percent_payload, dict) else None,
                "samples": count_payload.get("count") if isinstance(count_payload, dict) else None,
                "devices": [device_payload.get("string")] if isinstance(device_payload, dict) and device_payload.get("string") else [],
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("mean_duration_us") is None,
            -(row.get("mean_duration_us") or 0.0),
            row.get("name") or "",
        )
    )
    if rows:
        runtime_profile["top_ops"] = rows[:top_k]
    return rows[:top_k]


def md_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return lines


def build_markdown(summary: dict[str, Any]) -> str:
    hotspot = summary["hotspot_phase"]
    runtime = summary["runtime_phase"]
    lines = [
        "# Task 5.1 Operator Profiling",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- run_id: {summary['run_id']}",
        f"- overall_status: {summary['overall_status']}",
        f"- report_json: {summary['summary_json']}",
        f"- raw_dir: {summary['raw_dir']}",
        "",
        "## Task-stage hotspot extraction",
        "",
        f"- status: {hotspot['status']}",
        f"- requested_mode: {hotspot['requested_mode']}",
        f"- env_file: {hotspot['env_file']}",
        f"- report_json: {hotspot.get('report_json') or 'N/A'}",
        f"- report_md: {hotspot.get('report_md') or 'N/A'}",
        "- recommended_FULL_HOTSPOT_TASKS: "
        + (",".join(hotspot.get("recommended_full_hotspot_tasks") or []) or "N/A"),
    ]
    if hotspot.get("error"):
        lines.append(f"- note: {hotspot['error']}")
    if hotspot.get("top_tasks"):
        lines.extend(
            [
                "",
                "### Hotspot preview",
                "",
                *md_table(
                    ["rank", "task_name", "weight", "dispatched_count", "prim_funcs"],
                    [
                        [
                            row.get("rank", ""),
                            row.get("task_name", ""),
                            row.get("weight", ""),
                            row.get("dispatched_count", ""),
                            ",".join(row.get("prim_funcs") or []) or "-",
                        ]
                        for row in hotspot["top_tasks"]
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Runtime/operator profiling attempt",
            "",
            f"- status: {runtime['status']}",
            f"- requested_mode: {runtime['requested_mode']}",
            f"- trusted_env: {runtime['trusted_env']}",
            f"- trusted_variant: {runtime['trusted_variant']}",
            f"- remote_host: {runtime.get('remote_host') or 'N/A'}",
            f"- target: {runtime.get('target') or 'N/A'}",
            f"- command: `{runtime.get('command') or 'N/A'}`",
            f"- command_log: {runtime.get('command_log') or 'N/A'}",
            f"- expected_artifact_sha256: {runtime.get('expected_artifact_sha256') or 'N/A'}",
        ]
    )
    if runtime.get("fallback_reason"):
        lines.append(f"- fallback_reason: {runtime['fallback_reason']}")

    runtime_summary = runtime.get("summary") or {}
    runtime_profile = runtime_summary.get("runtime_profiling") or {}
    top_ops = extract_top_ops_from_runtime_profile(runtime_profile)
    if runtime_summary:
        lines.extend(
            [
                f"- artifact_path: {runtime_summary.get('artifact_path') or 'N/A'}",
                f"- artifact_sha256: {runtime_summary.get('artifact_sha256') or 'N/A'}",
                f"- processed_count: {runtime_summary.get('processed_count')}",
                f"- input_count: {runtime_summary.get('input_count')}",
                f"- run_median_ms: {runtime_summary.get('run_median_ms')}",
                f"- run_mean_ms: {runtime_summary.get('run_mean_ms')}",
                f"- load_ms: {runtime_summary.get('load_ms')}",
                f"- vm_init_ms: {runtime_summary.get('vm_init_ms')}",
                f"- runtime_profile_status: {runtime_profile.get('status')}",
                f"- runtime_profile_supported: {runtime_profile.get('supported')}",
            ]
        )
    if top_ops:
        lines.extend(
            [
                "",
                "### Runtime top ops",
                "",
                *md_table(
                    ["rank", "name", "mean_duration_us", "mean_percent", "samples", "devices"],
                    [
                        [
                            idx,
                            row.get("name", ""),
                            row.get("mean_duration_us", ""),
                            row.get("mean_percent", ""),
                            row.get("samples", ""),
                            ",".join(row.get("devices") or []) or "-",
                        ]
                        for idx, row in enumerate(top_ops, start=1)
                    ],
                ),
            ]
        )
    elif runtime_profile.get("sample_results"):
        sample = runtime_profile["sample_results"][0]
        if sample.get("report_text"):
            lines.extend(
                [
                    "",
                    "### Runtime raw report preview",
                    "",
                    "```text",
                    sample["report_text"],
                    "```",
                ]
            )

    lines.extend(
        [
            "",
            "## Outcome",
            "",
            f"- overall_status: {summary['overall_status']}",
            "- recommended_FULL_HOTSPOT_TASKS: "
            + (",".join(summary["recommended_full_hotspot_tasks"]) or "N/A"),
            "- runtime_hotspot_candidates: "
            + (",".join(summary["runtime_hotspot_candidates"]) or "N/A"),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()

    report_dir = Path(args.report_dir).resolve()
    log_dir = Path(args.log_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    run_id = args.run_id or f"profiling_{args.label}_{stamp}"
    summary_json_path, summary_md_path, raw_dir = ensure_clean_outputs(
        run_id=run_id,
        report_dir=report_dir,
        log_dir=log_dir,
        allow_overwrite=args.allow_overwrite,
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{run_id}.log"
    logger = make_logger(log_file)

    logger(f"task-5.1 start run_id={run_id}")

    hotspot_phase = run_hotspot_phase(args=args, raw_dir=raw_dir, log=logger)
    runtime_phase = run_runtime_phase(args=args, run_id=run_id, raw_dir=raw_dir, log=logger)

    recommended = hotspot_phase.get("recommended_full_hotspot_tasks") or []
    runtime_summary = runtime_phase.get("summary") or {}
    runtime_profile = runtime_summary.get("runtime_profiling") or {}
    top_ops = extract_top_ops_from_runtime_profile(runtime_profile)
    runtime_hotspots = [
        row.get("name")
        for row in top_ops[:2]
        if row.get("name")
    ]

    if runtime_phase["status"] in {"profiled", "profiled_raw"}:
        overall_status = "runtime_operator_profile"
    elif recommended:
        overall_status = "stage_level_hotspot_only"
    elif runtime_phase["status"] == "skipped":
        overall_status = "no_runtime_attempt"
    else:
        overall_status = "insufficient_evidence"

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "run_id": run_id,
        "summary_json": str(summary_json_path),
        "summary_md": str(summary_md_path),
        "log_file": str(log_file),
        "raw_dir": str(raw_dir),
        "hotspot_phase": hotspot_phase,
        "runtime_phase": runtime_phase,
        "overall_status": overall_status,
        "recommended_full_hotspot_tasks": recommended,
        "runtime_hotspot_candidates": runtime_hotspots,
        "next_step_guidance": (
            "If runtime_operator_profile is available, feed runtime_hotspot_candidates into 4.2/7.1. "
            "If only stage_level_hotspot_only is available, keep using recommended_full_hotspot_tasks for 4.2 "
            "and rebuild or replace the remote TVM runtime with profiler support before treating 7.1 as settled."
        ),
    }

    summary_json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary_md_path.write_text(build_markdown(summary), encoding="utf-8")
    logger(f"task-5.1 complete overall_status={overall_status}")

    print(f"run_id={run_id}")
    print(f"summary_json={summary_json_path}")
    print(f"summary_md={summary_md_path}")
    print(f"overall_status={overall_status}")
    print("recommended_full_hotspot_tasks=" + ",".join(recommended))
    print("runtime_hotspot_candidates=" + ",".join(runtime_hotspots))


if __name__ == "__main__":
    main()
