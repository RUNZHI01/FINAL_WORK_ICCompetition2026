#!/usr/bin/env python3
"""usrp_image_demo.py — 冻结 8KB 稳定参数的独立图片 OTA 演示

目标：
  1. 准备一张 <=8KB 的图片文件（用户提供或自动生成）
  2. 用当前最稳的 1 Msps / 单帧 OTA 参数通过 USRP 发送
  3. 自动抓回接收文件，并在本地生成原图 / 接收图对比图

说明：
  - 这是一条独立演示路径，不依赖主 demo
  - 当前走的是“图片文件明文 over USRP”，不是 TVM latent 重建链
  - 演示目标是：看见图片文件通过 USRP 成功重建，并留下完整留档
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageOps
except ImportError:
    Image = None
    ImageDraw = None
    ImageOps = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / 'artifacts' / 'usrp_image_demo_live'
DEFAULT_REMOTE_BUILD_DIR = (
    '/home/user/usrp_tensor_codex_20260421_rxpool_20260421b/usrp_tensor/build_clean'
)
MAX_SINGLE_FRAME_BYTES = 8192

FROZEN_PROFILE: dict[str, str] = {
    'rate': '1000000.0',
    'wait': '0.4',
    'start_pad': '250000',
    'repeat': '4',
    'frame_repeat': '1',
    'spb': '10000',
    'setup': '0.1',
    'decode_workers': '2',
    'no_frame_timeout': '20.0',
    'tx_gain': '60.0',
    'rx_gain': '60.0',
    'warmup_frames': '2',
    'warmup_repeats': '2',
    'warmup_rounds': '1',
    'round_gap_ms': '500',
    'tail_pad_samps': '2000',
    'first_frame_extra_repeats': '1',
    'last_frame_extra_repeats': '0',
    'payload_search_order': 'phase-first',
    'frame_order': 'normal',
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def generate_demo_image(path: Path) -> Path:
    if Image is None or ImageDraw is None:
        raise RuntimeError('缺少 Pillow，无法自动生成演示图片')

    image = Image.new('RGB', (80, 80), (240, 242, 245))
    draw = ImageDraw.Draw(image)

    for offset in range(0, 80, 8):
        draw.rectangle(
            (offset, 0, 79, 79 - offset),
            outline=(0, 90 + (offset * 2) % 120, 180),
            width=1,
        )
    draw.rectangle((8, 8, 72, 72), fill=(255, 255, 255), outline=(20, 40, 80), width=2)
    draw.text((18, 20), 'USRP', fill=(0, 0, 0))
    draw.text((22, 42), 'DEMO', fill=(0, 80, 160))

    image.save(path, format='PNG', optimize=True)
    return path


def fit_image_to_budget(source: Path, output_dir: Path, max_bytes: int) -> Path:
    if source.stat().st_size <= max_bytes:
        target = output_dir / f'input{source.suffix.lower()}'
        shutil.copy2(source, target)
        return target

    if Image is None:
        raise RuntimeError(f'输入图片 {source} 超过 {max_bytes}B，且 Pillow 不可用，无法自动压缩')

    with Image.open(source) as image:
        image = image.convert('RGB')

        scales = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
        jpeg_qualities = [92, 85, 78, 70, 62, 55, 48]

        best_candidate: Path | None = None
        best_size: int | None = None

        for scale in scales:
            resized = image
            if scale < 0.999:
                width = max(32, int(round(image.width * scale)))
                height = max(32, int(round(image.height * scale)))
                resized = image.resize((width, height))

            png_candidate = output_dir / f'input_scale_{int(scale * 100)}.png'
            resized.save(png_candidate, format='PNG', optimize=True)
            png_size = png_candidate.stat().st_size
            if png_size <= max_bytes:
                final_target = output_dir / 'input.png'
                shutil.copy2(png_candidate, final_target)
                return final_target
            if best_size is None or png_size < best_size:
                best_candidate = png_candidate
                best_size = png_size

            for quality in jpeg_qualities:
                jpg_candidate = output_dir / f'input_scale_{int(scale * 100)}_q{quality}.jpg'
                resized.save(jpg_candidate, format='JPEG', quality=quality, optimize=True)
                jpg_size = jpg_candidate.stat().st_size
                if jpg_size <= max_bytes:
                    final_target = output_dir / 'input.jpg'
                    shutil.copy2(jpg_candidate, final_target)
                    return final_target
                if best_size is None or jpg_size < best_size:
                    best_candidate = jpg_candidate
                    best_size = jpg_size

    if best_candidate is None or best_size is None:
        raise RuntimeError(f'无法将 {source} 压缩到 {max_bytes}B 以内')

    raise RuntimeError(
        f'无法将 {source} 压缩到 {max_bytes}B 以内，当前最小候选为 {best_candidate} ({best_size}B)'
    )


def create_comparison_image(source: Path, received: Path, output_path: Path) -> bool:
    if Image is None or ImageDraw is None or ImageOps is None:
        return False

    try:
        with Image.open(source) as source_img, Image.open(received) as received_img:
            source_rgb = source_img.convert('RGB')
            received_rgb = received_img.convert('RGB')
    except Exception:
        return False

    panel_size = (240, 240)
    title_h = 30
    gap = 20
    canvas = Image.new(
        'RGB',
        (panel_size[0] * 2 + gap * 3, panel_size[1] + gap * 2 + title_h),
        (246, 248, 251),
    )
    draw = ImageDraw.Draw(canvas)

    left = ImageOps.contain(source_rgb, panel_size)
    right = ImageOps.contain(received_rgb, panel_size)

    left_x = gap + (panel_size[0] - left.width) // 2
    right_x = gap * 2 + panel_size[0] + (panel_size[0] - right.width) // 2
    y = gap + title_h

    canvas.paste(left, (left_x, y))
    canvas.paste(right, (right_x, y))

    draw.text((gap, 8), 'Source Image', fill=(10, 20, 40))
    draw.text((gap * 2 + panel_size[0], 8), 'Received Image', fill=(10, 20, 40))

    draw.rectangle(
        (gap - 1, y - 1, gap + panel_size[0], y + panel_size[1]),
        outline=(40, 60, 90),
        width=1,
    )
    draw.rectangle(
        (gap * 2 + panel_size[0] - 1, y - 1, gap * 2 + panel_size[0] + panel_size[0], y + panel_size[1]),
        outline=(40, 60, 90),
        width=1,
    )

    canvas.save(output_path, format='PNG')
    return True


def build_sweep_command(
    *,
    input_file: Path,
    sweep_artifact_root: Path,
    board_host: str,
    board_user: str,
    board_pass: str,
    board_port: str,
    remote_build_dir: str,
    local_serial_args: str,
    remote_serial_args: str,
    remote_rx_ant: str,
    freq: float,
) -> list[str]:
    return [
        sys.executable,
        'scripts/usrp_ota_sweep.py',
        '--file', str(input_file),
        '--board-host', board_host,
        '--board-user', board_user,
        '--board-pass', board_pass,
        '--remote-build-dir', remote_build_dir,
        '--local-serial-args', local_serial_args,
        '--remote-serial-args', remote_serial_args,
        '--remote-rx-ant', remote_rx_ant,
        '--freq', str(freq),
        '--rates', FROZEN_PROFILE['rate'],
        '--waits', FROZEN_PROFILE['wait'],
        '--start-pads', FROZEN_PROFILE['start_pad'],
        '--repeats', FROZEN_PROFILE['repeat'],
        '--frame-repeats', FROZEN_PROFILE['frame_repeat'],
        '--spbs', FROZEN_PROFILE['spb'],
        '--setups', FROZEN_PROFILE['setup'],
        '--decode-workers', FROZEN_PROFILE['decode_workers'],
        '--no-frame-timeouts', FROZEN_PROFILE['no_frame_timeout'],
        '--tx-gain', FROZEN_PROFILE['tx_gain'],
        '--rx-gain', FROZEN_PROFILE['rx_gain'],
        '--warmup-frames', FROZEN_PROFILE['warmup_frames'],
        '--warmup-repeats', FROZEN_PROFILE['warmup_repeats'],
        '--warmup-rounds', FROZEN_PROFILE['warmup_rounds'],
        '--round-gap-ms', FROZEN_PROFILE['round_gap_ms'],
        '--tail-pad-samps', FROZEN_PROFILE['tail_pad_samps'],
        '--first-frame-extra-repeats', FROZEN_PROFILE['first_frame_extra_repeats'],
        '--last-frame-extra-repeats', FROZEN_PROFILE['last_frame_extra_repeats'],
        '--payload-search-orders', FROZEN_PROFILE['payload_search_order'],
        '--frame-orders', FROZEN_PROFILE['frame_order'],
        '--attempts-per-config', '3',
        '--stop-on-success',
        '--fetch-output',
        '--artifact-dir', str(sweep_artifact_root),
    ]


def load_summary_record(summary_path: Path) -> dict[str, object]:
    records: list[dict[str, object]] = []
    with summary_path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise RuntimeError(f'空的 summary.jsonl: {summary_path}')

    for record in records:
        if bool(record.get('success')):
            return record
    return records[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description='冻结 8KB 稳定参数的独立图片 OTA 演示')
    parser.add_argument('--input-image', help='待发送图片路径；留空时自动生成演示图')
    parser.add_argument('--artifact-root', default=str(DEFAULT_ARTIFACT_ROOT), help='本地演示留档根目录')
    parser.add_argument('--board-host', default='100.121.87.73', help='板端 SSH 地址')
    parser.add_argument('--board-user', default='user', help='板端 SSH 用户名')
    parser.add_argument('--board-pass', default='user', help='板端 SSH 密码')
    parser.add_argument('--board-port', default='22', help='板端 SSH 端口')
    parser.add_argument('--remote-build-dir', default=DEFAULT_REMOTE_BUILD_DIR, help='板端 usrp_tensor build 目录')
    parser.add_argument('--local-serial-args', default='serial=31E74E3', help='本地 TX UHD args')
    parser.add_argument('--remote-serial-args', default='serial=31DDAB3', help='板端 RX UHD args')
    parser.add_argument('--remote-rx-ant', default='TX/RX', help='板端 RX 天线口位')
    parser.add_argument('--freq', type=float, default=915e6, help='射频中心频率')
    parser.add_argument('--max-bytes', type=int, default=MAX_SINGLE_FRAME_BYTES, help='单帧图片大小上限')
    args = parser.parse_args()

    run_id = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path(args.artifact_root) / run_id
    assets_dir = run_dir / 'assets'
    sweep_root = run_dir / 'ota_trials'
    assets_dir.mkdir(parents=True, exist_ok=True)

    if args.input_image:
        source_image = fit_image_to_budget(Path(args.input_image), assets_dir, args.max_bytes)
    else:
        source_image = generate_demo_image(assets_dir / 'input.png')
        if source_image.stat().st_size > args.max_bytes:
            raise RuntimeError(
                f'自动生成的演示图片超过单帧预算: {source_image.stat().st_size}B > {args.max_bytes}B'
            )

    source_sha = sha256_file(source_image)
    print(f'[Image] source={source_image} size={source_image.stat().st_size} sha256={source_sha}', flush=True)

    command = build_sweep_command(
        input_file=source_image,
        sweep_artifact_root=sweep_root,
        board_host=args.board_host,
        board_user=args.board_user,
        board_pass=args.board_pass,
        board_port=args.board_port,
        remote_build_dir=args.remote_build_dir,
        local_serial_args=args.local_serial_args,
        remote_serial_args=args.remote_serial_args,
        remote_rx_ant=args.remote_rx_ant,
        freq=args.freq,
    )

    print('[Run] 启动 frozen 8KB OTA 图片演示...', flush=True)
    result = subprocess.run(command, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f'[Fail] OTA sweep 返回 rc={result.returncode}')
        print(f'[Artifacts] {run_dir}')
        return result.returncode

    summary_files = sorted(sweep_root.glob('*/summary.jsonl'))
    if not summary_files:
        raise RuntimeError(f'未找到 OTA 汇总文件: {sweep_root}')

    summary_path = summary_files[-1]
    record = load_summary_record(summary_path)
    trial_dir = REPO_ROOT / str(record['trial_dir'])
    rx_bin = trial_dir / 'rx.bin'
    if not rx_bin.exists():
        raise RuntimeError(f'未找到接收文件: {rx_bin}')

    received_path = assets_dir / f'received{source_image.suffix.lower()}'
    shutil.copy2(rx_bin, received_path)
    received_sha = sha256_file(received_path)

    comparison_path = assets_dir / 'comparison.png'
    comparison_ready = create_comparison_image(source_image, received_path, comparison_path)

    demo_result = {
        'success': bool(record['success']),
        'sha_match': bool(record['sha_match']),
        'source_image': str(source_image),
        'received_image': str(received_path),
        'comparison_image': str(comparison_path) if comparison_ready else '',
        'summary_jsonl': str(summary_path),
        'trial_dir': str(trial_dir),
        'source_size': source_image.stat().st_size,
        'received_size': received_path.stat().st_size,
        'source_sha256': source_sha,
        'received_sha256': received_sha,
        'profile': dict(FROZEN_PROFILE),
    }

    result_path = run_dir / 'demo_result.json'
    with result_path.open('w', encoding='utf-8') as handle:
        json.dump(demo_result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')

    print()
    print('=' * 60)
    print('[PASS] USRP 图片独立演示完成' if demo_result['sha_match'] else '[WARN] USRP 图片演示已完成但文件不一致')
    print(f'  source   : {source_image}')
    print(f'  received : {received_path}')
    if comparison_ready:
        print(f'  compare  : {comparison_path}')
    print(f'  summary  : {summary_path}')
    print(f'  result   : {result_path}')
    print('=' * 60)
    return 0 if demo_result['sha_match'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
