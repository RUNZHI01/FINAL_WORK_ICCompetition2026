#!/usr/bin/env python3
"""Shared helpers for judge-facing evidence reports."""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any


DEFAULT_REPORT_DIR = Path("session_bootstrap/reports")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return dt.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "report"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"ERROR: expected a JSON object in {path}")
    return payload


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        if math.isnan(value):
            return "nan"
        return "inf" if value > 0 else "-inf"
    return value


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "NA"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric):
            return f"{numeric:.{digits}f}"
        return "inf" if numeric > 0 else "-inf"
    return str(value)


def fmt_int(value: Any) -> str:
    if value is None:
        return "NA"
    return str(int(value))


def fmt_mib(size_bytes: int | None, digits: int = 3) -> str:
    if size_bytes is None:
        return "NA"
    return f"{size_bytes / (1024 * 1024):.{digits}f}"


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    text = str(value).strip().strip("`")
    if not text or text.upper() in {"NA", "N/A", "SKIPPED", "NONE"}:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return None
    return numeric if math.isfinite(numeric) else None


def mean_ci95(values: list[Any]) -> dict[str, Any]:
    finite_values = [numeric for value in values if (numeric := to_float(value)) is not None]
    count = len(finite_values)
    if count == 0:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "ci95_half_width": None,
            "min": None,
            "max": None,
        }
    if count == 1:
        mean_value = finite_values[0]
        return {
            "count": 1,
            "mean": mean_value,
            "median": mean_value,
            "std": 0.0,
            "ci95_half_width": 0.0,
            "min": mean_value,
            "max": mean_value,
        }
    mean_value = statistics.mean(finite_values)
    median_value = statistics.median(finite_values)
    std_value = statistics.stdev(finite_values)
    ci95 = 1.96 * std_value / math.sqrt(count)
    return {
        "count": count,
        "mean": mean_value,
        "median": median_value,
        "std": std_value,
        "ci95_half_width": ci95,
        "min": min(finite_values),
        "max": max(finite_values),
    }


def latest_match(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.glob(pattern))
    return matches[-1] if matches else None


def parse_markdown_key_values(text: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        payload[key.strip()] = value.strip()
    return payload


def parse_table_rows(text: str, header_startswith: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    rows: list[dict[str, str]] = []
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        columns = [part.strip() for part in line.strip("|").split("|")]
        if not columns or columns[0] != header_startswith:
            continue
        if index + 1 >= len(lines):
            break
        headers = columns
        cursor = index + 2
        while cursor < len(lines):
            row_line = lines[cursor].strip()
            if not row_line.startswith("|"):
                break
            parts = [part.strip() for part in row_line.strip("|").split("|")]
            if len(parts) != len(headers):
                break
            rows.append(dict(zip(headers, parts)))
            cursor += 1
        break
    return rows


def build_line_chart_svg(
    *,
    title: str,
    x_label: str,
    y_label: str,
    series: list[dict[str, Any]],
    width: int = 880,
    height: int = 420,
) -> str:
    valid_series = []
    for item in series:
        points = []
        for x_value, y_value in item.get("points", []):
            x_numeric = to_float(x_value)
            y_numeric = to_float(y_value)
            if x_numeric is None or y_numeric is None:
                continue
            points.append((x_numeric, y_numeric))
        if points:
            valid_series.append({**item, "points": points})
    if not valid_series:
        raise SystemExit("ERROR: line chart requested with no numeric points")

    left = 72
    right = 24
    top = 56
    bottom = 64
    plot_width = width - left - right
    plot_height = height - top - bottom

    all_x = [point[0] for item in valid_series for point in item["points"]]
    all_y = [point[1] for item in valid_series for point in item["points"]]
    min_x = min(all_x)
    max_x = max(all_x)
    min_y = min(all_y)
    max_y = max(all_y)
    if math.isclose(min_x, max_x):
        min_x -= 1.0
        max_x += 1.0
    if math.isclose(min_y, max_y):
        delta = abs(min_y) * 0.1 or 1.0
        min_y -= delta
        max_y += delta
    else:
        padding = (max_y - min_y) * 0.08
        min_y -= padding
        max_y += padding

    def scale_x(value: float) -> float:
        return left + ((value - min_x) / (max_x - min_x)) * plot_width

    def scale_y(value: float) -> float:
        return top + plot_height - ((value - min_y) / (max_y - min_y)) * plot_height

    x_tick_values = sorted({point[0] for item in valid_series for point in item["points"]})
    y_ticks = [min_y + index * (max_y - min_y) / 4 for index in range(5)]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2:.1f}" y="28" text-anchor="middle" font-size="20" font-family="sans-serif" fill="#1f2937">{html.escape(title)}</text>',
    ]

    for tick in y_ticks:
        y = scale_y(tick)
        parts.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="12" font-family="sans-serif" fill="#4b5563">{html.escape(fmt(tick, 3))}</text>'
        )

    for tick in x_tick_values:
        x = scale_x(tick)
        parts.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#f3f4f6" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-size="12" font-family="sans-serif" fill="#4b5563">{html.escape(fmt(tick, 0))}</text>'
        )

    parts.append(
        f'<line x1="{left}" y1="{top + plot_height}" x2="{width - right}" y2="{top + plot_height}" stroke="#111827" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#111827" stroke-width="1.5"/>'
    )
    parts.append(
        f'<text x="{width / 2:.1f}" y="{height - 18}" text-anchor="middle" font-size="13" font-family="sans-serif" fill="#111827">{html.escape(x_label)}</text>'
    )
    parts.append(
        f'<text x="20" y="{height / 2:.1f}" text-anchor="middle" font-size="13" font-family="sans-serif" fill="#111827" transform="rotate(-90 20 {height / 2:.1f})">{html.escape(y_label)}</text>'
    )

    legend_x = width - right - 180
    legend_y = 44
    for index, item in enumerate(valid_series):
        color = item.get("color", "#2563eb")
        y = legend_y + index * 18
        parts.append(
            f'<line x1="{legend_x}" y1="{y}" x2="{legend_x + 18}" y2="{y}" stroke="{color}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{legend_x + 24}" y="{y + 4}" font-size="12" font-family="sans-serif" fill="#111827">{html.escape(str(item.get("name", "series")))}</text>'
        )

    for item in valid_series:
        color = item.get("color", "#2563eb")
        points = item["points"]
        path = " ".join(f"{scale_x(x):.2f},{scale_y(y):.2f}" for x, y in points)
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{path}" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        for x_value, y_value in points:
            cx = scale_x(x_value)
            cy = scale_y(y_value)
            parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="{color}"/>')
            parts.append(
                f'<text x="{cx:.2f}" y="{cy - 10:.2f}" text-anchor="middle" font-size="11" font-family="sans-serif" fill="{color}">{html.escape(fmt(y_value, 2))}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)
