#!/usr/bin/env python3
"""Build a consolidated judge-facing PSNR/SSIM/LPIPS report."""

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
    latest_match,
    load_json,
    mean_ci95,
    now_iso,
    now_stamp,
    sanitize_json,
    slugify,
    write_text,
)


DEFAULT_PATTERNS = [
    "quality_metrics_*pytorch_vs_tvm_baseline.json",
    "quality_metrics_*pytorch_vs_tvm_current.json",
    "quality_metrics_*tvm_baseline_vs_tvm_current.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a formal quality matrix from quality_metrics JSON files.")
    parser.add_argument(
        "--quality-json",
        action="append",
        default=[],
        help="Input quality JSON. Repeat for multiple comparisons. Defaults to the latest known trio.",
    )
    parser.add_argument(
        "--report-prefix",
        default="",
        help="Output prefix without extension. Defaults to session_bootstrap/reports/judge_quality_formal_report_<timestamp>.",
    )
    parser.add_argument(
        "--title",
        default="Formal Quality Report",
        help="Markdown title.",
    )
    return parser.parse_args()


def resolve_inputs(paths: list[str]) -> list[Path]:
    if paths:
        resolved = [Path(path) for path in paths]
    else:
        resolved = []
        for pattern in DEFAULT_PATTERNS:
            match = latest_match(DEFAULT_REPORT_DIR, pattern)
            if match is not None:
                resolved.append(match)
    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in resolved:
        if not path.is_file():
            raise SystemExit(f"ERROR: quality JSON not found: {path}")
        canonical = path.resolve()
        if canonical in seen:
            continue
        seen.add(canonical)
        unique_paths.append(canonical)
    if not unique_paths:
        raise SystemExit("ERROR: no quality JSON inputs found")
    return unique_paths


def metric_ci(payload: dict[str, Any], metric_key: str) -> dict[str, Any]:
    values = [row.get(metric_key) for row in payload.get("per_image", [])]
    summary = mean_ci95(values)
    aggregate = payload.get("aggregate", {})
    report_metric = aggregate.get(metric_key) or {}
    summary["aggregate_mean"] = report_metric.get("mean")
    summary["aggregate_median"] = report_metric.get("median")
    summary["aggregate_std"] = report_metric.get("std")
    summary["aggregate_min"] = report_metric.get("min")
    summary["aggregate_max"] = report_metric.get("max")
    return summary


def canonicalize_comparison_label(label: str) -> str:
    if label.startswith("pytorch_vs_tvm_current"):
        return "pytorch_vs_tvm_current"
    if label.startswith("pytorch_vs_tvm_baseline"):
        return "pytorch_vs_tvm_baseline"
    if label.startswith("tvm_baseline_vs_tvm_current"):
        return "tvm_baseline_vs_tvm_current"
    return label


