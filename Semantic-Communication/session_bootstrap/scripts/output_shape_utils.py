#!/usr/bin/env python3
"""Helpers for reporting and normalizing output-shape mismatches."""

from __future__ import annotations

import json
from typing import Any


UNKNOWN_SHAPE_VALUES = {"", "NA", "None", "null"}


def parse_shape(value: Any) -> list[int] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        result = [int(item) for item in value]
        return result or None
    if isinstance(value, str):
        text = value.strip()
        if text in UNKNOWN_SHAPE_VALUES:
            return None
        if text.startswith("[") and text.endswith("]"):
            payload = json.loads(text)
            return parse_shape(payload)
        normalized = text.replace("x", ",")
        pieces = [piece.strip() for piece in normalized.split(",") if piece.strip()]
        if not pieces:
            return None
        return [int(piece) for piece in pieces]
    raise TypeError(f"unsupported shape value: {value!r}")


def crop_offsets(diff: int, anchor: str) -> tuple[int, int]:
    if diff < 0:
        raise ValueError(f"crop diff must be >= 0 (got: {diff})")
    if anchor == "top-left":
        return 0, diff
    if anchor == "center":
        start = diff // 2
        return start, diff - start
    raise ValueError(f"unsupported crop anchor: {anchor}")


def build_crop_plan(shape: list[int], target_shape: list[int], anchor: str) -> dict[str, Any]:
    if len(shape) != len(target_shape):
        raise ValueError("cannot build crop plan for shapes with different rank")
    if len(shape) < 2:
        raise ValueError("crop plan requires at least 2 dimensions")
    if any(source < target for source, target in zip(shape, target_shape)):
        raise ValueError("target shape cannot exceed source shape")

    crop_before_h, crop_after_h = crop_offsets(shape[-2] - target_shape[-2], anchor)
    crop_before_w, crop_after_w = crop_offsets(shape[-1] - target_shape[-1], anchor)
    changed = shape != target_shape
    return {
        "changed": changed,
        "anchor": anchor,
        "source_shape": list(shape),
        "target_shape": list(target_shape),
        "crop_top": crop_before_h,
        "crop_bottom": crop_after_h,
        "crop_left": crop_before_w,
        "crop_right": crop_after_w,
    }


def build_normalization_plan(left_shape: list[int], right_shape: list[int], anchor: str) -> dict[str, Any]:
    common_shape = list(left_shape[:-2]) + [
        min(left_shape[-2], right_shape[-2]),
        min(left_shape[-1], right_shape[-1]),
    ]
    return {
        "anchor": anchor,
        "target_shape": common_shape,
        "left": build_crop_plan(left_shape, common_shape, anchor),
        "right": build_crop_plan(right_shape, common_shape, anchor),
    }


def describe_crop_plan(label: str, plan: dict[str, Any]) -> str:
    if not plan["changed"]:
        return f"{label}: keep {plan['source_shape']}"
    return (
        f"{label}: crop {plan['source_shape']} -> {plan['target_shape']} "
        f"(top={plan['crop_top']}, bottom={plan['crop_bottom']}, "
        f"left={plan['crop_left']}, right={plan['crop_right']})"
    )


def describe_normalization_plan(plan: dict[str, Any], left_label: str, right_label: str) -> str:
    return "; ".join(
        [
            f"anchor={plan['anchor']}",
            describe_crop_plan(left_label, plan["left"]),
            describe_crop_plan(right_label, plan["right"]),
        ]
    )


def analyze_shape_pair(left: Any, right: Any, *, left_label: str = "left", right_label: str = "right") -> dict[str, Any]:
    left_shape = parse_shape(left)
    right_shape = parse_shape(right)
    result: dict[str, Any] = {
        "left_label": left_label,
        "right_label": right_label,
        "left_shape": left_shape,
        "right_shape": right_shape,
        "shapes_match": left_shape is not None and right_shape is not None and left_shape == right_shape,
        "relation": "unknown",
        "delta_right_minus_left": None,
        "common_shape": None,
        "normalization_candidates": [],
        "normalization_hint_center": None,
        "normalization_hint_top_left": None,
    }
    if left_shape is None or right_shape is None:
        return result
    if len(left_shape) != len(right_shape):
        result["relation"] = "rank_mismatch"
        return result

    result["delta_right_minus_left"] = [right_dim - left_dim for left_dim, right_dim in zip(left_shape, right_shape)]
    if left_shape == right_shape:
        result["relation"] = "exact_match"
        result["common_shape"] = list(left_shape)
        return result

    if len(left_shape) >= 2 and left_shape[:-2] == right_shape[:-2]:
        result["relation"] = "spatial_mismatch"
        center_plan = build_normalization_plan(left_shape, right_shape, "center")
        top_left_plan = build_normalization_plan(left_shape, right_shape, "top-left")
        result["common_shape"] = center_plan["target_shape"]
        result["normalization_candidates"] = [center_plan, top_left_plan]
        result["normalization_hint_center"] = describe_normalization_plan(
            center_plan,
            left_label=left_label,
            right_label=right_label,
        )
        result["normalization_hint_top_left"] = describe_normalization_plan(
            top_left_plan,
            left_label=left_label,
            right_label=right_label,
        )
        return result

    result["relation"] = "non_spatial_mismatch"
    return result


def crop_array_to_target(array, target_shape: tuple[int, int], *, anchor: str, np):
    height, width = array.shape[:2]
    target_height, target_width = target_shape
    if target_height > height or target_width > width:
        raise ValueError(
            f"target shape {target_shape} exceeds source image shape {(height, width)}"
        )
    top, bottom = crop_offsets(height - target_height, anchor)
    left, right = crop_offsets(width - target_width, anchor)
    row_end = height - bottom if bottom else height
    col_end = width - right if right else width
    cropped = np.ascontiguousarray(array[top:row_end, left:col_end, ...])
    return cropped, {
        "anchor": anchor,
        "crop_top": top,
        "crop_bottom": bottom,
        "crop_left": left,
        "crop_right": right,
        "source_shape": [int(dim) for dim in array.shape],
        "target_shape": [int(dim) for dim in cropped.shape],
    }
