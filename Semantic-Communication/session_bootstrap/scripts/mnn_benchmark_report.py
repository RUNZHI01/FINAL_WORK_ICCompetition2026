#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a consolidated MNN benchmark matrix report.")
    parser.add_argument("--results-jsonl", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--report-md", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--title", default="MNN Benchmark Report")
    return parser.parse_args()


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def result_sort_key(record: dict[str, Any]) -> tuple[float, float]:
    runner = record.get("runner_payload") or {}
    total_wall_ms = runner.get("total_wall_ms")
    mean_total_ms = ((runner.get("sample_stats") or {}).get("total_ms") or {}).get("mean_ms")
    total_sort = float(total_wall_ms) if isinstance(total_wall_ms, (int, float)) else float("inf")
    mean_sort = float(mean_total_ms) if isinstance(mean_total_ms, (int, float)) else float("inf")
    return (total_sort, mean_sort)


def best_record(records: list[dict[str, Any]], *, model_variant: str | None = None) -> dict[str, Any] | None:
    candidates = []
    for record in records:
        if record.get("status") != "ok":
            continue
        if model_variant is not None and record.get("model_variant") != model_variant:
            continue
        candidates.append(record)
    if not candidates:
        return None
    return sorted(candidates, key=result_sort_key)[0]


def simplify_best(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    runner = record.get("runner_payload") or {}
    quality = record.get("quality_summary") or {}
    return {
        "config_id": record.get("config_id"),
        "model_variant": record.get("model_variant"),
        "precision": record.get("precision"),
        "interpreter_count": record.get("interpreter_count"),
        "session_threads": record.get("session_threads"),
        "shape_mode": record.get("shape_mode"),
        "total_wall_ms": runner.get("total_wall_ms"),
        "images_per_sec": runner.get("images_per_sec"),
        "mean_total_ms": ((runner.get("sample_stats") or {}).get("total_ms") or {}).get("mean_ms"),
        "psnr_db": quality.get("psnr_db"),
        "ssim": quality.get("ssim"),
        "lpips": quality.get("lpips"),
    }


def build_findings(records: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    best_overall = best_record(records)
    best_fp32 = best_record(records, model_variant="fp32")
    best_fp16 = best_record(records, model_variant="fp16")
    best_int8 = best_record(records, model_variant="int8")
    failed = [record for record in records if record.get("status") != "ok"]

    if best_overall is not None:
        findings.append(
            "Best overall configuration is "
            f"`{best_overall.get('config_id')}` at "
            f"{fmt((best_overall.get('runner_payload') or {}).get('total_wall_ms'))} ms total wall time."
        )
    if best_fp32 is not None and best_fp16 is not None:
        fp32_wall = (best_fp32.get("runner_payload") or {}).get("total_wall_ms")
        fp16_wall = (best_fp16.get("runner_payload") or {}).get("total_wall_ms")
        if isinstance(fp32_wall, (int, float)) and isinstance(fp16_wall, (int, float)) and fp16_wall > 0:
            findings.append(
                "Best FP16 wall time is "
                f"{fmt(fp32_wall / fp16_wall, 3)}x relative to the best FP32 wall time."
            )
    if best_int8 is None:
        findings.append("INT8 is absent or not yet validated in this matrix.")
    if failed:
        findings.append(f"{len(failed)} configuration(s) failed and remain in the report for traceability.")
    if all(not (record.get("quality_summary") or {}) for record in records):
        findings.append("Quality metrics were not attached to this benchmark matrix.")
    return findings


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['title']}",
        "",
        f"- run_id: {report['run_id']}",
        f"- config_count: {report['config_count']}",
        f"- ok_count: {report['ok_count']}",
        f"- error_count: {report['error_count']}",
        "",
        "## Best Configurations",
        "",
        f"- overall: {report['best_overall']}",
        f"- fp32: {report['best_by_model'].get('fp32')}",
        f"- fp16: {report['best_by_model'].get('fp16')}",
        f"- int8: {report['best_by_model'].get('int8')}",
        "",
        "## Matrix",
        "",
        "| Config | Model | Precision | Interpreters | Threads | Shape | Auto | Total ms | Img/s | Mean item ms | PSNR | SSIM | LPIPS | Status |",
        "|---|---|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for record in report["records"]:
        runner = record.get("runner_payload") or {}
        quality = record.get("quality_summary") or {}
        lines.append(
            f"| {record.get('config_id')} | {record.get('model_variant')} | {record.get('precision')} | "
            f"{record.get('interpreter_count')} | {record.get('session_threads')} | {record.get('shape_mode')} | "
            f"{'yes' if record.get('auto_backend') else 'no'} | "
            f"{fmt(runner.get('total_wall_ms'))} | {fmt(runner.get('images_per_sec'), 6)} | "
            f"{fmt(((runner.get('sample_stats') or {}).get('total_ms') or {}).get('mean_ms'))} | "
            f"{fmt(quality.get('psnr_db'), 4)} | {fmt(quality.get('ssim'), 6)} | {fmt(quality.get('lpips'), 6)} | "
            f"{record.get('status')} |"
        )

    lines.extend(["", "## Findings", ""])
    for finding in report["findings"]:
        lines.append(f"- {finding}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    records = load_records(Path(args.results_jsonl))
    report = {
        "title": args.title,
        "run_id": args.run_id,
        "config_count": len(records),
        "ok_count": sum(1 for record in records if record.get("status") == "ok"),
        "error_count": sum(1 for record in records if record.get("status") != "ok"),
        "records": records,
        "best_overall": simplify_best(best_record(records)),
        "best_by_model": {
            "fp32": simplify_best(best_record(records, model_variant="fp32")),
            "fp16": simplify_best(best_record(records, model_variant="fp16")),
            "int8": simplify_best(best_record(records, model_variant="int8")),
        },
        "findings": build_findings(records),
    }
    report_json = Path(args.report_json)
    report_md = Path(args.report_md)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
