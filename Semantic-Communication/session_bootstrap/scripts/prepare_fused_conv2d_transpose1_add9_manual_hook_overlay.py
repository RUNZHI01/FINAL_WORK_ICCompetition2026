#!/usr/bin/env python3
"""Prepare the first manual-seed hook overlay for fused_conv2d_transpose1_add9.

This helper stays narrow on purpose:
- reuse the existing handwritten scaffold directory as the source of truth
- default the overlay to the checked-in candidate-v0 module
- optionally materialize one editable scaffold-local manual seed module when explicitly asked
- generate one rebuild overlay env that activates the existing pre-compile hook in rpc_tune.py
- avoid touching trusted current or any remote path
"""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OPERATOR_NAME = "fused_conv2d_transpose1_add9"
DEFAULT_SCAFFOLD_DIR = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "tmp"
    / "handwritten_fused_conv2d_transpose1_add9_scaffold"
)
DEFAULT_TEMPLATE_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "templates"
    / "handwritten"
    / "fused_conv2d_transpose1_add9_manual_impl.py.tmpl"
)
DEFAULT_CHECKED_IN_CANDIDATE_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "handwritten"
    / OPERATOR_NAME
    / f"{OPERATOR_NAME}_manual_candidate.py"
)
DEFAULT_LOCAL_BUILD_OUTPUT_DIR = (
    "./session_bootstrap/tmp/transpose1_post_db_swap_local_build"
)
DEFAULT_LOCAL_BUILD_ARTIFACT_NAME = f"{OPERATOR_NAME}_post_db_swap.so"
DEFAULT_LOCAL_BUILD_REPORT_NAME = f"{OPERATOR_NAME}_post_db_swap_report.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the handwritten rebuild overlay for the "
            f"{OPERATOR_NAME} scaffold. By default it points at the checked-in "
            "candidate-v0 hook target."
        )
    )
    parser.add_argument(
        "--scaffold-dir",
        type=Path,
        default=DEFAULT_SCAFFOLD_DIR,
        help="Existing scaffold directory produced by prepare_fused_conv2d_transpose1_add9_handwritten_scaffold.py.",
    )
    parser.add_argument(
        "--template-path",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help="Checked-in template used only when materializing a scaffold-local placeholder module.",
    )
    parser.add_argument(
        "--manual-impl-path",
        type=Path,
        help=(
            "Manual implementation module path for the overlay. Defaults to the "
            "checked-in candidate-v0 module; pass a scaffold-local path only when "
            "you explicitly want to materialize an editable placeholder seed file."
        ),
    )
    parser.add_argument(
        "--output-env",
        type=Path,
        help="Output path for the rebuild overlay env that points at the handwritten hook module.",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow overwriting a generated scaffold-local placeholder module or overlay env.",
    )
    return parser.parse_args(argv)


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def require_dir(path: Path, label: str) -> Path:
    if not path.is_dir():
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


def shell_quote(value: str) -> str:
    return shlex.quote(value)


