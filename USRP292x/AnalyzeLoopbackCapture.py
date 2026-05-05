#!/usr/bin/env python3
"""分析官方 txrx_loopback_to_file 抓到的 short IQ 文件。"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Analyze USRP loopback IQ capture.')
    parser.add_argument('input', type=Path, help='Path to short IQ capture file')
    parser.add_argument('--rate', type=float, default=1_000_000, help='Sample rate in sps')
    parser.add_argument(
        '--expected-tone',
        type=float,
        default=None,
        help='Expected tone frequency in Hz for local-peak check',
    )
    parser.add_argument(
        '--window-samples',
        type=int,
        default=65536,
        help='FFT window length',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = np.fromfile(args.input, dtype=np.int16)
    if raw.size < 2 or raw.size % 2:
        raise SystemExit('输入文件不是有效的 interleaved int16 IQ 文件。')

    iq = raw.astype(np.float32).reshape(-1, 2)
    z = iq[:, 0] + 1j * iq[:, 1]
    mag = np.abs(z)

    print(f'input={args.input}')
    print(f'complex_samples={z.size}')
    print(f'nonzero_ratio={np.count_nonzero(raw) / raw.size:.6f}')
    print(f'mag_mean={mag.mean():.6f}')
    print(f'mag_rms={np.sqrt(np.mean(mag * mag)):.6f}')
    print(f'mag_max={mag.max():.6f}')
    print(f'avg_power_dbfs_approx={10 * np.log10((np.mean(mag * mag) + 1e-12) / (32767.0**2)):.6f}')

    z = z - z.mean()
    n = min(args.window_samples, z.size)
    seg = z[:n] * np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(seg))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1 / args.rate))
    spec_mag = np.abs(spec)
    median_mag = float(np.median(spec_mag))

    dc_excluded = np.abs(freq) >= 5_000
    peak_idx = int(np.argmax(spec_mag[dc_excluded]))
    peak_freq = float(freq[dc_excluded][peak_idx])
    peak_mag = float(spec_mag[dc_excluded][peak_idx])
    print(f'strongest_non_dc_hz={peak_freq:.6f}')
    print(f'strongest_non_dc_over_median_db={20 * np.log10((peak_mag + 1e-12) / (median_mag + 1e-12)):.6f}')

    if args.expected_tone is not None:
        tone_mask = np.abs(freq - args.expected_tone) <= 5_000
        if np.any(tone_mask):
            tone_idx = int(np.argmax(spec_mag[tone_mask]))
            tone_freq = float(freq[tone_mask][tone_idx])
            tone_mag = float(spec_mag[tone_mask][tone_idx])
            print(f'expected_tone_hz={args.expected_tone:.6f}')
            print(f'peak_near_expected_hz={tone_freq:.6f}')
            print(f'peak_near_expected_over_median_db={20 * np.log10((tone_mag + 1e-12) / (median_mag + 1e-12)):.6f}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
