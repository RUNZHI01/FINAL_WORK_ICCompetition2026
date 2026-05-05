#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SSH_WITH_PASSWORD_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "ssh_with_password.sh"

RAW_LSCPU_BEGIN = "=== BIG_LITTLE_LSCPU BEGIN ==="
RAW_LSCPU_END = "=== BIG_LITTLE_LSCPU END ==="
RAW_LSCPU_E_BEGIN = "=== BIG_LITTLE_LSCPU_E BEGIN ==="
RAW_LSCPU_E_END = "=== BIG_LITTLE_LSCPU_E END ==="

HOST_KEYS = ("REMOTE_HOST", "PHYTIUM_PI_HOST")
USER_KEYS = ("REMOTE_USER", "PHYTIUM_PI_USER")
PASSWORD_KEYS = ("REMOTE_PASS", "PHYTIUM_PI_PASSWORD")
PORT_KEYS = ("REMOTE_SSH_PORT", "PHYTIUM_PI_PORT")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_project_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    return path


def parse_env_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env_file(raw_path: str | None) -> dict[str, str]:
    if not raw_path:
        return {}
    path = resolve_project_path(raw_path)
    if not path.is_file():
        raise ValueError(f"env file not found: {repo_relative(path)}")
    return parse_env_text(path.read_text(encoding="utf-8"))