def ensure_clean_outputs(paths: list[Path], allow_overwrite: bool) -> None:
    existing = [path for path in paths if path.exists()]
    if existing and not allow_overwrite:
        joined = "\n  ".join(str(path) for path in existing)
        raise SystemExit(
            "ERROR: output already exists. Re-run with --allow-overwrite or choose a "
            f"new location.\n  {joined}"
        )


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_bookkeeping(bookkeeping_json: Path) -> dict[str, Any]:
    payload = json.loads(bookkeeping_json.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise SystemExit(
            f"ERROR: expected bookkeeping operator {OPERATOR_NAME!r}, got {operator!r}"
        )
    return payload


def build_default_preferred_local_post_db_build() -> dict[str, str]:
    output_dir = repo_native(Path(DEFAULT_LOCAL_BUILD_OUTPUT_DIR))
    return {
        "command": (
            "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py "
            f"--output-dir {shell_quote(output_dir)}"
        ),
        "output_dir": output_dir,
        "artifact_name": DEFAULT_LOCAL_BUILD_ARTIFACT_NAME,
        "report_name": DEFAULT_LOCAL_BUILD_REPORT_NAME,
        "artifact_path": repo_native(
            Path(DEFAULT_LOCAL_BUILD_OUTPUT_DIR) / DEFAULT_LOCAL_BUILD_ARTIFACT_NAME
        ),
        "report_path": repo_native(
            Path(DEFAULT_LOCAL_BUILD_OUTPUT_DIR) / DEFAULT_LOCAL_BUILD_REPORT_NAME
        ),
        "output_naming_note": (
            "run_transpose1_post_db_local_build.py keeps these basenames; overriding "
            "--output-dir only changes the parent directory."
        ),
    }


def merge_nonempty_reference(target: dict[str, str], key: str, value: Any) -> None:
    if isinstance(value, str) and value.strip():
        target[key] = value.strip()


def resolve_preferred_local_post_db_build(bookkeeping: dict[str, Any]) -> dict[str, str]:
    preferred_local_post_db_build = build_default_preferred_local_post_db_build()
    preferred = bookkeeping.get("preferred_local_post_db_build")
    if isinstance(preferred, dict):
        for key in (
            "command",
            "output_dir",
            "artifact_name",
            "report_name",
            "artifact_path",
            "report_path",
            "output_naming_note",
        ):
            merge_nonempty_reference(preferred_local_post_db_build, key, preferred.get(key))

    commands = bookkeeping.get("commands")
    if isinstance(commands, dict):
        merge_nonempty_reference(
            preferred_local_post_db_build,
            "command",
            commands.get("local_schedule_preserving_build"),
        )

    merge_nonempty_reference(
        preferred_local_post_db_build,
        "output_dir",
        bookkeeping.get("preferred_local_build_output_dir"),
    )
    merge_nonempty_reference(
        preferred_local_post_db_build,
        "artifact_path",
        bookkeeping.get("preferred_local_build_artifact_path"),
    )
    merge_nonempty_reference(
        preferred_local_post_db_build,
        "report_path",
        bookkeeping.get("preferred_local_build_report_path"),
    )
    return preferred_local_post_db_build


def render_manual_impl(
    *,
    template_path: Path,
    bookkeeping: dict[str, Any],
    bookkeeping_json: Path,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    operator_context = bookkeeping.get("operator_context") or {}
    current_best_staging = bookkeeping.get("current_best_staging") or {}
    replacements = {
        "__OPERATOR_NAME__": bookkeeping.get("operator", OPERATOR_NAME),
        "__REFERENCE_STAGING_SHA256__": current_best_staging.get("artifact_sha256", ""),
        "__REFERENCE_PROFILE_JSON__": bookkeeping.get("current_profile_json", ""),
        "__ARGUMENT_SHAPES__": operator_context.get("current_argument_shapes", ""),
        "__BOOKKEEPING_JSON__": repo_native(bookkeeping_json),
        "__REMOTE_ARCHIVE_DIR__": bookkeeping.get("remote_archive_dir", ""),
    }
    rendered = template
    for token, value in replacements.items():
        if token not in rendered:
            raise SystemExit(f"ERROR: missing token in template: {token}")
        rendered = rendered.replace(token, json.dumps(value, ensure_ascii=False))
    return rendered


def resolve_manual_impl_target(
    *,
    scaffold_dir: Path,
    manual_impl_path: Path | None,
) -> tuple[Path, bool]:
    checked_in_candidate_path = DEFAULT_CHECKED_IN_CANDIDATE_PATH.resolve()
    if manual_impl_path is None:
        return checked_in_candidate_path, False

    resolved = as_abs(manual_impl_path)
    if resolved.exists() and not resolved.is_file():
        raise SystemExit(f"ERROR: handwritten hook module path is not a file: {resolved}")
    if resolved == checked_in_candidate_path:
        return resolved, False
    if resolved.exists() and not is_within(resolved, scaffold_dir):
        return resolved, False
    return resolved, True


def build_overlay_env(
    *,
    rebuild_env: Path,
    manual_impl_path: Path,
    bookkeeping_json: Path,
    bookkeeping: dict[str, Any],
) -> str:
    preferred_local_build = resolve_preferred_local_post_db_build(bookkeeping)

    lines = [
        "# Auto-generated overlay for the fused_conv2d_transpose1_add9 handwritten hook.",
        "# shellcheck source=/dev/null",
        f"source {shell_quote(str(rebuild_env.resolve()))}",
        "",
        "# This overlay is hook wiring only for the transpose1 handwritten seam.",
        "# It is local-only and diagnostic-only until you run the preferred post-db build.",
        "# Generating this file does not build, export, validate, or prove any performance result.",
        "# Preferred local build command:",
        f"# {preferred_local_build['command']}",
        f"# Preferred local build output dir: {preferred_local_build['output_dir']}",
        f"# Preferred local build artifact: {preferred_local_build['artifact_path']}",
        f"# Preferred local build report: {preferred_local_build['report_path']}",
        "",
        "# rpc_tune.py already consumes these variables at the pre-compile seam.",
        "# Keep this overlay staging-only by sourcing it only for the handwritten lane.",
        f"TVM_HANDWRITTEN_OP={OPERATOR_NAME}",
        f"TVM_HANDWRITTEN_IMPL_PATH={shell_quote(repo_native(manual_impl_path))}",
        "TVM_HANDWRITTEN_IMPL_ENTRYPOINT=build_manual_impl",
        "TVM_HANDWRITTEN_IMPL_METADATA_FN=describe_placeholder",
        f"TVM_HANDWRITTEN_BOOKKEEPING_JSON={shell_quote(repo_native(bookkeeping_json))}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.scaffold_dir = require_dir(as_abs(args.scaffold_dir), "scaffold dir")

    rebuild_env = require_file(args.scaffold_dir / "manual_rebuild.env", "scaffold rebuild env")
    bookkeeping_json = require_file(args.scaffold_dir / "bookkeeping.json", "scaffold bookkeeping")
    bookkeeping = load_bookkeeping(bookkeeping_json)
    preferred_local_build = resolve_preferred_local_post_db_build(bookkeeping)

    checked_in_candidate_path = require_file(
        DEFAULT_CHECKED_IN_CANDIDATE_PATH,
        "checked-in candidate module",
    )
    args.manual_impl_path, materialize_manual_impl = resolve_manual_impl_target(
        scaffold_dir=args.scaffold_dir,
        manual_impl_path=args.manual_impl_path,
    )
    args.output_env = as_abs(
        args.output_env if args.output_env is not None else args.scaffold_dir / "manual_hook_overlay.env"
    )

    protected_outputs = [args.output_env]
    if materialize_manual_impl:
        protected_outputs.append(args.manual_impl_path)
    ensure_clean_outputs(protected_outputs, args.allow_overwrite)

    if materialize_manual_impl:
        args.template_path = require_file(
            as_abs(args.template_path), "manual implementation template"
        )
        write_text(
            args.manual_impl_path,
            render_manual_impl(
                template_path=args.template_path,
                bookkeeping=bookkeeping,
                bookkeeping_json=bookkeeping_json,
            ),
        )
    else:
        require_file(args.manual_impl_path, "handwritten hook module")

    write_text(
        args.output_env,
        build_overlay_env(
            rebuild_env=rebuild_env,
            manual_impl_path=args.manual_impl_path,
            bookkeeping_json=bookkeeping_json,
            bookkeeping=bookkeeping,
        ),
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "scaffold_dir": str(args.scaffold_dir),
                "manual_impl_path": str(args.manual_impl_path),
                "manual_impl_generated": materialize_manual_impl,
                "output_env": str(args.output_env),
                "overlay_role": "hook_wiring_only",
                "overlay_is_hook_wiring_only": True,
                "preferred_local_build_command": preferred_local_build["command"],
                "preferred_local_build_output_dir": preferred_local_build["output_dir"],
                "preferred_local_build_artifact_path": preferred_local_build["artifact_path"],
                "preferred_local_build_report_path": preferred_local_build["report_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
