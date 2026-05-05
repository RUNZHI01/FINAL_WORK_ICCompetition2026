#!/usr/bin/env python3
"""RPC-based MetaSchedule tuning script.

Runs on the laptop (builder/orchestrator). Searches and compiles locally,
measures on a remote ARMv8 device via TVM RPC.

Usage:
    python rpc_tune.py \
        --onnx-path /path/to/model.onnx \
        --output-dir ./tune_output \
        --target 'llvm -mtriple=aarch64-linux-gnu -mcpu=generic -mattr=+neon' \
        --tracker-host 127.0.0.1 \
        --tracker-port 9190 \
        --device-key armv8 \
        --total-trials 500 \
        --input-shape 1,32,32,32

    Set --runner local to skip RPC and measure locally (for smoke testing).
"""

import argparse
import hashlib
import importlib.util
import inspect
import json
import logging
import os
import shutil
import sys
import time

from relax_ms_utils import (
    RAW_STAGE_NAME,
    TUNED_STAGE_NAME,
    load_onnx_to_relax as load_onnx_to_relax_module,
    summarize_task_stages,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rpc_tune")


def parse_args():
    p = argparse.ArgumentParser(description="RPC MetaSchedule tuning")
    p.add_argument("--onnx-path", required=True, help="Path to ONNX model")
    p.add_argument("--output-dir", required=True, help="Directory for tune artifacts")
    p.add_argument("--target", required=True, help="TVM target string")
    p.add_argument("--tracker-host", default="127.0.0.1")
    p.add_argument("--tracker-port", type=int, default=9190)
    p.add_argument("--device-key", default="armv8")
    p.add_argument("--total-trials", type=int, default=500)
    p.add_argument("--max-trials-per-task", type=int, default=None)
    p.add_argument("--num-trials-per-iter", type=int, default=64)
    p.add_argument(
        "--input-shape",
        required=True,
        help="Comma-separated input shape, e.g. 1,32,32,32",
    )
    p.add_argument("--input-name", default="input", help="ONNX input tensor name")
    p.add_argument("--input-dtype", default="float32")
    p.add_argument(
        "--op-names",
        default="",
        help="Optional comma-separated task names/substrings to tune",
    )
    p.add_argument(
        "--existing-db",
        default="",
        help="Path to existing tuning_logs dir for warm-start",
    )
    p.add_argument(
        "--runner",
        choices=["rpc", "local"],
        default="rpc",
        help="Runner type: rpc (real device) or local (smoke test)",
    )
    p.add_argument("--session-timeout", type=int, default=120)
    return p.parse_args()


def load_onnx_to_relax(onnx_path, input_name, input_shape, input_dtype):
    """Load ONNX model and convert to Relax IR."""
    logger.info("Loading ONNX model: %s", onnx_path)
    mod = load_onnx_to_relax_module(
        onnx_path=onnx_path,
        input_name=input_name,
        input_shape=list(input_shape),
        input_dtype=input_dtype,
    )
    logger.info("ONNX -> Relax IR conversion complete")
    return mod


def sanitize_tuning_records(work_dir):
    """Remove unsupported target feature keys from tuning records for compatibility."""
    record_path = os.path.join(work_dir, "database_tuning_record.json")
    if not os.path.isfile(record_path):
        return 0

    changed = 0
    out_lines = []
    with open(record_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                out_lines.append(raw.rstrip("\n"))
                continue

            target = None
            if (
                isinstance(rec, list)
                and len(rec) >= 2
                and isinstance(rec[1], list)
                and len(rec[1]) >= 3
                and isinstance(rec[1][2], dict)
            ):
                target = rec[1][2]

            if target is not None:
                keys = [k for k in list(target.keys()) if k.startswith("feature.")]
                if keys:
                    for k in keys:
                        target.pop(k, None)
                    changed += 1

            out_lines.append(json.dumps(rec, ensure_ascii=False))

    if changed > 0:
        with open(record_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")
        logger.info(
            "Sanitized tuning records: removed unsupported feature.* keys from %d record(s)",
            changed,
        )

    return changed


def prepare_warm_start(existing_db, work_dir):
    """Copy existing tuning database for warm-start."""
    if not existing_db or not os.path.isdir(existing_db):
        return

    for fname in ("database_workload.json", "database_tuning_record.json"):
        src = os.path.join(existing_db, fname)
        dst = os.path.join(work_dir, fname)
        if os.path.isfile(src) and not os.path.isfile(dst):
            shutil.copy2(src, dst)
            logger.info("Warm-start: copied %s -> %s", src, dst)

    sanitize_tuning_records(work_dir)


def build_rpc_runner(tracker_host, tracker_port, device_key, session_timeout):
    """Create an RPCRunner that measures on the remote device."""
    from tvm.s_tir.meta_schedule.runner import (  # pylint: disable=import-outside-toplevel
        RPCConfig,
        RPCRunner,
    )

    rpc_config = RPCConfig(
        tracker_host=tracker_host,
        tracker_port=tracker_port,
        tracker_key=device_key,
        session_timeout_sec=session_timeout,
    )
    runner = RPCRunner(rpc_config=rpc_config, max_workers=1)
    logger.info(
        "RPCRunner configured: %s:%d key=%s",
        tracker_host,
        tracker_port,
        device_key,
    )
    return runner


def parse_op_names(raw_value):
    return [item.strip() for item in str(raw_value).split(",") if item.strip()]


def _resolve_optional_path(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        return None
    return os.path.abspath(os.path.expanduser(value))


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "__fspath__"):
        return os.fspath(value)
    return repr(value)


def _load_python_module(module_path):
    module_name = "tvm_handwritten_impl_" + hashlib.sha256(
        module_path.encode("utf-8")
    ).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load handwritten module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _call_handwritten_callable(func, context, label):
    try:
        params = list(inspect.signature(func).parameters.values())
    except (TypeError, ValueError):
        return func(context)

    if not params:
        return func()
    if len(params) != 1:
        raise TypeError(
            f"{label} must accept zero arguments or a single context argument"
        )

    param = params[0]
    if param.kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        return func(context)
    if param.kind == inspect.Parameter.KEYWORD_ONLY:
        return func(**{param.name: context})
    if param.kind == inspect.Parameter.VAR_POSITIONAL:
        return func(context)
    if param.kind == inspect.Parameter.VAR_KEYWORD:
        return func(context=context)

    raise TypeError(
        f"{label} must accept zero arguments or a single context argument"
    )


def _task_stage_matches(task_stages, operator_name):
    if task_stages is None:
        return None

    matches = {}
    for stage_name, stage_payload in task_stages.items():
        tasks = stage_payload.get("tasks", [])
        matches[stage_name] = any(
            row.get("task_name") == operator_name for row in tasks
        )
    return matches


def _global_var_name(value):
    name_hint = getattr(value, "name_hint", None)
    if name_hint:
        return str(name_hint)
    return str(value)


def _lookup_global_func(mod, name):
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
            if _global_var_name(key) == name:
                return value

    get_global_vars = getattr(mod, "get_global_vars", None)
    if callable(get_global_vars):
        try:
            global_vars = list(get_global_vars())
        except Exception:
            global_vars = []
        for key in global_vars:
            if _global_var_name(key) == name:
                try:
                    return mod[key]
                except Exception:
                    return None

    return getattr(mod, name, None)


def _resolve_override_target_names(override, operator_name):
    raw_targets = override.get("target_global_vars")
    if raw_targets is None:
        raw_value = override.get("target_global_var")
        raw_targets = [] if raw_value is None else [raw_value]

    targets = []
    for raw_name in raw_targets:
        name = str(raw_name or "").strip()
        if name and name not in targets:
            targets.append(name)

    operator_name = str(operator_name or "").strip()
    if operator_name and operator_name not in targets:
        targets.append(operator_name)
    return targets


def _normalize_evaluation_contract(
    payload,
    operator_name,
    integration_phase,
    *,
    default_to_raw_pre_compile=False,
):
    contract = {}
    raw_contract = None
    if isinstance(payload, dict):
        raw_contract = payload.get("evaluation_contract")
        if raw_contract is not None and not isinstance(raw_contract, dict):
            raise TypeError("Handwritten evaluation_contract must be a dict when set")
        if isinstance(raw_contract, dict):
            contract.update(raw_contract)

    if raw_contract is None and not default_to_raw_pre_compile:
        return None

    path_kind = str(contract.get("path_kind", "")).strip()
    legacy_mode = str(contract.get("mode", "")).strip()
    if not path_kind:
        if legacy_mode:
            path_kind = legacy_mode
        elif default_to_raw_pre_compile and integration_phase == "pre_compile":
            path_kind = "diagnostic_raw_pre_compile_replacement"
        else:
            path_kind = f"raw_{integration_phase}_primfunc_replace"

    default_schedule_context_guarantee = "unspecified"
    default_performance_evaluable = None
    default_comparison_semantics = "unspecified"
    default_future_path_kind = None
    default_future_path_status = None
    default_reason = None
    if path_kind == "diagnostic_raw_pre_compile_replacement":
        default_schedule_context_guarantee = "not_guaranteed"
        default_performance_evaluable = False
        default_comparison_semantics = "non_comparable_diagnostic_only"
        default_future_path_kind = "schedule_context_preserving_evaluation"
        default_future_path_status = "not_implemented"
        default_reason = (
            "Raw pre-compile PrimFunc replacement can lose the best staging "
            "schedule context, so runtime numbers are diagnostic only."
        )

    schedule_context_guarantee = (
        str(
            contract.get(
                "schedule_context_guarantee",
                default_schedule_context_guarantee,
            )
            or default_schedule_context_guarantee
        ).strip()
        or default_schedule_context_guarantee
    )
    if "performance_evaluable" in contract:
        performance_evaluable = contract.get("performance_evaluable")
    else:
        performance_evaluable = default_performance_evaluable
    comparison_semantics = (
        str(contract.get("comparison_semantics", default_comparison_semantics)).strip()
        or default_comparison_semantics
    )
    future_path_kind = (
        str(contract.get("future_path_kind", default_future_path_kind or "")).strip()
        or default_future_path_kind
    )
    future_path_status = (
        str(
            contract.get(
                "future_path_status",
                default_future_path_status or "",
            )
        ).strip()
        or default_future_path_status
    )
    reason = str(contract.get("reason", default_reason or "")).strip() or default_reason
    intended_use = str(contract.get("intended_use", "")).strip()
    if not intended_use:
        intended_use = (
            "diagnostic_only"
            if comparison_semantics == "non_comparable_diagnostic_only"
            else "unspecified"
        )

    contract_summary = {
        "path_kind": path_kind,
        "mode": legacy_mode or path_kind,
        "operator": str(operator_name or "").strip() or None,
        "integration_phase": str(integration_phase or "").strip() or None,
        "schedule_context_guarantee": schedule_context_guarantee,
        "schedule_context_preserved": schedule_context_guarantee == "preserved",
        "performance_evaluable": performance_evaluable,
        "performance_comparable": bool(performance_evaluable),
        "comparison_semantics": comparison_semantics,
        "intended_use": intended_use,
        "future_path_kind": future_path_kind,
        "future_path_status": future_path_status,
        "reason": reason,
        "notes": _json_safe(contract.get("notes") or []),
    }
    return contract_summary


def _attach_evaluation_contract(report, evaluation_contract):
    if evaluation_contract is None:
        return
    report["evaluation_contract"] = evaluation_contract
    report["performance_evaluable"] = evaluation_contract.get(
        "performance_evaluable"
    )
    report["comparison_semantics"] = evaluation_contract.get(
        "comparison_semantics"
    )


def _align_override_global_symbol(func, target_name):
    with_attr = getattr(func, "with_attr", None)
    if not callable(with_attr):
        return func

    try:
        return with_attr("global_symbol", target_name)
    except Exception:
        return func


def _replace_global_func(mod, target_name, new_func):
    get_global_var = getattr(mod, "get_global_var", None)
    if callable(get_global_var):
        try:
            target_key = get_global_var(target_name)
        except Exception:
            target_key = target_name
    else:
        target_key = target_name

    new_func = _align_override_global_symbol(new_func, target_name)

    update_func = getattr(mod, "update_func", None)
    if callable(update_func):
        updated = update_func(target_key, new_func)
        return mod if updated is None else updated

    replace_global_func = getattr(mod, "replace_global_func", None)
    if callable(replace_global_func):
        updated = replace_global_func(target_key, new_func)
        return mod if updated is None else updated

    set_item = getattr(mod, "__setitem__", None)
    if callable(set_item):
        set_item(target_key, new_func)
        return mod

    raise TypeError(
        "IRModule override target does not support update_func, "
        "replace_global_func, or __setitem__"
    )


def _apply_handwritten_override(mod, operator_name, override):
    if not isinstance(override, dict):
        raise TypeError("Handwritten override payload must be a dict")

    kind = str(override.get("kind", "")).strip()
    if kind != "replace_prim_func_from_source":
        raise ValueError(f"Unsupported handwritten override kind: {kind!r}")

    source_path = _resolve_optional_path(override.get("source_path"))
    if source_path is None:
        raise ValueError("Handwritten override source_path must be set")
    if not os.path.isfile(source_path):
        raise FileNotFoundError(
            f"Handwritten override source_path does not exist: {source_path}"
        )

    source_module_attr = str(override.get("source_module_attr", "")).strip() or None
    source_func_name = str(override.get("source_func_name", "")).strip() or "main"
    source_module = _load_python_module(source_path)
    source_owner = source_module
    if source_module_attr is not None:
        source_owner = getattr(source_module, source_module_attr, None)
        if source_owner is None:
            raise AttributeError(
                "Handwritten override module attribute not found: "
                f"{source_module_attr}"
            )

    source_func = _lookup_global_func(source_owner, source_func_name)
    if source_func is None:
        raise AttributeError(
            "Handwritten override source func not found: "
            f"{source_func_name} in {source_path}"
        )

    target_names = _resolve_override_target_names(override, operator_name)
    if not target_names:
        raise ValueError("Handwritten override target_global_var is empty")

    resolved_target = None
    for candidate in target_names:
        if _lookup_global_func(mod, candidate) is not None:
            resolved_target = candidate
            break
    if resolved_target is None:
        raise ValueError(
            "Unable to find handwritten override target in compile module: %s"
            % ",".join(target_names)
        )

    updated_mod = _replace_global_func(mod, resolved_target, source_func)
    return updated_mod, {
        "kind": kind,
        "source_path": source_path,
        "source_module_attr": source_module_attr,
        "source_func_name": source_func_name,
        "target_global_var": resolved_target,
        "requested_target_global_vars": target_names,
        "candidate_version": override.get("candidate_version"),
        "staging_only": bool(override.get("staging_only")),
        "validation_scope": override.get("validation_scope"),
        "evaluation_contract": _normalize_evaluation_contract(
            override,
            operator_name=resolved_target or operator_name,
            integration_phase="pre_compile",
            default_to_raw_pre_compile=True,
        ),
    }


def resolve_handwritten_hook(mod, target, database, output_dir, task_stages=None):
    module_path = _resolve_optional_path(os.environ.get("TVM_HANDWRITTEN_IMPL_PATH"))
    if module_path is None:
        return mod, None

    operator_name = str(os.environ.get("TVM_HANDWRITTEN_OP", "")).strip()
    if not operator_name:
        raise ValueError(
            "TVM_HANDWRITTEN_OP must be set when TVM_HANDWRITTEN_IMPL_PATH is enabled"
        )
    if not os.path.isfile(module_path):
        raise FileNotFoundError(
            f"TVM_HANDWRITTEN_IMPL_PATH does not exist: {module_path}"
        )

    entrypoint_name = (
        str(os.environ.get("TVM_HANDWRITTEN_IMPL_ENTRYPOINT", "")).strip()
        or "build_manual_impl"
    )
    metadata_name = (
        str(os.environ.get("TVM_HANDWRITTEN_IMPL_METADATA_FN", "")).strip() or None
    )
    bookkeeping_json = _resolve_optional_path(
        os.environ.get("TVM_HANDWRITTEN_BOOKKEEPING_JSON")
    )
    task_stage_matches = _task_stage_matches(task_stages, operator_name)
    if task_stage_matches is not None and not any(task_stage_matches.values()):
        raise ValueError(
            "TVM_HANDWRITTEN_OP=%s is not present in the extracted task stages"
            % operator_name
        )

    report = {
        "enabled": True,
        "integration_phase": "pre_compile",
        "status": "pending",
        "operator": operator_name,
        "impl_path": module_path,
        "entrypoint": entrypoint_name,
        "metadata_fn": metadata_name,
        "bookkeeping_json": bookkeeping_json,
        "task_stage_matches": task_stage_matches,
        "manual_override_applied": False,
    }

    module = _load_python_module(module_path)
    effective_mod = mod
    call_context = {
        "phase": "pre_compile",
        "operator": operator_name,
        "module_path": module_path,
        "output_dir": output_dir,
        "target": target,
        "database": database,
        "mod": mod,
        "bookkeeping_json": bookkeeping_json,
        "task_stages": task_stages,
    }

    metadata = None
    if metadata_name is not None:
        metadata_fn = getattr(module, metadata_name, None)
        if metadata_fn is None or not callable(metadata_fn):
            raise AttributeError(
                f"Handwritten metadata function not found or not callable: {metadata_name}"
            )
        metadata = _call_handwritten_callable(
            metadata_fn, call_context, f"{module_path}:{metadata_name}"
        )
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError(
                f"Handwritten metadata function must return a dict or None: {metadata_name}"
            )

    report["metadata"] = _json_safe(metadata)
    _attach_evaluation_contract(
        report,
        _normalize_evaluation_contract(
            metadata,
            operator_name=operator_name,
            integration_phase=report["integration_phase"],
        ),
    )
    placeholder_only = bool(metadata and metadata.get("placeholder_only"))
    report["placeholder_only"] = placeholder_only

    metadata_operator = str(metadata.get("operator", "")).strip() if metadata else ""
    if metadata_operator:
        report["metadata_operator"] = metadata_operator
        if metadata_operator != operator_name:
            raise ValueError(
                "Handwritten metadata operator mismatch: env=%s metadata=%s"
                % (operator_name, metadata_operator)
            )

    entrypoint_fn = getattr(module, entrypoint_name, None)
    if entrypoint_fn is None or not callable(entrypoint_fn):
        raise AttributeError(
            f"Handwritten entrypoint not found or not callable: {entrypoint_name}"
        )

    try:
        result = _call_handwritten_callable(
            entrypoint_fn, call_context, f"{module_path}:{entrypoint_name}"
        )
        report["status"] = "entrypoint_completed"
        report["entrypoint_result"] = _json_safe(result)
        if isinstance(result, dict):
            _attach_evaluation_contract(
                report,
                _normalize_evaluation_contract(
                    result,
                    operator_name=operator_name,
                    integration_phase=report["integration_phase"],
                ),
            )
            override = result.get("override")
            if override is not None:
                effective_mod, applied_override = _apply_handwritten_override(
                    effective_mod,
                    operator_name,
                    override,
                )
                report["status"] = "manual_override_applied"
                report["manual_override_applied"] = True
                report["applied_override"] = _json_safe(applied_override)
                _attach_evaluation_contract(
                    report,
                    _json_safe(
                        applied_override.get("evaluation_contract")
                        or report.get("evaluation_contract")
                    ),
                )
                if report.get("performance_evaluable") is False:
                    report["status"] = "manual_override_applied_diagnostic_only"
            elif "manual_override_applied" in result:
                report["manual_override_applied"] = bool(
                    result["manual_override_applied"]
                )
    except NotImplementedError as err:
        if not placeholder_only:
            raise
        report["status"] = "placeholder_only"
        report["entrypoint_notice"] = str(err)

    logger.info(
        "Handwritten hook status=%s operator=%s impl=%s entrypoint=%s "
        "placeholder_only=%s comparison_semantics=%s performance_evaluable=%s",
        report["status"],
        operator_name,
        module_path,
        entrypoint_name,
        placeholder_only,
        report.get("comparison_semantics"),
        report.get("performance_evaluable"),
    )
    evaluation_contract = report.get("evaluation_contract") or {}
    if (
        report.get("manual_override_applied")
        and isinstance(evaluation_contract, dict)
        and report.get("performance_evaluable") is False
    ):
        logger.warning(
            "Handwritten override is diagnostic-only: path_kind=%s "
            "schedule_context_guarantee=%s comparison_semantics=%s",
            evaluation_contract.get("path_kind"),
            evaluation_contract.get("schedule_context_guarantee"),
            evaluation_contract.get("comparison_semantics"),
        )
    if bookkeeping_json is not None:
        logger.info("Handwritten bookkeeping json: %s", bookkeeping_json)
    return effective_mod, report


def maybe_apply_handwritten_hook(mod, target, database, output_dir, task_stages=None):
    _, report = resolve_handwritten_hook(
        mod=mod,
        target=target,
        database=database,
        output_dir=output_dir,
        task_stages=task_stages,
    )
    return report


def write_task_summary(output_dir, task_stages, args, handwritten_hook=None):
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "onnx_path": args.onnx_path,
        "target": args.target,
        "input_shape": args.input_shape,
        "task_stage_used_for_tuning": TUNED_STAGE_NAME,
        "raw_import_total_tasks": task_stages[RAW_STAGE_NAME]["total_tasks"],
        "tuned_stage_total_tasks": task_stages[TUNED_STAGE_NAME]["total_tasks"],
        "selected_op_names": parse_op_names(args.op_names),
        "stages": task_stages,
    }
    if handwritten_hook is not None:
        summary["handwritten_hook"] = handwritten_hook
    path = os.path.join(output_dir, "task_summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    logger.info("Task summary written: %s", path)
    return path


def log_task_stage_summary(task_stages):
    logger.info(
        "Task visibility: raw_import=%d tuned_stage=%d (stage=%s)",
        task_stages[RAW_STAGE_NAME]["total_tasks"],
        task_stages[TUNED_STAGE_NAME]["total_tasks"],
        TUNED_STAGE_NAME,
    )
    for row in task_stages[TUNED_STAGE_NAME]["tasks"][:10]:
        logger.info(
            "Tuned-stage task: rank=%d name=%s weight=%d prim_funcs=%s",
            row["rank"],
            row["task_name"],
            row["weight"],
            ",".join(row["prim_funcs"]) if row["prim_funcs"] else "-",
        )


def warn_on_task_filter(task_stages, op_names):
    if not op_names:
        return

    raw_names = {row["task_name"] for row in task_stages[RAW_STAGE_NAME]["tasks"]}
    tuned_names = {row["task_name"] for row in task_stages[TUNED_STAGE_NAME]["tasks"]}
    missing = [name for name in op_names if name not in tuned_names]
    if missing:
        logger.warning(
            "Selected op/task names are absent from the tuned stage: %s",
            ",".join(missing),
        )

    if all(name in raw_names for name in op_names) and task_stages[TUNED_STAGE_NAME]["total_tasks"] > len(raw_names):
        logger.warning(
            "Selected op/task filter matches only the raw-import stage (%s). "
            "Regenerate FULL_HOTSPOT_TASKS with extract_hotspot_tasks.py before the next real run.",
            ",".join(op_names),
        )


def run_tune(mod, target, work_dir, runner, args):
    """Run MetaSchedule tuning via tune_relax."""
    from tvm.s_tir.meta_schedule.relax_integration import (  # pylint: disable=import-outside-toplevel
        tune_relax,
    )

    op_names = parse_op_names(args.op_names)
    logger.info(
        "Starting tune_relax: total_trials=%d, work_dir=%s",
        args.total_trials,
        work_dir,
    )
    if op_names:
        logger.info("Selected op/task filter: %s", ",".join(op_names))
    t0 = time.time()
    db = tune_relax(
        mod=mod,
        params={},
        target=target,
        work_dir=work_dir,
        max_trials_global=args.total_trials,
        max_trials_per_task=args.max_trials_per_task,
        op_names=op_names or None,
        num_trials_per_iter=args.num_trials_per_iter,
        runner=runner,
    )
    elapsed = time.time() - t0
    logger.info("tune_relax completed in %.1f seconds", elapsed)
    return db, elapsed


def compile_and_export(mod, target, database, output_dir, task_stages=None):
    """Apply tuning database, compile, and export .so."""
    from tvm.s_tir.meta_schedule.relax_integration import (  # pylint: disable=import-outside-toplevel
        compile_relax,
    )

    os.makedirs(output_dir, exist_ok=True)
    compile_mod, handwritten_hook = resolve_handwritten_hook(
        mod=mod,
        target=target,
        database=database,
        output_dir=output_dir,
        task_stages=task_stages,
    )
    logger.info("Applying tuning database and compiling...")
    ex = compile_relax(
        database=database,
        mod=compile_mod,
        target=target,
        params={},
        enable_warning=False,
    )
    lib_path = os.path.join(output_dir, "optimized_model.so")
    ex.export_library(lib_path)
    logger.info("Compiled model exported: %s", lib_path)
    return lib_path, handwritten_hook


def write_tune_report(
    output_dir,
    args,
    elapsed_sec,
    lib_path,
    work_dir,
    task_summary_path,
    task_stages,
    handwritten_hook=None,
):
    """Write a JSON summary of the tuning run."""
    report = {
        "onnx_path": args.onnx_path,
        "target": args.target,
        "input_shape": args.input_shape,
        "total_trials": args.total_trials,
        "runner": args.runner,
        "tracker_host": args.tracker_host,
        "tracker_port": args.tracker_port,
        "device_key": args.device_key,
        "elapsed_sec": round(elapsed_sec, 1),
        "output_so": lib_path,
        "tuning_logs_dir": work_dir,
        "existing_db": args.existing_db or None,
        "task_stage_used_for_tuning": TUNED_STAGE_NAME,
        "raw_import_total_tasks": task_stages[RAW_STAGE_NAME]["total_tasks"],
        "tuned_stage_total_tasks": task_stages[TUNED_STAGE_NAME]["total_tasks"],
        "selected_op_names": parse_op_names(args.op_names),
        "task_summary_json": task_summary_path,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if handwritten_hook is not None:
        report["handwritten_hook"] = handwritten_hook
    report_path = os.path.join(output_dir, "tune_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Tune report written: %s", report_path)
    return report_path


def main():
    args = parse_args()

    input_shape = [int(x) for x in args.input_shape.split(",")]
    if len(input_shape) < 2:
        logger.error("Invalid --input-shape: %s", args.input_shape)
        sys.exit(1)

    if not os.path.isfile(args.onnx_path):
        logger.error("ONNX file not found: %s", args.onnx_path)
        sys.exit(1)

    import tvm  # pylint: disable=import-outside-toplevel

    target = tvm.target.Target(args.target)

    output_dir = os.path.abspath(args.output_dir)
    work_dir = os.path.join(output_dir, "tuning_logs")
    os.makedirs(work_dir, exist_ok=True)

    prepare_warm_start(args.existing_db, work_dir)

    raw_mod = load_onnx_to_relax(args.onnx_path, args.input_name, input_shape, args.input_dtype)
    mod, task_stages = summarize_task_stages(raw_mod, target)
    log_task_stage_summary(task_stages)
    warn_on_task_filter(task_stages, parse_op_names(args.op_names))
    task_summary_path = write_task_summary(output_dir, task_stages, args)

    if args.runner == "rpc":
        runner = build_rpc_runner(
            args.tracker_host,
            args.tracker_port,
            args.device_key,
            args.session_timeout,
        )
    else:
        runner = "local"

    db, elapsed = run_tune(mod, target, work_dir, runner, args)
    sanitize_tuning_records(work_dir)

    lib_path, handwritten_hook = compile_and_export(
        mod,
        target,
        db,
        output_dir,
        task_stages=task_stages,
    )
    if handwritten_hook is not None:
        task_summary_path = write_task_summary(
            output_dir,
            task_stages,
            args,
            handwritten_hook=handwritten_hook,
        )
    report_path = write_tune_report(
        output_dir,
        args,
        elapsed,
        lib_path,
        work_dir,
        task_summary_path,
        task_stages,
        handwritten_hook=handwritten_hook,
    )

    print(f"tune_output_dir={output_dir}")
    print(f"tune_so_path={lib_path}")
    print(f"tune_report={report_path}")
    print(f"task_summary_json={task_summary_path}")
    print(f"tune_elapsed_sec={elapsed:.1f}")
    if handwritten_hook is not None:
        print(f"handwritten_hook_status={handwritten_hook['status']}")


if __name__ == "__main__":
    main()
