#!/usr/bin/env python3
"""估算 1x32x32x32 latent 在 USRP292x 数据面上的最低空口时间。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


DEFAULT_RATES = [219_298, 1_000_000, 2_500_000, 5_000_000, 10_000_000]
DEFAULT_INPUT = Path(
    'artifacts/usrp_latent_demo_live/20260425_210417/assets/source_latent.npz'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Estimate latent OTA airtime.')
    parser.add_argument(
        '--input',
        type=Path,
        default=DEFAULT_INPUT,
        help='latent .npz/.npy/.bin path',
    )
    parser.add_argument(
        '--job-id',
        default=None,
        help='job_id written into metadata',
    )
    parser.add_argument(
        '--samples-per-symbol',
        type=float,
        default=2.0,
        help='RRC/PHY samples per symbol; 2 is a realistic first target',
    )
    parser.add_argument(
        '--rates',
        type=float,
        nargs='*',
        default=DEFAULT_RATES,
        help='complex sample rates to estimate, in sample/s',
    )
    parser.add_argument(
        '--write-dir',
        type=Path,
        default=None,
        help='optional directory to write raw payload and packed blob',
    )
    return parser.parse_args()


def load_latent(path: Path) -> tuple[np.ndarray, dict]:
    if path.suffix == '.bin':
        raw = path.read_bytes()
        n = len(raw) // 4
        if n == 32 * 32 * 32:
            shape = (1, 32, 32, 32)
        elif n == 3 * 64 * 64:
            shape = (1, 3, 64, 64)
        else:
            shape = (n,)
        arr = np.frombuffer(raw, dtype=np.float32).reshape(shape).copy()
        return arr, {'shape': list(shape), 'dtype': 'float32', 'source_format': 'raw-float32-bin'}

    if path.suffix == '.npz':
        data = np.load(path)
        if {'quant', 'scale', 'zero_point'}.issubset(data.files):
            q = np.asarray(data['quant'], dtype=np.float32)
            s = np.asarray(data['scale'], dtype=np.float32)
            zp = np.asarray(data['zero_point'], dtype=np.float32)
            arr = (q - zp) * s
            source_format = 'quant-scale-zero_point-npz'
        elif 'latent' in data.files:
            arr = np.asarray(data['latent'], dtype=np.float32)
            source_format = 'latent-npz'
        else:
            key = data.files[0]
            arr = np.asarray(data[key], dtype=np.float32)
            source_format = f'{key}-npz'
        return arr, {'shape': list(arr.shape), 'dtype': 'float32', 'source_format': source_format}

    if path.suffix == '.npy':
        arr = np.load(path).astype(np.float32)
        return arr, {'shape': list(arr.shape), 'dtype': 'float32', 'source_format': 'npy'}

    raise ValueError(f'unsupported input format: {path}')


def pack_blob(arr: np.ndarray, info: dict, job_id: str) -> tuple[bytes, bytes, dict]:
    payload = arr.astype(np.float32, copy=False).tobytes()
    sha = hashlib.sha256(payload).hexdigest()
    meta = {
        'job_id': job_id,
        'shape': info['shape'],
        'dtype': 'float32',
        'sha256': sha,
        'size': len(payload),
    }
    meta_json = json.dumps(meta, separators=(',', ':')).encode('utf-8')
    blob = len(meta_json).to_bytes(4, 'big') + meta_json + payload
    return payload, blob, meta


def fmt_rate(rate: float) -> str:
    if rate >= 1_000_000:
        return f'{rate / 1_000_000:.3g} Msps'
    return f'{rate / 1_000:.3g} kSps'


def main() -> int:
    args = parse_args()
    arr, info = load_latent(args.input)
    job_id = args.job_id or args.input.stem
    payload, blob, meta = pack_blob(arr, info, job_id)

    print(f'input={args.input}')
    print(f'source_format={info["source_format"]}')
    print(f'shape={info["shape"]}')
    print(f'dtype=float32')
    print(f'payload_bytes={len(payload)}')
    print(f'packed_blob_bytes={len(blob)}')
    print(f'metadata_bytes={len(blob) - len(payload) - 4}')
    print(f'sha256={meta["sha256"]}')
    print(f'samples_per_symbol={args.samples_per_symbol:g}')

    schemes = [
        ('BPSK uncoded', 1.0, 1.0),
        ('BPSK r=1/2', 1.0, 0.5),
        ('QPSK uncoded', 2.0, 1.0),
        ('QPSK r=3/4', 2.0, 0.75),
        ('QPSK r=1/2', 2.0, 0.5),
    ]

    bits = len(blob) * 8
    print()
    print('| sample_rate | scheme | payload_rate | airtime_ms |')
    print('|---:|---|---:|---:|')
    for rate in args.rates:
        symbol_rate = rate / args.samples_per_symbol
        for name, bits_per_symbol, code_rate in schemes:
            payload_rate = symbol_rate * bits_per_symbol * code_rate
            airtime_ms = bits / payload_rate * 1000.0
            print(
                f'| `{fmt_rate(rate)}` | `{name}` | '
                f'`{payload_rate / 1_000_000:.3f} Mbps` | `{airtime_ms:.1f}` |'
            )

    if args.write_dir is not None:
        args.write_dir.mkdir(parents=True, exist_ok=True)
        raw_path = args.write_dir / f'{job_id}_float32_payload.bin'
        blob_path = args.write_dir / f'{job_id}_wire_blob.bin'
        meta_path = args.write_dir / f'{job_id}_meta.json'
        raw_path.write_bytes(payload)
        blob_path.write_bytes(blob)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print()
        print(f'raw_payload={raw_path}')
        print(f'wire_blob={blob_path}')
        print(f'meta_json={meta_path}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
