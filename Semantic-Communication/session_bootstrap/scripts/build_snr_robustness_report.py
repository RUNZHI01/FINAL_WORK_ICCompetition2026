#!/usr/bin/env python3
"""Build a judge-facing multi-SNR robustness summary and curve."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from judge_evidence_utils import (
    DEFAULT_REPORT_DIR,
    build_line_chart_svg,
    dump_json,
    fmt,
    latest_match,
    load_json,
    now_iso,
    now_stamp,
    parse_markdown_key_values,
    parse_table_rows,
    sanitize_json,
    to_float,
    write_text,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a formal multi-SNR robustness summary.")
    parser.add_argument(
        "--summary-md",
        default="",
        help="Existing snr_sweep_*.md summary. Defaults to the latest match when no point inputs are given.",
    )
    parser.add_argument(
        "--snr-report",
        action="append",
        default=[],
        help="Explicit SNR point in the form '<snr>:<full_report.md>'. Repeat as needed.",
    )
    parser.add_argument(
        "--quality-json",
        action="append",
        default=[],
        help="Optional quality point in the form '<snr>:<quality.json>'. Repeat as needed.",
    )
    parser.add_argument(
        "--report-prefix",
        default="",
        help="Output prefix without extension. Defaults to session_bootstrap/reports/judge_snr_robustness_<timestamp>.",
    )
    parser.add_argument(
        "--title",
        default="Multi-SNR Robustness Report",
        help="Markdown title.",
    )
    return parser.parse_args()


def parse_summary_md(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    text = path.read_text(encoding="utf-8")
    rows = parse_table_rows(text, "SNR_CURRENT")
    snr_key = "SNR_CURRENT"
    if not rows:
        rows = parse_table_rows(text, "SNR")
        snr_key = "SNR"
    points = []
    for row in rows:
        snr = to_float(row.get(snr_key))
        if snr is None:
            continue
        baseline_ms = to_float(row.get("Baseline ms"))
        current_ms = to_float(row.get("Current ms"))
        if current_ms is None:
            current_ms = to_float(row.get("median ms/image"))
        status = row.get("Status")
        if status is None and row.get("SHA match") in {"True", "False"}:
            status = "success" if row.get("SHA match") == "True" else "sha_mismatch"
        points.append(
            {
                "snr": snr,
                "status": status,
                "baseline_ms": baseline_ms,
                "current_ms": current_ms,
                "improvement_pct": to_float(row.get("Improvement %")),
                "source_summary": str(path),
            }
        )
    source_reports: list[str] = []
    in_sources = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "## Source Reports":
            in_sources = True
            continue
        if in_sources and line.startswith("- "):
            source_reports.append(line[2:].strip())
        elif in_sources and line:
            break
    return points, source_reports


def parse_point_spec(spec: str) -> tuple[float, Path]:
    if ":" not in spec:
        raise SystemExit(f"ERROR: expected '<snr>:<path>' but got: {spec}")
    snr_text, path_text = spec.split(":", 1)
    snr_value = to_float(snr_text)
    if snr_value is None:
        raise SystemExit(f"ERROR: invalid SNR value in spec: {spec}")
    path = Path(path_text)
    if not path.is_file():
        raise SystemExit(f"ERROR: report not found: {path}")
    return snr_value, path.resolve()


def parse_full_report(path: Path, snr_value: float) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = parse_markdown_key_values(text)
    return {
        "snr": snr_value,
        "status": payload.get("status"),
        "baseline_ms": to_float(payload.get("baseline_elapsed_ms")),
        "current_ms": to_float(payload.get("current_elapsed_ms")),
        "improvement_pct": to_float(payload.get("improvement_pct")),
        "execution_id": payload.get("execution_id"),
        "source_report": str(path),
    }


def load_quality_point(spec: str) -> dict[str, Any]:
    snr_value, path = parse_point_spec(spec)
    payload = load_json(path)
    aggregate = payload.get("aggregate", {})
    lpips_aggregate = aggregate.get("lpips") or {}
    return {
        "snr": snr_value,
        "comparison_label": payload.get("comparison_label"),
        "run_id": payload.get("run_id"),
        "source_json": str(path),
        "psnr_mean_db": aggregate.get("psnr_db", {}).get("mean"),
        "ssim_mean": aggregate.get("ssim", {}).get("mean"),
        "lpips_mean": lpips_aggregate.get("mean") if isinstance(lpips_aggregate, dict) else None,
        "lpips_status": payload.get("lpips_status"),
    }


def resolve_latency_points(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str]]:
    if args.snr_report:
        points = [parse_full_report(path, snr) for snr, path in (parse_point_spec(spec) for spec in args.snr_report)]
        return points, []
    summary_path = Path(args.summary_md) if args.summary_md else latest_match(DEFAULT_REPORT_DIR, "snr_sweep_*.md")
    if summary_path is None or not summary_path.is_file():
        raise SystemExit("ERROR: no SNR summary markdown found")
    return parse_summary_md(summary_path.resolve())


def build_findings(points: list[dict[str, Any]], quality_points: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    if not points:
        return ["No latency points were parsed."]
    current_points = [point for point in points if point.get("current_ms") is not None]
    if current_points:
        best = min(current_points, key=lambda item: item["current_ms"])
        worst = max(current_points, key=lambda item: item["current_ms"])
        findings.append(
            f"Historical current latency is best at SNR={fmt(best['snr'], 0)} with {fmt(best['current_ms'], 3)} ms and worst at SNR={fmt(worst['snr'], 0)} with {fmt(worst['current_ms'], 3)} ms."
        )
    regressions = [point for point in points if (point.get("improvement_pct") or 0.0) < 0]
    if regressions:
        worst_regression = min(regressions, key=lambda item: item["improvement_pct"])
        findings.append(
            f"The strongest historical regression appears at SNR={fmt(worst_regression['snr'], 0)} with improvement_pct={fmt(worst_regression['improvement_pct'], 2)}%."
        )
    if quality_points:
        quality_best = max(quality_points, key=lambda item: item.get("psnr_mean_db") or float("-inf"))
        findings.append(
            f"Quality coverage exists for {len(quality_points)} SNR points; best mean PSNR currently recorded is {fmt(quality_best.get('psnr_mean_db'), 4)} dB at SNR={fmt(quality_best['snr'], 0)}."
        )
    else:
        findings.append("Quality-by-SNR points are not yet archived locally; only the historical latency sweep is currently plotted.")
    return findings


def build_manual_commands() -> str:
    return "\n".join(
        [
            "for snr in 1 4 7 10 13; do",
            '  RUN_TAG="judge_snr_${snr}_$(date +%Y%m%d_%H%M%S)"',
            '  ENV_COPY="session_bootstrap/tmp/${RUN_TAG}.env"',
            '  cp session_bootstrap/tmp/inference_real_reconstruction_compare_run_20260311_212301.env "$ENV_COPY"',
            '  sed -i \\',
            '    -e "s#^INFERENCE_OUTPUT_PREFIX=.*#INFERENCE_OUTPUT_PREFIX=${RUN_TAG}#" \\',
            '    -e "s#^INFERENCE_REAL_OUTPUT_PREFIX=.*#INFERENCE_REAL_OUTPUT_PREFIX=${RUN_TAG}#" \\',
            '    -e "s#^REMOTE_SNR_CURRENT=.*#REMOTE_SNR_CURRENT=${snr}#" \\',
            '    "$ENV_COPY"',
            "",
            '  bash ./session_bootstrap/scripts/run_remote_pytorch_reference_reconstruction.sh \\',
            '    --env-file "$ENV_COPY" \\',
            '    --output-prefix "${RUN_TAG}_pytorch_ref" \\',
            '    --snr "$snr"',
            "",
            '  set -a',
            '  source "$ENV_COPY"',
            '  set +a',
            '  bash ./session_bootstrap/scripts/run_remote_current_real_reconstruction.sh --variant current',
            "",
            '  REF_DIR="${REMOTE_OUTPUT_BASE}/${RUN_TAG}_pytorch_ref"',
            '  CUR_DIR="${REMOTE_OUTPUT_BASE}/${RUN_TAG}_current"',
            '  python3 ./session_bootstrap/scripts/compute_image_quality_metrics.py \\',
            '    --ref-dir "${REF_DIR}/reconstructions" \\',
            '    --test-dir "${CUR_DIR}/reconstructions" \\',
            '    --comparison-label "pytorch_vs_tvm_current_snr${snr}" \\',
            '    --report-prefix "session_bootstrap/reports/${RUN_TAG}_quality"',
            "done",
        ]
    )


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"- run_id: {report['run_id']}",
        f"- generated_at: {report['generated_at']}",
        f"- latency_point_count: {len(report['latency_points'])}",
        f"- quality_point_count: {len(report['quality_points'])}",
        f"- coverage_status: {report['coverage_status']}",
        f"- report_json: {report['report_json']}",
        f"- latency_chart_svg: {report['latency_chart_svg']}",
    ]
    if report.get("quality_chart_svg"):
        lines.append(f"- quality_chart_svg: {report['quality_chart_svg']}")
    lines.extend(
        [
            "",
            "## Latency Curve",
            "",
            "| SNR | Status | Baseline ms | Current ms | Improvement % | Source |",
            "|---:|---|---:|---:|---:|---|",
        ]
    )
    for point in report["latency_points"]:
        source = point.get("source_report") or point.get("source_summary") or "NA"
        lines.append(
            f"| {fmt(point['snr'], 0)} | {point.get('status', 'NA')} | {fmt(point.get('baseline_ms'), 3)} | {fmt(point.get('current_ms'), 3)} | {fmt(point.get('improvement_pct'), 2)} | {source} |"
        )

    lines.extend(["", "## Findings", ""])
    for finding in report["findings"]:
        lines.append(f"- {finding}")

    if report["quality_points"]:
        lines.extend(
            [
                "",
                "## Quality Points",
                "",
                "| SNR | Comparison | PSNR (dB) | SSIM | LPIPS | Source |",
                "|---:|---|---:|---:|---:|---|",
            ]
        )
        for point in report["quality_points"]:
            lines.append(
                f"| {fmt(point['snr'], 0)} | {point.get('comparison_label')} | {fmt(point.get('psnr_mean_db'), 4)} | {fmt(point.get('ssim_mean'), 6)} | {fmt(point.get('lpips_mean'), 6)} | {point.get('source_json')} |"
            )
    else:
        lines.extend(
            [
                "",
                "## Quality Points",
                "",
                "- No per-SNR quality JSON was provided. The report therefore documents the historical latency sweep only.",
            ]
        )

    if report["source_reports"]:
        lines.extend(["", "## Historical Source Reports", ""])
        for path in report["source_reports"]:
            lines.append(f"- {path}")

    lines.extend(
        [
            "",
            "## Manual Operator Command",
            "",
            "```bash",
            report["manual_command"],
            "```",
            "",
            "## Limitations",
            "",
        ]
    )
    if report["quality_points"]:
        lines.append("- Quality-vs-SNR points are now archived locally for the current trusted chunk4 line; LPIPS remains environment-gated.")
    else:
        lines.append("- Existing archived SNR evidence is latency-heavy; quality-vs-SNR still needs the manual board run above.")
    lines.append("- The generated SVG is local and dependency-free; it is meant for judge materials and not as a scientific plotting backend.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    latency_points, source_reports = resolve_latency_points(args)
    latency_points.sort(key=lambda item: item["snr"])
    quality_points = [load_quality_point(spec) for spec in args.quality_json]
    quality_points.sort(key=lambda item: item["snr"])

    report_prefix = (
        Path(args.report_prefix)
        if args.report_prefix
        else DEFAULT_REPORT_DIR / f"judge_snr_robustness_{now_stamp()}"
    )
    report_md = report_prefix.with_suffix(".md")
    report_json = report_prefix.with_suffix(".json")
    latency_svg = report_prefix.with_name(report_prefix.name + "_latency.svg")
    quality_svg = report_prefix.with_name(report_prefix.name + "_quality.svg") if quality_points else None

    latency_series = []
    baseline_points = [(point["snr"], point.get("baseline_ms")) for point in latency_points if point.get("baseline_ms") is not None]
    current_points = [(point["snr"], point.get("current_ms")) for point in latency_points if point.get("current_ms") is not None]
    if baseline_points:
        latency_series.append(
            {
                "name": "baseline",
                "color": "#94a3b8",
                "points": baseline_points,
            }
        )
    if current_points:
        latency_series.append(
            {
                "name": "current",
                "color": "#2563eb",
                "points": current_points,
            }
        )
    latency_svg_text = build_line_chart_svg(
        title="Historical Latency vs SNR",
        x_label="SNR (dB)",
        y_label="Latency (ms)",
        series=latency_series,
    )
    write_text(latency_svg, latency_svg_text)

    quality_svg_path = None
    if quality_svg is not None:
        quality_svg_text = build_line_chart_svg(
            title="Mean PSNR vs SNR",
            x_label="SNR (dB)",
            y_label="PSNR (dB)",
            series=[
                {
                    "name": "mean_psnr",
                    "color": "#059669",
                    "points": [(point["snr"], point.get("psnr_mean_db")) for point in quality_points],
                }
            ],
        )
        write_text(quality_svg, quality_svg_text)
        quality_svg_path = str(quality_svg)

    report = {
        "run_id": report_prefix.name,
        "generated_at": now_iso(),
        "title": args.title,
        "report_markdown": str(report_md),
        "report_json": str(report_json),
        "latency_chart_svg": str(latency_svg),
        "quality_chart_svg": quality_svg_path,
        "coverage_status": "latency_and_quality" if quality_points else "latency_only",
        "latency_points": latency_points,
        "quality_points": quality_points,
        "source_reports": source_reports,
        "findings": build_findings(latency_points, quality_points),
        "manual_command": build_manual_commands(),
    }
    dump_json(report_json, sanitize_json(report))
    write_text(report_md, build_markdown(report))
    print(f"latency_points={len(latency_points)}")
    print(f"quality_points={len(quality_points)}")
    print(f"markdown_report={report_md}")
    print(f"json_report={report_json}")


if __name__ == "__main__":
    main()
