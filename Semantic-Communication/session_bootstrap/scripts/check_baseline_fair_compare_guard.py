#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSPECTOR_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "inspect_baseline_lineage.py"
DEFAULT_COMPARE_ENV_GLOB = "session_bootstrap/tmp/inference_compare_scheme_a_fair_run_fixed_*.env"
DEFAULT_REBUILD_REPORT_GLOB = "session_bootstrap/reports/phytium_baseline_style_current_rebuild_*.json"
DEFAULT_PROBE_LOG_GLOB = "session_bootstrap/reports/baseline_current_safe_probe_*.log"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the latest baseline/current fair-compare evidence, run the "
            "strict baseline ABI/fairness guard, and print a concise operator verdict."
        )
    )
    parser.add_argument(
        "--compare-env",
        type=Path,
        help=(
            "Path to the fair compare env file. Defaults to the latest "
            f"{DEFAULT_COMPARE_ENV_GLOB}."
        ),
    )
    parser.add_argument(
        "--compare-log",
        type=Path,
        help=(
            "Path to the fair compare log. Defaults to the log derived from "
            "INFERENCE_EXECUTION_ID/EXECUTION_ID in --compare-env."
        ),
    )
    parser.add_argument(
        "--current-rebuild-report",
        type=Path,
        help=(
            "Path to the baseline-style current rebuild JSON report. Defaults to the "
            f"latest {DEFAULT_REBUILD_REPORT_GLOB}."
        ),
    )
    parser.add_argument(
        "--baseline-current-safe-probe-log",
        type=Path,
        help=(
            "Optional explicit baseline current-safe probe log. When omitted, this "
            "wrapper auto-picks the latest matching probe log if one exists."
        ),
    )
    parser.add_argument(
        "--no-auto-probe",
        action="store_true",
        help="Do not auto-pick the latest baseline current-safe probe log.",
    )
    return parser.parse_args(argv)


def pick_latest(project_root: Path, glob_pattern: str, label: str) -> Path:
    matches = sorted(project_root.glob(glob_pattern))
    if not matches:
        raise SystemExit(f"ERROR: no {label} found for glob: {glob_pattern}")
    return matches[-1]


def pick_latest_optional(project_root: Path, glob_pattern: str) -> Path | None:
    matches = sorted(project_root.glob(glob_pattern))
    if not matches:
        return None
    return matches[-1]


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
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


def derive_compare_log_path(project_root: Path, compare_env: Path) -> Path:
    env_vars = parse_shell_env(compare_env)
    run_id = env_vars.get("INFERENCE_EXECUTION_ID") or env_vars.get("EXECUTION_ID")
    if not run_id:
        raise SystemExit(
            "ERROR: compare env does not define INFERENCE_EXECUTION_ID/EXECUTION_ID; "
            "pass --compare-log explicitly."
        )
    return project_root / "session_bootstrap" / "logs" / f"{run_id}.log"


def resolve_inputs(args: argparse.Namespace, project_root: Path) -> dict[str, Path | None]:
    compare_env = require_file(
        args.compare_env or pick_latest(project_root, DEFAULT_COMPARE_ENV_GLOB, "fair compare env"),
        "fair compare env",
    )
    compare_log = require_file(
        args.compare_log or derive_compare_log_path(project_root, compare_env),
        "fair compare log",
    )
    rebuild_report = require_file(
        args.current_rebuild_report
        or pick_latest(
            project_root,
            DEFAULT_REBUILD_REPORT_GLOB,
            "baseline-style current rebuild report",
        ),
        "baseline-style current rebuild report",
    )

    probe_log: Path | None = args.baseline_current_safe_probe_log
    if probe_log is None and not args.no_auto_probe:
        probe_log = pick_latest_optional(project_root, DEFAULT_PROBE_LOG_GLOB)
    if probe_log is not None:
        probe_log = require_file(probe_log, "baseline current-safe probe log")

    return {
        "compare_env": compare_env,
        "compare_log": compare_log,
        "current_rebuild_report": rebuild_report,
        "baseline_current_safe_probe_log": probe_log,
    }


