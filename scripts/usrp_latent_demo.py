#!/usr/bin/env python3
"""usrp_latent_demo.py — 基于稳定单帧窗口的 33KB latent 独立 OTA 演示

目标：
  1. 读取真实的 quantized latent `.npz`（默认 `/tmp/usrp_single_image_baseline.npz`）
  2. 以 <= 8192B 的应用层分块串行复用当前最稳的单帧 OTA 参数
  3. 在本地重组文件并做 SHA256 校验
  4. 把源 latent / OTA 重组 latent 都送到板端 TVM 跑重建
  5. 拉回 baseline / OTA reconstruction，生成 PNG 与对比图

说明：
  - 数据面保持明文，不走 ML-KEM / AEAD
  - 不依赖主 demo 面板，可独立演示“latent over USRP”
  - 当前保留 `scripts/usrp_image_demo.py` 作为独立兜底路径
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

import numpy as np

from e2e_usrp import build_scp_prefix, build_ssh_prefix, run_ota, run_ota_chunked
from usrp_image_demo import (
    create_comparison_image,
    sha256_file,
)
from usrp_metrics import format_snr_text, npz_payload_metrics

try:
    from PIL import Image
except ImportError:
    Image = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / 'artifacts' / 'usrp_latent_demo_live'
DEFAULT_INPUT_LATENT = Path('/tmp/usrp_single_image_baseline.npz')
DEFAULT_REMOTE_BUILD_DIR = (
    '/home/user/usrp_tensor_codex_20260422_seq0best_1/usrp_tensor/build_seq0best'
)
DEFAULT_REMOTE_SPOOL_BUILD_DIR = (
    '/home/user/usrp_tensor_codex_20260423_spool_1/usrp_tensor/build_spool'
)
DEFAULT_REMOTE_TVM_PYTHON = '/home/user/anaconda3/envs/tvm310_safe/bin/python'
DEFAULT_REMOTE_TVM_ARTIFACT = (
    '/home/user/Downloads/jscc-test/jscc_opus_final_mean4_v7_20260406/'
    'tvm_tune_logs/optimized_model.so'
)
DEFAULT_REMOTE_TVM_LD_LIBRARY_PATH = (
    '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:'
    '/home/user/tvm_samegen_safe_20260309/build'
)
DEFAULT_REMOTE_TVM_PYTHONPATH = (
    '/home/user/tvm_samegen_20260307/python:'
    '/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages'
)
DEFAULT_REMOTE_TVM_LIBRARY_PATH = '/home/user/tvm_samegen_safe_20260309/build'
DEFAULT_CHUNK_BYTES = 8192
DEFAULT_SPOOL_ARQ_CHUNK_BYTES = 4096
DEFAULT_SEPARATE_TX_WARMUP_BYTES = 4096
DEFAULT_SEPARATE_TX_WARMUP_SETTLE_SEC = 0.2

LATENT_FROZEN_PROFILE: dict[str, str] = {
    'rate': '1000000.0',
    'wait': '0.4',
    'start_pad': '250000',
    'repeat': '3',
    'frame_repeat': '1',
    'spb': '10000',
    'setup': '0.1',
    'decode_workers': '2',
    'no_frame_timeout': '20.0',
    'tx_gain': '60.0',
    'rx_gain': '60.0',
    'warmup_frames': '1',
    'warmup_repeats': '1',
    'warmup_rounds': '1',
    'round_gap_ms': '128',
    'tail_pad_samps': '2000',
    'first_frame_extra_repeats': '0',
    'last_frame_extra_repeats': '0',
    'payload_search_order': 'phase-first',
    'frame_order': 'normal',
}

SPOOL_FROZEN_PROFILE_OVERRIDES: dict[str, str] = {
    'rate': '2500000.0',
    'frame_order': 'tail-first',
    'last_frame_extra_repeats': '1',
}

SPOOL_ARQ_PROFILE_OVERRIDES: dict[str, str] = {
    'rate': '2500000.0',
    'repeat': '1',
    'frame_order': 'normal',
    'warmup_frames': '1',
    'warmup_repeats': '1',
    'warmup_rounds': '0',
    'first_frame_extra_repeats': '1',
    'last_frame_extra_repeats': '1',
}

OTA_PROFILE_OVERRIDE_SPECS: tuple[tuple[str, str, type, str], ...] = (
    ('rate', 'rate', float, 'OTA 采样率'),
    ('wait', 'ota_wait', float, 'RX ready 后等待 TX 的秒数'),
    ('start_pad', 'start_pad_samps', int, 'TX 首帧前 pad 样点数'),
    ('repeat', 'repeat', int, '整包 repeat 次数'),
    ('frame_repeat', 'frame_repeat', int, '单帧 repeat 次数'),
    ('spb', 'rx_spb', int, 'RX samples-per-buffer'),
    ('setup', 'rx_setup', float, 'RX setup 等待秒数'),
    ('decode_workers', 'decode_workers', int, 'RX decode worker 数'),
    ('no_frame_timeout', 'no_frame_timeout', float, 'RX 无新帧超时秒数'),
    ('tx_gain', 'tx_gain', float, 'TX gain'),
    ('rx_gain', 'rx_gain', float, 'RX gain'),
    ('warmup_frames', 'warmup_frames', int, 'warmup frame 数'),
    ('warmup_repeats', 'warmup_repeats', int, 'warmup repeat 次数'),
    ('warmup_rounds', 'warmup_rounds', int, 'warmup round 数'),
    ('round_gap_ms', 'round_gap_ms', int, 'frame round gap 毫秒数'),
    ('tail_pad_samps', 'tail_pad_samps', int, '尾部 pad 样点数'),
    (
        'first_frame_extra_repeats',
        'first_frame_extra_repeats',
        int,
        '首帧额外 repeats',
    ),
    (
        'last_frame_extra_repeats',
        'last_frame_extra_repeats',
        int,
        '尾帧额外 repeats',
    ),
    (
        'payload_search_order',
        'payload_search_order',
        str,
        'RX payload search 顺序',
    ),
    ('frame_order', 'frame_order', str, 'TX frame 顺序'),
)


@dataclass
class ChunkAttemptRecord:
    """单次 chunk OTA 尝试结果。"""

    chunk_index: int
    offset: int
    length: int
    attempt_index: int
    success: bool
    received_size: int
    whitening_enabled: bool
    whitening_seed: int
    sha256_sent: str
    sha256_received: str
    wall_sec: float
    input_path: str
    output_path: str
    log_path: str
    radio_metrics: dict[str, object]


@dataclass
class RemoteInferenceRecord:
    """单次远端 TVM 推理结果。"""

    label: str
    remote_input: str
    remote_output: str
    local_output: str
    log_path: str
    output_sha256: str
    output_shape: list[int]
    output_dtype: str
    inference_ms: float
    load_ms: float
    jscc_configured_awgn_snr_db: float | None
    jscc_realized_awgn_snr_db: float | None
    jscc_awgn_note: str


class TeeStream:
    """stdout 简单双写。"""

    def __init__(self, *streams: TextIO) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def chunk_bytes(payload: bytes, max_chunk_bytes: int) -> list[tuple[int, bytes]]:
    """按固定大小切块。"""
    return [
        (offset, payload[offset:offset + max_chunk_bytes])
        for offset in range(0, len(payload), max_chunk_bytes)
    ]


def whiten_bytes(payload: bytes, seed: int) -> bytes:
    """使用固定公开 PRBS 做可逆 whitening。"""
    state = seed & 0xFFFFFFFF
    output = bytearray()
    for byte in payload:
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        output.append(byte ^ ((state >> 24) & 0xFF))
    return bytes(output)


def build_wire_chunk(
    payload: bytes,
    *,
    chunk_index: int,
    whitening_enabled: bool,
    whitening_seed: int,
) -> tuple[bytes, int]:
    """生成 OTA 发送字节。"""
    effective_seed = (int(whitening_seed) + int(chunk_index)) & 0xFFFFFFFF
    if not whitening_enabled:
        return payload, effective_seed
    return whiten_bytes(payload, effective_seed), effective_seed


def add_ota_profile_arguments(parser: argparse.ArgumentParser) -> None:
    """向 parser 注入可选 OTA profile 覆盖参数。"""
    for profile_key, arg_name, value_type, help_text in OTA_PROFILE_OVERRIDE_SPECS:
        parser.add_argument(
            f'--{arg_name.replace("_", "-")}',
            dest=arg_name,
            type=value_type,
            default=None,
            help=f'{help_text}；默认沿用 LATENT_FROZEN_PROFILE[{profile_key!r}]',
        )


def build_effective_ota_profile(args: argparse.Namespace) -> dict[str, str]:
    """基于 LATENT_FROZEN_PROFILE 与 CLI 覆盖项生成实际生效 profile。"""
    profile = dict(LATENT_FROZEN_PROFILE)
    if getattr(args, 'ota_path', None) == 'spool':
        profile.update(SPOOL_FROZEN_PROFILE_OVERRIDES)
    elif getattr(args, 'ota_path', None) == 'spool_arq':
        profile.update(SPOOL_ARQ_PROFILE_OVERRIDES)
    for profile_key, arg_name, _value_type, _help_text in OTA_PROFILE_OVERRIDE_SPECS:
        override = getattr(args, arg_name, None)
        if override is None:
            continue
        profile[profile_key] = str(override)
    return profile


def frozen_ota_kwargs(args: argparse.Namespace) -> dict[str, object]:
    """把实际生效 profile 转成 `run_ota()` 参数。"""
    profile = build_effective_ota_profile(args)
    return {
        'tx_args': args.local_serial_args,
        'rx_args': args.remote_serial_args,
        'tx_gain': float(profile['tx_gain']),
        'rx_gain': float(profile['rx_gain']),
        'rate': float(profile['rate']),
        'freq': float(args.freq),
        'repeat': int(profile['repeat']),
        'rx_timeout': float(args.rx_timeout),
        'ota_wait': float(profile['wait']),
        'start_pad_samps': int(profile['start_pad']),
        'round_gap_ms': int(profile['round_gap_ms']),
        'frame_repeat': int(profile['frame_repeat']),
        'rx_spb': int(profile['spb']),
        'rx_setup': float(profile['setup']),
        'no_frame_timeout': float(profile['no_frame_timeout']),
        'rx_ant': args.remote_rx_ant,
        'decode_workers': int(profile['decode_workers']),
        'payload_search_order': profile['payload_search_order'],
        'warmup_frames': int(profile['warmup_frames']),
        'warmup_repeats': int(profile['warmup_repeats']),
        'warmup_rounds': int(profile['warmup_rounds']),
        'tail_pad_samps': int(profile['tail_pad_samps']),
        'last_frame_extra_repeats': int(profile['last_frame_extra_repeats']),
        'first_frame_extra_repeats': int(profile['first_frame_extra_repeats']),
        'frame_order': profile['frame_order'],
        'board_host': args.board_host,
        'board_user': args.board_user,
        'board_pass': args.board_pass,
        'board_port': args.board_port,
        'remote_build_dir': args.remote_build_dir,
        'remote_kill_after': float(args.remote_kill_after),
    }


def frozen_chunked_ota_kwargs(args: argparse.Namespace) -> dict[str, object]:
    """把实际生效 profile 转成 `run_ota_chunked()` 参数。"""
    profile = build_effective_ota_profile(args)
    return {
        'tx_args': args.local_serial_args,
        'rx_args': args.remote_serial_args,
        'tx_gain': float(profile['tx_gain']),
        'rx_gain': float(profile['rx_gain']),
        'rate': float(profile['rate']),
        'freq': float(args.freq),
        'repeat': int(profile['repeat']),
        'rx_timeout': float(args.rx_timeout),
        'ota_wait': float(profile['wait']),
        'start_pad_samps': int(profile['start_pad']),
        'round_gap_ms': int(profile['round_gap_ms']),
        'frame_repeat': int(profile['frame_repeat']),
        'rx_spb': int(profile['spb']),
        'rx_setup': float(profile['setup']),
        'no_frame_timeout': float(profile['no_frame_timeout']),
        'rx_ant': args.remote_rx_ant,
        'decode_workers': int(profile['decode_workers']),
        'payload_search_order': profile['payload_search_order'],
        'warmup_frames': int(profile['warmup_frames']),
        'warmup_repeats': int(profile['warmup_repeats']),
        'warmup_rounds': int(profile['warmup_rounds']),
        'tail_pad_samps': int(profile['tail_pad_samps']),
        'last_frame_extra_repeats': int(profile['last_frame_extra_repeats']),
        'first_frame_extra_repeats': int(profile['first_frame_extra_repeats']),
        'board_host': args.board_host,
        'board_user': args.board_user,
        'board_pass': args.board_pass,
        'board_port': args.board_port,
        'remote_build_dir': args.remote_build_dir,
    }


def build_wire_payload(
    payload: bytes,
    *,
    app_chunk_bytes: int,
    whitening_enabled: bool,
    whitening_seed: int,
) -> tuple[list[tuple[int, bytes]], bytes, list[dict[str, object]]]:
    """按应用层分块生成整包 wire payload 与 manifest。"""
    app_chunk_plan = chunk_bytes(payload, app_chunk_bytes)
    wire_parts: list[bytes] = []
    manifest: list[dict[str, object]] = []
    wire_offset = 0

    for chunk_index, (offset, chunk) in enumerate(app_chunk_plan):
        wire_chunk, wire_seed = build_wire_chunk(
            chunk,
            chunk_index=chunk_index,
            whitening_enabled=whitening_enabled,
            whitening_seed=whitening_seed,
        )
        wire_parts.append(wire_chunk)
        manifest.append(
            {
                'chunk_index': chunk_index,
                'plain_offset': offset,
                'wire_offset': wire_offset,
                'length': len(chunk),
                'whitening_enabled': whitening_enabled,
                'whitening_seed': int(wire_seed),
            }
        )
        wire_offset += len(wire_chunk)

    return app_chunk_plan, b''.join(wire_parts), manifest


def recover_payload_from_wire(
    wire_payload: bytes,
    *,
    wire_manifest: list[dict[str, object]],
) -> bytes:
    """按原始应用层边界从 wire payload 恢复明文 payload。"""
    plain_parts: list[bytes] = []
    for item in wire_manifest:
        start = int(item['wire_offset'])
        end = start + int(item['length'])
        if start >= len(wire_payload):
            break
        wire_chunk = wire_payload[start:end]
        if bool(item.get('whitening_enabled')):
            wire_chunk = whiten_bytes(wire_chunk, int(item['whitening_seed']))
        plain_parts.append(wire_chunk)
        if len(wire_chunk) < int(item['length']):
            break
    return b''.join(plain_parts)


def transmit_chunk(
    *,
    chunk_index: int,
    offset: int,
    chunk: bytes,
    wire_chunk: bytes,
    chunk_dir: Path,
    max_attempts: int,
    ota_kwargs: dict[str, object],
    whitening_enabled: bool,
    whitening_seed: int,
) -> tuple[bool, bytes, list[ChunkAttemptRecord]]:
    """串行发送单个 chunk，直到成功或耗尽重试。"""
    input_path = chunk_dir / f'chunk_{chunk_index:02d}.bin'
    input_path.write_bytes(wire_chunk)
    sent_sha = hashlib.sha256(wire_chunk).hexdigest()

    attempts: list[ChunkAttemptRecord] = []
    for attempt_index in range(1, max_attempts + 1):
        output_path = chunk_dir / f'chunk_{chunk_index:02d}_attempt_{attempt_index:02d}.rx.bin'
        log_path = chunk_dir / f'chunk_{chunk_index:02d}_attempt_{attempt_index:02d}.log'
        if output_path.exists():
            output_path.unlink()

        with log_path.open('w', encoding='utf-8') as log_handle:
            tee = TeeStream(sys.stdout, log_handle)
            with contextlib.redirect_stdout(tee):
                print(
                    f'[Chunk {chunk_index + 1}] '
                    f'offset={offset} len={len(chunk)}B attempt={attempt_index}/{max_attempts}',
                    flush=True,
                )
                started = time.perf_counter()
                ota_result = run_ota(
                    str(input_path),
                    str(output_path),
                    **ota_kwargs,
                )
                wall_sec = time.perf_counter() - started
                print(
                    f'[Chunk {chunk_index + 1}] '
                    f'OTA result ok={bool(ota_result.get("ok"))} wall={wall_sec:.3f}s',
                    flush=True,
                )

        received = output_path.read_bytes() if output_path.exists() else b''
        received_sha = hashlib.sha256(received).hexdigest() if received else ''
        success = received == wire_chunk
        attempts.append(
            ChunkAttemptRecord(
                chunk_index=chunk_index,
                offset=offset,
                length=len(chunk),
                attempt_index=attempt_index,
                success=success,
                received_size=len(received),
                whitening_enabled=whitening_enabled,
                whitening_seed=int(whitening_seed),
                sha256_sent=sent_sha,
                sha256_received=received_sha,
                wall_sec=round(wall_sec, 6),
                input_path=str(input_path),
                output_path=str(output_path),
                log_path=str(log_path),
                radio_metrics=dict(ota_result.get('radio_metrics') or {}),
            )
        )

        if success:
            return True, chunk, attempts

    return False, b'', attempts


def build_ssh_command(
    *,
    host: str,
    user: str,
    password: str,
    port: str,
    command: str,
) -> list[str]:
    """构造单条远端 shell 命令。"""
    return build_ssh_prefix(host, user, password, port) + [command]


def run_remote_command(
    *,
    host: str,
    user: str,
    password: str,
    port: str,
    command: str,
    timeout: float,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """执行远端命令，可选落本地日志。"""
    cmd = build_ssh_command(
        host=host,
        user=user,
        password=password,
        port=port,
        command=command,
    )
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('w', encoding='utf-8') as handle:
            handle.write(f'$ {shlex.join(cmd)}\n')
            if result.stdout:
                handle.write('\n[stdout]\n')
                handle.write(result.stdout)
            if result.stderr:
                handle.write('\n[stderr]\n')
                handle.write(result.stderr)
    return result


def upload_remote_file(
    *,
    host: str,
    user: str,
    password: str,
    port: str,
    local_path: Path,
    remote_path: str,
    timeout: float = 60.0,
) -> None:
    """上传本地文件到板端。"""
    cmd = build_scp_prefix(host, user, password, port) + [
        str(local_path),
        f'{user}@{host}:{remote_path}',
    ]
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'上传远端文件失败: {local_path} -> {remote_path}\n'
            f'stdout={result.stdout[-400:]}\n'
            f'stderr={result.stderr[-400:]}'
        )


def fetch_remote_file(
    *,
    host: str,
    user: str,
    password: str,
    port: str,
    remote_path: str,
    local_path: Path,
    timeout: float = 60.0,
) -> None:
    """抓取远端文件到本地。"""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_scp_prefix(host, user, password, port) + [
        f'{user}@{host}:{remote_path}',
        str(local_path),
    ]
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'抓取远端文件失败: {remote_path} -> {local_path}\n'
            f'stdout={result.stdout[-400:]}\n'
            f'stderr={result.stderr[-400:]}'
        )


def read_log_text(log_path: Path) -> str:
    """读取本地日志文件，不存在时返回空串。"""
    if not log_path.exists():
        return ''
    return log_path.read_text(encoding='utf-8', errors='ignore')


def read_log_tail(log_path: Path, max_lines: int = 40) -> str:
    """读取日志尾部，供错误摘要使用。"""
    text = read_log_text(log_path)
    if not text:
        return ''
    return '\n'.join(text.splitlines()[-max_lines:])


def terminate_process(proc: subprocess.Popen[str]) -> None:
    """尽量温和地终止后台进程。"""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)


def wait_remote_ready(
    log_path: Path,
    proc: subprocess.Popen[str],
    timeout_sec: float,
) -> bool:
    """等待板端 `usrp_tensor_rx_spool` 进入首个 job 的接收态。"""
    deadline = time.time() + timeout_sec
    ready_markers = (
        'spool job 1 等待接收',
        '等待信号',
        '继续使用已启动的 continuous RX 流',
    )
    fail_markers = (
        'No UHD Devices Found',
        'No devices found',
        'LookupError: KeyError',
    )
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        text = read_log_text(log_path)
        if any(marker in text for marker in ready_markers):
            return True
        if any(marker in text for marker in fail_markers):
            return False
        time.sleep(0.2)
    return False


def wait_remote_log_marker_count(
    log_path: Path,
    proc: subprocess.Popen[str],
    timeout_sec: float,
    marker: str,
    min_count: int,
) -> bool:
    """等待远端日志中 marker 出现至少 min_count 次。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = read_log_text(log_path)
        if text.count(marker) >= min_count:
            return True
        if proc.poll() is not None and text.count(marker) < min_count:
            return False
        time.sleep(0.2)
    return False


