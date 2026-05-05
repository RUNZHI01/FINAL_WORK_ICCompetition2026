#!/usr/bin/env python3
"""Refresh the checked-in editable seed for fused_conv2d_transpose1_add9.

This helper stays narrow on purpose:
- read the existing local-only seed capture under session_bootstrap/tmp
- keep a checked-in manifest derived from the captured seed JSON
- extract the real operator TIR from the local MetaSchedule task log
- avoid changing rebuild hooks or trusted-current paths
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPERATOR_NAME = "fused_conv2d_transpose1_add9"
DEFAULT_SEED_JSON = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "tmp"
    / "handwritten_fused_conv2d_transpose1_add9_scaffold"
    / f"{OPERATOR_NAME}_manual_seed.json"
)
DEFAULT_SEED_TIR = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "tmp"
    / "handwritten_fused_conv2d_transpose1_add9_scaffold"
    / f"{OPERATOR_NAME}_manual_seed_tir.py"
)
DEFAULT_TASK_LOG = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "tmp"
    / "handwritten_fused_conv2d_transpose1_add9_seed_capture"
    / "tuning_logs"
    / "logs"
    / "tvm.s_tir.meta_schedule.logging.task_0_fused_conv2d_transpose1_add9.log"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "session_bootstrap" / "handwritten" / "fused_conv2d_transpose1_add9"
)
MANUAL_CANDIDATE_FILENAME = f"{OPERATOR_NAME}_manual_candidate.py"
EDITABLE_TIR_FILENAME = f"{OPERATOR_NAME}_editable_seed_tir.py"
POST_DB_SCHEDULED_REFERENCE_SEED_TIR_FILENAME = (
    f"{OPERATOR_NAME}_post_db_scheduled_reference_seed_tir.py"
)
MANIFEST_FILENAME = "seed_manifest.json"
POST_DB_SCHEDULED_REFERENCE_SEED_MANIFEST_FILENAME = (
    "post_db_scheduled_reference_seed_manifest.json"
)
SCHEDULED_FORM_WORKING_COPY_TIR_FILENAME = (
    f"{OPERATOR_NAME}_scheduled_form_candidate_v1_working_copy_tir.py"
)
SCHEDULED_FORM_WORKING_COPY_MANIFEST_FILENAME = (
    "scheduled_form_candidate_v1_working_copy_manifest.json"
)
README_FILENAME = "README.md"
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} ")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the checked-in editable seed package for "
            f"{OPERATOR_NAME} from the latest local seed capture."
        )
    )
    parser.add_argument(
        "--seed-json",
        type=Path,
        default=DEFAULT_SEED_JSON,
        help="Captured manual seed JSON emitted by the local-only seed hook.",
    )
    parser.add_argument(
        "--seed-tir",
        type=Path,
        default=DEFAULT_SEED_TIR,
        help="Captured pre-compile seed snapshot emitted by the local-only seed hook.",
    )
    parser.add_argument(
        "--task-log",
        type=Path,
        default=DEFAULT_TASK_LOG,
        help="MetaSchedule task log containing the operator TIR for this workload.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Repo-native directory that will hold the checked-in editable seed package.",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow overwriting existing checked-in seed package files.",
    )
    return parser.parse_args(argv)


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def as_abs(path: Path) -> Path:
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def repo_native(path: Path | str) -> str:
    value = Path(path)
    resolved = value if value.is_absolute() else (PROJECT_ROOT / value).resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return str(resolved)
    return f"./{relative.as_posix()}"


def ensure_clean_outputs(paths: list[Path], allow_overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not allow_overwrite:
        joined = "\n  ".join(str(path) for path in existing)
        raise SystemExit(
            "ERROR: output already exists. Re-run with --allow-overwrite to refresh.\n"
            f"  {joined}"
        )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_seed_json(seed_json_path: Path) -> dict[str, Any]:
    payload = json.loads(seed_json_path.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise SystemExit(
            f"ERROR: expected seed operator {OPERATOR_NAME!r}, got {operator!r}"
        )
    return payload


def extract_initial_tir(task_log_path: Path) -> str:
    lines = task_log_path.read_text(encoding="utf-8").splitlines()
    marker = f'Initializing Task #0: "{OPERATOR_NAME}"'
    try:
        marker_index = next(i for i, line in enumerate(lines) if marker in line)
    except StopIteration as err:
        raise SystemExit(
            f"ERROR: could not find task marker for {OPERATOR_NAME} in {task_log_path}"
        ) from err

    start = None
    for index in range(marker_index + 1, len(lines)):
        if lines[index].startswith("# from tvm.script import ir as I"):
            start = index
            break
    if start is None:
        raise SystemExit(
            f"ERROR: could not find initial TIR script block in {task_log_path}"
        )

    collected: list[str] = []
    for index in range(start, len(lines)):
        line = lines[index]
        if index > start and TIMESTAMP_RE.match(line):
            break
        collected.append(line)

    tir_text = "\n".join(collected).strip()
    if not tir_text:
        raise SystemExit(f"ERROR: extracted empty TIR block from {task_log_path}")
    return tir_text + "\n"


def build_manifest(
    *,
    seed_payload: dict[str, Any],
    seed_json_path: Path,
    seed_tir_path: Path,
    task_log_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "operator": OPERATOR_NAME,
        "reference_staging_sha256": seed_payload.get("reference_staging_sha256"),
        "reference_profile_json": seed_payload.get("reference_profile_json"),
        "argument_shapes": seed_payload.get("argument_shapes"),
        "phase": seed_payload.get("phase"),
        "task_row": seed_payload.get("task_row"),
        "prim_func_capture": seed_payload.get("prim_func_capture"),
        "seed_capture_kind": seed_payload.get("seed_capture_kind"),
        "checked_in_hook_target": repo_native(
            output_dir / MANUAL_CANDIDATE_FILENAME
        ),
        "checked_in_edit_target": repo_native(output_dir / EDITABLE_TIR_FILENAME),
        "source_files": {
            "captured_seed_json": repo_native(seed_json_path),
            "captured_seed_tir": repo_native(seed_tir_path),
            "captured_task_log": repo_native(task_log_path),
        },
        "notes": [
            "The pre-compile seed snapshot captured the Relax callsite under `main`.",
            "The editable TIR in this directory is extracted from the local MetaSchedule task log for the selected operator workload.",
            "The checked-in manual candidate module exposes the local/staging handwritten override descriptor for candidate v0.",
        ],
    }


def render_editable_tir(
    *,
    seed_json_path: Path,
    seed_tir_path: Path,
    task_log_path: Path,
    extracted_tir: str,
) -> str:
    normalized_tir = extracted_tir.replace(
        "# from tvm.script import ir as I\n# from tvm.script import tir as T\n",
        "from tvm.script import ir as I\nfrom tvm.script import tir as T\n",
        1,
    )
    header = [
        f"# Checked-in editable seed for {OPERATOR_NAME}.",
        "#",
        "# Source inputs:",
        f"# - captured seed json: {repo_native(seed_json_path)}",
        f"# - captured pre-compile seed snapshot: {repo_native(seed_tir_path)}",
        f"# - extracted operator task log: {repo_native(task_log_path)}",
        "#",
        "# Notes:",
        "# - the captured pre-compile seed snapshot only recorded the full Relax callsite",
        "# - this file preserves the actual operator TIR printed by the local MetaSchedule task log",
        "# - edit here when shaping the first handwritten candidate",
        "",
    ]
    return "\n".join(header) + normalized_tir


def render_readme(
    *,
    seed_json_path: Path,
    seed_tir_path: Path,
    task_log_path: Path,
    output_dir: Path,
) -> str:
    manual_candidate_path = repo_native(output_dir / MANUAL_CANDIDATE_FILENAME)
    editable_tir_path = repo_native(output_dir / EDITABLE_TIR_FILENAME)
    scheduled_reference_seed_tir_path = repo_native(
        output_dir / POST_DB_SCHEDULED_REFERENCE_SEED_TIR_FILENAME
    )
    scheduled_reference_seed_manifest_path = repo_native(
        output_dir / POST_DB_SCHEDULED_REFERENCE_SEED_MANIFEST_FILENAME
    )
    scheduled_form_working_copy_tir_path = repo_native(
        output_dir / SCHEDULED_FORM_WORKING_COPY_TIR_FILENAME
    )
    scheduled_form_working_copy_manifest_path = repo_native(
        output_dir / SCHEDULED_FORM_WORKING_COPY_MANIFEST_FILENAME
    )
    return "\n".join(
        [
            f"# Checked-in seed: `{OPERATOR_NAME}`",
            "",
            "This directory is the first repo-native handoff after the local-only",
            "manual seed capture. It keeps the operator-specific editing surface in",
            "the repo without touching trusted current or launching any remote work.",
            "",
            "## Files",
            "",
            f"- `{MANUAL_CANDIDATE_FILENAME}`: repo-native handwritten-hook entrypoint for this operator; it exposes the checked-in candidate v0 through the local/staging pre-compile override contract.",
            f"- `{EDITABLE_TIR_FILENAME}`: editable operator TIR extracted from the local MetaSchedule task log.",
            f"- `{POST_DB_SCHEDULED_REFERENCE_SEED_TIR_FILENAME}`: schedule-preserving reference/edit seed recovered from the post-db full-module path.",
            f"- `{SCHEDULED_FORM_WORKING_COPY_TIR_FILENAME}`: editable scheduled-form v1 working copy cloned from the checked-in post-db scheduled reference seed.",
            f"- `{MANIFEST_FILENAME}`: trimmed seed context copied from the captured seed JSON.",
            f"- `{POST_DB_SCHEDULED_REFERENCE_SEED_MANIFEST_FILENAME}`: small manifest for the scheduled-form reference/edit seed.",
            f"- `{SCHEDULED_FORM_WORKING_COPY_MANIFEST_FILENAME}`: small manifest for the editable scheduled-form v1 working copy.",
            f"- `{README_FILENAME}`: short editing runbook.",
            "",
            "## Why this exists",
            "",
            f"- the captured pre-compile seed JSON at `{repo_native(seed_json_path)}` is real, but its paired seed snapshot only shows the Relax callsite under `main`",
            f"- the local task log at `{repo_native(task_log_path)}` contains the actual `fused_conv2d_transpose1_add9` TIR workload",
            "- this package checks that workload into the repo so the first manual edits are not trapped under `tmp/`",
            "",
            "## Refresh from the latest local capture",
            "",
            "```bash",
            "python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_checked_in_seed.py",
            "```",
            "",
            "The helper reads:",
            f"- `{repo_native(seed_json_path)}`",
            f"- `{repo_native(seed_tir_path)}`",
            f"- `{repo_native(task_log_path)}`",
            "",
            "It refuses to overwrite this directory unless `--allow-overwrite` is passed.",
            "",
            "## Refresh the scheduled-form reference seed",
            "",
            "When the next operator-side iteration needs a schedule-preserving starting",
            "point, refresh the checked-in post-db scheduled reference seed instead of the",
            "older raw pre-compile seed:",
            "",
            "```bash",
            "python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_post_db_scheduled_seed.py \\",
            "  --allow-overwrite",
            "```",
            "",
            "The helper reuses the local post-db schedule-preserving seam and writes:",
            f"- `{scheduled_reference_seed_tir_path}`",
            f"- `{scheduled_reference_seed_manifest_path}`",
            "",
            "This handoff is still local-only and diagnostic-only. It gives a more honest",
            "reference/edit seed for the next handwritten pass, but it does not by itself",
            "justify runtime or performance claims.",
            "",
            "## Refresh the scheduled-form v1 working copy",
            "",
            "Once the checked-in scheduled reference seed is current, derive the editable",
            "scheduled-form v1 working copy from it with this narrow local-only helper:",
            "",
            "```bash",
            "python3 ./session_bootstrap/scripts/refresh_fused_conv2d_transpose1_add9_scheduled_form_working_copy.py \\",
            "  --allow-overwrite",
            "```",
            "",
            "The helper reads the checked-in scheduled reference seed and writes:",
            f"- `{scheduled_form_working_copy_tir_path}`",
            f"- `{scheduled_form_working_copy_manifest_path}`",
            "",
            "Keep the scheduled reference seed frozen for backtracking and re-refresh, and",
            "make operator-side v1 edits in the working copy instead. This working-copy",
            "handoff is still local-only, diagnostic-only, and not hook-facing.",
            "",
            "## Hook-facing candidate path",
            "",
            f"The existing `rpc_tune.py` handwritten hook can point at `{manual_candidate_path}`",
            "today. That module is deliberately honest:",
            "",
            "- it keeps the checked-in editable seed and checked-in candidate v0 side by side in this directory",
            "- it returns a local/staging-only override descriptor for candidate v0",
            "- `rpc_tune.py` now consumes that descriptor before `compile_relax()`, so the handwritten hook can replace the selected PrimFunc without touching trusted current",
            "- the current contract is explicitly diagnostic-only: it is a raw pre-compile replacement path with `schedule_context_guarantee=not_guaranteed`",
            "- runtime or reprobe numbers from this seam are `non_comparable_diagnostic_only`, not candidate-performance evidence",
            "- a future `schedule_context_preserving_evaluation` path is still required before another handwritten candidate can be judged on performance",
            "",
            "## Edit toward candidate v0",
            "",
            f"1. Start from `{editable_tir_path}`.",
            f"2. Keep `{manual_candidate_path}` as the hook-facing module path.",
            "3. Keep the buffer contract stable:",
            "   input `(1, 48, 64, 64)`, weight `(48, 24, 3, 3)`, bias `(1, 24, 1, 1)`, output `(1, 24, 128, 128)`.",
            "4. Treat `data_dilate`, `data_pad`, `kernel_transform`, `compute`, and `T_add` as the honest baseline stages from the captured workload.",
            "5. First manual edits should stay narrow: reduce intermediate traffic, fuse cheap transforms when possible, and only then try tiling/vectorization around `compute`.",
            "",
            "## Hook wiring diagnostic through the existing manual hook",
            "",
            "Regenerate the overlay so it points at the checked-in candidate module:",
            "",
            "```bash",
            "python3 ./session_bootstrap/scripts/prepare_fused_conv2d_transpose1_add9_manual_hook_overlay.py \\",
            "  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold \\",
            f"  --manual-impl-path {manual_candidate_path} \\",
            "  --allow-overwrite",
            "```",
            "",
            "Then exercise the existing hook with no remote work:",
            "",
            "```bash",
            "bash ./session_bootstrap/scripts/capture_fused_conv2d_transpose1_add9_manual_seed.sh \\",
            "  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold \\",
            "  --allow-existing-output",
            "```",
            "",
            "That proves the hook is loading the checked-in candidate path. It does not",
            "yet prove a performance change. It proves the local handwritten path reaches",
            "the checked-in candidate v0 and applies it at the pre-compile integration point.",
            "Treat any payload/runtime number from this path as diagnostic-only until a",
            "schedule-context-preserving evaluation contract exists.",
            "",
            "## Preferred local schedule-preserving build path",
            "",
            "Once hook wiring is confirmed and the scaffold pack exists, prefer this",
            "one-shot local-only path before any future remote/staging validation:",
            "",
            "```bash",
            "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py \\",
            "  --scaffold-dir ./session_bootstrap/tmp/handwritten_fused_conv2d_transpose1_add9_scaffold",
            "```",
            "",
            "This wrapper drives the checked-in best-staging task-summary / DB defaults,",
            "performs the post-DB scheduled `fused_conv2d_transpose1_add9` swap, syncs the",
            "result back into the scaffold bookkeeping pack, and prints a concise final JSON",
            "summary with the local artifact/report/SHA plus scaffold bookkeeping/template",
            "paths. The underlying `run_transpose1_post_db_local_build.py` and",
            "`sync_transpose1_post_db_local_build_result.py` commands remain available if you",
            "need to split those diagnostics.",
            "",
            "Default build outputs still land under:",
            "",
            "```text",
            "./session_bootstrap/tmp/transpose1_post_db_swap_local_build",
            "```",
            "",
            "This is still build-level diagnostic evidence only, but it preserves the best",
            "staging schedule context much more honestly than the older raw pre-compile hook",
            "lane.",
            "",
            "For the smallest useful `v1` prep step, keep the scheduled reference seed as",
            "the frozen source of truth, refresh the scheduled-form v1 working copy from",
            "it, and keep the older raw pre-compile seed only for backtracking or",
            "hook-wiring comparison.",
            "",
            "## Staging lane after a real override exists",
            "",
            "Reuse the same `manual_hook_overlay.env` with the existing staging-safe",
            "one-shot and profile commands from the transpose1 handwritten runbooks.",
            "Do not overwrite trusted current while this checked-in candidate is still",
            "seed-derived.",
            "Until a `schedule_context_preserving_evaluation` path exists, treat those",
            "one-shot / reprobe outputs as contract-side diagnostics rather than",
            "performance-comparable evidence.",
            "",
            "## Source reminder",
            "",
            f"The original captured pre-compile snapshot is still at `{repo_native(seed_tir_path)}` if you need the full Relax callsite context.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.seed_json = require_file(as_abs(args.seed_json), "captured seed json")
    args.seed_tir = require_file(as_abs(args.seed_tir), "captured seed tir")
    args.task_log = require_file(as_abs(args.task_log), "captured task log")
    args.output_dir = as_abs(args.output_dir)

    editable_tir_path = args.output_dir / EDITABLE_TIR_FILENAME
    manifest_path = args.output_dir / MANIFEST_FILENAME
    readme_path = args.output_dir / README_FILENAME
    ensure_clean_outputs(
        [editable_tir_path, manifest_path, readme_path], args.allow_overwrite
    )

    seed_payload = load_seed_json(args.seed_json)
    extracted_tir = extract_initial_tir(args.task_log)
    manifest = build_manifest(
        seed_payload=seed_payload,
        seed_json_path=args.seed_json,
        seed_tir_path=args.seed_tir,
        task_log_path=args.task_log,
        output_dir=args.output_dir,
    )

    write_text(
        editable_tir_path,
        render_editable_tir(
            seed_json_path=args.seed_json,
            seed_tir_path=args.seed_tir,
            task_log_path=args.task_log,
            extracted_tir=extracted_tir,
        ),
    )
    write_text(
        manifest_path,
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )
    write_text(
        readme_path,
        render_readme(
            seed_json_path=args.seed_json,
            seed_tir_path=args.seed_tir,
            task_log_path=args.task_log,
            output_dir=args.output_dir,
        ),
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "output_dir": str(args.output_dir),
                "editable_tir_path": str(editable_tir_path),
                "manifest_path": str(manifest_path),
                "readme_path": str(readme_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
