#!/usr/bin/env python3
"""Analog latent-IQ PHY for LGJSCC over NI-USRP-2922.

This module maps the continuous LGJSCC latent directly to complex I/Q symbols.
It intentionally does not provide bit-exact payload authentication for the
analog data plane; the output wire blob records the recovered noisy latent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from latent_transport import (  # noqa: E402
    _load_float32_latent,
    decode_transport_payload,
    pack_transport_frame,
    unpack_transport_frame,
)


DEFAULT_RATE = 5_000_000.0
DEFAULT_SPS = 4
DEFAULT_RRC_BETA = 0.35
DEFAULT_RRC_SPAN = 8
DEFAULT_SC16_AMPLITUDE = 3000
DEFAULT_ZERO_GUARD_SAMPLES = 4096
DEFAULT_TAIL_GUARD_SAMPLES = 4096
DEFAULT_CFO_PILOT_SYMBOLS = 1024
DEFAULT_SYNC_PILOT_SYMBOLS = 1024
DEFAULT_DATA_BLOCK_SYMBOLS = 4096
DEFAULT_MID_PILOT_SYMBOLS = 128
DEFAULT_CAPTURE_MARGIN_SAMPLES = 20_000
DEFAULT_SYNC_CANDIDATES = 12
DEFAULT_FAST_SYNC_CANDIDATES = 4
DEFAULT_FAST_SYNC_SEARCH_WINDOW_SYMBOLS = 1024
DEFAULT_FALLBACK_SYNC_CANDIDATES = 12
DEFAULT_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS = 4096
DEFAULT_ROBUST_CFO_MAX_HZ = 8000.0
DEFAULT_ROBUST_CFO_STEP_HZ = 500.0
DEFAULT_MIN_SYNC_METRIC = 0.25
DEFAULT_LOW_SYNC_RETRY_THRESHOLD = 0.08
DEFAULT_SYNC_POWER_DECIMATION = 8
SAMPLE_BYTES = 4
EPS = 1.0e-12
SCRAMBLING_MODE = "keyed-permutation-sign-v1"
SYNC_FFT_CORRELATE_MIN_VALID = 512
_SCIPY_SIGNAL: Any | None = None
_SCIPY_SIGNAL_IMPORT_ATTEMPTED = False


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def atomic_savez(path: Path, **items: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".npy":
        if "latent" not in items:
            raise KeyError("latent")
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp.npy")
        save = lambda target: np.save(target, np.asarray(items["latent"], dtype=np.float32))
    else:
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp.npz")
        save = lambda target: np.savez(target, **items)
    try:
        save(tmp_path)
        os.replace(tmp_path, path)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scipy_signal_module() -> Any | None:
    global _SCIPY_SIGNAL, _SCIPY_SIGNAL_IMPORT_ATTEMPTED
    if not _SCIPY_SIGNAL_IMPORT_ATTEMPTED:
        _SCIPY_SIGNAL_IMPORT_ATTEMPTED = True
        try:
            from scipy import signal as scipy_signal  # type: ignore

            _SCIPY_SIGNAL = scipy_signal
        except Exception:
            _SCIPY_SIGNAL = None
    return _SCIPY_SIGNAL


def sync_correlation(search_stream: np.ndarray, sync: np.ndarray) -> tuple[np.ndarray, str]:
    valid_count = int(search_stream.size - sync.size + 1)
    if valid_count >= SYNC_FFT_CORRELATE_MIN_VALID:
        scipy_signal = scipy_signal_module()
        if scipy_signal is not None:
            corr = scipy_signal.correlate(
                np.ascontiguousarray(search_stream),
                np.ascontiguousarray(sync),
                mode="valid",
                method="fft",
            )
            return np.abs(corr).astype(np.float32, copy=False), "scipy-fft"
    return np.abs(np.correlate(search_stream, sync, mode="valid")).astype(np.float32, copy=False), "numpy-direct"


def warm_sync_correlation() -> dict[str, Any]:
    raw_enabled = str(os.environ.get("ANALOG_SYNC_FFT_WARMUP", "1")).strip().lower()
    if raw_enabled in {"0", "false", "no", "off"}:
        return {"sync_fft_warmup_enabled": False}
    t0 = time.perf_counter()
    sync = np.ones(1024, dtype=np.complex64)
    search_stream = np.ones(4096 + sync.size - 1, dtype=np.complex64)
    _corr, method = sync_correlation(search_stream, sync)
    return {
        "sync_fft_warmup_enabled": True,
        "sync_fft_warmup_method": method,
        "sync_fft_warmup_ms": round(float((time.perf_counter() - t0) * 1000.0), 3),
    }


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _decode_warmup_shape() -> tuple[int, ...]:
    raw = str(os.environ.get("ANALOG_DECODE_WARMUP_SHAPE", "1,32,32,32")).strip()
    try:
        shape = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError:
        shape = (1, 32, 32, 32)
    if len(shape) not in {3, 4} or any(dim <= 0 for dim in shape):
        return (1, 32, 32, 32)
    return shape


def warm_decode_pipeline() -> dict[str, Any]:
    raw_enabled = str(os.environ.get("ANALOG_DECODE_PIPELINE_WARMUP", "0")).strip().lower()
    if raw_enabled in {"", "0", "false", "no", "off"}:
        return {"decode_pipeline_warmup_enabled": False}
    started = time.perf_counter()
    shape = _decode_warmup_shape()
    work_dir = Path(os.environ.get("ANALOG_DECODE_WARMUP_DIR", f"/tmp/analog_decode_warmup_{os.getpid()}"))
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / "latent.npz"
        tx_sc16 = work_dir / "tx_analog.sc16"
        manifest_path = work_dir / "manifest.json"
        out_npz = work_dir / "received_latent.npz"
        summary_path = work_dir / "decode_summary.json"
        latent = np.linspace(-1.0, 1.0, num=int(np.prod(shape)), dtype=np.float32).reshape(shape)
        np.savez(input_path, latent=latent)
        make_args = argparse.Namespace(
            input=str(input_path),
            out_sc16=str(tx_sc16),
            manifest=str(manifest_path),
            job_id="decode_pipeline_warmup",
            rate=_env_float("RATE", DEFAULT_RATE),
            sps=_env_int("ANALOG_SPS", DEFAULT_SPS),
            rrc_beta=_env_float("ANALOG_RRC_BETA", DEFAULT_RRC_BETA),
            rrc_span=_env_int("ANALOG_RRC_SPAN", DEFAULT_RRC_SPAN),
            amp=_env_int("ANALOG_AMPLITUDE", _env_int("AMPLITUDE", DEFAULT_SC16_AMPLITUDE)),
            zero_guard_samples=_env_int("ANALOG_ZERO_GUARD_SAMPLES", DEFAULT_ZERO_GUARD_SAMPLES),
            tail_guard_samples=_env_int("ANALOG_TAIL_GUARD_SAMPLES", DEFAULT_TAIL_GUARD_SAMPLES),
            cfo_pilot_symbols=_env_int("ANALOG_CFO_PILOT_SYMBOLS", DEFAULT_CFO_PILOT_SYMBOLS),
            sync_pilot_symbols=_env_int("ANALOG_SYNC_PILOT_SYMBOLS", DEFAULT_SYNC_PILOT_SYMBOLS),
            data_block_symbols=_env_int("ANALOG_DATA_BLOCK_SYMBOLS", DEFAULT_DATA_BLOCK_SYMBOLS),
            mid_pilot_symbols=_env_int("ANALOG_MID_PILOT_SYMBOLS", DEFAULT_MID_PILOT_SYMBOLS),
            cfo_seed=_env_int("ANALOG_CFO_SEED", 1001),
            sync_seed=_env_int("ANALOG_SYNC_SEED", 1002),
            mid_pilot_seed=_env_int("ANALOG_MID_PILOT_SEED", 1003),
            capture_margin_samples=_env_int("ANALOG_CAPTURE_MARGIN_SAMPLES", DEFAULT_CAPTURE_MARGIN_SAMPLES),
            rx_post_quantize=_env_bool("ANALOG_RX_POST_QUANTIZE", True),
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
        make_waveform(make_args)
        decode_args = argparse.Namespace(
            rx_sc16=str(tx_sc16),
            manifest=str(manifest_path),
            out_npz=str(out_npz),
            out_wire="",
            summary_json=str(summary_path),
            sync_profile=os.environ.get("ANALOG_SYNC_PROFILE", ""),
            sync_candidates=_env_int("ANALOG_SYNC_CANDIDATES", DEFAULT_SYNC_CANDIDATES),
            fast_sync_candidates=_env_int("ANALOG_FAST_SYNC_CANDIDATES", DEFAULT_FAST_SYNC_CANDIDATES),
            fast_sync_search_window_symbols=_env_int(
                "ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS",
                DEFAULT_FAST_SYNC_SEARCH_WINDOW_SYMBOLS,
            ),
            fallback_sync_candidates=_env_int("ANALOG_FALLBACK_SYNC_CANDIDATES", DEFAULT_FALLBACK_SYNC_CANDIDATES),
            fallback_sync_search_window_symbols=_env_int(
                "ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS",
                DEFAULT_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS,
            ),
            retry_on_burst_miss=_env_bool("ANALOG_RETRY_ON_BURST_MISS", False),
            retry_on_low_sync=_env_bool("ANALOG_RETRY_ON_LOW_SYNC", False),
            low_sync_retry_threshold=_env_float(
                "ANALOG_LOW_SYNC_RETRY_THRESHOLD",
                DEFAULT_LOW_SYNC_RETRY_THRESHOLD,
            ),
            min_sync_metric=_env_float("ANALOG_MIN_SYNC_METRIC", DEFAULT_MIN_SYNC_METRIC),
            robust_sync=_env_bool("ANALOG_ROBUST_SYNC", True),
            robust_cfo_max_hz=_env_float("ANALOG_ROBUST_CFO_MAX_HZ", DEFAULT_ROBUST_CFO_MAX_HZ),
            robust_cfo_step_hz=_env_float("ANALOG_ROBUST_CFO_STEP_HZ", DEFAULT_ROBUST_CFO_STEP_HZ),
            sync_search_center_symbol=-1,
            sync_search_window_symbols=_env_int("ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS", 0),
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
        summary = decode_waveform(decode_args)
        return {
            "decode_pipeline_warmup_enabled": True,
            "decode_pipeline_warmup_status": "ok",
            "decode_pipeline_warmup_shape": list(shape),
            "decode_pipeline_warmup_ms": round(float((time.perf_counter() - started) * 1000.0), 3),
            "decode_pipeline_warmup_decode_total_ms": float(summary.get("decode_total_ms") or 0.0),
        }
    except Exception as exc:
        return {
            "decode_pipeline_warmup_enabled": True,
            "decode_pipeline_warmup_status": "error",
            "decode_pipeline_warmup_error": str(exc),
            "decode_pipeline_warmup_ms": round(float((time.perf_counter() - started) * 1000.0), 3),
        }
    finally:
        if _env_bool("ANALOG_DECODE_WARMUP_CLEANUP", True):
            shutil.rmtree(work_dir, ignore_errors=True)


def ensure_batched_float32(array: np.ndarray) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim == 3:
        arr = np.expand_dims(arr, axis=0)
    return arr.astype(np.float32, copy=False)


def load_latent(path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    """Load latent from .npz/.npy/.pt/raw .bin or an existing transport wire blob."""
    p = Path(path)
    if p.suffix == ".bin":
        blob = p.read_bytes()
        try:
            meta, payload_bytes = unpack_transport_frame(blob)
            decoded = decode_transport_payload(meta, payload_bytes, verify_latent_sha=True)
            latent = ensure_batched_float32(decoded.latent)
            return latent, {
                "shape": list(latent.shape),
                "dtype": "float32",
                "source_format": "transport-frame",
                "source_meta": meta,
            }
        except Exception:
            pass

    latent, info = _load_float32_latent(str(p))
    latent = ensure_batched_float32(latent)
    info = dict(info)
    info.setdefault("source_format", p.suffix.lstrip(".") or "raw")
    info["shape"] = list(latent.shape)
    info["dtype"] = "float32"
    return latent, info


def rrc_taps(beta: float, span: int, sps: int) -> np.ndarray:
    if sps < 2:
        raise ValueError("sps must be >= 2")
    if span < 2:
        raise ValueError("rrc span must be >= 2 symbols")
    if beta < 0.0 or beta > 1.0:
        raise ValueError("rrc beta must be in [0, 1]")

    half = span * sps / 2.0
    t = np.arange(-half, half + 1.0, dtype=np.float64) / float(sps)
    taps = np.zeros_like(t, dtype=np.float64)

    for idx, ti in enumerate(t):
        if abs(ti) < 1.0e-12:
            taps[idx] = 1.0 + beta * (4.0 / math.pi - 1.0)
        elif beta > 0.0 and abs(abs(4.0 * beta * ti) - 1.0) < 1.0e-10:
            taps[idx] = (
                beta
                / math.sqrt(2.0)
                * (
                    (1.0 + 2.0 / math.pi) * math.sin(math.pi / (4.0 * beta))
                    + (1.0 - 2.0 / math.pi) * math.cos(math.pi / (4.0 * beta))
                )
            )
        else:
            if beta == 0.0:
                taps[idx] = math.sin(math.pi * ti) / (math.pi * ti)
            else:
                numerator = (
                    math.sin(math.pi * ti * (1.0 - beta))
                    + 4.0 * beta * ti * math.cos(math.pi * ti * (1.0 + beta))
                )
                denominator = math.pi * ti * (1.0 - (4.0 * beta * ti) ** 2)
                taps[idx] = numerator / denominator

    energy = math.sqrt(float(np.sum(np.square(taps))))
    if energy <= 0.0:
        raise ValueError("invalid RRC taps: zero energy")
    return (taps / energy).astype(np.float32)


def make_pilot_symbols(count: int, seed: int) -> np.ndarray:
    if count <= 0:
        return np.zeros(0, dtype=np.complex64)
    rng = np.random.default_rng(int(seed))
    choices = rng.integers(0, 4, size=int(count), dtype=np.int16)
    table = np.asarray(
        [1.0 + 1.0j, 1.0 - 1.0j, -1.0 + 1.0j, -1.0 - 1.0j],
        dtype=np.complex64,
    ) / np.float32(math.sqrt(2.0))
    return table[choices].astype(np.complex64)


def latent_to_complex_symbols(latent: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    x = np.asarray(latent, dtype=np.float32).reshape(-1)
    n_real = int(x.size)
    real_rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64)) + 1.0e-8))
    u = x / np.float32(real_rms)
    if u.size % 2:
        u = np.pad(u, (0, 1), mode="constant")
    symbols = (u[0::2].astype(np.float32) + 1j * u[1::2].astype(np.float32)).astype(np.complex64)
    info = {
        "n_real": n_real,
        "n_complex": int(symbols.size),
        "real_rms": real_rms,
    }
    return symbols, info


def complex_symbols_to_latent(symbols: np.ndarray, manifest: dict[str, Any]) -> np.ndarray:
    n_real = int(manifest["n_real"])
    n_complex = int(manifest["n_complex"])
    shape = tuple(int(v) for v in manifest["shape"])
    real_rms = float(manifest["real_rms"])
    symbols = np.asarray(symbols[:n_complex], dtype=np.complex64)
    flat = np.empty(n_complex * 2, dtype=np.float32)
    flat[0::2] = np.real(symbols)
    flat[1::2] = np.imag(symbols)
    flat = flat[:n_real] * np.float32(real_rms)
    return flat.reshape(shape).astype(np.float32, copy=False)


def build_frame_symbols(data_symbols: np.ndarray, manifest: dict[str, Any]) -> np.ndarray:
    cfo = make_pilot_symbols(int(manifest["cfo_pilot_symbols"]), int(manifest["cfo_seed"]))
    sync = make_pilot_symbols(int(manifest["sync_pilot_symbols"]), int(manifest["sync_seed"]))
    mid = make_pilot_symbols(int(manifest["mid_pilot_symbols"]), int(manifest["mid_pilot_seed"]))
    block = int(manifest["data_block_symbols"])

    parts: list[np.ndarray] = [cfo, cfo, sync]
    block_lengths: list[int] = []
    pos = 0
    while pos < len(data_symbols):
        take = min(block, len(data_symbols) - pos)
        parts.append(data_symbols[pos:pos + take])
        block_lengths.append(int(take))
        pos += take
        if pos < len(data_symbols) and len(mid) > 0:
            parts.append(mid)
    manifest["data_block_lengths"] = block_lengths
    manifest["frame_symbols"] = int(sum(len(part) for part in parts))
    return np.concatenate(parts).astype(np.complex64)


def symbols_to_rrc_waveform(symbols: np.ndarray, taps: np.ndarray, sps: int) -> np.ndarray:
    upsampled = np.zeros(len(symbols) * int(sps), dtype=np.complex64)
    upsampled[:: int(sps)] = symbols
    return np.convolve(upsampled, taps.astype(np.float32), mode="full").astype(np.complex64)


def waveform_to_sc16(wave: np.ndarray, amplitude: int) -> tuple[np.ndarray, float, float]:
    peak = float(np.max(np.abs(wave)) + 1.0e-8)
    normalized = wave / np.float32(peak)
    i = np.clip(np.real(normalized) * float(amplitude), -32767, 32767).astype(np.int16)
    q = np.clip(np.imag(normalized) * float(amplitude), -32767, 32767).astype(np.int16)
    interleaved = np.empty(i.size * 2, dtype=np.int16)
    interleaved[0::2] = i
    interleaved[1::2] = q
    clipping_ratio = float(np.mean((np.abs(i) >= 32767) | (np.abs(q) >= 32767)))
    return interleaved, peak, clipping_ratio


def normalized_complex_to_sc16(wave: np.ndarray, amplitude: int) -> tuple[np.ndarray, float]:
    i = np.clip(np.real(wave) * float(amplitude), -32767, 32767).astype(np.int16)
    q = np.clip(np.imag(wave) * float(amplitude), -32767, 32767).astype(np.int16)
    interleaved = np.empty(i.size * 2, dtype=np.int16)
    interleaved[0::2] = i
    interleaved[1::2] = q
    clipping_ratio = float(np.mean((np.abs(i) >= 32767) | (np.abs(q) >= 32767))) if i.size else 0.0
    return interleaved, clipping_ratio


def write_sc16(path: Path, interleaved: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    interleaved.astype(np.int16, copy=False).tofile(path)


def read_sc16_raw(path: Path) -> tuple[np.ndarray, float]:
    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2:
        raise ValueError(f"sc16 file has odd int16 count: {path}")
    clipping_ratio = float(np.mean((np.abs(raw[0::2]) >= 32767) | (np.abs(raw[1::2]) >= 32767))) if raw.size else 0.0
    return raw, clipping_ratio


def sc16_raw_to_complex(
    raw: np.ndarray,
    amplitude: int,
    *,
    sample_start: int = 0,
    sample_end: int | None = None,
    dc: complex = 0.0j,
) -> np.ndarray:
    total_samples = int(raw.size // 2)
    start = max(0, min(int(sample_start), total_samples))
    end = total_samples if sample_end is None else max(start, min(int(sample_end), total_samples))
    raw_slice = raw[start * 2:end * 2]
    complex_rx = raw_slice[0::2].astype(np.float32) + 1j * raw_slice[1::2].astype(np.float32)
    rx = (complex_rx / np.float32(amplitude)).astype(np.complex64)
    if abs(dc) > 0.0:
        rx = (rx - np.complex64(dc)).astype(np.complex64)
    return rx


def estimate_dc_from_sc16_raw(raw: np.ndarray, sample_count: int, amplitude: int) -> complex:
    count = min(max(int(sample_count), 1), int(raw.size // 2))
    if count <= 0:
        return complex(0.0, 0.0)
    window = raw[:count * 2]
    return complex(float(np.mean(window[0::2])) / float(amplitude), float(np.mean(window[1::2])) / float(amplitude))


def sc16_to_complex(path: Path, amplitude: int) -> tuple[np.ndarray, float]:
    raw, clipping_ratio = read_sc16_raw(path)
    complex_rx = sc16_raw_to_complex(raw, amplitude)
    return complex_rx, clipping_ratio


def sc16_power(raw: np.ndarray, amplitude: int, *, dc: complex = 0.0j, decimation: int = 1) -> np.ndarray:
    step = max(1, int(decimation))
    pairs = raw.reshape(-1, 2)[::step]
    i = pairs[:, 0].astype(np.float32) / np.float32(amplitude)
    q = pairs[:, 1].astype(np.float32) / np.float32(amplitude)
    if abs(dc) > 0.0:
        i = i - np.float32(np.real(dc))
        q = q - np.float32(np.imag(dc))
    return (i * i + q * q).astype(np.float32, copy=False)

def matched_filter(rx: np.ndarray, taps: np.ndarray) -> np.ndarray:
    return np.convolve(rx, np.conj(taps[::-1]), mode="same").astype(np.complex64)


def expected_symbols_after_sync(manifest: dict[str, Any]) -> int:
    sync_len = int(manifest["sync_pilot_symbols"])
    mid_len = int(manifest["mid_pilot_symbols"])
    block_lengths = [int(v) for v in manifest.get("data_block_lengths", [])]
    if not block_lengths:
        n_complex = int(manifest.get("n_complex", 0))
        block = max(int(manifest.get("data_block_symbols", 1)), 1)
        block_lengths = [min(block, n_complex - pos) for pos in range(0, n_complex, block)]
    return int(sync_len + sum(block_lengths) + max(0, len(block_lengths) - 1) * mid_len)


def sync_candidate_has_complete_frame(candidate: dict[str, Any], manifest: dict[str, Any]) -> bool:
    cfo_len = int(manifest["cfo_pilot_symbols"])
    start = int(candidate["sync_start"])
    if start < 2 * cfo_len:
        return False
    return start + expected_symbols_after_sync(manifest) <= int(candidate["sym_stream"].size)


def annotate_sync_candidate(candidate: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    if manifest is None:
        candidate["frame_complete"] = True
        return candidate
    candidate["frame_complete"] = bool(sync_candidate_has_complete_frame(candidate, manifest))
    candidate["expected_symbols_after_sync"] = int(expected_symbols_after_sync(manifest))
    return candidate


def find_sync_candidates(
    mf: np.ndarray,
    sync: np.ndarray,
    sps: int,
    *,
    max_candidates: int = DEFAULT_SYNC_CANDIDATES,
    manifest: dict[str, Any] | None = None,
    search_center_symbol: int | None = None,
    search_window_symbols: int = 0,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sync_energy = float(np.vdot(sync, sync).real)
    if sync_energy <= 0.0:
        raise ValueError("sync pilot has zero energy")

    for phase in range(int(sps)):
        stream = mf[phase:: int(sps)]
        if stream.size < sync.size:
            continue
        valid_count = int(stream.size - sync.size + 1)
        search_start = 0
        search_end = valid_count
        if search_center_symbol is not None and int(search_window_symbols) > 0:
            half_window = max(1, int(search_window_symbols)) // 2
            search_start = max(0, int(search_center_symbol) - half_window)
            search_end = min(valid_count, int(search_center_symbol) + half_window + 1)
        if search_end <= search_start:
            continue
        search_stream = stream[search_start:search_end + sync.size - 1]
        corr, corr_method = sync_correlation(search_stream, sync)
        if corr.size == 0:
            continue
        take = min(max(1, int(max_candidates)), int(corr.size))
        if take == corr.size:
            top_indices = np.arange(corr.size)
        else:
            top_indices = np.argpartition(corr, -take)[-take:]
        for raw_idx in top_indices:
            corr_idx = int(raw_idx)
            idx = corr_idx + search_start
            window = stream[idx:idx + sync.size]
            rx_energy = float(np.vdot(window, window).real)
            metric = float(corr[corr_idx] / math.sqrt(max(rx_energy * sync_energy, EPS)))
            candidate = {
                "phase": int(phase),
                "sync_start": idx,
                "sync_metric": metric,
                "sync_corr": float(corr[corr_idx]),
                "sync_correlation_method": corr_method,
                "sym_stream": stream,
                "search_start_symbol": int(search_start),
                "search_end_symbol": int(search_end),
            }
            candidates.append(annotate_sync_candidate(candidate, manifest))

    candidates.sort(
        key=lambda item: (
            bool(item.get("frame_complete", True)),
            float(item["sync_metric"]),
            -int(item["sync_start"]),
        ),
        reverse=True,
    )
    return candidates[: max(1, int(max_candidates))]


def find_sync(mf: np.ndarray, sync: np.ndarray, sps: int, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    candidates = find_sync_candidates(mf, sync, sps, max_candidates=1, manifest=manifest)
    if not candidates:
        raise RuntimeError("sync search failed: capture shorter than sync pilot")
    return candidates[0]


def sync_window_sample_range(
    total_samples: int,
    manifest: dict[str, Any],
    taps: np.ndarray,
    *,
    search_center_symbol: int | None,
    search_window_symbols: int,
    sps: int,
) -> tuple[int, int, int, dict[str, Any]] | None:
    if search_center_symbol is None or int(search_window_symbols) <= 0:
        return None

    total_symbols = int(math.ceil(float(total_samples) / float(max(int(sps), 1))))
    half_window = max(1, int(search_window_symbols)) // 2
    center = max(0, int(search_center_symbol))
    search_start = max(0, center - half_window)
    search_end = min(total_symbols, center + half_window + 1)
    cfo_len = int(manifest.get("cfo_pilot_symbols") or 0)
    pre_symbols = max(2 * cfo_len + 256, 256)
    post_symbols = max(expected_symbols_after_sync(manifest) + 256, 256)
    crop_start_symbol = max(0, search_start - pre_symbols)
    crop_end_symbol = min(total_symbols, search_end + post_symbols)

    tap_margin = int(max(taps.size, 1))
    sample_start = max(0, crop_start_symbol * int(sps) - tap_margin)
    sample_start -= sample_start % max(int(sps), 1)
    sample_end = min(int(total_samples), crop_end_symbol * int(sps) + tap_margin)
    if sample_end <= sample_start:
        return None

    symbol_offset = int(sample_start // max(int(sps), 1))
    return sample_start, sample_end, symbol_offset, {
        "sync_search_window_enabled": True,
        "sync_search_center_symbol": int(center),
        "sync_search_center_source": "manual",
        "sync_search_window_symbols": int(search_window_symbols),
        "sync_search_crop_start_symbol": int(symbol_offset),
        "sync_search_crop_end_symbol": int(math.ceil(float(sample_end) / float(max(int(sps), 1)))),
        "sync_search_original_samples": int(total_samples),
        "sync_search_cropped_samples": int(sample_end - sample_start),
    }


def crop_rx_for_sync_window(
    rx: np.ndarray,
    manifest: dict[str, Any],
    taps: np.ndarray,
    *,
    search_center_symbol: int | None,
    search_window_symbols: int,
    sps: int,
) -> tuple[np.ndarray, int, dict[str, Any]]:
    crop = sync_window_sample_range(
        int(rx.size),
        manifest,
        taps,
        search_center_symbol=search_center_symbol,
        search_window_symbols=search_window_symbols,
        sps=sps,
    )
    if crop is None:
        return rx, 0, {
            "sync_search_window_enabled": False,
        }
    sample_start, sample_end, symbol_offset, metrics = crop
    return rx[sample_start:sample_end].astype(np.complex64, copy=False), symbol_offset, metrics


def estimate_sync_center_from_power(
    power: np.ndarray,
    manifest: dict[str, Any],
    *,
    sps: int,
    sample_decimation: int = 1,
) -> tuple[int | None, dict[str, Any]]:
    decimation = max(1, int(sample_decimation))
    if power.size == 0:
        return None, {"sync_search_center_source": "none", "sync_search_center_error": "empty rx"}
    window_samples = max(64, int(sps) * 32)
    window = max(1, int(math.ceil(float(window_samples) / float(decimation))))
    if power.size < window:
        return None, {"sync_search_center_source": "none", "sync_search_center_error": "rx shorter than power window"}
    cumsum = np.concatenate([np.zeros(1, dtype=np.float64), np.cumsum(power, dtype=np.float64)])
    smooth = (cumsum[window:] - cumsum[:-window]) / float(window)
    if smooth.size == 0:
        return None, {"sync_search_center_source": "none", "sync_search_center_error": "empty power envelope"}
    peak = float(np.max(smooth))
    if peak <= EPS:
        return None, {"sync_search_center_source": "none", "sync_search_center_error": "zero power envelope"}
    floor = float(np.median(smooth))
    threshold = max(peak * 0.05, floor * 8.0)
    active = np.flatnonzero(smooth >= threshold)
    if active.size == 0:
        return None, {
            "sync_search_center_source": "none",
            "sync_search_center_error": "burst threshold not crossed",
            "sync_search_burst_power_peak": peak,
            "sync_search_burst_power_floor": floor,
            "sync_search_burst_power_threshold": threshold,
        }
    active_start_sample = max(0, int(active[0]) * decimation - window_samples // 2)
    center = active_start_sample // max(int(sps), 1) + 2 * int(manifest.get("cfo_pilot_symbols") or 0)
    return int(center), {
        "sync_search_center_source": "burst_power",
        "sync_search_burst_start_sample": int(active_start_sample),
        "sync_search_burst_power_peak": peak,
        "sync_search_burst_power_floor": floor,
        "sync_search_burst_power_threshold": threshold,
        "sync_search_power_decimation": int(decimation),
    }


def estimate_sync_center_from_burst_power(rx: np.ndarray, manifest: dict[str, Any], *, sps: int) -> tuple[int | None, dict[str, Any]]:
    power = np.square(np.abs(np.asarray(rx, dtype=np.complex64))).astype(np.float32, copy=False)
    return estimate_sync_center_from_power(power, manifest, sps=sps, sample_decimation=1)


def estimate_sync_center_from_sc16_power(
    raw: np.ndarray,
    manifest: dict[str, Any],
    *,
    sps: int,
    amplitude: int,
    dc: complex,
    decimation: int = DEFAULT_SYNC_POWER_DECIMATION,
) -> tuple[int | None, dict[str, Any]]:
    step = max(1, int(decimation))
    return estimate_sync_center_from_power(
        sc16_power(raw, amplitude, dc=dc, decimation=step),
        manifest,
        sps=sps,
        sample_decimation=step,
    )


def estimate_cfo_from_repeated_pilot(sym_stream: np.ndarray, sync_start: int, cfo_len: int, rate: float, sps: int) -> float:
    if cfo_len <= 0 or sync_start < 2 * cfo_len:
        return 0.0
    left = sym_stream[sync_start - 2 * cfo_len:sync_start - cfo_len]
    right = sym_stream[sync_start - cfo_len:sync_start]
    if left.size != cfo_len or right.size != cfo_len:
        return 0.0
    phase = float(np.angle(np.vdot(left, right)))
    symbol_rate = float(rate) / float(sps)
    return phase / (2.0 * math.pi * (float(cfo_len) / symbol_rate))


def correct_cfo(rx: np.ndarray, cfo_hz: float, rate: float) -> np.ndarray:
    if abs(cfo_hz) < 1.0e-9:
        return rx
    n = np.arange(rx.size, dtype=np.float64)
    rot = np.exp(-1j * 2.0 * math.pi * float(cfo_hz) * n / float(rate))
    return (rx * rot.astype(np.complex64)).astype(np.complex64)


def estimate_cfo_from_known_pilot(
    sym_stream: np.ndarray,
    sync_start: int,
    cfo_len: int,
    rate: float,
    sps: int,
    cfo_seed: int,
) -> tuple[float, str]:
    if cfo_len <= 0 or sync_start < 2 * cfo_len:
        return 0.0, "none"
    rx_pilot = sym_stream[sync_start - 2 * cfo_len:sync_start]
    if rx_pilot.size != 2 * cfo_len:
        return 0.0, "none"

    cfo = make_pilot_symbols(cfo_len, cfo_seed)
    tx_pilot = np.concatenate([cfo, cfo]).astype(np.complex64)
    derotated = rx_pilot * np.conj(tx_pilot)
    valid = np.abs(derotated) > EPS
    if int(np.count_nonzero(valid)) < 4:
        fallback = estimate_cfo_from_repeated_pilot(sym_stream, sync_start, cfo_len, rate, sps)
        return fallback, "repeated-pilot"

    n = np.arange(derotated.size, dtype=np.float64)[valid]
    phase = np.unwrap(np.angle(derotated[valid]).astype(np.float64))
    slope, _intercept = np.polyfit(n, phase, 1)
    symbol_rate = float(rate) / float(sps)
    return float(slope * symbol_rate / (2.0 * math.pi)), "known-pilot-phase-slope"


def estimate_channel_gain(tx: np.ndarray, rx: np.ndarray) -> complex:
    if tx.size == 0 or rx.size < tx.size:
        return complex(1.0, 0.0)
    numerator = np.vdot(tx, rx[:tx.size])
    denominator = np.vdot(tx, tx)
    if abs(denominator) <= EPS:
        return complex(1.0, 0.0)
    gain = numerator / denominator
    if abs(gain) <= EPS:
        return complex(1.0, 0.0)
    return complex(gain)


def interpolate_complex_gain(start_gain: complex, end_gain: complex, count: int) -> np.ndarray:
    if count <= 0:
        return np.zeros(0, dtype=np.complex64)
    if abs(start_gain) <= EPS or abs(end_gain) <= EPS:
        return np.full(count, start_gain if abs(start_gain) > EPS else complex(1.0, 0.0), dtype=np.complex64)
    alpha = (np.arange(count, dtype=np.float32) + np.float32(1.0)) / np.float32(count + 1)
    start_abs = float(abs(start_gain))
    end_abs = float(abs(end_gain))
    start_phase = float(np.angle(start_gain))
    phase_delta = float(np.angle(end_gain / start_gain))
    amp = (np.float32(1.0) - alpha) * np.float32(start_abs) + alpha * np.float32(end_abs)
    phase = np.float32(start_phase) + alpha * np.float32(phase_delta)
    return (amp * np.exp(1j * phase)).astype(np.complex64)


def recover_payload_symbols(sym_stream: np.ndarray, sync_start: int, manifest: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    cfo_len = int(manifest["cfo_pilot_symbols"])
    sync_len = int(manifest["sync_pilot_symbols"])
    mid_len = int(manifest["mid_pilot_symbols"])
    cfo = make_pilot_symbols(cfo_len, int(manifest["cfo_seed"]))
    sync = make_pilot_symbols(sync_len, int(manifest["sync_seed"]))
    mid = make_pilot_symbols(mid_len, int(manifest["mid_pilot_seed"]))
    block_lengths = [int(v) for v in manifest["data_block_lengths"]]

    sync_rx = sym_stream[sync_start:sync_start + sync_len]
    if sync_rx.size < sync_len:
        raise RuntimeError("sync pilot extends beyond symbol stream")
    if sync_start >= 2 * cfo_len and cfo_len > 0:
        pilot_tx = np.concatenate([cfo, cfo, sync])
        pilot_rx = sym_stream[sync_start - 2 * cfo_len:sync_start + sync_len]
        current_gain = estimate_channel_gain(pilot_tx, pilot_rx)
    else:
        current_gain = estimate_channel_gain(sync, sync_rx)
    gains = [current_gain]
    phase_corrections: list[dict[str, Any]] = []
    payload_blocks: list[np.ndarray] = []
    cursor = sync_start + sync_len

    for block_idx, block_len in enumerate(block_lengths):
        block_rx = sym_stream[cursor:cursor + block_len]
        if block_rx.size < block_len:
            raise RuntimeError(f"payload block {block_idx} extends beyond symbol stream")

        has_next_mid = block_idx != len(block_lengths) - 1 and mid_len > 0
        next_gain = current_gain
        if has_next_mid:
            mid_cursor = cursor + block_len
            mid_rx = sym_stream[mid_cursor:mid_cursor + mid_len]
            if mid_rx.size < mid_len:
                raise RuntimeError(f"mid pilot {block_idx} extends beyond symbol stream")
            next_gain = estimate_channel_gain(mid, mid_rx)
            if abs(next_gain) <= EPS:
                next_gain = current_gain
            gain_track = interpolate_complex_gain(current_gain, next_gain, block_len)
            payload_blocks.append((block_rx / gain_track).astype(np.complex64))
            phase_corrections.append({
                "block": int(block_idx),
                "mode": "linear-mid-pilot",
                "start_phase_deg": float(np.degrees(np.angle(current_gain))),
                "end_phase_deg": float(np.degrees(np.angle(next_gain))),
                "start_abs": float(abs(current_gain)),
                "end_abs": float(abs(next_gain)),
            })
            current_gain = next_gain
            gains.append(current_gain)
            cursor = mid_cursor + mid_len
        else:
            payload_blocks.append((block_rx / np.complex64(current_gain)).astype(np.complex64))
            phase_corrections.append({
                "block": int(block_idx),
                "mode": "constant-pilot-gain",
                "start_phase_deg": float(np.degrees(np.angle(current_gain))),
                "end_phase_deg": float(np.degrees(np.angle(current_gain))),
                "start_abs": float(abs(current_gain)),
                "end_abs": float(abs(current_gain)),
            })
            cursor += block_len

    payload = np.concatenate(payload_blocks).astype(np.complex64) if payload_blocks else np.zeros(0, dtype=np.complex64)
    metrics = {
        "data_start_symbol": int(sync_start + sync_len),
        "data_end_symbol": int(cursor),
        "channel_gain_real": float(np.real(gains[0])),
        "channel_gain_imag": float(np.imag(gains[0])),
        "channel_gain_abs": float(abs(gains[0])),
        "pilot_gains": [
            {"real": float(np.real(gain)), "imag": float(np.imag(gain)), "abs": float(abs(gain))}
            for gain in gains
        ],
        "phase_tracking_mode": "linear-mid-pilot" if len(gains) > 1 and mid_len > 0 else "constant-pilot-gain",
        "phase_corrections": phase_corrections,
    }
    return payload, metrics


def parse_scramble_key(args: argparse.Namespace) -> bytes:
    key = str(getattr(args, "scramble_key", "") or "")
    key_hex = str(getattr(args, "scramble_key_hex", "") or "")
    if key and key_hex:
        raise RuntimeError("use only one of --scramble-key or --scramble-key-hex")
    if key_hex:
        try:
            return bytes.fromhex("".join(key_hex.split()))
        except ValueError as exc:
            raise RuntimeError("--scramble-key-hex is not valid hex") from exc
    if key:
        return key.encode("utf-8")
    return b""


def scramble_key_fingerprint(key_bytes: bytes) -> str:
    return hashlib.sha256(key_bytes).hexdigest()


def scramble_seed_digest(key_bytes: bytes, job_id: str, context: str, n_symbols: int) -> bytes:
    h = hashlib.sha512()
    h.update(b"analog-latent-iq-scramble-v1\x00")
    h.update(str(job_id).encode("utf-8"))
    h.update(b"\x00")
    h.update(str(context).encode("utf-8"))
    h.update(b"\x00")
    h.update(str(int(n_symbols)).encode("ascii"))
    h.update(b"\x00")
    h.update(key_bytes)
    return h.digest()


def make_scrambler(n_symbols: int, key_bytes: bytes, job_id: str, context: str) -> tuple[np.ndarray, np.ndarray, str]:
    digest = scramble_seed_digest(key_bytes, job_id, context, n_symbols)
    entropy = np.frombuffer(digest[:32], dtype=np.uint32).astype(np.uint32).tolist()
    rng = np.random.default_rng(np.random.SeedSequence(entropy))
    perm = rng.permutation(int(n_symbols)).astype(np.int64)
    sign = rng.choice(np.asarray([-1.0, 1.0], dtype=np.float32), size=int(n_symbols)).astype(np.float32)
    return perm, sign, hashlib.sha256(digest).hexdigest()


def apply_symbol_scrambling(symbols: np.ndarray, key_bytes: bytes, job_id: str, context: str) -> tuple[np.ndarray, dict[str, Any]]:
    perm, sign, seed_sha = make_scrambler(len(symbols), key_bytes, job_id, context)
    scrambled = (sign.astype(np.complex64) * symbols[perm]).astype(np.complex64)
    meta = {
        "scrambling_enabled": True,
        "scrambling_mode": SCRAMBLING_MODE,
        "scrambling_context": context,
        "scrambling_key_sha256": scramble_key_fingerprint(key_bytes),
        "scrambling_seed_sha256": seed_sha,
    }
    return scrambled, meta


def maybe_unscramble_symbols(symbols: np.ndarray, manifest: dict[str, Any], args: argparse.Namespace) -> tuple[np.ndarray, dict[str, Any]]:
    enabled = bool(manifest.get("scrambling_enabled", False))
    if not enabled:
        return symbols.astype(np.complex64, copy=False), {
            "scrambling_enabled": False,
            "scrambling_mode": "none",
        }
    if manifest.get("scrambling_mode") != SCRAMBLING_MODE:
        raise RuntimeError(f"unsupported scrambling mode: {manifest.get('scrambling_mode')}")
    key_bytes = parse_scramble_key(args)
    if not key_bytes:
        raise RuntimeError("manifest requires a scramble key; pass --scramble-key or --scramble-key-hex")
    expected_fingerprint = str(manifest.get("scrambling_key_sha256") or "")
    actual_fingerprint = scramble_key_fingerprint(key_bytes)
    if expected_fingerprint and actual_fingerprint != expected_fingerprint:
        raise RuntimeError("scramble key fingerprint does not match manifest")
    context = str(getattr(args, "scramble_context", "") or manifest.get("scrambling_context") or "")
    perm, sign, seed_sha = make_scrambler(
        int(manifest["n_complex"]),
        key_bytes,
        str(manifest.get("job_id") or "analog_latent"),
        context,
    )
    expected_seed_sha = str(manifest.get("scrambling_seed_sha256") or "")
    if expected_seed_sha and seed_sha != expected_seed_sha:
        raise RuntimeError("scramble key/context does not match manifest")
    usable = np.asarray(symbols[: int(manifest["n_complex"])], dtype=np.complex64)
    restored = np.empty_like(usable)
    restored[perm] = sign.astype(np.complex64) * usable
    return restored.astype(np.complex64), {
        "scrambling_enabled": True,
        "scrambling_mode": SCRAMBLING_MODE,
        "scrambling_context": context,
        "scrambling_seed_sha256": seed_sha,
    }


def quantize_dequantize(latent: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    arr = np.asarray(latent, dtype=np.float32)
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    if max_val - min_val <= 1.0e-12:
        scale = 1.0
        zero_point = 0.0
        quant = np.zeros(arr.shape, dtype=np.uint8)
    else:
        scale = float((max_val - min_val) / 255.0)
        zero_point = float(np.clip(np.round(-min_val / scale), 0.0, 255.0))
        quant = np.clip(np.round(arr / scale + zero_point), 0.0, 255.0).astype(np.uint8)
    dequant = (quant.astype(np.float32) - np.float32(zero_point)) * np.float32(scale)
    return dequant.astype(np.float32, copy=False), {
        "quant": quant,
        "scale": np.asarray(scale, dtype=np.float32),
        "zero_point": np.asarray(zero_point, dtype=np.float32),
    }


def pack_received_wire_blob(latent: np.ndarray, manifest: dict[str, Any], summary: dict[str, Any]) -> bytes:
    latent = np.asarray(latent, dtype=np.float32)
    payload_bytes = latent.astype(np.float32, copy=False).tobytes()
    payload_sha = sha256_bytes(payload_bytes)
    meta = {
        "job_id": str(manifest.get("job_id") or "analog_latent"),
        "shape": list(latent.shape),
        "dtype": "float32",
        "payload_codec": "float32-raw",
        "sha256": payload_sha,
        "size": len(payload_bytes),
        "latent_sha256": payload_sha,
        "latent_size": len(payload_bytes),
        "phy": "analog-latent-iq",
        "payload_is_bit_exact": False,
        "rx_post_quantize": bool(manifest.get("rx_post_quantize", True)),
        "sync_success": bool(summary.get("sync_success", False)),
    }
    return pack_transport_frame(meta, payload_bytes)


def reference_symbols_from_manifest(manifest: dict[str, Any]) -> tuple[np.ndarray | None, np.ndarray | None]:
    source_path = str(manifest.get("source_path") or "")
    if not source_path:
        return None, None
    path = Path(source_path)
    if not path.is_file():
        return None, None
    try:
        latent, _info = load_latent(path)
        symbols, _latent_info = latent_to_complex_symbols(latent)
        return latent, symbols
    except Exception:
        return None, None


def symbol_quality_metrics(reference: np.ndarray | None, recovered: np.ndarray) -> dict[str, Any]:
    if reference is None or reference.size == 0 or recovered.size == 0:
        return {
            "evm_rms": None,
            "estimated_snr_db": None,
        }
    usable = min(reference.size, recovered.size)
    ref = np.asarray(reference[:usable], dtype=np.complex64)
    got = np.asarray(recovered[:usable], dtype=np.complex64)
    ref_power = float(np.mean(np.square(np.abs(ref), dtype=np.float64)))
    err_power = float(np.mean(np.square(np.abs(got - ref), dtype=np.float64)))
    if ref_power <= EPS:
        return {
            "evm_rms": None,
            "estimated_snr_db": None,
        }
    evm = math.sqrt(max(err_power, 0.0) / ref_power)
    snr_db = 99.0 if err_power <= EPS else 10.0 * math.log10(ref_power / err_power)
    return {
        "evm_rms": float(evm),
        "estimated_snr_db": float(snr_db),
        "reference_symbol_power": ref_power,
        "error_symbol_power": err_power,
    }


def latent_mse_metric(reference: np.ndarray | None, recovered: np.ndarray) -> dict[str, Any]:
    if reference is None or tuple(reference.shape) != tuple(recovered.shape):
        return {"latent_mse_vs_tx": None}
    return {
        "latent_mse_vs_tx": float(np.mean(np.square(np.asarray(recovered, dtype=np.float32) - np.asarray(reference, dtype=np.float32))))
    }


def make_waveform(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    out_sc16 = Path(args.out_sc16)
    manifest_path = Path(args.manifest)
    latent, source_info = load_latent(input_path)
    data_symbols, latent_info = latent_to_complex_symbols(latent)
    job_id = args.job_id or input_path.stem
    scramble_key = parse_scramble_key(args)
    scramble_context = str(getattr(args, "scramble_context", "") or "")
    scramble_meta: dict[str, Any]
    if scramble_key:
        data_symbols, scramble_meta = apply_symbol_scrambling(data_symbols, scramble_key, job_id, scramble_context)
    else:
        scramble_meta = {
            "scrambling_enabled": False,
            "scrambling_mode": "none",
            "scrambling_context": scramble_context,
        }
    manifest: dict[str, Any] = {
        "version": 1,
        "phy": "analog-latent-iq",
        "job_id": job_id,
        "shape": list(latent.shape),
        "dtype": "float32",
        "normalization": "global_real_rms",
        "sample_rate": float(args.rate),
        "sps": int(args.sps),
        "rrc_beta": float(args.rrc_beta),
        "rrc_span": int(args.rrc_span),
        "sc16_amplitude": int(args.amp),
        "zero_guard_samples": int(args.zero_guard_samples),
        "tail_guard_samples": int(args.tail_guard_samples),
        "cfo_pilot_symbols": int(args.cfo_pilot_symbols),
        "sync_pilot_symbols": int(args.sync_pilot_symbols),
        "data_block_symbols": int(args.data_block_symbols),
        "mid_pilot_symbols": int(args.mid_pilot_symbols),
        "cfo_seed": int(args.cfo_seed),
        "sync_seed": int(args.sync_seed),
        "mid_pilot_seed": int(args.mid_pilot_seed),
        "rx_post_quantize": bool(args.rx_post_quantize),
        "payload_is_bit_exact": False,
        "source_path": str(input_path),
        "source_info": source_info,
        "tx_latent_sha256": sha256_bytes(latent.astype(np.float32, copy=False).tobytes()),
        "payload_symbol_rms": float(np.sqrt(np.mean(np.square(np.abs(data_symbols), dtype=np.float64)))),
        **latent_info,
        **scramble_meta,
    }

    frame_symbols = build_frame_symbols(data_symbols, manifest)
    taps = rrc_taps(float(args.rrc_beta), int(args.rrc_span), int(args.sps))
    shaped = symbols_to_rrc_waveform(frame_symbols, taps, int(args.sps))
    guarded = np.concatenate(
        [
            np.zeros(int(args.zero_guard_samples), dtype=np.complex64),
            shaped,
            np.zeros(int(args.tail_guard_samples), dtype=np.complex64),
        ]
    )
    interleaved, peak, clipping_ratio = waveform_to_sc16(guarded, int(args.amp))
    write_sc16(out_sc16, interleaved)

    waveform_samples = int(interleaved.size // 2)
    manifest.update({
        "rrc_tap_count": int(taps.size),
        "tx_waveform_samples": waveform_samples,
        "waveform_samples": waveform_samples,
        "capture_nsamps": int(waveform_samples + int(args.capture_margin_samples)),
        "capture_margin_samples": int(args.capture_margin_samples),
        "tx_peak": peak,
        "tx_clipping_ratio": clipping_ratio,
        "airtime_ms": float(1000.0 * waveform_samples / float(args.rate)),
        "symbol_rate": float(args.rate) / float(args.sps),
        "out_sc16": str(out_sc16),
    })
    write_json(manifest_path, manifest)
    return manifest


def decode_waveform(args: argparse.Namespace) -> dict[str, Any]:
    decode_start = time.perf_counter()
    timing_last = decode_start
    decode_timing_ms: dict[str, float] = {}

    def mark_timing(name: str) -> None:
        nonlocal timing_last
        now = time.perf_counter()
        decode_timing_ms[name] = float((now - timing_last) * 1000.0)
        timing_last = now

    rx_sc16 = Path(args.rx_sc16)
    manifest = read_json(Path(args.manifest))
    out_npz = Path(args.out_npz)
    out_wire = Path(args.out_wire) if args.out_wire else None
    summary_path = Path(args.summary_json) if args.summary_json else None

    rate = float(manifest["sample_rate"])
    sps = int(manifest["sps"])
    amp = int(manifest["sc16_amplitude"])
    zero_guard = int(manifest["zero_guard_samples"])
    sync = make_pilot_symbols(int(manifest["sync_pilot_symbols"]), int(manifest["sync_seed"]))
    cfo_len = int(manifest["cfo_pilot_symbols"])
    taps = rrc_taps(float(manifest["rrc_beta"]), int(manifest["rrc_span"]), sps)
    mark_timing("setup")

    sync_profile = str(getattr(args, "sync_profile", "") or "").strip().lower()
    if sync_profile in {"", "default", "normal"}:
        sync_profile = ""
    if sync_profile not in {"", "fast-first"}:
        raise RuntimeError(f"unsupported sync profile: {sync_profile}")
    max_candidates = int(getattr(args, "sync_candidates", DEFAULT_SYNC_CANDIDATES))
    fast_sync_candidates = int(getattr(args, "fast_sync_candidates", DEFAULT_FAST_SYNC_CANDIDATES) or DEFAULT_FAST_SYNC_CANDIDATES)
    fast_sync_search_window_symbols = int(
        getattr(args, "fast_sync_search_window_symbols", DEFAULT_FAST_SYNC_SEARCH_WINDOW_SYMBOLS)
        or DEFAULT_FAST_SYNC_SEARCH_WINDOW_SYMBOLS
    )
    fallback_sync_candidates = int(
        getattr(args, "fallback_sync_candidates", DEFAULT_FALLBACK_SYNC_CANDIDATES)
        or DEFAULT_FALLBACK_SYNC_CANDIDATES
    )
    fallback_sync_search_window_symbols = int(
        getattr(args, "fallback_sync_search_window_symbols", DEFAULT_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS)
        or DEFAULT_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS
    )
    min_sync_metric = float(getattr(args, "min_sync_metric", DEFAULT_MIN_SYNC_METRIC))
    retry_on_burst_miss = bool(getattr(args, "retry_on_burst_miss", False))
    retry_on_low_sync = bool(getattr(args, "retry_on_low_sync", False))
    low_sync_retry_threshold = float(
        getattr(args, "low_sync_retry_threshold", DEFAULT_LOW_SYNC_RETRY_THRESHOLD)
        or DEFAULT_LOW_SYNC_RETRY_THRESHOLD
    )
    robust_enabled = bool(getattr(args, "robust_sync", True))
    raw_search_center = int(getattr(args, "sync_search_center_symbol", -1))
    search_window_symbols = int(getattr(args, "sync_search_window_symbols", 0) or 0)
    if sync_profile == "fast-first":
        search_window_symbols = max(
            search_window_symbols,
            fast_sync_search_window_symbols,
            fallback_sync_search_window_symbols,
        )
    search_center_symbol = raw_search_center if raw_search_center >= 0 and search_window_symbols > 0 else None
    center_metrics: dict[str, Any] = {}
    rx_search: np.ndarray | None = None
    sync_symbol_offset = 0
    crop_metrics: dict[str, Any] = {}
    dc = complex(0.0, 0.0)

    raw_sc16: np.ndarray | None = None
    rx_clipping_ratio = 0.0
    if search_window_symbols > 0:
        raw_sc16, rx_clipping_ratio = read_sc16_raw(rx_sc16)
        if raw_sc16.size == 0:
            raise RuntimeError(f"empty RX sc16 file: {rx_sc16}")
        mark_timing("read_sc16")
        dc = estimate_dc_from_sc16_raw(raw_sc16, zero_guard, amp)
        if search_center_symbol is None:
            search_center_symbol, center_metrics = estimate_sync_center_from_sc16_power(
                raw_sc16,
                manifest,
                sps=sps,
                amplitude=amp,
                dc=dc,
            )
            if (
                retry_on_burst_miss
                and sync_profile == "fast-first"
                and search_center_symbol is None
                and str(center_metrics.get("sync_search_center_error") or "") == "burst threshold not crossed"
            ):
                raise RuntimeError("burst threshold not crossed; retrying capture before full sync search")
        crop = sync_window_sample_range(
            int(raw_sc16.size // 2),
            manifest,
            taps,
            search_center_symbol=search_center_symbol,
            search_window_symbols=search_window_symbols,
            sps=sps,
        )
        if crop is not None:
            sample_start, sample_end, sync_symbol_offset, crop_metrics = crop
            rx_search = sc16_raw_to_complex(
                raw_sc16,
                amp,
                sample_start=sample_start,
                sample_end=sample_end,
                dc=dc,
            )
            crop_metrics["sync_search_raw_sc16_crop_enabled"] = True

    if rx_search is None:
        if raw_sc16 is None:
            rx, rx_clipping_ratio = sc16_to_complex(rx_sc16, amp)
            if rx.size == 0:
                raise RuntimeError(f"empty RX sc16 file: {rx_sc16}")
            mark_timing("read_sc16")
        else:
            rx = sc16_raw_to_complex(raw_sc16, amp)
        dc_window = rx[:min(max(zero_guard, 1), rx.size)]
        dc = complex(np.mean(dc_window))
        rx_dc = (rx - np.complex64(dc)).astype(np.complex64)
        if search_center_symbol is None and search_window_symbols > 0:
            search_center_symbol, center_metrics = estimate_sync_center_from_burst_power(rx_dc, manifest, sps=sps)
            if (
                retry_on_burst_miss
                and sync_profile == "fast-first"
                and search_center_symbol is None
                and str(center_metrics.get("sync_search_center_error") or "") == "burst threshold not crossed"
            ):
                raise RuntimeError("burst threshold not crossed; retrying capture before full sync search")
        rx_search, sync_symbol_offset, crop_metrics = crop_rx_for_sync_window(
            rx_dc,
            manifest,
            taps,
            search_center_symbol=search_center_symbol,
            search_window_symbols=search_window_symbols,
            sps=sps,
        )
        crop_metrics["sync_search_raw_sc16_crop_enabled"] = False
    if center_metrics:
        crop_metrics.update(center_metrics)
    mark_timing("dc_and_crop")
    local_search_center = (
        max(0, int(search_center_symbol) - int(sync_symbol_offset))
        if search_center_symbol is not None
        else None
    )
    mf0 = matched_filter(rx_search, taps)
    mark_timing("matched_filter")

    class SyncAttemptError(RuntimeError):
        def __init__(self, message: str, metrics: dict[str, Any]) -> None:
            super().__init__(message)
            self.metrics = metrics

    class LowSyncRetryRequest(RuntimeError):
        pass

    def run_sync_attempt(
        *,
        pass_name: str,
        pass_candidates: int,
        pass_window_symbols: int,
    ) -> dict[str, Any]:
        attempt_started = time.perf_counter()
        initial_ms = 0.0
        cfo_ms = 0.0
        initial_metric: float | None = None
        initial_count = 0
        try:
            initial_started = time.perf_counter()
            initial_candidates = find_sync_candidates(
                mf0,
                sync,
                sps,
                max_candidates=pass_candidates,
                manifest=manifest,
                search_center_symbol=local_search_center,
                search_window_symbols=pass_window_symbols,
            )
            initial_ms = float((time.perf_counter() - initial_started) * 1000.0)
            if not initial_candidates:
                raise RuntimeError("initial sync search failed")
            sync0 = initial_candidates[0]
            initial_count = int(len(initial_candidates))
            initial_metric = float(sync0["sync_metric"])
            if (
                retry_on_low_sync
                and sync_profile == "fast-first"
                and pass_name == "fast"
                and low_sync_retry_threshold > 0.0
                and initial_metric < low_sync_retry_threshold
            ):
                raise LowSyncRetryRequest(
                    f"low sync metric {initial_metric:.6f} below retry threshold "
                    f"{low_sync_retry_threshold:.6f}; retrying capture before fallback sync"
                )
            cfo_started = time.perf_counter()
            estimated_cfo_hz, cfo_method = estimate_cfo_from_known_pilot(
                sync0["sym_stream"],
                int(sync0["sync_start"]),
                cfo_len,
                rate,
                sps,
                int(manifest["cfo_seed"]),
            )
            if abs(estimated_cfo_hz) < 5.0:
                estimated_cfo_hz = 0.0
            cfo_ms = float((time.perf_counter() - cfo_started) * 1000.0)

            sync_search_mode = "normal"
            sync_debug: dict[str, Any] = {
                "sync_search_mode": sync_search_mode,
                "initial_sync_candidate_count": initial_count,
            }
            try:
                payload_symbols, payload_metrics, sync_final = recover_payload_with_fixed_cfo(
                    rx_search,
                    taps,
                    sync,
                    manifest,
                    cfo_hz=estimated_cfo_hz,
                    rate=rate,
                    sps=sps,
                    max_candidates=pass_candidates,
                    min_sync_metric=min_sync_metric,
                    search_center_symbol=local_search_center,
                    search_window_symbols=pass_window_symbols,
                )
            except RuntimeError as normal_exc:
                recovered_after_cfo_reject = False
                if abs(estimated_cfo_hz) >= 5.0 and float(sync0["sync_metric"]) >= min_sync_metric:
                    try:
                        payload_symbols, payload_metrics, sync_final = recover_payload_with_fixed_cfo(
                            rx_search,
                            taps,
                            sync,
                            manifest,
                            cfo_hz=0.0,
                            rate=rate,
                            sps=sps,
                            max_candidates=pass_candidates,
                            min_sync_metric=min_sync_metric,
                            search_center_symbol=local_search_center,
                            search_window_symbols=pass_window_symbols,
                        )
                        sync_debug["rejected_cfo_hz"] = float(estimated_cfo_hz)
                        sync_debug["rejected_cfo_error"] = str(normal_exc)
                        estimated_cfo_hz = 0.0
                        cfo_method = f"{cfo_method}/rejected"
                        sync_search_mode = "normal-cfo-rejected"
                        sync_debug["sync_search_mode"] = sync_search_mode
                    except RuntimeError:
                        pass
                    else:
                        recovered_after_cfo_reject = True
                if not recovered_after_cfo_reject and not robust_enabled:
                    raise
                if not recovered_after_cfo_reject and robust_enabled:
                    payload_symbols, payload_metrics, sync_final, estimated_cfo_hz, cfo_method, sync_debug = robust_cfo_grid_recover(
                        rx_search,
                        taps,
                        sync,
                        manifest,
                        rate=rate,
                        sps=sps,
                        max_candidates=pass_candidates,
                        min_sync_metric=min_sync_metric,
                        cfo_max_hz=float(getattr(args, "robust_cfo_max_hz", DEFAULT_ROBUST_CFO_MAX_HZ)),
                        cfo_step_hz=float(getattr(args, "robust_cfo_step_hz", DEFAULT_ROBUST_CFO_STEP_HZ)),
                        search_center_symbol=local_search_center,
                        search_window_symbols=pass_window_symbols,
                    )
                    sync_debug["normal_sync_error"] = str(normal_exc)
                    sync_search_mode = str(sync_debug["sync_search_mode"])
            elapsed_ms = float((time.perf_counter() - attempt_started) * 1000.0)
            return {
                "pass_name": pass_name,
                "pass_candidates": int(pass_candidates),
                "pass_window_symbols": int(pass_window_symbols),
                "elapsed_ms": elapsed_ms,
                "initial_sync_ms": initial_ms,
                "cfo_estimate_ms": cfo_ms,
                "payload_recovery_ms": max(0.0, elapsed_ms - initial_ms - cfo_ms),
                "initial_sync_metric": initial_metric,
                "sync_metric": float(sync_final["sync_metric"]),
                "sync0": sync0,
                "payload_symbols": payload_symbols,
                "payload_metrics": payload_metrics,
                "sync_final": sync_final,
                "estimated_cfo_hz": estimated_cfo_hz,
                "cfo_method": cfo_method,
                "sync_debug": sync_debug,
                "sync_search_mode": sync_search_mode,
            }
        except LowSyncRetryRequest:
            raise
        except RuntimeError as exc:
            elapsed_ms = float((time.perf_counter() - attempt_started) * 1000.0)
            raise SyncAttemptError(
                str(exc),
                {
                    "pass_name": pass_name,
                    "pass_candidates": int(pass_candidates),
                    "pass_window_symbols": int(pass_window_symbols),
                    "elapsed_ms": elapsed_ms,
                    "initial_sync_ms": initial_ms,
                    "cfo_estimate_ms": cfo_ms,
                    "initial_sync_metric": initial_metric,
                    "initial_sync_candidate_count": initial_count,
                    "error": str(exc),
                },
            ) from exc

    sync_pass_summary: dict[str, Any] = {}
    if sync_profile == "fast-first":
        try:
            selected_attempt = run_sync_attempt(
                pass_name="fast",
                pass_candidates=fast_sync_candidates,
                pass_window_symbols=fast_sync_search_window_symbols,
            )
            sync_pass_summary.update({
                "sync_profile": "fast-first",
                "sync_pass": 1,
                "fast_sync_metric": float(selected_attempt["sync_metric"]),
                "fallback_sync_metric": None,
                "selected_sync_metric": float(selected_attempt["sync_metric"]),
                "fast_sync_ms": round(float(selected_attempt["elapsed_ms"]), 3),
                "fallback_sync_ms": 0.0,
            })
        except SyncAttemptError as fast_exc:
            fallback_attempt = run_sync_attempt(
                pass_name="fallback",
                pass_candidates=fallback_sync_candidates,
                pass_window_symbols=fallback_sync_search_window_symbols,
            )
            selected_attempt = fallback_attempt
            sync_pass_summary.update({
                "sync_profile": "fast-first",
                "sync_pass": 2,
                "fast_sync_metric": fast_exc.metrics.get("initial_sync_metric"),
                "fallback_sync_metric": float(fallback_attempt["sync_metric"]),
                "selected_sync_metric": float(fallback_attempt["sync_metric"]),
                "fast_sync_ms": round(float(fast_exc.metrics["elapsed_ms"]), 3),
                "fallback_sync_ms": round(float(fallback_attempt["elapsed_ms"]), 3),
                "fast_sync_error": str(fast_exc),
            })
    else:
        selected_attempt = run_sync_attempt(
            pass_name="default",
            pass_candidates=max_candidates,
            pass_window_symbols=search_window_symbols,
        )

    sync0 = selected_attempt["sync0"]
    payload_symbols = selected_attempt["payload_symbols"]
    payload_metrics = selected_attempt["payload_metrics"]
    sync_final = selected_attempt["sync_final"]
    estimated_cfo_hz = float(selected_attempt["estimated_cfo_hz"])
    cfo_method = str(selected_attempt["cfo_method"])
    sync_debug = dict(selected_attempt["sync_debug"])
    sync_search_mode = str(selected_attempt["sync_search_mode"])
    decode_timing_ms["initial_sync"] = round(float(selected_attempt["initial_sync_ms"]), 3)
    decode_timing_ms["cfo_estimate"] = round(float(selected_attempt["cfo_estimate_ms"]), 3)
    decode_timing_ms["payload_recovery"] = round(float(selected_attempt["payload_recovery_ms"]), 3)
    timing_last = time.perf_counter()
    if sync_symbol_offset:
        payload_metrics["data_start_symbol_local"] = int(payload_metrics.get("data_start_symbol", 0))
        payload_metrics["data_end_symbol_local"] = int(payload_metrics.get("data_end_symbol", 0))
        payload_metrics["data_start_symbol"] = int(payload_metrics.get("data_start_symbol", 0)) + int(sync_symbol_offset)
        payload_metrics["data_end_symbol"] = int(payload_metrics.get("data_end_symbol", 0)) + int(sync_symbol_offset)
    n_complex = int(manifest["n_complex"])
    if payload_symbols.size < n_complex:
        raise RuntimeError(f"recovered {payload_symbols.size} symbols, expected {n_complex}")
    expected_symbol_rms = float(manifest.get("payload_symbol_rms") or 0.0)
    recovered_symbol_rms = float(np.sqrt(np.mean(np.square(np.abs(payload_symbols[:n_complex]), dtype=np.float64))))
    symbol_rms_gain = 1.0
    if expected_symbol_rms > 0.0 and recovered_symbol_rms > 0.0:
        symbol_rms_gain = expected_symbol_rms / recovered_symbol_rms
        payload_symbols = (payload_symbols * np.float32(symbol_rms_gain)).astype(np.complex64)

    payload_symbols, scrambling_metrics = maybe_unscramble_symbols(payload_symbols[:n_complex], manifest, args)
    reference_latent, reference_symbols = reference_symbols_from_manifest(manifest)
    latent_hat = complex_symbols_to_latent(payload_symbols[:n_complex], manifest)
    rx_post_quantize = bool(manifest.get("rx_post_quantize", True))
    npz_items: dict[str, Any]
    if rx_post_quantize:
        latent_out, quant_items = quantize_dequantize(latent_hat)
        npz_items = {"latent": latent_out, **quant_items}
    else:
        latent_out = latent_hat.astype(np.float32, copy=False)
        npz_items = {"latent": latent_out}
    mark_timing("latent_reconstruct")

    atomic_savez(out_npz, **npz_items)
    mark_timing("write_npz")

    summary: dict[str, Any] = {
        "status": "ok",
        "phy": "analog-latent-iq",
        "sync_success": True,
        "payload_is_bit_exact": False,
        "rx_sc16": str(rx_sc16),
        "out_npz": str(out_npz),
        "out_wire": str(out_wire) if out_wire else "",
        "sample_rate": rate,
        "sps": sps,
        "sync_phase": int(sync_final["phase"]),
        "sync_start_symbol": int(sync_final["sync_start"]) + int(sync_symbol_offset),
        "sync_start_symbol_local": int(sync_final["sync_start"]),
        "sync_symbol_offset": int(sync_symbol_offset),
        "sync_metric": float(sync_final["sync_metric"]),
        "initial_sync_metric": float(sync0["sync_metric"]),
        "sync_correlation_method": str(sync_final.get("sync_correlation_method") or ""),
        "estimated_cfo_hz": float(estimated_cfo_hz),
        "cfo_estimator": cfo_method,
        "sync_search_mode": sync_search_mode,
        "initial_frame_complete": bool(sync0.get("frame_complete", True)),
        "min_sync_metric": float(min_sync_metric),
        "dc_real": float(np.real(dc)),
        "dc_imag": float(np.imag(dc)),
        "rx_clipping_ratio": rx_clipping_ratio,
        "rx_post_quantize": rx_post_quantize,
        "received_latent_sha256": sha256_bytes(latent_out.astype(np.float32, copy=False).tobytes()),
        "payload_symbol_rms": expected_symbol_rms,
        "recovered_symbol_rms": recovered_symbol_rms,
        "symbol_rms_gain": float(symbol_rms_gain),
        "n_real": int(manifest["n_real"]),
        "n_complex": int(manifest["n_complex"]),
        "recovered_complex_symbols": int(payload_symbols.size),
        "latent_shape": list(latent_out.shape),
        "detected_airtime_ms": float(1000.0 * int(manifest["tx_waveform_samples"]) / rate),
    }
    summary.update(crop_metrics)
    summary.update(sync_debug)
    summary.update(sync_pass_summary)
    summary.update(payload_metrics)
    summary.update(scrambling_metrics)
    summary.update(symbol_quality_metrics(reference_symbols, payload_symbols[:n_complex]))
    summary.update(latent_mse_metric(reference_latent, latent_out))
    mark_timing("summary_metrics")
    summary["decode_timing_ms"] = {key: round(value, 3) for key, value in decode_timing_ms.items()}
    summary["decode_total_ms"] = round(float((time.perf_counter() - decode_start) * 1000.0), 3)

    if out_wire is not None:
        out_wire.parent.mkdir(parents=True, exist_ok=True)
        out_wire.write_bytes(pack_received_wire_blob(latent_out, manifest, summary))
        mark_timing("write_wire")
        summary["decode_timing_ms"] = {key: round(value, 3) for key, value in decode_timing_ms.items()}
        summary["decode_total_ms"] = round(float((time.perf_counter() - decode_start) * 1000.0), 3)
    if summary_path is not None:
        write_json(summary_path, summary)
    return summary


def simulate_channel(args: argparse.Namespace) -> dict[str, Any]:
    manifest = read_json(Path(args.manifest))
    rate = float(manifest["sample_rate"])
    amp = int(manifest["sc16_amplitude"])
    tx, tx_clipping_ratio = sc16_to_complex(Path(args.tx_sc16), amp)
    n = np.arange(tx.size, dtype=np.float64)
    phase_rad = math.radians(float(args.phase_deg))
    drift_rad = math.radians(float(args.phase_drift_deg))
    drift = drift_rad * (n / max(float(max(tx.size - 1, 1)), 1.0))
    rot = np.exp(1j * (phase_rad + drift + 2.0 * math.pi * float(args.cfo_hz) * n / rate)).astype(np.complex64)
    rx = (np.asarray(tx, dtype=np.complex64) * np.complex64(float(args.gain)) * rot).astype(np.complex64)

    snr_db = args.snr_db
    signal_power = 0.0
    noise_power = 0.0
    if snr_db is not None:
        zero_guard = int(manifest.get("zero_guard_samples") or 0)
        tail_guard = int(manifest.get("tail_guard_samples") or 0)
        active_end = max(zero_guard, tx.size - tail_guard)
        active = rx[zero_guard:active_end] if active_end > zero_guard else rx
        signal_power = float(np.mean(np.square(np.abs(active), dtype=np.float64))) if active.size else 0.0
        noise_power = signal_power * 10.0 ** (-float(snr_db) / 10.0)
        if noise_power > 0.0:
            rng = np.random.default_rng(int(args.seed))
            noise = (
                rng.standard_normal(rx.size).astype(np.float32)
                + 1j * rng.standard_normal(rx.size).astype(np.float32)
            ) * np.float32(math.sqrt(noise_power / 2.0))
            rx = (rx + noise.astype(np.complex64)).astype(np.complex64)

    rx = (rx + np.complex64(complex(float(args.dc_real), float(args.dc_imag)))).astype(np.complex64)
    interleaved, rx_clipping_ratio = normalized_complex_to_sc16(rx, amp)
    out_sc16 = Path(args.out_sc16)
    write_sc16(out_sc16, interleaved)

    summary = {
        "status": "ok",
        "phy": "analog-latent-iq",
        "tx_sc16": str(args.tx_sc16),
        "out_sc16": str(out_sc16),
        "sample_rate": rate,
        "sc16_amplitude": amp,
        "simulated_cfo_hz": float(args.cfo_hz),
        "simulated_snr_db": None if snr_db is None else float(snr_db),
        "simulated_gain": float(args.gain),
        "simulated_phase_deg": float(args.phase_deg),
        "simulated_phase_drift_deg": float(args.phase_drift_deg),
        "simulated_dc_real": float(args.dc_real),
        "simulated_dc_imag": float(args.dc_imag),
        "seed": int(args.seed),
        "signal_power": signal_power,
        "noise_power": noise_power,
        "tx_clipping_ratio": tx_clipping_ratio,
        "rx_clipping_ratio": rx_clipping_ratio,
        "payload_is_bit_exact": False,
    }
    if args.summary_json:
        write_json(Path(args.summary_json), summary)
    return summary


def decode_namespace_from_request(request: dict[str, Any]) -> argparse.Namespace:
    manifest_json = request.get("manifest_json")
    if manifest_json is not None:
        manifest_path = Path(str(request["manifest"]))
        if isinstance(manifest_json, str):
            manifest_payload = json.loads(manifest_json)
        else:
            manifest_payload = manifest_json
        if not isinstance(manifest_payload, dict):
            raise RuntimeError("manifest_json must be a JSON object")
        write_json(manifest_path, manifest_payload)
    return argparse.Namespace(
        rx_sc16=str(request["rx_sc16"]),
        manifest=str(request["manifest"]),
        out_npz=str(request["out_npz"]),
        out_wire=str(request.get("out_wire") or ""),
        summary_json=str(request.get("summary_json") or ""),
        sync_profile=str(request.get("sync_profile") or ""),
        sync_candidates=int(request.get("sync_candidates", DEFAULT_SYNC_CANDIDATES)),
        fast_sync_candidates=int(request.get("fast_sync_candidates", DEFAULT_FAST_SYNC_CANDIDATES)),
        fast_sync_search_window_symbols=int(
            request.get("fast_sync_search_window_symbols", DEFAULT_FAST_SYNC_SEARCH_WINDOW_SYMBOLS)
        ),
        fallback_sync_candidates=int(request.get("fallback_sync_candidates", DEFAULT_FALLBACK_SYNC_CANDIDATES)),
        fallback_sync_search_window_symbols=int(
            request.get("fallback_sync_search_window_symbols", DEFAULT_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS)
        ),
        retry_on_burst_miss=bool(request.get("retry_on_burst_miss", False)),
        retry_on_low_sync=bool(request.get("retry_on_low_sync", False)),
        low_sync_retry_threshold=float(
            request.get("low_sync_retry_threshold", DEFAULT_LOW_SYNC_RETRY_THRESHOLD)
        ),
        min_sync_metric=float(request.get("min_sync_metric", DEFAULT_MIN_SYNC_METRIC)),
        robust_sync=bool(request.get("robust_sync", True)),
        robust_cfo_max_hz=float(request.get("robust_cfo_max_hz", DEFAULT_ROBUST_CFO_MAX_HZ)),
        robust_cfo_step_hz=float(request.get("robust_cfo_step_hz", DEFAULT_ROBUST_CFO_STEP_HZ)),
        sync_search_center_symbol=int(request.get("sync_search_center_symbol", -1)),
        sync_search_window_symbols=int(request.get("sync_search_window_symbols", 0)),
        scramble_key=str(request.get("scramble_key") or ""),
        scramble_key_hex=str(request.get("scramble_key_hex") or ""),
        scramble_context=str(request.get("scramble_context") or ""),
    )


DECODE_WORKER_MINIMAL_SUMMARY_KEYS = (
    "status",
    "sync_success",
    "frame_complete",
    "sync_search_mode",
    "sync_metric",
    "estimated_cfo_hz",
    "detected_airtime_ms",
    "evm_rms",
    "estimated_snr_db",
    "rx_clipping_ratio",
    "decode_total_ms",
    "decode_timing_ms",
)


def decode_worker_response(
    summary: dict[str, Any],
    summary_json: str,
    *,
    mode: str = "full",
    request_id: str = "",
) -> dict[str, Any]:
    response_mode = str(mode or "full").strip().lower()
    response_summary = summary
    if response_mode in {"minimal", "compact"}:
        response_summary = {
            key: summary[key]
            for key in DECODE_WORKER_MINIMAL_SUMMARY_KEYS
            if key in summary
        }
    response = {
        "status": "ok",
        "summary_json": summary_json,
        "sync_metric": summary.get("sync_metric"),
        "estimated_cfo_hz": summary.get("estimated_cfo_hz"),
        "summary": response_summary,
    }
    if request_id:
        response["request_id"] = request_id
    return response


def run_decode_server() -> int:
    ready_payload = {"status": "ready"}
    try:
        ready_payload.update(warm_sync_correlation())
    except Exception as exc:
        ready_payload.update({
            "sync_fft_warmup_enabled": False,
            "sync_fft_warmup_error": str(exc),
        })
    ready_payload.update(warm_decode_pipeline())
    print(json.dumps(ready_payload, ensure_ascii=False), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"status": "error", "error": f"invalid json: {exc}"}, ensure_ascii=False), flush=True)
            continue
        cmd = str(request.get("cmd") or "decode").strip().lower()
        if cmd in {"quit", "exit"}:
            print(json.dumps({"status": "bye"}, ensure_ascii=False), flush=True)
            return 0
        if cmd != "decode":
            print(json.dumps({"status": "error", "error": f"unsupported cmd: {cmd}"}, ensure_ascii=False), flush=True)
            continue
        try:
            args = decode_namespace_from_request(request)
            summary = decode_waveform(args)
            print(json.dumps(
                decode_worker_response(
                    summary,
                    args.summary_json,
                    mode=str(request.get("response_mode") or "full"),
                    request_id=str(request.get("request_id") or ""),
                ),
                ensure_ascii=False,
            ), flush=True)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)
    return 0


def recover_payload_with_fixed_cfo(
    rx_dc: np.ndarray,
    taps: np.ndarray,
    sync: np.ndarray,
    manifest: dict[str, Any],
    *,
    cfo_hz: float,
    rate: float,
    sps: int,
    max_candidates: int,
    min_sync_metric: float,
    search_center_symbol: int | None = None,
    search_window_symbols: int = 0,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    rx_corr = correct_cfo(rx_dc, cfo_hz, rate)
    mf = matched_filter(rx_corr, taps)
    candidates = find_sync_candidates(
        mf,
        sync,
        sps,
        max_candidates=max_candidates,
        manifest=manifest,
        search_center_symbol=search_center_symbol,
        search_window_symbols=search_window_symbols,
    )
    if not candidates:
        raise RuntimeError("sync search failed after CFO correction")

    errors: list[str] = []
    attempted = 0
    for candidate in candidates:
        if not bool(candidate.get("frame_complete", True)):
            continue
        if float(candidate["sync_metric"]) < float(min_sync_metric):
            errors.append(
                f"phase={candidate['phase']} start={candidate['sync_start']}: "
                f"sync metric {float(candidate['sync_metric']):.6f} below threshold {float(min_sync_metric):.6f}"
            )
            continue
        attempted += 1
        try:
            payload_symbols, payload_metrics = recover_payload_symbols(
                candidate["sym_stream"],
                int(candidate["sync_start"]),
                manifest,
            )
            payload_metrics.update({
                "sync_candidate_count": int(len(candidates)),
                "sync_candidates_attempted": int(attempted),
                "frame_complete": True,
            })
            return payload_symbols, payload_metrics, candidate
        except RuntimeError as exc:
            errors.append(f"phase={candidate['phase']} start={candidate['sync_start']}: {exc}")

    if not errors:
        errors.append("no sync candidate had a complete frame")
    raise RuntimeError("; ".join(errors[:4]))


def cfo_grid_values(max_abs_hz: float, step_hz: float) -> list[float]:
    max_abs = abs(float(max_abs_hz))
    step = abs(float(step_hz))
    if max_abs <= 0.0 or step <= 0.0:
        return [0.0]
    values = np.arange(-max_abs, max_abs + 0.5 * step, step, dtype=np.float64)
    return [float(v) for v in sorted(values.tolist(), key=lambda item: (abs(item), item))]


def robust_cfo_grid_recover(
    rx_dc: np.ndarray,
    taps: np.ndarray,
    sync: np.ndarray,
    manifest: dict[str, Any],
    *,
    rate: float,
    sps: int,
    max_candidates: int,
    min_sync_metric: float,
    cfo_max_hz: float,
    cfo_step_hz: float,
    search_center_symbol: int | None = None,
    search_window_symbols: int = 0,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any], float, str, dict[str, Any]]:
    cfo_len = int(manifest["cfo_pilot_symbols"])
    cfo_seed = int(manifest["cfo_seed"])
    probes: list[dict[str, Any]] = []

    for coarse_hz in cfo_grid_values(cfo_max_hz, cfo_step_hz):
        rx_coarse = correct_cfo(rx_dc, coarse_hz, rate)
        mf = matched_filter(rx_coarse, taps)
        candidates = find_sync_candidates(
            mf,
            sync,
            sps,
            max_candidates=max(2, min(max_candidates, 4)),
            manifest=manifest,
            search_center_symbol=search_center_symbol,
            search_window_symbols=search_window_symbols,
        )
        for candidate in candidates:
            if not bool(candidate.get("frame_complete", True)):
                continue
            if float(candidate["sync_metric"]) < float(min_sync_metric):
                continue
            residual_hz, estimator = estimate_cfo_from_known_pilot(
                candidate["sym_stream"],
                int(candidate["sync_start"]),
                cfo_len,
                rate,
                sps,
                cfo_seed,
            )
            probes.append({
                "coarse_cfo_hz": float(coarse_hz),
                "residual_cfo_hz": float(residual_hz),
                "total_cfo_hz": float(coarse_hz + residual_hz),
                "sync_metric": float(candidate["sync_metric"]),
                "sync_start": int(candidate["sync_start"]),
                "phase": int(candidate["phase"]),
                "estimator": estimator,
            })

    probes.sort(key=lambda item: float(item["sync_metric"]), reverse=True)
    errors: list[str] = []
    for probe in probes[: max(1, int(max_candidates))]:
        total_cfo = float(probe["total_cfo_hz"])
        try:
            payload_symbols, payload_metrics, sync_final = recover_payload_with_fixed_cfo(
                rx_dc,
                taps,
                sync,
                manifest,
                cfo_hz=total_cfo,
                rate=rate,
                sps=sps,
                max_candidates=max_candidates,
                min_sync_metric=min_sync_metric,
                search_center_symbol=search_center_symbol,
                search_window_symbols=search_window_symbols,
            )
            payload_metrics.update({
                "robust_probe_count": int(len(probes)),
                "robust_coarse_cfo_hz": float(probe["coarse_cfo_hz"]),
                "robust_residual_cfo_hz": float(probe["residual_cfo_hz"]),
                "robust_probe_sync_metric": float(probe["sync_metric"]),
            })
            debug = {
                "sync_search_mode": "robust-cfo-grid",
                "robust_cfo_max_hz": float(cfo_max_hz),
                "robust_cfo_step_hz": float(cfo_step_hz),
                "robust_probe_count": int(len(probes)),
                "robust_errors": errors[:4],
            }
            return payload_symbols, payload_metrics, sync_final, total_cfo, str(probe["estimator"]), debug
        except RuntimeError as exc:
            errors.append(f"cfo={total_cfo:.3f}: {exc}")

    raise RuntimeError("robust CFO sync failed: " + "; ".join(errors[:4]))


def add_common_phy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE)
    parser.add_argument("--sps", type=int, default=DEFAULT_SPS)
    parser.add_argument("--rrc-beta", type=float, default=DEFAULT_RRC_BETA)
    parser.add_argument("--rrc-span", type=int, default=DEFAULT_RRC_SPAN)
    parser.add_argument("--amp", type=int, default=DEFAULT_SC16_AMPLITUDE)
    parser.add_argument("--zero-guard-samples", type=int, default=DEFAULT_ZERO_GUARD_SAMPLES)
    parser.add_argument("--tail-guard-samples", type=int, default=DEFAULT_TAIL_GUARD_SAMPLES)
    parser.add_argument("--cfo-pilot-symbols", type=int, default=DEFAULT_CFO_PILOT_SYMBOLS)
    parser.add_argument("--sync-pilot-symbols", type=int, default=DEFAULT_SYNC_PILOT_SYMBOLS)
    parser.add_argument("--data-block-symbols", type=int, default=DEFAULT_DATA_BLOCK_SYMBOLS)
    parser.add_argument("--mid-pilot-symbols", type=int, default=DEFAULT_MID_PILOT_SYMBOLS)
    parser.add_argument("--cfo-seed", type=int, default=1001)
    parser.add_argument("--sync-seed", type=int, default=1002)
    parser.add_argument("--mid-pilot-seed", type=int, default=1003)
    parser.add_argument("--capture-margin-samples", type=int, default=DEFAULT_CAPTURE_MARGIN_SAMPLES)
    parser.add_argument("--rx-post-quantize", dest="rx_post_quantize", action="store_true", default=True)
    parser.add_argument("--no-rx-post-quantize", dest="rx_post_quantize", action="store_false")


def add_scrambling_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scramble-key", default=os.environ.get("ANALOG_SCRAMBLE_KEY", ""))
    parser.add_argument("--scramble-key-hex", default=os.environ.get("ANALOG_SCRAMBLE_KEY_HEX", ""))
    parser.add_argument("--scramble-context", default=os.environ.get("ANALOG_SCRAMBLE_CONTEXT", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analog latent-IQ PHY for USRP292x sc16 files.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    make = sub.add_parser("make")
    make.add_argument("--input", required=True)
    make.add_argument("--out-sc16", required=True)
    make.add_argument("--manifest", required=True)
    make.add_argument("--job-id", default="")
    add_common_phy_args(make)
    add_scrambling_args(make)

    decode = sub.add_parser("decode")
    decode.add_argument("--rx-sc16", required=True)
    decode.add_argument("--manifest", required=True)
    decode.add_argument("--out-npz", required=True)
    decode.add_argument("--out-wire", default="")
    decode.add_argument("--summary-json", default="")
    decode.add_argument("--sync-profile", default=os.environ.get("ANALOG_SYNC_PROFILE", ""))
    decode.add_argument("--sync-candidates", type=int, default=_env_int("ANALOG_SYNC_CANDIDATES", DEFAULT_SYNC_CANDIDATES))
    decode.add_argument(
        "--fast-sync-candidates",
        type=int,
        default=_env_int("ANALOG_FAST_SYNC_CANDIDATES", DEFAULT_FAST_SYNC_CANDIDATES),
    )
    decode.add_argument(
        "--fast-sync-search-window-symbols",
        type=int,
        default=_env_int("ANALOG_FAST_SYNC_SEARCH_WINDOW_SYMBOLS", DEFAULT_FAST_SYNC_SEARCH_WINDOW_SYMBOLS),
    )
    decode.add_argument(
        "--fallback-sync-candidates",
        type=int,
        default=_env_int("ANALOG_FALLBACK_SYNC_CANDIDATES", DEFAULT_FALLBACK_SYNC_CANDIDATES),
    )
    decode.add_argument(
        "--fallback-sync-search-window-symbols",
        type=int,
        default=_env_int("ANALOG_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS", DEFAULT_FALLBACK_SYNC_SEARCH_WINDOW_SYMBOLS),
    )
    decode.add_argument(
        "--retry-on-burst-miss",
        dest="retry_on_burst_miss",
        action="store_true",
        default=_env_bool("ANALOG_RETRY_ON_BURST_MISS", False),
    )
    decode.add_argument("--no-retry-on-burst-miss", dest="retry_on_burst_miss", action="store_false")
    decode.add_argument(
        "--retry-on-low-sync",
        dest="retry_on_low_sync",
        action="store_true",
        default=_env_bool("ANALOG_RETRY_ON_LOW_SYNC", False),
    )
    decode.add_argument("--no-retry-on-low-sync", dest="retry_on_low_sync", action="store_false")
    decode.add_argument(
        "--low-sync-retry-threshold",
        type=float,
        default=_env_float("ANALOG_LOW_SYNC_RETRY_THRESHOLD", DEFAULT_LOW_SYNC_RETRY_THRESHOLD),
    )
    decode.add_argument("--min-sync-metric", type=float, default=DEFAULT_MIN_SYNC_METRIC)
    decode.add_argument("--robust-sync", dest="robust_sync", action="store_true", default=True)
    decode.add_argument("--no-robust-sync", dest="robust_sync", action="store_false")
    decode.add_argument("--robust-cfo-max-hz", type=float, default=DEFAULT_ROBUST_CFO_MAX_HZ)
    decode.add_argument("--robust-cfo-step-hz", type=float, default=DEFAULT_ROBUST_CFO_STEP_HZ)
    decode.add_argument("--sync-search-center-symbol", type=int, default=-1)
    decode.add_argument("--sync-search-window-symbols", type=int, default=0)
    add_scrambling_args(decode)

    simulate = sub.add_parser("simulate-channel")
    simulate.add_argument("--tx-sc16", required=True)
    simulate.add_argument("--manifest", required=True)
    simulate.add_argument("--out-sc16", required=True)
    simulate.add_argument("--cfo-hz", type=float, default=0.0)
    simulate.add_argument("--snr-db", type=float, default=None)
    simulate.add_argument("--gain", type=float, default=1.0)
    simulate.add_argument("--phase-deg", type=float, default=0.0)
    simulate.add_argument("--phase-drift-deg", type=float, default=0.0)
    simulate.add_argument("--dc-real", type=float, default=0.0)
    simulate.add_argument("--dc-imag", type=float, default=0.0)
    simulate.add_argument("--seed", type=int, default=1)
    simulate.add_argument("--summary-json", default="")

    sub.add_parser("decode-server")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.cmd == "make":
        manifest = make_waveform(args)
        print(json.dumps({
            "status": "ok",
            "manifest": args.manifest,
            "out_sc16": args.out_sc16,
            "tx_waveform_samples": manifest["tx_waveform_samples"],
            "capture_nsamps": manifest["capture_nsamps"],
        }, ensure_ascii=False))
        return 0
    if args.cmd == "decode":
        summary = decode_waveform(args)
        print(json.dumps({
            "status": "ok",
            "summary_json": args.summary_json,
            "sync_metric": summary["sync_metric"],
            "estimated_cfo_hz": summary["estimated_cfo_hz"],
        }, ensure_ascii=False))
        return 0
    if args.cmd == "simulate-channel":
        summary = simulate_channel(args)
        print(json.dumps({
            "status": "ok",
            "out_sc16": args.out_sc16,
            "simulated_cfo_hz": summary["simulated_cfo_hz"],
            "simulated_snr_db": summary["simulated_snr_db"],
        }, ensure_ascii=False))
        return 0
    if args.cmd == "decode-server":
        return run_decode_server()
    raise RuntimeError(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
