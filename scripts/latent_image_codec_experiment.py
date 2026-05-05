#!/usr/bin/env python3
"""latent_image_codec_experiment.py

把 quant latent 平铺成灰度图片，试验 PNG / WebP / JPEG 等图片编解码方式，
并统计压缩率、latent 误差，以及在可用时的 JSCC 重建质量退化。

设计目标：
1. 不改现有 OTA 主链路，只做离线实验。
2. 没有 torch 时也能跑 latent 级统计。
3. 如果给出 jscc root 且 torch 可用，则额外计算 recon PSNR / SSIM。
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


# ── Metrics ───────────────────────────────────────────────────────────────

def compute_psnr(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算 PSNR，输入假设已归一化到 [0, 1]。"""
    mse = float(np.mean((img1 - img2) ** 2))
    if mse < 1e-12:
        return float('inf')
    return float(10.0 * np.log10(1.0 / mse))


def _gaussian_kernel(size: int = 11, sigma: float = 1.5) -> np.ndarray:
    coords = np.arange(size) - size // 2
    g = np.exp(-(coords ** 2) / (2 * sigma ** 2))
    kernel = np.outer(g, g)
    return kernel / kernel.sum()


def _ssim_channel(img1: np.ndarray, img2: np.ndarray, kernel: np.ndarray) -> float:
    from scipy.ndimage import convolve

    c1 = 0.01 ** 2
    c2 = 0.03 ** 2

    mu1 = convolve(img1, kernel, mode='reflect')
    mu2 = convolve(img2, kernel, mode='reflect')
    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = convolve(img1 ** 2, kernel, mode='reflect') - mu1_sq
    sigma2_sq = convolve(img2 ** 2, kernel, mode='reflect') - mu2_sq
    sigma12 = convolve(img1 * img2, kernel, mode='reflect') - mu1_mu2

    numerator = (2 * mu1_mu2 + c1) * (2 * sigma12 + c2)
    denominator = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    return float((numerator / denominator).mean())


