#!/usr/bin/env python3
"""Safely migrate historical USRP reconstruction jobs over SFTP."""

from __future__ import annotations

import argparse
import errno
import json
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.board_image_compare.sources import extract_usrp_token, plan_usrp_migration


DEFAULT_LEGACY_ROOT = "/home/user/Downloads/jscc-test/jscc/infer_outputs"
DEFAULT_OUTPUT_ROOT = "/home/user/Downloads/jscc-test-usrp"
DEFAULT_REPORT = (
    "Semantic-Communication/session_bootstrap/reports/"
    "usrp_output_migration_20260717.json"
)


def _remote_path(value: str | PurePosixPath) -> str:
    path = str(value).replace("\\", "/")
    if not path.startswith("/"):
        raise ValueError(f"remote path must be absolute: {value}")
    return str(PurePosixPath(path))


def _is_missing_error(exc: OSError) -> bool:
    return getattr(exc, "errno", None) in (None, errno.ENOENT)


def _remote_exists(sftp: Any, path: str) -> bool:
    try:
        sftp.stat(path)
    except OSError as exc:
        if _is_missing_error(exc):
            return False
        raise
    return True


def _mkdir_parents(sftp: Any, destination: str) -> None:
    parent = PurePosixPath(destination).parent
    current = PurePosixPath("/")
    for part in parent.parts[1:]:
        current /= part
        current_path = str(current)
        if not _remote_exists(sftp, current_path):
            sftp.mkdir(current_path)


def _copy_entry(entry: dict[str, Any], **updates: Any) -> dict[str, Any]:
    copied = dict(entry)
    copied.update(updates)
    return copied


