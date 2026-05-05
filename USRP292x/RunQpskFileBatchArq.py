#!/usr/bin/env python3
"""Run multiple USRP292x QPSK selective-ARQ file transfers.

This is an orchestration helper for the "300 images without transfer error"
milestone. It repeatedly calls RunQpskFileArqOta.sh and aggregates each image's
merge summary into one batch_summary.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / 'USRP292x' / 'payloads' / 'source_latent_wire_blob.bin'
DEFAULT_RUN_ROOT = PROJECT_ROOT / 'USRP292x' / 'qpsk_batch_arq_runs'
DEFAULT_SCRIPT = PROJECT_ROOT / 'USRP292x' / 'RunQpskFileArqOta.sh'


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='USRP292x QPSK selective-ARQ batch runner.')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--input', type=Path, default=None, help='single payload/wire blob')
    source.add_argument('--input-list', type=Path, default=None, help='text file with one payload path per line')
    source.add_argument('--input-dir', type=Path, default=None, help='directory containing payload files')
    parser.add_argument('--pattern', default='*.bin', help='input-dir glob pattern')
    parser.add_argument('--count', type=int, default=300)
    parser.add_argument('--cycle-inputs', action='store_true', help='cycle input-list/input-dir if count is larger')
    parser.add_argument('--run-id', default=time.strftime('batch_%Y%m%d_%H%M%S'))
    parser.add_argument('--run-root', type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument('--script', type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument('--max-arq-rounds', type=int, default=2)
    parser.add_argument('--stop-on-fail', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    return parser.parse_args()


def load_inputs(args: argparse.Namespace) -> list[Path]:
    if args.input is not None:
        paths = [args.input]
    elif args.input_list is not None:
        paths = [
            Path(line.strip())
            for line in args.input_list.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        ]
    elif args.input_dir is not None:
        paths = sorted(path for path in args.input_dir.rglob(args.pattern) if path.is_file())
    else:
        paths = [DEFAULT_INPUT]

    if not paths:
        raise RuntimeError('no input payloads found')

    resolved = [path.resolve() for path in paths]
    missing = [str(path) for path in resolved if not path.is_file()]
    if missing:
        raise RuntimeError(f'input payload not found: {missing[:3]}')

    if len(resolved) >= args.count:
        return resolved[:args.count]
    if len(resolved) == 1:
        return [resolved[0] for _ in range(args.count)]
    if args.cycle_inputs:
        return [resolved[idx % len(resolved)] for idx in range(args.count)]
    raise RuntimeError(
        f'count={args.count} requires {args.count} inputs, got {len(resolved)}. '
        'Use --cycle-inputs to reuse them.'
    )


def latest_merge_summary(image_dir: Path) -> Path | None:
    candidates = list(image_dir.glob('merge_round*.json'))
    if not candidates:
        return None

    def key(path: Path) -> int:
        match = re.search(r'merge_round(\d+)\.json$', path.name)
        return int(match.group(1)) if match else -1

    return max(candidates, key=key)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def collect_image_result(index: int, input_path: Path, image_dir: Path, status: int, wall_sec: float) -> dict:
    merge_path = latest_merge_summary(image_dir)
    round_dirs = sorted(path for path in image_dir.glob('round*') if path.is_dir())
    decode_summaries = []
    for round_dir in round_dirs:
        summary_path = round_dir / 'decode_summary.json'
        if summary_path.is_file():
            decode_summaries.append(read_json(summary_path))

    if merge_path and merge_path.is_file():
        merge = read_json(merge_path)
        exact = bool(merge.get('exact'))
        missing_chunks = list(merge.get('missing_chunks', []))
        byte_errors = int(merge.get('byte_errors', -1))
        bit_errors = int(merge.get('bit_errors', -1))
    else:
        merge = {}
        exact = False
        missing_chunks = []
        byte_errors = -1
        bit_errors = -1

    payload_airtime_ms = sum(float(item.get('detected_airtime_ms', 0.0)) for item in decode_summaries)
    compared_bytes = sum(int(item.get('compared_transmitted_bytes', 0)) for item in decode_summaries)
    return {
        'index': index,
        'input': str(input_path),
        'input_sha256': sha256_file(input_path),
        'run_dir': str(image_dir),
        'status': status,
        'pass': status == 0 and exact and byte_errors == 0 and bit_errors == 0,
        'rounds': len(round_dirs),
        'payload_airtime_ms': payload_airtime_ms,
        'compared_transmitted_bytes': compared_bytes,
        'missing_chunks': missing_chunks,
        'byte_errors': byte_errors,
        'bit_errors': bit_errors,
        'merge_summary': str(merge_path) if merge_path else '',
        'wall_sec': wall_sec,
        'round_summaries': [
            {
                'frames_transmitted': item.get('frames_transmitted'),
                'crc_ok': item.get('crc_ok'),
                'missing_chunks': item.get('missing_chunks'),
                'ber': item.get('ber'),
                'detected_airtime_ms': item.get('detected_airtime_ms'),
                'effective_payload_mbps': item.get('effective_payload_mbps'),
            }
            for item in decode_summaries
        ],
        'merge': {
            'exact': merge.get('exact', False),
            'crc_ok_indices': merge.get('crc_ok_indices', []),
            'sha256': merge.get('sha256', ''),
            'reference_sha256': merge.get('reference_sha256', ''),
        },
    }


def write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise RuntimeError('--count must be positive')

    inputs = load_inputs(args)
    run_root = (args.run_root / args.run_id).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / 'batch_summary.json'

    started = time.time()
    results: list[dict] = []
    summary = {
        'run_id': args.run_id,
        'run_root': str(run_root),
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'target_count': args.count,
        'max_arq_rounds': args.max_arq_rounds,
        'dry_run': args.dry_run,
        'results': results,
    }
    write_summary(summary_path, summary)

    for idx, input_path in enumerate(inputs):
        image_dir = run_root / f'image_{idx:04d}'
        print(f'image={idx}/{args.count - 1} input={input_path}')
        if args.dry_run:
            results.append({
                'index': idx,
                'input': str(input_path),
                'run_dir': str(image_dir),
                'status': 0,
                'pass': True,
                'dry_run': True,
            })
            write_summary(summary_path, summary)
            continue

        env = os.environ.copy()
        env.update({
            'RUN_ID': f'image_{idx:04d}',
            'RUN_DIR': str(image_dir),
            'INPUT': str(input_path),
            'MAX_ARQ_ROUNDS': str(args.max_arq_rounds),
        })
        image_dir.mkdir(parents=True, exist_ok=True)
        log_path = image_dir / 'batch_runner.log'
        image_started = time.monotonic()
        with log_path.open('w', encoding='utf-8') as log:
            proc = subprocess.run(
                ['bash', str(args.script)],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        wall_sec = time.monotonic() - image_started
        result = collect_image_result(idx, input_path, image_dir, proc.returncode, wall_sec)
        results.append(result)

        passed = sum(1 for item in results if item.get('pass'))
        failed = len(results) - passed
        summary.update({
            'completed_count': len(results),
            'pass_count': passed,
            'fail_count': failed,
            'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'elapsed_sec': time.time() - started,
        })
        write_summary(summary_path, summary)
        print(
            f"image_result index={idx} pass={result['pass']} "
            f"rounds={result.get('rounds')} missing={result.get('missing_chunks')} "
            f"wall_sec={wall_sec:.3f}"
        )

        if args.stop_on_fail and not result['pass']:
            break

    passed = sum(1 for item in results if item.get('pass'))
    failed = len(results) - passed
    summary.update({
        'completed_count': len(results),
        'pass_count': passed,
        'fail_count': failed,
        'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'elapsed_sec': time.time() - started,
        'all_pass': len(results) == args.count and failed == 0,
        'total_payload_airtime_ms': sum(float(item.get('payload_airtime_ms', 0.0)) for item in results),
        'total_wall_sec': sum(float(item.get('wall_sec', 0.0)) for item in results),
    })
    write_summary(summary_path, summary)

    print(f'batch_summary={summary_path}')
    print(f'completed_count={len(results)}')
    print(f'pass_count={passed}')
    print(f'fail_count={failed}')
    print(f'all_pass={str(summary["all_pass"]).lower()}')
    return 0 if summary['all_pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
