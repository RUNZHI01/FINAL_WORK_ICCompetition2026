#!/usr/bin/env python3
"""usrp_send.py — 上位机 latent 发送端（USRP 明文数据面）

将 latent / quant latent 打包为统一 wire frame：
  [4B meta_len][JSON meta][payload bytes]
再通过 USRP 无线链路发送。

当前支持两种 payload codec：
1. `float32-raw`：直接发送 batched float32 latent；
2. `webp-lossless`：对已有 quant latent 做无损 source-codec 压缩。

用法:
  # SIM 模式（纯软件回环，无需硬件）
  python scripts/usrp_send.py --input test_latent.npz --mode sim

  # SIM + 自定义 SNR
  python scripts/usrp_send.py --input test_latent.npz --mode sim --snr 15

  # 硬件回环（单设备 + SMA 跳线）
  python scripts/usrp_send.py --input test_latent.npz --mode loopback --args "serial=31E74E3"

  # OTA 双设备（仅发送端）
  python scripts/usrp_send.py --input test_latent.npz --mode ota --args "serial=31DDAB3"
"""

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
import time

from latent_transport import SUPPORTED_PAYLOAD_CODECS, build_transport_blob

# ── USRP 二进制构建路径 ──

_USRP_BUILD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'usrp_tensor', 'build',
)

# ── 默认参数 ──
DEFAULT_RATE = 3e6  # 3 Msps: 板端 ARM 稳定工作上限 (Moose 搜索 ~24% CPU)


def _bin(name: str) -> str:
    """定位 usrp_tensor 构建产物"""
    path = os.path.join(_USRP_BUILD, name)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"找不到 {path}，请先编译: cd usrp_tensor && mkdir -p build && cd build && cmake .. && make")
    return path


def pack_latent_blob(
    npz_path: str,
    job_id: str | None = None,
    *,
    payload_codec: str = 'float32-raw',
) -> tuple[str, dict]:
    """将 latent .npz 打包为 USRP 传输的二进制 blob

    格式: [meta_len: 4B big-endian][meta JSON][payload bytes]
    与 Tailscale TCP 通道的格式一致。

    Returns:
        (bin_path, meta_dict) — bin_path 为临时文件路径
    """
    blob, meta, stats = build_transport_blob(
        npz_path,
        job_id=job_id,
        payload_codec=payload_codec,
    )

    resolved_job_id = str(meta.get('job_id') or job_id or 'job')
    fd, bin_path = tempfile.mkstemp(suffix='.bin', prefix=f'usrp_{resolved_job_id}_')
    with os.fdopen(fd, 'wb') as f:
        f.write(blob)

    print(f'[pack] job_id={meta["job_id"]}, shape={stats["shape"]}, '
          f'codec={stats["payload_codec"]}, payload={stats["payload_bytes"]}B, '
          f'latent={stats["latent_bytes"]}B, '
          f'sha256={str(stats["payload_sha256"])[:16]}..., blob={len(blob)}B')
    return bin_path, meta


# ── 发送模式 ──

def run_sim(blob_path: str, snr: float = 24.0,
            repeat: int = 1, rate: float = DEFAULT_RATE) -> bool:
    """SIM 模式: 调用 usrp_tensor_loopback --sim"""
    loopback = _bin('usrp_tensor_loopback')
    cmd = [loopback, '--sim', '--file', blob_path,
           '--snr', str(snr), '--repeat', str(repeat),
           '--rate', str(rate)]
    print(f'[SIM] {" ".join(cmd)}')

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    stdout_tail = result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout
    print(stdout_tail)

    if result.returncode != 0:
        print(f'[SIM] 失败 (rc={result.returncode})')
        if result.stderr:
            print(result.stderr[-2000:])
        return False
    return True


