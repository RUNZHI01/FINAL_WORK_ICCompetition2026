#!/usr/bin/env python3
import argparse
import json
import re
import statistics
from pathlib import Path

PATTERNS = [
    re.compile(r"批量推理时间.*?:\s*([0-9]+(?:\.[0-9]+)?)\s*秒"),
    re.compile(r"batch\s+infer(?:ence)?\s+time.*?:\s*([0-9]+(?:\.[0-9]+)?)\s*s(?:ec(?:onds?)?)?", re.I),
]


def parse_values(path: Path):
    values_ms = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            for pattern in PATTERNS:
                m = pattern.search(line)
                if m:
                    values_ms.append(float(m.group(1)) * 1000.0)
                    break
    return values_ms


def summarize(values_ms):
    if not values_ms:
        return {"count": 0}
    ordered = sorted(values_ms)
    p90_idx = int((len(ordered) - 1) * 0.9)
    return {
        "count": len(values_ms),
        "median_ms": round(statistics.median(values_ms), 3),
        "mean_ms": round(sum(values_ms) / len(values_ms), 3),
        "min_ms": round(min(values_ms), 3),
        "max_ms": round(max(values_ms), 3),
        "p90_ms": round(ordered[p90_idx], 3),
        "first10_ms": [round(v, 3) for v in values_ms[:10]],
        "last10_ms": [round(v, 3) for v in values_ms[-10:]],
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize legacy TVM inference logs that print per-sample latency lines.")
    parser.add_argument("log_file", help="Path to the legacy inference log file")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    path = Path(args.log_file)
    if not path.is_file():
        raise SystemExit(f"ERROR: log file not found: {path}")

    values_ms = parse_values(path)
    payload = {
        "log_file": str(path),
        "summary": summarize(values_ms),
    }
    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
