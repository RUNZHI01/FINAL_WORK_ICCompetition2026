#!/usr/bin/env python3
"""usrp_metrics.py — USRP / latent 质量指标辅助函数。"""

from __future__ import annotations

import io
import math
from typing import Any

import numpy as np


def ensure_batched(latent: Any) -> np.ndarray:
    """把 latent 统一成 batched float32 ndarray。"""
    array = np.asarray(latent, dtype=np.float32)
    if array.ndim == 3:
        array = np.expand_dims(array, axis=0)
    return array


def load_latent_from_npz_bytes(payload: bytes) -> np.ndarray:
    """从 `.npz` 字节加载 latent / quant payload。"""
    with np.load(io.BytesIO(payload)) as data:
        if 'latent' in data:
            return ensure_batched(data['latent'])
        if {'quant', 'scale', 'zero_point'}.issubset(set(data.files)):
            quant = np.asarray(data['quant'], dtype=np.float32)
            scale = np.asarray(data['scale'], dtype=np.float32)
            zero_point = np.asarray(data['zero_point'], dtype=np.float32)
            return ensure_batched((quant - zero_point) * scale)
        if not data.files:
            raise ValueError('npz payload 不包含任何数组')
        return ensure_batched(data[data.files[0]])


def byte_diff_metrics(reference: bytes, candidate: bytes) -> dict[str, int | bool]:
    """统计 byte / bit 级差异。"""
    compared = min(len(reference), len(candidate))
    byte_errors = 0
    bit_errors = 0

    for ref_byte, cand_byte in zip(reference[:compared], candidate[:compared]):
        delta = ref_byte ^ cand_byte
        if delta:
            byte_errors += 1
            bit_errors += int(delta.bit_count())

    trailing = abs(len(reference) - len(candidate))
    if trailing:
        byte_errors += trailing
        bit_errors += trailing * 8

    return {
        'byte_exact': bool(reference == candidate),
        'byte_errors': int(byte_errors),
        'bit_errors': int(bit_errors),
        'compared_bytes': int(compared),
        'trailing_bytes': int(trailing),
    }


def tensor_error_metrics(
    reference: np.ndarray,
    candidate: np.ndarray,
) -> dict[str, int | float | bool | None | str]:
    """统计 tensor 级误差与等效 SNR。"""
    ref = np.asarray(reference, dtype=np.float32)
    cand = np.asarray(candidate, dtype=np.float32)
    if ref.shape != cand.shape:
        raise ValueError(f'shape 不一致: ref={ref.shape} cand={cand.shape}')

    ref64 = ref.astype(np.float64, copy=False)
    cand64 = cand.astype(np.float64, copy=False)
    diff64 = cand64 - ref64

    signal_power = float(np.mean(np.square(ref64)))
    noise_power = float(np.mean(np.square(diff64)))
    mean_abs_error = float(np.mean(np.abs(diff64)))
    max_abs_error = float(np.max(np.abs(diff64))) if diff64.size else 0.0
    exact = bool(np.array_equal(ref, cand))

    if noise_power <= 0.0:
        effective_snr_db = None
        effective_snr_db_text = 'inf'
        effective_snr_db_infinite = True
    else:
        denom = max(noise_power, 1e-30)
        numer = max(signal_power, 1e-30)
        effective_snr_db = float(10.0 * np.log10(numer / denom))
        effective_snr_db_text = f'{effective_snr_db:.3f}'
        effective_snr_db_infinite = False

    return {
        'tensor_exact': exact,
        'element_count': int(ref.size),
        'signal_power': signal_power,
        'noise_power': noise_power,
        'mean_abs_error': mean_abs_error,
        'max_abs_error': max_abs_error,
        'effective_snr_db': effective_snr_db,
        'effective_snr_db_text': effective_snr_db_text,
        'effective_snr_db_infinite': effective_snr_db_infinite,
    }


def npz_payload_metrics(
    reference_payload: bytes,
    candidate_payload: bytes,
) -> dict[str, int | float | bool | None | str]:
    """对 `.npz` payload 同时做 byte 级与 tensor 级统计。"""
    metrics = byte_diff_metrics(reference_payload, candidate_payload)
    metrics.update(
        tensor_error_metrics(
            load_latent_from_npz_bytes(reference_payload),
            load_latent_from_npz_bytes(candidate_payload),
        )
    )
    return metrics


def format_snr_text(value: float | None, infinite: bool = False) -> str:
    """格式化 SNR 文本。"""
    if infinite or value is None:
        return 'inf'
    if math.isfinite(value):
        return f'{value:.3f}'
    return str(value)
