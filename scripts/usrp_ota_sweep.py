#!/usr/bin/env python3
"""usrp_ota_sweep.py — 本地 TX + 远端 RX 的 OTA 编排与扫参工具

用途：
  1. 固化本地 `usrp_tensor_tx` + 远端板端 `usrp_tensor_rx` 的启动节奏
  2. 对 wait / start-pad / rate / spb / repeat / frame-repeat 做参数扫描
  3. 自动收集 TX/RX 日志、远端输出文件与 SHA256，便于复现实验窗口

典型用法：
  source .venv/bin/activate
  python scripts/usrp_ota_sweep.py \
      --file usrp_tensor/build/test_1kb.bin \
      --rates 1000000 \
      --waits 0.4,0.5 \
      --start-pads 100000,200000 \
      --repeats 4 \
      --frame-repeats 1 \
      --stop-on-success
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / 'artifacts' / 'usrp_ota_trials'


@dataclass(frozen=True)
class TrialConfig:
    """单次 OTA 试验参数。"""

    rate: float
    wait_s: float
    start_pad_samps: int
    repeat: int
    frame_repeat: int
    spb: int
    setup: float
    decode_workers: int
    no_frame_timeout: float
    tx_gain: float
    rx_gain: float
    warmup_frames: int
    warmup_repeats: int
    warmup_rounds: int
    round_gap_ms: int
    tail_pad_samps: int
    first_frame_extra_repeats: int
    last_frame_extra_repeats: int
    payload_search_order: str
    frame_order: str

    def slug(self) -> str:
        """返回简短文件名标签。"""
        rate_ksps = int(round(self.rate / 1000.0))
        wait_ms = int(round(self.wait_s * 1000.0))
        setup_ms = int(round(self.setup * 1000.0))
        tx_gain_tag = int(round(self.tx_gain))
        rx_gain_tag = int(round(self.rx_gain))
        order_tag = self.payload_search_order.replace('-', '')
        frame_order_tag = self.frame_order.replace('-', '')
        return (
            f'r{rate_ksps}k_w{wait_ms}ms_pad{self.start_pad_samps}'
            f'_rep{self.repeat}_fr{self.frame_repeat}'
            f'_spb{self.spb}_setup{setup_ms}ms_dw{self.decode_workers}'
            f'_txg{tx_gain_tag}_rxg{rx_gain_tag}'
            f'_ffr{self.first_frame_extra_repeats}'
            f'_gap{self.round_gap_ms}ms'
            f'_ps{order_tag}'
            f'_fo{frame_order_tag}'
        )


def parse_float_list(raw: str) -> list[float]:
    """解析逗号分隔的浮点列表。"""
    return [float(item.strip()) for item in raw.split(',') if item.strip()]


def parse_int_list(raw: str) -> list[int]:
    """解析逗号分隔的整数列表。"""
    return [int(item.strip()) for item in raw.split(',') if item.strip()]


def sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    digest = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, record: dict[str, object]) -> None:
    """追加写入 JSONL 汇总记录。"""
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def build_sweep_replay_command(
    args: argparse.Namespace,
    config: TrialConfig,
) -> str:
    """生成当前参数组的单次复现命令。"""
    cmd = [
        'python3',
        'scripts/usrp_ota_sweep.py',
        '--file', str(args.file),
        '--board-host', args.board_host,
        '--board-user', args.board_user,
        '--remote-build-dir', args.remote_build_dir,
        '--local-serial-args', args.local_serial_args,
        '--remote-serial-args', args.remote_serial_args,
        '--remote-rx-ant', args.remote_rx_ant,
        '--freq', str(args.freq),
        '--rates', str(config.rate),
        '--waits', str(config.wait_s),
        '--start-pads', str(config.start_pad_samps),
        '--repeats', str(config.repeat),
        '--frame-repeats', str(config.frame_repeat),
        '--spbs', str(config.spb),
        '--setups', str(config.setup),
        '--decode-workers', str(config.decode_workers),
        '--no-frame-timeouts', str(config.no_frame_timeout),
        '--tx-gain', str(config.tx_gain),
        '--rx-gain', str(config.rx_gain),
        '--warmup-frames', str(config.warmup_frames),
        '--warmup-repeats', str(config.warmup_repeats),
        '--warmup-rounds', str(config.warmup_rounds),
        '--round-gap-ms', str(config.round_gap_ms),
        '--tail-pad-samps', str(config.tail_pad_samps),
        '--first-frame-extra-repeats', str(config.first_frame_extra_repeats),
        '--last-frame-extra-repeats', str(config.last_frame_extra_repeats),
        '--payload-search-orders', config.payload_search_order,
        '--frame-orders', config.frame_order,
        '--attempts-per-config', '1',
        '--fetch-output',
    ]
    return shlex.join(cmd)


def build_e2e_ota_command(
    args: argparse.Namespace,
    config: TrialConfig,
) -> str:
    """生成可复用到 e2e_usrp.py 的 OTA 参数模板。"""
    cmd = [
        'python3',
        'scripts/e2e_usrp.py',
        '--mode', 'ota',
        '--input', '<INPUT>',
        '--tx-args', args.local_serial_args,
        '--rx-args', args.remote_serial_args,
        '--rx-ant', args.remote_rx_ant,
        '--tx-gain', str(config.tx_gain),
        '--rx-gain', str(config.rx_gain),
        '--rate', str(config.rate),
        '--freq', str(args.freq),
        '--repeat', str(config.repeat),
        '--ota-wait', str(config.wait_s),
        '--start-pad-samps', str(config.start_pad_samps),
        '--frame-repeat', str(config.frame_repeat),
        '--rx-spb', str(config.spb),
        '--rx-setup', str(config.setup),
        '--decode-workers', str(config.decode_workers),
        '--no-frame-timeout', str(config.no_frame_timeout),
        '--warmup-frames', str(config.warmup_frames),
        '--warmup-repeats', str(config.warmup_repeats),
        '--warmup-rounds', str(config.warmup_rounds),
        '--round-gap-ms', str(config.round_gap_ms),
        '--tail-pad-samps', str(config.tail_pad_samps),
        '--first-frame-extra-repeats', str(config.first_frame_extra_repeats),
        '--last-frame-extra-repeats', str(config.last_frame_extra_repeats),
        '--frame-order', str(config.frame_order),
    ]
    return shlex.join(cmd)


def build_trial_record(
    args: argparse.Namespace,
    config: TrialConfig,
    result: dict[str, object],
    local_size: int,
    local_sha: str,
    trial_index: int,
) -> dict[str, object]:
    """生成单次 trial 的机器可读记录。"""
    remote_size = int(result['remote_size'])
    success = bool(result['success'])
    return {
        'trial_index': trial_index,
        'trial_name': result['trial_name'],
        'success': success,
        'summary': result['summary'],
        'trial_dir': str(result['trial_dir']),
        'local_file': str(args.file),
        'local_size': local_size,
        'local_sha256': local_sha,
        'remote_exists': bool(result['remote_exists']),
        'remote_size': remote_size,
        'remote_sha256': result['remote_sha'],
        'size_match': remote_size == local_size,
        'sha_match': bool(result['remote_exists']) and result['remote_sha'] == local_sha,
        'tx_rc': int(result['tx_rc']),
        'rx_rc': int(result['rx_rc']),
        'rx_elapsed_sec': float(result['rx_elapsed_sec']),
        'decode_search_dt_sec': float(result['decode_search_dt_sec']),
        'decode_search_order': result['decode_search_order'],
        'decode_search_ok': bool(result['decode_search_ok']),
        'frames_ok': int(result['frames_ok']),
        'frames_duplicate': int(result['frames_duplicate']),
        'frames_bad_crc': int(result['frames_bad_crc']),
        'frames_bad_hdr': int(result['frames_bad_hdr']),
        'frames_fec_fail': int(result['frames_fec_fail']),
        'max_payload_seen': int(result['max_payload_seen']),
        'expected_totlen_seen': int(result['expected_totlen_seen']),
        'max_unique_seen': int(result['max_unique_seen']),
        'pass_reported': bool(result['pass_reported']),
        'config': asdict(config),
        'replay_command': build_sweep_replay_command(args, config),
        'e2e_ota_command': build_e2e_ota_command(args, config),
    }


def trial_score(record: dict[str, object]) -> tuple[int, int, int, int]:
    """用于挑选当前最优窗口：优先完整成功，否则按恢复覆盖度排序。"""
    return (
        1 if bool(record['success']) else 0,
        int(record.get('max_payload_seen', 0)),
        int(record.get('max_unique_seen', 0)),
        int(record.get('frames_ok', 0)),
    )


def write_overview(
    path: Path,
    total_trials: int,
    success_trials: int,
    best_record: dict[str, object] | None,
) -> None:
    """写出本次 sweep 的文本总览。"""
    lines = [
        f'total_trials={total_trials}',
        f'success_trials={success_trials}',
    ]

    if best_record is not None:
        lines.extend([
            f'best_trial={best_record["trial_name"]}',
            f'best_success={int(bool(best_record["success"]))}',
            f'best_remote_size={best_record["remote_size"]}',
            f'best_size_match={int(bool(best_record["size_match"]))}',
            f'best_sha_match={int(bool(best_record["sha_match"]))}',
            f'best_frames_ok={best_record.get("frames_ok", 0)}',
            f'best_max_unique_seen={best_record.get("max_unique_seen", 0)}',
            f'best_max_payload_seen={best_record.get("max_payload_seen", 0)}',
            f'best_expected_totlen_seen={best_record.get("expected_totlen_seen", 0)}',
            f'best_pass_reported={int(bool(best_record.get("pass_reported", False)))}',
            'replay_command:',
            str(best_record['replay_command']),
            'e2e_ota_command:',
            str(best_record['e2e_ota_command']),
        ])

    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build_ssh_prefix(host: str, user: str, password: str) -> list[str]:
    """构造 sshpass + ssh 前缀。"""
    return [
        'sshpass', '-p', password,
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'LogLevel=ERROR',
        f'{user}@{host}',
    ]


def build_scp_prefix(host: str, user: str, password: str) -> list[str]:
    """构造 sshpass + scp 前缀。"""
    return [
        'sshpass', '-p', password,
        'scp',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'LogLevel=ERROR',
    ]


def run_command(
    cmd: list[str],
    timeout: float | None = None,
    capture_output: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """执行子进程命令。"""
    return subprocess.run(
        cmd,
        text=True,
        capture_output=capture_output,
        timeout=timeout,
        check=check,
    )


def normalize_probe_args(device_args: str) -> str:
    """规范化 UHD probe 参数。"""
    normalized = str(device_args or '').strip()
    return normalized or 'type=b200'


def summarize_probe_output(result: subprocess.CompletedProcess[str]) -> str:
    """提取 probe 命令的末尾关键信息。"""
    text = ((result.stdout or '') + '\n' + (result.stderr or '')).strip()
    if not text:
        return ''
    lines = [line for line in text.splitlines() if line.strip()]
    return '\n'.join(lines[-12:])


def prime_local_usrp(device_args: str, role: str) -> bool:
    """本地执行 UHD probe，避免首个正式试验承担固件加载。"""
    probe_args = normalize_probe_args(device_args)
    cmd = ['uhd_usrp_probe', '--args', probe_args]
    print(f'[Prime] 本地 {role}: {" ".join(cmd)}')
    result = run_command(cmd, timeout=45.0)
    if result.returncode == 0:
        return True

    print(f'[Prime] 本地 {role} 失败 (rc={result.returncode})')
    tail = summarize_probe_output(result)
    if tail:
        print(tail)
    return False


def prime_remote_usrp(
    host: str,
    user: str,
    password: str,
    device_args: str,
    role: str,
) -> bool:
    """远端执行 UHD probe，提前拉起板端固件/FPGA。"""
    probe_args = normalize_probe_args(device_args)
    ssh_prefix = build_ssh_prefix(host, user, password)
    remote_cmd = f'uhd_usrp_probe --args {probe_args!r}'
    print(f'[Prime] 远端 {role}: ssh {user}@{host} "{remote_cmd}"')
    result = run_command(ssh_prefix + [remote_cmd], timeout=60.0)
    if result.returncode == 0:
        return True

    print(f'[Prime] 远端 {role} 失败 (rc={result.returncode})')
    tail = summarize_probe_output(result)
    if tail:
        print(tail)
    return False


def remote_status_command(remote_output: str, remote_log: str) -> str:
    """生成远端状态探测命令。"""
    return (
        'python3 - <<\'PY\'\n'
        'import hashlib, os\n'
        f'out_path={remote_output!r}\n'
        f'log_path={remote_log!r}\n'
        'exists=os.path.exists(out_path)\n'
        'size=os.path.getsize(out_path) if exists else 0\n'
        'sha=""\n'
        'if exists:\n'
        '    with open(out_path, "rb") as f:\n'
        '        sha=hashlib.sha256(f.read()).hexdigest()\n'
        'log_exists=os.path.exists(log_path)\n'
        'log_size=os.path.getsize(log_path) if log_exists else 0\n'
        'ready=0\n'
        'saw_preamble=0\n'
        'saw_header=0\n'
        'saw_payload=0\n'
        'if log_exists:\n'
        '    with open(log_path, "rb") as f:\n'
        '        head=f.read(min(log_size, 16384)).decode("utf-8", errors="ignore")\n'
        '        if log_size > 16384:\n'
        '            f.seek(max(0, log_size - 16384), os.SEEK_SET)\n'
        '            tail=f.read().decode("utf-8", errors="ignore")\n'
        '        else:\n'
        '            tail=head\n'
        '    scan_text=head + "\\n" + tail\n'
        '    ready=int("等待信号" in scan_text or "离线回放" in scan_text)\n'
        '    saw_preamble=int("PREAMBLE CHAN" in scan_text)\n'
        '    saw_header=int("HEADER OK" in scan_text or "HEADER CRC FAIL" in scan_text)\n'
        '    saw_payload=int("decode_search:" in scan_text or "NEED MORE:" in scan_text or "→ 异步解码" in scan_text)\n'
        'print('
        '    f"exists={int(exists)} size={size} sha={sha} "'
        '    f"log_exists={int(log_exists)} log_size={log_size} ready={ready} "'
        '    f"saw_preamble={saw_preamble} saw_header={saw_header} saw_payload={saw_payload}"'
        ')\n'
        'PY'
    )


def remote_kill_command(remote_tag: str) -> str:
    """按唯一 tag 清理远端残留 RX。"""
    return (
        f'pkill -TERM -f {remote_tag!r} >/dev/null 2>&1 || true; '
        'sleep 1; '
        f'pkill -KILL -f {remote_tag!r} >/dev/null 2>&1 || true'
    )


def fetch_remote_file(
    host: str,
    user: str,
    password: str,
    remote_path: str,
    local_path: Path,
) -> bool:
    """抓取远端文件到本地。"""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_scp_prefix(host, user, password) + [
        f'{user}@{host}:{remote_path}',
        str(local_path),
    ]
    result = run_command(cmd, timeout=30.0)
    return result.returncode == 0


def parse_remote_status(stdout: str) -> dict[str, str]:
    """解析远端状态输出。"""
    fields: dict[str, str] = {}
    for token in stdout.strip().split():
        if '=' not in token:
            continue
        key, value = token.split('=', 1)
        fields[key] = value
    return fields


def query_remote_status(
    host: str,
    user: str,
    password: str,
    remote_output: str,
    remote_log: str,
    timeout: float,
) -> dict[str, str]:
    """轮询远端输出/日志状态。"""
    ssh_prefix = build_ssh_prefix(host, user, password)
    try:
        result = run_command(
            ssh_prefix + [remote_status_command(remote_output, remote_log)],
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {}
    return parse_remote_status(result.stdout or '')


def wait_remote_rx_ready(
    host: str,
    user: str,
    password: str,
    remote_output: str,
    remote_log: str,
    proc: subprocess.Popen[str],
    timeout: float,
) -> bool:
    """等待远端 RX 真正进入“等待信号”状态。"""
    deadline = time.monotonic() + max(0.0, float(timeout))
    while proc.poll() is None and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        status = query_remote_status(
            host=host,
            user=user,
            password=password,
            remote_output=remote_output,
            remote_log=remote_log,
            timeout=min(3.0, max(1.0, remaining)),
        )
        if status.get('ready', '0') == '1':
            return True
        time.sleep(0.5)
    return False


def wait_remote_rx_progress(
    host: str,
    user: str,
    password: str,
    remote_output: str,
    remote_log: str,
    proc: subprocess.Popen[str],
    timeout: float,
) -> dict[str, str]:
    """等待远端 RX 出现前导/头部/解码迹象，用于尽早区分“没锁到帧”。"""
    deadline = time.monotonic() + max(0.0, float(timeout))
    last_status: dict[str, str] = {}
    while proc.poll() is None and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        status = query_remote_status(
            host=host,
            user=user,
            password=password,
            remote_output=remote_output,
            remote_log=remote_log,
            timeout=min(3.0, max(1.0, remaining)),
        )
        if status:
            last_status = status
        if (
            status.get('exists', '0') == '1'
            or status.get('saw_preamble', '0') == '1'
            or status.get('saw_header', '0') == '1'
            or status.get('saw_payload', '0') == '1'
        ):
            return status
        time.sleep(0.5)
    return last_status


def parse_rx_metrics(log_text: str) -> dict[str, int | bool]:
    """从 usrp_tensor_rx 日志中提取关键恢复指标。"""
    metrics: dict[str, int | bool] = {
        'frames_ok': 0,
        'frames_duplicate': 0,
        'frames_bad_crc': 0,
        'frames_bad_hdr': 0,
        'frames_fec_fail': 0,
        'max_payload_seen': 0,
        'expected_totlen_seen': 0,
        'max_unique_seen': 0,
        'pass_reported': False,
        'decode_search_dt_sec': 0.0,
        'decode_search_order': '',
        'decode_search_ok': False,
        'rx_elapsed_sec': 0.0,
    }

    stat_patterns = {
        'frames_ok': r'帧正确:\s*(\d+)',
        'frames_duplicate': r'重复帧:\s*(\d+)',
        'frames_bad_crc': r'FRAME CRC:\s*(\d+)',
        'frames_bad_hdr': r'HDR CRC:\s*(\d+)',
        'frames_fec_fail': r'FEC 失败:\s*(\d+)',
    }
    for key, pattern in stat_patterns.items():
        match = re.search(pattern, log_text)
        if match:
            metrics[key] = int(match.group(1))

    payload_matches = re.findall(r'累计\s+(\d+)/(\d+)', log_text)
    if payload_matches:
        max_payload, expected_totlen = max(
            ((int(payload), int(total)) for payload, total in payload_matches),
            key=lambda item: item[0],
        )
        metrics['max_payload_seen'] = max_payload
        metrics['expected_totlen_seen'] = expected_totlen

    unique_matches = re.findall(r'unique=(\d+)', log_text)
    if unique_matches:
        metrics['max_unique_seen'] = max(int(value) for value in unique_matches)

    decode_matches = re.findall(
        r'decode_search:.*?order=([a-z-]+)\s+dt=([0-9.]+)s\s+(OK|FAIL)',
        log_text,
    )
    if decode_matches:
        order, dt_sec, status = decode_matches[-1]
        metrics['decode_search_order'] = order
        metrics['decode_search_dt_sec'] = float(dt_sec)
        metrics['decode_search_ok'] = (status == 'OK')

    elapsed_match = re.search(r'耗时:\s*([0-9.]+)\s*s', log_text)
    if elapsed_match:
        metrics['rx_elapsed_sec'] = float(elapsed_match.group(1))

    metrics['pass_reported'] = (
        '所有数据接收完毕' in log_text
        or 'PASS: 数据完整接收' in log_text
    )
    return metrics


def run_trial(
    args: argparse.Namespace,
    config: TrialConfig,
    local_sha: str,
    local_size: int,
    trial_index: int,
) -> dict[str, object]:
    """执行一次 OTA 试验。"""
    trial_name = f'{trial_index:03d}_{config.slug()}'
    trial_dir = Path(args.artifact_dir) / trial_name
    trial_dir.mkdir(parents=True, exist_ok=True)

    remote_output = f'/tmp/{trial_name}.bin'
    remote_log = f'/tmp/{trial_name}.log'

    ssh_prefix = build_ssh_prefix(args.board_host, args.board_user, args.board_pass)
    rx_bin = f'{args.remote_build_dir.rstrip("/")}/usrp_tensor_rx'
    tx_bin = Path(args.tx_bin)

    rx_cmd = (
        f'cd {shlex.quote(args.remote_build_dir)} && '
        f'rm -f {shlex.quote(remote_output)} {shlex.quote(remote_log)} && '
        f'timeout {args.remote_kill_after:.1f}s '
        f'{shlex.quote(rx_bin)} '
        f'--output {shlex.quote(remote_output)} '
        f'--args {shlex.quote(args.remote_serial_args)} '
        f'--rate {config.rate} '
        f'--freq {args.freq} '
        f'--gain {config.rx_gain} '
        f'{"--ant " + shlex.quote(args.remote_rx_ant) + " " if args.remote_rx_ant else ""}'
        f'--spb {config.spb} '
        f'--setup {config.setup} '
        f'--decode-workers {config.decode_workers} '
        f'--timeout {config.no_frame_timeout} '
        f'--payload-search-order {shlex.quote(config.payload_search_order)} '
        f'> {shlex.quote(remote_log)} 2>&1'
    )

    tx_cmd = [
        str(tx_bin),
        '--file', str(args.file),
        '--args', args.local_serial_args,
        '--rate', str(config.rate),
        '--freq', str(args.freq),
        '--gain', str(config.tx_gain),
        '--repeat', str(config.repeat),
        '--frame-repeat', str(config.frame_repeat),
        '--start-pad-samps', str(config.start_pad_samps),
        '--warmup-frames', str(config.warmup_frames),
        '--warmup-repeats', str(config.warmup_repeats),
        '--warmup-rounds', str(config.warmup_rounds),
        '--round-gap-ms', str(config.round_gap_ms),
        '--tail-pad-samps', str(config.tail_pad_samps),
        '--first-frame-extra-repeats', str(config.first_frame_extra_repeats),
        '--last-frame-extra-repeats', str(config.last_frame_extra_repeats),
        '--frame-order', str(config.frame_order),
    ]

    print(
        f'[Trial {trial_index:03d}] '
        f'rate={config.rate / 1e6:.3f}Msps wait={config.wait_s:.3f}s '
        f'pad={config.start_pad_samps} repeat={config.repeat} '
        f'frame_repeat={config.frame_repeat} ffr={config.first_frame_extra_repeats} '
        f'spb={config.spb} '
        f'ps={config.payload_search_order} '
        f'fo={config.frame_order}'
    )

    if not prime_remote_usrp(
        args.board_host,
        args.board_user,
        args.board_pass,
        args.remote_serial_args,
        'RX',
    ):
        raise RuntimeError('远端 RX 预热失败')
    if not prime_local_usrp(args.local_serial_args, 'TX'):
        raise RuntimeError('本地 TX 预热失败')

    rx_proc = subprocess.Popen(
        ssh_prefix + [rx_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready_wait_timeout = max(
        float(config.wait_s),
        min(12.0, max(4.0, float(config.setup) + 8.0)),
    )
    ready_wait_started = time.perf_counter()
    rx_ready = wait_remote_rx_ready(
        host=args.board_host,
        user=args.board_user,
        password=args.board_pass,
        remote_output=remote_output,
        remote_log=remote_log,
        proc=rx_proc,
        timeout=ready_wait_timeout,
    )
    ready_wait_sec = round(time.perf_counter() - ready_wait_started, 6)
    if rx_ready:
        print(
            f'[Trial {trial_index:03d}] 远端 RX 已 ready '
            f'(ready_wait={ready_wait_sec:.3f}s, budget={ready_wait_timeout:.1f}s)'
        )
    else:
        print(
            f'[Trial {trial_index:03d}] 远端 RX 未在 {ready_wait_timeout:.1f}s 内确认 ready，'
            '按最小窗口继续'
        )

    remaining_wait = max(0.0, float(config.wait_s) - ready_wait_sec)
    if remaining_wait > 1e-3:
        time.sleep(remaining_wait)

    if rx_proc.poll() is None:
        tx_result = run_command(tx_cmd, timeout=args.tx_timeout)
    else:
        tx_result = subprocess.CompletedProcess(
            args=tx_cmd,
            returncode=125,
            stdout='',
            stderr='[sweep] 远端 RX 在发射前提前退出\n',
        )

    post_tx_status: dict[str, str] = {}
    no_signal_abort = False
    post_tx_progress_timeout = min(
        float(args.rx_wait_timeout),
        max(2.5, min(4.0, float(config.setup) + 2.5)),
    )
    single_frame_fast_abort = (int(local_size) <= 8192)
    if tx_result.returncode == 0 and rx_proc.poll() is None and single_frame_fast_abort:
        post_tx_status = wait_remote_rx_progress(
            host=args.board_host,
            user=args.board_user,
            password=args.board_pass,
            remote_output=remote_output,
            remote_log=remote_log,
            proc=rx_proc,
            timeout=post_tx_progress_timeout,
        )
        if (
            post_tx_status.get('exists', '0') != '1'
            and post_tx_status.get('saw_preamble', '0') != '1'
            and post_tx_status.get('saw_header', '0') != '1'
            and post_tx_status.get('saw_payload', '0') != '1'
        ):
            no_signal_abort = True
            print(
                f'[Trial {trial_index:03d}] 发射后 {post_tx_progress_timeout:.1f}s 内仍无前导/帧迹象，'
                '提前终止本轮 RX'
            )
            try:
                run_command(
                    ssh_prefix + [remote_kill_command(trial_name)],
                    timeout=10.0,
                )
            except subprocess.TimeoutExpired:
                pass

    try:
        rx_stdout, _ = rx_proc.communicate(
            timeout=5.0 if no_signal_abort else args.rx_wait_timeout,
        )
    except subprocess.TimeoutExpired:
        rx_proc.kill()
        rx_stdout, _ = rx_proc.communicate()

    (trial_dir / 'tx.log').write_text(tx_result.stdout + tx_result.stderr)
    (trial_dir / 'rx_ssh.log').write_text(rx_stdout or '')

    status_result = run_command(
        ssh_prefix + [remote_status_command(remote_output, remote_log)],
        timeout=20.0,
    )
    (trial_dir / 'remote_status.log').write_text(
        (status_result.stdout or '') + (status_result.stderr or '')
    )
    status = parse_remote_status(status_result.stdout)
    status = {**post_tx_status, **status}
    remote_exists = status.get('exists', '0') == '1'
    remote_size = int(status.get('size', '0') or '0')
    remote_sha = status.get('sha', '')

    fetched_remote_log = fetch_remote_file(
        args.board_host,
        args.board_user,
        args.board_pass,
        remote_log,
        trial_dir / 'rx.log',
    )

    fetched_remote_output = False
    if remote_exists and remote_size > 0 and args.fetch_output:
        fetched_remote_output = fetch_remote_file(
            args.board_host,
            args.board_user,
            args.board_pass,
            remote_output,
            trial_dir / 'rx.bin',
        )

    rx_log_path = trial_dir / 'rx.log'
    rx_log_text = ''
    if rx_log_path.exists():
        rx_log_text = rx_log_path.read_text(encoding='utf-8', errors='ignore')
    else:
        rx_log_text = rx_stdout or ''
    rx_metrics = parse_rx_metrics(rx_log_text)

    success = (
        tx_result.returncode == 0
        and rx_proc.returncode == 0
        and remote_exists
        and remote_size == local_size
        and remote_sha == local_sha
    )

    summary = (
        f'[Trial {trial_index:03d}] '
        f'tx_rc={tx_result.returncode} rx_rc={rx_proc.returncode} '
        f'remote_exists={"yes" if remote_exists else "no"} '
        f'remote_size={remote_size} '
        f'rx_elapsed={rx_metrics["rx_elapsed_sec"]:.3f}s '
        f'decode_dt={rx_metrics["decode_search_dt_sec"]:.3f}s '
        f'decode_order={rx_metrics["decode_search_order"] or "n/a"} '
        f'frames_ok={rx_metrics["frames_ok"]} '
        f'unique={rx_metrics["max_unique_seen"]} '
        f'payload={rx_metrics["max_payload_seen"]}/{rx_metrics["expected_totlen_seen"]} '
        f'preamble={status.get("saw_preamble", "0")} '
        f'header={status.get("saw_header", "0")} '
        f'payload_seen={status.get("saw_payload", "0")} '
        f'early_abort={"yes" if no_signal_abort else "no"} '
        f'sha_match={"yes" if remote_sha == local_sha and remote_exists else "no"} '
        f'fetch_log={"yes" if fetched_remote_log else "no"} '
        f'fetch_out={"yes" if fetched_remote_output else "no"}'
    )
    print(summary)

    return {
        'trial_name': trial_name,
        'success': success,
        'summary': summary,
        'trial_dir': trial_dir,
        'remote_exists': remote_exists,
        'remote_size': remote_size,
        'remote_sha': remote_sha,
        'tx_rc': tx_result.returncode,
        'rx_rc': rx_proc.returncode,
        'remote_ready': (status.get('ready', '0') == '1'),
        'ready_wait_sec': ready_wait_sec,
        'single_frame_fast_abort': single_frame_fast_abort,
        'saw_preamble': (status.get('saw_preamble', '0') == '1'),
        'saw_header': (status.get('saw_header', '0') == '1'),
        'saw_payload': (status.get('saw_payload', '0') == '1'),
        'no_signal_abort': no_signal_abort,
        'rx_elapsed_sec': float(rx_metrics['rx_elapsed_sec']),
        'decode_search_dt_sec': float(rx_metrics['decode_search_dt_sec']),
        'decode_search_order': str(rx_metrics['decode_search_order']),
        'decode_search_ok': bool(rx_metrics['decode_search_ok']),
        'frames_ok': int(rx_metrics['frames_ok']),
        'frames_duplicate': int(rx_metrics['frames_duplicate']),
        'frames_bad_crc': int(rx_metrics['frames_bad_crc']),
        'frames_bad_hdr': int(rx_metrics['frames_bad_hdr']),
        'frames_fec_fail': int(rx_metrics['frames_fec_fail']),
        'max_payload_seen': int(rx_metrics['max_payload_seen']),
        'expected_totlen_seen': int(rx_metrics['expected_totlen_seen']),
        'max_unique_seen': int(rx_metrics['max_unique_seen']),
        'pass_reported': bool(rx_metrics['pass_reported']),
        'tx_log': trial_dir / 'tx.log',
        'rx_log': trial_dir / 'rx.log',
    }


def main() -> int:
    """程序入口。"""
    parser = argparse.ArgumentParser(
        description='本地 TX + 远端 RX 的 OTA 编排与扫参工具',
    )
    parser.add_argument(
        '--file',
        required=True,
        help='本地待发送文件',
    )
    parser.add_argument(
        '--tx-bin',
        default=str(REPO_ROOT / 'usrp_tensor' / 'build' / 'usrp_tensor_tx'),
        help='本地 usrp_tensor_tx 路径',
    )
    parser.add_argument(
        '--board-host',
        default='100.121.87.73',
        help='远端板端 SSH 地址',
    )
    parser.add_argument(
        '--board-user',
        default='user',
        help='远端板端 SSH 用户名',
    )
    parser.add_argument(
        '--board-pass',
        default='user',
        help='远端板端 SSH 密码',
    )
    parser.add_argument(
        '--remote-build-dir',
        default='/home/user/usrp_tensor_codex_20260421/usrp_tensor/build',
        help='远端编译目录',
    )
    parser.add_argument(
        '--local-serial-args',
        default='serial=31E74E3',
        help='本地 TX UHD args',
    )
    parser.add_argument(
        '--remote-serial-args',
        default='serial=31DDAB3',
        help='远端 RX UHD args',
    )
    parser.add_argument(
        '--remote-rx-ant',
        default='RX2',
        help='远端 RX 天线口位',
    )
    parser.add_argument(
        '--freq',
        type=float,
        default=915e6,
        help='中心频率 Hz',
    )
    parser.add_argument(
        '--rates',
        default='1000000',
        help='采样率列表，逗号分隔',
    )
    parser.add_argument(
        '--waits',
        default='0.4',
        help='RX 启动后到 TX 发射前的等待秒数列表',
    )
    parser.add_argument(
        '--start-pads',
        default='100000',
        help='TX 起始静默样本数列表',
    )
    parser.add_argument(
        '--repeats',
        default='4',
        help='TX 重复轮数列表',
    )
    parser.add_argument(
        '--frame-repeats',
        default='1',
        help='单帧紧邻重复次数列表',
    )
    parser.add_argument(
        '--spbs',
        default='10000',
        help='RX 每批次样本数列表',
    )
    parser.add_argument(
        '--setups',
        default='0.1',
        help='RX setup 秒数列表',
    )
    parser.add_argument(
        '--decode-workers',
        default='2',
        help='RX 异步 post-capture 解码 worker 数列表',
    )
    parser.add_argument(
        '--no-frame-timeouts',
        default='8',
        help='RX 无新帧超时秒数列表',
    )
    parser.add_argument(
        '--tx-gain',
        type=float,
        default=60.0,
        help='TX 增益 dB',
    )
    parser.add_argument(
        '--rx-gain',
        type=float,
        default=60.0,
        help='RX 增益 dB',
    )
    parser.add_argument(
        '--warmup-frames',
        type=int,
        default=2,
        help='TX 热机帧数',
    )
    parser.add_argument(
        '--warmup-repeats',
        type=int,
        default=2,
        help='TX 热机重复轮数',
    )
    parser.add_argument(
        '--warmup-rounds',
        type=int,
        default=1,
        help='TX 执行热机的发送轮数',
    )
    parser.add_argument(
        '--round-gap-ms',
        default='500',
        help='TX 发送轮之间等待毫秒数列表',
    )
    parser.add_argument(
        '--tail-pad-samps',
        default='2000',
        help='TX 每轮最后一帧后补零样本数列表',
    )
    parser.add_argument(
        '--first-frame-extra-repeats',
        default='0',
        help='TX 每轮首帧主发送后额外重复首帧的次数列表',
    )
    parser.add_argument(
        '--last-frame-extra-repeats',
        default='0',
        help='TX 每轮主发送结束后额外重复最后一帧的次数列表',
    )
    parser.add_argument(
        '--payload-search-orders',
        default='auto',
        help='RX payload 搜索顺序列表，逗号分隔: auto/gardner-first/phase-first/phase-only',
    )
    parser.add_argument(
        '--frame-orders',
        default='normal',
        help='TX 主发送顺序列表，逗号分隔: normal/tail-first',
    )
    parser.add_argument(
        '--artifact-dir',
        default=str(DEFAULT_ARTIFACT_DIR),
        help='本地试验产物目录',
    )
    parser.add_argument(
        '--tx-timeout',
        type=float,
        default=300.0,
        help='本地 TX 超时秒数',
    )
    parser.add_argument(
        '--rx-wait-timeout',
        type=float,
        default=40.0,
        help='等待远端 RX 退出的最大秒数',
    )
    parser.add_argument(
        '--remote-kill-after',
        type=float,
        default=18.0,
        help='远端 timeout 秒数',
    )
    parser.add_argument(
        '--attempts-per-config',
        type=int,
        default=1,
        help='每组参数重复试验次数',
    )
    parser.add_argument(
        '--stop-on-success',
        action='store_true',
        help='首个 bit-exact 成功后立即停止扫描',
    )
    parser.add_argument(
        '--fetch-output',
        action='store_true',
        help='成功或部分成功时将远端输出文件抓回本地',
    )
    args = parser.parse_args()
    args.artifact_dir = str(Path(args.artifact_dir) / time.strftime('%Y%m%d_%H%M%S'))
    artifact_root = Path(args.artifact_dir)
    artifact_root.mkdir(parents=True, exist_ok=True)

    tx_bin = Path(args.tx_bin)
    if not tx_bin.exists():
        print(f'[错误] 找不到 TX 可执行文件: {tx_bin}')
        return 1

    input_path = Path(args.file)
    if not input_path.exists():
        print(f'[错误] 找不到输入文件: {input_path}')
        return 1

    local_sha = sha256_file(input_path)
    local_size = input_path.stat().st_size
    print(f'[Input] file={input_path} size={local_size} sha256={local_sha}')

    configs = [
        TrialConfig(
            rate=rate,
            wait_s=wait_s,
            start_pad_samps=start_pad,
            repeat=repeat,
            frame_repeat=frame_repeat,
            spb=spb,
            setup=setup,
            decode_workers=decode_workers,
            no_frame_timeout=no_frame_timeout,
            tx_gain=args.tx_gain,
            rx_gain=args.rx_gain,
            warmup_frames=args.warmup_frames,
            warmup_repeats=args.warmup_repeats,
            warmup_rounds=args.warmup_rounds,
            round_gap_ms=round_gap_ms,
            tail_pad_samps=tail_pad_samps,
            first_frame_extra_repeats=first_frame_extra_repeats,
            last_frame_extra_repeats=last_frame_extra_repeats,
            payload_search_order=payload_search_order,
            frame_order=frame_order,
        )
        for rate, wait_s, start_pad, repeat, frame_repeat, spb, setup, decode_workers, no_frame_timeout, round_gap_ms, tail_pad_samps, first_frame_extra_repeats, last_frame_extra_repeats, payload_search_order, frame_order
        in itertools.product(
            parse_float_list(args.rates),
            parse_float_list(args.waits),
            parse_int_list(args.start_pads),
            parse_int_list(args.repeats),
            parse_int_list(args.frame_repeats),
            parse_int_list(args.spbs),
            parse_float_list(args.setups),
            parse_int_list(args.decode_workers),
            parse_float_list(args.no_frame_timeouts),
            parse_int_list(args.round_gap_ms),
            parse_int_list(args.tail_pad_samps),
            parse_int_list(args.first_frame_extra_repeats),
            parse_int_list(args.last_frame_extra_repeats),
            [item.strip() for item in args.payload_search_orders.split(',') if item.strip()],
            [item.strip() for item in args.frame_orders.split(',') if item.strip()],
        )
    ]

    configs = configs * max(args.attempts_per_config, 1)

    print(f'[Plan] total_trials={len(configs)} artifact_dir={args.artifact_dir}')
    successes = 0
    best_record: dict[str, object] | None = None
    summary_path = artifact_root / 'summary.jsonl'
    overview_path = artifact_root / 'summary.txt'

    for idx, config in enumerate(configs, start=1):
        result = run_trial(args, config, local_sha, local_size, idx)
        record = build_trial_record(
            args,
            config,
            result,
            local_size,
            local_sha,
            idx,
        )
        append_jsonl(summary_path, record)
        if best_record is None or trial_score(record) > trial_score(best_record):
            best_record = record

        if result['success']:
            successes += 1
            print(f'[Success] {result["trial_name"]} -> {result["trial_dir"]}')
            if args.stop_on_success:
                break

    write_overview(
        overview_path,
        total_trials=len(configs),
        success_trials=successes,
        best_record=best_record,
    )
    print(f'[Summary] jsonl={summary_path} overview={overview_path}')
    print(f'[Done] success_trials={successes} / {len(configs)}')
    return 0 if successes > 0 else 2


if __name__ == '__main__':
    sys.exit(main())
