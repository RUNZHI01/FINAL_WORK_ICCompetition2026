#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import shlex
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPARE_ENV_GLOB = "session_bootstrap/tmp/inference_compare_scheme_a_fair_run_fixed_*.env"
DEFAULT_REBUILD_REPORT_GLOB = "session_bootstrap/reports/phytium_baseline_style_current_rebuild_*.json"
PAYLOAD_RUNNER = "./session_bootstrap/scripts/run_remote_tvm_inference_payload.sh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract baseline/current artifact/runtime lineage from the fair "
            "Scheme A compare evidence, optionally classify baseline current-safe "
            "ABI compatibility, and guard invalid fair-compare claims."
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
            "Path to the fair compare benchmark log. Defaults to the log derived from "
            "INFERENCE_EXECUTION_ID inside --compare-env."
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
            "Optional path to a baseline-only probe log captured under the current-safe "
            "runtime. The helper classifies missing vm_load_executable failures as "
            "baseline ABI incompatibility / legacy-compat-only evidence."
        ),
    )
    parser.add_argument(
        "--strict-fair-compare",
        action="store_true",
        help=(
            "Exit 2 when the evidence shows baseline/current cannot be claimed as a "
            "fair compare because the runtime lines differ or baseline is "
            "current-safe ABI-incompatible."
        ),
    )
    return parser.parse_args()


def pick_latest(glob_pattern: str, label: str) -> Path:
    matches = sorted(PROJECT_ROOT.glob(glob_pattern))
    if not matches:
        raise SystemExit(f"ERROR: no {label} found for glob: {glob_pattern}")
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


