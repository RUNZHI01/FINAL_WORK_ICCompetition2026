#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re
import struct
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PREFIX = "legacy_baseline_db_bridge_probe"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe a baseline MetaSchedule DB snapshot for current-safe JSONDatabase "
            "compatibility, attempt guarded local normalization, and emit a machine-"
            "readable bridge report."
        )
    )
    parser.add_argument(
        "--source-db",
        type=Path,
        required=True,
        help="Local tuning_logs directory containing database_workload.json and database_tuning_record.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for generated probe artifacts. Defaults to session_bootstrap/tmp/<report_id>.",
    )
    parser.add_argument(
        "--report-id",
        help=f"Report prefix. Defaults to {DEFAULT_REPORT_PREFIX}_<timestamp>.",
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


def require_db_dir(path: Path) -> Path:
    directory = require_dir(path, "source db")
    require_file(directory / "database_workload.json", "database_workload.json")
    require_file(directory / "database_tuning_record.json", "database_tuning_record.json")
    return directory


def read_json_lines(path: Path) -> list[Any]:
    rows: list[Any] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def decode_streamed_json_payload(payload: str) -> Any:
    padding = "=" * ((4 - len(payload) % 4) % 4)
    raw = base64.b64decode(payload + padding)
    if len(raw) < 8:
        raise ValueError("streamed payload is too short")
    size = struct.unpack("<Q", raw[:8])[0]
    if len(raw) != size + 8:
        raise ValueError(
            f"streamed payload size mismatch: prefix={size} actual={len(raw) - 8}"
        )
    return json.loads(raw[8 : 8 + size].decode("utf-8"))


def encode_streamed_json_payload(json_obj: Any) -> str:
    raw = json.dumps(json_obj, ensure_ascii=False).encode("utf-8")
    streamed = struct.pack("<Q", len(raw)) + raw
    return base64.b64encode(streamed).decode("ascii")


def classify_workload_graph(graph: dict[str, Any]) -> str:
    if "root_index" in graph:
        return "current_safe_object_graph"
    if "root" in graph:
        return "legacy_root_object_graph"
    return "unknown_object_graph"


def normalize_numeric_string(value: Any) -> Any:
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


LEGACY_TYPE_NAME_MAP = {
    "": "None",
    "runtime.String": "ffi.String",
    "Array": "ffi.Array",
    "Map": "ffi.Map",
    "GlobalVar": "ir.GlobalVar",
    "IRModule": "ir.IRModule",
    "IntImm": "ir.IntImm",
    "FloatImm": "ir.FloatImm",
    "PrimType": "ir.PrimType",
    "PointerType": "ir.PointerType",
    "TupleType": "ir.TupleType",
    "FuncType": "ir.FuncType",
    "DictAttrs": "ir.DictAttrs",
    "Range": "ir.Range",
    "SourceMap": "ir.SourceMap",
    "SourceName": "ir.SourceName",
    "Span": "ir.Span",
    "tir.Block": "tir.SBlock",
    "tir.BlockRealize": "tir.SBlockRealize",
}


def map_legacy_type_name(type_key: str) -> str:
    return LEGACY_TYPE_NAME_MAP.get(type_key, type_key)


def normalize_legacy_workload_graph(
    legacy_graph: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    legacy_nodes = legacy_graph.get("nodes", [])
    normalized_nodes: list[dict[str, Any]] = []
    extra_nodes: list[dict[str, Any]] = []

    def alloc_string_node(value: str) -> int:
        index = len(legacy_nodes) + len(extra_nodes)
        extra_nodes.append({"type": "ffi.String", "data": value})
        return index

    for node in legacy_nodes:
        old_type = str(node.get("type_key", ""))
        new_type = map_legacy_type_name(old_type)
        normalized: dict[str, Any] = {"type": new_type}

        if "repr_str" in node:
            normalized["data"] = node["repr_str"]
            normalized_nodes.append(normalized)
            continue

        if "attrs" in node:
            data = {
                key: normalize_numeric_string(value)
                for key, value in node["attrs"].items()
            }
            if old_type == "tir.PrimFunc":
                checked_type = data.pop("_checked_type_", None)
                if isinstance(checked_type, int):
                    data["struct_info_"] = checked_type
                else:
                    data["struct_info_"] = 0
                    warnings.append(
                        "legacy tir.PrimFunc lacked a reusable _checked_type_ reference; "
                        "struct_info_ defaulted to None"
                    )
            elif old_type == "GlobalVar":
                data.pop("_checked_type_", None)
            elif old_type in {"tir.Block", "tir.BlockRealize", "PrimType", "PointerType"}:
                data.setdefault("span", 0)
            elif old_type == "tir.For":
                data.setdefault("step", 1)
            elif old_type == "tir.IterVar":
                data.pop("span", None)
            elif old_type == "Range":
                data.setdefault("span", 0)
            normalized["data"] = data
            normalized_nodes.append(normalized)
            continue

        if "data" in node or "keys" in node:
            if "keys" in node:
                data: list[Any] = []
                values = [normalize_numeric_string(value) for value in node.get("data", [])]
                keys = node.get("keys", [])
                for idx, key in enumerate(keys):
                    data.extend([alloc_string_node(str(key)), values[idx]])
                if len(values) > len(keys):
                    data.extend(values[len(keys) :])
            else:
                raw_data = node.get("data", [])
                if isinstance(raw_data, list):
                    data = [normalize_numeric_string(value) for value in raw_data]
                elif isinstance(raw_data, dict):
                    data = {
                        key: normalize_numeric_string(value)
                        for key, value in raw_data.items()
                    }
                else:
                    data = normalize_numeric_string(raw_data)
            normalized["data"] = data
            normalized_nodes.append(normalized)
            continue

        if old_type == "Array":
            normalized["data"] = []
        normalized_nodes.append(normalized)

    normalized_nodes.extend(extra_nodes)
    normalized_graph = {
        "root_index": int(legacy_graph["root"]),
        "nodes": normalized_nodes,
        "metadata": legacy_graph.get("attrs", {}),
    }
    return normalized_graph, warnings


TRACE_REWRITE_RULES = {
    "GetBlock": "GetSBlock",
}


def normalize_trace_json(trace_json: Any) -> tuple[Any, dict[str, int]]:
    if not isinstance(trace_json, list) or len(trace_json) != 2:
        return trace_json, {}
    insts = trace_json[0]
    decisions = trace_json[1]
    if not isinstance(insts, list):
        return trace_json, {}
    rewrites: dict[str, int] = {}
    new_insts: list[Any] = []
    for entry in insts:
        if not isinstance(entry, list) or not entry:
            new_insts.append(entry)
            continue
        new_entry = list(entry)
        name = new_entry[0]
        if isinstance(name, str) and name in TRACE_REWRITE_RULES:
            new_name = TRACE_REWRITE_RULES[name]
            rewrites[name] = rewrites.get(name, 0) + 1
            new_entry[0] = new_name
        new_insts.append(new_entry)
    return [new_insts, decisions], rewrites


def load_ms_runtime():
    try:
        from tvm.s_tir import meta_schedule as ms
        from tvm.s_tir.schedule import InstructionKind
    except Exception as err:  # pragma: no cover - environment failure
        raise RuntimeError(f"unable to import current-safe TVM runtime: {err}") from err
    return ms, InstructionKind


def attempt_workload_parse(ms: Any, workload_row: Any) -> tuple[bool, str | None]:
    try:
        ms.database.Workload.from_json(workload_row)
        return True, None
    except Exception as err:
        return False, f"{type(err).__name__}: {err}"


def attempt_record_parse(
    ms: Any,
    record_row: Any,
    workloads: list[Any | None],
) -> tuple[bool, str | None]:
    try:
        if not isinstance(record_row, list) or len(record_row) != 2:
            raise ValueError(f"unexpected tuning record row format: {record_row!r}")
        workload_index = int(record_row[0])
        workload = workloads[workload_index]
        if workload is None:
            raise ValueError(f"workload index {workload_index} is not parseable")
        ms.database.TuningRecord.from_json(record_row[1], workload)
        return True, None
    except Exception as err:
        return False, f"{type(err).__name__}: {err}"


def format_error_counts(errors: list[str]) -> dict[str, Any]:
    if not errors:
        return {
            "success": True,
            "count": 0,
            "first_error": None,
        }
    return {
        "success": False,
        "count": len(errors),
        "first_error": errors[0],
    }


def write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    direct = summary["direct_probe"]
    normalized = summary["normalized_probe"]
    trace_ops = summary["trace_ops"]
    candidate = summary["candidate_db"]
    path.write_text(
        "\n".join(
            [
                "# Legacy baseline DB bridge probe",
                "",
                f"- report_id: {summary['report_id']}",
                f"- source_db: {summary['source_db']}",
                f"- workload_rows: {summary['workload_rows']}",
                f"- tuning_record_rows: {summary['tuning_record_rows']}",
                f"- workload_graph_formats: {json.dumps(summary['workload_graph_formats'], ensure_ascii=False)}",
                "",
                "## Direct current-safe probe",
                "",
                f"- workload_parse: {json.dumps(direct['workloads'], ensure_ascii=False)}",
                f"- tuning_record_parse: {json.dumps(direct['tuning_records'], ensure_ascii=False)}",
                "",
                "## Normalization probe",
                "",
                f"- workload_parse: {json.dumps(normalized['workloads'], ensure_ascii=False)}",
                f"- tuning_record_parse: {json.dumps(normalized['tuning_records'], ensure_ascii=False)}",
                f"- workload_warnings: {json.dumps(normalized['workload_warnings'], ensure_ascii=False)}",
                "",
                "## Trace ops",
                "",
                f"- unsupported_ops: {json.dumps(trace_ops['unsupported_ops'], ensure_ascii=False)}",
                f"- rewrite_counts: {json.dumps(trace_ops['rewrite_counts'], ensure_ascii=False)}",
                "",
                "## Candidate DB",
                "",
                f"- parse_validated: {candidate['parse_validated']}",
                f"- candidate_dir: {candidate['candidate_dir']}",
                "",
                "## Remaining blocker",
                "",
                f"- {summary['remaining_blocker']}",
                "",
                "## Next command",
                "",
                f"- `{summary['next_operator_command']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def probe_db(source_db: Path, report_id: str, output_root: Path) -> dict[str, Any]:
    ms, instruction_kind = load_ms_runtime()

    workload_rows = read_json_lines(source_db / "database_workload.json")
    tuning_rows = read_json_lines(source_db / "database_tuning_record.json")

    workload_graph_formats: dict[str, int] = {}
    normalized_workload_rows: list[Any] = []
    normalized_workload_graphs: list[Any] = []
    workload_normalization_warnings: list[str] = []
    direct_workload_errors: list[str] = []
    normalized_workload_errors: list[str] = []

    parsed_direct_workloads: list[Any | None] = []
    parsed_normalized_workloads: list[Any | None] = []

    for workload_row in workload_rows:
        direct_ok, direct_error = attempt_workload_parse(ms, workload_row)
        if direct_ok:
            parsed_direct_workloads.append(ms.database.Workload.from_json(workload_row))
        else:
            parsed_direct_workloads.append(None)
            direct_workload_errors.append(direct_error or "unknown workload parse failure")

        graph = decode_streamed_json_payload(workload_row[1])
        graph_format = classify_workload_graph(graph)
        workload_graph_formats[graph_format] = workload_graph_formats.get(graph_format, 0) + 1

        if graph_format == "legacy_root_object_graph":
            normalized_graph, warnings = normalize_legacy_workload_graph(graph)
            workload_normalization_warnings.extend(warnings)
            normalized_workload_rows.append([workload_row[0], encode_streamed_json_payload(normalized_graph)])
            normalized_workload_graphs.append(normalized_graph)
        else:
            normalized_workload_rows.append(workload_row)
            normalized_workload_graphs.append(graph)

    for workload_row in normalized_workload_rows:
        try:
            parsed_normalized_workloads.append(ms.database.Workload.from_json(workload_row))
        except Exception as err:
            parsed_normalized_workloads.append(None)
            normalized_workload_errors.append(f"{type(err).__name__}: {err}")

    direct_record_errors: list[str] = []
    normalized_record_errors: list[str] = []
    trace_op_counts: dict[str, int] = {}
    unsupported_ops: dict[str, int] = {}
    rewrite_counts: dict[str, int] = {}
    normalized_tuning_rows: list[Any] = []

    for record_row in tuning_rows:
        ok, error = attempt_record_parse(ms, record_row, parsed_direct_workloads)
        if not ok:
            direct_record_errors.append(error or "unknown tuning record parse failure")

        trace_json = record_row[1][0] if isinstance(record_row, list) and len(record_row) == 2 else None
        if isinstance(trace_json, list) and len(trace_json) == 2 and isinstance(trace_json[0], list):
            for inst in trace_json[0]:
                if isinstance(inst, list) and inst and isinstance(inst[0], str):
                    name = inst[0]
                    trace_op_counts[name] = trace_op_counts.get(name, 0) + 1
                    try:
                        instruction_kind.get(name)
                    except Exception:
                        unsupported_ops[name] = unsupported_ops.get(name, 0) + 1

        normalized_trace, rewrites = normalize_trace_json(trace_json)
        for name, count in rewrites.items():
            rewrite_counts[name] = rewrite_counts.get(name, 0) + count
        normalized_row = [record_row[0], [normalized_trace, record_row[1][1], record_row[1][2], record_row[1][3]]]
        normalized_tuning_rows.append(normalized_row)

    for record_row in normalized_tuning_rows:
        ok, error = attempt_record_parse(ms, record_row, parsed_normalized_workloads)
        if not ok:
            normalized_record_errors.append(error or "unknown normalized tuning record parse failure")

    attempted_db_dir = output_root / "attempted_current_safe_candidate"
    write_jsonl(attempted_db_dir / "database_workload.json", normalized_workload_rows)
    write_jsonl(attempted_db_dir / "database_tuning_record.json", normalized_tuning_rows)

    candidate_db_dir: str | None = None
    parse_validated = not normalized_workload_errors and not normalized_record_errors
    if parse_validated:
        candidate_db_dir = str(attempted_db_dir)

    remaining_blocker = (
        "none"
        if parse_validated
        else (
            normalized_workload_errors[0]
            if normalized_workload_errors
            else normalized_record_errors[0]
        )
    )

    if parse_validated:
        next_operator_command = (
            f"/home/tianxing/.venvs/tvm-ms/bin/python "
            f"{PROJECT_ROOT / 'session_bootstrap' / 'scripts' / 'build_baseline_export_bridge.py'} "
            f"--source-db {attempted_db_dir}"
        )
    else:
        next_operator_command = (
            f"/home/tianxing/.venvs/tvm-ms/bin/python "
            f"{PROJECT_ROOT / 'session_bootstrap' / 'scripts' / 'probe_legacy_baseline_db_bridge.py'} "
            f"--source-db {source_db}"
        )

    return {
        "report_id": report_id,
        "source_db": str(source_db),
        "workload_rows": len(workload_rows),
        "tuning_record_rows": len(tuning_rows),
        "workload_graph_formats": workload_graph_formats,
        "direct_probe": {
            "workloads": format_error_counts(direct_workload_errors),
            "tuning_records": format_error_counts(direct_record_errors),
        },
        "normalized_probe": {
            "workloads": format_error_counts(normalized_workload_errors),
            "tuning_records": format_error_counts(normalized_record_errors),
            "workload_warnings": workload_normalization_warnings,
        },
        "trace_ops": {
            "counts": trace_op_counts,
            "unsupported_ops": unsupported_ops,
            "rewrite_counts": rewrite_counts,
        },
        "attempted_candidate": {
            "database_workload_json": str(attempted_db_dir / "database_workload.json"),
            "database_tuning_record_json": str(attempted_db_dir / "database_tuning_record.json"),
        },
        "candidate_db": {
            "parse_validated": parse_validated,
            "candidate_dir": candidate_db_dir,
        },
        "remaining_blocker": remaining_blocker,
        "next_operator_command": next_operator_command,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_db = require_db_dir(args.source_db)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    report_id = args.report_id or f"{DEFAULT_REPORT_PREFIX}_{stamp}"
    output_root = args.output_dir or (PROJECT_ROOT / "session_bootstrap" / "tmp" / report_id)
    output_root.mkdir(parents=True, exist_ok=True)

    summary = probe_db(source_db, report_id, output_root)

    report_json = PROJECT_ROOT / "session_bootstrap" / "reports" / f"{report_id}.json"
    report_md = PROJECT_ROOT / "session_bootstrap" / "reports" / f"{report_id}.md"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown_summary(report_md, summary)

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