def build_row(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    psnr_ci = metric_ci(payload, "psnr_db")
    ssim_ci = metric_ci(payload, "ssim")
    lpips_ci = metric_ci(payload, "lpips")
    raw_label = payload.get("comparison_label", path.stem)
    return {
        "comparison_label": canonicalize_comparison_label(raw_label),
        "comparison_label_raw": raw_label,
        "run_id": payload.get("run_id", path.stem),
        "source_json": str(path),
        "source_markdown": payload.get("markdown_report"),
        "status": payload.get("status"),
        "matched_png_count": payload.get("matched_png_count"),
        "compared_image_count": payload.get("compared_image_count"),
        "missing_in_test_count": payload.get("missing_in_test_count"),
        "extra_in_test_count": payload.get("extra_in_test_count"),
        "cropped_pair_count": payload.get("cropped_pair_count"),
        "shape_mismatch_status": payload.get("shape_mismatch_status"),
        "shape_mismatch_message": payload.get("shape_mismatch_message"),
        "lpips_status": payload.get("lpips_status"),
        "psnr": psnr_ci,
        "ssim": ssim_ci,
        "lpips": lpips_ci,
        "worst_cases": payload.get("worst_cases", []),
    }


def build_findings(rows: list[dict[str, Any]]) -> list[str]:
    by_label = {row["comparison_label"]: row for row in rows}
    findings: list[str] = []

    baseline_row = by_label.get("pytorch_vs_tvm_baseline")
    current_row = by_label.get("pytorch_vs_tvm_current")
    tvm_row = by_label.get("tvm_baseline_vs_tvm_current")

    if baseline_row and current_row:
        psnr_delta = (current_row["psnr"]["aggregate_mean"] or 0.0) - (baseline_row["psnr"]["aggregate_mean"] or 0.0)
        ssim_delta = (current_row["ssim"]["aggregate_mean"] or 0.0) - (baseline_row["ssim"]["aggregate_mean"] or 0.0)
        findings.append(
            "Against the same PyTorch reference, current is "
            f"{fmt(psnr_delta, 4)} dB higher in mean PSNR and {fmt(ssim_delta, 6)} higher in mean SSIM than baseline."
        )
    if tvm_row:
        findings.append(
            "Direct TVM baseline-vs-current divergence is "
            f"{fmt(tvm_row['psnr']['aggregate_mean'], 4)} dB PSNR and {fmt(tvm_row['ssim']['aggregate_mean'], 6)} SSIM."
        )
    if any((row["lpips"]["count"] or 0) == 0 for row in rows):
        findings.append("LPIPS is missing for at least one comparison; keep PSNR/SSIM as the formal minimum set and treat LPIPS as environment-gated complementary evidence.")
    if any((row.get("cropped_pair_count") or 0) > 0 for row in rows):
        findings.append("At least one comparison required spatial normalization; judge-facing tables should footnote the crop policy.")
    return findings


def flatten_worst_cases(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for row in rows:
        for case in row.get("worst_cases", [])[:5]:
            merged.append(
                {
                    "comparison_label": row["comparison_label"],
                    "relative_path": case.get("relative_path"),
                    "psnr_db": case.get("psnr_db"),
                    "ssim": case.get("ssim"),
                    "lpips": case.get("lpips"),
                }
            )
    merged.sort(key=lambda item: (item.get("psnr_db") is None, item.get("psnr_db", float("inf"))))
    return merged[:limit]


def build_markdown(title: str, report: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- run_id: {report['run_id']}",
        f"- generated_at: {report['generated_at']}",
        f"- comparison_count: {len(report['rows'])}",
        f"- report_json: {report['report_json']}",
        "",
        "## Aggregate Matrix",
        "",
        "| Comparison | Images | PSNR mean | PSNR 95% CI | SSIM mean | SSIM 95% CI | LPIPS mean | LPIPS 95% CI | Notes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rows"]:
        notes = [
            f"status={row['status']}",
            f"crop={row['cropped_pair_count']}",
            f"missing={row['missing_in_test_count']}",
            f"extra={row['extra_in_test_count']}",
        ]
        lines.append(
            f"| {row['comparison_label']} | {row['compared_image_count']} | "
            f"{fmt(row['psnr']['aggregate_mean'], 4)} | {fmt(row['psnr']['ci95_half_width'], 4)} | "
            f"{fmt(row['ssim']['aggregate_mean'], 6)} | {fmt(row['ssim']['ci95_half_width'], 6)} | "
            f"{fmt(row['lpips']['aggregate_mean'], 6)} | {fmt(row['lpips']['ci95_half_width'], 6)} | "
            f"{'; '.join(notes)} |"
        )
    lines.extend(
        [
            "",
            "## Findings",
            "",
        ]
    )
    for finding in report["findings"]:
        lines.append(f"- {finding}")

    if report["worst_cases"]:
        lines.extend(
            [
                "",
                "## Worst Cases",
                "",
                "| Comparison | Image | PSNR (dB) | SSIM | LPIPS |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for case in report["worst_cases"]:
            lines.append(
                f"| {case['comparison_label']} | {case['relative_path']} | {fmt(case['psnr_db'], 4)} | {fmt(case['ssim'], 6)} | {fmt(case['lpips'], 6)} |"
            )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- The report is descriptive by default; it does not silently enforce pass/fail thresholds.",
            "- LPIPS remains environment-dependent because the historical run skipped it when torch/lpips was unavailable.",
            "- Historical data is consumed as-is from quality_metrics JSON files; regenerate the source JSONs if the underlying reconstruction directories change.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    input_paths = resolve_inputs(args.quality_json)

    rows_by_label: dict[str, dict[str, Any]] = {}
    for path in input_paths:
        row = build_row(path, load_json(path))
        rows_by_label[row["comparison_label"]] = row
    rows = list(rows_by_label.values())
    rows.sort(key=lambda row: row["comparison_label"])
    report_prefix = (
        Path(args.report_prefix)
        if args.report_prefix
        else DEFAULT_REPORT_DIR / f"judge_quality_formal_report_{now_stamp()}"
    )
    report_json = report_prefix.with_suffix(".json")
    report_md = report_prefix.with_suffix(".md")
    run_id = report_prefix.name or f"judge_quality_formal_report_{slugify(args.title)}"

    report = {
        "run_id": run_id,
        "generated_at": now_iso(),
        "title": args.title,
        "report_json": str(report_json),
        "report_markdown": str(report_md),
        "rows": rows,
        "findings": build_findings(rows),
        "worst_cases": flatten_worst_cases(rows),
    }
    markdown = build_markdown(args.title, report)
    dump_json(report_json, sanitize_json(report))
    write_text(report_md, markdown)
    print(f"quality_inputs={len(rows)}")
    print(f"markdown_report={report_md}")
    print(f"json_report={report_json}")


if __name__ == "__main__":
    main()
