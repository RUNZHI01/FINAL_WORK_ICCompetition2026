#!/usr/bin/env python3
"""latent_serialize.py — latent 张量二进制序列化 / 反序列化工具

将语义编码器输出的 .npz latent 张量文件序列化为原始二进制文件,
供 USRP B205 无线传输使用。也可反向操作: 二进制 → npz。

用法:
  # 序列化 (默认)
  python scripts/latent_serialize.py input.npz -o latent.bin

  # 反序列化
  python scripts/latent_serialize.py latent.bin -o output.npz --deserialize

  # 指定 key (默认 'latent')
  python scripts/latent_serialize.py input.npz -o latent.bin --key arr_0

  # 指定 shape (反序列化时)
  python scripts/latent_serialize.py latent.bin -o output.npz --deserialize --shape 1,32,32,32

  # 附加 shape 头 (接收端可自动解析 shape)
  python scripts/latent_serialize.py input.npz -o latent.bin --header
"""

import argparse
import struct
import sys

import numpy as np


# ── 二进制文件格式 ──
# 无 header: 纯 float32 little-endian 原始字节
# 有 header: [ndim: uint32 LE] [dim0: uint32 LE] ... [dimN: uint32 LE] [float32 data...]
# header 总长度 = 4 + ndim * 4 bytes


def serialize(npz_path: str, output_path: str, key: str = 'latent',
              add_header: bool = False) -> None:
    """将 .npz 文件中的 latent 张量序列化为二进制文件。

    Args:
        npz_path: 输入 .npz 文件路径
        output_path: 输出二进制文件路径
        key: npz 中的数组 key
        add_header: 是否在二进制文件头部附加 shape 信息
    """
    data = np.load(npz_path)
    if key not in data:
        raise KeyError(f"npz 中不包含 key '{key}', 可用 key: {list(data.keys())}")

    tensor = data[key]
    print(f"[serialize] shape={tensor.shape}, dtype={tensor.dtype}, "
          f"大小={tensor.nbytes} bytes, key='{key}'")

    with open(output_path, 'wb') as f:
        if add_header:
            ndim = len(tensor.shape)
            header = struct.pack('<I', ndim)
            for dim in tensor.shape:
                header += struct.pack('<I', dim)
            f.write(header)
            print(f"[serialize] shape 头: ndim={ndim}, "
                  f"shape={tuple(tensor.shape)}, header 大小={len(header)} bytes")
        f.write(tensor.tobytes())

    total_size = len(open(output_path, 'rb').read())
    print(f"[serialize] 写入 {output_path}: {total_size} bytes")


def deserialize(bin_path: str, output_path: str,
                shape: tuple[int, ...] | None = None,
                has_header: bool = False) -> None:
    """将二进制文件反序列化为 .npz 文件。

    Args:
        bin_path: 输入二进制文件路径
        output_path: 输出 .npz 文件路径
        shape: 张量 shape（当 has_header=False 时使用）
        has_header: 二进制文件是否包含 shape 头
    """
    with open(bin_path, 'rb') as f:
        raw = f.read()

    if has_header:
        ndim = struct.unpack('<I', raw[:4])[0]
        header_size = 4 + ndim * 4
        parsed_shape = struct.unpack(f'<{ndim}I', raw[4:header_size])
        dtype_size = 4  # float32
        data_size = len(raw) - header_size
        inferred_shape = tuple(parsed_shape)
        if shape is not None and shape != inferred_shape:
            print(f"[warn] --shape {shape} 与 header 中的 shape {inferred_shape} "
                  "不一致, 使用 header 值")
        shape = inferred_shape
        data_bytes = raw[header_size:]
        print(f"[deserialize] shape 头: ndim={ndim}, shape={shape}")
    else:
        if shape is None:
            shape = (1, 32, 32, 32)
            print(f"[deserialize] 未指定 shape, 使用默认值: {shape}")
        data_bytes = raw

    expected_size = 1
    for dim in shape:
        expected_size *= dim
    expected_size *= 4  # float32

    if len(data_bytes) != expected_size:
        raise ValueError(
            f"文件大小 {len(raw)} 字节与 shape {shape} 不匹配 "
            f"(期望 {expected_size} 字节)")

    tensor = np.frombuffer(data_bytes, dtype=np.float32).reshape(shape)
    print(f"[deserialize] shape={tensor.shape}, dtype={tensor.dtype}, "
          f"大小={tensor.nbytes} bytes")

    np.savez(output_path, latent=tensor)
    print(f"[deserialize] 写入 {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='latent 张量二进制序列化 / 反序列化工具')
    parser.add_argument('input', help='输入文件路径 (.npz 或 .bin)')
    parser.add_argument('-o', '--output', required=True,
                        help='输出文件路径')
    parser.add_argument('-d', '--deserialize', action='store_true',
                        help='反序列化模式 (二进制 → npz)')
    parser.add_argument('--key', default='latent',
                        help='npz 中的数组 key (默认: latent)')
    parser.add_argument('--shape', default=None,
                        help='反序列化时的 shape, 逗号分隔 (默认: 1,32,32,32)')
    parser.add_argument('--header', action='store_true',
                        help='在二进制文件中附加 shape 头')
    args = parser.parse_args()

    if args.deserialize:
        shape = tuple(int(x) for x in args.shape.split(',')) if args.shape else None
        deserialize(args.input, args.output, shape=shape, has_header=args.header)
    else:
        serialize(args.input, args.output, key=args.key, add_header=args.header)


if __name__ == '__main__':
    main()
