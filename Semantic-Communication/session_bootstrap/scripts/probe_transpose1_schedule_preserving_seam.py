#!/usr/bin/env python3
"""Probe a schedule-preserving handwritten evaluation seam from local artifacts.

This helper is intentionally local-only. It does not claim performance validity.
It answers a narrower contract question:

- can the best scheduled task for a chosen operator be recovered from the
  staged MetaSchedule database?
- after MetaScheduleApplyDatabase, does the full module still expose a
  scheduled PrimFunc for that operator that could become a post-database
  handwritten hook seam?
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from relax_ms_utils import load_onnx_to_relax, summarize_task_stages

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPERATOR = "fused_conv2d_transpose1_add9"
DEFAULT_CANDIDATE_IMPL = (
    Path(__file__).resolve().parents[1]
    / "handwritten"
    / DEFAULT_OPERATOR
    / f"{DEFAULT_OPERATOR}_manual_candidate.py"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe whether a local tune output exposes a schedule-preserving "
            "handwritten seam for a specific operator."
        )
    )
    parser.add_argument(
        "--task-summary",
        type=Path,
        required=True,
        help="Path to task_summary.json from a staged tune output.",
    )
    parser.add_argument(
        "--database-dir",
        type=Path,
        required=True,
        help="Directory containing database_workload.json and database_tuning_record.json.",
    )
    parser.add_argument(
        "--operator",
        default=DEFAULT_OPERATOR,
        help=f"Operator/task name to probe. Default: {DEFAULT_OPERATOR}",
    )
    parser.add_argument(
        "--build-standalone-scheduled-task",
        action="store_true",
        help=(
            "Also attempt a local tvm.build() of the scheduled per-task IRModule. "
            "This is a structural build probe only, not a benchmark."
        ),
    )
    parser.add_argument(
        "--candidate-impl",
        type=Path,
        default=DEFAULT_CANDIDATE_IMPL,
        help=(
            "Checked-in handwritten candidate entrypoint module. Defaults to the "
            "repo-native transpose1 manual candidate."
        ),
    )
    parser.add_argument(
        "--skip-handwritten-candidate",
        action="store_true",
        help=(
            "Skip loading a handwritten candidate module. Use this when only the "
            "DB recovery / scheduled seed path is needed."
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output path for the probe JSON report.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Optional local-only output directory for the swapped full-module "
            "build/export artifact plus an adjacent JSON report."
        ),
    )
    parser.add_argument(
        "--scheduled-seed-dir",
        type=Path,
        help=(
            "Optional output directory for a post-db scheduled reference seed "
            "TIR + manifest handoff."
        ),
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def require_dir(path: Path, label: str) -> Path:
    if not path.is_dir():
        raise SystemExit(f"ERROR: {label} not found: {path}")
    return path


def require_database_dir(path: Path) -> Path:
    directory = require_dir(path, "database dir")
    require_file(directory / "database_workload.json", "database workload")
    require_file(directory / "database_tuning_record.json", "database tuning record")
    return directory


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_native(path: Path | str) -> str:
    value = Path(path)
    resolved = value if value.is_absolute() else (PROJECT_ROOT / value).resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return str(resolved)
    return f"./{relative.as_posix()}"


def parse_input_shape(raw_value: str) -> list[int]:
    dims = [item.strip() for item in str(raw_value).split(",") if item.strip()]
    if not dims:
        raise SystemExit(f"ERROR: invalid input_shape: {raw_value!r}")
    try:
        return [int(item) for item in dims]
    except ValueError as err:
        raise SystemExit(f"ERROR: invalid input_shape: {raw_value!r}") from err


def load_task_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(require_file(path, "task summary").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"ERROR: unexpected task summary payload in {path}")
    return payload


def load_python_module(module_path: Path):
    module_name = f"transpose1_probe_{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def lookup_global_func(mod: Any, name: str):
    if mod is None or not name:
        return None

    get_global_var = getattr(mod, "get_global_var", None)
    if callable(get_global_var):
        try:
            global_var = get_global_var(name)
        except Exception:
            global_var = None
        else:
            try:
                return mod[global_var]
            except Exception:
                pass

    try:
        return mod[name]
    except Exception:
        pass

    functions = getattr(mod, "functions", None)
    if functions is not None:
        try:
            items = list(functions.items())
        except Exception:
            items = []
        for key, value in items:
            if getattr(key, "name_hint", None) == name or str(key) == name:
                return value

    get_global_vars = getattr(mod, "get_global_vars", None)
    if callable(get_global_vars):
        try:
            global_vars = list(get_global_vars())
        except Exception:
            global_vars = []
        for key in global_vars:
            if getattr(key, "name_hint", None) == name or str(key) == name:
                try:
                    return mod[key]
                except Exception:
                    return None

    return getattr(mod, name, None)


def align_global_symbol(func: Any, target_name: str):
    with_attr = getattr(func, "with_attr", None)
    if not callable(with_attr):
        return func
    try:
        return with_attr("global_symbol", target_name)
    except Exception:
        return func


def replace_global_func(mod: Any, target_name: str, new_func: Any):
    get_global_var = getattr(mod, "get_global_var", None)
    if callable(get_global_var):
        try:
            target_key = get_global_var(target_name)
        except Exception:
            target_key = target_name
    else:
        target_key = target_name

    new_func = align_global_symbol(new_func, target_name)

    update_func = getattr(mod, "update_func", None)
    if callable(update_func):
        updated = update_func(target_key, new_func)
        return mod if updated is None else updated

    replace_global_func_method = getattr(mod, "replace_global_func", None)
    if callable(replace_global_func_method):
        updated = replace_global_func_method(target_key, new_func)
        return mod if updated is None else updated

    set_item = getattr(mod, "__setitem__", None)
    if callable(set_item):
        set_item(target_key, new_func)
        return mod

    raise TypeError(
        "IRModule override target does not support update_func, replace_global_func, or __setitem__"
    )


def load_candidate_override(candidate_impl: Path, task_stages: dict[str, Any]) -> dict[str, Any]:
    module = load_python_module(candidate_impl)
    build_manual_impl = getattr(module, "build_manual_impl", None)
    describe_placeholder = getattr(module, "describe_placeholder", None)
    if build_manual_impl is None or not callable(build_manual_impl):
        raise AttributeError(f"build_manual_impl missing in {candidate_impl}")
    if describe_placeholder is None or not callable(describe_placeholder):
        raise AttributeError(f"describe_placeholder missing in {candidate_impl}")

    metadata = describe_placeholder()
    result = build_manual_impl({"phase": "scheduled_task_compare", "task_stages": task_stages})
    override = result.get("override") if isinstance(result, dict) else None
    if not isinstance(override, dict):
        raise TypeError("build_manual_impl must return a dict with an override payload")

    source_path = Path(str(override.get("source_path") or "")).resolve()
    source_module = load_python_module(source_path)
    source_owner = source_module
    source_module_attr = str(override.get("source_module_attr") or "").strip() or None
    if source_module_attr is not None:
        source_owner = getattr(source_module, source_module_attr, None)
        if source_owner is None:
            raise AttributeError(
                f"source_module_attr missing in candidate source: {source_module_attr}"
            )
    source_func_name = str(override.get("source_func_name") or "main").strip() or "main"
    source_func = lookup_global_func(source_owner, source_func_name)
    if source_func is None:
        raise AttributeError(
            f"source_func_name missing in candidate source: {source_func_name}"
        )

    return {
        "module": module,
        "metadata": metadata,
        "result": result,
        "override": override,
        "source_path": source_path,
        "source_owner": source_owner,
        "source_func_name": source_func_name,
        "source_func": source_func,
    }


def find_stage_task_row(task_summary: dict[str, Any], operator: str) -> dict[str, Any] | None:
    stages = task_summary.get("stages")
    if not isinstance(stages, dict):
        return None

    for stage_name, stage_payload in stages.items():
        if not isinstance(stage_payload, dict):
            continue
        tasks = stage_payload.get("tasks")
        if not isinstance(tasks, list):
            continue
        for row in tasks:
            if not isinstance(row, dict):
                continue
            if row.get("task_name") == operator:
                result = dict(row)
                result["stage_name"] = stage_name
                return result
    return None


def _as_float_list(values: Any) -> list[float] | None:
    if values is None:
        return None
    if not isinstance(values, (list, tuple)):
        return None
    result: list[float] = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            return None
    return result


def build_output_layout(operator: str, output_dir: Path | None) -> dict[str, str | None]:
    if output_dir is None:
        return {
            "output_dir": None,
            "artifact_path": None,
            "report_path": None,
        }

    resolved_output_dir = output_dir.resolve()
    return {
        "output_dir": str(resolved_output_dir),
        "artifact_path": str(resolved_output_dir / f"{operator}_post_db_swap.so"),
        "report_path": str(resolved_output_dir / f"{operator}_post_db_swap_report.json"),
    }


def build_post_db_scheduled_seed_layout(
    operator: str,
    output_dir: Path | None,
) -> dict[str, str | None]:
    if output_dir is None:
        return {
            "output_dir": None,
            "reference_tir_path": None,
            "manifest_path": None,
        }

    resolved_output_dir = output_dir.resolve()
    return {
        "output_dir": str(resolved_output_dir),
        "reference_tir_path": str(
            resolved_output_dir / f"{operator}_post_db_scheduled_reference_seed_tir.py"
        ),
        "manifest_path": str(
            resolved_output_dir / "post_db_scheduled_reference_seed_manifest.json"
        ),
    }


def normalize_tvm_script_text(script_text: str) -> str:
    normalized = script_text.replace(
        "# from tvm.script import ir as I\n# from tvm.script import tir as T\n",
        "from tvm.script import ir as I\nfrom tvm.script import tir as T\n",
        1,
    ).strip()
    if not normalized:
        raise ValueError("rendered empty TVM script")
    return normalized + "\n"


def render_tvm_script(obj: Any) -> str:
    script_method = getattr(obj, "script", None)
    if not callable(script_method):
        raise TypeError(f"object of type {type(obj).__name__} does not expose script()")

    for kwargs in ({}, {"show_meta": False}):
        try:
            rendered = script_method(**kwargs)
        except TypeError:
            continue
        return normalize_tvm_script_text(str(rendered))

    rendered = script_method()
    return normalize_tvm_script_text(str(rendered))


def render_post_db_scheduled_reference_seed_tir(
    *,
    operator: str,
    task_summary_path: Path,
    database_dir: Path,
    raw_precompile_seed_path: Path | None,
    scheduled_reference_script: str,
) -> str:
    header = [
        f"# Schedule-preserving reference/edit seed for {operator}.",
        "#",
        "# Source:",
        "# - recovered from the post-database full-module path via MetaScheduleApplyDatabase",
        f"# - source operator global: {operator}",
        f"# - source task summary: {repo_native(task_summary_path)}",
        f"# - source database dir: {repo_native(database_dir)}",
    ]
    if raw_precompile_seed_path is not None:
        header.append(
            f"# - distinct from the older raw pre-compile seed: {repo_native(raw_precompile_seed_path)}"
        )
    header.extend(
        [
            "#",
            "# Contract:",
            "# - local-only diagnostic reference/edit seed",
            "# - preserve the scheduled form as recovered from the post-db path",
            "# - no runtime or performance claims attach to this file by itself",
            "",
        ]
    )
    return "\n".join(header) + normalize_tvm_script_text(scheduled_reference_script)


def build_post_db_scheduled_seed_manifest(
    *,
    operator: str,
    task_summary_path: Path,
    database_dir: Path,
    reference_tir_path: Path,
    raw_precompile_seed_path: Path | None,
    raw_precompile_manifest_path: Path | None,
    task_summary_row: dict[str, Any] | None,
    reconstructed_task_row: dict[str, Any] | None,
    post_db_operator_tir_is_scheduled: bool,
    structural_equal_to_database_query_ir_module_main: bool | None,
) -> dict[str, Any]:
    related_files: dict[str, str] = {
        "scheduled_reference_tir": repo_native(reference_tir_path),
    }
    if raw_precompile_seed_path is not None:
        related_files["raw_precompile_edit_seed_tir"] = repo_native(raw_precompile_seed_path)
    if raw_precompile_manifest_path is not None:
        related_files["raw_precompile_seed_manifest"] = repo_native(raw_precompile_manifest_path)

    return {
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "operator": operator,
        "phase": "post_db_meta_schedule_apply",
        "seed_capture_kind": "post_db_schedule_preserving_reference_seed",
        "seed_contract": {
            "path_kind": "diagnostic_post_db_scheduled_reference_seed",
            "local_only": True,
            "diagnostic_only": True,
            "performance_claims": False,
            "comparison_semantics": "reference_edit_seed_only",
        },
        "source": {
            "task_summary_json": repo_native(task_summary_path),
            "database_dir": repo_native(database_dir),
            "operator_global_var": operator,
            "post_db_operator_tir_is_scheduled": post_db_operator_tir_is_scheduled,
            "structural_equal_to_database_query_ir_module_main": (
                structural_equal_to_database_query_ir_module_main
            ),
            "source_seam_id": "post_database_scheduled_primfunc_swap",
        },
        "task_rows": {
            "task_summary_row": task_summary_row,
            "reconstructed_task_row": reconstructed_task_row,
        },
        "related_files": related_files,
        "notes": [
            "This manifest tracks the schedule-preserving reference/edit seed recovered from the post-db full-module path.",
            "Keep this distinct from the older raw pre-compile seed when preparing the next handwritten candidate.",
            "This handoff is local-only and diagnostic-only; it does not make performance claims.",
        ],
    }


def write_post_db_scheduled_seed_outputs(
    *,
    operator: str,
    output_dir: Path,
    task_summary_path: Path,
    database_dir: Path,
    scheduled_reference_script: str,
    task_summary_row: dict[str, Any] | None,
    reconstructed_task_row: dict[str, Any] | None,
    post_db_operator_tir_is_scheduled: bool,
    structural_equal_to_database_query_ir_module_main: bool | None,
) -> dict[str, Any]:
    layout = build_post_db_scheduled_seed_layout(operator, output_dir)
    reference_tir_path = Path(str(layout["reference_tir_path"]))
    manifest_path = Path(str(layout["manifest_path"]))
    raw_precompile_seed_path = output_dir.resolve() / f"{operator}_editable_seed_tir.py"
    if not raw_precompile_seed_path.is_file():
        raw_precompile_seed_path = None
    raw_precompile_manifest_path = output_dir.resolve() / "seed_manifest.json"
    if not raw_precompile_manifest_path.is_file():
        raw_precompile_manifest_path = None

    reference_tir_text = render_post_db_scheduled_reference_seed_tir(
        operator=operator,
        task_summary_path=task_summary_path,
        database_dir=database_dir,
        raw_precompile_seed_path=raw_precompile_seed_path,
        scheduled_reference_script=scheduled_reference_script,
    )
    manifest = build_post_db_scheduled_seed_manifest(
        operator=operator,
        task_summary_path=task_summary_path,
        database_dir=database_dir,
        reference_tir_path=reference_tir_path,
        raw_precompile_seed_path=raw_precompile_seed_path,
        raw_precompile_manifest_path=raw_precompile_manifest_path,
        task_summary_row=task_summary_row,
        reconstructed_task_row=reconstructed_task_row,
        post_db_operator_tir_is_scheduled=post_db_operator_tir_is_scheduled,
        structural_equal_to_database_query_ir_module_main=(
            structural_equal_to_database_query_ir_module_main
        ),
    )

    reference_tir_path.parent.mkdir(parents=True, exist_ok=True)
    reference_tir_path.write_text(reference_tir_text, encoding="utf-8")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "requested": True,
        "status": "written",
        "output_dir": str(output_dir.resolve()),
        "reference_tir_path": str(reference_tir_path),
        "reference_tir_sha256": file_sha256(reference_tir_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "post_db_operator_tir_is_scheduled": post_db_operator_tir_is_scheduled,
        "structural_equal_to_database_query_ir_module_main": (
            structural_equal_to_database_query_ir_module_main
        ),
        "raw_precompile_seed_path": (
            None if raw_precompile_seed_path is None else str(raw_precompile_seed_path)
        ),
        "raw_precompile_manifest_path": (
            None
            if raw_precompile_manifest_path is None
            else str(raw_precompile_manifest_path)
        ),
    }


def export_built_artifact(executable: Any, artifact_path: Path) -> dict[str, Any]:
    exporter_owner = "build_output"
    exporter = getattr(executable, "export_library", None)
    if not callable(exporter):
        runtime_mod = getattr(executable, "mod", None)
        exporter = getattr(runtime_mod, "export_library", None)
        exporter_owner = "build_output.mod"

    result = {
        "attempted": True,
        "status": "skipped",
        "error": None,
        "export_owner": None,
        "artifact_exists": False,
        "artifact_size_bytes": None,
        "artifact_sha256": None,
    }
    if not callable(exporter):
        result["status"] = "missing_export_library"
        return result

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        exporter(str(artifact_path))
    except Exception as err:  # pragma: no cover - integration-only path
        result["status"] = "failed"
        result["error"] = f"{type(err).__name__}: {err}"
        result["export_owner"] = exporter_owner
        return result

    artifact_exists = artifact_path.exists()
    result["status"] = "exported" if artifact_exists else "export_called_missing_artifact"
    result["export_owner"] = exporter_owner
    result["artifact_exists"] = artifact_exists
    if artifact_exists and artifact_path.is_file():
        result["artifact_size_bytes"] = artifact_path.stat().st_size
        result["artifact_sha256"] = file_sha256(artifact_path)
    return result


def write_report_outputs(
    payload: str,
    *,
    output_json: Path | None,
    adjacent_report_path: Path | None,
) -> None:
    seen_paths: set[str] = set()
    for path in (adjacent_report_path, output_json):
        if path is None:
            continue
        resolved = str(path.resolve())
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")


def probe_schedule_seam(
    task_summary_path: Path,
    database_dir: Path,
    operator: str,
    *,
    candidate_impl: Path | None,
    build_standalone_scheduled_task: bool,
    output_dir: Path | None = None,
    scheduled_seed_dir: Path | None = None,
) -> dict[str, Any]:
    import tvm  # pylint: disable=import-outside-toplevel
    from tvm.relax.transform import (  # pylint: disable=import-outside-toplevel
        MetaScheduleApplyDatabase,
    )
    from tvm.s_tir.meta_schedule.database import (  # pylint: disable=import-outside-toplevel
        JSONDatabase,
    )
    from tvm.s_tir.meta_schedule.relax_integration import (  # pylint: disable=import-outside-toplevel
        extract_tasks,
    )

    task_summary = load_task_summary(task_summary_path)
    database_dir = require_database_dir(database_dir)
    output_layout = build_output_layout(operator, output_dir)
    scheduled_seed_layout = build_post_db_scheduled_seed_layout(operator, scheduled_seed_dir)
    onnx_path = require_file(Path(task_summary["onnx_path"]), "onnx model")
    input_shape = parse_input_shape(task_summary["input_shape"])
    input_name = str(task_summary.get("input_name") or "input")
    input_dtype = str(task_summary.get("input_dtype") or "float32")
    target = tvm.target.Target(task_summary["target"])

    raw_mod = load_onnx_to_relax(
        onnx_path=str(onnx_path),
        input_name=input_name,
        input_shape=input_shape,
        input_dtype=input_dtype,
    )
    tuned_mod, task_stages = summarize_task_stages(raw_mod, target)
    extracted_tasks = list(extract_tasks(tuned_mod, target))
    extracted_task = next((task for task in extracted_tasks if task.task_name == operator), None)
    if extracted_task is None:
        raise SystemExit(
            "ERROR: operator is absent from extracted tuned tasks: "
            f"{operator}"
        )

    resolved_candidate_impl: Path | None = None
    candidate = None
    if candidate_impl is not None:
        resolved_candidate_impl = require_file(candidate_impl.resolve(), "candidate impl")
        candidate = load_candidate_override(resolved_candidate_impl, task_stages)

    db = JSONDatabase(
        str(database_dir / "database_workload.json"),
        str(database_dir / "database_tuning_record.json"),
    )

    scheduled_record = db.query_tuning_record(
        extracted_task.dispatched[0],
        target,
        extracted_task.task_name,
    )
    scheduled_ir_module = db.query_ir_module(
        extracted_task.dispatched[0],
        target,
        extracted_task.task_name,
    )
    scheduled_schedule = db.query_schedule(
        extracted_task.dispatched[0],
        target,
        extracted_task.task_name,
    )

    standalone_build = {
        "attempted": bool(build_standalone_scheduled_task),
        "status": "skipped",
        "error": None,
    }
    if build_standalone_scheduled_task:
        if scheduled_ir_module is None:
            standalone_build["status"] = "missing_scheduled_ir_module"
        else:
            try:
                tvm.build(scheduled_ir_module, target=target)
            except Exception as err:  # pragma: no cover - integration-only path
                standalone_build["status"] = "failed"
                standalone_build["error"] = f"{type(err).__name__}: {err}"
            else:
                standalone_build["status"] = "built"

    with target, db, tvm.transform.PassContext(opt_level=3):
        applied_mod = MetaScheduleApplyDatabase(enable_warning=False)(tuned_mod)

    applied_global_var_names = [gv.name_hint for gv in applied_mod.get_global_vars()]
    applied_operator_func: Any | None = None
    applied_operator_present = operator in applied_global_var_names
    if applied_operator_present:
        applied_operator_func = applied_mod[applied_mod.get_global_var(operator)]
    post_db_operator_tir_is_scheduled = bool(
        applied_operator_func is not None
        and applied_operator_func.attrs
        and applied_operator_func.attrs.get("tir.is_scheduled", False)
    )

    task_summary_row = find_stage_task_row(task_summary, operator)
    reconstructed_task_row = find_stage_task_row({"stages": task_stages}, operator)

    swapped_full_module = {
        "attempted": bool(
            applied_operator_present
            and candidate is not None
            and candidate["source_func"] is not None
        ),
        "swap_succeeded": False,
        "swap_target_global": operator if applied_operator_present else None,
        "post_swap_global_present": False,
        "post_swap_func_type": None,
        "structural_equal_post_swap_vs_candidate": None,
        "build_attempted": False,
        "build_status": "skipped",
        "build_error": None,
    }
    local_build_output = {
        "requested": output_dir is not None,
        "output_dir": output_layout["output_dir"],
        "artifact_path": output_layout["artifact_path"],
        "report_path": output_layout["report_path"],
        "build_executable_type": None,
        "export_attempted": False,
        "export_status": "skipped",
        "export_error": None,
        "export_owner": None,
        "artifact_exists": False,
        "artifact_size_bytes": None,
        "artifact_sha256": None,
    }
    post_db_scheduled_seed = {
        "requested": scheduled_seed_dir is not None,
        "status": "skipped",
        "error": None,
        "output_dir": scheduled_seed_layout["output_dir"],
        "reference_tir_path": scheduled_seed_layout["reference_tir_path"],
        "reference_tir_sha256": None,
        "manifest_path": scheduled_seed_layout["manifest_path"],
        "manifest_sha256": None,
        "raw_precompile_seed_path": None,
        "raw_precompile_manifest_path": None,
        "post_db_operator_tir_is_scheduled": post_db_operator_tir_is_scheduled,
        "structural_equal_to_database_query_ir_module_main": (
            None
            if applied_operator_func is None or scheduled_ir_module is None
            else bool(
                tvm.ir.structural_equal(
                    applied_operator_func,
                    lookup_global_func(scheduled_ir_module, "main"),
                )
            )
        ),
    }
    if scheduled_seed_dir is not None:
        if applied_operator_func is None:
            post_db_scheduled_seed["status"] = "missing_post_db_operator"
        else:
            try:
                scheduled_reference_module = tvm.IRModule(
                    {operator: align_global_symbol(applied_operator_func, operator)}
                )
                scheduled_reference_script = render_tvm_script(scheduled_reference_module)
                post_db_scheduled_seed = write_post_db_scheduled_seed_outputs(
                    operator=operator,
                    output_dir=scheduled_seed_dir,
                    task_summary_path=task_summary_path,
                    database_dir=database_dir,
                    scheduled_reference_script=scheduled_reference_script,
                    task_summary_row=task_summary_row,
                    reconstructed_task_row=reconstructed_task_row,
                    post_db_operator_tir_is_scheduled=post_db_operator_tir_is_scheduled,
                    structural_equal_to_database_query_ir_module_main=(
                        post_db_scheduled_seed[
                            "structural_equal_to_database_query_ir_module_main"
                        ]
                    ),
                )
            except Exception as err:  # pragma: no cover - integration-only path
                post_db_scheduled_seed["status"] = "failed"
                post_db_scheduled_seed["error"] = f"{type(err).__name__}: {err}"

    if swapped_full_module["attempted"] and candidate is not None:
        swapped_mod = replace_global_func(applied_mod, operator, candidate["source_func"])
        swapped_func = lookup_global_func(swapped_mod, operator)
        swapped_full_module["swap_succeeded"] = swapped_func is not None
        swapped_full_module["post_swap_global_present"] = operator in [
            gv.name_hint for gv in swapped_mod.get_global_vars()
        ]
        swapped_full_module["post_swap_func_type"] = (
            None if swapped_func is None else type(swapped_func).__name__
        )
        swapped_full_module["structural_equal_post_swap_vs_candidate"] = (
            None
            if swapped_func is None
            else bool(tvm.ir.structural_equal(swapped_func, candidate["source_func"]))
        )
        swapped_full_module["build_attempted"] = True
        try:
            from tvm import relax  # pylint: disable=import-outside-toplevel

            with target, tvm.transform.PassContext(opt_level=3):
                built_executable = relax.build(swapped_mod, target=target)
        except Exception as err:  # pragma: no cover - integration-only path
            swapped_full_module["build_status"] = "failed"
            swapped_full_module["build_error"] = f"{type(err).__name__}: {err}"
        else:
            swapped_full_module["build_status"] = "built"
            local_build_output["build_executable_type"] = type(built_executable).__name__
            if output_dir is not None and output_layout["artifact_path"] is not None:
                local_build_output["export_attempted"] = True
                export_result = export_built_artifact(
                    built_executable,
                    Path(output_layout["artifact_path"]),
                )
                local_build_output["export_status"] = str(export_result["status"])
                local_build_output["export_error"] = export_result["error"]
                local_build_output["export_owner"] = export_result["export_owner"]
                local_build_output["artifact_exists"] = bool(export_result["artifact_exists"])
                local_build_output["artifact_size_bytes"] = export_result["artifact_size_bytes"]
                local_build_output["artifact_sha256"] = export_result["artifact_sha256"]

    report = {
        "task_summary_json": str(task_summary_path.resolve()),
        "database_dir": str(database_dir.resolve()),
        "operator": operator,
        "task_summary_row": task_summary_row,
        "reconstructed_task_row": reconstructed_task_row,
        "extracted_task": {
            "task_name": extracted_task.task_name,
            "weight": int(extracted_task.weight),
            "dispatched_count": len(extracted_task.dispatched),
            "dispatched_global_vars": [
                gv.name_hint for gv in extracted_task.dispatched[0].get_global_vars()
            ],
            "dispatched_tir_is_scheduled": bool(
                extracted_task.dispatched[0].attrs
                and extracted_task.dispatched[0].attrs.get("tir.is_scheduled", False)
            ),
        },
        "database_lookup": {
            "query_tuning_record_hit": scheduled_record is not None,
            "query_ir_module_hit": scheduled_ir_module is not None,
            "query_schedule_hit": scheduled_schedule is not None,
            "scheduled_run_secs": None
            if scheduled_record is None
            else _as_float_list(scheduled_record.run_secs),
            "scheduled_tuning_record_trace_inst_count": None
            if scheduled_record is None
            else len(scheduled_record.trace.insts),
            "scheduled_trace_inst_count": None
            if scheduled_schedule is None
            else len(scheduled_schedule.trace.insts),
            "scheduled_ir_module_global_vars": None
            if scheduled_ir_module is None
            else [gv.name_hint for gv in scheduled_ir_module.get_global_vars()],
            "query_schedule_matches_query_ir_module": (
                None
                if scheduled_schedule is None or scheduled_ir_module is None
                else bool(tvm.ir.structural_equal(scheduled_schedule.mod, scheduled_ir_module))
            ),
        },
        "standalone_scheduled_task_build": standalone_build,
        "post_database_apply": {
            "operator_present": applied_operator_present,
            "operator_tir_is_scheduled": post_db_operator_tir_is_scheduled,
            "operator_func_type": None
            if applied_operator_func is None
            else type(applied_operator_func).__name__,
            "global_var_names_sample": applied_global_var_names[:40],
        },
        "post_db_scheduled_seed": post_db_scheduled_seed,
        "handwritten_candidate": {
            "candidate_requested": candidate is not None,
            "candidate_impl": None
            if resolved_candidate_impl is None
            else str(resolved_candidate_impl),
            "candidate_source_path": None
            if candidate is None
            else str(candidate["source_path"]),
            "metadata": None if candidate is None else candidate["metadata"],
            "result_evaluation_contract": None
            if candidate is None
            else candidate["result"].get("evaluation_contract"),
            "override_evaluation_contract": None
            if candidate is None
            else candidate["override"].get("evaluation_contract"),
            "override_target_global_vars": None
            if candidate is None
            else candidate["override"].get("target_global_vars"),
            "source_func_name": None
            if candidate is None
            else candidate["source_func_name"],
            "source_func_type": None
            if candidate is None
            else type(candidate["source_func"]).__name__,
            "source_owner_global_vars": None
            if candidate is None or not hasattr(candidate["source_owner"], "get_global_vars")
            else [gv.name_hint for gv in candidate["source_owner"].get_global_vars()],
        },
        "scheduled_vs_handwritten": {
            "candidate_source_matches_operator_name": None
            if candidate is None
            else bool(
                candidate["override"].get("target_global_vars")
                and operator in candidate["override"].get("target_global_vars")
            ),
            "scheduled_reference_available": scheduled_ir_module is not None,
            "handwritten_source_available": bool(
                candidate is not None and candidate["source_func"] is not None
            ),
            "scheduled_reference_func_type": None
            if scheduled_ir_module is None
            else type(lookup_global_func(scheduled_ir_module, "main")).__name__,
            "structural_equal_scheduled_ref_vs_handwritten": (
                None
                if scheduled_ir_module is None or candidate is None
                else bool(
                    tvm.ir.structural_equal(
                        lookup_global_func(scheduled_ir_module, "main"),
                        candidate["source_func"],
                    )
                )
            ),
            "scheduled_param_count": None
            if scheduled_ir_module is None
            else len(lookup_global_func(scheduled_ir_module, "main").params),
            "handwritten_param_count": None
            if candidate is None
            else len(candidate["source_func"].params),
            "mechanically_swappable_post_db": bool(
                applied_operator_present
                and candidate is not None
                and candidate["source_func"] is not None
            ),
        },
        "post_db_scheduled_swap": swapped_full_module,
        "local_build_output": local_build_output,
        "recommended_seam": {
            "seam_id": "post_database_scheduled_primfunc_swap",
            "why": (
                "Apply MetaScheduleApplyDatabase first, then expose/replace the "
                "named scheduled PrimFunc inside the applied module."
            ),
            "precondition": (
                "Handwritten candidates must be authored against the scheduled "
                "operator form or an explicitly derived scheduled editable seed, "
                "not the raw pre-compile seed."
            ),
        },
    }
    return report


def main() -> None:
    args = parse_args()
    report = probe_schedule_seam(
        task_summary_path=args.task_summary,
        database_dir=args.database_dir,
        operator=args.operator,
        candidate_impl=(
            None if args.skip_handwritten_candidate else args.candidate_impl
        ),
        build_standalone_scheduled_task=args.build_standalone_scheduled_task,
        output_dir=args.output_dir,
        scheduled_seed_dir=args.scheduled_seed_dir,
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    adjacent_report_path = None
    local_build_output = report.get("local_build_output")
    if isinstance(local_build_output, dict):
        report_path = local_build_output.get("report_path")
        if isinstance(report_path, str) and report_path.strip():
            adjacent_report_path = Path(report_path)
    write_report_outputs(
        payload,
        output_json=args.output_json,
        adjacent_report_path=adjacent_report_path,
    )
    print(payload)


if __name__ == "__main__":
    main()
