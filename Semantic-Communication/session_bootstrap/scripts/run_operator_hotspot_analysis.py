#!/usr/bin/env python3
"""Generate a practical operator hotspot report for paper task 5.1.

This entrypoint keeps `extract_hotspot_tasks.py` as the source of truth for
MetaSchedule task extraction, then adds a reproducible report layer that ties
the hotspot list back to the current trusted line and the next 4.2 decision.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from extract_hotspot_tasks import load_shell_env
from relax_ms_utils import RAW_STAGE_NAME, TUNED_STAGE_NAME


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ENV = (
    "session_bootstrap/config/"
    "rpc_tune_current_safe.baseline_seeded_warm_start."
    "recommended_cortex_a72_neon.2026-03-10.phytium_pi.env"
)
DEFAULT_INFERENCE_ENV = (
    "./session_bootstrap/config/inference_tvm310_safe.2026-03-10.phytium_pi.env"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run task-5.1 operator hotspot analysis for the trusted current line."
    )
    parser.add_argument(
        "--env",
        default=DEFAULT_ENV,
        help="Shell env file for the trusted current line.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=8,
        help="Number of top tuned-stage tasks to use for the 4.2 hotspot candidate list.",
    )
    parser.add_argument(
        "--run-id",
        default=f"trusted_current_{time.strftime('%Y%m%d_%H%M%S')}",
        help="Run id suffix used for profiling_*.{md,json} and hotspot_tasks_*.{md,json}.",
    )
    parser.add_argument(
        "--report-dir",
        default="",
        help="Optional report directory override. Defaults to REPORT_DIR from the env file.",
    )
    parser.add_argument(
        "--resource-profile",
        default="",
        help="Optional resource profile JSON. Defaults to latest resource_profile_trusted_current_*.json.",
    )
    parser.add_argument(
        "--quality-report",
        default="",
        help="Optional quality metrics JSON. Defaults to latest quality_metrics_*tvm_baseline_vs_tvm_current.json.",
    )
    parser.add_argument(
        "--reference-hotspot",
        default="",
        help="Optional historical hotspot JSON for comparison. Defaults to hotspot_tasks_20260311_0008.json if present.",
    )
    return parser.parse_args()


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def choose_latest(report_dir: Path, pattern: str) -> Path | None:
    matches = sorted(report_dir.glob(pattern))
    if not matches:
        return None
    return matches[-1]


def load_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_local_vm_profile_api_probe(local_python: str) -> dict[str, Any]:
    probe_code = """
import json
import tvm
from tvm import relax
from tvm.runtime import profiling