def run_loopback(blob_path: str, args: str = '',
                 tx_gain: float = 60.0, rx_gain: float = 60.0,
                 repeat: int = 3, rate: float = DEFAULT_RATE) -> bool:
    """硬件回环: 调用 usrp_tensor_loopback"""
    loopback = _bin('usrp_tensor_loopback')
    cmd = [loopback, '--file', blob_path,
           '--tx-gain', str(tx_gain), '--rx-gain', str(rx_gain),
           '--repeat', str(repeat), '--rate', str(rate)]
    if args:
        cmd += ['--args', args]

    print(f'[LOOPBACK] {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stdout_tail = result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout
    print(stdout_tail)

    if result.returncode != 0:
        print(f'[LOOPBACK] 失败 (rc={result.returncode})')
        if result.stderr:
            print(result.stderr[-2000:])
        return False
    return True


def run_ota_tx(blob_path: str, args: str = '',
               tx_gain: float = 60.0, repeat: int = 5,
               rate: float = DEFAULT_RATE) -> bool:
    """OTA 发送: 调用 usrp_tensor_tx"""
    tx = _bin('usrp_tensor_tx')
    cmd = [tx, '--file', blob_path,
           '--gain', str(tx_gain), '--repeat', str(repeat),
           '--rate', str(rate)]
    if args:
        cmd += ['--args', args]

    print(f'[OTA TX] {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    stdout_tail = result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout
    print(stdout_tail)

    if result.returncode != 0:
        print(f'[OTA TX] 失败 (rc={result.returncode})')
        if result.stderr:
            print(result.stderr[-2000:])
        return False
    return True


# ── SIM 模式验证 ──

def verify_sim_roundtrip(blob_path: str, meta: dict) -> bool:
    """验证 SIM 回环后收到的文件 SHA256 是否匹配"""
    blob_sha = meta['sha256']
    blob_dir = os.path.dirname(os.path.abspath(blob_path))

    candidates: list[str] = []
    for name in os.listdir(blob_dir):
        if name.startswith('received_') and name.endswith('.bin'):
            candidates.append(os.path.join(blob_dir, name))

    if not candidates:
        print('[verify] 未找到 received_*.bin 文件（SIM 模式可能仅输出日志）')
        return True

    latest = max(candidates, key=os.path.getmtime)
    print(f'[verify] 检查接收文件: {latest}')

    with open(latest, 'rb') as f:
        received = f.read()
    with open(blob_path, 'rb') as f:
        original = f.read()

    recv_sha = hashlib.sha256(received).hexdigest()
    orig_sha = hashlib.sha256(original).hexdigest()

    if recv_sha == orig_sha:
        print(f'[verify] SHA256 匹配: {recv_sha[:16]}...')
        return True

    print(f'[verify] SHA256 不匹配')
    print(f'  原始: {orig_sha[:16]}... ({len(original)}B)')
    print(f'  接收: {recv_sha[:16]}... ({len(received)}B)')

    if len(received) == len(original):
        diffs = sum(1 for a, b in zip(original, received) if a != b)
        print(f'  字节差异: {diffs}/{len(original)}')
    return False


# ── main ──

def main() -> None:
    parser = argparse.ArgumentParser(
        description='USRP 明文 latent 发送端')
    parser.add_argument('--input', required=True,
                        help='latent 文件路径 (.npz / .npy / .bin / .pt)')
    parser.add_argument('--mode', required=True,
                        choices=['sim', 'loopback', 'ota'],
                        help='传输模式: sim=软件回环, loopback=硬件回环, ota=空中发送')
    parser.add_argument('--args', default='',
                        help='UHD 设备参数 (例: "serial=31DDAB3")')
    parser.add_argument('--rate', type=float, default=DEFAULT_RATE,
                        help=f'采样率 Hz (默认 {DEFAULT_RATE/1e6:.0f}e6)')
    parser.add_argument('--tx-gain', type=float, default=60.0,
                        help='TX 增益 dB (默认 60)')
    parser.add_argument('--rx-gain', type=float, default=60.0,
                        help='RX 增益 dB (默认 60, loopback 模式)')
    parser.add_argument('--snr', type=float, default=24.0,
                        help='SIM 模式 SNR dB (默认 24)')
    parser.add_argument('--repeat', type=int, default=3,
                        help='发送重复轮数 (默认 3)')
    parser.add_argument('--job-id', default=None,
                        help='任务 ID (默认取文件名)')
    parser.add_argument(
        '--payload-codec',
        choices=SUPPORTED_PAYLOAD_CODECS,
        default='float32-raw',
        help='传输 payload 编码方式 (默认 float32-raw)',
    )
    parser.add_argument('--pack-only', action='store_true',
                        help='仅生成 wire blob，不执行发送')
    parser.add_argument('--output-blob', default=None,
                        help='pack-only 时输出 blob 路径')
    args = parser.parse_args()

    print('=' * 60)
    print('USRP 明文 latent 发送端')
    print('=' * 60)

    # ── 1. 打包 latent blob ──
    blob, meta, stats = build_transport_blob(
        args.input,
        job_id=args.job_id,
        payload_codec=args.payload_codec,
    )
    job_id = str(meta.get('job_id') or os.path.splitext(os.path.basename(args.input))[0])
    if args.pack_only:
        if not args.output_blob:
            parser.error('--pack-only 需要 --output-blob')
        with open(args.output_blob, 'wb') as handle:
            handle.write(blob)
        print(f'[pack-only] job_id={meta["job_id"]}, codec={stats["payload_codec"]}, '
              f'payload={stats["payload_bytes"]}B, latent={stats["latent_bytes"]}B, '
              f'blob={len(blob)}B -> {args.output_blob}')
        return

    fd, blob_path = tempfile.mkstemp(suffix='.bin', prefix=f'usrp_{job_id}_')
    with os.fdopen(fd, 'wb') as handle:
        handle.write(blob)

    try:
        # ── 2. 发送 ──
        t0 = time.perf_counter()

        if args.mode == 'sim':
            ok = run_sim(blob_path, snr=args.snr, repeat=args.repeat,
                         rate=args.rate)
        elif args.mode == 'loopback':
            ok = run_loopback(blob_path, args=args.args,
                              tx_gain=args.tx_gain, rx_gain=args.rx_gain,
                              repeat=args.repeat, rate=args.rate)
        elif args.mode == 'ota':
            ok = run_ota_tx(blob_path, args=args.args,
                            tx_gain=args.tx_gain, repeat=args.repeat,
                            rate=args.rate)
        else:
            ok = False

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # ── 3. 验证（仅 SIM/loopback 模式）──
        if ok and args.mode in ('sim', 'loopback'):
            verify_sim_roundtrip(blob_path, meta)

        print()
        print('=' * 60)
        blob_size = len(open(blob_path, 'rb').read()) if os.path.exists(blob_path) else 0
        print(f'{"OK" if ok else "FAIL"} {args.mode} 模式, '
              f'耗时 {elapsed_ms:.0f}ms, codec {stats["payload_codec"]}, blob {blob_size}B')
        print('=' * 60)

        sys.exit(0 if ok else 1)

    finally:
        if os.path.exists(blob_path):
            os.unlink(blob_path)


if __name__ == '__main__':
    main()