def parse_compare_payloads(path: Path) -> dict[str, dict[str, object]]:
    payloads: dict[str, dict[str, object]] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        variant = payload.get("variant")
        if variant not in {"baseline", "current"}:
            continue
        if "artifact_path" not in payload:
            continue
        payloads[str(variant)] = payload
    missing = {"baseline", "current"} - set(payloads)
    if missing:
        raise SystemExit(
            f"ERROR: missing compare payload JSON for variant(s): {', '.join(sorted(missing))}"
        )
    return payloads


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_command_env_assignments(command: str | None) -> dict[str, str]:
    if not command:
        return {}
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return {}

    index = 0
    if tokens[:1] == ["env"]:
        index = 1
        while index < len(tokens) and tokens[index].startswith("-"):
            index += 1

    assignments: dict[str, str] = {}
    for token in tokens[index:]:
        if "=" not in token:
            break
        key, value = token.split("=", 1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            break
        assignments[key] = value
    return assignments


def extract_remote_tvm_python_override(command: str | None) -> str | None:
    return extract_command_env_assignments(command).get("REMOTE_TVM_PYTHON")


def derive_compare_log_path(compare_env: Path, env_vars: dict[str, str]) -> Path:
    run_id = env_vars.get("INFERENCE_EXECUTION_ID") or env_vars.get("EXECUTION_ID")
    if not run_id:
        raise SystemExit(
            "ERROR: compare env does not define INFERENCE_EXECUTION_ID/EXECUTION_ID; "
            "pass --compare-log explicitly."
        )
    return PROJECT_ROOT / "session_bootstrap" / "logs" / f"{run_id}.log"


def to_abs_project_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except FileNotFoundError:
        return str(path)


def infer_runtime_family(remote_tvm_python: object) -> str:
    text = str(remote_tvm_python or "").strip().lower()
    if not text:
        return "unknown"
    if "compat" in text or "legacy" in text:
        return "compat_or_legacy"
    if "current-safe" in text or "tvm310_safe" in text or "samegen_safe" in text or "/safe/" in text:
        return "current_safe"
    return "custom"


def build_variant_summary(
    *,
    variant: str,
    payload: dict[str, object],
    command: str | None,
    env_remote_tvm_python: str | None,
) -> dict[str, object]:
    override_remote_tvm_python = extract_remote_tvm_python_override(command)
    effective_remote_tvm_python = override_remote_tvm_python or env_remote_tvm_python
    return {
        "variant": variant,
        "command": command,
        "archive_dir": payload.get("archive"),
        "artifact_path": payload.get("artifact_path"),
        "artifact_sha256": payload.get("artifact_sha256"),
        "artifact_sha256_expected": payload.get("artifact_sha256_expected"),
        "artifact_sha256_match": payload.get("artifact_sha256_match"),
        "artifact_size_bytes": payload.get("artifact_size_bytes"),
        "output_shape": payload.get("output_shape"),
        "output_dtype": payload.get("output_dtype"),
        "tvm_version": payload.get("tvm_version"),
        "device": payload.get("device"),
        "effective_remote_tvm_python": effective_remote_tvm_python,
        "remote_tvm_python_source": "command_override" if override_remote_tvm_python else "compare_env",
        "remote_tvm_python_override": override_remote_tvm_python,
    }


def build_current_rebuild_summary(report: dict[str, object]) -> dict[str, object]:
    remote_artifact = report.get("remote_artifact") or {}
    safe_runtime_inference = report.get("safe_runtime_inference") or {}
    payload = safe_runtime_inference.get("payload") or {}
    return {
        "report_id": report.get("report_id"),
        "mode": report.get("mode"),
        "archive_dir": payload.get("archive") or remote_artifact.get("archive_dir"),
        "artifact_path": payload.get("artifact_path") or remote_artifact.get("optimized_model_so"),
        "artifact_sha256": payload.get("artifact_sha256") or remote_artifact.get("optimized_model_sha256"),
        "artifact_sha256_expected": payload.get("artifact_sha256_expected"),
        "artifact_sha256_match": payload.get("artifact_sha256_match"),
        "artifact_size_bytes": payload.get("artifact_size_bytes") or remote_artifact.get("optimized_model_size_bytes"),
        "output_shape": payload.get("output_shape"),
        "output_dtype": payload.get("output_dtype"),
        "tvm_version": payload.get("tvm_version") or safe_runtime_inference.get("remote_tvm_version"),
        "device": payload.get("device") or safe_runtime_inference.get("device"),
        "effective_remote_tvm_python": safe_runtime_inference.get("remote_tvm_python"),
        "remote_tvm_python_source": "rebuild_report",
        "remote_tvm_python_override": None,
        "remote_archive_hash_match": remote_artifact.get("hash_match"),
    }


def shape_equals(left: object, right: object) -> bool:
    return left == right and left is not None


def extract_last_json_payload(text: str) -> dict[str, object] | None:
    for raw_line in reversed(text.splitlines()):
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_shape_literal(raw_shape: str | None) -> list[int] | None:
    if not raw_shape:
        return None
    try:
        parsed = ast.literal_eval(raw_shape)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(parsed, (list, tuple)):
        return None
    if not all(isinstance(dim, int) for dim in parsed):
        return None
    return [int(dim) for dim in parsed]


def extract_probe_error_excerpt(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "missing_vm_load_executable" in line or "vm_load_executable" in line:
            return line
    return None


def analyze_baseline_current_safe_probe(probe_log: Path | None) -> dict[str, object]:
    if probe_log is None:
        return {
            "source": None,
            "status": "not_provided",
            "error_signature": None,
            "error_excerpt": None,
            "output_shape": None,
            "output_dtype": None,
            "artifact_path": None,
            "artifact_sha256": None,
            "tvm_version": None,
            "device": None,
        }

    path = require_file(probe_log, "baseline current-safe probe log")
    text = path.read_text(encoding="utf-8", errors="replace")
    json_payload = extract_last_json_payload(text)
    error_excerpt = extract_probe_error_excerpt(text)

    if "missing_vm_load_executable" in text or re.search(
        r"AttributeError:\s*Module has no function ['\"]vm_load_executable['\"]",
        text,
        re.MULTILINE,
    ):
        return {
            "source": to_abs_project_path(path),
            "status": "current_safe_abi_incompatible",
            "error_signature": "missing_vm_load_executable",
            "error_excerpt": error_excerpt,
            "output_shape": None,
            "output_dtype": None,
            "artifact_path": None,
            "artifact_sha256": None,
            "tvm_version": None,
            "device": None,
        }

    if json_payload is not None:
        return {
            "source": to_abs_project_path(path),
            "status": "current_safe_probe_succeeded",
            "error_signature": None,
            "error_excerpt": None,
            "output_shape": json_payload.get("output_shape"),
            "output_dtype": json_payload.get("output_dtype"),
            "artifact_path": json_payload.get("artifact_path"),
            "artifact_sha256": json_payload.get("artifact_sha256"),
            "tvm_version": json_payload.get("tvm_version"),
            "device": json_payload.get("device"),
        }

    run_ok_match = re.search(
        r"RUN_OK\s+(\[[^\]]+\]|\([^)]+\))(?:\s+([A-Za-z0-9_]+))?",
        text,
    )
    if run_ok_match:
        return {
            "source": to_abs_project_path(path),
            "status": "current_safe_probe_succeeded",
            "error_signature": None,
            "error_excerpt": None,
            "output_shape": parse_shape_literal(run_ok_match.group(1)),
            "output_dtype": run_ok_match.group(2),
            "artifact_path": None,
            "artifact_sha256": None,
            "tvm_version": None,
            "device": None,
        }

    if "Traceback" in text or "ERROR:" in text:
        fallback_error_excerpt = None
        stripped_lines = [line.strip() for line in text.splitlines() if line.strip()]
        if stripped_lines:
            fallback_error_excerpt = stripped_lines[-1]
        return {
            "source": to_abs_project_path(path),
            "status": "current_safe_probe_failed_other",
            "error_signature": "probe_failed_other",
            "error_excerpt": error_excerpt or fallback_error_excerpt,
            "output_shape": None,
            "output_dtype": None,
            "artifact_path": None,
            "artifact_sha256": None,
            "tvm_version": None,
            "device": None,
        }

    return {
        "source": to_abs_project_path(path),
        "status": "unclassified_probe_output",
        "error_signature": None,
        "error_excerpt": error_excerpt,
        "output_shape": None,
        "output_dtype": None,
        "artifact_path": None,
        "artifact_sha256": None,
        "tvm_version": None,
        "device": None,
    }


def build_runtime_lineage(
    *,
    compare_env_remote_tvm_python: str | None,
    baseline: dict[str, object],
    current_compare: dict[str, object],
    current_rebuild: dict[str, object],
) -> dict[str, object]:
    baseline_python = baseline.get("effective_remote_tvm_python")
    current_compare_python = current_compare.get("effective_remote_tvm_python")
    current_rebuild_python = current_rebuild.get("effective_remote_tvm_python")

    def relation(left: object, right: object) -> str:
        if not left or not right:
            return "unknown"
        if left == right:
            return "same_runtime_line"
        left_family = infer_runtime_family(left)
        right_family = infer_runtime_family(right)
        if left_family == "compat_or_legacy" and right_family == "current_safe":
            return "compat_vs_current_safe"
        return "different_runtime_line"

    return {
        "compare_env_remote_tvm_python": compare_env_remote_tvm_python,
        "compare_env_runtime_family": infer_runtime_family(compare_env_remote_tvm_python),
        "baseline_compare_runtime_family": infer_runtime_family(baseline_python),
        "current_compare_runtime_family": infer_runtime_family(current_compare_python),
        "current_rebuild_runtime_family": infer_runtime_family(current_rebuild_python),
        "baseline_vs_current_compare": relation(baseline_python, current_compare_python),
        "baseline_vs_current_rebuild": relation(baseline_python, current_rebuild_python),
        "current_compare_vs_current_rebuild": relation(current_compare_python, current_rebuild_python),
    }


def build_baseline_abi_assessment(
    *,
    baseline: dict[str, object],
    current_compare: dict[str, object],
    current_rebuild: dict[str, object],
    runtime_lineage: dict[str, object],
    probe: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    evidence: list[str] = []
    baseline_runtime = baseline.get("effective_remote_tvm_python")
    current_runtime = current_compare.get("effective_remote_tvm_python")
    baseline_shape = baseline.get("output_shape")
    current_compare_shape = current_compare.get("output_shape")
    current_rebuild_shape = current_rebuild.get("output_shape")
    probe_status = probe.get("status")
    runtime_relation = runtime_lineage.get("baseline_vs_current_compare")

    if runtime_relation != "same_runtime_line":
        evidence.append(
            "baseline compare used a different runtime line than current compare: "
            f"baseline={baseline_runtime!r}, current={current_runtime!r}"
        )
    if baseline_shape != current_compare_shape:
        evidence.append(
            "baseline/current compare output shapes differ: "
            f"baseline={baseline_shape}, current={current_compare_shape}"
        )

    if probe_status == "current_safe_abi_incompatible":
        if probe.get("error_excerpt"):
            evidence.append(
                "baseline current-safe probe failed with explicit ABI marker: "
                f"{probe['error_excerpt']}"
            )
        assessment = {
            "status": "current_safe_abi_incompatible",
            "classification": "legacy_compat_only",
            "confidence": "high",
            "summary": (
                "Baseline fails under the current-safe runtime with missing "
                "vm_load_executable, so treat it as legacy/compat-only rather than a "
                "fair baseline for current-safe comparisons."
            ),
            "evidence": evidence,
            "recommended_operator_label": "baseline=legacy/compat-only",
        }
        guard = {
            "status": "blocked_baseline_current_safe_abi_incompatible",
            "reason": "baseline_current_safe_probe_missing_vm_load_executable",
            "claim_allowed": False,
            "summary": (
                "Do not claim a fair baseline/current compare. Baseline is ABI-"
                "incompatible with the current-safe runtime."
            ),
            "next_action": (
                "Mark the baseline line as legacy/compat-only in operator reports and "
                "exclude it from fair compare claims against current-safe artifacts."
            ),
        }
        return assessment, guard

    if probe_status == "current_safe_probe_succeeded":
        probe_shape = probe.get("output_shape")
        if probe_shape == current_rebuild_shape and probe_shape == current_compare_shape:
            evidence.append(
                "baseline current-safe probe succeeded and matched the current-safe output shape: "
                f"{probe_shape}"
            )
            assessment = {
                "status": "current_safe_compatible",
                "classification": "current_safe_compatible",
                "confidence": "high",
                "summary": (
                    "Baseline executes under the current-safe runtime and matches the "
                    "current-safe output shape."
                ),
                "evidence": evidence,
                "recommended_operator_label": "baseline=current-safe-compatible",
            }
        else:
            evidence.append(
                "baseline current-safe probe succeeded but still diverged from the current-safe "
                f"output: probe={probe_shape}, current_rebuild={current_rebuild_shape}"
            )
            assessment = {
                "status": "current_safe_compatible_shape_divergent",
                "classification": "separate_export_line",
                "confidence": "high",
                "summary": (
                    "Baseline runs under the current-safe runtime but still behaves as a "
                    "different export line, so it is not a fair apples-to-apples baseline."
                ),
                "evidence": evidence,
                "recommended_operator_label": "baseline=separate-current-safe-export-line",
            }
        if runtime_relation == "same_runtime_line" and assessment["status"] == "current_safe_compatible":
            guard = {
                "status": "allowed",
                "reason": None,
                "claim_allowed": True,
                "summary": "Provided evidence does not show a runtime-line ABI blocker.",
                "next_action": "Proceed with same-runtime compare validation.",
            }
        elif assessment["status"] == "current_safe_compatible":
            guard = {
                "status": "blocked_runtime_line_mismatch",
                "reason": "fair_compare_used_mismatched_runtime_lines",
                "claim_allowed": False,
                "summary": (
                    "The historical fair compare still used mismatched runtime lines even "
                    "though baseline now appears current-safe compatible."
                ),
                "next_action": (
                    "Rerun the fair compare with baseline/current both on the current-safe "
                    "runtime before making apples-to-apples claims."
                ),
            }
        else:
            guard = {
                "status": "blocked_baseline_current_safe_shape_divergence",
                "reason": "baseline_current_safe_probe_shape_diverged",
                "claim_allowed": False,
                "summary": (
                    "Do not claim a fair compare because baseline remains a different "
                    "output/export line even under the current-safe runtime."
                ),
                "next_action": (
                    "Keep baseline classified as a separate export line and compare only "
                    "artifacts that agree on the current-safe output contract."
                ),
            }
        return assessment, guard

    if runtime_relation != "same_runtime_line":
        assessment = {
            "status": "runtime_line_mismatch_observed",
            "classification": "inconclusive_without_current_safe_probe",
            "confidence": "medium",
            "summary": (
                "Baseline/current compare used different runtime lines, so a fair compare "
                "claim is already blocked even before a dedicated current-safe probe."
            ),
            "evidence": evidence,
            "recommended_operator_label": "baseline=runtime-line-mismatch",
        }
        guard = {
            "status": "blocked_runtime_line_mismatch",
            "reason": "fair_compare_used_mismatched_runtime_lines",
            "claim_allowed": False,
            "summary": (
                "Do not claim a fair baseline/current compare until the same baseline "
                "archive is rerun under the current-safe runtime."
            ),
            "next_action": (
                "Run the baseline archive once under the current-safe runtime and feed the "
                "probe log back into this helper."
            ),
        }
        return assessment, guard

    assessment = {
        "status": "no_runtime_abi_blocker_observed",
        "classification": "inconclusive",
        "confidence": "low",
        "summary": (
            "No mismatched runtime line or current-safe ABI failure was observed in the "
            "provided evidence."
        ),
        "evidence": evidence,
        "recommended_operator_label": "baseline=unclassified",
    }
    guard = {
        "status": "allowed",
        "reason": None,
        "claim_allowed": True,
        "summary": "No fair-compare runtime-line blocker was detected from the provided inputs.",
        "next_action": "Proceed with normal compare validation.",
    }
    return assessment, guard


def build_board_probe_command(compare_env: Path) -> str:
    env_path = shlex.quote(to_abs_project_path(compare_env))
    project_root = shlex.quote(str(PROJECT_ROOT))
    payload_runner = shlex.quote(PAYLOAD_RUNNER)
    return (
        "bash -lc "
        + shlex.quote(
            f"cd {project_root} && "
            f"set -a; source {env_path}; set +a; "
            "INFERENCE_WARMUP_RUNS=0 INFERENCE_REPEAT=1 "
            f"bash {payload_runner} --variant baseline"
        )
    )


def main() -> int:
    args = parse_args()

    compare_env = require_file(
        args.compare_env or pick_latest(DEFAULT_COMPARE_ENV_GLOB, "fair compare env"),
        "fair compare env",
    )
    env_vars = parse_shell_env(compare_env)

    compare_log = require_file(
        args.compare_log or derive_compare_log_path(compare_env, env_vars),
        "fair compare log",
    )
    compare_payloads = parse_compare_payloads(compare_log)

    rebuild_report_path = require_file(
        args.current_rebuild_report
        or pick_latest(DEFAULT_REBUILD_REPORT_GLOB, "baseline-style current rebuild report"),
        "baseline-style current rebuild report",
    )
    rebuild_report = load_json(rebuild_report_path)
    baseline_current_safe_probe = analyze_baseline_current_safe_probe(
        args.baseline_current_safe_probe_log
    )

    compare_env_remote_tvm_python = env_vars.get("REMOTE_TVM_PYTHON")
    baseline = build_variant_summary(
        variant="baseline",
        payload=compare_payloads["baseline"],
        command=env_vars.get("INFERENCE_BASELINE_CMD"),
        env_remote_tvm_python=compare_env_remote_tvm_python,
    )
    current_compare = build_variant_summary(
        variant="current",
        payload=compare_payloads["current"],
        command=env_vars.get("INFERENCE_CURRENT_CMD"),
        env_remote_tvm_python=compare_env_remote_tvm_python,
    )
    current_rebuild = build_current_rebuild_summary(rebuild_report)

    baseline_archive = baseline.get("archive_dir")
    current_compare_archive = current_compare.get("archive_dir")
    current_rebuild_archive = current_rebuild.get("archive_dir")

    baseline_shape = baseline.get("output_shape")
    current_compare_shape = current_compare.get("output_shape")
    current_rebuild_shape = current_rebuild.get("output_shape")

    baseline_archive_touched_by_rebuild = baseline_archive == current_rebuild_archive
    current_archive_reused_between_compare_and_rebuild = current_compare_archive == current_rebuild_archive
    current_outputs_match_between_compare_and_rebuild = shape_equals(current_compare_shape, current_rebuild_shape)
    baseline_runtime_differs_from_current_compare = (
        baseline.get("effective_remote_tvm_python") != current_compare.get("effective_remote_tvm_python")
    )
    runtime_lineage = build_runtime_lineage(
        compare_env_remote_tvm_python=compare_env_remote_tvm_python,
        baseline=baseline,
        current_compare=current_compare,
        current_rebuild=current_rebuild,
    )
    baseline_abi_assessment, fair_compare_guard = build_baseline_abi_assessment(
        baseline=baseline,
        current_compare=current_compare,
        current_rebuild=current_rebuild,
        runtime_lineage=runtime_lineage,
        probe=baseline_current_safe_probe,
    )

    most_likely_249_source = (
        "baseline artifact/export lineage anchored at "
        f"{baseline.get('artifact_path')} "
        f"(archive {baseline_archive}, sha256 {baseline.get('artifact_sha256')})"
    )
    residual_runtime_uncertainty = (
        "baseline fair compare used a compat runtime override, so a pure runtime effect "
        "is not completely eliminated until the same baseline archive is rerun under the "
        "current-safe runtime"
    )
    if baseline_current_safe_probe["status"] == "current_safe_abi_incompatible":
        residual_runtime_uncertainty = (
            "current-safe ABI incompatibility is directly observed from the provided "
            "baseline probe, so residual runtime uncertainty is low."
        )
    elif baseline_current_safe_probe["status"] == "current_safe_probe_succeeded":
        residual_runtime_uncertainty = (
            "baseline was rerun under the current-safe runtime, so residual runtime "
            "uncertainty is materially reduced."
        )

    result = {
        "sources": {
            "compare_env": to_abs_project_path(compare_env),
            "compare_log": to_abs_project_path(compare_log),
            "current_rebuild_report": to_abs_project_path(rebuild_report_path),
            "baseline_current_safe_probe_log": (
                None
                if args.baseline_current_safe_probe_log is None
                else to_abs_project_path(args.baseline_current_safe_probe_log)
            ),
        },
        "baseline_compare": baseline,
        "current_compare": current_compare,
        "current_rebuild": current_rebuild,
        "runtime_lineage": runtime_lineage,
        "baseline_current_safe_probe": baseline_current_safe_probe,
        "lineage_assessment": {
            "baseline_archive_touched_by_rebuild": baseline_archive_touched_by_rebuild,
            "current_archive_reused_between_compare_and_rebuild": current_archive_reused_between_compare_and_rebuild,
            "current_outputs_match_between_compare_and_rebuild": current_outputs_match_between_compare_and_rebuild,
            "baseline_runtime_differs_from_current_compare": baseline_runtime_differs_from_current_compare,
            "baseline_shape_differs_from_current_compare": baseline_shape != current_compare_shape,
            "baseline_shape_differs_from_current_rebuild": baseline_shape != current_rebuild_shape,
            "most_likely_249_source": most_likely_249_source,
            "most_likely_249_source_confidence": "high",
            "residual_runtime_uncertainty": residual_runtime_uncertainty,
        },
        "baseline_abi_assessment": baseline_abi_assessment,
        "fair_compare_guard": fair_compare_guard,
        "next_board_probe": {
            "purpose": (
                "Rerun the baseline archive through the payload runner without the compat "
                "runtime override to isolate artifact lineage from runtime-version effects."
            ),
            "command": build_board_probe_command(compare_env),
            "expected_interpretation": (
                "If this still reports output_shape [1, 3, 249, 249] while using the "
                "current-safe runtime, the baseline artifact/export lineage is effectively "
                "confirmed as the source of the 249x249 output."
            ),
        },
    }

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if args.strict_fair_compare and not fair_compare_guard["claim_allowed"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
