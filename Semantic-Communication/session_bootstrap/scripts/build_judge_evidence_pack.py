#!/usr/bin/env python3
"""Build a unified judge-facing technical evidence pack."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from judge_evidence_utils import (
    DEFAULT_REPORT_DIR,
    dump_json,
    fmt,
    fmt_mib,
    latest_match,
    load_json,
    now_iso,
    now_stamp,
    parse_markdown_key_values,
    sanitize_json,
    to_float,
    write_text,
)


DEFAULT_TRUSTED_ARTIFACT = Path(
    "session_bootstrap/tmp/phytium_baseline_seeded_warm_start_current_incremental_chunk4_20260313_131545/optimized_model.so"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the consolidated judge-facing evidence pack.")
    parser.add_argument("--quality-formal-json", default="", help="Formal quality report JSON.")
    parser.add_argument("--hotspot-json", default="", help="Operator profiling / hotspot JSON.")
    parser.add_argument("--resource-json", default="", help="Resource profile JSON.")
    parser.add_argument("--snr-json", default="", help="SNR robustness report JSON.")
    parser.add_argument("--payload-report-md", default="", help="Trusted payload compare markdown.")
    parser.add_argument("--e2e-report-md", default="", help="Trusted real-reconstruction compare markdown.")
    parser.add_argument("--big-little-summary-md", default="", help="Optional big.LITTLE summary markdown.")
    parser.add_argument("--trusted-artifact", default=str(DEFAULT_TRUSTED_ARTIFACT), help="Trusted local artifact path.")
    parser.add_argument(
        "--report-prefix",
        default="",
        help="Output prefix without extension. Defaults to session_bootstrap/reports/judge_evidence_pack_<timestamp>.",
    )
    parser.add_argument(
        "--title",
        default="Judge Technical Evidence Pack",
        help="Markdown title.",
    )
    return parser.parse_args()


def resolve_path_or_latest(path_text: str, pattern: str | None = None) -> Path | None:
    if path_text:
        path = Path(path_text)
        if not path.is_file():
            raise SystemExit(f"ERROR: file not found: {path}")
        return path.resolve()
    if pattern is None:
        return None
    match = latest_match(DEFAULT_REPORT_DIR, pattern)
    return match.resolve() if match is not None else None


def parse_markdown_report(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = parse_markdown_key_values(path.read_text(encoding="utf-8"))
    return {"path": str(path), "fields": payload}


def artifact_summary(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
    }


def build_summary(report: dict[str, Any]) -> list[str]:
    quality = report.get("quality_report")
    payload = report.get("payload_report")
    e2e = report.get("e2e_report")
    resource = report.get("resource_profile")
    hotspot = report.get("hotspot_report")
    snr = report.get("snr_report")
    artifact = report.get("artifact")

    summary: list[str] = []
    if payload and payload["fields"]:
        summary.append(
            "Trusted payload benchmark holds at "
            f"{payload['fields'].get('baseline_run_median_ms', 'NA')} -> {payload['fields'].get('current_run_median_ms', 'NA')} ms "
            f"({payload['fields'].get('improvement_pct', 'NA')}% improvement)."
        )
    if e2e and e2e["fields"]:
        summary.append(
            "Trusted real reconstruction holds at "
            f"{e2e['fields'].get('baseline_run_median_ms', 'NA')} -> {e2e['fields'].get('current_run_median_ms', 'NA')} ms/image "
            f"({e2e['fields'].get('improvement_pct', 'NA')}% improvement)."
        )
    if quality:
        rows = quality.get("rows", [])
        current_row = next((row for row in rows if row.get("comparison_label") == "pytorch_vs_tvm_current"), None)
        baseline_row = next((row for row in rows if row.get("comparison_label") == "pytorch_vs_tvm_baseline"), None)
        if current_row and baseline_row:
            summary.append(
                "Current stays closer to the PyTorch reference than baseline by "
                f"{fmt((current_row['psnr']['aggregate_mean'] or 0.0) - (baseline_row['psnr']['aggregate_mean'] or 0.0), 4)} dB mean PSNR."
            )
    if hotspot:
        status = hotspot.get("overall_status")
        top_ops = ",".join(hotspot.get("recommended_full_hotspot_tasks", [])[:4]) or "NA"
        summary.append(f"Operator evidence is currently {status}; the top stage-weight hotspot set starts with {top_ops}.")
    if resource:
        vmstat = resource.get("vmstat_summary", {})
        summary.append(
            "Trusted current resource profile shows avg CPU user/system/idle/wait "
            f"{fmt(vmstat.get('avg_cpu_user_pct'), 3)} / {fmt(vmstat.get('avg_cpu_system_pct'), 3)} / "
            f"{fmt(vmstat.get('avg_cpu_idle_pct'), 3)} / {fmt(vmstat.get('avg_cpu_wait_pct'), 3)} %."
        )
    if artifact:
        summary.append(
            f"Trusted local artifact size is {artifact['size_bytes']} bytes ({fmt_mib(artifact['size_bytes'])} MiB)."
        )
    if snr:
        summary.append(
            f"Multi-SNR evidence currently covers {len(snr.get('latency_points', []))} latency points and {len(snr.get('quality_points', []))} quality points."
        )
    return summary


def build_defense_map(report: dict[str, Any]) -> list[dict[str, Any]]:
    quality = report.get("quality_report")
    hotspot = report.get("hotspot_report")
    resource = report.get("resource_profile")
    snr = report.get("snr_report")
    payload = report.get("payload_report")
    e2e = report.get("e2e_report")
    return [
        {
            "slide": "1. Trusted Performance Headline",
            "claim": "Current trusted artifact materially outperforms baseline on both payload and real reconstruction.",
            "evidence": [item for item in [payload and payload["path"], e2e and e2e["path"]] if item],
        },
        {
            "slide": "2. Reconstruction Quality",
            "claim": "Current keeps reconstruction quality at least comparable to baseline against the PyTorch reference.",
            "evidence": [item for item in [quality and quality.get("report_markdown")] if item],
        },
        {
            "slide": "3. Operator and System Bottlenecks",
            "claim": "The dominant optimization targets are already localized even though trusted runtime per-op profiling remains limited.",
            "evidence": [item for item in [hotspot and hotspot.get("summary_md"), resource and resource.get("wrapper_log_file")] if item],
        },
        {
            "slide": "4. Resource Footprint",
            "claim": "CPU load, free-memory floor, and artifact size are bounded and can be cited directly.",
            "evidence": [item for item in [resource and report.get("resource_json")] if item],
        },
        {
            "slide": "5. Robustness vs SNR",
            "claim": (
                "Current trusted chunk4 now has both latency and quality SNR coverage for 5 points."
                if snr and snr.get("quality_points")
                else "Historical SNR sweep already exists for latency, and the missing quality-vs-SNR path is fully scripted for manual collection."
            ),
            "evidence": [item for item in [snr and snr.get("report_markdown")] if item],
        },
    ]


def build_markdown(title: str, report: dict[str, Any]) -> str:
    quality = report.get("quality_report")
    hotspot = report.get("hotspot_report")
    resource = report.get("resource_profile")
    snr = report.get("snr_report")
    payload = report.get("payload_report")
    e2e = report.get("e2e_report")
    artifact = report.get("artifact")
    defense_map = report["defense_map"]

    lines = [
        f"# {title}",
        "",
        f"- run_id: {report['run_id']}",
        f"- generated_at: {report['generated_at']}",
        f"- report_json: {report['report_json']}",
        "",
        "## Executive Summary",
        "",
    ]
    for item in report["executive_summary"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Evidence Tracks", ""])
    if payload and payload["fields"]:
        lines.extend(
            [
                "### 1. Trusted Performance Baseline",
                "",
                f"- payload_report: {payload['path']}",
                f"- payload_median_ms: {payload['fields'].get('baseline_run_median_ms')} -> {payload['fields'].get('current_run_median_ms')}",
                f"- payload_improvement_pct: {payload['fields'].get('improvement_pct')}",
                f"- e2e_report: {e2e['path'] if e2e else 'NA'}",
            ]
        )
        if e2e and e2e["fields"]:
            lines.extend(
                [
                    f"- e2e_median_ms_per_image: {e2e['fields'].get('baseline_run_median_ms')} -> {e2e['fields'].get('current_run_median_ms')}",
                    f"- e2e_improvement_pct: {e2e['fields'].get('improvement_pct')}",
                ]
            )

    if quality:
        lines.extend(
            [
                "",
                "### 2. Formal Quality Report",
                "",
                f"- quality_report_markdown: {quality.get('report_markdown')}",
                f"- quality_report_json: {quality.get('report_json')}",
            ]
        )
        for finding in quality.get("findings", []):
            lines.append(f"- {finding}")

    if hotspot:
        runtime_phase = hotspot.get("runtime_phase", {})
        lines.extend(
            [
                "",
                "### 3. Operator-Level Profiling / Hotspots",
                "",
                f"- hotspot_report_json: {report.get('hotspot_json')}",
                f"- hotspot_overall_status: {hotspot.get('overall_status')}",
                f"- recommended_full_hotspot_tasks: {','.join(hotspot.get('recommended_full_hotspot_tasks', []))}",
                f"- runtime_status: {runtime_phase.get('status')}",
                f"- runtime_fallback_reason: {runtime_phase.get('fallback_reason')}",
            ]
        )

    if resource:
        vmstat = resource.get("vmstat_summary", {})
        target_last = resource.get("target_last_json", {})
        lines.extend(
            [
                "",
                "### 4. CPU / Memory / Artifact Size",
                "",
                f"- resource_profile_json: {report.get('resource_json')}",
                f"- wall_time_seconds: {resource.get('wall_time_seconds')}",
                f"- avg_cpu_user_system_idle_wait_pct: {fmt(vmstat.get('avg_cpu_user_pct'), 3)} / {fmt(vmstat.get('avg_cpu_system_pct'), 3)} / {fmt(vmstat.get('avg_cpu_idle_pct'), 3)} / {fmt(vmstat.get('avg_cpu_wait_pct'), 3)}",
                f"- min_free_kb: {fmt(vmstat.get('min_free_kb'), 0)}",
                f"- avg_runnable_max_runnable: {fmt(vmstat.get('avg_runnable'), 3)} / {fmt(vmstat.get('max_runnable'), 0)}",
                f"- target_run_median_ms: {fmt(target_last.get('run_median_ms'), 3)}",
                f"- target_artifact_sha256_match: {target_last.get('artifact_sha256_match')}",
            ]
        )
        if artifact:
            lines.extend(
                [
                    f"- trusted_local_artifact: {artifact['path']}",
                    f"- trusted_local_artifact_size_bytes: {artifact['size_bytes']}",
                    f"- trusted_local_artifact_size_mib: {fmt_mib(artifact['size_bytes'])}",
                ]
            )

    if snr:
        lines.extend(
            [
                "",
                "### 5. Multi-SNR Robustness",
                "",
                f"- snr_report_markdown: {snr.get('report_markdown')}",
                f"- snr_latency_points: {len(snr.get('latency_points', []))}",
                f"- snr_quality_points: {len(snr.get('quality_points', []))}",
                f"- snr_coverage_status: {snr.get('coverage_status')}",
                f"- latency_chart_svg: {snr.get('latency_chart_svg')}",
            ]
        )
        if snr.get("quality_chart_svg"):
            lines.append(f"- quality_chart_svg: {snr.get('quality_chart_svg')}")
        for finding in snr.get("findings", []):
            lines.append(f"- {finding}")

    lines.extend(
        [
            "",
            "## Defense Slide Map",
            "",
            "| Slide | Claim | Evidence |",
            "|---|---|---|",
        ]
    )
    for item in defense_map:
        lines.append(f"| {item['slide']} | {item['claim']} | {'; '.join(item['evidence']) or 'NA'} |")

    manual_command = snr.get("manual_command") if snr else None
    if manual_command:
        lines.extend(
            [
                "",
                (
                    "## Manual Operator Command For Refreshing SNR Quality Points"
                    if snr and snr.get("quality_points")
                    else "## Manual Operator Command For Missing SNR Quality Points"
                ),
                "",
                "```bash",
                manual_command,
                "```",
            ]
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Runtime per-op profiling on the trusted remote runtime still falls back to stage-weight hotspot evidence because vm.profile support is not validated there.",
            "- LPIPS is not guaranteed in historical data because the archived quality runs skipped it when the environment lacked torch/lpips.",
        ]
    )
    if snr and snr.get("quality_points"):
        lines.append("- The current SNR pack now includes 5 archived quality points for trusted chunk4; further work is mainly about upgrading LPIPS, not filling a blank table.")
    else:
        lines.append("- The current SNR pack is only partially complete until the manual quality-by-SNR loop is executed and archived.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()

    quality_json_path = resolve_path_or_latest(args.quality_formal_json, "judge_quality_formal_report_*.json")
    hotspot_json_path = resolve_path_or_latest(args.hotspot_json, "profiling_*.json")
    resource_json_path = resolve_path_or_latest(args.resource_json, "resource_profile_trusted_current_*.json")
    snr_json_path = resolve_path_or_latest(args.snr_json, "judge_snr_robustness_*.json")
    payload_md_path = resolve_path_or_latest(args.payload_report_md, "inference_compare_currentsafe_chunk4_refresh_*.md")
    e2e_md_path = resolve_path_or_latest(
        args.e2e_report_md, "inference_real_reconstruction_compare_currentsafe_chunk4_refresh_*.md"
    )
    big_little_md_path = resolve_path_or_latest(args.big_little_summary_md, "big_little_real_run_summary_*.md")

    report_prefix = (
        Path(args.report_prefix)
        if args.report_prefix
        else DEFAULT_REPORT_DIR / f"judge_evidence_pack_{now_stamp()}"
    )
    report_md = report_prefix.with_suffix(".md")
    report_json = report_prefix.with_suffix(".json")

    quality_report = load_json(quality_json_path) if quality_json_path else None
    hotspot_report = load_json(hotspot_json_path) if hotspot_json_path else None
    resource_profile = load_json(resource_json_path) if resource_json_path else None
    snr_report = load_json(snr_json_path) if snr_json_path else None
    payload_report = parse_markdown_report(payload_md_path)
    e2e_report = parse_markdown_report(e2e_md_path)
    big_little_summary = parse_markdown_report(big_little_md_path)
    artifact = artifact_summary(Path(args.trusted_artifact))

    report = {
        "run_id": report_prefix.name,
        "generated_at": now_iso(),
        "title": args.title,
        "report_markdown": str(report_md),
        "report_json": str(report_json),
        "quality_json": str(quality_json_path) if quality_json_path else None,
        "hotspot_json": str(hotspot_json_path) if hotspot_json_path else None,
        "resource_json": str(resource_json_path) if resource_json_path else None,
        "snr_json": str(snr_json_path) if snr_json_path else None,
        "quality_report": quality_report,
        "hotspot_report": hotspot_report,
        "resource_profile": resource_profile,
        "snr_report": snr_report,
        "payload_report": payload_report,
        "e2e_report": e2e_report,
        "big_little_summary": big_little_summary,
        "artifact": artifact,
    }
    report["executive_summary"] = build_summary(report)
    report["defense_map"] = build_defense_map(report)

    dump_json(report_json, sanitize_json(report))
    write_text(report_md, build_markdown(args.title, report))
    print(f"markdown_report={report_md}")
    print(f"json_report={report_json}")


if __name__ == "__main__":
    main()
