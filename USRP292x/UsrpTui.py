#!/usr/bin/env python3
"""USRP292x QPSK/ARQ TUI.

用途：
1. 从 `tui_start.sh --usrp` 进入 USRP 数据面测试。
2. 以同一套参数启动 single/batch selective-ARQ 测试。
3. 提供 `--smoke` / `--dry-run` 入口，方便非交互回归。
"""

from __future__ import annotations

import asyncio
import argparse
import atexit
import json
import os
import re
import shlex
import signal
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Callable

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STRESS_INPUT = PROJECT_ROOT / 'USRP292x' / 'payloads' / 'source_latent_wire_blob.bin'
DEFAULT_WEBP_INPUT_DIR = PROJECT_ROOT / 'USRP292x' / 'payloads' / 'finalwork_webp5'
DEFAULT_INPUT = DEFAULT_WEBP_INPUT_DIR
DEFAULT_RUN_ROOT = PROJECT_ROOT / 'USRP292x' / 'qpsk_batch_spool_arq_runs'
DEFAULT_BATCH_RUNNER = PROJECT_ROOT / 'USRP292x' / 'RunQpskFileBatchSpoolArq.py'
QPSK_CPP_DECODE = PROJECT_ROOT / 'USRP292x' / 'QpskFileDecode'
RX_SERVER = PROJECT_ROOT / 'USRP292x' / 'OtaRxPersistentServer.sh'
TX_SERVER = PROJECT_ROOT / 'USRP292x' / 'OtaTxPersistentServer.sh'
RX_CONTROL = PROJECT_ROOT / 'USRP292x' / 'OtaRxControl.py'
TX_CONTROL = PROJECT_ROOT / 'USRP292x' / 'OtaTxControl.py'
SERVER_LOG_DIR = PROJECT_ROOT / 'USRP292x' / 'server_logs'
DEFAULT_FAST_ARQ_PROFILE = True
DEFAULT_REMOTE_RUN_ROOT = '/tmp/usrp292x_remote_runs'
ROLE_MODE_LABELS = {
    'local-rxtx': 'Local RX/TX',
    'local-tx': 'Local TX',
    'local-rx': 'Local RX',
}
_ROLE_HIDDEN_IDS = {
    'local-rx': [
        '#lbl_tx_args', '#tx_args',
        '#lbl_tx_gain', '#tx_gain',
        '#lbl_tx_ctrl', '#tx_control',
        '#lbl_remote_rx', '#remote_rx_ssh_target',
        '#lbl_remote_password', '#remote_rx_password',
        '#lbl_remote_project', '#remote_project_root',
        '#lbl_remote_run_root', '#remote_rx_run_root',
    ],
}
BASELINE_PRESETS = {
    'webp': {
        'label': 'Frozen Baseline: WebP',
        'path': DEFAULT_WEBP_INPUT_DIR,
        'description': 'finalWork + webp-lossless 业务基线，均值约 24 KB，冻结指标约 0.502 s/image。',
    },
    'stress': {
        'label': 'Frozen Baseline: Stress Blob',
        'path': DEFAULT_STRESS_INPUT,
        'description': '131 KB 压力包口径，TUI 历史常见约 0.9-1.0 s/image。',
    },
}

USRP_HELP_TEXT = dedent(
    '''
    USRP292x 数据面 TUI 帮助

    推荐顺序
    1. 先选择 Local role mode（下拉框）；双机演示时 TX 端选 Local TX，RX 端选 Local RX。
    2. 再按 `u` 启动当前模式下的常驻服务。
    3. 按 `r` 看状态是否 ready / idle。
    4. 填好参数后按 `b` 跑批量，或按 `s` 跑单图。
    5. 若只想检查配置是否能组命令，用 `d` 做 dry-run。

    快捷键
    h / F1: 打开帮助
    u: 启动常驻 RX/TX
    r: 查询常驻状态
    c: 关闭常驻 RX/TX
    d: dry-run
    s: 单图
    b: 批量
    x: 停止当前 batch
    q: 退出 TUI

    参数说明
    Local role mode（下拉框）:
      Local RX/TX — 本机双端模式
      Local TX — 本机 TX + 远端 RX，由 TX 端统一编排
      Local RX — 本机 RX helper，用于远端部署/排障
    Payload preset:
      WebP (~24KB) 为当前冻结业务基线（默认）
      Stress (131KB) 为压力包口径
    FREQ: 中心频率，支持简写 500M / 2.45G / 500MHz
    RATE: 采样率，支持简写 5M / 219.298k / 5MSps
    TX_GAIN / RX_GAIN: 增益，单位 dB
    TX_ARGS: TX 设备地址，格式 addr=192.168.10.x
    RX_ARGS: RX 设备地址，格式 addr=192.168.10.x
    TX CTRL / RX CTRL: 常驻 server 控制地址 host:port；
      双机时 RX 侧填远端 Tailscale IP，如 100.121.87.73:29220
    Remote RX SSH target: Local TX 模式下远端拉起 RX server，如 user@100.121.87.73
    Remote project root: 远端项目目录（默认与本机相同）
    Remote run root: 远端临时文件目录
    chunk_bytes: 每个 payload chunk 的字节数；当前默认 2048
    batch_size: 一个 RF capture 内最多打包多少张；当前演示默认 6，安全上限 20
    decode_workers: 并行解码 worker 数；当前安全值 2
    Artifact mode（下拉框）:
      minimal — 适合日常跑
      full — 保留完整中间产物，适合排障
      board — 偏板端节省空间
    Backend（下拉框）:
      cpp — 当前推荐
      python — 只用于对照
    C++ mode（下拉框）:
      header — 当前推荐
      hybrid — 更接近旧 Python 口径
      sync — 实验模式

    当前默认基线
    WebP payload preset + 500M / 5M / TX gain 25 / RX gain 15 /
    chunk=2048 / cpp+header / minimal / fast-arq-profile
    '''
).strip()