def apply_migration(
    sftp: Any,
    migration_plan: Iterable[dict[str, Any]],
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Preflight a plan and optionally rename every safe classified source."""
    plan = [dict(entry) for entry in migration_plan]
    classified = [entry for entry in plan if entry.get("destination")]
    unresolved = [entry for entry in plan if not entry.get("destination")]
    pending: list[dict[str, Any]] = []
    already_moved: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for entry in classified:
        source = _remote_path(str(entry["source"]))
        destination = _remote_path(str(entry["destination"]))
        source_exists = _remote_exists(sftp, source)
        destination_exists = _remote_exists(sftp, destination)
        if source_exists and destination_exists:
            collisions.append(entry)
        elif destination_exists:
            already_moved.append(entry)
        elif source_exists:
            pending.append(entry)
        else:
            missing_entry = _copy_entry(
                entry,
                reason="classified source and destination are both missing",
            )
            missing.append(missing_entry)
            unresolved.append(missing_entry)

    safe = bool(plan) and not collisions and not missing
    moved: list[dict[str, Any]] = []
    if apply and safe:
        for entry in pending:
            source = _remote_path(str(entry["source"]))
            destination = _remote_path(str(entry["destination"]))
            _mkdir_parents(sftp, destination)
            sftp.rename(source, destination)
            moved.append(entry)

    return {
        "safe": safe,
        "classified": classified,
        "moved": moved,
        "already_moved": already_moved,
        "unresolved": unresolved,
        "collisions": collisions,
        "missing": missing,
    }


def rollback_migration(
    sftp: Any,
    report: dict[str, Any],
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Reverse classified report entries whose migrated destination exists."""
    reverse_plan: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in report.get("classified", []):
        source = entry.get("source")
        destination = entry.get("destination")
        if not source or not destination:
            continue
        if not _remote_exists(sftp, _remote_path(str(destination))):
            skipped.append(
                _copy_entry(entry, reason="rollback destination does not exist")
            )
            continue
        reverse_plan.append(
            _copy_entry(entry, source=destination, destination=source)
        )

    result = apply_migration(sftp, reverse_plan, apply=apply)
    result["unresolved"].extend(skipped)
    return result


def _evidence_token(name: str) -> str | None:
    token = extract_usrp_token(name)
    if token is not None:
        return token
    prefix = "cockpit_usrp_usrp-"
    if name.startswith(prefix):
        return name[len(prefix) :]
    return None


def _relative_evidence(source: str, run_root: Path) -> str | None:
    source_path = Path(source)
    try:
        return source_path.relative_to(run_root).as_posix()
    except ValueError:
        return source_path.name or None


def build_remote_migration_plan(
    job_names: Iterable[str],
    run_root: str | Path,
    legacy_root: str,
    output_root: str,
) -> list[dict[str, Any]]:
    """Classify from local evidence and produce reversible remote paths."""
    local_run_root = Path(run_root)
    remote_legacy_root = PurePosixPath(_remote_path(legacy_root))
    remote_output_root = PurePosixPath(_remote_path(output_root))
    names = sorted({str(name) for name in job_names})
    decisions = plan_usrp_migration(
        names,
        local_run_root,
        local_run_root,
        output_root,
    )
    remote_plan: list[dict[str, Any]] = []

    for job_name, decision in zip(names, decisions, strict=True):
        mode = decision.get("mode")
        evidence = (
            _relative_evidence(str(decision["source"]), local_run_root)
            if mode is not None
            else None
        )
        target_token = extract_usrp_token(job_name)
        evidence_token = _evidence_token(Path(evidence).name) if evidence else None
        if mode is None:
            classification = "unresolved"
            destination = None
        else:
            classification = (
                "inherited-base-summary"
                if target_token and evidence_token and target_token != evidence_token
                else "exact-summary"
            )
            layout = "iq-direct" if mode == "usrp-iq-direct" else "qpsk"
            destination = str(remote_output_root / layout / "tvm" / job_name)
        remote_plan.append(
            {
                "source": str(remote_legacy_root / job_name),
                "destination": destination,
                "mode": mode,
                "reason": decision["reason"],
                "classification": classification,
                "evidence": evidence,
            }
        )
    return remote_plan


def _listdir_if_present(sftp: Any, root: str) -> list[str]:
    try:
        return [str(name) for name in sftp.listdir(root)]
    except OSError as exc:
        if _is_missing_error(exc):
            return []
        raise


def collect_remote_job_names(sftp: Any, legacy_root: str, output_root: str) -> list[str]:
    """Collect strict USRP job names from the legacy and migrated TVM roots."""
    output = PurePosixPath(_remote_path(output_root))
    roots = [
        _remote_path(legacy_root),
        str(output / "qpsk" / "tvm"),
        str(output / "iq-direct" / "tvm"),
    ]
    names = {
        name
        for root in roots
        for name in _listdir_if_present(sftp, root)
        if extract_usrp_token(name) is not None
    }
    return sorted(names)


def write_report_atomic(report_path: str | Path, payload: dict[str, Any]) -> None:
    """Write stable JSON through a temporary sibling and Path.replace()."""
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _mode_counts(classified: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {"usrp-iq-direct": 0, "usrp-qpsk": 0}
    for entry in classified:
        mode = str(entry.get("mode") or "")
        if mode in counts:
            counts[mode] += 1
    return counts


def _classification_counts(plan: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "exact-summary": 0,
        "inherited-base-summary": 0,
        "unresolved": 0,
    }
    for entry in plan:
        classification = str(entry.get("classification") or "unresolved")
        counts[classification] = counts.get(classification, 0) + 1
    return counts


def _with_report_metadata(
    result: dict[str, Any],
    *,
    operation: str,
    apply: bool,
    host: str,
    port: int,
    user: str,
    run_root: str | None,
    legacy_root: str | None,
    output_root: str | None,
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "operation": operation,
        "apply": apply,
        "connection": {"host": host, "port": port, "user": user},
        "run_root": run_root,
        "legacy_root": legacy_root,
        "output_root": output_root,
        **result,
    }
    payload["counts"] = {
        key: len(payload[key])
        for key in (
            "classified",
            "moved",
            "already_moved",
            "unresolved",
            "collisions",
            "missing",
        )
    }
    payload["mode_counts"] = _mode_counts(payload["classified"])
    payload["classification_counts"] = _classification_counts(
        [*payload["classified"], *[entry for entry in payload["unresolved"] if not entry.get("destination")]]
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--run-root", default="USRP292x/qpsk_batch_spool_arq_runs")
    parser.add_argument("--legacy-root", default=DEFAULT_LEGACY_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback-report")
    return parser.parse_args(argv)


def _connect_sftp(args: argparse.Namespace) -> tuple[Any, Any]:
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=args.host,
        port=args.port,
        username=args.user,
        password=args.password,
        look_for_keys=False,
        allow_agent=False,
        timeout=10.0,
    )
    return client, client.open_sftp()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client, sftp = _connect_sftp(args)
    try:
        if args.rollback_report:
            prior_report = json.loads(Path(args.rollback_report).read_text(encoding="utf-8"))
            result = rollback_migration(sftp, prior_report, apply=args.apply)
            payload = _with_report_metadata(
                result,
                operation="rollback",
                apply=args.apply,
                host=args.host,
                port=args.port,
                user=args.user,
                run_root=prior_report.get("run_root"),
                legacy_root=prior_report.get("legacy_root"),
                output_root=prior_report.get("output_root"),
            )
        else:
            run_root = Path(args.run_root)
            if not run_root.is_dir():
                raise FileNotFoundError(f"local run evidence not found: {run_root}")
            job_names = collect_remote_job_names(sftp, args.legacy_root, args.output_root)
            plan = build_remote_migration_plan(
                job_names,
                run_root,
                args.legacy_root,
                args.output_root,
            )
            result = apply_migration(sftp, plan, apply=args.apply)
            payload = _with_report_metadata(
                result,
                operation="migration",
                apply=args.apply,
                host=args.host,
                port=args.port,
                user=args.user,
                run_root=str(run_root),
                legacy_root=_remote_path(args.legacy_root),
                output_root=_remote_path(args.output_root),
            )
        write_report_atomic(args.report, payload)
    finally:
        sftp.close()
        client.close()

    print(json.dumps({"safe": payload["safe"], **payload["counts"], **payload["mode_counts"]}, sort_keys=True))
    return 0 if payload["safe"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
