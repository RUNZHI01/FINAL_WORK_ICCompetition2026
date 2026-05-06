#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def last_matching(records: list[dict[str, Any]], **expected: str) -> dict[str, Any]:
    for payload in reversed(records):
        if all(str(payload.get(key) or "") == value for key, value in expected.items()):
            return payload
    return {}


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def nested_number(payload: dict[str, Any], *keys: str) -> float | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return number(current)


def file_count(path: Path, pattern: str) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for _ in path.glob(pattern))


def metric(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean_ms": None, "median_ms": None, "min_ms": None, "max_ms": None}
    return {
        "n": len(values),
        "mean_ms": round(statistics.mean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize-demo-kpis.py RUN_ROOT", file=sys.stderr)
        return 2

    run_root = Path(sys.argv[1]).resolve()
    logs = run_root / "logs"
    outputs = run_root / "work" / "outputs"

    tvm_summary = load_json(outputs / "tvm" / "summary.json")
    mnn_summary = last_matching(load_json_lines(logs / "mnn.json"), status="ok")
    pytorch_summary = last_matching(load_json_lines(logs / "pytorch.json"), runtime="pytorch_reference")

    tvm_jsonl = load_json_lines(logs / "tvm.jsonl")
    tvm_samples = [value for value in (number(item.get("inference_ms")) for item in tvm_jsonl) if value is not None]
    pytorch_samples = [
        value for value in (number(item) for item in pytorch_summary.get("run_samples_ms", [])) if value is not None
    ]

    mnn_total_median = nested_number(mnn_summary, "sample_stats", "total_ms", "median_ms")
    mnn_run_median = nested_number(mnn_summary, "sample_stats", "run_ms", "median_ms")

    summary = {
        "run_root": str(run_root),
        "counts": {
            "tvm_outputs": file_count(outputs / "tvm" / "results", "*.npy"),
            "mnn_outputs": file_count(outputs / "mnn" / "reconstructions", "*.png"),
            "pytorch_outputs": file_count(outputs / "pytorch" / "reconstructions", "*.png"),
        },
        "demo_kpis": {
            "tvm": {
                "demo_metric_ms": round(float(tvm_summary["run_median_ms"]), 3),
                "metric_source": "TVM batch KPI: inference_ms.median_ms, same as Electron batch comparison",
                "processed_count": int(tvm_summary.get("processed_count") or 0),
                "inference_ms": metric(tvm_samples),
                "load_mean_ms": number(tvm_summary.get("load_mean_ms")),
            },
            "mnn": {
                "demo_metric_ms": round(float(mnn_total_median), 3) if mnn_total_median is not None else None,
                "metric_source": "MNN batch KPI: total_ms.median_ms, same as Electron batch comparison",
                "processed_count": int(mnn_summary.get("processed_count") or 0),
                "total_ms": mnn_summary.get("sample_stats", {}).get("total_ms", {}),
                "run_ms": mnn_summary.get("sample_stats", {}).get("run_ms", {}),
                "run_median_ms": round(float(mnn_run_median), 3) if mnn_run_median is not None else None,
            },
            "pytorch": {
                "demo_metric_ms": round(float(pytorch_summary["run_median_ms"]), 3),
                "metric_source": "PyTorch reference KPI: run_median_ms",
                "processed_count": int(pytorch_summary.get("processed_count") or 0),
                "run_ms": metric(pytorch_samples),
                "load_ms": number(pytorch_summary.get("load_ms")),
            },
        },
    }

    output_path = logs / "demo-kpi-summary.json"
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
