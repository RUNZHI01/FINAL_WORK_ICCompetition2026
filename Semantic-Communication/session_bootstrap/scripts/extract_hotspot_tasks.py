#!/usr/bin/env python3
"""Extract and rank Relax/MetaSchedule tasks for a target model.

Supports direct CLI arguments or loading defaults from a shell env file used by
run_rpc_tune.sh. This is intended as a lightweight visibility tool before a real
MetaSchedule round.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from relax_ms_utils import (
    RAW_STAGE_NAME,
    TUNED_STAGE_NAME,
    TUNED_STAGE_PIPELINE,
    load_onnx_to_relax,
    summarize_task_stages,
)


def load_shell_env(env_path: str) -> dict[str, str]:
    python_exe = shlex.quote(sys.executable)
    env_quoted = shlex.quote(env_path)
    cmd = (
        f"set -a; source {env_quoted} >/dev/null 2>&1; "
        f"{python_exe} - <<'PY'\n"
        "import json, os\n"
        "print(json.dumps(dict(os.environ), ensure_ascii=False))\n"
        "PY"
    )
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract/rank MetaSchedule hotspot tasks")
    p.add_argument("--env", help="Optional shell env file to source for defaults")
    p.add_argument("--onnx-path", help="Path to ONNX model")
    p.add_argument("--target", help="TVM target string")
    p.add_argument("--input-shape", help="Comma-separated input shape, e.g. 1,32,32,32")
    p.add_argument("--input-name", default=None, help="ONNX input tensor name")
    p.add_argument("--input-dtype", default=None, help="Input dtype")
    p.add_argument("--top-k", type=int, default=8, help="How many top tasks to print")
    p.add_argument("--output", help="Optional output markdown path")
    p.add_argument("--json-output", help="Optional output JSON path")
    return p.parse_args()


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    env = load_shell_env(args.env) if args.env else {}

    def pick(name: str, default: str | None = None) -> str | None:
        cli_value = getattr(args, name.lower().replace("-", "_"), None)
        if cli_value not in (None, ""):
            return cli_value
        return env.get(name, default)

    cfg = {
        "onnx_path": pick("ONNX_MODEL_PATH"),
        "target": pick("TARGET"),
        "input_shape": pick("TUNE_INPUT_SHAPE"),
        "input_name": pick("TUNE_INPUT_NAME", "input"),
        "input_dtype": pick("TUNE_INPUT_DTYPE", "float32"),
        "report_dir": env.get("REPORT_DIR", "./session_bootstrap/reports"),
    }

    if args.onnx_path:
        cfg["onnx_path"] = args.onnx_path
    if args.target:
        cfg["target"] = args.target
    if args.input_shape:
        cfg["input_shape"] = args.input_shape
    if args.input_name:
        cfg["input_name"] = args.input_name
    if args.input_dtype:
        cfg["input_dtype"] = args.input_dtype

    missing = [
        key
        for key in ("onnx_path", "target", "input_shape", "input_name", "input_dtype")
        if not cfg.get(key)
    ]
    if missing:
        raise SystemExit(f"Missing required config: {', '.join(missing)}")

    return cfg


def extract_task_stages(cfg: dict[str, Any]) -> dict[str, Any]:
    import tvm  # pylint: disable=import-outside-toplevel

    input_shape = [int(x) for x in str(cfg["input_shape"]).split(",") if x]
    if not input_shape:
        raise SystemExit(f"Invalid input shape: {cfg['input_shape']}")

    mod = load_onnx_to_relax(
        onnx_path=cfg["onnx_path"],
        input_name=cfg["input_name"],
        input_shape=input_shape,
        input_dtype=cfg["input_dtype"],
    )
    target = tvm.target.Target(cfg["target"])
    _, stage_data = summarize_task_stages(mod, target)
    return stage_data


def write_stage_table(
    f,
    title: str,
    stage_key: str,
    stage: dict[str, Any],
    top_k: int,
) -> None:
    top_names = ",".join(row["task_name"] for row in stage["tasks"][:top_k]) or "N/A"
    f.write(f"## {title}\n\n")
    f.write(f"- stage_name: {stage_key}\n")
    f.write(f"- total_tasks: {stage['total_tasks']}\n")
    if stage.get("pipeline"):
        f.write(f"- pipeline: {stage['pipeline']}\n")
    f.write(f"- recommended_FULL_HOTSPOT_TASKS: {top_names}\n\n")
    f.write("| rank | task_name | weight | dispatched_count | prim_funcs |\n")
    f.write("|---|---|---:|---:|---|\n")
    for row in stage["tasks"][:top_k]:
        prim_funcs = ", ".join(row["prim_funcs"]) if row["prim_funcs"] else "-"
        f.write(
            f"| {row['rank']} | {row['task_name']} | {row['weight']} | {row['dispatched_count']} | {prim_funcs} |\n"
        )
    f.write("\n")


def write_markdown(path: str, stages: dict[str, Any], cfg: dict[str, Any], top_k: int) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    recommended = stages[TUNED_STAGE_NAME]
    raw_import = stages[RAW_STAGE_NAME]
    top_names = ",".join(row["task_name"] for row in recommended["tasks"][:top_k]) or "N/A"
    with out.open("w", encoding="utf-8") as f:
        f.write("# MetaSchedule Hotspot Tasks\n\n")
        f.write(f"- generated_at: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        f.write(f"- onnx_path: {cfg['onnx_path']}\n")
        f.write(f"- target: {cfg['target']}\n")
        f.write(f"- input_shape: {cfg['input_shape']}\n")
        f.write(f"- task_stage_used_for_recommendation: {TUNED_STAGE_NAME}\n")
        f.write(f"- tuned_stage_pipeline: {TUNED_STAGE_PIPELINE}\n")
        f.write(f"- tuned_stage_total_tasks: {recommended['total_tasks']}\n")
        f.write(f"- raw_import_total_tasks: {raw_import['total_tasks']}\n")
        f.write(f"- recommended_FULL_HOTSPOT_TASKS: {top_names}\n\n")
        write_stage_table(
            f,
            "Recommended Tuned Stage",
            TUNED_STAGE_NAME,
            recommended,
            top_k,
        )
        write_stage_table(
            f,
            "Raw Import Stage",
            RAW_STAGE_NAME,
            raw_import,
            top_k,
        )


def main() -> None:
    args = parse_args()
    cfg = resolve_config(args)
    stages = extract_task_stages(cfg)
    recommended = stages[TUNED_STAGE_NAME]
    raw_import = stages[RAW_STAGE_NAME]
    rows = recommended["tasks"]

    top_k = max(1, args.top_k)
    report_dir = Path(cfg["report_dir"])
    default_md = report_dir / f"hotspot_tasks_{time.strftime('%Y%m%d_%H%M%S')}.md"
    default_json = report_dir / f"hotspot_tasks_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output_md = args.output or str(default_md)
    output_json = args.json_output or str(default_json)

    Path(output_json).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "onnx_path": cfg["onnx_path"],
                "target": cfg["target"],
                "input_shape": cfg["input_shape"],
                "task_stage_used_for_recommendation": TUNED_STAGE_NAME,
                "tuned_stage_pipeline": TUNED_STAGE_PIPELINE,
                "total_tasks": len(rows),
                "raw_import_total_tasks": raw_import["total_tasks"],
                "top_k": top_k,
                "tasks": rows,
                "stages": stages,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    write_markdown(output_md, stages, cfg, top_k)

    recommended = ",".join(row["task_name"] for row in rows[:top_k]) if rows else ""
    print(f"task_stage_used_for_recommendation={TUNED_STAGE_NAME}")
    print(f"tuned_stage_pipeline={TUNED_STAGE_PIPELINE}")
    print(f"total_tasks={len(rows)}")
    print(f"raw_import_total_tasks={raw_import['total_tasks']}")
    print(f"top_k={top_k}")
    print(f"recommended_full_hotspot_tasks={recommended}")
    print(f"markdown_report={output_md}")
    print(f"json_report={output_json}")
    for row in rows[:top_k]:
        prim_funcs = ",".join(row["prim_funcs"]) if row["prim_funcs"] else "-"
        print(
            f"task rank={row['rank']} name={row['task_name']} weight={row['weight']} "
            f"dispatched={row['dispatched_count']} prim_funcs={prim_funcs}"
        )
    if raw_import["tasks"]:
        print("raw_import_stage_preview_begin")
        for row in raw_import["tasks"][: min(top_k, len(raw_import["tasks"]))]:
            prim_funcs = ",".join(row["prim_funcs"]) if row["prim_funcs"] else "-"
            print(
                f"raw_task rank={row['rank']} name={row['task_name']} weight={row['weight']} "
                f"dispatched={row['dispatched_count']} prim_funcs={prim_funcs}"
            )
        print("raw_import_stage_preview_end")


if __name__ == "__main__":
    main()