def build_inspector_command(
    resolved_inputs: dict[str, Path | None],
    inspector_script: Path,
) -> list[str]:
    cmd = [
        sys.executable,
        str(inspector_script),
        "--strict-fair-compare",
        "--compare-env",
        str(resolved_inputs["compare_env"]),
        "--compare-log",
        str(resolved_inputs["compare_log"]),
        "--current-rebuild-report",
        str(resolved_inputs["current_rebuild_report"]),
    ]
    probe_log = resolved_inputs["baseline_current_safe_probe_log"]
    if probe_log is not None:
        cmd.extend(["--baseline-current-safe-probe-log", str(probe_log)])
    return cmd


def parse_inspector_payload(stdout: str) -> dict[str, object]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as err:
        raise SystemExit(f"ERROR: inspector did not emit valid JSON: {err}") from err
    if not isinstance(payload, dict):
        raise SystemExit("ERROR: inspector emitted a non-object JSON payload.")
    return payload


def to_display_path(project_root: Path, raw_path: object) -> str:
    if not raw_path:
        return "none"
    path = Path(str(raw_path))
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)
    except FileNotFoundError:
        return str(path)


def render_shape(value: object) -> str:
    if value is None:
        return "none"
    return json.dumps(value, ensure_ascii=False)


def render_verdict(payload: dict[str, object], *, project_root: Path, exit_code: int) -> str:
    fair_compare_guard = payload["fair_compare_guard"]
    baseline_abi = payload["baseline_abi_assessment"]
    probe = payload["baseline_current_safe_probe"]
    runtime = payload["runtime_lineage"]
    baseline = payload["baseline_compare"]
    current_compare = payload["current_compare"]
    current_rebuild = payload["current_rebuild"]
    sources = payload["sources"]

    lines = [
        (
            "guard: "
            f"{fair_compare_guard['status']} "
            f"(claim_allowed={str(fair_compare_guard['claim_allowed']).lower()}, exit={exit_code})"
        ),
        (
            "baseline: "
            f"{baseline_abi['classification']} "
            f"[{baseline_abi['recommended_operator_label']}]"
        ),
        (
            "probe/runtime: "
            f"{probe['status']} / {runtime['baseline_vs_current_compare']}"
        ),
        (
            "shapes: "
            f"baseline={render_shape(baseline.get('output_shape'))} "
            f"current_compare={render_shape(current_compare.get('output_shape'))} "
            f"current_rebuild={render_shape(current_rebuild.get('output_shape'))}"
        ),
        f"compare_env: {to_display_path(project_root, sources.get('compare_env'))}",
        f"compare_log: {to_display_path(project_root, sources.get('compare_log'))}",
        f"rebuild_report: {to_display_path(project_root, sources.get('current_rebuild_report'))}",
        (
            "probe_log: "
            f"{to_display_path(project_root, sources.get('baseline_current_safe_probe_log'))}"
        ),
        f"summary: {fair_compare_guard['summary']}",
        f"next_action: {fair_compare_guard['next_action']}",
    ]
    return "\n".join(lines)


def main(
    argv: list[str] | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
    inspector_script: Path = INSPECTOR_SCRIPT,
) -> int:
    args = parse_args(argv)
    resolved_inputs = resolve_inputs(args, project_root)
    cmd = build_inspector_command(resolved_inputs, inspector_script)
    completed = subprocess.run(
        cmd,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode not in {0, 2}:
        if completed.stdout:
            sys.stderr.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        return completed.returncode or 1

    payload = parse_inspector_payload(completed.stdout)
    sys.stdout.write(
        render_verdict(payload, project_root=project_root, exit_code=completed.returncode)
    )
    sys.stdout.write("\n")
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
