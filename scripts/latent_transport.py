#!/usr/bin/env python3
"""latent_transport.py

统一管理 latent 数据面的传输打包格式：
1. 兼容现有 `float32-raw` 路径；
2. 新增 `webp-lossless` source-codec；
3. 提供 CLI 方便直接生成/解包 wire blob。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


SUPPORTED_PAYLOAD_CODECS = ('float32-raw', 'webp-lossless')


@dataclass
class DecodedPayload:
    """解码后的 latent 结果。"""

    meta: dict[str, Any]
    payload_bytes: bytes
    latent: np.ndarray
    npz_items: dict[str, Any]
    storage_format: str


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_pillow_image():
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError('缺少 Pillow，无法使用 webp-lossless latent 编解码') from exc
    return Image


def _ensure_batched_float32(array: np.ndarray) -> np.ndarray:
    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim == 3:
        arr = np.expand_dims(arr, axis=0)
    return arr


def _torch_load(path: str) -> Any:
    try:
        import torch  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f'读取 .pt latent 需要 torch: {path}') from exc

    try:
        return torch.load(path, map_location='cpu', weights_only=False)
    except TypeError:
        return torch.load(path, map_location='cpu')


def _torch_load(path: str) -> Any:
    try:
        import torch  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f'读取 .pt latent 需要 torch: {path}') from exc

    try:
        return torch.load(path, map_location='cpu', weights_only=False)
    except TypeError:
        return torch.load(path, map_location='cpu')


def _load_float32_latent(path: str) -> tuple[np.ndarray, dict[str, Any]]:
    """加载旧路径可用的 float32 latent。"""
    if path.endswith('.pt'):
        payload = _torch_load(path)
        if not isinstance(payload, dict) or 'latent' not in payload:
            raise ValueError(f'{path} 不包含 raw float latent 字段 "latent"')
        arr = payload['latent']
        if hasattr(arr, 'detach'):
            arr = arr.detach().cpu().numpy()
        arr = np.asarray(arr, dtype=np.float32)
        return arr.astype(np.float32, copy=False), {'shape': list(arr.shape), 'dtype': 'float32'}

    if path.endswith('.bin'):
        raw = Path(path).read_bytes()
        n = len(raw) // 4
        if n == 32 * 32 * 32:
            shape = (1, 32, 32, 32)
        elif n == 3 * 64 * 64:
            shape = (1, 3, 64, 64)
        else:
            shape = (n,)
        arr = np.frombuffer(raw, dtype=np.float32).reshape(shape).copy()
        return arr, {'shape': list(shape), 'dtype': 'float32'}

    if path.endswith('.npz'):
        with np.load(path) as data:
            if 'quant' in data and 'scale' in data and 'zero_point' in data:
                quant = np.asarray(data['quant'], dtype=np.float32)
                scale = np.asarray(data['scale'], dtype=np.float32)
                zero_point = np.asarray(data['zero_point'], dtype=np.float32)
                arr = (quant - zero_point) * scale
            elif 'latent' in data:
                arr = np.asarray(data['latent'], dtype=np.float32)
            else:
                key = list(data.keys())[0]
                arr = np.asarray(data[key], dtype=np.float32)
    elif path.endswith('.npy'):
        arr = np.load(path).astype(np.float32)
    else:
        raise ValueError(f'不支持的文件格式: {path}（需要 .pt / .npz / .npy / .bin）')

    return arr.astype(np.float32, copy=False), {'shape': list(arr.shape), 'dtype': 'float32'}


def _normalize_quant_array(quant: np.ndarray) -> tuple[np.ndarray, str, str]:
    """把 quant 统一映射到 uint8 图像域。"""
    array = np.asarray(quant)
    original_dtype = str(array.dtype)

    if array.dtype == np.uint8:
        return array.astype(np.uint8, copy=False), original_dtype, 'identity'

    if array.dtype == np.int8:
        mapped = (array.astype(np.int16) + 128).astype(np.uint8)
        return mapped, original_dtype, 'int8_offset_128'

    raise ValueError(f'暂不支持的 quant dtype: {array.dtype}')


def _restore_quant_array(mapped: np.ndarray, *, quant_dtype: str, quant_encoding: str) -> np.ndarray:
    """把图像域 quant 恢复到原始量化域。"""
    array = np.asarray(mapped, dtype=np.uint8)
    if quant_encoding == 'identity':
        if quant_dtype == 'uint8':
            return array.astype(np.uint8, copy=False)
        raise ValueError(f'identity 编码不支持 quant_dtype={quant_dtype}')

    if quant_encoding == 'int8_offset_128':
        if quant_dtype != 'int8':
            raise ValueError(f'int8_offset_128 期望 int8，实际 {quant_dtype}')
        return (array.astype(np.int16) - 128).astype(np.int8)

    raise ValueError(f'未知 quant_encoding: {quant_encoding}')


def _load_quantized_latent(path: str) -> tuple[np.ndarray, float, float, dict[str, Any]]:
    """加载 quant latent；供 source-codec 使用。"""
    if path.endswith('.pt'):
        payload = _torch_load(path)
        quant = np.asarray(payload['quant'].cpu().numpy())
        scale = float(np.asarray(payload['scale']).reshape(()))
        zero_point = float(np.asarray(payload['zero_point']).reshape(()))
        original_filename = str(payload.get('original_filename') or '')
    elif path.endswith('.npz'):
        with np.load(path) as data:
            if not {'quant', 'scale', 'zero_point'}.issubset(set(data.files)):
                raise ValueError(
                    f'{path} 不包含 quant/scale/zero_point，'
                    'webp-lossless 仅支持已有量化 latent'
                )
            quant = np.asarray(data['quant'])
            scale = float(np.asarray(data['scale']).reshape(()))
            zero_point = float(np.asarray(data['zero_point']).reshape(()))
            original_filename = str(np.asarray(data['original_filename']).reshape(())) if 'original_filename' in data else ''
    else:
        raise ValueError(
            f'{path} 不是可量化 latent 文件；webp-lossless 仅支持 .npz/.pt'
        )

    if quant.ndim == 4 and quant.shape[0] == 1:
        quant = quant[0]
    if quant.ndim != 3:
        raise ValueError(f'期望 quant latent 为 [C,H,W] 或 [1,C,H,W]，实际 {quant.shape}')

    mapped, original_dtype, quant_encoding = _normalize_quant_array(quant)
    info = {
        'quant_shape': list(mapped.shape),
        'quant_dtype': original_dtype,
        'quant_encoding': quant_encoding,
        'original_filename': original_filename,
    }
    return mapped, scale, zero_point, info


def _choose_grid(channels: int) -> tuple[int, int]:
    cols = 1
    while cols * cols < channels:
        cols += 1
    rows = (channels + cols - 1) // cols
    return rows, cols


def _tile_quant_to_atlas(quant_u8: np.ndarray) -> tuple[np.ndarray, dict[str, int]]:
    channels, height, width = quant_u8.shape
    rows, cols = _choose_grid(channels)
    atlas = np.zeros((rows * height, cols * width), dtype=np.uint8)
    for idx in range(channels):
        row = idx // cols
        col = idx % cols
        y0 = row * height
        x0 = col * width
        atlas[y0:y0 + height, x0:x0 + width] = quant_u8[idx]
    return atlas, {
        'channels': channels,
        'height': height,
        'width': width,
        'rows': rows,
        'cols': cols,
    }


def _untile_atlas_to_quant(atlas: np.ndarray, layout: dict[str, Any]) -> np.ndarray:
    channels = int(layout['channels'])
    height = int(layout['height'])
    width = int(layout['width'])
    rows = int(layout['rows'])
    cols = int(layout['cols'])
    expected_shape = (rows * height, cols * width)
    if tuple(atlas.shape) != expected_shape:
        raise ValueError(f'atlas 尺寸不匹配: got={atlas.shape}, expected={expected_shape}')

    quant_u8 = np.zeros((channels, height, width), dtype=np.uint8)
    for idx in range(channels):
        row = idx // cols
        col = idx % cols
        y0 = row * height
        x0 = col * width
        quant_u8[idx] = atlas[y0:y0 + height, x0:x0 + width]
    return quant_u8


def _encode_webp_lossless(quant_u8: np.ndarray) -> tuple[bytes, dict[str, Any]]:
    Image = _load_pillow_image()
    atlas, layout = _tile_quant_to_atlas(quant_u8)
    image = Image.fromarray(atlas, mode='L')
    buffer = io.BytesIO()
    image.save(buffer, format='WEBP', lossless=True, quality=100, method=6)
    return buffer.getvalue(), layout


def _decode_webp_lossless(payload_bytes: bytes, layout: dict[str, Any]) -> np.ndarray:
    Image = _load_pillow_image()
    with Image.open(io.BytesIO(payload_bytes)) as image:
        atlas = np.asarray(image.convert('L'), dtype=np.uint8)
    return _untile_atlas_to_quant(atlas, layout)


def build_transport_payload(
    input_path: str,
    *,
    job_id: str | None = None,
    payload_codec: str = 'float32-raw',
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    """从输入文件构建传输 payload 与 meta。"""
    if payload_codec not in SUPPORTED_PAYLOAD_CODECS:
        raise ValueError(f'不支持的 payload_codec: {payload_codec}')

    resolved_job_id = job_id or os.path.splitext(os.path.basename(input_path))[0]

    if payload_codec == 'float32-raw':
        latent, info = _load_float32_latent(input_path)
        latent = _ensure_batched_float32(latent)
        payload_bytes = latent.astype(np.float32, copy=False).tobytes()
        payload_sha = _sha256_bytes(payload_bytes)
        meta = {
            'job_id': resolved_job_id,
            'shape': list(latent.shape),
            'dtype': 'float32',
            'payload_codec': payload_codec,
            'sha256': payload_sha,
            'size': len(payload_bytes),
            'latent_sha256': payload_sha,
            'latent_size': len(payload_bytes),
        }
        stats = {
            'payload_codec': payload_codec,
            'shape': list(latent.shape),
            'payload_bytes': len(payload_bytes),
            'latent_bytes': len(payload_bytes),
            'payload_sha256': payload_sha,
            'latent_sha256': payload_sha,
        }
        return payload_bytes, meta, stats

    quant_u8, scale, zero_point, info = _load_quantized_latent(input_path)
    payload_bytes, layout = _encode_webp_lossless(quant_u8)
    quant_restored = _restore_quant_array(
        quant_u8,
        quant_dtype=info['quant_dtype'],
        quant_encoding=info['quant_encoding'],
    )
    latent = (quant_restored.astype(np.float32) - float(zero_point)) * float(scale)
    latent = _ensure_batched_float32(latent)
    latent_bytes = latent.astype(np.float32, copy=False).tobytes()

    payload_sha = _sha256_bytes(payload_bytes)
    latent_sha = _sha256_bytes(latent_bytes)
    meta = {
        'job_id': resolved_job_id,
        'shape': list(latent.shape),
        'dtype': 'float32',
        'payload_codec': payload_codec,
        'payload_format': 'quant-image-codec',
        'sha256': payload_sha,
        'size': len(payload_bytes),
        'latent_sha256': latent_sha,
        'latent_size': len(latent_bytes),
        'scale': float(scale),
        'zero_point': float(zero_point),
        'quant_shape': info['quant_shape'],
        'quant_dtype': info['quant_dtype'],
        'quant_encoding': info['quant_encoding'],
        'original_filename': info.get('original_filename', ''),
        'layout': layout,
    }
    stats = {
        'payload_codec': payload_codec,
        'shape': list(latent.shape),
        'payload_bytes': len(payload_bytes),
        'latent_bytes': len(latent_bytes),
        'payload_sha256': payload_sha,
        'latent_sha256': latent_sha,
        'original_filename': info.get('original_filename', ''),
    }
    return payload_bytes, meta, stats


def pack_transport_frame(meta: dict[str, Any], payload_bytes: bytes) -> bytes:
    meta_json = json.dumps(meta, separators=(',', ':')).encode('utf-8')
    return len(meta_json).to_bytes(4, 'big') + meta_json + payload_bytes


def unpack_transport_frame(blob_bytes: bytes) -> tuple[dict[str, Any], bytes]:
    if len(blob_bytes) < 4:
        raise ValueError(f'wire blob 过小: {len(blob_bytes)}B')
    meta_len = int.from_bytes(blob_bytes[:4], 'big')
    if 4 + meta_len > len(blob_bytes):
        raise ValueError(f'meta_len={meta_len} 超出 blob 大小 {len(blob_bytes)}')
    meta = json.loads(blob_bytes[4:4 + meta_len].decode('utf-8'))
    payload_bytes = blob_bytes[4 + meta_len:]
    return meta, payload_bytes


def decode_transport_payload(
    meta: dict[str, Any],
    payload_bytes: bytes,
    *,
    verify_latent_sha: bool = True,
) -> DecodedPayload:
    """把传输 payload 还原为 TVM/重建可用的 latent。

    Args:
        meta: 传输元数据。
        payload_bytes: 真实 payload 字节。
        verify_latent_sha: 是否校验还原后 latent 的 sha256。
            对 lossless 正常链路应保持开启；若仅想在 payload 已损坏时尽量
            恢复可解析结果，可临时关闭该校验。
    """
    payload_codec = str(meta.get('payload_codec') or 'float32-raw')

    if payload_codec == 'float32-raw':
        shape = tuple(meta.get('shape', [1, 32, 32, 32]))
        dtype = np.dtype(str(meta.get('dtype', 'float32')))
        latent = np.frombuffer(payload_bytes, dtype=dtype).reshape(shape).astype(np.float32, copy=False)
        latent_sha = _sha256_bytes(latent.astype(np.float32, copy=False).tobytes())
        expected_sha = str(meta.get('latent_sha256') or meta.get('sha256') or '')
        if verify_latent_sha and expected_sha and latent_sha != expected_sha:
            raise RuntimeError(
                f'latent_sha256 不匹配: expect={expected_sha[:16]} got={latent_sha[:16]}'
            )
        return DecodedPayload(
            meta=meta,
            payload_bytes=payload_bytes,
            latent=latent,
            npz_items={'latent': latent},
            storage_format='latent',
        )

    if payload_codec == 'webp-lossless':
        layout = dict(meta.get('layout') or {})
        quant_u8 = _decode_webp_lossless(payload_bytes, layout)
        quant = _restore_quant_array(
            quant_u8,
            quant_dtype=str(meta.get('quant_dtype') or 'uint8'),
            quant_encoding=str(meta.get('quant_encoding') or 'identity'),
        )
        scale = float(meta['scale'])
        zero_point = float(meta['zero_point'])
        latent = (quant.astype(np.float32) - zero_point) * scale
        latent = _ensure_batched_float32(latent)
        latent_sha = _sha256_bytes(latent.astype(np.float32, copy=False).tobytes())
        expected_sha = str(meta.get('latent_sha256') or '')
        if verify_latent_sha and expected_sha and latent_sha != expected_sha:
            raise RuntimeError(
                f'latent_sha256 不匹配: expect={expected_sha[:16]} got={latent_sha[:16]}'
            )
        quant_batched = np.expand_dims(quant, axis=0)
        npz_items = {
            'quant': quant_batched,
            'scale': np.asarray(scale, dtype=np.float32),
            'zero_point': np.asarray(zero_point, dtype=np.float32),
        }
        return DecodedPayload(
            meta=meta,
            payload_bytes=payload_bytes,
            latent=latent,
            npz_items=npz_items,
            storage_format='quant',
        )

    raise ValueError(f'未知 payload_codec: {payload_codec}')


def save_decoded_npz(decoded: DecodedPayload, output_path: str | Path) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez(target, **decoded.npz_items)


def build_transport_blob(
    input_path: str,
    *,
    job_id: str | None = None,
    payload_codec: str = 'float32-raw',
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    payload_bytes, meta, stats = build_transport_payload(
        input_path,
        job_id=job_id,
        payload_codec=payload_codec,
    )
    return pack_transport_frame(meta, payload_bytes), meta, stats


def _print_stats(meta: dict[str, Any], stats: dict[str, Any]) -> None:
    print(f'job_id={meta.get("job_id")}')
    print(f'payload_codec={stats.get("payload_codec")}')
    print(f'shape={stats.get("shape")}')
    print(f'payload_bytes={stats.get("payload_bytes")} latent_bytes={stats.get("latent_bytes")}')
    print(f'payload_sha256={str(stats.get("payload_sha256"))[:16]}...')
    print(f'latent_sha256={str(stats.get("latent_sha256"))[:16]}...')


def main() -> None:
    parser = argparse.ArgumentParser(description='latent transport 打包/解包工具')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pack', action='store_true', help='从 latent 输入生成 wire blob')
    mode.add_argument('--unpack', action='store_true', help='把 wire blob 解包为 .npz')
    mode.add_argument('--inspect', action='store_true', help='查看 wire blob 元数据')
    parser.add_argument('--input', required=True, help='输入文件：pack 时为 latent；unpack/inspect 时为 wire blob')
    parser.add_argument('-o', '--output', help='输出文件：pack 时为 .bin；unpack 时为 .npz')
    parser.add_argument(
        '--payload-codec',
        choices=SUPPORTED_PAYLOAD_CODECS,
        default='float32-raw',
        help='传输 payload 编码方式',
    )
    parser.add_argument('--job-id', default=None, help='可选任务 ID')
    args = parser.parse_args()

    if args.pack:
        if not args.output:
            raise RuntimeError('--pack 需要 --output')
        blob, meta, stats = build_transport_blob(
            args.input,
            job_id=args.job_id,
            payload_codec=args.payload_codec,
        )
        Path(args.output).write_bytes(blob)
        _print_stats(meta, stats)
        print(f'blob={args.output} size={len(blob)}')
        return

    blob_bytes = Path(args.input).read_bytes()
    meta, payload_bytes = unpack_transport_frame(blob_bytes)

    if args.inspect:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        print(f'payload_bytes={len(payload_bytes)}')
        return

    if args.unpack:
        if not args.output:
            raise RuntimeError('--unpack 需要 --output')
        decoded = decode_transport_payload(meta, payload_bytes)
        save_decoded_npz(decoded, args.output)
        print(f'payload_codec={meta.get("payload_codec", "float32-raw")}')
        print(f'output={args.output}')
        return


if __name__ == '__main__':
    main()
