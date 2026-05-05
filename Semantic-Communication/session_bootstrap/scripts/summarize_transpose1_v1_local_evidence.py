#!/usr/bin/env python3
"""Summarize repo-local evidence for the transpose1 scheduled-form v1 line."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


OPERATOR_NAME = "fused_conv2d_transpose1_add9"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def repo_rel(path: Path, root: Path) -> str:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        return f"./{resolved_path.relative_to(resolved_root).as_posix()}"
    except ValueError:
        return str(resolved_path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def block_slice(text: str, block_name: str, next_block_names: list[str]) -> str:
    marker = f'with T.sblock("{block_name}")'
    start = text.find(marker)
    if start < 0:
        return ""
    end = len(text)
    for next_name in next_block_names:
        next_marker = f'with T.sblock("{next_name}")'
        next_pos = text.find(next_marker, start + len(marker))
        if next_pos >= 0:
            end = min(end, next_pos)
    return text[start:end]


def structural_change_checks(reference_tir: Path, working_copy_tir: Path) -> dict[str, bool]:
    reference_text = reference_tir.read_text(encoding="utf-8")
    working_text = working_copy_tir.read_text(encoding="utf-8")
    working_compute_init = block_slice(working_text, "compute_init", ["compute_update"])
    working_compute_update = block_slice(working_text, "compute_update", ["T_add"])
    reference_compute_init = block_slice(reference_text, "compute_init", ["compute_update"])
    reference_compute_update = block_slice(reference_text, "compute_update", ["T_add"])
    return {
        "reference_has_compute_intermediate": "compute_intermediate = T.alloc_buffer" in reference_text,
        "working_has_compute_intermediate": "compute_intermediate = T.alloc_buffer" in working_text,
        "reference_has_t_add": 'with T.sblock("T_add")' in reference_text,
        "working_has_t_add": 'with T.sblock("T_add")' in working_text,
        "reference_compute_init_zeroes_intermediate": "compute_intermediate" in reference_compute_init
        and "T.float32(0.0)" in reference_compute_init
        and "T.reads()" in reference_compute_init,
        "working_compute_init_reads_bias_into_output": "T.reads(lv320[" in working_compute_init
        and "T.writes(T_add_intermediate[" in working_compute_init,
        "reference_compute_update_accumulates_intermediate": "T.writes(compute_intermediate[" in reference_compute_update,
        "working_compute_update_accumulates_output": "T.writes(T_add_intermediate[" in working_compute_update,
        "reference_has_data_dilate": "data_dilate = T.alloc_buffer" in reference_text,
        "working_has_data_dilate": "data_dilate = T.alloc_buffer" in working_text,
        "reference_has_data_pad": "data_pad = T.alloc_buffer" in reference_text,
        "working_has_data_pad": "data_pad = T.alloc_buffer" in working_text,
        "reference_has_kernel_transform": "kernel_transform = T.alloc_buffer" in reference_text,
        "working_has_kernel_transform": "kernel_transform = T.alloc_buffer" in working_text,
    }


def render_status(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def format_sha(value: str) -> str:
    return value if len(value) <= 12 else f"{value[:12]}..."


def build_note(
    *,
    root: Path,
    working_copy_manifest: dict[str, Any],
    current_local_report: dict[str, Any],
    previous_local_report: dict[str, Any],
    scheduled_reference_report: dict[str, Any],
    prior_v0_runtime_report: dict[str, Any],
    checks: dict[str, bool],
    generated_at: str,
) -> str:
    current_build = current_local_report["local_build_output"]
    current_swap = current_local_report["post_db_scheduled_swap"]

    previous_build = previous_local_report["local_build_output"]
    previous_swap = previous_local_report["post_db_scheduled_swap"]
    previous_candidate = previous_local_report["handwritten_candidate"]

    scheduled_build = scheduled_reference_report["local_build"]
    scheduled_runtime = scheduled_reference_report["safe_runtime_inference"]["payload"]

    prior_v0_build = prior_v0_runtime_report["local_build"]
    prior_v0_runtime = prior_v0_runtime_report["safe_runtime_inference"]["payload"]

    size_delta_vs_reference = int(current_build["artifact_size_bytes"]) - int(
        scheduled_build["optimized_model_size_bytes"]
    )
    size_delta_vs_previous_local = int(current_build["artifact_size_bytes"]) - int(
        previous_build["artifact_size_bytes"]
    )

    reference_source = working_copy_manifest["source_reference_seed"]["reference_source"]
    current_edit_state = working_copy_manifest["current_edit_state"]

    worth_next_step = (
        current_swap.get("swap_succeeded") is True
        and current_swap.get("build_status") == "built"
        and current_build.get("export_status") == "exported"
        and current_swap.get("structural_equal_post_swap_vs_candidate") is True
    )
    recommendation = (
        "Proceed to stronger local compare"
        if worth_next_step
        else "Not worth it yet"
    )
    previous_local_size_line = (
        f"- Compared with that previous local post-db artifact, `v1` changed the exported `.so` "
        f"from `{format_sha(previous_build['artifact_sha256'])}` to "
        f"`{format_sha(current_build['artifact_sha256'])}` and reduced size by "
        f"`{abs(size_delta_vs_previous_local)}` bytes."
        if size_delta_vs_previous_local < 0
        else f"- Compared with that previous local post-db artifact, `v1` changed the exported `.so` "
        f"from `{format_sha(previous_build['artifact_sha256'])}` to "
        f"`{format_sha(current_build['artifact_sha256'])}` and increased size by "
        f"`{size_delta_vs_previous_local}` bytes."
    )

    structural_lines = [
        "- `v1` still uses the checked-in scheduled reference form as the base and keeps `data_dilate`, `data_pad`, and `kernel_transform` materialized."
        if checks["working_has_data_dilate"]
        and checks["working_has_data_pad"]
        and checks["working_has_kernel_transform"]
        else "- The working copy no longer matches the expected scheduled-form base; re-check the checked-in TIR files.",
        "- `compute_intermediate` is removed from `v1`, while it is present in the scheduled reference."
        if checks["reference_has_compute_intermediate"] and not checks["working_has_compute_intermediate"]
        else "- `compute_intermediate` removal was not confirmed from the checked-in TIR files.",
        "- The trailing `T_add` block is removed from `v1`, while it is present in the scheduled reference."
        if checks["reference_has_t_add"] and not checks["working_has_t_add"]
        else "- Removal of the trailing `T_add` block was not confirmed from the checked-in TIR files.",
        "- `compute_init` now seeds `T_add_intermediate` from bias `lv320` instead of zero-initializing `compute_intermediate`."
        if checks["reference_compute_init_zeroes_intermediate"]
        and checks["working_compute_init_reads_bias_into_output"]
        else "- The expected `compute_init` bias-folding change was not fully confirmed from the checked-in TIR files.",
        "- `compute_update` now accumulates directly into `T_add_intermediate`."
        if checks["reference_compute_update_accumulates_intermediate"]
        and checks["working_compute_update_accumulates_output"]
        else "- The expected `compute_update` output-accumulation change was not fully confirmed from the checked-in TIR files.",
    ]

    lines = [
        "# Transpose1 v1 Local Evidence Note",
        "",
        f"- generated_at: `{generated_at}`",
        f"- operator: `{OPERATOR_NAME}`",
        f"- scope: `scheduled-form v1 / local-only compare`",
        f"- recommendation: `{recommendation}`",
        "",
        "## What v1 changed structurally",
        "",
        *structural_lines,
        f"- Working-copy manifest states: `{current_edit_state['concrete_change']}`",
        "",
        "## Known local artifact/build facts",
        "",
        f"- Scheduled reference source stays anchored to `{reference_source['source_seam_id']}` with `post_db_operator_tir_is_scheduled={render_status(reference_source['post_db_operator_tir_is_scheduled'])}` and task summary `{reference_source['task_summary_json']}`.",
        f"- Current `v1` local post-db report: `swap_succeeded={render_status(current_swap['swap_succeeded'])}`, `build_status={current_swap['build_status']}`, `export_status={current_build['export_status']}`, `structural_equal_post_swap_vs_candidate={render_status(current_swap['structural_equal_post_swap_vs_candidate'])}`.",
        f"- Current `v1` local artifact: `sha256={current_build['artifact_sha256']}`, `size={current_build['artifact_size_bytes']}`, report `{repo_rel(Path(current_build['report_path']), root)}`.",
        f"- Previous local post-db evidence: candidate `{previous_candidate['metadata']['candidate_version']}`, `swap_succeeded={render_status(previous_swap['swap_succeeded'])}`, `build_status={previous_swap['build_status']}`, `export_status={previous_build['export_status']}`, `structural_equal_post_swap_vs_candidate={render_status(previous_swap['structural_equal_post_swap_vs_candidate'])}`, artifact `sha256={previous_build['artifact_sha256']}`, `size={previous_build['artifact_size_bytes']}`.",
        previous_local_size_line,
        f"- Scheduled reference staged artifact in repo remains `sha256={scheduled_build['optimized_model_sha256']}`, `size={scheduled_build['optimized_model_size_bytes']}`, `run_median_ms={scheduled_runtime['run_median_ms']}` from `{repo_rel(root / 'session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.json', root)}`.",
        f"- Relative to that staged reference artifact, the current `v1` local artifact differs in SHA and is `{size_delta_vs_reference:+d}` bytes in size.",
        f"- Prior handwritten `v0` runtime evidence in repo remains `sha256={prior_v0_build['optimized_model_sha256']}`, `size={prior_v0_build['optimized_model_size_bytes']}`, `run_median_ms={prior_v0_runtime['run_median_ms']}`, but that report is still marked non-comparable because it came from the older raw pre-compile seam.",
        "",
        "## Still unknown",
        "",
        "- No local runtime number exists yet for `v1` on the post-db schedule-preserving seam.",
        "- No correctness or numerical-equality check against the scheduled reference artifact is recorded here.",
        "- No remote/staging-safe validation exists yet for this `v1` line.",
        "- Artifact SHA/size movement alone does not justify any performance claim.",
        "",
        "## Recommendation",
        "",
    ]

    if worth_next_step:
        lines.extend(
            [
                "- `v1` is worth the next stronger validation step because the structural delta is narrow, the post-db scheduled swap stayed mechanical (`true`), and the local build/export completed cleanly on the same scheduled reference inputs/DB.",
                "- The next step should still be `stronger local compare`, not a performance claim: add a local correctness/behavior compare first, then decide whether staging-safe validation is justified.",
            ]
        )
    else:
        lines.extend(
            [
                "- `v1` is not worth a stronger validation step yet because the current local evidence does not show a clean post-db scheduled swap/build/export outcome.",
            ]
        )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    root = repo_root()
    today = date.today().strftime("%Y%m%d")
    parser = argparse.ArgumentParser(
        description="Summarize repo-local evidence for the transpose1 scheduled-form v1 line."
    )
    parser.add_argument(
        "--reference-manifest",
        default=str(
            root
            / "session_bootstrap/handwritten/fused_conv2d_transpose1_add9/post_db_scheduled_reference_seed_manifest.json"
        ),
        help="Checked-in scheduled reference manifest.",
    )
    parser.add_argument(
        "--working-copy-manifest",
        default=str(
            root
            / "session_bootstrap/handwritten/fused_conv2d_transpose1_add9/scheduled_form_candidate_v1_working_copy_manifest.json"
        ),
        help="Checked-in scheduled-form v1 working-copy manifest.",
    )
    parser.add_argument(
        "--reference-tir",
        default=str(
            root
            / "session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_post_db_scheduled_reference_seed_tir.py"
        ),
        help="Checked-in scheduled reference TIR.",
    )
    parser.add_argument(
        "--working-copy-tir",
        default=str(
            root
            / "session_bootstrap/handwritten/fused_conv2d_transpose1_add9/fused_conv2d_transpose1_add9_scheduled_form_candidate_v1_working_copy_tir.py"
        ),
        help="Checked-in scheduled-form v1 working-copy TIR.",
    )
    parser.add_argument(
        "--current-local-report",
        default=str(
            root
            / "session_bootstrap/tmp/transpose1_post_db_swap_local_build_v1/fused_conv2d_transpose1_add9_post_db_swap_report.json"
        ),
        help="Current v1 local post-db swap report.",
    )
    parser.add_argument(
        "--previous-local-report",
        default=str(
            root
            / "session_bootstrap/tmp/transpose1_post_db_swap_local_build/fused_conv2d_transpose1_add9_post_db_swap_report.json"
        ),
        help="Previous local post-db swap report.",
    )
    parser.add_argument(
        "--scheduled-reference-report",
        default=str(
            root
            / "session_bootstrap/reports/phytium_runtime_joint_top6_targeted_staging_search_20260330_2315.json"
        ),
        help="Scheduled reference staged report.",
    )
    parser.add_argument(
        "--prior-v0-runtime-report",
        default=str(
            root
            / "session_bootstrap/reports/phytium_handwritten_fused_conv2d_transpose1_add9_20260331_044114.json"
        ),
        help="Prior handwritten v0 runtime report.",
    )
    parser.add_argument(
        "--output-path",
        default=str(root / f"session_bootstrap/reports/transpose1_v1_local_evidence_{today}.md"),
        help="Markdown note output path.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Optional fixed timestamp string to embed in the note.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()

    reference_manifest_path = Path(args.reference_manifest).resolve()
    working_copy_manifest_path = Path(args.working_copy_manifest).resolve()
    reference_tir_path = Path(args.reference_tir).resolve()
    working_copy_tir_path = Path(args.working_copy_tir).resolve()
    current_local_report_path = Path(args.current_local_report).resolve()
    previous_local_report_path = Path(args.previous_local_report).resolve()
    scheduled_reference_report_path = Path(args.scheduled_reference_report).resolve()
    prior_v0_runtime_report_path = Path(args.prior_v0_runtime_report).resolve()
    output_path = Path(args.output_path).resolve()

    for required in (
        reference_manifest_path,
        working_copy_manifest_path,
        reference_tir_path,
        working_copy_tir_path,
        current_local_report_path,
        previous_local_report_path,
        scheduled_reference_report_path,
        prior_v0_runtime_report_path,
    ):
        if not required.is_file():
            raise FileNotFoundError(f"required file not found: {required}")

    working_copy_manifest = load_json(working_copy_manifest_path)
    current_local_report = load_json(current_local_report_path)
    previous_local_report = load_json(previous_local_report_path)
    scheduled_reference_report = load_json(scheduled_reference_report_path)
    prior_v0_runtime_report = load_json(prior_v0_runtime_report_path)
    checks = structural_change_checks(reference_tir_path, working_copy_tir_path)

    generated_at = args.generated_at or datetime.now().astimezone().isoformat(
        timespec="seconds"
    )
    note = build_note(
        root=root,
        working_copy_manifest=working_copy_manifest,
        current_local_report=current_local_report,
        previous_local_report=previous_local_report,
        scheduled_reference_report=scheduled_reference_report,
        prior_v0_runtime_report=prior_v0_runtime_report,
        checks=checks,
        generated_at=generated_at,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(note, encoding="utf-8")
    print(repo_rel(output_path, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
