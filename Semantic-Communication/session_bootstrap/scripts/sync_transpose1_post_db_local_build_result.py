#!/usr/bin/env python3
"""Sync transpose1 post-db local build facts back into the scaffold pack.

This helper is intentionally narrow and operator-specific:
- it only understands the handwritten transpose1 scaffold workflow
- it reads the local report emitted by run_transpose1_post_db_local_build.py
- it records local build facts into scaffold bookkeeping/template/env files
- it stays diagnostic-only and does not imply payload or runtime validation
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import re
import shlex
import time
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
DEFAULT_LOCAL_BUILD_OUTPUT_DIR = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "tmp"
    / "transpose1_post_db_swap_local_build"
)
DEFAULT_LOCAL_BUILD_ARTIFACT_NAME = f"{OPERATOR_NAME}_post_db_swap.so"
DEFAULT_LOCAL_BUILD_REPORT_NAME = f"{OPERATOR_NAME}_post_db_swap_report.json"
LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME = "latest_local_build_sync_snapshot.md"
SYNC_COMMENT = "# Synced from the local post-db build report."
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync the transpose1 local post-db build report back into the "
            "handwritten scaffold bookkeeping flow."
        )
    )
    parser.add_argument(
        "--scaffold-dir",
        type=Path,
        default=DEFAULT_SCAFFOLD_DIR,
        help="Existing handwritten scaffold directory to update in place.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help=(
            "Local JSON report from run_transpose1_post_db_local_build.py. "
            "If omitted, the helper falls back to --output-dir or the scaffold's "
            "preferred report path."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Directory containing the local post-db build artifact and adjacent "
            "JSON report. The helper expects the standard transpose1 basenames."
        ),
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


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    digest = value.strip()
    if not digest or not SHA256_RE.fullmatch(digest):
        return None
    return digest.lower()


def merge_nonempty_reference(target: dict[str, str], key: str, value: Any) -> None:
    if isinstance(value, str) and value.strip():
        target[key] = value.strip()


def build_default_preferred_local_post_db_build() -> dict[str, str]:
    output_dir = repo_native(DEFAULT_LOCAL_BUILD_OUTPUT_DIR)
    return {
        "command": (
            "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py "
            f"--output-dir {shell_quote(output_dir)}"
        ),
        "output_dir": output_dir,
        "artifact_name": DEFAULT_LOCAL_BUILD_ARTIFACT_NAME,
        "report_name": DEFAULT_LOCAL_BUILD_REPORT_NAME,
        "artifact_path": repo_native(DEFAULT_LOCAL_BUILD_OUTPUT_DIR / DEFAULT_LOCAL_BUILD_ARTIFACT_NAME),
        "report_path": repo_native(DEFAULT_LOCAL_BUILD_OUTPUT_DIR / DEFAULT_LOCAL_BUILD_REPORT_NAME),
        "output_naming_note": (
            "run_transpose1_post_db_local_build.py keeps these basenames; overriding "
            "--output-dir only changes the parent directory."
        ),
    }


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

    for key, bookkeeping_key in (
        ("output_dir", "preferred_local_build_output_dir"),
        ("artifact_path", "preferred_local_build_artifact_path"),
        ("report_path", "preferred_local_build_report_path"),
    ):
        merge_nonempty_reference(
            preferred_local_post_db_build,
            key,
            bookkeeping.get(bookkeeping_key),
        )
    return preferred_local_post_db_build


def build_local_build_command(output_dir: str) -> str:
    return (
        "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build.py "
        f"--output-dir {shell_quote(output_dir)}"
    )


def build_local_build_and_sync_command(scaffold_dir: Path, output_dir: str) -> str:
    return (
        "python3 ./session_bootstrap/scripts/run_transpose1_post_db_local_build_and_sync.py "
        f"--scaffold-dir {shell_quote(repo_native(scaffold_dir))} "
        f"--output-dir {shell_quote(output_dir)}"
    )


def build_sync_command(scaffold_dir: Path, output_dir: str) -> str:
    return (
        "python3 ./session_bootstrap/scripts/sync_transpose1_post_db_local_build_result.py "
        f"--scaffold-dir {shell_quote(repo_native(scaffold_dir))} "
        f"--output-dir {shell_quote(output_dir)}"
    )


def load_bookkeeping(bookkeeping_json: Path) -> dict[str, Any]:
    payload = json.loads(bookkeeping_json.read_text(encoding="utf-8"))
    operator = payload.get("operator")
    if operator != OPERATOR_NAME:
        raise SystemExit(
            f"ERROR: expected bookkeeping operator {OPERATOR_NAME!r}, got {operator!r}"
        )
    return payload


def resolve_report_json(args: argparse.Namespace, bookkeeping: dict[str, Any]) -> Path:
    if args.report_json is not None:
        return require_file(as_abs(args.report_json), "local build report JSON")

    if args.output_dir is not None:
        output_dir = require_dir(as_abs(args.output_dir), "local build output dir")
        return require_file(
            output_dir / DEFAULT_LOCAL_BUILD_REPORT_NAME,
            "local build report JSON",
        )

    preferred_local_build = resolve_preferred_local_post_db_build(bookkeeping)
    return require_file(
        as_abs(Path(preferred_local_build["report_path"])),
        "local build report JSON",
    )


def resolve_artifact_path(report: dict[str, Any], report_json: Path) -> Path:
    local_build_output = report.get("local_build_output")
    if isinstance(local_build_output, dict):
        artifact_path = local_build_output.get("artifact_path")
        if isinstance(artifact_path, str) and artifact_path.strip():
            return as_abs(Path(artifact_path))
    return (report_json.parent / DEFAULT_LOCAL_BUILD_ARTIFACT_NAME).resolve()


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def update_env_sha(path: Path, artifact_sha256: str | None) -> None:
    if artifact_sha256 is None:
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    line_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith("INFERENCE_CURRENT_EXPECTED_SHA256=")
        ),
        None,
    )
    if line_index is None:
        raise SystemExit(f"ERROR: expected INFERENCE_CURRENT_EXPECTED_SHA256 in {path}")

    lines[line_index] = f"INFERENCE_CURRENT_EXPECTED_SHA256={artifact_sha256}"
    if line_index > 0:
        previous = lines[line_index - 1]
        if previous.startswith("# ") and (
            "INFERENCE_CURRENT_EXPECTED_SHA256" in previous
            or "Prefilled from --manual-artifact-sha256." in previous
            or previous == SYNC_COMMENT
        ):
            lines[line_index - 1] = SYNC_COMMENT
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def replace_prefixed_line(
    path: Path,
    replacements: dict[str, str],
    *,
    insert_after: dict[str, str] | None = None,
) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    seen_prefixes: set[str] = set()
    for index, line in enumerate(lines):
        for prefix, replacement in replacements.items():
            if line.startswith(prefix):
                lines[index] = replacement
                seen_prefixes.add(prefix)
                break

    if insert_after is not None:
        for prefix, anchor_prefix in insert_after.items():
            if prefix in seen_prefixes:
                continue
            anchor_index = next(
                (index for index, line in enumerate(lines) if line.startswith(anchor_prefix)),
                None,
            )
            if anchor_index is not None:
                lines.insert(anchor_index + 1, replacements[prefix])
                seen_prefixes.add(prefix)

    missing = [prefix for prefix in replacements if prefix not in seen_prefixes]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"ERROR: expected scaffold template fields missing in {path}: {joined}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_local_build_swap_result(sync_payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("swap_succeeded", "build_status", "export_status"):
        value = sync_payload.get(key)
        if value is None:
            continue
        parts.append(f"{key}={value}")
    if not parts:
        parts.append("diagnostic_sync_recorded")
    return ", ".join(parts)


def render_local_build_notes(sync_payload: dict[str, Any]) -> str:
    parts = [
        "diagnostic-only sync",
        f"report={sync_payload['report_path']}",
        f"artifact_exists={sync_payload['artifact_exists']}",
    ]
    artifact_size_bytes = sync_payload.get("artifact_size_bytes")
    if artifact_size_bytes is not None:
        parts.append(f"artifact_size_bytes={artifact_size_bytes}")
    artifact_sha256 = sync_payload.get("artifact_sha256")
    if artifact_sha256 is not None:
        parts.append(f"artifact_sha256={artifact_sha256}")
    return "; ".join(parts)


def render_snapshot_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "<not_synced_yet>"
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or "<not_synced_yet>"
    return str(value)


def build_latest_local_build_sync_snapshot(sync_payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Latest local build+sync snapshot",
            "",
            "- snapshot_status: `synced_local_build_result`",
            f"- synced_at: `{render_snapshot_value(sync_payload.get('synced_at'))}`",
            f"- report_path: `{render_snapshot_value(sync_payload.get('report_path'))}`",
            f"- artifact_path: `{render_snapshot_value(sync_payload.get('artifact_path'))}`",
            f"- artifact_sha256: `{render_snapshot_value(sync_payload.get('artifact_sha256'))}`",
            f"- artifact_exists: `{render_snapshot_value(sync_payload.get('artifact_exists'))}`",
            f"- build_status: `{render_snapshot_value(sync_payload.get('build_status'))}`",
            f"- swap_succeeded: `{render_snapshot_value(sync_payload.get('swap_succeeded'))}`",
            f"- export_status: `{render_snapshot_value(sync_payload.get('export_status'))}`",
            "",
            "This file is refreshed by `sync_transpose1_post_db_local_build_result.py` and only records local diagnostic build facts.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.scaffold_dir = require_dir(as_abs(args.scaffold_dir), "scaffold dir")

    bookkeeping_json = require_file(args.scaffold_dir / "bookkeeping.json", "scaffold bookkeeping")
    validation_template_md = require_file(
        args.scaffold_dir / "validation_report_template.md",
        "validation report template",
    )
    validate_env = require_file(
        args.scaffold_dir / "manual_validate_inference.env",
        "validation inference env",
    )
    profile_env = require_file(args.scaffold_dir / "manual_profile.env", "profile env")
    bookkeeping = load_bookkeeping(bookkeeping_json)
    latest_local_build_sync_snapshot_md = (
        args.scaffold_dir / LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME
    )

    report_json = resolve_report_json(args, bookkeeping)
    report = json.loads(report_json.read_text(encoding="utf-8"))
    if report.get("operator") != OPERATOR_NAME:
        raise SystemExit(
            f"ERROR: expected report operator {OPERATOR_NAME!r}, got {report.get('operator')!r}"
        )

    local_build_output = report.get("local_build_output")
    if not isinstance(local_build_output, dict):
        raise SystemExit(f"ERROR: missing local_build_output in {report_json}")

    artifact_path = resolve_artifact_path(report, report_json)
    artifact_exists = artifact_path.is_file()
    artifact_sha256 = normalize_sha256(local_build_output.get("artifact_sha256"))
    if artifact_sha256 is None and artifact_exists:
        artifact_sha256 = file_sha256(artifact_path)

    artifact_size_bytes = local_build_output.get("artifact_size_bytes")
    if artifact_exists:
        artifact_size_bytes = artifact_path.stat().st_size

    output_dir = artifact_path.parent.resolve()
    output_dir_repo = repo_native(output_dir)
    artifact_path_repo = repo_native(artifact_path)
    report_path_repo = repo_native(report_json)

    swap_payload = report.get("post_db_scheduled_swap")
    build_status = None
    swap_succeeded = None
    if isinstance(swap_payload, dict):
        raw_build_status = swap_payload.get("build_status")
        if isinstance(raw_build_status, str) and raw_build_status.strip():
            build_status = raw_build_status.strip()
        swap_succeeded = as_bool(swap_payload.get("swap_succeeded"))

    export_status = local_build_output.get("export_status")
    if isinstance(export_status, str):
        export_status = export_status.strip() or None
    else:
        export_status = None

    sync_payload = {
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "diagnostic_only": True,
        "source_report_json": report_path_repo,
        "report_path": report_path_repo,
        "output_dir": output_dir_repo,
        "artifact_path": artifact_path_repo,
        "artifact_exists": artifact_exists,
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size_bytes,
        "build_status": build_status,
        "swap_succeeded": swap_succeeded,
        "export_status": export_status,
        "report_id": report.get("report_id"),
    }

    preferred_local_build = resolve_preferred_local_post_db_build(bookkeeping)
    preferred_local_build.update(
        {
            "command": build_local_build_command(output_dir_repo),
            "output_dir": output_dir_repo,
            "artifact_name": artifact_path.name,
            "report_name": report_json.name,
            "artifact_path": artifact_path_repo,
            "report_path": report_path_repo,
        }
    )
    bookkeeping["preferred_local_post_db_build"] = preferred_local_build
    bookkeeping["local_schedule_preserving_build_output_dir"] = output_dir_repo
    bookkeeping["preferred_local_build_output_dir"] = output_dir_repo
    bookkeeping["preferred_local_build_artifact_path"] = artifact_path_repo
    bookkeeping["preferred_local_build_report_path"] = report_path_repo
    bookkeeping["preferred_local_build_output_names"] = {
        "artifact": artifact_path.name,
        "report": report_json.name,
    }
    if artifact_sha256 is not None:
        bookkeeping["manual_artifact_sha256"] = artifact_sha256
    bookkeeping["latest_local_post_db_build"] = sync_payload
    generated_files = bookkeeping.get("generated_files")
    if not isinstance(generated_files, dict):
        generated_files = {}
        bookkeeping["generated_files"] = generated_files
    generated_files[LATEST_LOCAL_BUILD_SYNC_SNAPSHOT_NAME] = str(
        latest_local_build_sync_snapshot_md
    )

    commands = bookkeeping.get("commands")
    if not isinstance(commands, dict):
        commands = {}
        bookkeeping["commands"] = commands
    commands["local_build_and_sync"] = build_local_build_and_sync_command(
        args.scaffold_dir,
        output_dir_repo,
    )
    commands["local_schedule_preserving_build"] = build_local_build_command(output_dir_repo)
    commands["sync_local_build_result"] = build_sync_command(args.scaffold_dir, output_dir_repo)

    bookkeeping_json.write_text(
        json.dumps(bookkeeping, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    latest_local_build_sync_snapshot_md.write_text(
        build_latest_local_build_sync_snapshot(sync_payload),
        encoding="utf-8",
    )

    validation_replacements = {
        "- local_build_command: ": (
            f"- local_build_command: `{commands['local_schedule_preserving_build']}`"
        ),
        "- local_build_sync_command: ": (
            f"- local_build_sync_command: `{commands['sync_local_build_result']}`"
        ),
        "- preferred_local_build_output_dir: ": (
            f"- preferred_local_build_output_dir: `{output_dir_repo}`"
        ),
        "- preferred_local_build_report_json: ": (
            f"- preferred_local_build_report_json: `{report_path_repo}`"
        ),
        "- local_build_swap_result: ": (
            f"- local_build_swap_result: `{render_local_build_swap_result(sync_payload)}`"
        ),
        "- preferred_local_build_artifact: ": (
            f"- preferred_local_build_artifact: `{artifact_path_repo}`"
        ),
        "- local_build_notes: ": (
            f"- local_build_notes: `{render_local_build_notes(sync_payload)}`"
        ),
    }
    if artifact_sha256 is not None:
        validation_replacements["- candidate_sha256: "] = (
            f"- candidate_sha256: `{artifact_sha256}`"
        )

    replace_prefixed_line(
        validation_template_md,
        validation_replacements,
        insert_after={"- local_build_sync_command: ": "- local_build_command: "},
    )

    update_env_sha(validate_env, artifact_sha256)
    update_env_sha(profile_env, artifact_sha256)

    print(
        json.dumps(
            {
                "status": "ok",
                "scaffold_dir": str(args.scaffold_dir),
                "report_json": str(report_json),
                "artifact_path": artifact_path_repo,
                "artifact_sha256": artifact_sha256,
                "bookkeeping_json": str(bookkeeping_json),
                "validation_report_template": str(validation_template_md),
                "latest_local_build_sync_snapshot": str(latest_local_build_sync_snapshot_md),
                "diagnostic_only": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
