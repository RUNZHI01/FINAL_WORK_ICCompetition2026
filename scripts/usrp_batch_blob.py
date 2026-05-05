#!/usr/bin/env python3
"""usrp_batch_blob.py — 将多文件张量目录打包成单个 USRP 传输 blob

用途:
  1. pack:  将目录中的多个张量文件打包为一个二进制 blob，供 usrp_tensor_tx 发送
  2. unpack: 将 usrp_tensor_rx 收到的 blob 拆包回目录，并逐文件做 SHA256 校验
  3. inspect: 查看 blob 清单与传输规模估算

格式:
  [ magic(8B='UTBLOB01') ][ manifest_len(8B, little-endian) ][ manifest_json ][ payload bytes... ]

manifest JSON:
  {
    "version": 1,
    "file_count": N,
    "total_bytes": ...,
    "files": [
      {"path": "a/b.npy", "size": 1234, "sha256": "...", "offset": 0},
      ...
    ]
  }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
from pathlib import Path


MAGIC = b'UTBLOB01'
HEADER_STRUCT = struct.Struct('<8sQ')
MAX_PAYLOAD = 219


def sha256_file(path: Path) -> str:
    """计算单个文件的 SHA256。

    Args:
        path: 文件路径

    Returns:
        64 字符十六进制摘要
    """
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def collect_files(input_dir: Path, pattern: str) -> list[Path]:
    """收集输入目录下待打包文件。"""
    files = [
        p for p in input_dir.rglob(pattern)
        if p.is_file()
    ]
    files.sort(key=lambda p: p.relative_to(input_dir).as_posix())
    return files


def build_manifest(input_dir: Path, files: list[Path]) -> dict:
    """构建 blob manifest。"""
    entries: list[dict] = []
    offset = 0
    total_bytes = 0

    for path in files:
        size = path.stat().st_size
        rel = path.relative_to(input_dir).as_posix()
        digest = sha256_file(path)
        entries.append({
            'path': rel,
            'size': size,
            'sha256': digest,
            'offset': offset,
        })
        offset += size
        total_bytes += size

    return {
        'version': 1,
        'file_count': len(entries),
        'total_bytes': total_bytes,
        'files': entries,
    }


def write_blob(input_dir: Path, files: list[Path], output_path: Path) -> dict:
    """写出 blob 文件，并返回 manifest。"""
    manifest = build_manifest(input_dir, files)
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')

    with output_path.open('wb') as out:
        out.write(HEADER_STRUCT.pack(MAGIC, len(manifest_bytes)))
        out.write(manifest_bytes)
        for path in files:
            with path.open('rb') as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)

    return manifest


def read_blob(blob_path: Path) -> tuple[dict, int]:
    """读取 blob header + manifest。

    Returns:
        (manifest, payload_start_offset)
    """
    with blob_path.open('rb') as f:
        header = f.read(HEADER_STRUCT.size)
        if len(header) != HEADER_STRUCT.size:
            raise RuntimeError('blob 头部不完整')
        magic, manifest_len = HEADER_STRUCT.unpack(header)
        if magic != MAGIC:
            raise RuntimeError(f'blob magic 不匹配: {magic!r}')

        manifest_bytes = f.read(manifest_len)
        if len(manifest_bytes) != manifest_len:
            raise RuntimeError('manifest 长度不足')

    manifest = json.loads(manifest_bytes.decode('utf-8'))
    payload_start = HEADER_STRUCT.size + manifest_len
    return manifest, payload_start


def unpack_blob(blob_path: Path, output_dir: Path, verify_only: bool) -> None:
    """拆包并逐文件校验。"""
    manifest, payload_start = read_blob(blob_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    with blob_path.open('rb') as f:
        for entry in manifest['files']:
            rel = Path(entry['path'])
            target = output_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)

            f.seek(payload_start + entry['offset'])
            data = f.read(entry['size'])
            if len(data) != entry['size']:
                raise RuntimeError(f'读取 payload 失败: {entry["path"]}')

            digest = hashlib.sha256(data).hexdigest()
            if digest != entry['sha256']:
                raise RuntimeError(
                    f'SHA256 校验失败: {entry["path"]} '
                    f'期望 {entry["sha256"]}, 实际 {digest}'
                )

            if not verify_only:
                with target.open('wb') as out:
                    out.write(data)


def inspect_blob(blob_path: Path) -> None:
    """打印 blob 规模与清单摘要。"""
    manifest, payload_start = read_blob(blob_path)
    total_bytes = int(manifest['total_bytes'])
    file_count = int(manifest['file_count'])
    total_frames = (total_bytes + MAX_PAYLOAD - 1) // MAX_PAYLOAD
    last_seq = total_frames - 1 if total_frames > 0 else 0

    print(f'blob: {blob_path}')
    print(f'  文件数: {file_count}')
    print(f'  payload: {total_bytes} bytes ({total_bytes / 1024.0 / 1024.0:.2f} MiB)')
    print(f'  manifest 起始后 payload 偏移: {payload_start} bytes')
    print(f'  估算帧数(MAX_PAYLOAD={MAX_PAYLOAD}): {total_frames}')
    print(f'  末帧 seq: {last_seq}')
    print('  前 5 项:')
    for entry in manifest['files'][:5]:
        print(f'    - {entry["path"]} ({entry["size"]} bytes, sha256={entry["sha256"][:16]}...)')


def pack_mode(input_dir: Path, output_path: Path, pattern: str) -> None:
    """执行 pack。"""
    files = collect_files(input_dir, pattern)
    if not files:
        raise RuntimeError(f'未找到匹配文件: dir={input_dir} pattern={pattern}')

    manifest = write_blob(input_dir, files, output_path)
    total_bytes = int(manifest['total_bytes'])
    total_frames = (total_bytes + MAX_PAYLOAD - 1) // MAX_PAYLOAD
    last_seq = total_frames - 1 if total_frames > 0 else 0

    print(f'[PACK] 输入目录: {input_dir}')
    print(f'[PACK] 文件数: {manifest["file_count"]}')
    print(f'[PACK] payload: {total_bytes} bytes ({total_bytes / 1024.0 / 1024.0:.2f} MiB)')
    print(f'[PACK] 输出 blob: {output_path}')
    print(f'[PACK] 估算帧数: {total_frames}, 末帧 seq={last_seq}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='多文件张量目录 <-> 单文件 USRP blob 打包工具',
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pack', action='store_true', help='打包目录为 blob')
    mode.add_argument('--unpack', action='store_true', help='拆包 blob 到目录')
    mode.add_argument('--inspect', action='store_true', help='查看 blob 信息')

    parser.add_argument('--input-dir', help='待打包目录')
    parser.add_argument('--input', help='输入 blob 文件')
    parser.add_argument('-o', '--output', help='输出 blob 文件或输出目录')
    parser.add_argument('--pattern', default='*.npz', help='pack 模式文件匹配模式 (默认: *.npz)')
    parser.add_argument('--verify-only', action='store_true', help='unpack 模式仅校验，不落盘')
    args = parser.parse_args()

    if args.pack:
        if not args.input_dir or not args.output:
            raise RuntimeError('pack 模式需要 --input-dir 和 --output')
        pack_mode(Path(args.input_dir), Path(args.output), args.pattern)
        return

    if args.unpack:
        if not args.input or not args.output:
            raise RuntimeError('unpack 模式需要 --input 和 --output')
        unpack_blob(Path(args.input), Path(args.output), args.verify_only)
        print(f'[UNPACK] 完成: {args.input} -> {args.output}')
        return

    if args.inspect:
        if not args.input:
            raise RuntimeError('inspect 模式需要 --input')
        inspect_blob(Path(args.input))
        return


if __name__ == '__main__':
    main()
