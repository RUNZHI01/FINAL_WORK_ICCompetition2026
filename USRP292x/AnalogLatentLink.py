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
import sys
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
DEFAULT_ROBUST_CFO_MAX_HZ = 8000.0
DEFAULT_ROBUST_CFO_STEP_HZ = 500.0
DEFAULT_MIN_SYNC_METRIC = 0.25
SAMPLE_BYTES = 4
EPS = 1.0e-12
SCRAMBLING_MODE = "keyed-permutation-sign-v1"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def sc16_to_complex(path: Path, amplitude: int) -> tuple[np.ndarray, float]:
    raw = np.fromfile(path, dtype=np.int16)
    if raw.size % 2:
        raise ValueError(f"sc16 file has odd int16 count: {path}")
    clipping_ratio = float(np.mean((np.abs(raw[0::2]) >= 32767) | (np.abs(raw[1::2]) >= 32767))) if raw.size else 0.0
    complex_rx = raw[0::2].astype(np.float32) + 1j * raw[1::2].astype(np.float32)
    return (complex_rx / np.float32(amplitude)).astype(np.complex64), clipping_ratio


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
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sync_energy = float(np.vdot(sync, sync).real)
    if sync_energy <= 0.0:
        raise ValueError("sync pilot has zero energy")

    for phase in range(int(sps)):
        stream = mf[phase:: int(sps)]
        if stream.size < sync.size:
            continue
        corr = np.abs(np.correlate(stream, sync, mode="valid"))
        if corr.size == 0:
            continue
        take = min(max(1, int(max_candidates)), int(corr.size))
        if take == corr.size:
            top_indices = np.arange(corr.size)
        else:
            top_indices = np.argpartition(corr, -take)[-take:]
        for raw_idx in top_indices:
            idx = int(raw_idx)
            window = stream[idx:idx + sync.size]
            rx_energy = float(np.vdot(window, window).real)
            metric = float(corr[idx] / math.sqrt(max(rx_energy * sync_energy, EPS)))
            candidate = {
                "phase": int(phase),
                "sync_start": idx,
                "sync_metric": metric,
                "sync_corr": float(corr[idx]),
                "sym_stream": stream,
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

    rx, rx_clipping_ratio = sc16_to_complex(rx_sc16, amp)
    if rx.size == 0:
        raise RuntimeError(f"empty RX sc16 file: {rx_sc16}")
    dc_window = rx[:min(max(zero_guard, 1), rx.size)]
    dc = complex(np.mean(dc_window))
    rx_dc = (rx - np.complex64(dc)).astype(np.complex64)

    max_candidates = int(getattr(args, "sync_candidates", DEFAULT_SYNC_CANDIDATES))
    min_sync_metric = float(getattr(args, "min_sync_metric", DEFAULT_MIN_SYNC_METRIC))
    robust_enabled = bool(getattr(args, "robust_sync", True))
    mf0 = matched_filter(rx_dc, taps)
    initial_candidates = find_sync_candidates(
        mf0,
        sync,
        sps,
        max_candidates=max_candidates,
        manifest=manifest,
    )
    if not initial_candidates:
        raise RuntimeError("initial sync search failed")
    sync0 = initial_candidates[0]
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

    sync_search_mode = "normal"
    sync_debug: dict[str, Any] = {
        "sync_search_mode": sync_search_mode,
        "initial_sync_candidate_count": int(len(initial_candidates)),
    }
    try:
        payload_symbols, payload_metrics, sync_final = recover_payload_with_fixed_cfo(
            rx_dc,
            taps,
            sync,
            manifest,
            cfo_hz=estimated_cfo_hz,
            rate=rate,
            sps=sps,
            max_candidates=max_candidates,
            min_sync_metric=min_sync_metric,
        )
    except RuntimeError as normal_exc:
        if not robust_enabled:
            raise
        payload_symbols, payload_metrics, sync_final, estimated_cfo_hz, cfo_method, sync_debug = robust_cfo_grid_recover(
            rx_dc,
            taps,
            sync,
            manifest,
            rate=rate,
            sps=sps,
            max_candidates=max_candidates,
            min_sync_metric=min_sync_metric,
            cfo_max_hz=float(getattr(args, "robust_cfo_max_hz", DEFAULT_ROBUST_CFO_MAX_HZ)),
            cfo_step_hz=float(getattr(args, "robust_cfo_step_hz", DEFAULT_ROBUST_CFO_STEP_HZ)),
        )
        sync_debug["normal_sync_error"] = str(normal_exc)
        sync_search_mode = str(sync_debug["sync_search_mode"])
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

    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out_npz, **npz_items)

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
        "sync_start_symbol": int(sync_final["sync_start"]),
        "sync_metric": float(sync_final["sync_metric"]),
        "initial_sync_metric": float(sync0["sync_metric"]),
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
    summary.update(sync_debug)
    summary.update(payload_metrics)
    summary.update(scrambling_metrics)
    summary.update(symbol_quality_metrics(reference_symbols, payload_symbols[:n_complex]))
    summary.update(latent_mse_metric(reference_latent, latent_out))

    if out_wire is not None:
        out_wire.parent.mkdir(parents=True, exist_ok=True)
        out_wire.write_bytes(pack_received_wire_blob(latent_out, manifest, summary))
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
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    rx_corr = correct_cfo(rx_dc, cfo_hz, rate)
    mf = matched_filter(rx_corr, taps)
    candidates = find_sync_candidates(
        mf,
        sync,
        sps,
        max_candidates=max_candidates,
        manifest=manifest,
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
    decode.add_argument("--sync-candidates", type=int, default=DEFAULT_SYNC_CANDIDATES)
    decode.add_argument("--min-sync-metric", type=float, default=DEFAULT_MIN_SYNC_METRIC)
    decode.add_argument("--robust-sync", dest="robust_sync", action="store_true", default=True)
    decode.add_argument("--no-robust-sync", dest="robust_sync", action="store_false")
    decode.add_argument("--robust-cfo-max-hz", type=float, default=DEFAULT_ROBUST_CFO_MAX_HZ)
    decode.add_argument("--robust-cfo-step-hz", type=float, default=DEFAULT_ROBUST_CFO_STEP_HZ)
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
    raise RuntimeError(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
