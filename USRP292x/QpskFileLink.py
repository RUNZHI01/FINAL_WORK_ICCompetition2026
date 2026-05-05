#!/usr/bin/env python3
"""USRP292x chunked QPSK file-link smoke.

用途：
1. 将现有 wire blob 映射成 sc16 QPSK 波形，供 UHD tx_samples_from_file 发送。
2. 从 OtaRxCaptureGain 抓到的 sc16 IQ 中按 chunk 解调，统计 BER/PER。

这不是最终 PHY，只是 Level 1 快速量级验证：131 KB payload 是否能在 5 Msps
量级接近 TVM/MNN 推理耗时。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import time
import zlib
from pathlib import Path
from typing import Iterable

import numpy as np


DEFAULT_RATE = 5_000_000.0
DEFAULT_SPS = 2
DEFAULT_CHUNK_BYTES = 4096
DEFAULT_AMP = 3000.0
DEFAULT_GAP_SAMPLES = 1024
DEFAULT_WARMUP_SAMPLES = 250_000
DEFAULT_TAIL_SAMPLES = 250_000
DEFAULT_BLOCK_SYMBOLS = 128
DEFAULT_BLOCK_REPEATS = 16
DEFAULT_SYNC_SYMBOLS = 512
CHUNK_MAGIC = b'QFCK'
CHUNK_VERSION = 1
CHUNK_HEADER = struct.Struct('>4sBBHHHII')
CHUNK_FLAG_LAST = 0x01


def build_chunk_header(seq: int, total: int, payload_len: int, total_len: int, crc32: int) -> bytes:
    flags = CHUNK_FLAG_LAST if seq == total - 1 else 0
    return CHUNK_HEADER.pack(
        CHUNK_MAGIC,
        CHUNK_VERSION,
        flags,
        seq,
        total,
        payload_len,
        total_len,
        crc32,
    )


def parse_chunk_header(data: bytes) -> dict:
    if len(data) < CHUNK_HEADER.size:
        raise ValueError('short chunk header')
    magic, version, flags, seq, total, payload_len, total_len, crc32 = CHUNK_HEADER.unpack(
        data[:CHUNK_HEADER.size]
    )
    if magic != CHUNK_MAGIC:
        raise ValueError(f'bad chunk magic: {magic!r}')
    if version != CHUNK_VERSION:
        raise ValueError(f'bad chunk version: {version}')
    return {
        'flags': flags,
        'seq': seq,
        'total': total,
        'payload_len': payload_len,
        'total_len': total_len,
        'crc32': crc32,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Chunked QPSK file link helper.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    make = sub.add_parser('make', help='make sc16 QPSK waveform from a payload file')
    make.add_argument('--input', type=Path, required=True, help='input payload/wire blob')
    make.add_argument('--out-sc16', type=Path, required=True, help='output interleaved int16 IQ')
    make.add_argument('--manifest', type=Path, required=True, help='output manifest json')
    make.add_argument('--rate', type=float, default=DEFAULT_RATE)
    make.add_argument('--sps', type=int, default=DEFAULT_SPS)
    make.add_argument('--chunk-bytes', type=int, default=DEFAULT_CHUNK_BYTES)
    make.add_argument('--amplitude', type=float, default=DEFAULT_AMP)
    make.add_argument('--gap-samples', type=int, default=DEFAULT_GAP_SAMPLES)
    make.add_argument(
        '--only-chunks',
        type=str,
        default='',
        help='comma-separated source chunk ids to transmit, empty means all chunks',
    )
    make.add_argument(
        '--warmup-samples',
        type=int,
        default=DEFAULT_WARMUP_SAMPLES,
        help='uncounted random QPSK samples before payload frames',
    )
    make.add_argument(
        '--tail-samples',
        type=int,
        default=DEFAULT_TAIL_SAMPLES,
        help='uncounted zero samples after payload frames to avoid EOB tail clipping',
    )

    decode = sub.add_parser('decode', help='decode captured sc16 IQ and compare with reference')
    decode.add_argument('--rx-sc16', type=Path, required=True, help='captured interleaved int16 IQ')
    decode.add_argument('--manifest', type=Path, required=True, help='manifest from make')
    decode.add_argument('--reference', type=Path, required=True, help='original payload/wire blob')
    decode.add_argument('--out-bin', type=Path, default=None, help='optional decoded bytes output')
    decode.add_argument('--summary-json', type=Path, default=None, help='optional machine-readable decode summary')
    decode.add_argument('--rx-offset-samples', type=int, default=0, help='optional complex-sample offset inside rx-sc16')
    decode.add_argument('--rx-length-samples', type=int, default=0, help='optional complex-sample span inside rx-sc16; 0 means to EOF')
    decode.add_argument('--search-start-sec', type=float, default=0.2)
    decode.add_argument('--search-end-sec', type=float, default=2.0)
    decode.add_argument('--local-search-samples', type=int, default=3000)
    decode.add_argument('--sync-search-samples', type=int, default=3500)
    decode.add_argument('--frame-candidates', type=int, default=64, help='direct-sync candidates per chunk')
    decode.add_argument('--timing-search-samples', type=int, default=8, help='sample offsets around data start')
    decode.add_argument('--max-chunks', type=int, default=0, help='0 means all chunks')

    merge = sub.add_parser('merge', help='merge decoded ARQ rounds by crc_ok chunk indices')
    merge.add_argument('--reference', type=Path, required=True, help='original payload/wire blob for verification')
    merge.add_argument('--out-bin', type=Path, required=True, help='merged payload output')
    merge.add_argument('--summary-out', type=Path, default=None, help='optional merged summary json')
    merge.add_argument('--chunk-bytes', type=int, default=DEFAULT_CHUNK_BYTES)
    merge.add_argument('--summary-json', type=Path, action='append', required=True)
    merge.add_argument('--decoded-bin', type=Path, action='append', required=True)

    return parser.parse_args()


def parse_chunk_list(value: str, total_chunks: int) -> list[int]:
    if not value.strip():
        return list(range(total_chunks))
    chunks: list[int] = []
    seen: set[int] = set()
    for part in value.split(','):
        item = part.strip()
        if not item:
            continue
        seq = int(item)
        if seq < 0 or seq >= total_chunks:
            raise ValueError(f'chunk id out of range: {seq}, total={total_chunks}')
        if seq not in seen:
            chunks.append(seq)
            seen.add(seq)
    if not chunks:
        raise ValueError('empty chunk selection')
    return chunks


def split_payload(payload: bytes, chunk_bytes: int) -> list[bytes]:
    return [payload[i:i + chunk_bytes] for i in range(0, len(payload), chunk_bytes)]


def chunk_lens(chunks: Iterable[bytes]) -> list[int]:
    return [len(chunk) for chunk in chunks]


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder='big')


def bits_to_bytes(bits: np.ndarray, nbytes: int) -> bytes:
    needed = nbytes * 8
    if bits.size < needed:
        bits = np.pad(bits, (0, needed - bits.size))
    bits = bits[:needed].astype(np.uint8, copy=False)
    return np.packbits(bits, bitorder='big').tobytes()


def qpsk_symbols_from_bits(bits: np.ndarray) -> np.ndarray:
    if bits.size % 2:
        bits = np.pad(bits, (0, 1))
    pairs = bits.reshape(-1, 2)
    i = np.where(pairs[:, 0] == 0, 1.0, -1.0)
    q = np.where(pairs[:, 1] == 0, 1.0, -1.0)
    return ((i + 1j * q) / np.sqrt(2.0)).astype(np.complex64)


def bits_from_qpsk_symbols(symbols: np.ndarray) -> np.ndarray:
    bits = np.empty(symbols.size * 2, dtype=np.uint8)
    bits[0::2] = np.real(symbols) < 0
    bits[1::2] = np.imag(symbols) < 0
    return bits


def upsample_rect(symbols: np.ndarray, sps: int) -> np.ndarray:
    return np.repeat(symbols, sps).astype(np.complex64)


def make_training(sps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    block_rng = np.random.default_rng(2922)
    sync_rng = np.random.default_rng(2923)
    block_bits = block_rng.integers(0, 2, DEFAULT_BLOCK_SYMBOLS * 2, dtype=np.uint8)
    sync_bits = sync_rng.integers(0, 2, DEFAULT_SYNC_SYMBOLS * 2, dtype=np.uint8)

    block_symbols = qpsk_symbols_from_bits(block_bits)
    sync_symbols = qpsk_symbols_from_bits(sync_bits)
    repeated_symbols = np.tile(block_symbols, DEFAULT_BLOCK_REPEATS)

    repeated_samples = upsample_rect(repeated_symbols, sps)
    sync_samples = upsample_rect(sync_symbols, sps)
    return block_symbols, sync_symbols, repeated_samples, sync_samples


def complex_to_sc16(samples: np.ndarray, amplitude: float) -> np.ndarray:
    scaled = samples * amplitude
    interleaved = np.empty(samples.size * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(np.real(scaled), -32767, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(np.imag(scaled), -32767, 32767).astype(np.int16)
    return interleaved


def sc16_to_complex(path: Path, *, offset_samples: int = 0, length_samples: int = 0) -> np.ndarray:
    total_complex = path.stat().st_size // 4
    start = min(max(0, int(offset_samples)), total_complex)
    count_complex = total_complex - start
    if length_samples > 0:
        count_complex = min(count_complex, int(length_samples))
    with path.open('rb') as handle:
        handle.seek(start * 4)
        raw = np.fromfile(handle, dtype=np.int16, count=count_complex * 2)
    if raw.size % 2:
        raw = raw[:-1]
    iq = raw.astype(np.float32).reshape(-1, 2)
    return iq[:, 0] + 1j * iq[:, 1]


def make_waveform(args: argparse.Namespace) -> int:
    payload = args.input.read_bytes()
    _, _, repeated_samples, sync_samples = make_training(args.sps)
    gap = np.zeros(args.gap_samples, dtype=np.complex64)

    chunks = split_payload(payload, args.chunk_bytes)
    selected_chunks = parse_chunk_list(args.only_chunks, len(chunks))
    frames: list[np.ndarray] = []
    chunk_symbol_counts: list[int] = []
    chunk_sample_counts: list[int] = []
    chunk_payload_lens: list[int] = []
    chunk_frame_lens: list[int] = []
    chunk_crc32: list[str] = []

    for seq in selected_chunks:
        chunk = chunks[seq]
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        header = build_chunk_header(seq, len(chunks), len(chunk), len(payload), crc)
        frame_bytes = header + chunk
        data_bits = bytes_to_bits(frame_bytes)
        data_symbols = qpsk_symbols_from_bits(data_bits)
        data_samples = upsample_rect(data_symbols, args.sps)
        frames.append(np.concatenate([gap, repeated_samples, sync_samples, data_samples]))
        chunk_symbol_counts.append(int(data_symbols.size))
        chunk_sample_counts.append(int(data_samples.size))
        chunk_payload_lens.append(len(chunk))
        chunk_frame_lens.append(len(frame_bytes))
        chunk_crc32.append(f'{crc:08x}')

    if args.warmup_samples > 0:
        warmup_rng = np.random.default_rng(2924)
        warmup_bits = warmup_rng.integers(0, 2, args.warmup_samples * 2, dtype=np.uint8)
        warmup = qpsk_symbols_from_bits(warmup_bits)[:args.warmup_samples]
    else:
        warmup = np.zeros(0, dtype=np.complex64)

    payload_waveform = np.concatenate(frames) if frames else np.zeros(0, dtype=np.complex64)
    tail = np.zeros(max(0, args.tail_samples), dtype=np.complex64)
    waveform = np.concatenate([warmup, payload_waveform, tail])
    args.out_sc16.parent.mkdir(parents=True, exist_ok=True)
    args.out_sc16.write_bytes(complex_to_sc16(waveform, args.amplitude).tobytes())

    crc32 = zlib.crc32(payload) & 0xFFFFFFFF
    manifest = {
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'input': str(args.input),
        'out_sc16': str(args.out_sc16),
        'sample_rate': args.rate,
        'sps': args.sps,
        'amplitude': args.amplitude,
        'gap_samples': args.gap_samples,
        'warmup_samples': args.warmup_samples,
        'tail_samples': args.tail_samples,
        'block_symbols': DEFAULT_BLOCK_SYMBOLS,
        'block_repeats': DEFAULT_BLOCK_REPEATS,
        'sync_symbols': DEFAULT_SYNC_SYMBOLS,
        'repeated_samples': int(repeated_samples.size),
        'sync_samples': int(sync_samples.size),
        'preamble_samples': int(repeated_samples.size + sync_samples.size),
        'payload_bytes': len(payload),
        'transmitted_payload_bytes': sum(len(chunks[seq]) for seq in selected_chunks),
        'chunk_bytes': args.chunk_bytes,
        'chunk_header_bytes': CHUNK_HEADER.size,
        'num_chunks': len(selected_chunks),
        'source_num_chunks': len(chunks),
        'chunk_indices': selected_chunks,
        'source_chunk_payload_lens': chunk_lens(chunks),
        'chunk_payload_lens': chunk_payload_lens,
        'chunk_frame_lens': chunk_frame_lens,
        'chunk_crc32': chunk_crc32,
        'chunk_symbol_counts': chunk_symbol_counts,
        'chunk_sample_counts': chunk_sample_counts,
        'waveform_samples': int(waveform.size),
        'payload_waveform_samples': int(payload_waveform.size),
        'waveform_airtime_ms': float(waveform.size / args.rate * 1000.0),
        'payload_waveform_airtime_ms': float(payload_waveform.size / args.rate * 1000.0),
        'crc32': f'{crc32:08x}',
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'payload_bytes={len(payload)}')
    print(f'transmitted_payload_bytes={manifest["transmitted_payload_bytes"]}')
    print(f'chunk_header_bytes={CHUNK_HEADER.size}')
    print(f'num_chunks={len(selected_chunks)}')
    print(f'source_num_chunks={len(chunks)}')
    print(f'chunk_indices={selected_chunks}')
    print(f'waveform_samples={waveform.size}')
    print(f'payload_waveform_samples={payload_waveform.size}')
    print(f'tail_samples={tail.size}')
    print(f'waveform_airtime_ms={manifest["waveform_airtime_ms"]:.3f}')
    print(f'payload_waveform_airtime_ms={manifest["payload_waveform_airtime_ms"]:.3f}')
    print(f'crc32={manifest["crc32"]}')
    print(f'out_sc16={args.out_sc16}')
    print(f'manifest={args.manifest}')
    return 0


def sliding_sum(x: np.ndarray, width: int) -> np.ndarray:
    cs = np.concatenate([[0], np.cumsum(x)])
    return cs[width:] - cs[:-width]


def schmidl_metric(segment: np.ndarray, block_samples: int, span_samples: int) -> tuple[np.ndarray, np.ndarray]:
    usable = min(segment.size, span_samples + block_samples)
    segment = segment[:usable]
    if segment.size < 2 * block_samples:
        raise ValueError('segment too short for preamble search')
    prod = np.conj(segment[:-block_samples]) * segment[block_samples:]
    p = sliding_sum(prod, block_samples)
    e1 = sliding_sum(np.abs(segment[:-block_samples]) ** 2, block_samples)
    e2 = sliding_sum(np.abs(segment[block_samples:]) ** 2, block_samples)
    metric = (np.abs(p) ** 2) / (e1 * e2 + 1e-12)
    return metric, p


def estimate_cfo(frame: np.ndarray, block_samples: int, rate: float, repeats: int) -> float:
    usable = min(frame.size, block_samples * repeats)
    if usable < 2 * block_samples:
        return 0.0
    pairs = usable // block_samples - 1
    acc = 0.0j
    for i in range(pairs):
        a = frame[i * block_samples:(i + 1) * block_samples]
        b = frame[(i + 1) * block_samples:(i + 2) * block_samples]
        acc += np.vdot(a, b)
    return float(np.angle(acc) * rate / (2.0 * np.pi * block_samples))


def correct_cfo(x: np.ndarray, rate: float, cfo_hz: float, start_index: int) -> np.ndarray:
    n = np.arange(x.size, dtype=np.float64) + float(start_index)
    return x * np.exp(-2j * np.pi * cfo_hz * n / rate)


def find_frame(
    rx: np.ndarray,
    search_start: int,
    search_end: int,
    manifest: dict,
    sync_samples: np.ndarray,
) -> tuple[int, int, float, float]:
    rate = float(manifest['sample_rate'])
    sps = int(manifest['sps'])
    block_samples = int(manifest['block_symbols']) * sps
    repeated_samples = int(manifest['repeated_samples'])
    sync_len = int(manifest['sync_samples'])
    span_samples = repeated_samples - block_samples

    start = max(0, search_start)
    stop = min(rx.size, search_end + repeated_samples + sync_len + block_samples)
    segment = rx[start:stop]
    metric, p = schmidl_metric(segment, block_samples, span_samples)
    energy = sliding_sum(np.abs(segment[:-block_samples]) ** 2, block_samples)
    if metric.size == 0:
        raise ValueError('empty Schmidl metric')

    energy_floor = np.percentile(energy, 75) if energy.size else 0.0
    valid = energy[:metric.size] > max(energy_floor * 1.5, 1.0)
    if not np.any(valid):
        valid = np.ones_like(metric, dtype=bool)
    valid_metric = np.where(valid, metric, 0.0)
    peak = int(np.argmax(valid_metric))
    peak_val = float(valid_metric[peak])
    threshold = max(0.25, peak_val * 0.70)
    left_candidates = np.where(valid_metric[:peak + 1] >= threshold)[0]
    coarse = int(left_candidates[0] if left_candidates.size else peak)
    coarse_abs = start + coarse

    frame_for_cfo = rx[coarse_abs:min(rx.size, coarse_abs + repeated_samples)]
    cfo_hz = estimate_cfo(frame_for_cfo, block_samples, rate, int(manifest['block_repeats']))

    expected_sync = coarse_abs + repeated_samples
    sync_search = int(manifest.get('sync_search_samples', 3500))
    lo = max(0, expected_sync - sync_search)
    hi = min(rx.size - sync_len, expected_sync + sync_search)
    if hi <= lo:
        raise ValueError('invalid sync search window')

    best_pos = lo
    best_score = -1.0
    ref = sync_samples.astype(np.complex64)
    ref_norm = float(np.vdot(ref, ref).real)
    for pos in range(lo, hi):
        cand = correct_cfo(rx[pos:pos + sync_len], rate, cfo_hz, pos)
        score = abs(np.vdot(ref, cand)) / math.sqrt(ref_norm * float(np.vdot(cand, cand).real) + 1e-12)
        if score > best_score:
            best_score = float(score)
            best_pos = pos

    frame_start = best_pos - repeated_samples
    if frame_start >= 0 and frame_start + repeated_samples <= rx.size:
        cfo_hz = estimate_cfo(
            rx[frame_start:frame_start + repeated_samples],
            block_samples,
            rate,
            int(manifest['block_repeats']),
        )
    data_start = best_pos + sync_len
    return frame_start, data_start, cfo_hz, best_score


def direct_sync_candidates(
    rx: np.ndarray,
    search_start: int,
    search_end: int,
    manifest: dict,
    sync_samples: np.ndarray,
    max_candidates: int,
) -> list[tuple[int, int, float, float]]:
    """按已知 sync 序列直接找候选帧。

    返回 `(frame_start, data_start, cfo_hz, sync_score)`，score 为归一化相关值。
    """
    sync_len = int(manifest['sync_samples'])
    repeated_samples = int(manifest['repeated_samples'])
    sps = int(manifest['sps'])
    rate = float(manifest['sample_rate'])
    block_samples = int(manifest['block_symbols']) * sps

    start = max(0, search_start + repeated_samples)
    stop = min(rx.size - sync_len, search_end + repeated_samples)
    if stop <= start or max_candidates <= 0:
        return []

    try:
        from scipy import signal
    except ImportError:
        return []

    segment = rx[start:stop + sync_len].astype(np.complex128, copy=False)
    ref = sync_samples.astype(np.complex128, copy=False)
    corr = signal.fftconvolve(segment, np.conj(ref[::-1]), mode='valid')
    energy = sliding_sum(np.abs(segment) ** 2, sync_len)
    ref_energy = float(np.vdot(ref, ref).real)
    score = np.abs(corr) / np.sqrt(ref_energy * energy + 1e-12)
    if score.size == 0:
        return []

    take = min(score.size, max_candidates * 8)
    top_idx = np.argpartition(score, score.size - take)[-take:]
    top_idx = top_idx[np.argsort(score[top_idx])[::-1]]

    min_spacing = max(sync_len, block_samples)
    candidates: list[tuple[int, int, float, float]] = []
    for rel_pos in top_idx:
        sync_pos = start + int(rel_pos)
        if any(abs(sync_pos - (item[1] - sync_len)) < min_spacing for item in candidates):
            continue
        frame_start = sync_pos - repeated_samples
        if frame_start < 0:
            continue
        cfo_hz = estimate_cfo(
            rx[frame_start:frame_start + repeated_samples],
            block_samples,
            rate,
            int(manifest['block_repeats']),
        )
        data_start = sync_pos + sync_len
        candidates.append((frame_start, data_start, cfo_hz, float(score[int(rel_pos)])))
        if len(candidates) >= max_candidates:
            break
    return candidates


def find_frame_candidates(
    rx: np.ndarray,
    search_start: int,
    search_end: int,
    manifest: dict,
    sync_samples: np.ndarray,
    max_candidates: int,
) -> list[tuple[int, int, float, float]]:
    candidates = direct_sync_candidates(rx, search_start, search_end, manifest, sync_samples, max_candidates)
    try:
        candidates.append(find_frame(rx, search_start, search_end, manifest, sync_samples))
    except ValueError:
        pass

    deduped: list[tuple[int, int, float, float]] = []
    for item in sorted(candidates, key=lambda value: value[3], reverse=True):
        if any(abs(item[1] - existing[1]) < int(manifest['sync_samples']) for existing in deduped):
            continue
        deduped.append(item)
        if len(deduped) >= max_candidates:
            break
    return deduped


def average_symbols(samples: np.ndarray, sps: int, nsymbols: int) -> np.ndarray:
    usable = samples[:nsymbols * sps]
    return usable.reshape(nsymbols, sps).mean(axis=1)


def symbols_for_bytes(nbytes: int) -> int:
    return (nbytes * 8 + 1) // 2


def decode_qpsk_bytes(
    rx: np.ndarray,
    rate: float,
    cfo_hz: float,
    data_start: int,
    sps: int,
    nbytes: int,
    h: complex,
    phase_rotation: complex,
) -> bytes:
    symbols_needed = symbols_for_bytes(nbytes)
    sample_count = symbols_needed * sps
    data_rx = correct_cfo(
        rx[data_start:data_start + sample_count],
        rate,
        cfo_hz,
        data_start,
    )
    if data_rx.size < sample_count:
        data_rx = np.pad(data_rx, (0, sample_count - data_rx.size))
    rx_symbols = average_symbols(data_rx, sps, symbols_needed) / h
    return bits_to_bytes(bits_from_qpsk_symbols(rx_symbols * phase_rotation), nbytes)


def header_plausible(header: dict, manifest: dict) -> bool:
    source_total = int(manifest.get('source_num_chunks', manifest.get('num_chunks', 0)))
    payload_bytes = int(manifest.get('payload_bytes', 0))
    chunk_bytes = int(manifest.get('chunk_bytes', DEFAULT_CHUNK_BYTES))
    seq = int(header['seq'])
    total = int(header['total'])
    payload_len = int(header['payload_len'])
    total_len = int(header['total_len'])
    if seq < 0 or total <= 0 or seq >= total:
        return False
    if source_total > 0 and total != source_total:
        return False
    if payload_bytes > 0 and total_len != payload_bytes:
        return False
    if payload_len <= 0 or payload_len > chunk_bytes:
        return False
    return True


def centered_offsets(radius: int) -> list[int]:
    offsets = [0]
    for value in range(1, radius + 1):
        offsets.extend([-value, value])
    return offsets


def decode_one_frame(
    rx: np.ndarray,
    manifest: dict,
    sync_symbols: np.ndarray,
    frame_start: int,
    data_start: int,
    cfo_hz: float,
    sync_score: float,
    frame_len: int,
    payload_len: int,
    expected_seq: int,
    timing_search_samples: int,
    has_chunk_header: bool,
) -> dict:
    sps = int(manifest['sps'])
    rate = float(manifest['sample_rate'])
    sync_len = int(manifest['sync_samples'])

    best: dict | None = None
    phase_rotations = (1.0 + 0.0j, 0.0 + 1.0j, -1.0 + 0.0j, 0.0 - 1.0j)
    for timing_offset in centered_offsets(timing_search_samples):
        candidate_data_start = data_start + timing_offset
        if candidate_data_start - sync_len < 0:
            continue

        sync_rx = correct_cfo(
            rx[candidate_data_start - sync_len:candidate_data_start],
            rate,
            cfo_hz,
            candidate_data_start - sync_len,
        )
        if sync_rx.size < sync_len:
            continue
        sync_rx_symbols = average_symbols(sync_rx, sps, sync_symbols.size)
        h = np.vdot(sync_symbols, sync_rx_symbols) / (np.vdot(sync_symbols, sync_symbols) + 1e-12)
        if abs(h) < 1e-9:
            h = 1.0 + 0.0j

        for phase_rotation in phase_rotations:
            header_valid = False
            header_error = ''
            protocol_seq = expected_seq
            protocol_payload_len = payload_len
            protocol_crc32 = None
            got = b''
            crc_ok = False
            got_frame_prefix = ''
            decode_full = True
            if has_chunk_header:
                try:
                    got_header = decode_qpsk_bytes(
                        rx,
                        rate,
                        cfo_hz,
                        candidate_data_start,
                        sps,
                        CHUNK_HEADER.size,
                        h,
                        phase_rotation,
                    )
                    got_frame_prefix = got_header[:4].hex()
                    header = parse_chunk_header(got_header)
                    header_valid = True
                    protocol_seq = int(header['seq'])
                    protocol_payload_len = int(header['payload_len'])
                    protocol_crc32 = int(header['crc32'])
                    decode_full = header_plausible(header, manifest) and protocol_seq == expected_seq
                    if not decode_full:
                        header_error = 'header valid but not selected for full decode'
                except ValueError as exc:
                    header_error = str(exc)
                    decode_full = False

            if decode_full:
                full_frame_len = CHUNK_HEADER.size + protocol_payload_len if has_chunk_header else frame_len
                got_frame = decode_qpsk_bytes(
                    rx,
                    rate,
                    cfo_hz,
                    candidate_data_start,
                    sps,
                    full_frame_len,
                    h,
                    phase_rotation,
                )
                got_frame_prefix = got_frame[:4].hex()
                if has_chunk_header:
                    got = got_frame[CHUNK_HEADER.size:CHUNK_HEADER.size + protocol_payload_len]
                    if len(got) == protocol_payload_len:
                        actual_crc = zlib.crc32(got) & 0xFFFFFFFF
                        crc_ok = actual_crc == protocol_crc32
                    else:
                        header_error = 'payload truncated'
                else:
                    got = got_frame[:payload_len]

            score = (
                3 if crc_ok and protocol_seq == expected_seq else 0,
                2 if crc_ok else 0,
                1 if header_valid else 0,
                -abs(protocol_seq - expected_seq),
                sync_score,
                -abs(timing_offset),
                abs(h),
            )
            current = {
                'score': score,
                'frame_start': frame_start,
                'data_start': candidate_data_start,
                'cfo_hz': cfo_hz,
                'sync_score': sync_score,
                'timing_offset': timing_offset,
                'phase_rotation': str(phase_rotation),
                'channel_gain_abs': float(abs(h)),
                'header_valid': header_valid,
                'header_error': header_error,
                'protocol_seq': protocol_seq,
                'protocol_payload_len': protocol_payload_len,
                'protocol_crc32': protocol_crc32,
                'crc_ok': crc_ok,
                'got': got,
                'got_frame_prefix': got_frame_prefix,
                'decoded_full': decode_full,
            }
            if best is None or score > best['score']:
                best = current
            if crc_ok and protocol_seq == expected_seq:
                return current

    if best is not None:
        return best
    return {
        'score': (0,),
        'frame_start': frame_start,
        'data_start': data_start,
        'cfo_hz': cfo_hz,
        'sync_score': sync_score,
        'timing_offset': 0,
        'phase_rotation': '0j',
        'channel_gain_abs': 0.0,
        'header_valid': False,
        'header_error': 'no decodable candidate',
        'protocol_seq': expected_seq,
        'protocol_payload_len': payload_len,
        'protocol_crc32': None,
        'crc_ok': False,
        'got': b'',
        'got_frame_prefix': '',
        'decoded_full': False,
    }


def decode_capture(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    manifest['sync_search_samples'] = args.sync_search_samples
    reference = args.reference.read_bytes()
    rx = sc16_to_complex(
        args.rx_sc16,
        offset_samples=args.rx_offset_samples,
        length_samples=args.rx_length_samples,
    )
    rx = rx - np.mean(rx)

    sps = int(manifest['sps'])
    rate = float(manifest['sample_rate'])
    _, sync_symbols, _, sync_samples = make_training(sps)
    sync_len = int(manifest['sync_samples'])
    chunk_bytes = int(manifest['chunk_bytes'])
    frame_count = int(manifest['num_chunks'])
    source_total_chunks = int(manifest.get('source_num_chunks', frame_count))
    frame_chunk_indices = manifest.get('chunk_indices', list(range(frame_count)))
    frame_chunk_indices = [int(item) for item in frame_chunk_indices]
    if len(frame_chunk_indices) != frame_count:
        raise ValueError('manifest chunk_indices length does not match num_chunks')
    if args.max_chunks > 0:
        frame_count = min(frame_count, args.max_chunks)
        frame_chunk_indices = frame_chunk_indices[:frame_count]
    has_chunk_header = int(manifest.get('chunk_header_bytes', 0)) == CHUNK_HEADER.size
    chunk_payload_lens = manifest.get('chunk_payload_lens')
    chunk_frame_lens = manifest.get('chunk_frame_lens')
    source_chunk_payload_lens = manifest.get('source_chunk_payload_lens')
    if source_chunk_payload_lens is None:
        source_chunk_payload_lens = chunk_payload_lens

    chunk_results = []
    decoded_by_seq: dict[int, bytes] = {}
    best_effort_by_seq: dict[int, bytes] = {}
    crc_ok_by_seq: dict[int, bytes] = {}
    predicted_start = int(args.search_start_sec * rate)
    first_search_end = int(args.search_end_sec * rate)

    for idx in range(frame_count):
        expected_seq = frame_chunk_indices[idx]
        payload_len = (
            int(chunk_payload_lens[idx])
            if chunk_payload_lens is not None
            else min(chunk_bytes, len(reference) - expected_seq * chunk_bytes)
        )
        frame_len = (
            int(chunk_frame_lens[idx])
            if chunk_frame_lens is not None
            else payload_len + (CHUNK_HEADER.size if has_chunk_header else 0)
        )
        if payload_len <= 0 or frame_len <= 0:
            break

        if idx == 0:
            search_start = predicted_start
            search_end = first_search_end
        else:
            half = args.local_search_samples
            search_start = predicted_start - half
            search_end = predicted_start + half

        candidates = find_frame_candidates(
            rx, search_start, search_end, manifest, sync_samples, args.frame_candidates
        )
        if not candidates:
            candidates = [(search_start, search_start + int(manifest['preamble_samples']), 0.0, 0.0)]

        decoded_candidates = [
            decode_one_frame(
                rx,
                manifest,
                sync_symbols,
                frame_start,
                data_start,
                cfo_hz,
                sync_score,
                frame_len,
                payload_len,
                expected_seq,
                args.timing_search_samples,
                has_chunk_header,
            )
            for frame_start, data_start, cfo_hz, sync_score in candidates
        ]
        best = max(decoded_candidates, key=lambda item: item['score'])

        frame_start = int(best['frame_start'])
        data_start = int(best['data_start'])
        cfo_hz = float(best['cfo_hz'])
        sync_score = float(best['sync_score'])
        header_valid = bool(best['header_valid'])
        header_error = str(best['header_error'])
        protocol_seq = int(best['protocol_seq'])
        protocol_payload_len = int(best['protocol_payload_len'])
        protocol_crc32 = best['protocol_crc32']
        crc_ok = bool(best['crc_ok'])
        got = best['got']

        if len(got) < payload_len:
            got_for_compare = got + bytes(payload_len - len(got))
        else:
            got_for_compare = got[:payload_len]

        if (
            has_chunk_header
            and header_valid
            and crc_ok
            and 0 <= protocol_seq < source_total_chunks
            and protocol_payload_len == len(got)
        ):
            crc_ok_by_seq[protocol_seq] = got
            decoded_by_seq[protocol_seq] = got
        if 0 <= protocol_seq < source_total_chunks and len(got_for_compare) == payload_len:
            best_effort_by_seq[protocol_seq] = got_for_compare

        ref_seq = protocol_seq if header_valid and 0 <= protocol_seq < source_total_chunks else expected_seq
        ref_chunk = reference[ref_seq * chunk_bytes:ref_seq * chunk_bytes + payload_len]
        if len(got_for_compare) < len(ref_chunk):
            got_compare = got_for_compare + bytes(len(ref_chunk) - len(got_for_compare))
        else:
            got_compare = got_for_compare[:len(ref_chunk)]
        payload_bits_needed = len(ref_chunk) * 8
        byte_errors = sum(a != b for a, b in zip(got_compare, ref_chunk))
        bit_errors = int(
            np.count_nonzero(bytes_to_bits(got_compare)[:payload_bits_needed] != bytes_to_bits(ref_chunk))
        )
        exact = byte_errors == 0 and (not has_chunk_header or protocol_seq == expected_seq)
        chunk_results.append({
            'frame': idx,
            'chunk': expected_seq,
            'protocol_seq': protocol_seq,
            'protocol_payload_len': protocol_payload_len,
            'protocol_crc32': protocol_crc32,
            'header_valid': header_valid,
            'header_error': header_error,
            'crc_ok': crc_ok,
            'frame_start': frame_start,
            'data_start': data_start,
            'cfo_hz': cfo_hz,
            'sync_score': sync_score,
            'timing_offset': int(best['timing_offset']),
            'phase_rotation': best['phase_rotation'],
            'channel_gain_abs': best['channel_gain_abs'],
            'candidate_count': len(candidates),
            'got_frame_prefix': best['got_frame_prefix'],
            'decoded_full': bool(best.get('decoded_full', False)),
            'chunk_len': payload_len,
            'frame_len': frame_len,
            'byte_errors': byte_errors,
            'bit_errors': bit_errors,
            'exact': exact,
        })

        nominal_frame_samples = (
            int(manifest['gap_samples'])
            + int(manifest['repeated_samples'])
            + int(manifest['sync_samples'])
            + int(manifest['chunk_sample_counts'][idx])
        )
        if crc_ok or header_valid:
            predicted_start = frame_start + nominal_frame_samples
        else:
            predicted_start = predicted_start + nominal_frame_samples

    decoded_parts: list[bytes] = []
    for seq in range(source_total_chunks):
        seq_len = (
            int(chunk_payload_lens[seq])
            if source_chunk_payload_lens is None and chunk_payload_lens is not None
            else min(chunk_bytes, len(reference) - seq * chunk_bytes)
        )
        if source_chunk_payload_lens is not None:
            seq_len = int(source_chunk_payload_lens[seq])
        decoded_parts.append(decoded_by_seq.get(seq, best_effort_by_seq.get(seq, bytes(seq_len))))
    decoded_bytes = b''.join(decoded_parts)[:len(reference)]
    compared = reference[:len(decoded_bytes)]
    compared_transmitted_bytes = sum(int(item['chunk_len']) for item in chunk_results)
    total_bits = compared_transmitted_bytes * 8
    bit_errors = sum(int(item['bit_errors']) for item in chunk_results)
    byte_errors = sum(int(item['byte_errors']) for item in chunk_results)
    exact_chunks = sum(1 for item in chunk_results if item['exact'])
    bad_chunks = len(chunk_results) - exact_chunks
    header_valid_count = sum(1 for item in chunk_results if item['header_valid'])
    crc_ok_count = sum(1 for item in chunk_results if item['crc_ok'])
    all_seq = set(frame_chunk_indices)
    decoded_seq = set(crc_ok_by_seq)
    missing_chunks = sorted(all_seq - decoded_seq)
    ber = bit_errors / total_bits if total_bits else 1.0
    per = bad_chunks / len(chunk_results) if chunk_results else 1.0
    protocol_per = len(missing_chunks) / len(frame_chunk_indices) if frame_chunk_indices else 1.0

    if args.out_bin is not None:
        args.out_bin.parent.mkdir(parents=True, exist_ok=True)
        args.out_bin.write_bytes(decoded_bytes)

    if chunk_results:
        first = chunk_results[0]['frame_start']
        last_idx = len(chunk_results) - 1
        last_data_start = chunk_results[-1]['data_start']
        last_samples = int(manifest['chunk_sample_counts'][last_idx])
        detected_airtime_ms = (last_data_start + last_samples - first) / rate * 1000.0
    else:
        detected_airtime_ms = 0.0

    effective_mbps = (
        compared_transmitted_bytes * 8 / (detected_airtime_ms / 1000.0) / 1e6
    ) if detected_airtime_ms else 0.0
    crc_ok_indices = sorted(crc_ok_by_seq)
    summary = {
        'rx_sc16': str(args.rx_sc16),
        'manifest': str(args.manifest),
        'reference': str(args.reference),
        'decoded_bytes': len(decoded_bytes),
        'compared_bytes': len(compared),
        'chunks_decoded': len(chunk_results),
        'frames_transmitted': len(frame_chunk_indices),
        'transmitted_chunks': frame_chunk_indices,
        'total_chunks': source_total_chunks,
        'chunk_exact': exact_chunks,
        'header_valid': header_valid_count,
        'crc_ok': crc_ok_count,
        'missing_chunks': missing_chunks,
        'crc_ok_indices': crc_ok_indices,
        'byte_errors': byte_errors,
        'bit_errors': bit_errors,
        'ber': ber,
        'per': per,
        'protocol_per': protocol_per,
        'detected_airtime_ms': detected_airtime_ms,
        'effective_payload_mbps': effective_mbps,
        'sample_rate': rate,
        'sps': sps,
        'payload_bytes': int(manifest['payload_bytes']),
        'compared_transmitted_bytes': compared_transmitted_bytes,
        'chunk_results': chunk_results,
    }

    print(f'rx_sc16={args.rx_sc16}')
    print(f'rx_offset_samples={args.rx_offset_samples}')
    print(f'rx_length_samples={args.rx_length_samples}')
    print(f'reference={args.reference}')
    print(f'decoded_bytes={len(decoded_bytes)}')
    print(f'compared_bytes={len(compared)}')
    print(f'compared_transmitted_bytes={compared_transmitted_bytes}')
    print(f'chunks_decoded={len(chunk_results)}/{len(frame_chunk_indices)}')
    print(f'source_total_chunks={source_total_chunks}')
    print(f'transmitted_chunks={frame_chunk_indices}')
    print(f'chunk_exact={exact_chunks}/{len(chunk_results)}')
    print(f'header_valid={header_valid_count}/{len(chunk_results)}')
    print(f'crc_ok={crc_ok_count}/{len(frame_chunk_indices)}')
    print(f'missing_chunks={missing_chunks}')
    print(f'byte_errors={byte_errors}')
    print(f'bit_errors={bit_errors}')
    print(f'ber={ber:.9g}')
    print(f'per={per:.9g}')
    print(f'protocol_per={protocol_per:.9g}')
    print(f'detected_airtime_ms={detected_airtime_ms:.3f}')
    print(f'effective_payload_mbps={effective_mbps:.3f}')
    if chunk_results:
        exact_indices = [item['chunk'] for item in chunk_results if item['exact']]
        bad_indices = [item['chunk'] for item in chunk_results if not item['exact']]
        print(f'exact_chunk_indices={exact_indices}')
        print(f'bad_chunk_indices={bad_indices}')
        print(f'crc_ok_indices={crc_ok_indices}')
        cfo_values = [item['cfo_hz'] for item in chunk_results]
        sync_scores = [item['sync_score'] for item in chunk_results]
        print(f'cfo_hz_min={min(cfo_values):.3f}')
        print(f'cfo_hz_max={max(cfo_values):.3f}')
        print(f'sync_score_min={min(sync_scores):.6f}')
        print(f'sync_score_max={max(sync_scores):.6f}')
        print('chunk_summary=' + json.dumps(chunk_results[:8], ensure_ascii=False))
        if len(chunk_results) > 8:
            print(f'chunk_summary_truncated={len(chunk_results) - 8}')

    if args.summary_json is not None:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'summary_json={args.summary_json}')

    return 0 if bit_errors == 0 and not missing_chunks else 2


def merge_rounds(args: argparse.Namespace) -> int:
    if len(args.summary_json) != len(args.decoded_bin):
        raise ValueError('--summary-json and --decoded-bin counts must match')

    reference = args.reference.read_bytes()
    source_chunks = split_payload(reference, args.chunk_bytes)
    merged_by_seq: dict[int, bytes] = {}
    accepted_by_round: list[dict] = []

    for round_idx, (summary_path, decoded_path) in enumerate(zip(args.summary_json, args.decoded_bin)):
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        decoded = decoded_path.read_bytes()
        accepted: list[int] = []
        rejected: list[dict] = []

        for item in summary.get('chunk_results', []):
            if not item.get('crc_ok', False):
                continue
            seq = int(item.get('protocol_seq', item.get('chunk', -1)))
            if seq < 0 or seq >= len(source_chunks):
                rejected.append({'seq': seq, 'reason': 'seq out of range'})
                continue
            payload_len = int(item.get('protocol_payload_len') or len(source_chunks[seq]))
            start = seq * args.chunk_bytes
            chunk = decoded[start:start + payload_len]
            if len(chunk) != payload_len:
                rejected.append({'seq': seq, 'reason': 'decoded chunk truncated'})
                continue
            protocol_crc32 = item.get('protocol_crc32')
            if protocol_crc32 is not None and (zlib.crc32(chunk) & 0xFFFFFFFF) != int(protocol_crc32):
                rejected.append({'seq': seq, 'reason': 'crc mismatch after slicing decoded-bin'})
                continue
            if seq not in merged_by_seq:
                merged_by_seq[seq] = chunk
            accepted.append(seq)

        accepted_by_round.append({
            'round': round_idx,
            'summary_json': str(summary_path),
            'decoded_bin': str(decoded_path),
            'accepted_chunks': sorted(set(accepted)),
            'rejected_chunks': rejected,
        })

    merged_parts = [merged_by_seq.get(seq, bytes(len(chunk))) for seq, chunk in enumerate(source_chunks)]
    merged = b''.join(merged_parts)
    args.out_bin.parent.mkdir(parents=True, exist_ok=True)
    args.out_bin.write_bytes(merged)

    crc_ok_indices = sorted(merged_by_seq)
    missing_chunks = [seq for seq in range(len(source_chunks)) if seq not in merged_by_seq]
    byte_errors = sum(a != b for a, b in zip(merged, reference))
    bit_errors = int(np.count_nonzero(bytes_to_bits(merged)[:len(reference) * 8] != bytes_to_bits(reference)))
    exact = byte_errors == 0 and not missing_chunks and len(merged) == len(reference)
    summary = {
        'reference': str(args.reference),
        'out_bin': str(args.out_bin),
        'total_chunks': len(source_chunks),
        'crc_ok_indices': crc_ok_indices,
        'missing_chunks': missing_chunks,
        'byte_errors': byte_errors,
        'bit_errors': bit_errors,
        'exact': exact,
        'sha256': hashlib.sha256(merged).hexdigest(),
        'reference_sha256': hashlib.sha256(reference).hexdigest(),
        'rounds': accepted_by_round,
    }
    if args.summary_out is not None:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(f'out_bin={args.out_bin}')
    print(f'total_chunks={len(source_chunks)}')
    print(f'crc_ok={len(crc_ok_indices)}/{len(source_chunks)}')
    print(f'missing_chunks={missing_chunks}')
    print(f'byte_errors={byte_errors}')
    print(f'bit_errors={bit_errors}')
    print(f'exact={str(exact).lower()}')
    if args.summary_out is not None:
        print(f'summary_out={args.summary_out}')
    return 0 if exact else 2


def main() -> int:
    args = parse_args()
    if args.cmd == 'make':
        return make_waveform(args)
    if args.cmd == 'decode':
        return decode_capture(args)
    if args.cmd == 'merge':
        return merge_rounds(args)
    raise RuntimeError(f'unknown command: {args.cmd}')


if __name__ == '__main__':
    raise SystemExit(main())