payload = {
    "python_executable": __import__("sys").executable,
    "tvm_version": getattr(tvm, "__version__", "unknown"),
    "virtual_machine_has_profile": hasattr(relax.VirtualMachine, "profile"),
    "profiling_report_methods": [
        name for name in dir(profiling.Report) if not name.startswith("_")
    ],
}
print(json.dumps(payload, ensure_ascii=False))
"""
    proc = subprocess.run(
        [local_python, "-c", probe_code],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def run_extract_hotspots(
    local_python: str,
    env_file: str,
    top_k: int,
    output_md: Path,
    output_json: Path,
) -> str:
    cmd = [
        local_python,
        str(SCRIPT_DIR / "extract_hotspot_tasks.py"),
        "--env",
        env_file,
        "--top-k",
        str(top_k),
        "--output",
        str(output_md),
        "--json-output",
        str(output_json),
    ]
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def infer_task_family(task_name: str) -> str:
    name = task_name.lower()
    if "reshape" in name:
        return "reshape"
    if "mirror_pad" in name or name.startswith("pad") or "_pad" in name:
        return "pad"
    if "conv2d" in name or "conv" in name:
        return "conv2d"
    if any(token in name for token in ("variance", "mean", "layernorm", "norm", "sqrt", "divide", "multiply")):
        return "norm_stats"
    return "other"


def summarize_stage(stage: dict[str, Any], top_k: int) -> dict[str, Any]:
    tasks = list(stage.get("tasks", []))
    total_weight = sum(int(row["weight"]) for row in tasks)
    ranked_rows: list[dict[str, Any]] = []
    cumulative_weight = 0
    for row in tasks:
        weight = int(row["weight"])
        cumulative_weight += weight
        ranked_rows.append(
            {
                **row,
                "family": infer_task_family(str(row["task_name"])),
                "weight_share_pct": round((weight / total_weight) * 100, 3) if total_weight else 0.0,
                "cumulative_weight_share_pct": round((cumulative_weight / total_weight) * 100, 3)
                if total_weight
                else 0.0,
            }
        )

    family_map: dict[str, dict[str, Any]] = {}
    for row in ranked_rows:
        family = str(row["family"])
        summary = family_map.setdefault(
            family,
            {
                "family": family,
                "weight": 0,
                "top_tasks": [],
            },
        )
        summary["weight"] += int(row["weight"])
        if len(summary["top_tasks"]) < 3:
            summary["top_tasks"].append(str(row["task_name"]))

    family_rows = []
    for family, summary in family_map.items():
        weight = int(summary["weight"])
        family_rows.append(
            {
                "family": family,
                "weight": weight,
                "weight_share_pct": round((weight / total_weight) * 100, 3) if total_weight else 0.0,
                "top_tasks": summary["top_tasks"],
            }
        )
    family_rows.sort(key=lambda row: (-int(row["weight"]), str(row["family"])))

    top_rows = ranked_rows[:top_k]
    return {
        "stage_name": stage.get("stage_name", TUNED_STAGE_NAME),
        "total_tasks": int(stage.get("total_tasks", len(tasks))),
        "total_weight": total_weight,
        "top_k": top_k,
        "top_rows": top_rows,
        "top_k_weight_share_pct": top_rows[-1]["cumulative_weight_share_pct"] if top_rows else 0.0,
        "recommended_full_hotspot_tasks": ",".join(str(row["task_name"]) for row in top_rows),
        "families": family_rows,
    }


def compare_with_reference(
    current_names: list[str],
    reference_path: Path | None,
    reference_json: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if reference_path is None or reference_json is None:
        return None
    ref_stage = reference_json.get("stages", {}).get(TUNED_STAGE_NAME, {})
    ref_names = [str(row["task_name"]) for row in ref_stage.get("tasks", [])[: len(current_names)]]
    return {
        "reference_json": str(reference_path),
        "same_top_k": current_names == ref_names,
        "reference_top_k": ref_names,
        "added_vs_reference": [name for name in current_names if name not in ref_names],
        "removed_vs_reference": [name for name in ref_names if name not in current_names],
    }


def build_resource_summary(resource_json: dict[str, Any] | None, resource_path: Path | None) -> dict[str, Any] | None:
    if resource_json is None or resource_path is None:
        return None
    vmstat = resource_json.get("vmstat_summary", {})
    target_last_json = resource_json.get("target_last_json", {})
    return {
        "resource_profile_json": str(resource_path),
        "run_id": resource_json.get("run_id"),
        "wall_time_seconds": resource_json.get("wall_time_seconds"),
        "avg_cpu_user_pct": vmstat.get("avg_cpu_user_pct"),
        "avg_cpu_system_pct": vmstat.get("avg_cpu_system_pct"),
        "avg_cpu_idle_pct": vmstat.get("avg_cpu_idle_pct"),
        "avg_cpu_wait_pct": vmstat.get("avg_cpu_wait_pct"),
        "avg_runnable": vmstat.get("avg_runnable"),
        "max_runnable": vmstat.get("max_runnable"),
        "min_free_kb": vmstat.get("min_free_kb"),
        "run_median_ms": target_last_json.get("run_median_ms"),
        "run_mean_ms": target_last_json.get("run_mean_ms"),
        "run_count": target_last_json.get("run_count"),
        "artifact_sha256": target_last_json.get("artifact_sha256"),
        "artifact_sha256_match": target_last_json.get("artifact_sha256_match"),
        "output_shape": target_last_json.get("output_shape"),
    }


def build_quality_summary(quality_json: dict[str, Any] | None, quality_path: Path | None) -> dict[str, Any] | None:
    if quality_json is None or quality_path is None:
        return None
    aggregate = quality_json.get("aggregate", {})
    return {
        "quality_report_json": str(quality_path),
        "run_id": quality_json.get("run_id"),
        "status": quality_json.get("status"),
        "matched_png_count": quality_json.get("matched_png_count"),
        "psnr_mean_db": aggregate.get("psnr_db", {}).get("mean"),
        "psnr_median_db": aggregate.get("psnr_db", {}).get("median"),
        "ssim_mean": aggregate.get("ssim", {}).get("mean"),
        "ssim_median": aggregate.get("ssim", {}).get("median"),
    }


def shell_single_quote(value: str) -> str:
    return shlex.quote(value)


def build_next_4_2_command(env_file: str, hotspot_tasks: str) -> str:
    report_id = "phytium_baseline_seeded_warm_start_current_incremental_hotspot_$(date +%Y%m%d_%H%M%S)"
    quoted_hotspots = shell_single_quote(hotspot_tasks)
    quoted_env = shell_single_quote(env_file)
    return "\n".join(
        [
            f"TUNE_OP_NAMES={quoted_hotspots} \\",
            "bash ./session_bootstrap/scripts/run_phytium_baseline_seeded_warm_start_current_incremental.sh \\",
            f"  --rebuild-env {quoted_env} \\",
            f"  --inference-env {DEFAULT_INFERENCE_ENV} \\",
            "  --total-trials 2000 \\",
            f'  --report-id "{report_id}" \\',
            "  --repeat 10 \\",
            "  --warmup-runs 2",
        ]
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    stage = payload["stage_weight_summary"]
    runtime_status = payload["runtime_profiling_status"]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Operator Hotspot Analysis\n\n")
        handle.write(f"- run_id: {payload['run_id']}\n")
        handle.write(f"- mode: {payload['mode']}\n")
        handle.write(f"- generated_at: {payload['generated_at']}\n")
        handle.write(f"- env_file: {payload['env_file']}\n")
        handle.write(f"- target: {payload['target']}\n")
        handle.write(f"- onnx_path: {payload['onnx_path']}\n")
        handle.write(f"- input_shape: {payload['input_shape']}\n")
        handle.write(f"- trusted_target_line: {payload['trusted_target_line']}\n\n")

        handle.write("## Runtime Profiling Status\n\n")
        handle.write(f"- status: {runtime_status['status']}\n")
        handle.write(f"- note: {runtime_status['note']}\n")
        handle.write(
            f"- local_vm_profile_api_available: {runtime_status['local_vm_profile_api_available']}\n"
        )
        handle.write(f"- local_tvm_version: {runtime_status['local_tvm_version']}\n")
        handle.write(
            f"- local_profiling_report_methods: {','.join(runtime_status['local_profiling_report_methods'])}\n\n"
        )

        resource_summary = payload.get("resource_profile_summary")
        if resource_summary:
            handle.write("## Trusted Current Resource Evidence\n\n")
            handle.write(f"- resource_profile_json: {resource_summary['resource_profile_json']}\n")
            handle.write(f"- resource_profile_run_id: {resource_summary['run_id']}\n")
            handle.write(
                "- cpu_summary_pct: "
                f"user={resource_summary['avg_cpu_user_pct']} "
                f"system={resource_summary['avg_cpu_system_pct']} "
                f"idle={resource_summary['avg_cpu_idle_pct']} "
                f"wait={resource_summary['avg_cpu_wait_pct']}\n"
            )
            handle.write(
                f"- runnable_tasks_avg_max: {resource_summary['avg_runnable']} / {resource_summary['max_runnable']}\n"
            )
            handle.write(f"- min_free_kb: {resource_summary['min_free_kb']}\n")
            handle.write(
                "- trusted_current_runtime_ms: "
                f"median={resource_summary['run_median_ms']} "
                f"mean={resource_summary['run_mean_ms']} "
                f"count={resource_summary['run_count']}\n"
            )
            handle.write(
                "- artifact_sha256_match: "
                f"{resource_summary['artifact_sha256_match']} "
                f"({resource_summary['artifact_sha256']})\n\n"
            )

        quality_summary = payload.get("quality_summary")
        if quality_summary:
            handle.write("## Quality Guard\n\n")
            handle.write(f"- quality_report_json: {quality_summary['quality_report_json']}\n")
            handle.write(f"- quality_run_id: {quality_summary['run_id']}\n")
            handle.write(f"- matched_png_count: {quality_summary['matched_png_count']}\n")
            handle.write(
                f"- psnr_mean_median_db: {quality_summary['psnr_mean_db']} / {quality_summary['psnr_median_db']}\n"
            )
            handle.write(
                f"- ssim_mean_median: {quality_summary['ssim_mean']} / {quality_summary['ssim_median']}\n\n"
            )

        handle.write("## Stage-Weight Hotspots\n\n")
        handle.write(f"- task_stage_used_for_recommendation: {stage['stage_name']}\n")
        handle.write(f"- total_tasks: {stage['total_tasks']}\n")
        handle.write(f"- total_stage_weight: {stage['total_weight']}\n")
        handle.write(f"- top_k: {stage['top_k']}\n")
        handle.write(f"- top_k_weight_share_pct: {stage['top_k_weight_share_pct']}\n")
        handle.write(
            f"- FULL_HOTSPOT_TASKS_candidate: {stage['recommended_full_hotspot_tasks']}\n\n"
        )

        handle.write("| rank | task_name | family | weight | share % | cumulative % | prim_funcs |\n")
        handle.write("|---|---|---|---:|---:|---:|---|\n")
        for row in stage["top_rows"]:
            prim_funcs = ",".join(row.get("prim_funcs", [])) or "-"
            handle.write(
                f"| {row['rank']} | {row['task_name']} | {row['family']} | "
                f"{row['weight']} | {row['weight_share_pct']} | "
                f"{row['cumulative_weight_share_pct']} | {prim_funcs} |\n"
            )
        handle.write("\n")

        handle.write("## Family Summary\n\n")
        handle.write("| family | total weight | share % | top tasks |\n")
        handle.write("|---|---:|---:|---|\n")
        for row in stage["families"]:
            handle.write(
                f"| {row['family']} | {row['weight']} | {row['weight_share_pct']} | "
                f"{','.join(row['top_tasks']) or '-'} |\n"
            )
        handle.write("\n")

        reference = payload.get("reference_comparison")
        if reference:
            handle.write("## Reference Check\n\n")
            handle.write(f"- reference_json: {reference['reference_json']}\n")
            handle.write(f"- same_top_k_as_reference: {reference['same_top_k']}\n")
            handle.write(
                f"- added_vs_reference: {','.join(reference['added_vs_reference']) or 'none'}\n"
            )
            handle.write(
                f"- removed_vs_reference: {','.join(reference['removed_vs_reference']) or 'none'}\n\n"
            )

        handle.write("## Artifacts\n\n")
        handle.write(f"- stage_hotspot_markdown: {payload['stage_hotspot_markdown']}\n")
        handle.write(f"- stage_hotspot_json: {payload['stage_hotspot_json']}\n")
        handle.write(f"- profiling_markdown: {payload['profiling_markdown']}\n")
        handle.write(f"- profiling_json: {payload['profiling_json']}\n\n")

        handle.write("## Next 4.2 Command\n\n")
        handle.write("```bash\n")
        handle.write(payload["next_4_2_command"])
        handle.write("\n```\n\n")

        handle.write("## Limitations\n\n")
        for item in payload["limitations"]:
            handle.write(f"- {item}\n")


def main() -> None:
    args = parse_args()
    env_path = resolve_project_path(args.env)
    if not env_path.is_file():
        raise SystemExit(f"Env file not found: {env_path}")

    env_vars = load_shell_env(str(env_path))
    report_dir_value = args.report_dir or env_vars.get("REPORT_DIR", "./session_bootstrap/reports")
    report_dir = resolve_project_path(report_dir_value)
    report_dir.mkdir(parents=True, exist_ok=True)

    local_python = env_vars.get("LOCAL_TVM_PYTHON") or env_vars.get("TVM_PYTHON") or sys.executable
    run_id = args.run_id

    stage_md = report_dir / f"hotspot_tasks_{run_id}.md"
    stage_json = report_dir / f"hotspot_tasks_{run_id}.json"
    profiling_md = report_dir / f"profiling_{run_id}.md"
    profiling_json = report_dir / f"profiling_{run_id}.json"

    extract_stdout = run_extract_hotspots(
        local_python=local_python,
        env_file=str(env_path),
        top_k=max(1, args.top_k),
        output_md=stage_md,
        output_json=stage_json,
    )
    stage_payload = load_json_if_exists(stage_json)
    if stage_payload is None:
        raise SystemExit(f"Failed to load generated hotspot JSON: {stage_json}")

    tuned_stage = stage_payload.get("stages", {}).get(TUNED_STAGE_NAME, {})
    raw_stage = stage_payload.get("stages", {}).get(RAW_STAGE_NAME, {})
    stage_summary = summarize_stage(tuned_stage, max(1, args.top_k))
    current_top_names = [str(row["task_name"]) for row in stage_summary["top_rows"]]

    resource_path = (
        resolve_project_path(args.resource_profile)
        if args.resource_profile
        else choose_latest(report_dir, "resource_profile_trusted_current_*.json")
    )
    quality_path = (
        resolve_project_path(args.quality_report)
        if args.quality_report
        else choose_latest(report_dir, "quality_metrics_*tvm_baseline_vs_tvm_current.json")
    )
    reference_path = (
        resolve_project_path(args.reference_hotspot)
        if args.reference_hotspot
        else resolve_project_path("session_bootstrap/reports/hotspot_tasks_20260311_0008.json")
    )
    if reference_path and not reference_path.is_file():
        reference_path = None

    resource_json = load_json_if_exists(resource_path)
    quality_json = load_json_if_exists(quality_path)
    reference_json = load_json_if_exists(reference_path)
    profile_probe = run_local_vm_profile_api_probe(local_python)

    payload = {
        "run_id": run_id,
        "mode": "stage_weight_hotspot_analysis",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "env_file": str(env_path),
        "target": stage_payload.get("target") or env_vars.get("TARGET", ""),
        "onnx_path": stage_payload.get("onnx_path") or env_vars.get("ONNX_MODEL_PATH", ""),
        "input_shape": stage_payload.get("input_shape") or env_vars.get("TUNE_INPUT_SHAPE", ""),
        "trusted_target_line": "Phytium Pi current-safe / cortex-a72 + neon",
        "local_python": local_python,
        "runtime_profiling_status": {
            "status": "not_productized",
            "note": (
                "The repo has stage-weight hotspot extraction and the TVM VM profile API exists "
                "locally, but there is no validated trusted remote per-op profiling wrapper yet. "
                "This 5.1 artifact promotes the current stage-weight hotspot path to first-class status."
            ),
            "local_vm_profile_api_available": profile_probe["virtual_machine_has_profile"],
            "local_tvm_version": profile_probe["tvm_version"],
            "local_profiling_report_methods": profile_probe["profiling_report_methods"],
        },
        "extract_hotspots_stdout": extract_stdout.splitlines(),
        "raw_import_total_tasks": raw_stage.get("total_tasks"),
        "stage_weight_summary": stage_summary,
        "resource_profile_summary": build_resource_summary(resource_json, resource_path),
        "quality_summary": build_quality_summary(quality_json, quality_path),
        "reference_comparison": compare_with_reference(current_top_names, reference_path, reference_json),
        "stage_hotspot_markdown": str(stage_md),
        "stage_hotspot_json": str(stage_json),
        "profiling_markdown": str(profiling_md),
        "profiling_json": str(profiling_json),
        "next_4_2_command": build_next_4_2_command(str(env_path), stage_summary["recommended_full_hotspot_tasks"]),
        "limitations": [
            "This report uses tuned-stage MetaSchedule weight as a hotspot proxy, not true remote per-op wall time.",
            "Trusted resource evidence says the current path is compute-heavy, but it does not attribute latency to individual operators.",
            "Do not lock 7.1 manual TIR targets from reshape-heavy stage weights alone; get runtime or focused micro-benchmark evidence first.",
        ],
    }

    with profiling_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    write_markdown(profiling_md, payload)

    print(f"run_id={run_id}")
    print(f"stage_hotspot_markdown={stage_md}")
    print(f"stage_hotspot_json={stage_json}")
    print(f"profiling_markdown={profiling_md}")
    print(f"profiling_json={profiling_json}")
    print(f"recommended_full_hotspot_tasks={stage_summary['recommended_full_hotspot_tasks']}")
    print(f"top_k_weight_share_pct={stage_summary['top_k_weight_share_pct']}")
    print(f"runtime_profiling_status={payload['runtime_profiling_status']['status']}")


if __name__ == "__main__":
    main()
