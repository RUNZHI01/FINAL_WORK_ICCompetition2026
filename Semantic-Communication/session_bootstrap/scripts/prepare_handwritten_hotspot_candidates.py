#!/usr/bin/env python3
"""Prepare a minimal handwritten hotspot/TIR/NEON candidate pack.

This script turns the existing runtime profiling evidence into a small manual
work queue so the next optimization step can stay repo-native and staging-safe.
It does not launch tuning or mutate any trusted artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CURRENT_PROFILE_JSON = (
    "session_bootstrap/reports/"
    "profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010.json"
)
DEFAULT_REFERENCE_PROFILE_JSON = (
    "session_bootstrap/reports/"
    "profiling_runtime_joint_top5_staging_artifact_reprobe_fixed_20260330_2305.json"
)
DEFAULT_BEST_CANDIDATE_MD = (
    "session_bootstrap/reports/current_best_staging_candidate_20260331.md"
)
DEFAULT_OUTPUT_MD = "session_bootstrap/reports/handwritten_hotspot_candidates_20260331.md"
DEFAULT_OUTPUT_JSON = "session_bootstrap/reports/handwritten_hotspot_candidates_20260331.json"
DEFAULT_STAGING_ARCHIVE = "/home/user/Downloads/jscc-test/jscc_staging_handwritten"
REPORT_ROW_RE = re.compile(
    r"^(?P<name>.+?)\s{2,}"
    r"(?P<duration>[\d,]+\.\d+)\s+"
    r"(?P<percent>[\d.]+)\s+"
    r"(?P<device>\S+)\s+"
    r"(?P<count>\d+)\s+"
    r"(?P<shapes>.*)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a handwritten hotspot candidate pack from staged runtime profiling evidence."
        )
    )
    parser.add_argument(
        "--current-profile-json",
        default=DEFAULT_CURRENT_PROFILE_JSON,
        help="Current best staging runtime profiling summary JSON.",
    )
    parser.add_argument(
        "--reference-profile-json",
        default=DEFAULT_REFERENCE_PROFILE_JSON,
        help="Earlier staging runtime profiling summary JSON used for movement comparison.",
    )
    parser.add_argument(
        "--best-candidate-md",
        default=DEFAULT_BEST_CANDIDATE_MD,
        help="Freeze record or summary markdown for the best staging candidate.",
    )
    parser.add_argument(
        "--output-md",
        default=DEFAULT_OUTPUT_MD,
        help="Output markdown path.",
    )
    parser.add_argument(
        "--output-json",
        default=DEFAULT_OUTPUT_JSON,
        help="Output JSON path.",
    )
    parser.add_argument(
        "--primary-count",
        type=int,
        default=4,
        help="How many wave-1 conv/deconv candidates to keep.",
    )
    parser.add_argument(
        "--secondary-count",
        type=int,
        default=4,
        help="How many wave-2 norm/reduction candidates to keep.",
    )
    parser.add_argument(
        "--monitor-min-percent",
        type=float,
        default=5.0,
        help="Raw percent threshold for monitor-only carryover candidates.",
    )
    parser.add_argument(
        "--staging-archive-dir",
        default=DEFAULT_STAGING_ARCHIVE,
        help="Recommended staging archive for handwritten experiments.",
    )
    args = parser.parse_args()
    if args.primary_count <= 0:
        raise SystemExit(f"--primary-count must be > 0 (got {args.primary_count})")
    if args.secondary_count <= 0:
        raise SystemExit(f"--secondary-count must be > 0 (got {args.secondary_count})")
    if args.monitor_min_percent < 0:
        raise SystemExit(
            f"--monitor-min-percent must be >= 0 (got {args.monitor_min_percent})"
        )
    return args


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"JSON file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def scalar(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return None


def candidate_family(name: str) -> str:
    lower = name.lower()
    if "conv2d_transpose" in lower:
        return "deconv"
    if "conv2d" in lower:
        return "conv"
    if any(
        token in lower
        for token in ("variance", "mean", "layernorm", "norm", "sqrt", "divide", "multiply")
    ):
        return "norm_stats"
    if "reshape" in lower or "mirror_pad" in lower or "pad" in lower:
        return "layout"
    return "other"


def manual_direction(name: str) -> str:
    family = candidate_family(name)
    if family == "deconv":
        return "Wave 1: handwritten TIR plus NEON for spatial tile and vector store."
    if family == "conv":
        return "Wave 1: handwritten TIR plus NEON for kernel tile and epilogue."
    if family == "norm_stats":
        return "Wave 2: handwritten TIR for reduction, vector math, and fused epilogue."
    return "Monitor only."


def parse_aggregated_report_rows(report_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    in_table = False
    for raw_line in report_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if line.startswith("Name "):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("----------") or line.startswith("Configuration"):
            break
        match = REPORT_ROW_RE.match(line)
        if not match:
            continue
        name = match.group("name").strip()
        if name in {"Sum", "Total"} or name.startswith("vm.builtin."):
            continue
        rows.append(
            {
                "name": name,
                "family": candidate_family(name),
                "mean_duration_us": float(match.group("duration").replace(",", "")),
                "mean_percent": float(match.group("percent")),
                "count": int(match.group("count")),
                "device": match.group("device"),
                "argument_shapes": match.group("shapes").strip(),
            }
        )
    rows.sort(key=lambda row: (-row["mean_duration_us"], row["name"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def load_profile_summary(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    runtime_phase = payload.get("runtime_phase") or {}
    summary = runtime_phase.get("summary") or {}
    runtime_profiling = summary.get("runtime_profiling") or {}
    curated = []
    for rank, row in enumerate(runtime_profiling.get("top_ops") or [], start=1):
        name = str(row.get("name") or "")
        if not name:
            continue
        curated.append(
            {
                "rank": rank,
                "name": name,
                "family": candidate_family(name),
                "mean_duration_us": float(row.get("mean_duration_us") or 0.0),
                "mean_percent": float(row.get("mean_percent") or 0.0),
                "samples": row.get("samples"),
                "devices": list(row.get("devices") or []),
            }
        )

    sample_results = runtime_profiling.get("sample_results") or []
    report_text = sample_results[0].get("report_text") if sample_results else ""
    raw_rows = parse_aggregated_report_rows(report_text or "")

    return {
        "path": str(path),
        "payload": payload,
        "run_id": payload.get("run_id"),
        "profile_summary_md": payload.get("summary_md"),
        "trusted_env": runtime_phase.get("trusted_env"),
        "command_log": runtime_phase.get("command_log"),
        "artifact_sha256": summary.get("artifact_sha256"),
        "artifact_path": summary.get("artifact_path"),
        "reprobe_run_median_ms": summary.get("run_median_ms"),
        "reprobe_run_mean_ms": summary.get("run_mean_ms"),
        "target": runtime_phase.get("target"),
        "curated_top_ops": curated,
        "curated_by_name": {row["name"]: row for row in curated},
        "raw_ops": raw_rows,
        "raw_by_name": {row["name"]: row for row in raw_rows},
    }


def format_optional_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def comparison_fields(
    name: str,
    current: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    current_row = current["raw_by_name"].get(name)
    reference_row = reference["raw_by_name"].get(name)
    current_curated = current["curated_by_name"].get(name)
    reference_curated = reference["curated_by_name"].get(name)
    return {
        "current_raw_rank": current_row.get("rank") if current_row else None,
        "current_mean_duration_us": current_row.get("mean_duration_us") if current_row else None,
        "current_mean_percent": current_row.get("mean_percent") if current_row else None,
        "current_count": current_row.get("count") if current_row else None,
        "current_argument_shapes": current_row.get("argument_shapes") if current_row else "",
        "current_curated_rank": current_curated.get("rank") if current_curated else None,
        "reference_raw_rank": reference_row.get("rank") if reference_row else None,
        "reference_mean_duration_us": reference_row.get("mean_duration_us") if reference_row else None,
        "reference_mean_percent": reference_row.get("mean_percent") if reference_row else None,
        "reference_curated_rank": reference_curated.get("rank") if reference_curated else None,
        "delta_percent_vs_reference": (
            None
            if current_row is None or reference_row is None
            else current_row["mean_percent"] - reference_row["mean_percent"]
        ),
    }


def wave_reason(
    name: str,
    family: str,
    current: dict[str, Any],
    reference: dict[str, Any],
    mode: str,
) -> str:
    fields = comparison_fields(name, current, reference)
    current_pct = fields["current_mean_percent"]
    reference_pct = fields["reference_mean_percent"]
    current_us = fields["current_mean_duration_us"]
    if mode == "wave1":
        base = (
            f"Still a top compute kernel in the best staging candidate "
            f"({format_optional_float(current_us)} us, {format_optional_float(current_pct)}%)."
        )
        if reference_pct is not None:
            base += (
                f" Joint-top5 reference was {format_optional_float(reference_pct)}%, "
                "so this kernel survived multiple targeted rounds."
            )
        return base + " Manual NEON/TIR is the next conservative lever."

    base = (
        f"Now visible after the joint-top6 conv/deconv protection set "
        f"({format_optional_float(current_us)} us, {format_optional_float(current_pct)}%)."
    )
    if reference_pct is not None:
        base += (
            f" Joint-top5 reference was {format_optional_float(reference_pct)}%, "
            "so this is a real residual rather than a one-off spike."
        )
    if family == "norm_stats":
        base += " This is a reduction/vector epilogue candidate for handwritten TIR."
    return base


def monitor_reason(name: str, current: dict[str, Any], reference: dict[str, Any]) -> str:
    fields = comparison_fields(name, current, reference)
    current_pct = fields["current_mean_percent"]
    reference_pct = fields["reference_mean_percent"]
    if name == "fused_conv2d_add2" and reference_pct is not None and current_pct is not None:
        return (
            f"Triggered the jump from joint-top5 to joint-top6 "
            f"({format_optional_float(reference_pct)}% -> {format_optional_float(current_pct)}%). "
            "Keep it as a control, not the first handwritten kernel."
        )
    if name == "fused_conv2d2_add2":
        return (
            "Still visible in raw aggregated calls, but the diagnosis no longer promotes it as a "
            "curated top hotspot. Reconfirm with a focused reprobe before manual TIR."
        )
    return (
        "Visible in raw aggregated calls but not promoted into the diagnosis shortlist. "
        "Use a focused reprobe or micro-benchmark before spending handwritten effort here."
    )


def build_candidates(args: argparse.Namespace) -> dict[str, Any]:
    current_profile_path = resolve_path(args.current_profile_json)
    reference_profile_path = resolve_path(args.reference_profile_json)
    best_candidate_md_path = resolve_path(args.best_candidate_md)
    current = load_profile_summary(current_profile_path)
    reference = load_profile_summary(reference_profile_path)

    primary = []
    secondary = []
    for row in current["curated_top_ops"]:
        family = row["family"]
        if family in {"deconv", "conv"} and len(primary) < args.primary_count:
            fields = comparison_fields(row["name"], current, reference)
            primary.append(
                {
                    "priority": len(primary) + 1,
                    "name": row["name"],
                    "family": family,
                    "manual_direction": manual_direction(row["name"]),
                    "reason": wave_reason(row["name"], family, current, reference, "wave1"),
                    **fields,
                }
            )
        elif family == "norm_stats" and len(secondary) < args.secondary_count:
            fields = comparison_fields(row["name"], current, reference)
            secondary.append(
                {
                    "priority": len(secondary) + 1,
                    "name": row["name"],
                    "family": family,
                    "manual_direction": manual_direction(row["name"]),
                    "reason": wave_reason(row["name"], family, current, reference, "wave2"),
                    **fields,
                }
            )

    chosen_names = {row["name"] for row in primary + secondary}
    monitor = []
    for row in current["raw_ops"]:
        if row["name"] in chosen_names:
            continue
        reference_row = reference["raw_by_name"].get(row["name"])
        if row["family"] not in {"conv", "norm_stats"}:
            continue
        if row["mean_percent"] < args.monitor_min_percent and (
            reference_row is None or reference_row["mean_percent"] < args.monitor_min_percent
        ):
            continue
        fields = comparison_fields(row["name"], current, reference)
        monitor.append(
            {
                "name": row["name"],
                "family": row["family"],
                "manual_direction": "Monitor only.",
                "reason": monitor_reason(row["name"], current, reference),
                **fields,
            }
        )

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "current_profile_json": str(current_profile_path),
        "reference_profile_json": str(reference_profile_path),
        "best_candidate_freeze_md": str(best_candidate_md_path),
        "current_best_staging": {
            "run_id": current["run_id"],
            "summary_md": current["profile_summary_md"],
            "artifact_sha256": current["artifact_sha256"],
            "artifact_path": current["artifact_path"],
            "reprobe_run_median_ms": current["reprobe_run_median_ms"],
            "reprobe_run_mean_ms": current["reprobe_run_mean_ms"],
            "target": current["target"],
            "trusted_env": current["trusted_env"],
            "command_log": current["command_log"],
        },
        "reference_staging": {
            "run_id": reference["run_id"],
            "summary_md": reference["profile_summary_md"],
            "artifact_sha256": reference["artifact_sha256"],
            "artifact_path": reference["artifact_path"],
            "reprobe_run_median_ms": reference["reprobe_run_median_ms"],
            "reprobe_run_mean_ms": reference["reprobe_run_mean_ms"],
            "target": reference["target"],
            "trusted_env": reference["trusted_env"],
            "command_log": reference["command_log"],
        },
        "current_curated_top_ops": current["curated_top_ops"],
        "wave1_candidates": primary,
        "wave2_candidates": secondary,
        "monitor_only_candidates": monitor,
        "suggested_staging_archive": args.staging_archive_dir,
        "guardrails": [
            "Do not overwrite the trusted current archive.",
            "Use the current best staging candidate as the fixed comparison point.",
            "Work one handwritten kernel at a time and re-profile after each candidate.",
            "If a candidate creates a new dominant hotspot or regresses payload, keep it in staging only.",
        ],
    }


def bullet_list(lines: list[str], items: list[str]) -> None:
    for item in items:
        lines.append(f"- {item}")


def write_candidate_section(lines: list[str], title: str, rows: list[dict[str, Any]]) -> None:
    lines.append(f"## {title}")
    lines.append("")
    if not rows:
        lines.append("- none")
        lines.append("")
        return

    lines.append("| priority | name | family | current us | current % | reference % | current raw rank | shapes |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("priority", "-")),
                    row["name"],
                    row["family"],
                    format_optional_float(row.get("current_mean_duration_us")),
                    format_optional_float(row.get("current_mean_percent")),
                    format_optional_float(row.get("reference_mean_percent")),
                    str(row.get("current_raw_rank") or "n/a"),
                    row.get("current_argument_shapes") or "n/a",
                ]
            )
            + " |"
        )
    lines.append("")
    for row in rows:
        priority = row.get("priority")
        prefix = f"{priority}. " if priority is not None else "- "
        lines.append(
            f"{prefix}`{row['name']}`: {row['reason']} {row['manual_direction']}"
        )
    lines.append("")


def write_monitor_section(lines: list[str], rows: list[dict[str, Any]]) -> None:
    lines.append("## Monitor Only")
    lines.append("")
    if not rows:
        lines.append("- none")
        lines.append("")
        return

    lines.append("| name | family | current % | reference % | current raw rank |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["name"],
                    row["family"],
                    format_optional_float(row.get("current_mean_percent")),
                    format_optional_float(row.get("reference_mean_percent")),
                    str(row.get("current_raw_rank") or "n/a"),
                ]
            )
            + " |"
        )
    lines.append("")
    for row in rows:
        lines.append(f"- `{row['name']}`: {row['reason']}")
    lines.append("")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = [
        "# Handwritten Hotspot Candidates",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- current_profile_json: {payload['current_profile_json']}",
        f"- reference_profile_json: {payload['reference_profile_json']}",
        f"- best_candidate_freeze_md: {payload['best_candidate_freeze_md']}",
        f"- current_best_staging_artifact_sha256: {payload['current_best_staging']['artifact_sha256']}",
        f"- current_best_staging_reprobe_median_ms: {payload['current_best_staging']['reprobe_run_median_ms']}",
        f"- reference_staging_reprobe_median_ms: {payload['reference_staging']['reprobe_run_median_ms']}",
        f"- suggested_staging_archive: {payload['suggested_staging_archive']}",
        "",
        "## Current Curated Runtime Top Ops",
        "",
        "| rank | name | family | duration us | percent |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in payload["current_curated_top_ops"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["rank"]),
                    row["name"],
                    row["family"],
                    format_optional_float(row.get("mean_duration_us")),
                    format_optional_float(row.get("mean_percent")),
                ]
            )
            + " |"
        )
    lines.append("")

    write_candidate_section(lines, "Wave 1: Conv and Deconv", payload["wave1_candidates"])
    write_candidate_section(lines, "Wave 2: Norm and Reduction", payload["wave2_candidates"])
    write_monitor_section(lines, payload["monitor_only_candidates"])

    lines.extend(
        [
            "## Guardrails",
            "",
        ]
    )
    bullet_list(lines, list(payload["guardrails"]))
    lines.append("")

    lines.extend(
        [
            "## Suggested Commands",
            "",
            "```bash",
            "python3 ./session_bootstrap/scripts/prepare_handwritten_hotspot_candidates.py",
            "```",
            "",
            "```bash",
            "bash ./session_bootstrap/scripts/run_phytium_runtime_joint_top6_refine_staging_search.sh",
            "```",
            "",
            "```bash",
            "bash ./session_bootstrap/scripts/run_phytium_current_safe_staging_validate.sh \\",
            "  --rebuild-env <manual_overlay.env> \\",
            f"  --remote-archive-dir {payload['suggested_staging_archive']} \\",
            "  --report-id phytium_handwritten_<op>_$(date +%Y%m%d_%H%M%S)",
            "```",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_md = resolve_path(args.output_md)
    output_json = resolve_path(args.output_json)
    payload = build_candidates(args)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_markdown(output_md, payload)

    print(f"output_json={output_json}")
    print(f"output_md={output_md}")
    print(
        "wave1="
        + ",".join(row["name"] for row in payload["wave1_candidates"])
    )
    print(
        "wave2="
        + ",".join(row["name"] for row in payload["wave2_candidates"])
    )
    print(
        "monitor_only="
        + ",".join(row["name"] for row in payload["monitor_only_candidates"])
    )


if __name__ == "__main__":
    main()