def wait_remote_job_terminal(
    log_path: Path,
    proc: subprocess.Popen[str],
    timeout_sec: float,
    complete_marker: str,
    fail_marker: str,
    *,
    start_offset: int = 0,
    extra_fail_markers: tuple[str, ...] = (),
) -> str:
    """等待远端单个 spool job 进入完成/失败终态。"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = read_log_text(log_path)
        segment = text[start_offset:]
        if complete_marker in segment:
            return 'complete'
        if fail_marker in segment:
            return 'fail'
        if extra_fail_markers and any(marker in segment for marker in extra_fail_markers):
            return 'fail'
        if proc.poll() is not None:
            return 'exited'
        time.sleep(0.2)
    return 'timeout'


def cleanup_remote_spool(args: argparse.Namespace, remote_spool_dir: str) -> None:
    """清理板端 spool 临时目录，并回收绑在该 spool-dir 上的 RX 进程。"""
    spool_arg = shlex.quote(f'--spool-dir {remote_spool_dir}')
    run_remote_command(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        port=args.board_port,
        command=(
            'pids=$(ps -eo pid=,args= | '
            "grep -F 'usrp_tensor_rx_spool' | "
            f'grep -F -- {spool_arg} | '
            "awk '{print $1}'); "
            'if [ -n "$pids" ]; then '
            'kill $pids >/dev/null 2>&1 || true; '
            'sleep 1; '
            'kill -9 $pids >/dev/null 2>&1 || true; '
            'fi; '
            f'rm -rf {shlex.quote(remote_spool_dir)}'
        ),
        timeout=20.0,
    )


SPOOL_GENERIC_FAIL_MARKERS: tuple[str, ...] = (
    '首帧搜索超时',
    '首帧搜索超时后未收到任何数据',
    '未收到任何数据',
    'payload 未收齐',
)


def build_spool_tx_cmd(
    *,
    tx_bin: Path,
    wire_payload_path: Path,
    args: argparse.Namespace,
    profile: dict[str, str],
) -> list[str]:
    """构造本地 `usrp_tensor_tx` 命令，供 `rx_spool` 路径使用。"""
    return [
        str(tx_bin),
        '--file', str(wire_payload_path),
        '--args', str(args.local_serial_args),
        '--rate', str(float(profile['rate'])),
        '--freq', str(float(args.freq)),
        '--gain', str(float(profile['tx_gain'])),
        '--repeat', str(int(profile['repeat'])),
        '--frame-repeat', str(int(profile['frame_repeat'])),
        '--start-pad-samps', str(int(profile['start_pad'])),
        '--round-gap-ms', str(int(profile['round_gap_ms'])),
        '--warmup-frames', str(int(profile['warmup_frames'])),
        '--warmup-repeats', str(int(profile['warmup_repeats'])),
        '--warmup-rounds', str(int(profile['warmup_rounds'])),
        '--tail-pad-samps', str(int(profile['tail_pad_samps'])),
        '--first-frame-extra-repeats', str(int(profile['first_frame_extra_repeats'])),
        '--last-frame-extra-repeats', str(int(profile['last_frame_extra_repeats'])),
        '--frame-order', str(profile['frame_order']),
    ]


def build_profile_without_inline_warmup(profile: dict[str, str]) -> dict[str, str]:
    """返回关闭 inline warmup 后的正式 TX profile。"""
    output = dict(profile)
    output.update({
        'warmup_frames': '0',
        'warmup_repeats': '0',
        'warmup_rounds': '0',
    })
    return output


def build_separate_tx_warmup_profile(profile: dict[str, str]) -> dict[str, str]:
    """构造独立 TX 热机使用的轻量 profile。"""
    output = build_profile_without_inline_warmup(profile)
    output.update({
        'repeat': '1',
        'frame_repeat': '1',
        'start_pad': '0',
        'round_gap_ms': '0',
        'tail_pad_samps': '0',
        'first_frame_extra_repeats': '0',
        'last_frame_extra_repeats': '0',
        'frame_order': 'normal',
    })
    return output


def write_tx_warmup_payload(
    *,
    payload: bytes,
    target_path: Path,
    max_bytes: int,
) -> int:
    """写出独立 TX 热机使用的小 payload。"""
    if max_bytes <= 0:
        raise ValueError('tx_warmup_bytes 必须大于 0')
    warmup_payload = payload[:max_bytes] if len(payload) > max_bytes else payload
    if not warmup_payload:
        raise ValueError('热机 payload 不能为空')
    target_path.write_bytes(warmup_payload)
    return len(warmup_payload)


def run_separate_tx_warmup(
    *,
    tx_bin: Path,
    payload: bytes,
    target_path: Path,
    log_path: Path,
    args: argparse.Namespace,
    base_profile: dict[str, str],
    label: str,
) -> dict[str, object]:
    """执行独立 TX 热机，不让 remote RX / decode 消耗热机事务。"""
    warmup_profile = build_separate_tx_warmup_profile(base_profile)
    payload_bytes = write_tx_warmup_payload(
        payload=payload,
        target_path=target_path,
        max_bytes=int(args.tx_warmup_bytes),
    )
    print(f'[{label}] 本地 TX 预热（与收发/解码流程解耦）', flush=True)
    warmup_cmd = build_spool_tx_cmd(
        tx_bin=tx_bin,
        wire_payload_path=target_path,
        args=args,
        profile=warmup_profile,
    )
    started = time.perf_counter()
    with log_path.open('w', encoding='utf-8') as warmup_handle:
        warmup_result = subprocess.run(
            warmup_cmd,
            stdout=warmup_handle,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60.0,
        )
    wall_sec = time.perf_counter() - started
    if warmup_result.returncode != 0:
        raise RuntimeError(f'本地 TX 预热失败: rc={warmup_result.returncode}')
    if args.tx_warmup_settle_sec > 0:
        time.sleep(args.tx_warmup_settle_sec)
    return {
        'enabled': True,
        'payload_bytes': payload_bytes,
        'wall_sec': round(wall_sec, 6),
        'settle_sec': float(args.tx_warmup_settle_sec),
        'log_path': str(log_path),
        'profile': warmup_profile,
    }


def recover_plain_chunk_from_wire(
    wire_chunk: bytes,
    *,
    whitening_enabled: bool,
    whitening_seed: int,
) -> bytes:
    """从单个 wire chunk 恢复明文 chunk。"""
    if not whitening_enabled:
        return wire_chunk
    return whiten_bytes(wire_chunk, int(whitening_seed))


def run_ota_spool_arq(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    chunk_plan: list[tuple[int, bytes]],
    received_wire_path: Path,
    profile: dict[str, str],
    max_attempts: int,
    whitening_enabled: bool,
    whitening_seed: int,
) -> tuple[bool, bytes, bytes, dict[str, object]]:
    """基于 continuous RX + spool 的 chunk 级选择性重传实验线。"""
    tx_bin = REPO_ROOT / 'usrp_tensor' / 'build' / 'usrp_tensor_tx'
    if not tx_bin.exists():
        raise FileNotFoundError(f'找不到本地 TX: {tx_bin}')

    remote_build_dir = args.remote_build_dir
    if remote_build_dir == DEFAULT_REMOTE_BUILD_DIR:
        remote_build_dir = DEFAULT_REMOTE_SPOOL_BUILD_DIR

    logical_chunk_count = len(chunk_plan)
    max_remote_jobs = max(1, logical_chunk_count * max_attempts)
    # 首帧搜索超时：给 RX 充裕时间锁定 preamble + CFO
    # repeat=1 时空口窗口短，需要更长的搜索窗口
    initial_search_timeout = max(
        25.0,
        float(profile['no_frame_timeout']) * 1.5,
    )
    effective_remote_kill_after = max(
        float(args.remote_kill_after),
        float(max_remote_jobs) * max(float(args.rx_timeout), 45.0) + 30.0,
    )
    remote_spool_dir = f'/tmp/usrp_rx_spool_arq_{run_dir.name}'
    remote_log = run_dir / 'remote_rx_arq.log'
    tx_logs_dir = run_dir / 'tx_logs_arq'
    chunk_inputs_dir = run_dir / 'chunks' / 'spool_arq_tx'
    received_jobs_dir = run_dir / 'received_wire' / 'spool_arq'
    tx_logs_dir.mkdir(parents=True, exist_ok=True)
    chunk_inputs_dir.mkdir(parents=True, exist_ok=True)
    received_jobs_dir.mkdir(parents=True, exist_ok=True)

    formal_profile = (
        build_profile_without_inline_warmup(profile)
        if args.separate_tx_warmup
        else dict(profile)
    )
    warmup_metrics: dict[str, object] = {'enabled': False}
    if args.separate_tx_warmup and chunk_plan:
        warmup_wire_chunk, _ = build_wire_chunk(
            chunk_plan[0][1],
            chunk_index=0,
            whitening_enabled=whitening_enabled,
            whitening_seed=whitening_seed,
        )
        warmup_metrics = run_separate_tx_warmup(
            tx_bin=tx_bin,
            payload=warmup_wire_chunk,
            target_path=chunk_inputs_dir / 'warmup.bin',
            log_path=tx_logs_dir / 'warmup.log',
            args=args,
            base_profile=formal_profile,
            label='Spool ARQ',
        )

    remote_cmd = (
        f'mkdir -p {shlex.quote(remote_spool_dir)} && '
        f'rm -f {remote_spool_dir}/rx_*.bin && '
        f'cd {shlex.quote(remote_build_dir)} && '
        f'timeout {effective_remote_kill_after:.1f}s '
        f'./usrp_tensor_rx_spool '
        f'--spool-dir {shlex.quote(remote_spool_dir)} '
        f'--spool-prefix rx '
        f'--max-jobs {max_remote_jobs} '
        f'--spool-advance-on-fail '
        f'--args {shlex.quote(args.remote_serial_args)} '
        f'--rate {float(profile["rate"])} '
        f'--freq {float(args.freq)} '
        f'--gain {float(profile["rx_gain"])} '
        f'--ant {shlex.quote(args.remote_rx_ant)} '
        f'--spb {int(profile["spb"])} '
        f'--setup {float(profile["setup"])} '
        f'--timeout {float(profile["no_frame_timeout"])} '
        f'--initial-search-timeout {initial_search_timeout} '
        f'--decode-workers {int(profile["decode_workers"])} '
        f'--payload-search-order {shlex.quote(profile["payload_search_order"])}'
    )

    cleanup_remote_spool(args, remote_spool_dir)
    remote_started = time.perf_counter()
    with remote_log.open('w', encoding='utf-8') as log_handle:
        remote_proc = subprocess.Popen(
            build_ssh_prefix(args.board_host, args.board_user, args.board_pass, args.board_port) + [remote_cmd],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

    wait_signal_marker = '[RX] 等待信号 ... (Ctrl+C 停止)'
    wait_signal_seen = read_log_text(remote_log).count(wait_signal_marker)
    current_remote_job_index = 1
    remote_jobs_consumed = 0
    total_attempts = 0
    retry_attempts = 0
    job_results: list[dict[str, object]] = []
    received_wire_parts: list[bytes] = []
    received_plain_parts: list[bytes] = []
    all_ok = True

    try:
        ready_timeout = min(
            max(float(formal_profile['wait']) + 20.0, 30.0),
            max(45.0, float(args.rx_timeout)),
        )
        if not wait_remote_ready(remote_log, remote_proc, ready_timeout):
            raise RuntimeError(
                'remote RX spool_arq 未在时限内就绪\n'
                f'{read_log_tail(remote_log)}'
            )

        if float(formal_profile['wait']) > 0:
            time.sleep(float(formal_profile['wait']))

        for chunk_index, (offset, chunk) in enumerate(chunk_plan):
            wire_chunk, wire_seed = build_wire_chunk(
                chunk,
                chunk_index=chunk_index,
                whitening_enabled=whitening_enabled,
                whitening_seed=whitening_seed,
            )
            chunk_input_path = chunk_inputs_dir / f'chunk_{chunk_index:06d}.bin'
            chunk_input_path.write_bytes(wire_chunk)
            logical_success = False

            for attempt_index in range(1, max_attempts + 1):
                if attempt_index > 1:
                    retry_attempts += 1
                remote_job_index = current_remote_job_index
                if remote_job_index > max_remote_jobs:
                    all_ok = False
                    job_results.append({
                        'chunk_index': chunk_index,
                        'remote_job_index': remote_job_index,
                        'attempt_index': attempt_index,
                        'success': False,
                        'stage': 'budget_exhausted',
                        'message': 'spool max-jobs 已耗尽',
                    })
                    break

                if remote_job_index > 1 or attempt_index > 1:
                    target_wait_count = wait_signal_seen + 1
                    wait_ok = wait_remote_log_marker_count(
                        remote_log,
                        remote_proc,
                        float(args.rx_timeout),
                        wait_signal_marker,
                        target_wait_count,
                    )
                    if not wait_ok:
                        all_ok = False
                        job_results.append({
                            'chunk_index': chunk_index,
                            'offset': offset,
                            'length': len(chunk),
                            'remote_job_index': remote_job_index,
                            'attempt_index': attempt_index,
                            'success': False,
                            'stage': 'remote_wait_signal',
                            'message': f'未等到第 {target_wait_count} 次等待信号',
                        })
                        print(
                            f'[Spool ARQ Chunk {chunk_index + 1}/{logical_chunk_count}] '
                            'FAIL wait-signal timeout',
                            flush=True,
                        )
                        break
                    wait_signal_seen = target_wait_count
                    if args.ready_settle_sec > 0:
                        time.sleep(args.ready_settle_sec)

                local_tx_log = tx_logs_dir / (
                    f'chunk_{chunk_index:06d}_job_{remote_job_index:06d}_'
                    f'attempt_{attempt_index:02d}.log'
                )
                print(
                    f'[Spool ARQ Chunk {chunk_index + 1}/{logical_chunk_count}] '
                    f'[Remote Job {remote_job_index}] '
                    f'offset={offset} len={len(chunk)}B '
                    f'attempt={attempt_index}/{max_attempts}',
                    flush=True,
                )

                terminal_wait_offset = len(read_log_text(remote_log))
                tx_started = time.perf_counter()
                tx_cmd = build_spool_tx_cmd(
                    tx_bin=tx_bin,
                    wire_payload_path=chunk_input_path,
                    args=args,
                    profile=formal_profile,
                )
                with local_tx_log.open('w', encoding='utf-8') as tx_log_handle:
                    tx_result = subprocess.run(
                        tx_cmd,
                        stdout=tx_log_handle,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=max(120.0, float(args.rx_timeout)),
                    )
                tx_wall_sec = time.perf_counter() - tx_started
                total_attempts += 1

                if tx_result.returncode != 0:
                    all_ok = False
                    job_results.append({
                        'chunk_index': chunk_index,
                        'offset': offset,
                        'length': len(chunk),
                        'remote_job_index': remote_job_index,
                        'attempt_index': attempt_index,
                        'success': False,
                        'stage': 'local_tx',
                        'message': f'local TX rc={tx_result.returncode}',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}] '
                        f'FAIL local tx rc={tx_result.returncode}',
                        flush=True,
                    )
                    break

                complete_marker = f'spool job {remote_job_index} 完成'
                fail_marker = f'spool job {remote_job_index} 失败:'
                terminal_state = wait_remote_job_terminal(
                    remote_log,
                    remote_proc,
                    float(args.rx_timeout),
                    complete_marker,
                    fail_marker,
                    start_offset=terminal_wait_offset,
                    extra_fail_markers=SPOOL_GENERIC_FAIL_MARKERS,
                )

                if terminal_state == 'fail':
                    current_remote_job_index += 1
                    remote_jobs_consumed += 1
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}] '
                        f'[Remote Job {remote_job_index}] remote fail marker',
                        flush=True,
                    )
                    if attempt_index < max_attempts:
                        continue
                    all_ok = False
                    job_results.append({
                        'chunk_index': chunk_index,
                        'offset': offset,
                        'length': len(chunk),
                        'remote_job_index': remote_job_index,
                        'attempt_index': attempt_index,
                        'success': False,
                        'stage': 'remote_fail',
                        'message': 'remote RX 明确报告该 chunk 失败',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    break

                if terminal_state == 'timeout':
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}] '
                        f'[Remote Job {remote_job_index}] remote wait timeout',
                        flush=True,
                    )
                    all_ok = False
                    job_results.append({
                        'chunk_index': chunk_index,
                        'offset': offset,
                        'length': len(chunk),
                        'remote_job_index': remote_job_index,
                        'attempt_index': attempt_index,
                        'success': False,
                        'stage': 'remote_wait',
                        'message': '等待 remote job 完成超时',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    break

                if terminal_state != 'complete':
                    all_ok = False
                    job_results.append({
                        'chunk_index': chunk_index,
                        'offset': offset,
                        'length': len(chunk),
                        'remote_job_index': remote_job_index,
                        'attempt_index': attempt_index,
                        'success': False,
                        'stage': 'remote_wait',
                        'message': f'terminal_state={terminal_state}',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}] '
                        f'[Remote Job {remote_job_index}] FAIL terminal={terminal_state}',
                        flush=True,
                    )
                    break

                remote_output = f'{remote_spool_dir}/rx_{remote_job_index:06d}.bin'
                job_received_path = received_jobs_dir / f'job_{remote_job_index:06d}.bin'
                try:
                    fetch_remote_file(
                        host=args.board_host,
                        user=args.board_user,
                        password=args.board_pass,
                        port=args.board_port,
                        remote_path=remote_output,
                        local_path=job_received_path,
                        timeout=30.0,
                    )
                except Exception as exc:
                    current_remote_job_index += 1
                    remote_jobs_consumed += 1
                    if attempt_index < max_attempts:
                        job_results.append({
                            'chunk_index': chunk_index,
                            'offset': offset,
                            'length': len(chunk),
                            'remote_job_index': remote_job_index,
                            'attempt_index': attempt_index,
                            'success': False,
                            'stage': 'fetch_retry',
                            'message': str(exc),
                            'tx_wall_sec': round(tx_wall_sec, 6),
                            'local_tx_log': str(local_tx_log),
                        })
                        continue
                    all_ok = False
                    job_results.append({
                        'chunk_index': chunk_index,
                        'offset': offset,
                        'length': len(chunk),
                        'remote_job_index': remote_job_index,
                        'attempt_index': attempt_index,
                        'success': False,
                        'stage': 'fetch',
                        'message': str(exc),
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}] '
                        f'[Remote Job {remote_job_index}] FAIL fetch',
                        flush=True,
                    )
                    break

                received_wire_chunk = job_received_path.read_bytes()
                received_plain_chunk = recover_plain_chunk_from_wire(
                    received_wire_chunk,
                    whitening_enabled=whitening_enabled,
                    whitening_seed=wire_seed,
                )
                wire_match = (received_wire_chunk == wire_chunk)
                plain_match = (received_plain_chunk == chunk)

                job_record = {
                    'chunk_index': chunk_index,
                    'offset': offset,
                    'length': len(chunk),
                    'remote_job_index': remote_job_index,
                    'attempt_index': attempt_index,
                    'success': bool(wire_match and plain_match),
                    'wire_match': bool(wire_match),
                    'plain_match': bool(plain_match),
                    'tx_wall_sec': round(tx_wall_sec, 6),
                    'received_wire_size': len(received_wire_chunk),
                    'received_plain_size': len(received_plain_chunk),
                    'whitening_enabled': bool(whitening_enabled),
                    'whitening_seed': int(wire_seed),
                    'local_tx_log': str(local_tx_log),
                }

                if wire_match and plain_match:
                    received_wire_parts.append(received_wire_chunk)
                    received_plain_parts.append(received_plain_chunk)
                    current_remote_job_index += 1
                    remote_jobs_consumed += 1
                    logical_success = True
                    job_results.append(job_record)
                    chunk_elapsed = time.perf_counter() - remote_started
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}/{logical_chunk_count}] '
                        f'PASS attempt={attempt_index}/{max_attempts} '
                        f'tx_wall={tx_wall_sec:.3f}s '
                        f'elapsed={chunk_elapsed:.1f}s '
                        f'jobs={remote_jobs_consumed}/{max_remote_jobs}',
                        flush=True,
                    )
                    break

                current_remote_job_index += 1
                remote_jobs_consumed += 1
                if attempt_index < max_attempts:
                    job_record['stage'] = 'mismatch_retry'
                    job_results.append(job_record)
                    print(
                        f'[Spool ARQ Chunk {chunk_index + 1}] '
                        f'RETRY attempt={attempt_index}/{max_attempts} '
                        f'(wire={wire_match} plain={plain_match} '
                        f'recv={len(received_wire_chunk)}B sent={len(wire_chunk)}B)',
                        flush=True,
                    )
                    continue

                all_ok = False
                job_record['stage'] = 'mismatch'
                job_results.append(job_record)
                print(
                    f'[Spool ARQ Chunk {chunk_index + 1}] '
                    f'[Remote Job {remote_job_index}] FAIL mismatch',
                    flush=True,
                )
                break

            if not logical_success:
                all_ok = False
                break

        remote_wall_sec = time.perf_counter() - remote_started
        received_wire_final = b''.join(received_wire_parts)
        received_plain_final = b''.join(received_plain_parts)
        received_wire_path.write_bytes(received_wire_final)

        ota_metrics = {
            'transport': 'spool_arq',
            'logical_chunk_count': logical_chunk_count,
            'chunk_bytes': args.chunk_bytes,
            'max_attempts': max_attempts,
            'total_attempts': total_attempts,
            'retry_attempts': retry_attempts,
            'remote_jobs_consumed': remote_jobs_consumed,
            'max_remote_jobs': max_remote_jobs,
            'initial_search_timeout': round(initial_search_timeout, 6),
            'effective_remote_kill_after': round(effective_remote_kill_after, 6),
            'formal_tx_profile': formal_profile,
            'separate_tx_warmup': warmup_metrics,
            'remote_wall_sec': round(remote_wall_sec, 6),
            'remote_log': str(remote_log),
            'tx_logs_dir': str(tx_logs_dir),
            'remote_spool_dir': remote_spool_dir,
            'remote_build_dir': remote_build_dir,
            'pass_count': len(received_plain_parts),
            'fail_count': sum(1 for r in job_results if not r.get('success')),
            'job_results': job_results,
            'received_wire_size': len(received_wire_final),
            'ota_ok': bool(
                all_ok
                and len(received_plain_parts) == logical_chunk_count
            ),
        }
        return (
            bool(all_ok and len(received_plain_parts) == logical_chunk_count),
            received_wire_final,
            received_plain_final,
            ota_metrics,
        )
    finally:
        terminate_process(remote_proc)
        cleanup_remote_spool(args, remote_spool_dir)


def run_ota_copy(
    *,
    wire_payload_path: Path,
    received_wire_path: Path,
    wire_manifest: list[dict[str, object]],
    source_bytes: bytes,
) -> tuple[bool, bytes, bytes, dict[str, object]]:
    """跳过无线传输，直接复制 wire payload，验证重建主链路。"""
    started = time.perf_counter()
    received_wire = wire_payload_path.read_bytes()
    received_wire_path.write_bytes(received_wire)
    received_plain = recover_payload_from_wire(
        received_wire,
        wire_manifest=wire_manifest,
    )
    wall_sec = time.perf_counter() - started
    ota_metrics = {
        'transport': 'copy',
        'tx_wall_sec': 0.0,
        'remote_wall_sec': round(wall_sec, 6),
        'received_wire_size': len(received_wire),
        'wire_match': True,
        'ota_ok': bool(received_plain == source_bytes),
    }
    return bool(received_plain == source_bytes), received_wire, received_plain, ota_metrics


def run_ota_spool(
    *,
    args: argparse.Namespace,
    run_dir: Path,
    wire_payload_path: Path,
    received_wire_path: Path,
    wire_manifest: list[dict[str, object]],
    source_bytes: bytes,
    profile: dict[str, str],
    spool_count: int = 1,
    max_attempts: int = 2,
) -> tuple[bool, bytes, bytes, dict[str, object]]:
    """使用 `usrp_tensor_rx_spool` 完成多图 OTA 收发（支持重试 + 可选 TVM）。

    spool_count=1 时行为与旧版一致（单图）。
    spool_count>1 时 RX 持续运行，本地逐 job 发 TX，每个 job 支持重试。
    成功后可选调用 TVM 重建。
    """
    tx_bin = REPO_ROOT / 'usrp_tensor' / 'build' / 'usrp_tensor_tx'
    if not tx_bin.exists():
        raise FileNotFoundError(f'找不到本地 TX: {tx_bin}')

    remote_build_dir = args.remote_build_dir
    if remote_build_dir == DEFAULT_REMOTE_BUILD_DIR:
        remote_build_dir = DEFAULT_REMOTE_SPOOL_BUILD_DIR

    formal_profile = (
        build_profile_without_inline_warmup(profile)
        if args.separate_tx_warmup
        else dict(profile)
    )
    remote_spool_dir = f'/tmp/usrp_rx_spool_demo_{run_dir.name}'
    remote_log = run_dir / 'remote_rx.log'
    tx_logs_dir = run_dir / 'tx_logs'
    tx_logs_dir.mkdir(parents=True, exist_ok=True)
    warmup_metrics: dict[str, object] = {'enabled': False}
    if args.separate_tx_warmup:
        warmup_metrics = run_separate_tx_warmup(
            tx_bin=tx_bin,
            payload=wire_payload_path.read_bytes(),
            target_path=tx_logs_dir / 'warmup.bin',
            log_path=tx_logs_dir / 'warmup.log',
            args=args,
            base_profile=formal_profile,
            label='Spool',
        )
    remote_cmd = (
        f'mkdir -p {shlex.quote(remote_spool_dir)} && '
        f'rm -f {remote_spool_dir}/rx_*.bin && '
        f'cd {shlex.quote(remote_build_dir)} && '
        f'timeout {float(args.remote_kill_after):.1f}s '
        f'./usrp_tensor_rx_spool '
        f'--spool-dir {shlex.quote(remote_spool_dir)} '
        f'--spool-prefix rx '
        f'--max-jobs {spool_count} '
        f'--args {shlex.quote(args.remote_serial_args)} '
        f'--rate {float(formal_profile["rate"])} '
        f'--freq {float(args.freq)} '
        f'--gain {float(formal_profile["rx_gain"])} '
        f'--ant {shlex.quote(args.remote_rx_ant)} '
        f'--spb {int(formal_profile["spb"])} '
        f'--setup {float(formal_profile["setup"])} '
        f'--timeout {float(formal_profile["no_frame_timeout"])} '
        f'--decode-workers {int(formal_profile["decode_workers"])} '
        f'--payload-search-order {shlex.quote(formal_profile["payload_search_order"])}'
    )

    cleanup_remote_spool(args, remote_spool_dir)
    remote_started = time.perf_counter()
    with remote_log.open('w', encoding='utf-8') as log_handle:
        remote_proc = subprocess.Popen(
            build_ssh_prefix(args.board_host, args.board_user, args.board_pass, args.board_port) + [remote_cmd],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

    job_results: list[dict[str, object]] = []
    all_ok = True
    tvm_results: list[dict[str, object]] = []
    tx_wall_total = 0.0
    wait_signal_marker = '[RX] 等待信号 ... (Ctrl+C 停止)'
    wait_signal_seen = read_log_text(remote_log).count(wait_signal_marker)

    try:
        ready_timeout = min(max(float(formal_profile['wait']) + 8.0, 12.0), max(20.0, float(args.rx_timeout)))
        if not wait_remote_ready(remote_log, remote_proc, ready_timeout):
            raise RuntimeError(
                'remote RX spool 未在时限内就绪\n'
                f'{read_log_tail(remote_log)}'
            )

        if float(formal_profile['wait']) > 0:
            time.sleep(float(formal_profile['wait']))

        # ── 多 job 循环 ──
        for job_index in range(1, spool_count + 1):
            complete_marker = f'spool job {job_index} 完成'
            fail_marker = f'spool job {job_index} 失败:'
            job_success = False

            for attempt_index in range(1, max_attempts + 1):
                # 后续 job 或重试：等待 RX 回到等待信号状态
                if job_index > 1 or attempt_index > 1:
                    target_wait_count = wait_signal_seen + 1
                    wait_ok = wait_remote_log_marker_count(
                        remote_log, remote_proc,
                        float(args.rx_timeout),
                        wait_signal_marker,
                        target_wait_count,
                    )
                    if not wait_ok:
                        all_ok = False
                        job_results.append({
                            'job_index': job_index,
                            'attempt_count': attempt_index,
                            'success': False,
                            'stage': 'remote_wait_signal',
                            'message': f'未等到第 {target_wait_count} 次等待信号',
                        })
                        print(
                            f'[Spool Job {job_index}/{spool_count}] '
                            f'FAIL wait-signal timeout',
                            flush=True,
                        )
                        break
                    wait_signal_seen = target_wait_count
                    if args.ready_settle_sec > 0:
                        time.sleep(args.ready_settle_sec)

                local_tx_log = tx_logs_dir / f'local_tx_{job_index:06d}_attempt_{attempt_index:02d}.log'
                print(
                    f'[Spool Job {job_index}/{spool_count}] '
                    f'[Attempt {attempt_index}/{max_attempts}] 本地 TX 发送',
                    flush=True,
                )

                terminal_wait_offset = len(read_log_text(remote_log))
                tx_started = time.perf_counter()
                tx_cmd = build_spool_tx_cmd(
                    tx_bin=tx_bin,
                    wire_payload_path=wire_payload_path,
                    args=args,
                    profile=formal_profile,
                )
                with local_tx_log.open('w', encoding='utf-8') as tx_log_handle:
                    tx_result = subprocess.run(
                        tx_cmd,
                        stdout=tx_log_handle,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=max(120.0, float(args.rx_timeout)),
                    )
                tx_wall_sec = time.perf_counter() - tx_started
                tx_wall_total += tx_wall_sec

                if tx_result.returncode != 0:
                    all_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'local_tx',
                        'message': f'local TX rc={tx_result.returncode}',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    print(
                        f'[Spool Job {job_index}] FAIL local tx rc={tx_result.returncode}',
                        flush=True,
                    )
                    break

                terminal_state = wait_remote_job_terminal(
                    remote_log, remote_proc,
                    float(args.rx_timeout),
                    complete_marker, fail_marker,
                    start_offset=terminal_wait_offset,
                    extra_fail_markers=SPOOL_GENERIC_FAIL_MARKERS,
                )
                if terminal_state == 'fail':
                    print(
                        f'[Spool Job {job_index}][Attempt {attempt_index}] remote fail marker',
                        flush=True,
                    )
                    if attempt_index < max_attempts:
                        continue
                    all_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'remote_fail',
                        'message': 'remote RX 明确报告该 job 失败',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    break
                if terminal_state != 'complete':
                    all_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'remote_wait',
                        'message': f'terminal_state={terminal_state}',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                    })
                    print(
                        f'[Spool Job {job_index}] FAIL terminal={terminal_state}',
                        flush=True,
                    )
                    break

                # 抓回远端输出
                remote_output = f'{remote_spool_dir}/rx_{job_index:06d}.bin'
                job_received_path = run_dir / 'received_wire' / f'job_{job_index:06d}.bin'
                job_received_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fetch_remote_file(
                        host=args.board_host,
                        user=args.board_user,
                        password=args.board_pass,
                        port=args.board_port,
                        remote_path=remote_output,
                        local_path=job_received_path,
                        timeout=30.0,
                    )
                except Exception as exc:
                    all_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'fetch',
                        'message': str(exc),
                        'tx_wall_sec': round(tx_wall_sec, 6),
                    })
                    print(f'[Spool Job {job_index}] FAIL fetch', flush=True)
                    break

                received_wire = job_received_path.read_bytes()
                try:
                    received_plain = recover_payload_from_wire(
                        received_wire, wire_manifest=wire_manifest,
                    )
                except Exception as exc:
                    all_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'recover',
                        'message': str(exc),
                        'tx_wall_sec': round(tx_wall_sec, 6),
                    })
                    print(f'[Spool Job {job_index}] FAIL recover', flush=True)
                    break

                wire_match = (received_wire == wire_payload_path.read_bytes())
                sha_match = (received_plain == source_bytes)
                job_results.append({
                    'job_index': job_index,
                    'attempt_count': attempt_index,
                    'success': bool(sha_match),
                    'wire_match': bool(wire_match),
                    'sha_match': bool(sha_match),
                    'tx_wall_sec': round(tx_wall_sec, 6),
                    'received_wire_size': len(received_wire),
                    'received_plain_size': len(received_plain),
                    'local_tx_log': str(local_tx_log),
                })
                print(
                    f'[Spool Job {job_index}/{spool_count}] '
                    f'{"PASS" if sha_match else "FAIL"} '
                    f'wire={wire_match} sha={sha_match} '
                    f'tx_wall={tx_wall_sec:.3f}s attempt={attempt_index}',
                    flush=True,
                )
                if not sha_match:
                    all_ok = False
                    break
                job_success = True
                break

            if not job_success:
                break

        remote_wall_sec = time.perf_counter() - remote_started
        remote_proc.wait(timeout=min(20.0, float(args.rx_timeout)))

        # 单图兼容：写入 received_wire_path
        if spool_count == 1 and job_results:
            first = job_results[0]
            if first.get('success'):
                first_path = run_dir / 'received_wire' / 'job_000001.bin'
                if first_path.exists():
                    shutil.copy2(first_path, received_wire_path)

        # 收集最终 received_plain（取最后一个成功的）
        last_ok_result = None
        for r in job_results:
            if r.get('success'):
                last_ok_result = r
        received_wire_final = b''
        received_plain_final = b''
        if last_ok_result:
            last_path = run_dir / 'received_wire' / f'job_{last_ok_result["job_index"]:06d}.bin'
            if last_path.exists():
                received_wire_final = last_path.read_bytes()
                received_plain_final = recover_payload_from_wire(
                    received_wire_final, wire_manifest=wire_manifest,
                )

        ota_metrics = {
            'transport': 'spool',
            'spool_count': spool_count,
            'max_attempts': max_attempts,
            'tx_wall_total_sec': round(tx_wall_total, 6),
            'formal_tx_profile': formal_profile,
            'separate_tx_warmup': warmup_metrics,
            'remote_wall_sec': round(remote_wall_sec, 6),
            'remote_log': str(remote_log),
            'tx_logs_dir': str(tx_logs_dir),
            'remote_spool_dir': remote_spool_dir,
            'remote_build_dir': remote_build_dir,
            'pass_count': sum(1 for r in job_results if r.get('success')),
            'fail_count': sum(1 for r in job_results if not r.get('success')),
            'job_results': job_results,
            'received_wire_size': len(received_wire_final),
            'wire_match': bool(received_wire_final and received_wire_final == wire_payload_path.read_bytes()),
            'ota_ok': bool(received_plain_final == source_bytes),
        }
        return all_ok, received_wire_final, received_plain_final, ota_metrics
    finally:
        terminate_process(remote_proc)
        cleanup_remote_spool(args, remote_spool_dir)


def ensure_remote_dir(args: argparse.Namespace, remote_dir: str, log_path: Path) -> None:
    """确保远端目录存在。"""
    command = f'mkdir -p {shlex.quote(remote_dir)}'
    result = run_remote_command(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        port=args.board_port,
        command=command,
        timeout=20.0,
        log_path=log_path,
    )
    if result.returncode != 0:
        raise RuntimeError(f'创建远端目录失败: {remote_dir}')


def normalize_image_array(array: np.ndarray) -> np.ndarray:
    """把 TVM 输出数组转成可保存的 uint8 图像。"""
    image = np.asarray(array)
    if image.ndim == 4 and image.shape[0] == 1:
        image = image[0]
    if image.ndim == 3 and image.shape[0] in (1, 3, 4):
        image = np.transpose(image, (1, 2, 0))
    if image.ndim == 3 and image.shape[-1] == 1:
        image = image[..., 0]
    if image.ndim not in (2, 3):
        raise ValueError(f'不支持的输出形状: {image.shape}')

    if np.issubdtype(image.dtype, np.floating):
        image = image.astype(np.float32)
        min_value = float(np.min(image))
        max_value = float(np.max(image))
        if min_value >= 0.0 and max_value <= 1.0 + 1e-6:
            image = image * 255.0
        elif min_value >= -1.0 - 1e-6 and max_value <= 1.0 + 1e-6:
            image = (image + 1.0) * 127.5
        elif min_value < 0.0 or max_value > 255.0:
            if max_value > min_value:
                image = (image - min_value) / (max_value - min_value) * 255.0
            else:
                image = np.zeros_like(image)
    image = np.clip(image, 0.0, 255.0).astype(np.uint8)
    return image


def save_npy_as_png(npy_path: Path, png_path: Path) -> bool:
    """把 `.npy` 重建结果保存为 `.png`。"""
    if Image is None:
        return False
    array = np.load(npy_path)
    image = normalize_image_array(array)
    Image.fromarray(image).save(png_path, format='PNG')
    return True


def run_remote_tvm_inference(
    *,
    args: argparse.Namespace,
    label: str,
    local_input: Path,
    remote_work_dir: str,
    local_result_dir: Path,
    helper_local_path: Path,
) -> RemoteInferenceRecord:
    """上传 latent、远端推理、抓回 `.npy` 结果。"""
    remote_input = f'{remote_work_dir}/{label}.npz'
    remote_output = f'{remote_work_dir}/{label}.npy'
    remote_helper = f'{remote_work_dir}/tvm_inference_helper.py'
    local_output = local_result_dir / f'{label}.npy'
    log_path = local_result_dir / f'{label}.remote.log'

    upload_remote_file(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        port=args.board_port,
        local_path=helper_local_path,
        remote_path=remote_helper,
    )
    upload_remote_file(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        port=args.board_port,
        local_path=local_input,
        remote_path=remote_input,
    )

    env_exports = ' '.join(
        [
            f'export TVM_FFI_DISABLE_TORCH_C_DLPACK=1;',
            f'export LD_LIBRARY_PATH={shlex.quote(args.remote_tvm_ld_library_path)};',
            f'export TVM_LIBRARY_PATH={shlex.quote(args.remote_tvm_library_path)};',
            f'export PYTHONPATH={shlex.quote(args.remote_tvm_pythonpath)};',
        ]
    )
    command = (
        f'{env_exports} '
        f'{shlex.quote(args.remote_tvm_python)} '
        f'{shlex.quote(remote_helper)} '
        f'--artifact-path {shlex.quote(args.remote_tvm_artifact)} '
        f'--input {shlex.quote(remote_input)} '
        f'--output {shlex.quote(remote_output)} '
        f'--snr {args.snr} '
        f'--seed {args.seed}'
    )
    result = run_remote_command(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        port=args.board_port,
        command=command,
        timeout=args.remote_infer_timeout,
        log_path=log_path,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'远端 TVM 推理失败 ({label}): stdout={result.stdout[-400:]} '
            f'stderr={result.stderr[-400:]}'
        )

    try:
        summary = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'远端 TVM 输出解析失败 ({label}): {exc}') from exc
    if str(summary.get('status')) != 'ok':
        raise RuntimeError(f'远端 TVM 返回错误 ({label}): {summary}')

    jscc_awgn_note = str(summary.get('jscc_awgn_note') or '').strip()
    realized_awgn = summary.get('jscc_realized_awgn_snr_db')
    if realized_awgn is None and jscc_awgn_note:
        realized_awgn_text = f'undefined({jscc_awgn_note})'
    else:
        realized_awgn_text = format_snr_text(realized_awgn)
    print(
        f'[TVM {label}] '
        f'jscc_awgn_config_db={summary.get("jscc_configured_awgn_snr_db", summary.get("snr"))} '
        f'jscc_awgn_realized_db={realized_awgn_text}'
    )

    fetch_remote_file(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        port=args.board_port,
        remote_path=remote_output,
        local_path=local_output,
    )
    output_sha = sha256_file(local_output)
    return RemoteInferenceRecord(
        label=label,
        remote_input=remote_input,
        remote_output=remote_output,
        local_output=str(local_output),
        log_path=str(log_path),
        output_sha256=output_sha,
        output_shape=list(summary.get('output_shape') or []),
        output_dtype=str(summary.get('output_dtype') or ''),
        inference_ms=float(summary.get('inference_ms') or 0.0),
        load_ms=float(summary.get('load_ms') or 0.0),
        jscc_configured_awgn_snr_db=float(summary.get('jscc_configured_awgn_snr_db') or summary.get('snr') or 0.0),
        jscc_realized_awgn_snr_db=(
            None if summary.get('jscc_realized_awgn_snr_db') is None
            else float(summary.get('jscc_realized_awgn_snr_db'))
        ),
        jscc_awgn_note=str(summary.get('jscc_awgn_note') or ''),
    )


def maybe_copy_reference_image(reference_image: str, assets_dir: Path) -> str:
    """可选复制参考图。"""
    if not reference_image:
        return ''
    source = Path(reference_image)
    if not source.exists():
        return ''
    target = assets_dir / f'reference{source.suffix.lower()}'
    shutil.copy2(source, target)
    return str(target)


def main() -> int:
    parser = argparse.ArgumentParser(description='真实 33KB latent 的独立 USRP OTA 演示')
    parser.add_argument('--input-latent', default=str(DEFAULT_INPUT_LATENT), help='待发送 latent .npz 路径')
    parser.add_argument('--artifact-root', default=str(DEFAULT_ARTIFACT_ROOT), help='本地演示留档根目录')
    parser.add_argument('--chunk-bytes', type=int, default=DEFAULT_CHUNK_BYTES, help='单个 OTA chunk 最大字节数')
    parser.add_argument('--chunk-attempts', type=int, default=3, help='单个 chunk 最大尝试次数')
    parser.add_argument('--chunk-gap-sec', type=float, default=0.5, help='chunk 成功后额外等待秒数')
    parser.add_argument('--board-host', default='100.121.87.73', help='板端 SSH 地址')
    parser.add_argument('--board-user', default='user', help='板端 SSH 用户名')
    parser.add_argument('--board-pass', default='user', help='板端 SSH 密码')
    parser.add_argument('--board-port', default='22', help='板端 SSH 端口')
    parser.add_argument('--remote-build-dir', default=DEFAULT_REMOTE_BUILD_DIR, help='板端 usrp_tensor build 目录')
    parser.add_argument('--local-serial-args', default='serial=31E74E3', help='本地 TX UHD args')
    parser.add_argument('--remote-serial-args', default='serial=31DDAB3', help='板端 RX UHD args')
    parser.add_argument('--remote-rx-ant', default='TX/RX', help='板端 RX 天线口位')
    parser.add_argument('--freq', type=float, default=915e6, help='射频中心频率')
    parser.add_argument('--rx-timeout', type=float, default=120.0, help='单个 chunk OTA 总等待时限')
    parser.add_argument('--remote-kill-after', type=float, default=150.0, help='板端 RX shell timeout')
    parser.add_argument('--remote-tvm-python', default=DEFAULT_REMOTE_TVM_PYTHON, help='板端 TVM Python 路径')
    parser.add_argument('--remote-tvm-artifact', default=DEFAULT_REMOTE_TVM_ARTIFACT, help='板端 TVM optimized_model.so 路径')
    parser.add_argument('--remote-tvm-ld-library-path', default=DEFAULT_REMOTE_TVM_LD_LIBRARY_PATH, help='板端 TVM LD_LIBRARY_PATH')
    parser.add_argument('--remote-tvm-pythonpath', default=DEFAULT_REMOTE_TVM_PYTHONPATH, help='板端 TVM PYTHONPATH')
    parser.add_argument('--remote-tvm-library-path', default=DEFAULT_REMOTE_TVM_LIBRARY_PATH, help='板端 TVM_LIBRARY_PATH')
    parser.add_argument('--remote-infer-timeout', type=float, default=180.0, help='单次远端推理超时秒数')
    parser.add_argument('--snr', type=float, default=10.0, help='重建时传给 TVM helper 的 JSCC/AWGN 仿真 SNR')
    parser.add_argument('--seed', type=int, default=0, help='远端 TVM helper 随机种子')
    parser.add_argument(
        '--ota-path',
        choices=('daemon', 'single', 'spool', 'spool_arq', 'copy', 'legacy'),
        default='daemon',
        help=(
            'OTA 编排路径：daemon=应用层 chunked-daemon；'
            'single=整图一次 daemon 事务；'
            'spool=continuous rx_spool 单图事务；'
            'spool_arq=continuous rx_spool + chunk 级选择性重传；'
            'copy=跳过无线仅验证重建链路；'
            'legacy=逐 chunk 调用 run_ota()'
        ),
    )
    parser.add_argument('--spool-count', type=int, default=1, help='spool 路径连续收发次数（默认 1 = 单图）')
    parser.add_argument('--spool-max-attempts', type=int, default=2, help='spool 单 job 最大重试次数')
    parser.add_argument('--tvm-skip', action='store_true', help='跳过 TVM 重建步骤，仅验证 OTA 传输')
    parser.add_argument('--ready-settle-sec', type=float, default=0.0, help='spool 多 job 间等待信号就绪后的额外等待秒数')
    parser.add_argument(
        '--separate-tx-warmup',
        action=argparse.BooleanOptionalAction,
        default=None,
        help='在 remote RX 启动前先做一次独立 TX 热机；默认 spool_arq 开启，其余路径关闭',
    )
    parser.add_argument(
        '--tx-warmup-bytes',
        type=int,
        default=DEFAULT_SEPARATE_TX_WARMUP_BYTES,
        help='独立 TX 热机使用的 payload 字节数',
    )
    parser.add_argument(
        '--tx-warmup-settle-sec',
        type=float,
        default=DEFAULT_SEPARATE_TX_WARMUP_SETTLE_SEC,
        help='独立 TX 热机结束后的额外等待秒数',
    )
    parser.add_argument('--no-whitening', action='store_true', help='关闭公开 PRBS chunk whitening')
    parser.add_argument('--whitening-seed', type=int, default=0x6D2B79F5, help='公开 PRBS whitening 基准种子')
    parser.add_argument('--reference-image', default='', help='可选原始输入图路径，用于一起留档')
    add_ota_profile_arguments(parser)
    args = parser.parse_args()
    chunk_bytes_explicit = any(
        item == '--chunk-bytes' or item.startswith('--chunk-bytes=')
        for item in sys.argv[1:]
    )
    if args.ota_path == 'spool_arq' and not chunk_bytes_explicit:
        args.chunk_bytes = DEFAULT_SPOOL_ARQ_CHUNK_BYTES
    if args.separate_tx_warmup is None:
        args.separate_tx_warmup = (args.ota_path == 'spool_arq')
    # spool_arq: 默认给 RX 0.3s settle 时间，避免 AGC 未收敛就发 TX
    if args.ota_path == 'spool_arq' and args.ready_settle_sec == 0.0:
        args.ready_settle_sec = 0.3

    input_latent = Path(args.input_latent)
    if not input_latent.exists():
        raise FileNotFoundError(f'找不到 latent 输入文件: {input_latent}')
    if args.chunk_bytes <= 0:
        raise ValueError('chunk_bytes 必须大于 0')
    if args.chunk_attempts <= 0:
        raise ValueError('chunk_attempts 必须大于 0')
    if args.tx_warmup_bytes <= 0:
        raise ValueError('tx_warmup_bytes 必须大于 0')
    if args.tx_warmup_settle_sec < 0:
        raise ValueError('tx_warmup_settle_sec 不能小于 0')

    run_id = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path(args.artifact_root) / run_id
    chunks_dir = run_dir / 'chunks'
    assets_dir = run_dir / 'assets'
    recon_dir = run_dir / 'reconstruction'
    remote_dir = f'/tmp/usrp_latent_demo_{run_id}'
    chunks_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    recon_dir.mkdir(parents=True, exist_ok=True)

    source_latent = assets_dir / 'source_latent.npz'
    shutil.copy2(input_latent, source_latent)
    source_bytes = source_latent.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    effective_profile = build_effective_ota_profile(args)
    chunk_plan, wire_payload, wire_manifest = build_wire_payload(
        source_bytes,
        app_chunk_bytes=args.chunk_bytes,
        whitening_enabled=not args.no_whitening,
        whitening_seed=args.whitening_seed,
    )
    wire_payload_path = assets_dir / 'wire_payload.bin'
    wire_payload_path.write_bytes(wire_payload)

    print(
        '[Latent] '
        f'source={source_latent} size={len(source_bytes)}B sha256={source_sha} '
        f'chunks={len(chunk_plan)} ota_path={args.ota_path}',
        flush=True,
    )
    for chunk_index, (offset, chunk) in enumerate(chunk_plan):
        print(
            f'  - chunk[{chunk_index}] offset={offset} len={len(chunk)}B '
            f'ota_window={args.chunk_bytes}B',
            flush=True,
        )

    all_attempts: list[ChunkAttemptRecord] = []
    received_plain = b''
    ota_metrics: dict[str, object] = {}
    received_wire_path = assets_dir / 'received_wire.bin'

    if args.ota_path == 'daemon':
        started = time.perf_counter()
        daemon_ok, received_wire, ota_metrics = run_ota_chunked(
            wire_payload,
            chunk_bytes=args.chunk_bytes,
            chunk_retries=max(0, args.chunk_attempts - 1),
            **frozen_chunked_ota_kwargs(args),
        )
        ota_total_wall_sec = time.perf_counter() - started
        ota_metrics = dict(ota_metrics or {})
        ota_metrics['ota_total_wall_sec'] = round(ota_total_wall_sec, 6)
        received_wire_path.write_bytes(received_wire)
        received_plain = recover_payload_from_wire(
            received_wire,
            wire_manifest=wire_manifest,
        )
        if not daemon_ok or received_plain != source_bytes:
            summary = {
                'success': False,
                'stage': 'ota_chunk',
                'ota_path': args.ota_path,
                'source_latent': str(source_latent),
                'source_size': len(source_bytes),
                'source_sha256': source_sha,
                'profile': effective_profile,
                'app_chunk_bytes': args.chunk_bytes,
                'app_chunk_count': len(chunk_plan),
                'wire_payload_size': len(wire_payload),
                'received_wire_size': len(received_wire),
                'received_plain_size': len(received_plain),
                'wire_payload_path': str(wire_payload_path),
                'received_wire_path': str(received_wire_path),
                'chunk_plan': [
                    {'chunk_index': idx, 'offset': off, 'length': len(payload)}
                    for idx, (off, payload) in enumerate(chunk_plan)
                ],
                'wire_manifest': wire_manifest,
                'chunk_attempts': list(ota_metrics.get('job_results') or []),
                'ota_metrics': ota_metrics,
            }
            summary_path = run_dir / 'demo_result.json'
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print()
            print('=' * 60)
            print('[FAIL] daemon latent OTA 未全部成功')
            print(f'  result       : {summary_path}')
            print('=' * 60)
            return 2
    elif args.ota_path == 'single':
        started = time.perf_counter()
        daemon_ok, received_wire, ota_metrics = run_ota_chunked(
            wire_payload,
            chunk_bytes=max(1, len(wire_payload)),
            chunk_retries=0,
            chunk_align_bytes=0,
            **frozen_chunked_ota_kwargs(args),
        )
        ota_total_wall_sec = time.perf_counter() - started
        ota_metrics = dict(ota_metrics or {})
        ota_metrics['ota_total_wall_sec'] = round(ota_total_wall_sec, 6)
        ota_metrics['ota_ok'] = bool(daemon_ok)
        ota_metrics['ota_transaction_count'] = 1
        received_wire_path.write_bytes(received_wire)
        received_plain = recover_payload_from_wire(
            received_wire,
            wire_manifest=wire_manifest,
        )
        if not daemon_ok or received_plain != source_bytes:
            summary = {
                'success': False,
                'stage': 'ota_single',
                'ota_path': args.ota_path,
                'source_latent': str(source_latent),
                'source_size': len(source_bytes),
                'source_sha256': source_sha,
                'profile': effective_profile,
                'app_chunk_bytes': args.chunk_bytes,
                'app_chunk_count': len(chunk_plan),
                'wire_payload_size': len(wire_payload),
                'received_wire_size': len(received_wire),
                'received_plain_size': len(received_plain),
                'wire_payload_path': str(wire_payload_path),
                'received_wire_path': str(received_wire_path),
                'chunk_plan': [
                    {'chunk_index': idx, 'offset': off, 'length': len(payload)}
                    for idx, (off, payload) in enumerate(chunk_plan)
                ],
                'wire_manifest': wire_manifest,
                'chunk_attempts': [],
                'ota_metrics': ota_metrics,
            }
            summary_path = run_dir / 'demo_result.json'
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print()
            print('=' * 60)
            print('[FAIL] single-shot latent OTA 未全部成功')
            print(f'  result       : {summary_path}')
            print('=' * 60)
            return 2
    elif args.ota_path == 'spool':
        received_wire = b''
        received_plain = b''
        try:
            spool_ok, received_wire, received_plain, ota_metrics = run_ota_spool(
                args=args,
                run_dir=run_dir,
                wire_payload_path=wire_payload_path,
                received_wire_path=received_wire_path,
                wire_manifest=wire_manifest,
                source_bytes=source_bytes,
                profile=effective_profile,
                spool_count=args.spool_count,
                max_attempts=args.spool_max_attempts,
            )
        except Exception as exc:
            spool_ok = False
            if received_wire_path.exists():
                received_wire = received_wire_path.read_bytes()
                try:
                    received_plain = recover_payload_from_wire(
                        received_wire,
                        wire_manifest=wire_manifest,
                    )
                except Exception:
                    received_plain = b''
            ota_metrics = {
                'transport': 'spool',
                'error': str(exc),
                'remote_log': str(run_dir / 'remote_rx.log'),
                'tx_logs_dir': str(run_dir / 'tx_logs'),
            }
        if not spool_ok and args.spool_count == 1:
            summary = {
                'success': False,
                'stage': 'ota_spool',
                'ota_path': args.ota_path,
                'source_latent': str(source_latent),
                'source_size': len(source_bytes),
                'source_sha256': source_sha,
                'profile': effective_profile,
                'app_chunk_bytes': args.chunk_bytes,
                'app_chunk_count': len(chunk_plan),
                'wire_payload_size': len(wire_payload),
                'received_wire_size': len(received_wire),
                'received_plain_size': len(received_plain),
                'wire_payload_path': str(wire_payload_path),
                'received_wire_path': str(received_wire_path),
                'chunk_plan': [
                    {'chunk_index': idx, 'offset': off, 'length': len(payload)}
                    for idx, (off, payload) in enumerate(chunk_plan)
                ],
                'wire_manifest': wire_manifest,
                'chunk_attempts': [],
                'ota_metrics': ota_metrics,
            }
            summary_path = run_dir / 'demo_result.json'
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print()
            print('=' * 60)
            print('[FAIL] spool latent OTA 未全部成功')
            print(f'  result       : {summary_path}')
            print('=' * 60)
            return 2
        # 多 job spool 全部失败：输出汇总后退出
        if not spool_ok and args.spool_count > 1:
            pass_count = ota_metrics.get('pass_count', 0)
            summary = {
                'success': False,
                'stage': 'ota_spool_multi',
                'ota_path': args.ota_path,
                'spool_count': args.spool_count,
                'pass_count': pass_count,
                'source_latent': str(source_latent),
                'source_size': len(source_bytes),
                'source_sha256': source_sha,
                'profile': effective_profile,
                'wire_payload_size': len(wire_payload),
                'ota_metrics': ota_metrics,
            }
            summary_path = run_dir / 'demo_result.json'
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print()
            print('=' * 60)
            print(f'[FAIL] spool multi-job OTA: {pass_count}/{args.spool_count} passed')
            print(f'  result       : {summary_path}')
            print('=' * 60)
            return 2
    elif args.ota_path == 'spool_arq':
        received_wire = b''
        received_plain = b''
        try:
            spool_arq_ok, received_wire, received_plain, ota_metrics = run_ota_spool_arq(
                args=args,
                run_dir=run_dir,
                chunk_plan=chunk_plan,
                received_wire_path=received_wire_path,
                profile=effective_profile,
                max_attempts=args.chunk_attempts,
                whitening_enabled=not args.no_whitening,
                whitening_seed=args.whitening_seed,
            )
        except Exception as exc:
            spool_arq_ok = False
            if received_wire_path.exists():
                received_wire = received_wire_path.read_bytes()
                try:
                    received_plain = recover_payload_from_wire(
                        received_wire,
                        wire_manifest=wire_manifest,
                    )
                except Exception:
                    received_plain = b''
            ota_metrics = {
                'transport': 'spool_arq',
                'error': str(exc),
                'remote_log': str(run_dir / 'remote_rx_arq.log'),
                'tx_logs_dir': str(run_dir / 'tx_logs_arq'),
            }
        if not spool_arq_ok:
            summary = {
                'success': False,
                'stage': 'ota_spool_arq',
                'ota_path': args.ota_path,
                'source_latent': str(source_latent),
                'source_size': len(source_bytes),
                'source_sha256': source_sha,
                'profile': effective_profile,
                'app_chunk_bytes': args.chunk_bytes,
                'app_chunk_count': len(chunk_plan),
                'wire_payload_size': len(wire_payload),
                'received_wire_size': len(received_wire),
                'received_plain_size': len(received_plain),
                'wire_payload_path': str(wire_payload_path),
                'received_wire_path': str(received_wire_path),
                'chunk_plan': [
                    {'chunk_index': idx, 'offset': off, 'length': len(payload)}
                    for idx, (off, payload) in enumerate(chunk_plan)
                ],
                'wire_manifest': wire_manifest,
                'chunk_attempts': [],
                'ota_metrics': ota_metrics,
            }
            summary_path = run_dir / 'demo_result.json'
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print()
            print('=' * 60)
            print('[FAIL] spool_arq latent OTA 未全部成功')
            print(f'  result       : {summary_path}')
            print('=' * 60)
            return 2
    elif args.ota_path == 'copy':
        copy_ok, received_wire, received_plain, ota_metrics = run_ota_copy(
            wire_payload_path=wire_payload_path,
            received_wire_path=received_wire_path,
            wire_manifest=wire_manifest,
            source_bytes=source_bytes,
        )
        if not copy_ok:
            summary = {
                'success': False,
                'stage': 'ota_copy',
                'ota_path': args.ota_path,
                'source_latent': str(source_latent),
                'source_size': len(source_bytes),
                'source_sha256': source_sha,
                'profile': effective_profile,
                'app_chunk_bytes': args.chunk_bytes,
                'app_chunk_count': len(chunk_plan),
                'wire_payload_size': len(wire_payload),
                'received_wire_size': len(received_wire),
                'received_plain_size': len(received_plain),
                'wire_payload_path': str(wire_payload_path),
                'received_wire_path': str(received_wire_path),
                'chunk_plan': [
                    {'chunk_index': idx, 'offset': off, 'length': len(payload)}
                    for idx, (off, payload) in enumerate(chunk_plan)
                ],
                'wire_manifest': wire_manifest,
                'chunk_attempts': [],
                'ota_metrics': ota_metrics,
            }
            summary_path = run_dir / 'demo_result.json'
            with summary_path.open('w', encoding='utf-8') as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print()
            print('=' * 60)
            print('[FAIL] copy latent 验链失败')
            print(f'  result       : {summary_path}')
            print('=' * 60)
            return 2
    else:
        ota_kwargs = frozen_ota_kwargs(args)
        received_parts: list[bytes] = []

        for chunk_index, (offset, chunk) in enumerate(chunk_plan):
            wire_chunk, wire_seed = build_wire_chunk(
                chunk,
                chunk_index=chunk_index,
                whitening_enabled=not args.no_whitening,
                whitening_seed=args.whitening_seed,
            )
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
            all_attempts.extend(attempts)
            if not success:
                summary = {
                    'success': False,
                    'stage': 'ota_chunk',
                    'ota_path': args.ota_path,
                    'failed_chunk_index': chunk_index,
                    'source_latent': str(source_latent),
                    'source_size': len(source_bytes),
                    'source_sha256': source_sha,
                    'profile': effective_profile,
                    'chunk_plan': [
                        {'chunk_index': idx, 'offset': off, 'length': len(payload)}
                        for idx, (off, payload) in enumerate(chunk_plan)
                    ],
                    'wire_manifest': wire_manifest,
                    'chunk_attempts': [asdict(item) for item in all_attempts],
                }
                summary_path = run_dir / 'demo_result.json'
                with summary_path.open('w', encoding='utf-8') as handle:
                    json.dump(summary, handle, ensure_ascii=False, indent=2)
                    handle.write('\n')
                print()
                print('=' * 60)
                print('[FAIL] latent chunk OTA 未全部成功')
                print(f'  failed chunk : {chunk_index}')
                print(f'  result       : {summary_path}')
                print('=' * 60)
                return 2

            received_parts.append(received_chunk)
            if args.chunk_gap_sec > 0:
                time.sleep(args.chunk_gap_sec)

        received_plain = b''.join(received_parts)

    reassembled_path = assets_dir / 'received_latent.npz'
    reassembled_bytes = received_plain
    reassembled_path.write_bytes(reassembled_bytes)
    reassembled_sha = hashlib.sha256(reassembled_bytes).hexdigest()
    sha_match = reassembled_bytes == source_bytes
    try:
        payload_metrics = npz_payload_metrics(source_bytes, reassembled_bytes)
    except Exception as exc:
        payload_metrics = {
            'effective_snr_db': None,
            'effective_snr_db_text': 'unavailable',
            'error': str(exc),
        }
    print(
        '[Reassemble] '
        f'size={len(reassembled_bytes)}B sha256={reassembled_sha} '
        f'sha_match={sha_match}',
        flush=True,
    )
    print(
        '[Reassemble] '
        f'latent_effective_snr_db={payload_metrics["effective_snr_db_text"]} '
        f'byte_errors={payload_metrics.get("byte_errors")} '
        f'bit_errors={payload_metrics.get("bit_errors")} '
        f'max_abs_error={payload_metrics.get("max_abs_error")}',
        flush=True,
    )
    if not sha_match:
        raise RuntimeError('chunk 全部返回成功，但重组结果与源文件不一致')

    # ── TVM 重建（--tvm-skip 跳过）──
    tvm_skip = getattr(args, 'tvm_skip', False)
    reconstruction_summary = None
    if tvm_skip:
        print('[TVM] --tvm-skip: 跳过重建', flush=True)
    else:
        helper_local_path = REPO_ROOT / 'scripts' / 'tvm_inference_helper.py'
        ensure_remote_dir(args, remote_dir, run_dir / 'remote_mkdir.log')

        source_recon = run_remote_tvm_inference(
            args=args,
            label='source_recon',
            local_input=source_latent,
            remote_work_dir=remote_dir,
            local_result_dir=recon_dir,
            helper_local_path=helper_local_path,
        )
        received_recon = run_remote_tvm_inference(
            args=args,
            label='received_recon',
            local_input=reassembled_path,
            remote_work_dir=remote_dir,
            local_result_dir=recon_dir,
            helper_local_path=helper_local_path,
        )

        source_recon_npy = Path(source_recon.local_output)
        received_recon_npy = Path(received_recon.local_output)
        source_recon_png = recon_dir / 'source_recon.png'
        received_recon_png = recon_dir / 'received_recon.png'
        source_png_ready = save_npy_as_png(source_recon_npy, source_recon_png)
        received_png_ready = save_npy_as_png(received_recon_npy, received_recon_png)

        source_arr = np.load(source_recon_npy)
        received_arr = np.load(received_recon_npy)
        recon_equal = np.array_equal(source_arr, received_arr)
        max_abs_diff = float(np.max(np.abs(source_arr - received_arr)))

        comparison_path = recon_dir / 'comparison.png'
        comparison_ready = (
            source_png_ready
            and received_png_ready
            and create_comparison_image(source_recon_png, received_recon_png, comparison_path)
        )
        reconstruction_summary = {
            'source': asdict(source_recon),
            'received': asdict(received_recon),
            'source_png': str(source_recon_png) if source_png_ready else '',
            'received_png': str(received_recon_png) if received_png_ready else '',
            'comparison_png': str(comparison_path) if comparison_ready else '',
            'array_equal': recon_equal,
            'max_abs_diff': max_abs_diff,
        }

    reference_image = maybe_copy_reference_image(args.reference_image, assets_dir)

    # spool 多 job 时的 transaction count
    if args.ota_path == 'spool' and args.spool_count > 1:
        ota_transaction_count = ota_metrics.get('pass_count', 0)
    elif args.ota_path == 'spool_arq':
        ota_transaction_count = int(ota_metrics.get('total_attempts', 0))
    elif args.ota_path == 'copy':
        ota_transaction_count = 0
    elif args.ota_path in ('single', 'spool'):
        ota_transaction_count = 1
    else:
        ota_transaction_count = len(chunk_plan)

    summary = {
        'success': True,
        'source_latent': str(source_latent),
        'received_latent': str(reassembled_path),
        'source_size': len(source_bytes),
        'received_size': len(reassembled_bytes),
        'source_sha256': source_sha,
        'received_sha256': reassembled_sha,
        'sha_match': sha_match,
        'payload_metrics': payload_metrics,
        'ota_path': args.ota_path,
        'spool_count': getattr(args, 'spool_count', 1),
        'chunk_bytes': args.chunk_bytes,
        'chunk_count': len(chunk_plan),
        'ota_transaction_count': ota_transaction_count,
        'chunk_attempts_limit': args.chunk_attempts,
        'whitening_enabled': (not args.no_whitening),
        'whitening_seed_base': int(args.whitening_seed),
        'separate_tx_warmup': bool(args.separate_tx_warmup),
        'tx_warmup_bytes': int(args.tx_warmup_bytes),
        'tx_warmup_settle_sec': float(args.tx_warmup_settle_sec),
        'wire_payload_path': str(wire_payload_path),
        'received_wire_path': str(received_wire_path) if received_wire_path.exists() else '',
        'profile': effective_profile,
        'chunk_plan': [
            {'chunk_index': idx, 'offset': off, 'length': len(payload)}
            for idx, (off, payload) in enumerate(chunk_plan)
        ],
        'wire_manifest': wire_manifest,
        'chunk_attempts': (
            list(ota_metrics.get('job_results') or [])
            if args.ota_path == 'spool_arq'
            else [asdict(item) for item in all_attempts]
        ),
        'ota_metrics': ota_metrics,
        'reference_image': reference_image,
        'reconstruction': reconstruction_summary,
        'remote': {
            'host': args.board_host,
            'remote_work_dir': remote_dir,
            'tvm_python': args.remote_tvm_python,
            'artifact_path': args.remote_tvm_artifact,
            'snr': args.snr,
            'seed': args.seed,
        },
    }
    summary_path = run_dir / 'demo_result.json'
    with summary_path.open('w', encoding='utf-8') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write('\n')

    print()
    print('=' * 60)
    if args.ota_path == 'spool' and args.spool_count > 1:
        pass_count = ota_metrics.get('pass_count', 0)
        print(f'[PASS] spool multi-job OTA: {pass_count}/{args.spool_count} passed')
    elif args.ota_path == 'spool_arq':
        print(
            '[PASS] spool_arq chunk OTA: '
            f'chunks={len(chunk_plan)} '
            f'attempts={ota_metrics.get("total_attempts", 0)} '
            f'retries={ota_metrics.get("retry_attempts", 0)}'
        )
    else:
        print('[PASS] USRP latent 独立演示完成')
    print(f'  source latent : {source_latent}')
    print(f'  received      : {reassembled_path}')
    if reconstruction_summary:
        print(f'  source recon  : {reconstruction_summary["source"]["local_output"]}')
        print(f'  recv recon    : {reconstruction_summary["received"]["local_output"]}')
        if reconstruction_summary.get('source_png'):
            print(f'  source png    : {reconstruction_summary["source_png"]}')
        if reconstruction_summary.get('received_png'):
            print(f'  recv png      : {reconstruction_summary["received_png"]}')
        if reconstruction_summary.get('comparison_png'):
            print(f'  compare png   : {reconstruction_summary["comparison_png"]}')
    else:
        print('  (TVM 重建已跳过)')
    print(f'  result        : {summary_path}')
    print('=' * 60)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