class UsrpHelpScreen(ModalScreen[None]):
    CSS = '''
    UsrpHelpScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    #usrp-help-dialog {
        width: 92;
        max-width: 96%;
        height: 26;
        max-height: 90%;
        border: round #4f7c89;
        background: #10181b;
        padding: 1 2;
    }
    #usrp-help-title {
        content-align: center middle;
        text-style: bold;
        color: #d8e2dc;
        margin-bottom: 1;
    }
    #usrp-help-body {
        height: 1fr;
        color: #d8e2dc;
    }
    #usrp-help-close {
        margin-top: 1;
        width: 1fr;
    }
    '''
    BINDINGS = [
        ('escape', 'close_help', '关闭'),
        ('h', 'close_help', '关闭'),
        ('f1', 'close_help', '关闭'),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id='usrp-help-dialog'):
            yield Static('USRP292x TUI Help', id='usrp-help-title')
            with VerticalScroll(id='usrp-help-body'):
                yield Static(USRP_HELP_TEXT)
            yield Button('关闭帮助 (Esc / h / F1)', id='usrp-help-close', variant='primary')

    def action_close_help(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'usrp-help-close':
            self.dismiss(None)


@dataclass
class RadioParams:
    local_role_mode: str = 'local-tx'
    tx_args: str = 'addr=192.168.10.2'
    rx_args: str = 'addr=192.168.10.22'
    freq: str = '500M'
    rate: str = '5M'
    tx_gain: str = '25'
    rx_gain: str = '15'
    rx_ant: str = 'RX2'
    amplitude: str = '3000'
    chunk_bytes: str = '2048'
    rx_duration: str = '2.3'
    search_start_sec: str = '0.20'
    search_end_sec: str = '2.25'
    frame_candidates: str = '64'
    max_arq_rounds: str = '2'
    rx_control_host: str = '100.121.87.73'
    rx_control_port: str = '29220'
    tx_control_host: str = '127.0.0.1'
    tx_control_port: str = '29221'
    bind_addr: str = '0.0.0.0'
    remote_rx_ssh_target: str = 'user@100.121.87.73'
    remote_rx_password: str = ''
    remote_project_root: str = '/home/user'
    remote_rx_run_root: str = DEFAULT_REMOTE_RUN_ROOT

    @classmethod
    def from_env(cls) -> 'RadioParams':
        return cls(
            local_role_mode=os.environ.get('USRP_LOCAL_ROLE_MODE', cls.local_role_mode),
            tx_args=os.environ.get('TX_ARGS', cls.tx_args),
            rx_args=os.environ.get('RX_ARGS', cls.rx_args),
            freq=os.environ.get('FREQ', cls.freq),
            rate=os.environ.get('RATE', cls.rate),
            tx_gain=os.environ.get('TX_GAIN', cls.tx_gain),
            rx_gain=os.environ.get('RX_GAIN', cls.rx_gain),
            rx_ant=os.environ.get('RX_ANT', cls.rx_ant),
            amplitude=os.environ.get('AMPLITUDE', cls.amplitude),
            chunk_bytes=os.environ.get('CHUNK_BYTES', cls.chunk_bytes),
            rx_duration=os.environ.get('RX_DURATION', cls.rx_duration),
            search_start_sec=os.environ.get('SEARCH_START_SEC', cls.search_start_sec),
            search_end_sec=os.environ.get('SEARCH_END_SEC', cls.search_end_sec),
            frame_candidates=os.environ.get('FRAME_CANDIDATES', cls.frame_candidates),
            max_arq_rounds=os.environ.get('MAX_ARQ_ROUNDS', cls.max_arq_rounds),
            rx_control_host=os.environ.get('RX_CONTROL_HOST', cls.rx_control_host),
            rx_control_port=os.environ.get('RX_CONTROL_PORT', cls.rx_control_port),
            tx_control_host=os.environ.get('TX_CONTROL_HOST', cls.tx_control_host),
            tx_control_port=os.environ.get('TX_CONTROL_PORT', cls.tx_control_port),
            bind_addr=os.environ.get('BIND_ADDR', cls.bind_addr),
            remote_rx_ssh_target=os.environ.get('REMOTE_RX_SSH_TARGET', cls.remote_rx_ssh_target),
            remote_rx_password=os.environ.get('SSHPASS', cls.remote_rx_password),
            remote_project_root=os.environ.get('REMOTE_PROJECT_ROOT', cls.remote_project_root),
            remote_rx_run_root=os.environ.get('REMOTE_RX_RUN_ROOT', cls.remote_rx_run_root),
        )

    def as_env(self) -> dict[str, str]:
        return {
            'USRP_LOCAL_ROLE_MODE': self.local_role_mode,
            'TX_ARGS': self.tx_args,
            'RX_ARGS': self.rx_args,
            'FREQ': self.freq,
            'RATE': self.rate,
            'TX_GAIN': self.tx_gain,
            'RX_GAIN': self.rx_gain,
            'RX_ANT': self.rx_ant,
            'AMPLITUDE': self.amplitude,
            'CHUNK_BYTES': self.chunk_bytes,
            'RX_DURATION': self.rx_duration,
            'SEARCH_START_SEC': self.search_start_sec,
            'SEARCH_END_SEC': self.search_end_sec,
            'FRAME_CANDIDATES': self.frame_candidates,
            'MAX_ARQ_ROUNDS': self.max_arq_rounds,
            'RX_CONTROL_HOST': self.rx_control_host,
            'RX_CONTROL_PORT': self.rx_control_port,
            'TX_CONTROL_HOST': self.tx_control_host,
            'TX_CONTROL_PORT': self.tx_control_port,
            'REMOTE_RX_SSH_TARGET': self.remote_rx_ssh_target,
            'SSHPASS': self.remote_rx_password,
            'REMOTE_PROJECT_ROOT': self.remote_project_root,
            'REMOTE_RX_RUN_ROOT': self.remote_rx_run_root,
        }


def _qshell(path: str) -> str:
    """Quote a path for shell, preserving ~ expansion."""
    if path.startswith('~/'):
        return '~/' + shlex.quote(path[2:])
    return shlex.quote(path)


def default_run_id(prefix: str) -> str:
    return time.strftime(f'{prefix}_%Y%m%d_%H%M%S')


def format_decimal(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f'{value:.6f}'.rstrip('0').rstrip('.')


def _compact_number(value: int | float | str) -> str:
    n = abs(float(value))
    if n >= 1e9:
        return f'{format_decimal(float(value) / 1e9)}G'
    if n >= 1e6:
        return f'{format_decimal(float(value) / 1e6)}M'
    if n >= 1e3:
        return f'{format_decimal(float(value) / 1e3)}k'
    return str(int(float(value)))


def parse_scaled_integer(text: str, *, field: str) -> str:
    raw = text.strip()
    if raw == '':
        raise ValueError(f'{field} 不能为空')
    compact = raw.replace('_', '').replace(' ', '')
    lower = compact.lower()
    if lower.endswith('sps'):
        lower = lower[:-3]
    elif lower.endswith('hz'):
        lower = lower[:-2]
    multiplier = 1.0
    if lower.endswith('k'):
        multiplier = 1e3
        lower = lower[:-1]
    elif lower.endswith('m'):
        multiplier = 1e6
        lower = lower[:-1]
    elif lower.endswith('g'):
        multiplier = 1e9
        lower = lower[:-1]
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', lower):
        raise ValueError(f'{field} 不支持的格式: {text}')
    value = float(lower) * multiplier
    if value <= 0:
        raise ValueError(f'{field} 必须大于 0')
    return str(int(round(value)))


def parse_float_text(text: str, *, field: str) -> str:
    raw = text.strip()
    if raw == '':
        raise ValueError(f'{field} 不能为空')
    value = float(raw)
    return format_decimal(value)


def parse_int_text(text: str, *, field: str) -> str:
    raw = text.strip()
    if raw == '':
        raise ValueError(f'{field} 不能为空')
    return str(int(raw))


def normalize_local_role_mode(text: str) -> str:
    normalized = str(text or '').strip().lower().replace('_', '-')
    aliases = {
        'rxtx': 'local-rxtx',
        'local': 'local-rxtx',
        'local-rxtx': 'local-rxtx',
        'tx': 'local-tx',
        'local-tx': 'local-tx',
        'rx': 'local-rx',
        'local-rx': 'local-rx',
    }
    if normalized not in aliases:
        allowed = ', '.join(ROLE_MODE_LABELS)
        raise ValueError(f'local_role_mode 仅支持: {allowed}')
    return aliases[normalized]


def role_has_local_rx(mode: str) -> bool:
    return mode in ('local-rxtx', 'local-rx')


def role_has_local_tx(mode: str) -> bool:
    return mode in ('local-rxtx', 'local-tx')


def role_uses_remote_rx(mode: str) -> bool:
    return mode == 'local-tx'


def normalize_radio_params(params: RadioParams) -> RadioParams:
    params.local_role_mode = normalize_local_role_mode(params.local_role_mode)
    params.freq = parse_scaled_integer(params.freq, field='FREQ')
    params.rate = parse_scaled_integer(params.rate, field='RATE')
    params.tx_gain = parse_float_text(params.tx_gain, field='TX_GAIN')
    params.rx_gain = parse_float_text(params.rx_gain, field='RX_GAIN')
    params.chunk_bytes = parse_int_text(params.chunk_bytes, field='chunk_bytes')
    params.rx_control_host = params.rx_control_host.strip() or '100.121.87.73'
    params.tx_control_host = params.tx_control_host.strip() or '127.0.0.1'
    params.rx_control_port = parse_int_text(params.rx_control_port, field='RX_CONTROL_PORT')
    params.tx_control_port = parse_int_text(params.tx_control_port, field='TX_CONTROL_PORT')
    params.remote_rx_ssh_target = params.remote_rx_ssh_target.strip()
    params.remote_project_root = params.remote_project_root.strip() or str(PROJECT_ROOT)
    params.remote_rx_run_root = params.remote_rx_run_root.strip() or DEFAULT_REMOTE_RUN_ROOT
    return params


def read_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def format_bytes_text(value: int | float | None) -> str:
    if value is None:
        return '-'
    number = float(value)
    if number.is_integer():
        return f'{int(number):,} B'
    return f'{number:,.3f} B'


def format_hz_text(value: int | float | str | None, *, suffix: str = 'Hz') -> str:
    if value in (None, ''):
        return '-'
    number = float(value)
    abs_number = abs(number)
    if abs_number >= 1e9:
        return f'{format_decimal(number / 1e9)} G{suffix}'
    if abs_number >= 1e6:
        return f'{format_decimal(number / 1e6)} M{suffix}'
    if abs_number >= 1e3:
        return f'{format_decimal(number / 1e3)} k{suffix}'
    return f'{format_decimal(number)} {suffix}'


def format_ms_text(value: int | float | None) -> str:
    if value is None:
        return '-'
    return f'{float(value):.3f} ms'


def format_sec_text(value: int | float | None) -> str:
    if value is None:
        return '-'
    return f'{float(value):.3f} s'


def get_baseline_preset_meta(name: str) -> dict[str, object]:
    return BASELINE_PRESETS.get(str(name or '').strip().lower(), BASELINE_PRESETS['webp'])


def infer_baseline_preset(path: Path) -> str | None:
    try:
        resolved = path.expanduser().resolve()
    except FileNotFoundError:
        resolved = path.expanduser()
    for preset_name, meta in BASELINE_PRESETS.items():
        preset_path = Path(str(meta['path']))
        try:
            if resolved == preset_path.resolve():
                return preset_name
        except FileNotFoundError:
            if resolved == preset_path:
                return preset_name
    return None


def resolve_effective_input_path(args: argparse.Namespace) -> Path:
    raw_input = getattr(args, 'input', None)
    if raw_input not in (None, ''):
        return Path(str(raw_input)).expanduser()
    return Path(str(get_baseline_preset_meta(getattr(args, 'baseline_preset', 'webp'))['path'])).expanduser()


def summarize_input_source(path: Path) -> tuple[str, int | None, int | None]:
    expanded = path.expanduser()
    if expanded.is_dir():
        files = sorted(item for item in expanded.rglob('*.bin') if item.is_file())
        if not files:
            return (f'{expanded.name}/*.bin', None, 0)
        sizes = [item.stat().st_size for item in files]
        mean_bytes = int(round(sum(sizes) / len(sizes)))
        return (f'{expanded.name}/*.bin', mean_bytes, len(files))
    if expanded.is_file():
        return (expanded.name, expanded.stat().st_size, 1)
    return (expanded.name, None, None)


def build_input_source_args(path: Path) -> tuple[list[str], str, int | None, int | None]:
    expanded = path.expanduser()
    label, input_bytes, source_count = summarize_input_source(expanded)
    if expanded.is_dir():
        return (
            ['--input-dir', str(expanded), '--pattern', '*.bin', '--cycle-inputs'],
            label,
            input_bytes,
            source_count,
        )
    return (['--input', str(expanded)], label, input_bytes, source_count)


def format_payload_line(payload_label: str, input_bytes: int | None, count: int, source_count: int | None) -> str:
    if source_count is not None and source_count > 1:
        return (
            f'payload={payload_label} ({format_bytes_text(input_bytes)} mean, '
            f'source_count={source_count}) x{count}'
        )
    return f'payload={payload_label} ({format_bytes_text(input_bytes)}) x{count}'


def parse_key_value_tokens(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in str(text).split():
        if '=' not in token:
            continue
        key, value = token.split('=', 1)
        result[key.strip()] = value.strip()
    return result


def extract_duration_stats(summary: dict) -> tuple[float | None, float | None]:
    mean_sec = float(summary.get('per_image_sec', 0.0) or 0.0)
    results = summary.get('results') or []
    if not isinstance(results, list) or not results:
        return (mean_sec if mean_sec > 0 else None, None)

    shared_other_sec = float(summary.get('estimated_non_airtime_non_decode_non_merge_wall_sec_mean', 0.0) or 0.0)
    durations: list[float] = []
    for item in results:
        payload_sec = float(item.get('payload_airtime_ms', 0.0) or 0.0) / 1000.0
        decode_sec = 0.0
        merge_sec = 0.0
        for record in item.get('round_records', []) or []:
            decode_sec += float(record.get('decode_total_wall_sec', 0.0) or 0.0)
            merge_sec += float(record.get('merge_wall_sec', 0.0) or 0.0)
        durations.append(payload_sec + decode_sec + merge_sec + shared_other_sec)
    if not durations:
        return (mean_sec if mean_sec > 0 else None, None)
    return statistics.mean(durations), statistics.median(durations)


def build_batch_command(args: argparse.Namespace, *, dry_run: bool) -> list[str]:
    input_path = resolve_effective_input_path(args)
    input_args, _, _, _ = build_input_source_args(input_path)
    cmd = [
        sys.executable,
        str(DEFAULT_BATCH_RUNNER),
        '--count',
        str(args.count),
        '--run-id',
        args.run_id,
        '--run-root',
        str(args.run_root),
        '--max-arq-rounds',
        str(args.max_arq_rounds),
        '--chunk-bytes',
        str(args.chunk_bytes),
        '--batch-size',
        str(args.batch_size),
        '--decode-workers',
        str(args.decode_workers),
        '--decode-backend',
        args.decode_backend,
        '--cpp-sync-mode',
        args.cpp_sync_mode,
        '--artifact-mode',
        args.artifact_mode,
    ]
    cmd.extend(input_args)
    if args.fast_arq_profile:
        cmd.append('--fast-arq-profile')
    if dry_run:
        cmd.append('--dry-run')
    if args.stop_on_fail:
        cmd.append('--stop-on-fail')
    return cmd


def build_batch_env(params: RadioParams) -> dict[str, str]:
    env = params.as_env()
    env['RX_CAPTURE_MODE'] = 'remote-decode' if role_uses_remote_rx(params.local_role_mode) else 'local'
    return env


async def compose_smoke(args: argparse.Namespace) -> list[str]:
    app = UsrpTui(RadioParams.from_env(), args)
    async with app.run_test() as pilot:
        await pilot.pause()
        run_id = app.query_one('#run_id', Input)
        chunk_bytes = app.query_one('#chunk_bytes', Input)
        log = app.query_one('#log', RichLog)
        return [
            f'run_id={run_id.value}',
            f'chunk_bytes={chunk_bytes.value}',
            f'log_widget={log.id}',
        ]


async def auto_stop_selftest(args: argparse.Namespace) -> dict[str, object]:
    params = normalize_radio_params(RadioParams.from_env())
    pre_messages = persistent_status(params)
    app = UsrpTui(params, args)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.action_persistent_start()
        deadline = time.time() + 20.0
        while time.time() < deadline:
            await pilot.pause()
            ready = control_ok(RX_CONTROL, params.rx_control_host, params.rx_control_port) and control_ok(
                TX_CONTROL, params.tx_control_host, params.tx_control_port
            )
            if ready:
                break
            await asyncio.sleep(0.2)
        started_ready = control_ok(RX_CONTROL, params.rx_control_host, params.rx_control_port) and control_ok(
            TX_CONTROL, params.tx_control_host, params.tx_control_port
        )
        app.action_quit()
        await pilot.pause()
    await asyncio.sleep(1.0)
    rx_alive = control_ok(RX_CONTROL, params.rx_control_host, params.rx_control_port)
    tx_alive = control_ok(TX_CONTROL, params.tx_control_host, params.tx_control_port)
    post_messages = persistent_status(params)
    return {
        'pre_messages': pre_messages,
        'started_ready': started_ready,
        'post_rx_alive': rx_alive,
        'post_tx_alive': tx_alive,
        'post_messages': post_messages,
    }


def check_ready() -> list[str]:
    problems: list[str] = []
    if not DEFAULT_BATCH_RUNNER.is_file():
        problems.append(f'missing batch runner: {DEFAULT_BATCH_RUNNER}')
    if not QPSK_CPP_DECODE.is_file():
        problems.append(f'missing C++ decoder: {QPSK_CPP_DECODE}; run ./USRP292x/BuildOtaTools.sh')
    for path in (RX_SERVER, TX_SERVER, RX_CONTROL, TX_CONTROL):
        if not path.is_file():
            problems.append(f'missing persistent control entry: {path}')
    if not DEFAULT_WEBP_INPUT_DIR.is_dir():
        problems.append(f'missing default webp baseline dir: {DEFAULT_WEBP_INPUT_DIR}')
    if not DEFAULT_STRESS_INPUT.is_file():
        problems.append(f'missing stress baseline input: {DEFAULT_STRESS_INPUT}')
    if not (PROJECT_ROOT / 'USRP292x' / 'RunQpskFileArqOta.sh').is_file():
        problems.append('missing RunQpskFileArqOta.sh')
    return problems


def control_cmd(script: Path, host: str, port: str, cmd: str, timeout: str = '5') -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), '--host', host, '--port', port, '--timeout', timeout, cmd],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def control_ok(script: Path, host: str, port: str) -> bool:
    proc = control_cmd(script, host, port, 'ping', timeout='3')
    return proc.returncode == 0 and proc.stdout.startswith('OK')


def _ssh_base_args(password: str = '', timeout: int = 10) -> list[str]:
    """Build SSH base args, using sshpass if password is provided."""
    if password:
        return ['sshpass', '-e', 'ssh', '-o', 'ConnectTimeout={}'.format(timeout)]
    if os.environ.get('SSHPASS'):
        return ['sshpass', '-e', 'ssh', '-o', 'ConnectTimeout={}'.format(timeout)]
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout={}'.format(timeout)]


def run_ssh_command(
    target: str,
    remote_cmd: str,
    *,
    log_path: Path | None = None,
    check: bool = True,
    timeout: int = 10,
    password: str = '',
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if password:
        env['SSHPASS'] = password
    proc = subprocess.run(
        _ssh_base_args(password, timeout) + [target, remote_cmd],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(proc.stdout, encoding='utf-8')
    if check and proc.returncode != 0:
        raise RuntimeError(f'ssh command failed ({proc.returncode}): {target}\n{proc.stdout}')
    return proc


def start_local_server(script: Path, params: RadioParams, *, role: str) -> str:
    SERVER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = SERVER_LOG_DIR / f'{role.lower()}_persistent_demo_{time.strftime("%Y%m%d_%H%M%S")}.log'
    env = os.environ.copy()
    if role == 'RX':
        env.update({
            'DEVICE_ARGS': params.rx_args,
            'RATE': params.rate,
            'FREQ': params.freq,
            'GAIN': params.rx_gain,
            'ANT': params.rx_ant,
            'BIND_ADDR': params.bind_addr,
            'PORT': params.rx_control_port,
        })
    else:
        env.update({
            'DEVICE_ARGS': params.tx_args,
            'RATE': params.rate,
            'FREQ': params.freq,
            'GAIN': params.tx_gain,
            'ANT': 'TX/RX',
            'BIND_ADDR': params.bind_addr,
            'PORT': params.tx_control_port,
        })
    with log_path.open('w', encoding='utf-8') as log:
        proc = subprocess.Popen(
            [str(script)],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    return f'{role}_pid={proc.pid} log={log_path}'


def start_remote_rx_server(params: RadioParams) -> str:
    if not params.remote_rx_ssh_target:
        raise RuntimeError('Local TX 模式下缺少 REMOTE_RX_SSH_TARGET，无法远端拉起 RX')
    SERVER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    local_boot_log = SERVER_LOG_DIR / f'remote_rx_boot_{stamp}.log'
    remote_log_dir = f'{params.remote_rx_run_root.rstrip("/")}/server_logs'
    remote_log = f'{remote_log_dir}/rx_persistent_{stamp}.log'
    inner = ' && '.join([
        f'cd {_qshell(params.remote_project_root)}',
        f'mkdir -p {shlex.quote(remote_log_dir)}',
    ]) + '; ' + (
        'nohup env '
        f'DEVICE_ARGS={shlex.quote(params.rx_args)} '
        f'RATE={shlex.quote(params.rate)} '
        f'FREQ={shlex.quote(params.freq)} '
        f'GAIN={shlex.quote(params.rx_gain)} '
        f'ANT={shlex.quote(params.rx_ant)} '
        f'BIND_ADDR={shlex.quote(params.bind_addr)} '
        f'PORT={shlex.quote(params.rx_control_port)} '
        f'./USRP292x/OtaRxPersistentServer.sh '
        f'> {shlex.quote(remote_log)} 2>&1 < /dev/null &'
    ) + ' sleep 1'
    remote_cmd = 'bash -lc ' + shlex.quote(inner)
    run_ssh_command(params.remote_rx_ssh_target, remote_cmd, log_path=local_boot_log, check=True, password=params.remote_rx_password)
    return (
        'RX_remote_started '
        f'target={params.remote_rx_ssh_target} '
        f'remote_log={remote_log} '
        f'boot_log={local_boot_log}'
    )


def start_persistent_rxtx(
    params: RadioParams,
    *,
    on_ownership: Callable[[set[str]], None] | None = None,
) -> list[str]:
    messages: list[str] = []
    owned_roles: set[str] = set()
    if control_ok(RX_CONTROL, params.rx_control_host, params.rx_control_port):
        messages.append('RX already running')
    elif role_has_local_rx(params.local_role_mode):
        messages.append(start_local_server(RX_SERVER, params, role='RX'))
        owned_roles.add('RX')
    else:
        messages.append(start_remote_rx_server(params))
        owned_roles.add('RX')

    if role_has_local_tx(params.local_role_mode):
        if control_ok(TX_CONTROL, params.tx_control_host, params.tx_control_port):
            messages.append('TX already running')
        else:
            messages.append(start_local_server(TX_SERVER, params, role='TX'))
            owned_roles.add('TX')
    else:
        messages.append('TX unmanaged role=local-rx')

    if on_ownership is not None and owned_roles:
        on_ownership(set(owned_roles))

    deadline = time.time() + 15.0
    while time.time() < deadline:
        rx_ok = control_ok(RX_CONTROL, params.rx_control_host, params.rx_control_port)
        tx_ok = True
        if role_has_local_tx(params.local_role_mode):
            tx_ok = control_ok(TX_CONTROL, params.tx_control_host, params.tx_control_port)
        if rx_ok and tx_ok:
            messages.append('persistent_status=ready')
            return messages
        time.sleep(0.5)
    messages.append('persistent_status=not_ready')
    return messages


def stop_persistent_rxtx(params: RadioParams) -> list[str]:
    messages: list[str] = []
    rx_stop = control_cmd(RX_CONTROL, params.rx_control_host, params.rx_control_port, 'quit', timeout='10')
    messages.append('RX ' + (rx_stop.stdout.strip() or f'rc={rx_stop.returncode}'))
    if role_has_local_tx(params.local_role_mode):
        tx_stop = control_cmd(TX_CONTROL, params.tx_control_host, params.tx_control_port, 'quit', timeout='10')
        messages.append('TX ' + (tx_stop.stdout.strip() or f'rc={tx_stop.returncode}'))
    else:
        messages.append('TX unmanaged role=local-rx')
    return messages


def persistent_status(params: RadioParams) -> list[str]:
    rx_status = control_cmd(RX_CONTROL, params.rx_control_host, params.rx_control_port, 'status', timeout='5')
    lines = ['RX ' + (rx_status.stdout.strip() or f'rc={rx_status.returncode}')]
    if role_has_local_tx(params.local_role_mode):
        tx_status = control_cmd(TX_CONTROL, params.tx_control_host, params.tx_control_port, 'status', timeout='5')
        lines.append('TX ' + (tx_status.stdout.strip() or f'rc={tx_status.returncode}'))
    else:
        lines.append('TX unmanaged role=local-rx')
    return lines


def run_noninteractive(args: argparse.Namespace, *, dry_run: bool) -> int:
    problems = check_ready()
    if problems:
        for item in problems:
            print(f'usrp_tui_problem={item}')
        return 2

    try:
        params = normalize_radio_params(RadioParams.from_env())
    except ValueError as exc:
        print(f'usrp_tui_problem={exc}')
        return 2
    try:
        if args.start_persistent_rxtx:
            for item in start_persistent_rxtx(params):
                print(item)
            return 0
        if args.stop_persistent_rxtx:
            for item in stop_persistent_rxtx(params):
                print(item)
            return 0
        if args.persistent_status:
            for item in persistent_status(params):
                print(item)
            return 0
    except Exception as exc:
        print(f'usrp_tui_problem=persistent_control_failed: {exc}')
        return 2
    if params.local_role_mode == 'local-rx':
        print('usrp_tui_problem=local-rx mode is RX-helper only; run batch from the TX host')
        return 2

    env = os.environ.copy()
    env.update(build_batch_env(params))
    env['MAX_ARQ_ROUNDS'] = str(args.max_arq_rounds)
    cmd = build_batch_command(args, dry_run=dry_run)
    print('usrp_tui_cmd=' + ' '.join(cmd), flush=True)
    return subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False).returncode


class UsrpTui(App):
    """USRP292x 数据面操作台。"""

    TITLE = 'USRP292x QPSK/ARQ TUI'
    BINDINGS = [
        ('q', 'quit', '退出'),
        ('h', 'show_help', '帮助'),
        ('f1', 'show_help', '帮助'),
        ('d', 'dry_run', 'Dry Run'),
        ('s', 'single', '单图'),
        ('b', 'batch', '批量'),
        ('u', 'persistent_start', '启动常驻'),
        ('r', 'persistent_status', '常驻状态'),
        ('c', 'persistent_stop', '关闭常驻'),
        ('x', 'stop', '停止'),
    ]
    CSS = """
    Screen {
        background: #101416;
        color: #d8e2dc;
    }
    #main {
        height: 1fr;
    }
    #left {
        width: 48;
        height: 1fr;
        padding: 1;
        background: #162024;
        border: solid #37515a;
    }
    #right {
        width: 1fr;
        padding: 1;
    }
    .field-label {
        color: #94a89f;
        margin-top: 1;
    }
    Input {
        margin-bottom: 0;
    }
    Button {
        width: 1fr;
        margin-top: 1;
    }
    #status {
        height: 7;
        padding: 1;
        border: solid #37515a;
        background: #0d1112;
        content-align: left top;
    }
    #dashboard {
        height: 8;
        padding: 1;
        margin-top: 1;
        border: solid #37515a;
        background: #0d1112;
        content-align: left top;
    }
    #log {
        height: 1fr;
        border: solid #37515a;
        background: #0b0f10;
        margin-top: 1;
    }
    """

    def __init__(self, params: RadioParams, args: argparse.Namespace) -> None:
        super().__init__()
        self.params = params
        self.args = args
        self.baseline_preset = str(getattr(args, 'baseline_preset', 'webp') or 'webp')
        self.proc: subprocess.Popen[str] | None = None
        self.proc_thread: threading.Thread | None = None
        self.current_run_root: Path | None = None
        self.current_job_meta: dict[str, object] = {}
        self.log_has_content = False
        self._persistent_owned_roles: set[str] = set()
        self._persistent_owner_params: RadioParams | None = None
        self._shutdown_cleanup_done = False
        self._ui_closing = False
        self._persistent_polling_active = False
        self.persistent_snapshot: dict[str, str] = {
            'rx': 'unknown',
            'tx': 'unknown',
            'detail': '按 u 启动常驻服务',
        }
        self.progress_state: dict[str, object] = {
            'mode': 'idle',
            'target': 0,
            'processed': 0,
            'pass_count': 0,
            'pending': 0,
            'round': None,
            'batch_done': 0,
            'batch_total': 0,
            'started_monotonic': 0.0,
            'dry_run': False,
        }
        atexit.register(self._atexit_cleanup)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id='main'):
            with VerticalScroll(id='left'):
                yield Label('Run ID', classes='field-label')
                yield Input(value=default_run_id('tui'), id='run_id')
                yield Label('Count', classes='field-label')
                yield Input(value=str(self.args.count), id='count')
                yield Label('Local role mode', classes='field-label')
                yield Select(
                    [
                        ('Local RX/TX', 'local-rxtx'),
                        ('Local TX', 'local-tx'),
                        ('Local RX', 'local-rx'),
                    ],
                    value=self.params.local_role_mode,
                    allow_blank=False,
                    id='local_role_mode',
                )
                yield Label('Payload preset', classes='field-label')
                with Horizontal():
                    yield Button('WebP (~24KB)', id='preset_webp', variant='success')
                    yield Button('Stress (131KB)', id='preset_stress', variant='default')
                yield Label('Input wire blob', classes='field-label')
                yield Input(value=str(resolve_effective_input_path(self.args)), id='input')
                yield Label('FREQ (Hz)', classes='field-label')
                yield Input(value=self.params.freq, id='freq')
                yield Label('RATE (Sps)', classes='field-label')
                yield Input(value=self.params.rate, id='rate')
                yield Label('TX_GAIN (dB)', classes='field-label', id='lbl_tx_gain')
                yield Input(value=self.params.tx_gain, id='tx_gain')
                yield Label('RX_GAIN (dB)', classes='field-label')
                yield Input(value=self.params.rx_gain, id='rx_gain')
                yield Label('TX_ARGS (addr=IP)', classes='field-label', id='lbl_tx_args')
                yield Input(value=self.params.tx_args, id='tx_args')
                yield Label('RX_ARGS (addr=IP)', classes='field-label')
                yield Input(value=self.params.rx_args, id='rx_args')
                yield Label('TX CTRL host:port', classes='field-label', id='lbl_tx_ctrl')
                yield Input(value=f'{self.params.tx_control_host}:{self.params.tx_control_port}', id='tx_control')
                yield Label('RX CTRL host:port', classes='field-label')
                yield Input(value=f'{self.params.rx_control_host}:{self.params.rx_control_port}', id='rx_control')
                yield Label('Remote RX SSH target', classes='field-label', id='lbl_remote_rx')
                yield Input(value=self.params.remote_rx_ssh_target, id='remote_rx_ssh_target')
                yield Label('Remote RX password', classes='field-label', id='lbl_remote_password')
                yield Input(value=self.params.remote_rx_password, id='remote_rx_password', password=True, placeholder='SSH key auth if empty')
                yield Label('Remote project root', classes='field-label', id='lbl_remote_project')
                yield Input(value=self.params.remote_project_root, id='remote_project_root')
                yield Label('Remote run root', classes='field-label', id='lbl_remote_run_root')
                yield Input(value=self.params.remote_rx_run_root, id='remote_rx_run_root')
                yield Label('Chunk bytes / batch size / decode workers', classes='field-label')
                yield Input(value=self.params.chunk_bytes, id='chunk_bytes')
                yield Input(value=str(self.args.batch_size), id='batch_size')
                yield Input(value=str(self.args.decode_workers), id='decode_workers')
                yield Label('Artifact mode', classes='field-label')
                yield Select(
                    [
                        ('minimal', 'minimal'),
                        ('full', 'full'),
                        ('board', 'board'),
                    ],
                    value=self.args.artifact_mode,
                    allow_blank=False,
                    id='artifact_mode',
                )
                yield Label('Backend / C++ mode', classes='field-label')
                yield Select(
                    [
                        ('cpp', 'cpp'),
                        ('python', 'python'),
                    ],
                    value=self.args.decode_backend,
                    allow_blank=False,
                    id='decode_backend',
                )
                yield Select(
                    [
                        ('header', 'header'),
                        ('hybrid', 'hybrid'),
                        ('sync', 'sync'),
                    ],
                    value=self.args.cpp_sync_mode,
                    allow_blank=False,
                    id='cpp_sync_mode',
                )
            with Vertical(id='right'):
                yield RichLog(id='status', highlight=True, wrap=True)
                yield RichLog(id='dashboard', highlight=True, wrap=True)
                yield RichLog(id='log', wrap=True, highlight=True)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(5.0, self._refresh_progress_tick)
        self.set_interval(3.0, self._refresh_persistent_tick)
        self._sync_baseline_buttons()
        self._update_role_visibility(self.params.local_role_mode)
        problems = check_ready()
        if problems:
            self._set_status('状态：入口检查失败')
            for item in problems:
                self._log(f'problem: {item}')
        else:
            baseline_meta = get_baseline_preset_meta(self.baseline_preset)
            self._set_progress('进度：未开始')
            self._log_block(
                '\n'.join(
                    [
                        'USRP292x TUI ready.',
                        '默认数据面参数：500 MHz / 5 MSps / chunk=2048 / cpp+header / fast-arq-profile。',
                        f"默认冻结基线：{baseline_meta['label']}。",
                        str(baseline_meta['description']),
                        'FREQ/RATE 支持 K/M/G 缩写，例如 500M、5M、219.298k。',
                        'role mode 支持 local-rxtx / local-tx / local-rx；双机正式 demo 推荐在 TX 端使用 local-tx。',
                    ]
                )
            )

    def _input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _select_value(self, selector: str) -> str:
        widget = self.query_one(selector, Select)
        if widget.is_blank():
            return ''
        return str(widget.value)

    def _set_input_value(self, selector: str, value: str) -> None:
        self.query_one(selector, Input).value = value

    def _sync_baseline_buttons(self) -> None:
        webp_button = self.query_one('#preset_webp', Button)
        stress_button = self.query_one('#preset_stress', Button)
        webp_active = self.baseline_preset == 'webp'
        stress_active = self.baseline_preset == 'stress'
        webp_button.variant = 'success' if webp_active else 'default'
        stress_button.variant = 'warning' if stress_active else 'default'
        webp_button.label = 'WebP (~24KB)' + (' [default]' if webp_active else '')
        stress_button.label = 'Stress (131KB)' + (' [active]' if stress_active else '')

    def _apply_baseline_preset(self, preset: str) -> None:
        normalized = str(preset).strip().lower()
        if normalized not in BASELINE_PRESETS:
            self._log_block(f'未知 baseline preset: {preset}')
            return
        self.baseline_preset = normalized
        meta = get_baseline_preset_meta(normalized)
        self._set_input_value('#input', str(meta['path']))
        self._sync_baseline_buttons()
        self._log_block(
            '\n'.join(
                [
                    f'=== Payload Preset Switched ===',
                    f'preset: {meta["label"]}',
                    str(meta['description']),
                ]
            )
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == 'local_role_mode' and event.value is not Select.NULL:
            self._update_role_visibility(str(event.value))

    def _update_role_visibility(self, mode: str) -> None:
        hidden_ids = set(_ROLE_HIDDEN_IDS.get(mode, []))
        all_togglable: list[str] = []
        for ids in _ROLE_HIDDEN_IDS.values():
            all_togglable.extend(ids)
        for selector in all_togglable:
            try:
                widget = self.query_one(selector)
                widget.visible = selector not in hidden_ids
            except Exception:
                pass

    def _collect_params(self) -> tuple[RadioParams, int, str, Path]:
        params = RadioParams.from_env()
        params.local_role_mode = self._select_value('#local_role_mode')
        params.freq = self._input_value('#freq')
        params.rate = self._input_value('#rate')
        params.tx_gain = self._input_value('#tx_gain')
        params.rx_gain = self._input_value('#rx_gain')
        params.tx_args = self._input_value('#tx_args')
        params.rx_args = self._input_value('#rx_args')
        tx_ctrl = self._input_value('#tx_control')
        if ':' in tx_ctrl:
            params.tx_control_host, params.tx_control_port = tx_ctrl.rsplit(':', 1)
        rx_ctrl = self._input_value('#rx_control')
        if ':' in rx_ctrl:
            params.rx_control_host, params.rx_control_port = rx_ctrl.rsplit(':', 1)
        params.remote_rx_ssh_target = self._input_value('#remote_rx_ssh_target')
        params.remote_rx_password = self._input_value('#remote_rx_password')
        params.remote_project_root = self._input_value('#remote_project_root')
        params.remote_rx_run_root = self._input_value('#remote_rx_run_root')
        params.chunk_bytes = self._input_value('#chunk_bytes')
        params = normalize_radio_params(params)
        self.params = RadioParams(**vars(params))
        self._set_input_value('#freq', _compact_number(params.freq))
        self._set_input_value('#rate', _compact_number(params.rate))
        self._set_input_value('#tx_gain', params.tx_gain)
        self._set_input_value('#rx_gain', params.rx_gain)
        self._set_input_value('#chunk_bytes', params.chunk_bytes)
        count = int(self._input_value('#count') or '1')
        run_id = self._input_value('#run_id') or default_run_id('tui')
        input_path = Path(self._input_value('#input')).expanduser()
        inferred = infer_baseline_preset(input_path)
        if inferred is not None:
            self.baseline_preset = inferred
            self._sync_baseline_buttons()
        return params, count, run_id, input_path

    def _set_status(self, message: str) -> None:
        w = self.query_one('#status', RichLog)
        w.clear()
        w.write(message)

    def _set_progress(self, message: str) -> None:
        w = self.query_one('#dashboard', RichLog)
        w.clear()
        w.write(message)

    def _set_persistent_widget(self, message: str) -> None:
        self._set_progress(message)

    def _render_dashboard_text(self) -> str:
        parts = []
        persistent_text = self._render_persistent_text()
        if persistent_text != '按 u 启动常驻服务':
            parts.append(persistent_text)
        progress_text = self._render_progress_text()
        if progress_text != '进度：未开始':
            if parts:
                parts.append('─' * 30)
            parts.append(progress_text)
        return '\n'.join(parts) if parts else '按 u 启动常驻服务'

    def _refresh_dashboard(self) -> None:
        w = self.query_one('#dashboard', RichLog)
        w.clear()
        w.write(self._render_dashboard_text())

    def _log(self, message: str, *, gap: bool = False) -> None:
        text = message.rstrip()
        log = self.query_one('#log', RichLog)
        if gap and self.log_has_content:
            log.write('')
        log.write(text)
        if text:
            self.log_has_content = True

    def _log_block(self, message: str) -> None:
        self._log(message, gap=True)

    def _call_from_thread_safe(self, callback, *args) -> None:
        if self._ui_closing:
            return
        try:
            self.call_from_thread(callback, *args)
        except Exception:
            pass

    def _mark_owned_persistent_roles(self, messages: list[str], params: RadioParams) -> None:
        owned: set[str] = set()
        for item in messages:
            text = str(item).strip()
            if text.startswith(('RX_pid=', 'RX_remote_started ')):
                owned.add('RX')
            elif text.startswith('TX_pid='):
                owned.add('TX')
        if owned:
            self._persistent_owned_roles.update(owned)
            self._persistent_owner_params = RadioParams(**vars(params))

    def _stop_owned_persistent_roles(self, *, log_to_ui: bool) -> None:
        if self._shutdown_cleanup_done:
            return
        if not self._persistent_owned_roles:
            self._shutdown_cleanup_done = True
            return
        params = self._persistent_owner_params
        if params is None:
            self._shutdown_cleanup_done = True
            return

        messages: list[str] = []
        if 'RX' in self._persistent_owned_roles:
            rx_stop = control_cmd(RX_CONTROL, params.rx_control_host, params.rx_control_port, 'quit', timeout='10')
            messages.append('RX ' + (rx_stop.stdout.strip() or f'rc={rx_stop.returncode}'))
        if 'TX' in self._persistent_owned_roles:
            tx_stop = control_cmd(TX_CONTROL, params.tx_control_host, params.tx_control_port, 'quit', timeout='10')
            messages.append('TX ' + (tx_stop.stdout.strip() or f'rc={tx_stop.returncode}'))

        self._persistent_owned_roles.clear()
        self._shutdown_cleanup_done = True
        if log_to_ui:
            self._log_block('=== Persistent RX/TX Auto Stop ===')
            for item in messages:
                self._log_block(self._format_persistent_line(item))

    def _atexit_cleanup(self) -> None:
        try:
            self._stop_owned_persistent_roles(log_to_ui=False)
        except Exception:
            pass

    def _reset_progress_state(self) -> None:
        self.progress_state = {
            'mode': 'idle',
            'target': 0,
            'processed': 0,
            'pass_count': 0,
            'pending': 0,
            'round': None,
            'batch_done': 0,
            'batch_total': 0,
            'started_monotonic': 0.0,
            'dry_run': False,
        }
        self._set_progress('进度：未开始')

    def _render_progress_text(self) -> str:
        mode = str(self.progress_state.get('mode', 'idle'))
        if mode == 'idle':
            return '进度：未开始'

        target = int(self.progress_state.get('target', 0) or 0)
        processed = min(int(self.progress_state.get('processed', 0) or 0), target) if target else 0
        pass_count = int(self.progress_state.get('pass_count', 0) or 0)
        pending = int(self.progress_state.get('pending', 0) or 0)
        round_idx = self.progress_state.get('round')
        batch_done = int(self.progress_state.get('batch_done', 0) or 0)
        batch_total = int(self.progress_state.get('batch_total', 0) or 0)
        dry_run = bool(self.progress_state.get('dry_run', False))

        if mode == 'done':
            elapsed = self.progress_state.get('elapsed_final', 0.0)
            per_image = self.progress_state.get('per_image_final', 0.0)
            all_pass = self.progress_state.get('all_pass', False)
            tag = '全部通过' if all_pass else f'{pass_count}/{target} 通过'
            lines = [
                f'已完成 {processed}/{target} | {tag}',
            ]
            if elapsed > 0:
                lines.append(f'总耗时 {format_sec_text(elapsed)}')
            if per_image > 0:
                lines.append(f'平均 {format_sec_text(per_image)}/张')
            return '\n'.join(lines)

        started = float(self.progress_state.get('started_monotonic', 0.0) or 0.0)
        elapsed_sec = max(0.0, time.monotonic() - started) if started > 0 else 0.0

        if dry_run:
            return '\n'.join(
                [
                    'Dry Run',
                    f'耗时 {format_sec_text(elapsed_sec)}',
                    '只做输入和命令编排检查，不进行 OTA 收发。',
                ]
            )

        percent = (processed / target * 100.0) if target > 0 else 0.0
        slots = 20
        filled = max(0, min(slots, int(round(percent / 100.0 * slots))))
        bar = '█' * filled + '·' * (slots - filled)
        round_text = f'第 {round_idx} 轮' if round_idx is not None else '轮次 -'
        batch_text = f'批次 {batch_done}/{batch_total}' if batch_total > 0 else '批次 -'
        return '\n'.join(
            [
                f'[{bar}] {percent:5.1f}%',
                f'已完成 {processed}/{target} | 通过 {pass_count} | 待处理 {pending}',
                f'{round_text} | {batch_text} | 耗时 {format_sec_text(elapsed_sec)}',
            ]
        )

    def _render_persistent_text(self) -> str:
        rx = self.persistent_snapshot.get('rx', 'unknown')
        tx = self.persistent_snapshot.get('tx', 'unknown')
        detail = self.persistent_snapshot.get('detail', '按 u 启动常驻服务')
        mode = self.persistent_snapshot.get('mode', self.params.local_role_mode)
        return '\n'.join(
            [
                f'模式: {ROLE_MODE_LABELS.get(str(mode), str(mode))}',
                f'RX: {rx}',
                f'TX: {tx}',
                detail,
            ]
        )

    def _parse_persistent_role_line(self, role: str, line: str) -> tuple[str, str]:
        text = str(line).strip()
        if 'unmanaged' in text:
            return ('unmanaged', text)
        body = text.removeprefix(f'{role} ').strip() if text.startswith(f'{role} ') else text
        if body.startswith('OK'):
            payload = body.removeprefix('OK').strip()
            kv = parse_key_value_tokens(payload)
            if role == 'RX':
                busy = kv.get('busy', '-')
                job_id = kv.get('job_id', '-')
                ok = kv.get('ok', '-')
                return ('alive', f'RX 就绪 busy={busy} job={job_id}')
            job_id = kv.get('job_id', '-')
            ok = kv.get('ok', '-')
            return ('alive', f'TX 就绪 ok={ok} job={job_id}')
        if 'ConnectionRefusedError' in text or 'ERR_CONNECTION_REFUSED' in text or 'connect' in text.lower():
            return ('offline', f'{role} 未连接')
        if 'ERR_TIMEOUT' in text or 'timed out' in text.lower():
            return ('busy', f'{role} 忙碌（超时）')
        return ('error', f'{role} 状态异常')

    def _refresh_persistent_tick(self) -> None:
        if self._ui_closing or not self._persistent_polling_active:
            return
        threading.Thread(target=self._poll_persistent_snapshot, daemon=True).start()

    def _poll_persistent_snapshot(self) -> None:
        params = RadioParams.from_env()
        try:
            current, _, _, _ = self._collect_params()
            params = current
        except Exception:
            pass
        status_lines = persistent_status(params)
        rx_line = status_lines[0] if status_lines else 'RX status unavailable'
        tx_line = status_lines[1] if len(status_lines) > 1 else 'TX status unavailable'
        rx_state, rx_detail = self._parse_persistent_role_line('RX', rx_line)
        tx_state, tx_detail = self._parse_persistent_role_line('TX', tx_line)
        snapshot = {
            'rx': rx_state,
            'tx': tx_state,
            'mode': params.local_role_mode,
            'detail': f'{rx_detail} | {tx_detail}',
        }
        self._call_from_thread_safe(self._update_persistent_snapshot, snapshot)

    def _update_persistent_snapshot(self, snapshot: dict[str, str]) -> None:
        self.persistent_snapshot = dict(snapshot)
        self._refresh_dashboard()

    def _scan_progress_from_fs(self) -> None:
        if self.current_run_root is None or not self.current_run_root.exists():
            return
        processed_dirs = {
            path.parent.name
            for path in self.current_run_root.glob('image_*/merge_round*.json')
        }
        processed = len(processed_dirs)
        if processed > int(self.progress_state.get('processed', 0) or 0):
            self.progress_state['processed'] = processed

        round_dirs: list[tuple[int, Path]] = []
        for path in self.current_run_root.glob('round*'):
            if not path.is_dir():
                continue
            suffix = path.name.removeprefix('round')
            if suffix.isdigit():
                round_dirs.append((int(suffix), path))
        if round_dirs:
            round_idx, round_path = max(round_dirs, key=lambda item: item[0])
            self.progress_state['round'] = round_idx
            batch_seen = len([item for item in round_path.glob('batch_*') if item.is_dir()])
            if batch_seen > int(self.progress_state.get('batch_done', 0) or 0):
                self.progress_state['batch_done'] = batch_seen

    def _refresh_progress_tick(self) -> None:
        if self.progress_state.get('mode') == 'idle':
            return
        if self.proc is None or self.proc.poll() is not None:
            return
        self._scan_progress_from_fs()
        self._refresh_dashboard()

    def _ingest_runner_progress(self, line: str) -> None:
        text = line.strip()
        if text.startswith('round='):
            try:
                round_idx = int(text.split('=', 1)[1])
            except ValueError:
                return
            self.progress_state['round'] = round_idx
            self.progress_state['batch_done'] = 0
            self.progress_state['batch_total'] = 0
            self._refresh_dashboard()
            return
        if text.startswith('batch_progress '):
            kv = parse_key_value_tokens(text)
            batch_token = kv.get('batch', '')
            if '/' in batch_token:
                done_text, total_text = batch_token.split('/', 1)
                if done_text.isdigit():
                    self.progress_state['batch_done'] = int(done_text)
                if total_text.isdigit():
                    self.progress_state['batch_total'] = int(total_text)
            processed_token = kv.get('processed', '')
            if '/' in processed_token:
                done_text, total_text = processed_token.split('/', 1)
                if done_text.isdigit():
                    self.progress_state['processed'] = int(done_text)
                if total_text.isdigit():
                    self.progress_state['target'] = int(total_text)
            if kv.get('round', '').isdigit():
                self.progress_state['round'] = int(kv['round'])
            if kv.get('pass', '').isdigit():
                self.progress_state['pass_count'] = int(kv['pass'])
            if kv.get('pending', '').isdigit():
                self.progress_state['pending'] = int(kv['pending'])
            self._refresh_dashboard()
            return
        if text.startswith('round_result '):
            kv = parse_key_value_tokens(text)
            if kv.get('pass', '').isdigit():
                self.progress_state['pass_count'] = int(kv['pass'])
            if kv.get('fail', '').isdigit():
                self.progress_state['pending'] = int(kv['fail'])
            self._refresh_dashboard()

    def _format_status_overview(
        self,
        *,
        phase: str,
        run_id: str,
        count: int,
        input_path: Path,
        input_bytes: int | None,
        params: RadioParams,
        dry_run: bool,
        batch_size: str,
        decode_backend: str,
        cpp_sync_mode: str,
        result_line: str = '',
        timing_line: str = '',
    ) -> str:
        lines = [
            f'状态：{phase}',
            f'run_id={run_id}',
            f'role={ROLE_MODE_LABELS.get(params.local_role_mode, params.local_role_mode)}',
            format_payload_line(
                str(self.current_job_meta.get('payload_label', input_path.name)),
                input_bytes,
                count,
                self.current_job_meta.get('source_count') if isinstance(self.current_job_meta.get('source_count'), int) else None,
            ),
            (
                f'{format_hz_text(params.freq)} / {format_hz_text(params.rate, suffix="Sps")} / '
                f'TX {params.tx_gain} dB / RX {params.rx_gain} dB'
            ),
            f'chunk {params.chunk_bytes} B / batch {batch_size} / {decode_backend}-{cpp_sync_mode}',
            f'ctrl: TX {params.tx_control_host}:{params.tx_control_port} | RX {params.rx_control_host}:{params.rx_control_port}',
        ]
        if dry_run:
            lines.append('dry-run: 只做命令与输入编排检查，不实际发射。')
        if result_line:
            lines.append(result_line)
        if timing_line:
            lines.append(timing_line)
        return '\n'.join(lines)

    def _format_run_start_log(self, meta: dict[str, object]) -> str:
        params = meta['params']
        assert isinstance(params, RadioParams)
        lines = [
            '=== USRP Batch Start ===',
            f"run_id: {meta['run_id']}",
            f"mode: {'dry-run' if meta['dry_run'] else 'ota batch'} / count={meta['count']}",
            f"role: {ROLE_MODE_LABELS.get(params.local_role_mode, params.local_role_mode)}",
            "payload: "
            + format_payload_line(
                str(meta.get('payload_label', Path(str(meta['input_path'])).name)),
                meta.get('input_bytes') if isinstance(meta.get('input_bytes'), int) else None,
                int(meta['count']),
                meta.get('source_count') if isinstance(meta.get('source_count'), int) else None,
            ).removeprefix('payload='),
            (
                f"radio: {format_hz_text(params.freq)} / {format_hz_text(params.rate, suffix='Sps')} / "
                f"TX {params.tx_gain} dB / RX {params.rx_gain} dB"
            ),
            (
                f"phy: chunk {params.chunk_bytes} B / batch {meta['batch_size']} / "
                f"{meta['decode_backend']}-{meta['cpp_sync_mode']} / artifact {meta['artifact_mode']} / "
                f"fast-arq={'on' if meta['fast_arq_profile'] else 'off'} / "
                f"rx_capture_mode={meta.get('rx_capture_mode', '-')}"
            ),
            f"baseline: {meta.get('baseline_label', 'custom input')}",
            f'device: TX {params.tx_args} | RX {params.rx_args}',
            f'control: TX {params.tx_control_host}:{params.tx_control_port} | RX {params.rx_control_host}:{params.rx_control_port}',
            f'remote_rx: {params.remote_rx_ssh_target or "-"} | remote_run_root: {params.remote_rx_run_root}',
            f"output: {meta['run_root']}",
        ]
        return '\n'.join(lines)

    def _format_runner_line(self, line: str) -> str | None:
        text = line.strip()
        if text == '':
            return None
        if text.startswith('round='):
            return f"ARQ Round {text.split('=', 1)[1]} 开始。"
        if text.startswith('round_result '):
            kv = parse_key_value_tokens(text)
            return (
                f"ARQ Round {kv.get('round', '?')} 结果："
                f"PASS {kv.get('pass', '?')} / FAIL {kv.get('fail', '?')}"
            )
        if text.startswith('batch_progress '):
            kv = parse_key_value_tokens(text)
            return (
                f"Batch Progress: round {kv.get('round', '?')} | "
                f"batch {kv.get('batch', '?')} | "
                f"processed {kv.get('processed', '?')} | "
                f"pass {kv.get('pass', '?')} | pending {kv.get('pending', '?')}"
            )
        if text.startswith('remote_rx_pull '):
            kv = parse_key_value_tokens(text)
            return (
                f"Remote RX 回传：round {kv.get('round', '?')} | "
                f"batch {kv.get('batch', '?')} | "
                f"target {kv.get('target', '?')} | "
                f"wall {kv.get('wall_sec', '?')} s"
            )
        if text.startswith('batch_spool_summary='):
            summary_path = text.split('=', 1)[1].strip()
            return f'汇总文件已写入：{Path(summary_path).name}'
        if text.startswith(('completed_count=', 'pass_count=', 'fail_count=', 'all_pass=', 'dry_run=')):
            return None
        return text

    def _format_persistent_line(self, line: str) -> str:
        text = line.strip()
        if text == 'persistent_status=ready':
            return '常驻 RX/TX 已就绪。'
        if text.endswith('already running'):
            return text.replace('already running', '已在运行')
        if text.startswith('RX_remote_started '):
            kv = parse_key_value_tokens(text)
            return '\n'.join(
                [
                    f'[RX remote] target={kv.get("target", "-")} 已发起拉起',
                    f'log: {Path(kv.get("remote_log", "-")).name} | boot: {Path(kv.get("boot_log", "-")).name}',
                ]
            )
        if 'unmanaged role=local-rx' in text:
            return 'TX 未由当前 TUI 管理（Local RX 模式）。'
        if text.startswith('persistent_') and '_error=' in text:
            _, _, payload = text.partition('=')
            return f'Persistent 操作失败：{payload}'
        if text.startswith(('RX OK ', 'TX OK ')):
            role, _, payload = text.partition(' ')
            payload = payload.removeprefix('OK ').strip()
            kv = parse_key_value_tokens(payload)
            file_name = Path(kv.get('file', '')).name if kv.get('file') else '-'
            if role == 'RX':
                return '\n'.join(
                    [
                        f'[RX] busy={kv.get("busy", "-")} ok={kv.get("ok", "-")} job={kv.get("job_id", "-")} file={file_name}',
                        (
                            f'samples: {kv.get("written_samps", "-")} / {kv.get("target_samps", "-")} | '
                            f'timeouts={kv.get("timeouts", "-")} overflows={kv.get("overflows", "-")} | '
                            f'wall={kv.get("wall_sec", "-")} s'
                        ),
                    ]
                )
            return '\n'.join(
                [
                    f'[TX] ok={kv.get("ok", "-")} job={kv.get("job_id", "-")} file={file_name}',
                    f'samples: {kv.get("sent_samps", "-")} / {kv.get("target_samps", "-")} | wall={kv.get("wall_sec", "-")} s',
                ]
            )
        return text

    def _format_run_finish_log(self, rc: int, summary: dict | None) -> str:
        if not summary:
            return f'=== USRP Batch End ===\nresult: rc={rc}\nsummary: unavailable'
        rounds = summary.get('rounds') or []
        rounds_executed = len(rounds)
        retransmissions = max(0, rounds_executed - 1)
        mean_sec, median_sec = extract_duration_stats(summary)
        lines = [
            '=== USRP Batch Result ===',
            (
                f"result: PASS {summary.get('pass_count', 0)} / {summary.get('completed_count', 0)}"
                f" | FAIL {summary.get('fail_count', 0)} | all_pass={summary.get('all_pass', False)} | rc={rc}"
            ),
            (
                f"payload: mean {format_bytes_text(summary.get('compared_transmitted_bytes_mean'))} / image"
                f" | rounds_executed={rounds_executed}"
                f" | retransmission={'yes' if retransmissions else 'no'}"
            ),
        ]
        if not summary.get('dry_run'):
            lines.append(
                (
                    f"timing: total {format_sec_text(summary.get('elapsed_sec'))}"
                    f" | wall mean {format_sec_text(mean_sec)} / image"
                    f" | wall median {format_sec_text(median_sec)} / image"
                    f" | airtime {format_ms_text(summary.get('payload_airtime_ms_mean'))} / image"
                )
            )
            lines.append(
                (
                    f"decode: {format_ms_text((summary.get('decode_total_wall_sec_mean') or 0.0) * 1000.0)} / image"
                    f" | merge: {format_ms_text((summary.get('merge_wall_sec_mean') or 0.0) * 1000.0)} / image"
                )
            )
        lines.append(f"summary: {Path(str(summary.get('run_root', ''))).name or '-'}")
        return '\n'.join(lines)

    def _start_batch(self, *, count_override: int | None = None, dry_run: bool = False) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self._log('已有任务正在运行；请先停止或等待结束。')
            return

        try:
            params, count, run_id, input_path = self._collect_params()
        except ValueError as exc:
            self._log(f'参数错误: {exc}')
            return
        if params.local_role_mode == 'local-rx':
            self._log_block('Local RX 模式只用于 RX helper / 排障；批量发送请在 TX 端使用 Local TX 或 Local RX/TX 模式。')
            return

        if count_override is not None:
            count = count_override
        if count <= 0:
            self._log_block('count 必须为正整数。')
            return
        if not input_path.exists():
            self._log_block(f'input 不存在: {input_path}')
            return
        rx_ready = control_ok(RX_CONTROL, params.rx_control_host, params.rx_control_port)
        tx_ready = control_ok(TX_CONTROL, params.tx_control_host, params.tx_control_port)
        if not dry_run and (not rx_ready or not tx_ready):
            self._log_block(
                '\n'.join(
                    [
                        '常驻链路尚未就绪；请先按 `u` 启动。',
                        f'role={ROLE_MODE_LABELS.get(params.local_role_mode, params.local_role_mode)}',
                        f'rx_ready={rx_ready} tx_ready={tx_ready}',
                    ]
                )
            )
            return
        input_args, payload_label, input_bytes, source_count = build_input_source_args(input_path)
        inferred_preset = infer_baseline_preset(input_path)
        baseline_label = str(get_baseline_preset_meta(inferred_preset)['label']) if inferred_preset else 'Custom input'

        cmd = [
            sys.executable,
            str(DEFAULT_BATCH_RUNNER),
            '--count',
            str(count),
            '--run-id',
            run_id,
            '--run-root',
            str(DEFAULT_RUN_ROOT),
            '--max-arq-rounds',
            self.params.max_arq_rounds,
            '--chunk-bytes',
            params.chunk_bytes or self.args.chunk_bytes,
            '--batch-size',
            self._input_value('#batch_size') or str(self.args.batch_size),
            '--decode-workers',
            self._input_value('#decode_workers') or str(self.args.decode_workers),
            '--decode-backend',
            self._select_value('#decode_backend') or self.args.decode_backend,
            '--cpp-sync-mode',
            self._select_value('#cpp_sync_mode') or self.args.cpp_sync_mode,
            '--artifact-mode',
            self._select_value('#artifact_mode') or self.args.artifact_mode,
            '--stop-on-fail',
        ]
        cmd.extend(input_args)
        if self.args.fast_arq_profile:
            cmd.append('--fast-arq-profile')
        if dry_run:
            cmd.append('--dry-run')

        env = os.environ.copy()
        env.update(build_batch_env(params))
        self.current_run_root = DEFAULT_RUN_ROOT / run_id
        self.current_job_meta = {
            'run_id': run_id,
            'count': count,
            'input_path': str(input_path),
            'input_bytes': input_bytes,
            'payload_label': payload_label,
            'source_count': source_count,
            'baseline_label': baseline_label,
            'params': params,
            'dry_run': dry_run,
            'run_root': str(self.current_run_root),
            'batch_size': self._input_value('#batch_size') or str(self.args.batch_size),
            'decode_workers': self._input_value('#decode_workers') or str(self.args.decode_workers),
            'decode_backend': self._select_value('#decode_backend') or self.args.decode_backend,
            'cpp_sync_mode': self._select_value('#cpp_sync_mode') or self.args.cpp_sync_mode,
            'artifact_mode': self._select_value('#artifact_mode') or self.args.artifact_mode,
            'fast_arq_profile': self.args.fast_arq_profile,
            'rx_capture_mode': 'remote-decode' if role_uses_remote_rx(params.local_role_mode) else 'local',
        }
        batch_size = int(str(self.current_job_meta['batch_size']))
        batch_total = (count + batch_size - 1) // batch_size if batch_size > 0 else 0
        self.progress_state = {
            'mode': 'running',
            'target': count,
            'processed': 0,
            'pass_count': 0,
            'pending': count,
            'round': 0,
            'batch_done': 0,
            'batch_total': batch_total,
            'started_monotonic': time.monotonic(),
            'dry_run': dry_run,
        }
        self._set_status(
            self._format_status_overview(
                phase='运行中',
                run_id=run_id,
                count=count,
                input_path=input_path,
                input_bytes=input_bytes,
                params=params,
                dry_run=dry_run,
                batch_size=str(self.current_job_meta['batch_size']),
                decode_backend=str(self.current_job_meta['decode_backend']),
                cpp_sync_mode=str(self.current_job_meta['cpp_sync_mode']),
            )
        )
        self._refresh_dashboard()
        self._log_block(self._format_run_start_log(self.current_job_meta))
        self.proc_thread = threading.Thread(target=self._run_subprocess, args=(cmd, env), daemon=True)
        self.proc_thread.start()

    def _run_subprocess(self, cmd: list[str], env: dict[str, str]) -> None:
        self.proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            raw = line.rstrip()
            self._call_from_thread_safe(self._ingest_runner_progress, raw)
            formatted = self._format_runner_line(raw)
            if formatted is not None:
                self._call_from_thread_safe(self._log_block, formatted)
        rc = self.proc.wait()
        self._call_from_thread_safe(self._finish_subprocess, rc)

    def _finish_subprocess(self, rc: int) -> None:
        summary_text = ''
        summary: dict | None = None
        if self.current_run_root is not None:
            summary_path = self.current_run_root / 'batch_spool_summary.json'
            if summary_path.is_file():
                summary = read_summary(summary_path)
                summary_text = (
                    f" completed={summary.get('completed_count', 0)}"
                    f" pass={summary.get('pass_count', 0)}"
                    f" fail={summary.get('fail_count', 0)}"
                    f" all_pass={summary.get('all_pass', False)}"
                )
        input_path = Path(str(self.current_job_meta.get('input_path', DEFAULT_INPUT)))
        params = self.current_job_meta.get('params')
        if isinstance(params, RadioParams):
            result_line = f"结果：PASS {summary.get('pass_count', 0)} / {summary.get('completed_count', 0)} | FAIL {summary.get('fail_count', 0)} | rc={rc}" if summary else f'结果：rc={rc}'
            timing_line = ''
            if summary and not summary.get('dry_run'):
                mean_sec, median_sec = extract_duration_stats(summary)
                timing_line = (
                    f"wall mean {format_sec_text(mean_sec)}/image | "
                    f"wall median {format_sec_text(median_sec)}/image | "
                    f"airtime {format_ms_text(summary.get('payload_airtime_ms_mean'))}/image"
                )
            self._set_status(
                self._format_status_overview(
                    phase='结束',
                    run_id=str(self.current_job_meta.get('run_id', '-')),
                    count=int(self.current_job_meta.get('count', 0) or 0),
                    input_path=input_path,
                    input_bytes=self.current_job_meta.get('input_bytes') if isinstance(self.current_job_meta.get('input_bytes'), int) else None,
                    params=params,
                    dry_run=bool(self.current_job_meta.get('dry_run', False)),
                    batch_size=str(self.current_job_meta.get('batch_size', '-')),
                    decode_backend=str(self.current_job_meta.get('decode_backend', '-')),
                    cpp_sync_mode=str(self.current_job_meta.get('cpp_sync_mode', '-')),
                    result_line=result_line,
                    timing_line=timing_line,
                )
            )
        else:
            self._set_status(f'状态：结束 rc={rc}{summary_text}')
        if summary:
            self.progress_state['mode'] = 'done'
            self.progress_state['processed'] = int(summary.get('completed_count', 0) or 0)
            self.progress_state['target'] = int(summary.get('target_count', 0) or self.progress_state.get('target', 0) or 0)
            self.progress_state['pass_count'] = int(summary.get('pass_count', 0) or 0)
            self.progress_state['pending'] = int(summary.get('fail_count', 0) or 0)
            self.progress_state['elapsed_final'] = float(summary.get('elapsed_sec', 0) or 0)
            self.progress_state['per_image_final'] = float(summary.get('per_image_sec', 0) or 0)
            self.progress_state['all_pass'] = bool(summary.get('all_pass', False))
            rounds = summary.get('rounds') or []
            self.progress_state['round'] = (len(rounds) - 1) if rounds else self.progress_state.get('round')
            if rounds:
                last_round = rounds[-1]
                self.progress_state['batch_done'] = int(last_round.get('batch_count', 0) or 0)
                self.progress_state['batch_total'] = int(last_round.get('batch_count', 0) or 0)
        else:
            self.progress_state['mode'] = 'done'
        self._refresh_dashboard()
        self._log_block(self._format_run_finish_log(rc, summary))
        self.proc = None
        self.current_job_meta = {}

    def action_quit(self) -> None:
        self._ui_closing = True
        if self.proc is not None and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self._stop_owned_persistent_roles(log_to_ui=False)
        self.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'dry_run':
            self._start_batch(dry_run=True)
        elif event.button.id == 'single':
            self._start_batch(count_override=1)
        elif event.button.id == 'batch':
            self._start_batch()
        elif event.button.id == 'persistent_start':
            self.action_persistent_start()
        elif event.button.id == 'persistent_status':
            self.action_persistent_status()
        elif event.button.id == 'persistent_stop':
            self.action_persistent_stop()
        elif event.button.id == 'preset_webp':
            self._apply_baseline_preset('webp')
        elif event.button.id == 'preset_stress':
            self._apply_baseline_preset('stress')
        elif event.button.id == 'help':
            self.action_show_help()
        elif event.button.id == 'stop':
            self.action_stop()

    def action_dry_run(self) -> None:
        self._start_batch(dry_run=True)

    def action_single(self) -> None:
        self._start_batch(count_override=1)

    def action_batch(self) -> None:
        self._start_batch()

    def action_show_help(self) -> None:
        self.push_screen(UsrpHelpScreen())

    def _run_persistent_action(self, action: str) -> None:
        def worker() -> None:
            params = RadioParams.from_env()
            try:
                current, _, _, _ = self._collect_params()
                params = current
            except ValueError:
                pass
            try:
                if action == 'start':
                    self._persistent_polling_active = True
                    self._call_from_thread_safe(
                        self._log_block,
                        '\n'.join(
                            [
                                '=== Persistent Start ===',
                                f'role: {ROLE_MODE_LABELS.get(params.local_role_mode, params.local_role_mode)}',
                                (
                                    f"radio: {format_hz_text(params.freq)} / {format_hz_text(params.rate, suffix='Sps')} / "
                                    f"TX {params.tx_gain} dB / RX {params.rx_gain} dB"
                                ),
                                f'device: TX {params.tx_args} | RX {params.rx_args}',
                                f'control: TX {params.tx_control_host}:{params.tx_control_port} | RX {params.rx_control_host}:{params.rx_control_port}',
                                f'remote_rx_target: {params.remote_rx_ssh_target or "-"}',
                            ]
                        ),
                    )

                    def mark_owned(roles: set[str]) -> None:
                        self._persistent_owned_roles.update(roles)
                        self._persistent_owner_params = RadioParams(**vars(params))
                        self._shutdown_cleanup_done = False

                    messages = start_persistent_rxtx(params, on_ownership=mark_owned)
                    self._mark_owned_persistent_roles(messages, params)
                elif action == 'stop':
                    self._persistent_polling_active = True
                    messages = stop_persistent_rxtx(params)
                    self._persistent_owned_roles.clear()
                    self._persistent_owner_params = None
                    self._shutdown_cleanup_done = False
                else:
                    self._persistent_polling_active = True
                    messages = persistent_status(params)
            except Exception as exc:
                messages = [f'persistent_{action}_error={exc}']
            for item in messages:
                self._call_from_thread_safe(self._log_block, self._format_persistent_line(item))
            self._call_from_thread_safe(self._set_status, f'状态：persistent {action} done')
            self._call_from_thread_safe(self._refresh_persistent_tick)

        self._set_status(f'状态：persistent {action}...')
        threading.Thread(target=worker, daemon=True).start()

    def action_persistent_start(self) -> None:
        self._run_persistent_action('start')

    def action_persistent_status(self) -> None:
        self._run_persistent_action('status')

    def action_persistent_stop(self) -> None:
        self._run_persistent_action('stop')

    def action_stop(self) -> None:
        if self.proc is None or self.proc.poll() is not None:
            self._log_block('没有正在运行的任务。')
            return
        self._log_block('stopping process group...')
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        self.progress_state['mode'] = 'stopping'
        self._refresh_dashboard()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='USRP292x Textual TUI / smoke runner.')
    parser.add_argument('--smoke', action='store_true', help='check imports and local entry files, then exit')
    parser.add_argument('--selftest-auto-stop', action='store_true', help='start persistent RX/TX inside TUI test mode, quit app, then verify auto-stop')
    parser.add_argument('--dry-run', action='store_true', help='run batch runner in dry-run mode, then exit')
    parser.add_argument('--start-persistent-rxtx', action='store_true', help='start persistent services according to USRP_LOCAL_ROLE_MODE, then exit')
    parser.add_argument('--stop-persistent-rxtx', action='store_true', help='stop persistent services according to USRP_LOCAL_ROLE_MODE, then exit')
    parser.add_argument('--persistent-status', action='store_true', help='query persistent services according to USRP_LOCAL_ROLE_MODE, then exit')
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--run-id', default=default_run_id('tui_cli'))
    parser.add_argument('--run-root', type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument('--baseline-preset', choices=('webp', 'stress'), default='webp')
    parser.add_argument('--input', type=Path, default=None)
    parser.add_argument('--max-arq-rounds', type=int, default=2)
    parser.add_argument('--chunk-bytes', type=int, default=2048)
    parser.add_argument('--batch-size', type=int, default=6)
    parser.add_argument('--decode-workers', type=int, default=2)
    parser.add_argument('--decode-backend', choices=('python', 'cpp'), default='cpp')
    parser.add_argument('--cpp-sync-mode', choices=('header', 'hybrid', 'sync'), default='header')
    parser.add_argument('--artifact-mode', choices=('minimal', 'full', 'board'), default='minimal')
    parser.add_argument('--fast-arq-profile', dest='fast_arq_profile', action='store_true')
    parser.add_argument('--no-fast-arq-profile', dest='fast_arq_profile', action='store_false')
    parser.add_argument('--stop-on-fail', action='store_true')
    parser.set_defaults(fast_arq_profile=DEFAULT_FAST_ARQ_PROFILE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    problems = check_ready()
    if args.smoke:
        if problems:
            for item in problems:
                print(f'usrp_tui_problem={item}')
            return 2
        try:
            composed = asyncio.run(compose_smoke(args))
        except Exception as exc:
            print(f'usrp_tui_problem=compose_failed: {exc}')
            return 2
        print('usrp_tui_smoke=PASS')
        print(f'batch_runner={DEFAULT_BATCH_RUNNER}')
        print(f'default_baseline_preset={args.baseline_preset}')
        print(f'default_input={resolve_effective_input_path(args)}')
        print(f'default_run_root={DEFAULT_RUN_ROOT}')
        print(f'default_chunk_bytes={args.chunk_bytes}')
        print(f'default_decode_backend={args.decode_backend}')
        print(f'default_artifact_mode={args.artifact_mode}')
        print(f'default_fast_arq_profile={args.fast_arq_profile}')
        print('compose_widgets=' + ','.join(composed))
        return 0
    if args.selftest_auto_stop:
        if problems:
            for item in problems:
                print(f'usrp_tui_problem={item}')
            return 2
        result = asyncio.run(auto_stop_selftest(args))
        print('usrp_tui_auto_stop_started_ready=' + str(result['started_ready']).lower())
        print('usrp_tui_auto_stop_post_rx_alive=' + str(result['post_rx_alive']).lower())
        print('usrp_tui_auto_stop_post_tx_alive=' + str(result['post_tx_alive']).lower())
        for item in result['pre_messages']:
            print('usrp_tui_auto_stop_pre=' + str(item))
        for item in result['post_messages']:
            print('usrp_tui_auto_stop_post=' + str(item))
        return 0 if result['started_ready'] and not result['post_rx_alive'] and not result['post_tx_alive'] else 2
    if args.start_persistent_rxtx or args.stop_persistent_rxtx or args.persistent_status:
        return run_noninteractive(args, dry_run=False)
    if args.dry_run:
        return run_noninteractive(args, dry_run=True)

    app = UsrpTui(RadioParams.from_env(), args)
    app.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