def compute_ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算 SSIM，输入支持 HWC 或 CHW，像素范围假设为 [0, 1]。"""
    try:
        kernel = _gaussian_kernel()
        if img1.ndim == 3 and img1.shape[0] in (1, 3):
            vals = [_ssim_channel(img1[c], img2[c], kernel) for c in range(img1.shape[0])]
            return float(np.mean(vals))
        if img1.ndim == 3 and img1.shape[-1] in (1, 3):
            vals = [_ssim_channel(img1[..., c], img2[..., c], kernel) for c in range(img1.shape[-1])]
            return float(np.mean(vals))
        return _ssim_channel(img1, img2, kernel)
    except ImportError:
        return float('nan')


# ── Codec Spec ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CodecSpec:
    name: str
    fmt: str
    save_kwargs: dict[str, Any]


CODECS = [
    CodecSpec('png', 'PNG', {}),
    CodecSpec('webp-lossless', 'WEBP', {'lossless': True, 'quality': 100, 'method': 6}),
    CodecSpec('jpeg-q95', 'JPEG', {'quality': 95, 'subsampling': 0}),
    CodecSpec('jpeg-q85', 'JPEG', {'quality': 85, 'subsampling': 0}),
    CodecSpec('jpeg-q75', 'JPEG', {'quality': 75, 'subsampling': 0}),
]


# ── Latent Loading ────────────────────────────────────────────────────────

@dataclass
class QuantLatent:
    name: str
    path: Path
    quant_u8: np.ndarray
    scale: float
    zero_point: float
    meta: dict[str, Any]


def import_torch():
    try:
        import torch  # type: ignore
        return torch
    except Exception:
        return None


def torch_load_compat(torch_mod, path: Path):
    try:
        return torch_mod.load(path, map_location='cpu', weights_only=False)
    except TypeError:
        return torch_mod.load(path, map_location='cpu')


def load_quant_latent(path: Path, torch_mod=None) -> QuantLatent:
    name = path.stem
    meta: dict[str, Any] = {}

    if path.suffix.lower() == '.pt':
        if torch_mod is None:
            raise RuntimeError('加载 .pt latent 需要 torch')
        payload = torch_load_compat(torch_mod, path)
        quant = payload['quant']
        scale = float(payload['scale'])
        zero_point = float(payload['zero_point'])
        quant_u8 = np.asarray(quant.cpu().numpy(), dtype=np.uint8)
        meta = {
            'snr': payload.get('snr'),
            'config_str': payload.get('config_str'),
        }
    elif path.suffix.lower() == '.npz':
        payload = np.load(path)
        if 'quant' not in payload or 'scale' not in payload or 'zero_point' not in payload:
            raise KeyError(f'{path} 缺少 quant/scale/zero_point')
        quant = np.asarray(payload['quant'])
        scale = float(np.asarray(payload['scale']).reshape(()))
        zero_point = float(np.asarray(payload['zero_point']).reshape(()))
        if quant.dtype == np.uint8:
            quant_u8 = quant.astype(np.uint8, copy=False)
        elif quant.dtype == np.int8:
            quant_u8 = (quant.astype(np.int16) + 128).astype(np.uint8)
            meta['quant_encoding'] = 'int8_offset_128'
        else:
            raise ValueError(f'暂不支持 {path} 的 quant dtype={quant.dtype}')
    else:
        raise ValueError(f'不支持的 latent 文件: {path}')

    if quant_u8.ndim == 4 and quant_u8.shape[0] == 1:
        quant_u8 = quant_u8[0]
    if quant_u8.ndim != 3:
        raise ValueError(f'期望量化 latent 为 [C,H,W] 或 [1,C,H,W]，实际是 {quant_u8.shape}')

    meta['source_suffix'] = path.suffix.lower()
    meta['original_file_size'] = path.stat().st_size
    return QuantLatent(
        name=name,
        path=path,
        quant_u8=quant_u8,
        scale=scale,
        zero_point=zero_point,
        meta=meta,
    )


# ── Tiling / Untiling ─────────────────────────────────────────────────────

def choose_grid(channels: int) -> tuple[int, int]:
    cols = max(1, int(math.ceil(math.sqrt(channels))))
    rows = int(math.ceil(channels / cols))
    return rows, cols


def tile_quant_to_image(quant_u8: np.ndarray) -> tuple[np.ndarray, dict[str, int]]:
    channels, height, width = quant_u8.shape
    rows, cols = choose_grid(channels)
    canvas = np.zeros((rows * height, cols * width), dtype=np.uint8)

    for idx in range(channels):
        row = idx // cols
        col = idx % cols
        y0 = row * height
        x0 = col * width
        canvas[y0:y0 + height, x0:x0 + width] = quant_u8[idx]

    return canvas, {'channels': channels, 'height': height, 'width': width, 'rows': rows, 'cols': cols}


def untile_image_to_quant(image_u8: np.ndarray, layout: dict[str, int]) -> np.ndarray:
    channels = layout['channels']
    height = layout['height']
    width = layout['width']
    rows = layout['rows']
    cols = layout['cols']

    expected_shape = (rows * height, cols * width)
    if image_u8.shape != expected_shape:
        raise ValueError(f'还原图尺寸不匹配: got={image_u8.shape}, expected={expected_shape}')

    out = np.zeros((channels, height, width), dtype=np.uint8)
    for idx in range(channels):
        row = idx // cols
        col = idx % cols
        y0 = row * height
        x0 = col * width
        out[idx] = image_u8[y0:y0 + height, x0:x0 + width]
    return out


# ── JSCC Decoder Bridge ───────────────────────────────────────────────────

class JsccDecoder:
    def __init__(self, jscc_root: Path, torch_mod):
        self.jscc_root = jscc_root
        self.torch = torch_mod
        self._generator = None
        self._generator_state = None

    def _ensure_imports(self):
        jscc_pkg_root = self.jscc_root / 'jscc'
        if str(jscc_pkg_root) not in sys.path:
            sys.path.insert(0, str(jscc_pkg_root))
        from channel_configs import decode_config  # type: ignore
        from src.network.sub_generator import SubMobileGenerator  # type: ignore
        return decode_config, SubMobileGenerator

    def _load_generator(self, config_str: str, latent_channels: int):
        if self._generator is not None:
            return self._generator

        decode_config, sub_generator_cls = self._ensure_imports()
        state_path = self.jscc_root / 'export' / 'compressed_gan.pt'
        raw_state = torch_load_compat(self.torch, state_path)
        state = {
            key: value
            for key, value in raw_state.items()
            if not key.endswith('total_ops') and not key.endswith('total_params')
        }
        resblock_indices = []
        for key in state.keys():
            match = re.match(r'resblock_(\d+)\.', key)
            if match:
                resblock_indices.append(int(match.group(1)))
        n_residual_blocks = max(resblock_indices) + 1 if resblock_indices else 5

        generator = sub_generator_cls(
            3,
            decode_config(config_str),
            C=latent_channels,
            n_residual_blocks=n_residual_blocks,
        )
        generator.load_state_dict(state, strict=True)
        generator.eval()
        self._generator = generator
        self._generator_state = str(state_path)
        return generator

    def reconstruct(self, quant_u8: np.ndarray, scale: float, zero_point: float, *, config_str: str) -> np.ndarray:
        generator = self._load_generator(config_str=config_str, latent_channels=quant_u8.shape[0])
        torch_mod = self.torch
        with torch_mod.no_grad():
            q = torch_mod.from_numpy(quant_u8.astype(np.float32, copy=False))
            latent = (q - zero_point) * scale
            out = generator(latent.unsqueeze(0)).squeeze(0).cpu().numpy().astype(np.float32)
        return np.clip(out, 0.0, 1.0)


# ── Experiment Core ───────────────────────────────────────────────────────

def encode_decode_codec(atlas_u8: np.ndarray, codec: CodecSpec) -> tuple[bytes, np.ndarray]:
    image = Image.fromarray(atlas_u8, mode='L')
    buffer = io.BytesIO()
    image.save(buffer, format=codec.fmt, **codec.save_kwargs)
    raw = buffer.getvalue()

    restored = Image.open(io.BytesIO(raw)).convert('L')
    restored_u8 = np.asarray(restored, dtype=np.uint8)
    return raw, restored_u8


def summarise_numeric(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    return {
        'mean': float(arr.mean()),
        'median': float(np.median(arr)),
        'min': float(arr.min()),
        'max': float(arr.max()),
    }


def run_experiment(args) -> dict[str, Any]:
    torch_mod = import_torch()
    if args.jscc_root and torch_mod is None:
        print('[warn] 已给出 --jscc-root，但当前 python 没有 torch，只能跑 latent 级统计。')

    decoder = None
    if args.jscc_root and torch_mod is not None:
        decoder = JsccDecoder(Path(args.jscc_root), torch_mod)

    input_paths = [Path(p) for p in sorted(glob.glob(args.input_glob))]
    if args.limit > 0:
        input_paths = input_paths[:args.limit]
    if not input_paths:
        raise SystemExit(f'未匹配到 latent 文件: {args.input_glob}')

    results: dict[str, Any] = {
        'input_glob': args.input_glob,
        'num_files': len(input_paths),
        'jscc_root': args.jscc_root or '',
        'torch_available': torch_mod is not None,
        'reconstruction_enabled': decoder is not None,
        'codecs': [codec.name for codec in CODECS],
        'files': [],
        'summary': {},
    }

    per_codec_size: dict[str, list[float]] = {codec.name: [] for codec in CODECS}
    per_codec_ratio: dict[str, list[float]] = {codec.name: [] for codec in CODECS}
    per_codec_latent_mse: dict[str, list[float]] = {codec.name: [] for codec in CODECS}
    per_codec_qdiff: dict[str, list[float]] = {codec.name: [] for codec in CODECS}
    per_codec_psnr: dict[str, list[float]] = {codec.name: [] for codec in CODECS}
    per_codec_ssim: dict[str, list[float]] = {codec.name: [] for codec in CODECS}

    for index, path in enumerate(input_paths, start=1):
        item = load_quant_latent(path, torch_mod=torch_mod)
        atlas_u8, layout = tile_quant_to_image(item.quant_u8)
        baseline_quant_bytes = int(item.quant_u8.size)

        file_result: dict[str, Any] = {
            'name': item.name,
            'path': str(item.path),
            'shape': list(item.quant_u8.shape),
            'scale': item.scale,
            'zero_point': item.zero_point,
            'meta': item.meta,
            'baseline_quant_bytes': baseline_quant_bytes,
            'codec_results': {},
        }

        baseline_recon = None
        config_str = str(item.meta.get('config_str') or args.default_config_str or '')
        if decoder is not None:
            if not config_str:
                raise RuntimeError(f'{path} 缺少 config_str，且未提供 --default-config-str')
            baseline_recon = decoder.reconstruct(
                item.quant_u8,
                item.scale,
                item.zero_point,
                config_str=config_str,
            )

        print(f'[{index}/{len(input_paths)}] {path.name} shape={item.quant_u8.shape} size={item.meta["original_file_size"]}B')

        for codec in CODECS:
            encoded_bytes, restored_atlas_u8 = encode_decode_codec(atlas_u8, codec)
            restored_quant_u8 = untile_image_to_quant(restored_atlas_u8, layout)
            q_delta = restored_quant_u8.astype(np.int16) - item.quant_u8.astype(np.int16)
            latent_a = (item.quant_u8.astype(np.float32) - item.zero_point) * item.scale
            latent_b = (restored_quant_u8.astype(np.float32) - item.zero_point) * item.scale
            exact = bool(np.array_equal(restored_quant_u8, item.quant_u8))

            codec_result: dict[str, Any] = {
                'encoded_bytes': len(encoded_bytes),
                'ratio_vs_quant_bytes': float(len(encoded_bytes) / baseline_quant_bytes),
                'exact_quant_recovery': exact,
                'quant_diff_nonzero': int(np.count_nonzero(q_delta)),
                'quant_diff_max_abs': int(np.max(np.abs(q_delta))),
                'latent_mse': float(np.mean((latent_a - latent_b) ** 2)),
                'latent_max_abs': float(np.max(np.abs(latent_a - latent_b))),
            }

            if baseline_recon is not None:
                recon = decoder.reconstruct(
                    restored_quant_u8,
                    item.scale,
                    item.zero_point,
                    config_str=config_str,
                )
                codec_result['recon_psnr_vs_baseline'] = compute_psnr(baseline_recon, recon)
                codec_result['recon_ssim_vs_baseline'] = compute_ssim(baseline_recon, recon)

            file_result['codec_results'][codec.name] = codec_result
            per_codec_size[codec.name].append(codec_result['encoded_bytes'])
            per_codec_ratio[codec.name].append(codec_result['ratio_vs_quant_bytes'])
            per_codec_latent_mse[codec.name].append(codec_result['latent_mse'])
            per_codec_qdiff[codec.name].append(codec_result['quant_diff_nonzero'])

            if 'recon_psnr_vs_baseline' in codec_result:
                per_codec_psnr[codec.name].append(codec_result['recon_psnr_vs_baseline'])
            if 'recon_ssim_vs_baseline' in codec_result:
                per_codec_ssim[codec.name].append(codec_result['recon_ssim_vs_baseline'])

        results['files'].append(file_result)

    for codec in CODECS:
        summary = {
            'encoded_bytes': summarise_numeric(per_codec_size[codec.name]),
            'ratio_vs_quant_bytes': summarise_numeric(per_codec_ratio[codec.name]),
            'latent_mse': summarise_numeric(per_codec_latent_mse[codec.name]),
            'quant_diff_nonzero': summarise_numeric(per_codec_qdiff[codec.name]),
            'exact_quant_recovery_count': int(sum(
                1
                for file_item in results['files']
                if file_item['codec_results'][codec.name]['exact_quant_recovery']
            )),
        }
        if per_codec_psnr[codec.name]:
            summary['recon_psnr_vs_baseline'] = summarise_numeric(per_codec_psnr[codec.name])
        if per_codec_ssim[codec.name]:
            summary['recon_ssim_vs_baseline'] = summarise_numeric(per_codec_ssim[codec.name])
        results['summary'][codec.name] = summary

    return results


def print_summary(results: dict[str, Any]) -> None:
    print('\n═══ Latent Image Codec Summary ═══')
    recon_enabled = results['reconstruction_enabled']
    headers = [
        'codec',
        'size_mean(B)',
        'ratio_mean',
        'exact',
        'qdiff_mean',
    ]
    if recon_enabled:
        headers.extend(['recon_psnr', 'recon_ssim'])
    print(' | '.join(f'{h:>14}' for h in headers))
    print('-' * (18 * len(headers)))

    for codec_name, summary in results['summary'].items():
        row = [
            codec_name,
            f'{summary["encoded_bytes"]["mean"]:.1f}',
            f'{summary["ratio_vs_quant_bytes"]["mean"]:.4f}',
            f'{summary["exact_quant_recovery_count"]}/{results["num_files"]}',
            f'{summary["quant_diff_nonzero"]["mean"]:.1f}',
        ]
        if recon_enabled:
            psnr = summary.get('recon_psnr_vs_baseline', {}).get('mean', float('nan'))
            ssim = summary.get('recon_ssim_vs_baseline', {}).get('mean', float('nan'))
            row.extend([
                'inf' if math.isinf(psnr) else f'{psnr:.2f}',
                f'{ssim:.4f}',
            ])
        print(' | '.join(f'{cell:>14}' for cell in row))


def parse_args():
    parser = argparse.ArgumentParser(description='把 quant latent 平铺成图片并试验图片编解码。')
    parser.add_argument(
        '--input-glob',
        required=True,
        help="latent 文件 glob，例如 '/tmp/jscc-test-extract/jscc-test/encoder_outputs/*_latent.pt'",
    )
    parser.add_argument(
        '--jscc-root',
        default='',
        help='可选。若给出提取后的 jscc-test 根目录，且 torch 可用，则额外计算 recon 质量。',
    )
    parser.add_argument(
        '--default-config-str',
        default='',
        help='当 latent 文件本身没有 config_str 时使用，例如 6_6_6_6_6_6_6。',
    )
    parser.add_argument('--limit', type=int, default=12, help='最多处理多少个文件；<=0 表示全部。')
    parser.add_argument(
        '--output',
        default='/tmp/latent_image_codec_results.json',
        help='结果 JSON 输出路径。',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    results = run_experiment(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    print_summary(results)
    print(f'\n结果已写入: {output_path}')


if __name__ == '__main__':
    main()
