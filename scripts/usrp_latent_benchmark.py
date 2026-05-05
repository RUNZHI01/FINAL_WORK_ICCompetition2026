#!/usr/bin/env python3
"""usrp_latent_benchmark.py — 多张 latent OTA 基准测试

目标：
  1. 使用同一份已验证 `33KB` latent `.npz` 重复构造 `N` 张图片的数据面 payload
  2. 对比当前 `chunked-daemon` fallback 与“整图一次 OTA 事务”的新入口
  3. 统计总耗时、每张耗时、有效吞吐和重试情况

说明：
  - 该脚本只测 USRP 数据面，不做 TVM reconstruction
  - 当前口径是“同一张 latent 重复 N 次”
  - 输出 JSON 摘要到 `artifacts/usrp_latent_benchmark/<timestamp>/summary.json`
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from usrp_image_demo import sha256_file
from usrp_latent_demo import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_INPUT_LATENT,
    add_ota_profile_arguments,
    build_wire_payload,
    build_effective_ota_profile,
    chunk_bytes,
    frozen_chunked_ota_kwargs,
    frozen_ota_kwargs,
    recover_payload_from_wire,
    transmit_chunk,
)
from e2e_usrp import run_ota_chunked


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / 'artifacts' / 'usrp_latent_benchmark'
DEFAULT_COUNTS = '10,50,100,200,300'


def parse_counts(raw: str) -> list[int]:
    values = []
    for item in str(raw).split(','):
        text = item.strip()
        if not text:
            continue
        value = int(text)
        if value <= 0:
            raise ValueError('count 必须为正整数')
        values.append(value)
    if not values:
        raise ValueError('至少需要一个 count')
    return values


def format_seconds(total_sec: float) -> str:
    seconds = int(round(total_sec))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f'{hours}h{minutes:02d}m{secs:02d}s'
    return f'{minutes}m{secs:02d}s'


def run_single_count(
    *,
    count: int,
    source_bytes: bytes,
    source_sha256: str,
    run_dir: Path,
    args: argparse.Namespace,
) -> dict[str, object]:
    batch_dir = run_dir / f'count_{count:03d}'
    chunks_dir = batch_dir / 'chunks'
    batch_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    batch_payload = source_bytes * count
    batch_path = batch_dir / f'latent_x{count}.bin'
    batch_path.write_bytes(batch_payload)
    batch_sha256 = sha256_file(batch_path)

    received_path = batch_dir / f'latent_x{count}.rx.bin'
    chunk_plan, wire_payload, wire_manifest = build_wire_payload(
        batch_payload,
        app_chunk_bytes=args.chunk_bytes,
        whitening_enabled=not args.no_whitening,
        whitening_seed=args.whitening_seed,
    )
    attempt_records = []
    failed_chunk_index: int | None = None
    ota_metrics: dict[str, object] = {}
    effective_profile = build_effective_ota_profile(args)

    received_wire_path = batch_dir / 'wire_payload.rx.bin'

    if args.ota_path == 'daemon':
        started = time.perf_counter()
        daemon_ok, received_wire, ota_metrics = run_ota_chunked(
            wire_payload,
            chunk_bytes=args.chunk_bytes,
            chunk_retries=max(0, args.chunk_attempts - 1),
            **frozen_chunked_ota_kwargs(args),
        )
        total_wall_sec = time.perf_counter() - started
        received_payload = recover_payload_from_wire(
            received_wire,
            wire_manifest=wire_manifest,
        )
        if not daemon_ok:
            failed_chunk_index = int(ota_metrics.get('chunk_completed') or 0)
    elif args.ota_path == 'single':
        started = time.perf_counter()
        daemon_ok, received_wire, ota_metrics = run_ota_chunked(
            wire_payload,
            chunk_bytes=max(1, len(wire_payload)),
            chunk_retries=0,
            chunk_align_bytes=0,
            **frozen_chunked_ota_kwargs(args),
        )
        total_wall_sec = time.perf_counter() - started
        ota_metrics = dict(ota_metrics or {})
        ota_metrics['ota_total_wall_sec'] = round(total_wall_sec, 6)
        ota_metrics['ota_ok'] = bool(daemon_ok)
        ota_metrics['ota_transaction_count'] = 1
        received_wire_path.write_bytes(received_wire)
        received_payload = recover_payload_from_wire(
            received_wire,
            wire_manifest=wire_manifest,
        )
        if not daemon_ok:
            failed_chunk_index = 0
    else:
        ota_kwargs = frozen_ota_kwargs(args)
        received_parts: list[bytes] = []
        started = time.perf_counter()
        for chunk_index, (offset, chunk) in enumerate(chunk_plan):
            wire_chunk = wire_payload[offset:offset + len(chunk)]
            wire_seed = int(wire_manifest[chunk_index]['whitening_seed'])
            success, received_chunk, attempts = transmit_chunk(
                chunk_index=chunk_index,
                offset=offset,
                chunk=chunk,
                wire_chunk=wire_chunk,
                chunk_dir=chunks_dir,
                max_attempts=args.chunk_attempts,
                ota_kwargs=ota_kwargs,
                whitening_enabled=not args.no_whitening,
                whitening_seed=wire_seed,
            )
            attempt_records.extend(asdict(item) for item in attempts)
            if not success:
                failed_chunk_index = chunk_index
                break
            received_parts.append(received_chunk)
            if args.chunk_gap_sec > 0:
                time.sleep(args.chunk_gap_sec)
        total_wall_sec = time.perf_counter() - started
        received_payload = b''.join(received_parts)

    received_path.write_bytes(received_payload)
    received_sha256 = sha256_file(received_path) if received_payload else ''
    sha_match = received_payload == batch_payload

    success = failed_chunk_index is None and sha_match
    total_bytes = len(batch_payload)
    throughput_kib_s = (total_bytes / 1024.0 / total_wall_sec) if total_wall_sec > 0 else 0.0
    per_image_sec = (total_wall_sec / count) if count > 0 else 0.0
    if args.ota_path == 'daemon':
        retry_used = int(ota_metrics.get('chunk_retry_used') or 0)
    elif args.ota_path == 'single':
        retry_used = 0
    else:
        retry_used = sum(
            int(record['attempt_index']) - 1
            for record in attempt_records
            if bool(record['success'])
        )

    result = {
        'success': success,
        'ota_path': args.ota_path,
        'count': count,
        'single_image_bytes': len(source_bytes),
        'single_image_sha256': source_sha256,
        'total_bytes': total_bytes,
        'chunk_bytes': args.chunk_bytes,
        'chunk_count': len(chunk_plan),
        'ota_transaction_count': 1 if args.ota_path == 'single' else len(chunk_plan),
        'chunk_attempts_limit': args.chunk_attempts,
        'retry_used': retry_used,
        'failed_chunk_index': failed_chunk_index,
        'source_path': str(batch_path),
        'received_path': str(received_path),
        'source_sha256': batch_sha256,
        'received_sha256': received_sha256,
        'sha_match': sha_match,
        'total_wall_sec': round(total_wall_sec, 6),
        'per_image_sec': round(per_image_sec, 6),
        'throughput_kib_s': round(throughput_kib_s, 6),
        'whitening_enabled': (not args.no_whitening),
        'whitening_seed_base': int(args.whitening_seed),
        'chunk_gap_sec': float(args.chunk_gap_sec),
        'profile': effective_profile,
        'ota_metrics': ota_metrics,
        'wire_manifest': wire_manifest,
        'attempts': attempt_records,
    }

    result_path = batch_dir / 'result.json'
    with result_path.open('w', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')

    print(
        f'[Count {count}] '
        f'{"PASS" if success else "FAIL"} '
        f'total={format_seconds(total_wall_sec)} '
        f'per_image={per_image_sec:.2f}s '
        f'throughput={throughput_kib_s:.2f} KiB/s '
        f'chunks={len(chunk_plan)} retries={retry_used}',
        flush=True,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='多张 latent OTA 基准测试')
    parser.add_argument('--input-latent', default=str(DEFAULT_INPUT_LATENT), help='单张 latent .npz 路径')
    parser.add_argument('--counts', default=DEFAULT_COUNTS, help='图片数列表，逗号分隔')
    parser.add_argument('--artifact-root', default=str(DEFAULT_ARTIFACT_ROOT), help='本地留档根目录')
    parser.add_argument('--chunk-bytes', type=int, default=8192, help='单个 OTA chunk 最大字节数')
    parser.add_argument('--chunk-attempts', type=int, default=4, help='单个 chunk 最大尝试次数')
    parser.add_argument('--chunk-gap-sec', type=float, default=0.5, help='chunk 成功后额外等待秒数')
    parser.add_argument(
        '--ota-path',
        choices=('daemon', 'single', 'legacy'),
        default='daemon',
        help='OTA 编排路径：daemon=应用层 chunked-daemon；single=整图一次 daemon 事务；legacy=逐 chunk 调用 run_ota()',
    )
    parser.add_argument('--board-host', default='100.121.87.73', help='板端 SSH 地址')
    parser.add_argument('--board-user', default='user', help='板端 SSH 用户名')
    parser.add_argument('--board-pass', default='user', help='板端 SSH 密码')
    parser.add_argument('--board-port', default='22', help='板端 SSH 端口')
    parser.add_argument(
        '--remote-build-dir',
        default='/home/user/usrp_tensor_codex_20260422_seq0best_1/usrp_tensor/build_seq0best',
        help='板端 usrp_tensor build 目录',
    )
    parser.add_argument('--local-serial-args', default='serial=31E74E3', help='本地 TX UHD args')
    parser.add_argument('--remote-serial-args', default='serial=31DDAB3', help='板端 RX UHD args')
    parser.add_argument('--remote-rx-ant', default='TX/RX', help='板端 RX 天线口位')
    parser.add_argument('--freq', type=float, default=915e6, help='射频中心频率')
    parser.add_argument('--rx-timeout', type=float, default=60.0, help='单个 chunk OTA 总等待时限')
    parser.add_argument('--remote-kill-after', type=float, default=60.0, help='板端 RX shell timeout')
    parser.add_argument('--no-whitening', action='store_true', help='关闭公开 PRBS chunk whitening')
    parser.add_argument('--whitening-seed', type=int, default=0x6D2B79F5, help='公开 PRBS whitening 基准种子')
    add_ota_profile_arguments(parser)
    args = parser.parse_args()

    input_latent = Path(args.input_latent)
    if not input_latent.exists():
        raise FileNotFoundError(f'找不到 latent 输入文件: {input_latent}')

    counts = parse_counts(args.counts)
    run_id = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path(args.artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    source_copy = run_dir / input_latent.name
    shutil.copy2(input_latent, source_copy)
    source_bytes = source_copy.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    print(
        f'[Input] latent={source_copy} size={len(source_bytes)}B sha256={source_sha256} '
        f'counts={counts}',
        flush=True,
    )

    results = []
    for count in counts:
        results.append(
            run_single_count(
                count=count,
                source_bytes=source_bytes,
                source_sha256=source_sha256,
                run_dir=run_dir,
                args=args,
            )
        )

    summary = {
        'input_latent': str(source_copy),
        'single_image_bytes': len(source_bytes),
        'single_image_sha256': source_sha256,
        'counts': counts,
        'profile': build_effective_ota_profile(args),
        'results': results,
    }
    summary_path = run_dir / 'summary.json'
    with summary_path.open('w', encoding='utf-8') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write('\n')

    print()
    print('=' * 60)
    print('[Benchmark] 完成')
    print(f'  summary : {summary_path}')
    print('=' * 60)
    return 0 if all(bool(item['success']) for item in results) else 2


if __name__ == '__main__':
    raise SystemExit(main())