def first_non_empty(mapping: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(mapping.get(key, "")).strip()
        if value:
            return value
    return ""


def normalize_port(raw_value: str) -> str:
    value = (raw_value or "22").strip() or "22"
    try:
        port = int(value)
    except ValueError as err:
        raise ValueError(f"invalid SSH port: {raw_value}") from err
    if port < 1 or port > 65535:
        raise ValueError(f"invalid SSH port: {raw_value}")
    return str(port)


def parse_cpu_list(raw: str) -> list[int]:
    text = raw.strip()
    if not text:
        return []
    cpus: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start = int(start_raw.strip())
            end = int(end_raw.strip())
            if end < start:
                raise ValueError(f"invalid CPU range: {token}")
            cpus.update(range(start, end + 1))
        else:
            cpus.add(int(token))
    return sorted(cpus)


def format_cpu_list(cpus: list[int]) -> str:
    return ",".join(str(cpu) for cpu in sorted(cpus))


def parse_number(raw: str) -> float | None:
    token = raw.strip()
    if not token or token in {"-", "?", "N/A"}:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def parse_int(raw: str) -> int | None:
    token = raw.strip()
    if not token or token in {"-", "?", "N/A"}:
        return None
    try:
        return int(token)
    except ValueError:
        return None


def parse_online(raw: str) -> bool | None:
    token = raw.strip().lower()
    if not token:
        return None
    if token in {"y", "yes", "true", "1"}:
        return True
    if token in {"n", "no", "false", "0"}:
        return False
    return None


def parse_lscpu_summary(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip()
    return values


def parse_lscpu_extended(text: str) -> dict[str, Any]:
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not columns:
            columns = re.split(r"\s+", line)
            continue
        parts = line.split(None, len(columns) - 1) if len(columns) > 1 else [line]
        if len(parts) < len(columns):
            parts.extend([""] * (len(columns) - len(parts)))
        raw_row = {columns[index]: parts[index] for index in range(len(columns))}
        cpu = parse_int(raw_row.get("CPU", ""))
        if cpu is None:
            continue
        rows.append(
            {
                "cpu": cpu,
                "core": parse_int(raw_row.get("CORE", "")),
                "socket": parse_int(raw_row.get("SOCKET", "")),
                "node": parse_int(raw_row.get("NODE", "")),
                "online": parse_online(raw_row.get("ONLINE", "")),
                "maxmhz": parse_number(raw_row.get("MAXMHZ", "")),
                "minmhz": parse_number(raw_row.get("MINMHZ", "")),
                "mhz": parse_number(raw_row.get("MHZ", "")),
                "raw": raw_row,
            }
        )
    return {"columns": columns, "rows": rows}


def build_raw_capture(lscpu_text: str, lscpu_e_text: str) -> str:
    return "\n".join(
        [
            RAW_LSCPU_BEGIN,
            lscpu_text.rstrip(),
            RAW_LSCPU_END,
            RAW_LSCPU_E_BEGIN,
            lscpu_e_text.rstrip(),
            RAW_LSCPU_E_END,
            "",
        ]
    )


def extract_marked_section(text: str, begin: str, end: str) -> str:
    try:
        start = text.index(begin) + len(begin)
        stop = text.index(end, start)
    except ValueError as err:
        raise ValueError("missing capture markers") from err
    return text[start:stop].strip()


def read_parse_inputs(
    *,
    input_path: str,
    lscpu_path: str,
    lscpu_e_path: str,
    stdin_kind: str,
) -> tuple[str, str, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "input_path": "",
        "lscpu_path": "",
        "lscpu_e_path": "",
        "stdin_used": False,
        "stdin_kind": stdin_kind,
    }
    if input_path:
        path = resolve_project_path(input_path)
        raw_text = path.read_text(encoding="utf-8")
        metadata["input_path"] = repo_relative(path)
    else:
        raw_text = ""

    lscpu_text = ""
    lscpu_e_text = ""
    if lscpu_path:
        path = resolve_project_path(lscpu_path)
        lscpu_text = path.read_text(encoding="utf-8")
        metadata["lscpu_path"] = repo_relative(path)
    if lscpu_e_path:
        path = resolve_project_path(lscpu_e_path)
        lscpu_e_text = path.read_text(encoding="utf-8")
        metadata["lscpu_e_path"] = repo_relative(path)

    if not raw_text and not lscpu_text and not lscpu_e_text:
        if sys.stdin.isatty():
            raise ValueError("no input provided; use --input, --lscpu/--lscpu-e, or stdin")
        raw_text = sys.stdin.read()
        metadata["stdin_used"] = True

    if raw_text:
        effective_kind = stdin_kind
        if effective_kind == "auto":
            stripped = raw_text.lstrip()
            if RAW_LSCPU_BEGIN in raw_text and RAW_LSCPU_E_BEGIN in raw_text:
                effective_kind = "capture"
            elif stripped.startswith("CPU ") or stripped.startswith("CPU\t") or stripped == "CPU":
                effective_kind = "lscpu-e"
            else:
                effective_kind = "lscpu"
        metadata["stdin_kind"] = effective_kind
        if effective_kind == "capture":
            lscpu_text = extract_marked_section(raw_text, RAW_LSCPU_BEGIN, RAW_LSCPU_END)
            lscpu_e_text = extract_marked_section(raw_text, RAW_LSCPU_E_BEGIN, RAW_LSCPU_E_END)
        elif effective_kind == "lscpu":
            lscpu_text = raw_text
        elif effective_kind == "lscpu-e":
            lscpu_e_text = raw_text
        else:
            raise ValueError(f"unsupported --stdin-kind: {stdin_kind}")

    if not lscpu_text and not lscpu_e_text:
        raise ValueError("no parseable lscpu input found")
    return lscpu_text, lscpu_e_text, metadata


def enrich_rows(summary: dict[str, str], rows: list[dict[str, Any]]) -> tuple[list[int], list[dict[str, Any]]]:
    online_from_summary = parse_cpu_list(summary.get("On-line CPU(s) list", ""))
    enriched: list[dict[str, Any]] = []
    for row in rows:
        online = row["online"]
        if online is None and online_from_summary:
            online = row["cpu"] in online_from_summary
        if online is None:
            online = True
        enriched.append({**row, "online": online})
    online_cpus = sorted(row["cpu"] for row in enriched if row["online"])
    if not online_cpus:
        online_cpus = online_from_summary
    return online_cpus, enriched


def split_metric_groups(values: list[tuple[int, float]]) -> dict[str, Any] | None:
    distinct_values = sorted({value for _, value in values})
    if len(distinct_values) < 2:
        return None
    best_gap = -1.0
    best_index = -1
    for index in range(len(distinct_values) - 1):
        gap = distinct_values[index + 1] - distinct_values[index]
        if gap > best_gap:
            best_gap = gap
            best_index = index
    if best_gap <= 0:
        return None
    threshold = max(50.0, 0.05 * abs(distinct_values[-1]))
    if best_gap < threshold:
        return None
    split_point = (distinct_values[best_index] + distinct_values[best_index + 1]) / 2.0
    low = sorted(cpu for cpu, value in values if value <= split_point)
    high = sorted(cpu for cpu, value in values if value > split_point)
    if not low or not high:
        return None
    return {
        "low": low,
        "high": high,
        "largest_gap_mhz": round(best_gap, 3),
        "gap_threshold_mhz": round(threshold, 3),
        "distinct_values": distinct_values,
    }


def evaluate_metric(
    rows: list[dict[str, Any]],
    *,
    online_cpus: list[int],
    metric_key: str,
    metric_label: str,
    confidence: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    online_rows = [row for row in rows if row["online"]]
    values = [(row["cpu"], row[metric_key]) for row in online_rows if row[metric_key] is not None]
    covered_cpus = sorted(cpu for cpu, _ in values)
    missing_cpus = sorted(set(online_cpus) - set(covered_cpus))
    if missing_cpus:
        warnings.append(f"{metric_label} missing for CPU(s): {format_cpu_list(missing_cpus)}")
        return None, warnings
    split = split_metric_groups([(cpu, float(value)) for cpu, value in values])
    if split is None:
        warnings.append(f"{metric_label} does not provide a stable big/little split")
        return None, warnings
    big_values = sorted({float(value) for cpu, value in values if cpu in split["high"]})
    little_values = sorted({float(value) for cpu, value in values if cpu in split["low"]})
    return (
        {
            "status": "ok",
            "confidence": confidence,
            "basis": metric_key,
            "big_cores": split["high"],
            "little_cores": split["low"],
            "big_cores_env": format_cpu_list(split["high"]),
            "little_cores_env": format_cpu_list(split["low"]),
            "largest_gap_mhz": split["largest_gap_mhz"],
            "gap_threshold_mhz": split["gap_threshold_mhz"],
            "big_values": [round(value, 3) for value in big_values],
            "little_values": [round(value, 3) for value in little_values],
            "explanation": (
                f"Per-CPU {metric_label} splits online CPUs into a higher-frequency group "
                f"{format_cpu_list(split['high'])} and a lower-frequency group {format_cpu_list(split['low'])}."
            ),
        },
        warnings,
    )


def suggest_big_little(
    summary: dict[str, str],
    parsed_extended: dict[str, Any],
) -> tuple[dict[str, Any], list[int], list[dict[str, Any]], list[str]]:
    online_cpus, rows = enrich_rows(summary, parsed_extended["rows"])
    warnings: list[str] = []
    if not online_cpus:
        return (
            {
                "status": "needs_manual_confirmation",
                "confidence": "none",
                "basis": "none",
                "big_cores": [],
                "little_cores": [],
                "big_cores_env": "",
                "little_cores_env": "",
                "explanation": "No online CPUs were detected from lscpu output.",
            },
            online_cpus,
            rows,
            warnings,
        )

    for metric_key, metric_label, confidence in (
        ("maxmhz", "MAXMHZ", "high"),
        ("minmhz", "MINMHZ", "medium"),
    ):
        candidate, metric_warnings = evaluate_metric(
            rows,
            online_cpus=online_cpus,
            metric_key=metric_key,
            metric_label=metric_label,
            confidence=confidence,
        )
        warnings.extend(metric_warnings)
        if candidate is not None:
            return candidate, online_cpus, rows, warnings

    explanation = "Unable to derive a reliable big/little split from per-CPU MAXMHZ/MINMHZ."
    if not parsed_extended["rows"]:
        explanation = "lscpu -e rows are missing; capture lscpu -e output for a reliable suggestion."
    return (
        {
            "status": "needs_manual_confirmation",
            "confidence": "none",
            "basis": "none",
            "big_cores": [],
            "little_cores": [],
            "big_cores_env": "",
            "little_cores_env": "",
            "explanation": explanation,
        },
        online_cpus,
        rows,
        warnings,
    )


def analyze_topology(
    *,
    lscpu_text: str,
    lscpu_e_text: str,
    source: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = parse_lscpu_summary(lscpu_text)
    parsed_extended = parse_lscpu_extended(lscpu_e_text)
    suggestion, online_cpus, rows, warnings = suggest_big_little(summary, parsed_extended)
    status = "ok" if suggestion["status"] == "ok" else "needs_manual_confirmation"
    payload = {
        "status": status,
        "source": source,
        "summary": {
            "architecture": summary.get("Architecture", ""),
            "model_name": summary.get("Model name", ""),
            "cpu_count": summary.get("CPU(s)", ""),
            "online_cpu_list": summary.get("On-line CPU(s) list", format_cpu_list(online_cpus)),
        },
        "topology": {
            "online_cpus": online_cpus,
            "columns": parsed_extended["columns"],
            "rows": [
                {
                    "cpu": row["cpu"],
                    "core": row["core"],
                    "socket": row["socket"],
                    "node": row["node"],
                    "online": row["online"],
                    "maxmhz": row["maxmhz"],
                    "minmhz": row["minmhz"],
                    "mhz": row["mhz"],
                }
                for row in rows
            ],
        },
        "suggestion": suggestion,
        "warnings": warnings,
    }
    if extra:
        payload["input"] = extra
    return payload


def build_remote_probe_payload() -> str:
    return (
        "set -eu\n"
        f"printf '%s\\n' {shlex.quote(RAW_LSCPU_BEGIN)}\n"
        "LC_ALL=C lscpu\n"
        f"printf '%s\\n' {shlex.quote(RAW_LSCPU_END)}\n"
        f"printf '%s\\n' {shlex.quote(RAW_LSCPU_E_BEGIN)}\n"
        "LC_ALL=C lscpu -e\n"
        f"printf '%s\\n' {shlex.quote(RAW_LSCPU_E_END)}\n"
    )


def build_remote_probe_command(
    *,
    host: str,
    user: str,
    password: str,
    port: str,
) -> tuple[list[str], dict[str, Any]]:
    remote_command = build_remote_probe_payload()
    connection = {
        "host": host,
        "user": user,
        "port": port,
        "auth_mode": "ssh_with_password" if password else "ssh",
    }
    if password:
        return (
            [
                "bash",
                str(SSH_WITH_PASSWORD_SCRIPT),
                "--host",
                host,
                "--user",
                user,
                "--pass",
                password,
                "--port",
                port,
                "--",
                remote_command,
            ],
            connection,
        )
    return (
        [
            "ssh",
            "-p",
            port,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "BatchMode=yes",
            f"{user}@{host}",
            remote_command,
        ],
        connection,
    )


def resolve_ssh_config(args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    values = load_env_file(args.env)
    host = args.host or first_non_empty(values, HOST_KEYS)
    user = args.user or first_non_empty(values, USER_KEYS)
    password = args.password or first_non_empty(values, PASSWORD_KEYS)
    port = normalize_port(args.port or first_non_empty(values, PORT_KEYS) or "22")
    if not host or not user:
        raise ValueError("remote SSH mode requires host and user via args or --env")
    warnings: list[str] = []
    if not password:
        warnings.append("REMOTE_PASS/PHYTIUM_PI_PASSWORD not set; falling back to plain ssh")
    return (
        {
            "host": host,
            "user": user,
            "password": password,
            "port": port,
            "env_file": repo_relative(resolve_project_path(args.env)) if args.env else "",
        },
        warnings,
    )


def run_remote_probe(args: argparse.Namespace) -> dict[str, Any]:
    ssh_config, warnings = resolve_ssh_config(args)
    command, connection = build_remote_probe_command(
        host=ssh_config["host"],
        user=ssh_config["user"],
        password=ssh_config["password"],
        port=ssh_config["port"],
    )
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=args.timeout_sec,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        return {
            "status": "error",
            "source": "ssh",
            "connection": connection,
            "stderr": stderr,
            "stdout": stdout,
            "warnings": warnings,
            "returncode": completed.returncode,
        }

    raw_capture = completed.stdout
    lscpu_text = extract_marked_section(raw_capture, RAW_LSCPU_BEGIN, RAW_LSCPU_END)
    lscpu_e_text = extract_marked_section(raw_capture, RAW_LSCPU_E_BEGIN, RAW_LSCPU_E_END)
    if args.write_raw:
        output_path = resolve_project_path(args.write_raw)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build_raw_capture(lscpu_text, lscpu_e_text), encoding="utf-8")
    payload = analyze_topology(
        lscpu_text=lscpu_text,
        lscpu_e_text=lscpu_e_text,
        source="ssh",
        extra={
            "env_file": ssh_config["env_file"],
            "write_raw": repo_relative(resolve_project_path(args.write_raw)) if args.write_raw else "",
        },
    )
    payload["connection"] = connection
    payload["warnings"] = warnings + payload.get("warnings", [])
    return payload


def print_summary(payload: dict[str, Any]) -> None:
    suggestion = payload.get("suggestion", {})
    online_cpus = payload.get("topology", {}).get("online_cpus", [])
    print(f"status={payload.get('status', 'unknown')}")
    print(f"source={payload.get('source', 'unknown')}")
    if online_cpus:
        print(f"online_cpus={format_cpu_list(list(online_cpus))}")
    if suggestion.get("big_cores_env"):
        print(f"BIG_LITTLE_BIG_CORES={suggestion['big_cores_env']}")
    if suggestion.get("little_cores_env"):
        print(f"BIG_LITTLE_LITTLE_CORES={suggestion['little_cores_env']}")
    if suggestion.get("basis"):
        print(f"basis={suggestion['basis']}")
    if suggestion.get("confidence"):
        print(f"confidence={suggestion['confidence']}")
    if suggestion.get("explanation"):
        print(f"explanation={suggestion['explanation']}")
    for warning in payload.get("warnings", []):
        print(f"warning={warning}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only big.LITTLE topology probe for tomorrow's execution prep. "
            "It parses lscpu/lscpu -e output and suggests BIG_LITTLE_BIG_CORES "
            "and BIG_LITTLE_LITTLE_CORES when the evidence is strong enough."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse local lscpu/lscpu -e text from files or stdin.",
    )
    parse_parser.add_argument("--input", default="", help="Marker-wrapped capture file produced by this helper.")
    parse_parser.add_argument("--lscpu", default="", help="Path to raw lscpu output.")
    parse_parser.add_argument("--lscpu-e", default="", help="Path to raw lscpu -e output.")
    parse_parser.add_argument(
        "--stdin-kind",
        choices=("auto", "capture", "lscpu", "lscpu-e"),
        default="auto",
        help="How to interpret stdin or --input text.",
    )
    parse_parser.add_argument("--json-only", action="store_true", help="Print JSON only.")

    ssh_parser = subparsers.add_parser(
        "ssh",
        help="Run a read-only remote lscpu/lscpu -e probe over SSH and print a suggestion.",
    )
    ssh_parser.add_argument("--env", default="", help="Env file with REMOTE_* or PHYTIUM_PI_* SSH settings.")
    ssh_parser.add_argument("--host", default="", help="Remote host override.")
    ssh_parser.add_argument("--user", default="", help="Remote user override.")
    ssh_parser.add_argument("--password", default="", help="Remote password override.")
    ssh_parser.add_argument("--port", default="", help="Remote SSH port override.")
    ssh_parser.add_argument("--write-raw", default="", help="Optional path to save the raw marker-wrapped capture.")
    ssh_parser.add_argument("--timeout-sec", type=float, default=30.0, help="SSH timeout in seconds.")
    ssh_parser.add_argument("--json-only", action="store_true", help="Print JSON only.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "parse":
        lscpu_text, lscpu_e_text, metadata = read_parse_inputs(
            input_path=args.input,
            lscpu_path=args.lscpu,
            lscpu_e_path=args.lscpu_e,
            stdin_kind=args.stdin_kind,
        )
        payload = analyze_topology(
            lscpu_text=lscpu_text,
            lscpu_e_text=lscpu_e_text,
            source="local_parse",
            extra=metadata,
        )
        if not args.json_only:
            print_summary(payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if args.command == "ssh":
        payload = run_remote_probe(args)
        if not args.json_only:
            print_summary(payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload.get("status") != "error" else 1

    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        raise SystemExit(2) from err
