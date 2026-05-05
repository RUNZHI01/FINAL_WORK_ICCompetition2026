#!/usr/bin/env python3
"""usrp_continuous_spool_smoke.py — continuous RX + spool 激进采样率 smoke"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from e2e_usrp import build_scp_prefix, build_ssh_prefix
from usrp_image_demo import sha256_file
from usrp_latent_demo import (
    DEFAULT_INPUT_LATENT,
    add_ota_profile_arguments,
    build_effective_ota_profile,
    build_wire_payload,
    recover_payload_from_wire,
)
from usrp_metrics import npz_payload_metrics


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / 'artifacts' / 'usrp_continuous_spool_smoke'
DEFAULT_REMOTE_BUILD_DIR = '/home/user/usrp_tensor_codex_20260423_spool_1/usrp_tensor/build_spool'
DEFAULT_RATES = '30000000,20000000,10000000,5000000,2000000,1000000'


def parse_rates(raw: str) -> list[float]:
    values = []
    for item in str(raw).split(','):
        text = item.strip()
        if not text:
            continue
        values.append(float(text))
    if not values:
        raise ValueError('至少需要一个 rate')
    return values


def wait_remote_ready(log_path: Path, proc: subprocess.Popen[str], timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    ready_markers = (
        'spool job 1 等待接收',
        '等待信号',
        '继续使用已启动的 continuous RX 流',
    )
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        if log_path.exists():
            text = log_path.read_text(encoding='utf-8', errors='ignore')
            if any(marker in text for marker in ready_markers):
                return True
        time.sleep(0.2)
    return False


def wait_remote_log_marker(
    log_path: Path,
    proc: subprocess.Popen[str],
    timeout_sec: float,
    marker: str,
) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = ''
        if log_path.exists():
            text = log_path.read_text(encoding='utf-8', errors='ignore')
            if marker in text:
                return True
        if proc.poll() is not None and marker not in text:
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
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = ''
        if log_path.exists():
            text = log_path.read_text(encoding='utf-8', errors='ignore')
            if text.count(marker) >= min_count:
                return True
        if proc.poll() is not None and text.count(marker) < min_count:
            return False
        time.sleep(0.2)
    return False


def read_log_text(log_path: Path) -> str:
    if not log_path.exists():
        return ''
    return log_path.read_text(encoding='utf-8', errors='ignore')


def wait_remote_log_marker_since_offset(
    log_path: Path,
    proc: subprocess.Popen[str],
    timeout_sec: float,
    marker: str,
    start_offset: int,
) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = read_log_text(log_path)
        if marker in text[start_offset:]:
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.2)
    return False


def wait_remote_job_terminal(
    log_path: Path,
    proc: subprocess.Popen[str],
    timeout_sec: float,
    complete_marker: str,
    fail_marker: str,
    start_offset: int,
) -> str:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        text = read_log_text(log_path)
        tail = text[start_offset:]
        if complete_marker in tail:
            return 'complete'
        if fail_marker in tail:
            return 'fail'
        if proc.poll() is not None:
            return 'dead'
        time.sleep(0.2)
    return 'timeout'


def terminate_process(proc: subprocess.Popen[str], timeout_sec: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout_sec)


def cleanup_remote_spool(
    *,
    ssh_prefix: list[str],
    remote_spool_dir: str,
) -> None:
    remote_cmd = (
        f"pkill -f {shlex.quote(remote_spool_dir)} >/dev/null 2>&1 || true; "
        f"rm -rf {shlex.quote(remote_spool_dir)} >/dev/null 2>&1 || true"
    )
    subprocess.run(
        ssh_prefix + [remote_cmd],
        capture_output=True,
        text=True,
        timeout=20.0,
    )


def remote_read_file_base64_command(remote_path: str) -> str:
    """在远端把小文件编码成 base64 输出到 stdout。"""
    return (
        'python3 - <<\'PY\'\n'
        'import base64, os, sys\n'
        f'path={remote_path!r}\n'
        'if not os.path.exists(path):\n'
        '    raise SystemExit(2)\n'
        'with open(path, "rb") as handle:\n'
        '    sys.stdout.write(base64.b64encode(handle.read()).decode("ascii"))\n'
        'PY'
    )


def fetch_remote_file(
    *,
    ssh_prefix: list[str],
    scp_prefix: list[str],
    board_user: str,
    board_host: str,
    remote_path: str,
    local_path: Path,
    timeout_sec: float,
) -> tuple[bool, str, str]:
    """取回远端文件；SCP 失败时用 SSH/base64 兜底。"""
    scp_result = subprocess.run(
        scp_prefix + [f'{board_user}@{board_host}:{remote_path}', str(local_path)],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if scp_result.returncode == 0 and local_path.exists():
        return True, 'scp', ''

    scp_error = (scp_result.stderr or scp_result.stdout or '').strip()
    inline_result = subprocess.run(
        ssh_prefix + [remote_read_file_base64_command(remote_path)],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if inline_result.returncode == 0 and inline_result.stdout.strip():
        local_path.write_bytes(base64.b64decode(inline_result.stdout.strip()))
        return True, 'ssh-base64', scp_error

    inline_error = (inline_result.stderr or inline_result.stdout or '').strip()
    return False, 'failed', f'scp={scp_error}; inline={inline_error}'


def build_tx_cmd(
    *,
    tx_bin: Path,
    wire_payload_path: Path,
    local_serial_args: str,
    rate: float,
    freq: float,
    base_profile: dict[str, object],
) -> list[str]:
    return [
        str(tx_bin),
        '--file', str(wire_payload_path),
        '--args', str(local_serial_args),
        '--rate', str(float(rate)),
        '--freq', str(float(freq)),
        '--gain', str(float(base_profile['tx_gain'])),
        '--repeat', str(int(base_profile['repeat'])),
        '--frame-repeat', str(int(base_profile['frame_repeat'])),
        '--start-pad-samps', str(int(base_profile['start_pad'])),
        '--round-gap-ms', str(int(base_profile['round_gap_ms'])),
        '--warmup-frames', str(int(base_profile['warmup_frames'])),
        '--warmup-repeats', str(int(base_profile['warmup_repeats'])),
        '--warmup-rounds', str(int(base_profile['warmup_rounds'])),
        '--tail-pad-samps', str(int(base_profile['tail_pad_samps'])),
        '--first-frame-extra-repeats', str(int(base_profile['first_frame_extra_repeats'])),
        '--last-frame-extra-repeats', str(int(base_profile['last_frame_extra_repeats'])),
        '--frame-order', str(base_profile['frame_order']),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description='continuous RX + spool 激进采样率 smoke')
    parser.add_argument('--input-latent', default=str(DEFAULT_INPUT_LATENT), help='单张 latent .npz 路径')
    parser.add_argument('--artifact-root', default=str(DEFAULT_ARTIFACT_ROOT), help='本地留档根目录')
    parser.add_argument('--chunk-bytes', type=int, default=6707, help='构造 wire payload 时的应用层切块大小')
    parser.add_argument('--rates', default=DEFAULT_RATES, help='待测采样率列表，逗号分隔')
    parser.add_argument('--count', type=int, default=1, help='连续发送多少张相同 latent；RX spool 对应接收多少 job')
    parser.add_argument('--board-host', default='100.121.87.73', help='板端 SSH 地址')
    parser.add_argument('--board-user', default='user', help='板端 SSH 用户名')
    parser.add_argument('--board-pass', default='user', help='板端 SSH 密码')
    parser.add_argument('--board-port', default='22', help='板端 SSH 端口')
    parser.add_argument('--remote-build-dir', default=DEFAULT_REMOTE_BUILD_DIR, help='板端 build 目录')
    parser.add_argument('--local-serial-args', default='serial=31E74E3', help='本地 TX UHD args')
    parser.add_argument('--remote-serial-args', default='serial=31DDAB3', help='板端 RX UHD args')
    parser.add_argument('--remote-rx-ant', default='TX/RX', help='板端 RX 天线口位')
    parser.add_argument('--freq', type=float, default=915e6, help='射频中心频率')
    parser.add_argument('--remote-ready-timeout', type=float, default=12.0, help='等待板端 RX 就绪的秒数')
    parser.add_argument('--remote-wait-timeout', type=float, default=180.0, help='等待单个 job 完成的秒数')
    parser.add_argument('--remote-kill-after', type=float, default=240.0, help='板端 timeout 秒数')
    parser.add_argument('--ready-settle-sec', type=float, default=0.35, help='RX ready marker 出现后，TX 前额外等待秒数')
    parser.add_argument('--job-max-attempts', type=int, default=1, help='同一 spool job 最多尝试发送多少次')
    parser.add_argument('--no-whitening', action='store_true', help='关闭公开 PRBS chunk whitening')
    parser.add_argument('--whitening-seed', type=int, default=0x6D2B79F5, help='公开 PRBS whitening 基准种子')
    add_ota_profile_arguments(parser)
    args = parser.parse_args()

    input_latent = Path(args.input_latent)
    if not input_latent.exists():
        raise FileNotFoundError(f'找不到 latent 输入文件: {input_latent}')
    if args.count <= 0:
        raise ValueError('count 必须 >= 1')
    if args.job_max_attempts <= 0:
        raise ValueError('job-max-attempts 必须 >= 1')

    rates = parse_rates(args.rates)
    run_id = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = Path(args.artifact_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    source_copy = run_dir / input_latent.name
    shutil.copy2(input_latent, source_copy)
    source_bytes = source_copy.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    chunk_plan, wire_payload, wire_manifest = build_wire_payload(
        source_bytes,
        app_chunk_bytes=args.chunk_bytes,
        whitening_enabled=not args.no_whitening,
        whitening_seed=args.whitening_seed,
    )
    wire_payload_path = run_dir / 'wire_payload.bin'
    wire_payload_path.write_bytes(wire_payload)

    tx_bin = REPO_ROOT / 'usrp_tensor' / 'build' / 'usrp_tensor_tx'
    if not tx_bin.exists():
        raise FileNotFoundError(f'找不到本地 TX: {tx_bin}')

    ssh_prefix = build_ssh_prefix(args.board_host, args.board_user, args.board_pass, args.board_port)
    scp_prefix = build_scp_prefix(args.board_host, args.board_user, args.board_pass, args.board_port)
    base_profile = build_effective_ota_profile(args)
    results: list[dict[str, object]] = []

    print(
        f'[Input] latent={source_copy} size={len(source_bytes)}B sha256={source_sha256} '
        f'rates={rates} chunk_count={len(chunk_plan)} count={args.count}',
        flush=True,
    )

    for rate in rates:
        rate_tag = f'rate_{int(rate)}'
        rate_dir = run_dir / rate_tag
        rate_dir.mkdir(parents=True, exist_ok=True)
        remote_log = rate_dir / 'remote_rx.log'
        tx_logs_dir = rate_dir / 'tx_logs'
        tx_logs_dir.mkdir(parents=True, exist_ok=True)
        received_dir = rate_dir / 'received'
        received_dir.mkdir(parents=True, exist_ok=True)
        remote_spool_dir = f'/tmp/usrp_rx_spool_{run_id}_{int(rate)}'
        effective_remote_kill_after = max(
            float(args.remote_kill_after),
            float(args.count) * float(args.remote_wait_timeout) + 120.0,
        )

        remote_cmd = (
            f'mkdir -p {shlex.quote(remote_spool_dir)} && '
            f'rm -f {remote_spool_dir}/rx_*.bin && '
            f'cd {shlex.quote(args.remote_build_dir)} && '
            f'timeout {effective_remote_kill_after:.1f}s '
            f'./usrp_tensor_rx_spool '
            f'--spool-dir {shlex.quote(remote_spool_dir)} '
            f'--spool-prefix rx '
            f'--max-jobs {int(args.count)} '
            f'--args {shlex.quote(args.remote_serial_args)} '
            f'--rate {float(rate)} '
            f'--freq {float(args.freq)} '
            f'--gain {float(base_profile["rx_gain"])} '
            f'--ant {shlex.quote(args.remote_rx_ant)} '
            f'--spb {int(base_profile["spb"])} '
            f'--setup {float(base_profile["setup"])} '
            f'--timeout {float(base_profile["no_frame_timeout"])} '
            f'--decode-workers {int(base_profile["decode_workers"])} '
            f'--payload-search-order {shlex.quote(base_profile["payload_search_order"])}'
        )

        print(
            f'[Rate {int(rate)}] 启动 remote RX spool '
            f'(count={args.count}, kill_after={effective_remote_kill_after:.1f}s)',
            flush=True,
        )
        cleanup_remote_spool(
            ssh_prefix=ssh_prefix,
            remote_spool_dir=remote_spool_dir,
        )
        remote_started = time.perf_counter()
        with remote_log.open('w', encoding='utf-8') as log_handle:
            remote_proc = subprocess.Popen(
                ssh_prefix + [remote_cmd],
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )

        ready = wait_remote_ready(remote_log, remote_proc, args.remote_ready_timeout)
        if not ready:
            terminate_process(remote_proc)
            cleanup_remote_spool(
                ssh_prefix=ssh_prefix,
                remote_spool_dir=remote_spool_dir,
            )
            result = {
                'rate': rate,
                'count': int(args.count),
                'success': False,
                'stage': 'remote_ready',
                'message': 'remote RX spool 未在时限内就绪',
                'remote_log': str(remote_log),
            }
            results.append(result)
            print(f'[Rate {int(rate)}] FAIL remote not ready', flush=True)
            continue
        if args.ready_settle_sec > 0:
            time.sleep(args.ready_settle_sec)

        job_results: list[dict[str, object]] = []
        tx_wall_total_sec = 0.0
        rate_ok = True
        wait_signal_marker = '[RX] 等待信号 ... (Ctrl+C 停止)'
        wait_signal_seen = read_log_text(remote_log).count(wait_signal_marker)

        for job_index in range(1, int(args.count) + 1):
            tx_cmd = build_tx_cmd(
                tx_bin=tx_bin,
                wire_payload_path=wire_payload_path,
                local_serial_args=args.local_serial_args,
                rate=rate,
                freq=args.freq,
                base_profile=base_profile,
            )
            complete_marker = f'spool job {job_index} 完成'
            fail_marker = f'spool job {job_index} 失败:'
            job_success = False

            for attempt_index in range(1, int(args.job_max_attempts) + 1):
                if job_index > 1 or attempt_index > 1:
                    target_wait_signal_count = wait_signal_seen + 1
                    if not wait_remote_log_marker_count(
                        remote_log,
                        remote_proc,
                        args.remote_wait_timeout,
                        wait_signal_marker,
                        target_wait_signal_count,
                    ):
                        rate_ok = False
                        job_results.append({
                            'job_index': job_index,
                            'attempt_count': attempt_index,
                            'success': False,
                            'stage': 'remote_wait_signal',
                            'message': f'未等到第 {target_wait_signal_count} 次等待信号 marker',
                            'remote_log': str(remote_log),
                        })
                        print(
                            f'[Rate {int(rate)}][Job {job_index}] FAIL wait-signal timeout',
                            flush=True,
                        )
                        break
                    wait_signal_seen = target_wait_signal_count
                    if args.ready_settle_sec > 0:
                        time.sleep(args.ready_settle_sec)

                local_tx_log = tx_logs_dir / f'local_tx_{job_index:06d}_attempt_{attempt_index:02d}.log'
                print(
                    f'[Rate {int(rate)}][Job {job_index}/{args.count}][Attempt {attempt_index}/{args.job_max_attempts}] 本地 TX 发送',
                    flush=True,
                )
                terminal_wait_offset = len(read_log_text(remote_log))
                tx_started = time.perf_counter()
                with local_tx_log.open('w', encoding='utf-8') as tx_log_handle:
                    tx_result = subprocess.run(
                        tx_cmd,
                        stdout=tx_log_handle,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=max(120.0, args.remote_wait_timeout),
                    )
                tx_wall_sec = time.perf_counter() - tx_started
                tx_wall_total_sec += tx_wall_sec

                if tx_result.returncode != 0:
                    rate_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'local_tx',
                        'message': f'local TX rc={tx_result.returncode}',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                        'remote_log': str(remote_log),
                    })
                    print(
                        f'[Rate {int(rate)}][Job {job_index}] FAIL local tx rc={tx_result.returncode}',
                        flush=True,
                    )
                    break

                terminal_state = wait_remote_job_terminal(
                    remote_log,
                    remote_proc,
                    args.remote_wait_timeout,
                    complete_marker,
                    fail_marker,
                    terminal_wait_offset,
                )
                if terminal_state == 'fail':
                    print(
                        f'[Rate {int(rate)}][Job {job_index}][Attempt {attempt_index}] remote fail marker',
                        flush=True,
                    )
                    if attempt_index < int(args.job_max_attempts):
                        continue
                    rate_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'remote_fail',
                        'message': 'remote RX 明确报告该 job 失败',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                        'remote_log': str(remote_log),
                    })
                    break
                if terminal_state != 'complete':
                    rate_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'remote_wait',
                        'message': f'未正常完成，terminal_state={terminal_state}',
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                        'remote_log': str(remote_log),
                    })
                    print(
                        f'[Rate {int(rate)}][Job {job_index}] FAIL remote terminal={terminal_state}',
                        flush=True,
                    )
                    break

                remote_output = f'{remote_spool_dir}/rx_{job_index:06d}.bin'
                received_wire_path = received_dir / f'received_wire_{job_index:06d}.bin'
                fetch_ok, fetch_method, fetch_error = fetch_remote_file(
                    ssh_prefix=ssh_prefix,
                    scp_prefix=scp_prefix,
                    board_user=args.board_user,
                    board_host=args.board_host,
                    remote_path=remote_output,
                    local_path=received_wire_path,
                    timeout_sec=30.0,
                )
                if not fetch_ok or not received_wire_path.exists():
                    rate_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'fetch',
                        'message': '未能取回 remote spool 输出',
                        'fetch_method': fetch_method,
                        'fetch_error': fetch_error,
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'local_tx_log': str(local_tx_log),
                        'remote_log': str(remote_log),
                    })
                    print(f'[Rate {int(rate)}][Job {job_index}] FAIL fetch', flush=True)
                    break

                received_wire = received_wire_path.read_bytes()
                try:
                    received_plain = recover_payload_from_wire(
                        received_wire,
                        wire_manifest=wire_manifest,
                    )
                except Exception as exc:
                    rate_ok = False
                    job_results.append({
                        'job_index': job_index,
                        'attempt_count': attempt_index,
                        'success': False,
                        'stage': 'recover',
                        'message': str(exc),
                        'tx_wall_sec': round(tx_wall_sec, 6),
                        'received_wire_size': len(received_wire),
                        'received_wire_path': str(received_wire_path),
                        'local_tx_log': str(local_tx_log),
                        'remote_log': str(remote_log),
                    })
                    print(f'[Rate {int(rate)}][Job {job_index}] FAIL recover payload', flush=True)
                    break

                wire_match = (received_wire == wire_payload)
                sha_match = (received_plain == source_bytes)
                try:
                    payload_metrics = npz_payload_metrics(source_bytes, received_plain)
                except Exception as exc:
                    payload_metrics = {
                        'effective_snr_db': None,
                        'effective_snr_db_text': 'unavailable',
                        'error': str(exc),
                    }
                job_results.append({
                    'job_index': job_index,
                    'attempt_count': attempt_index,
                    'success': bool(sha_match),
                    'wire_match': bool(wire_match),
                    'sha_match': bool(sha_match),
                    'payload_metrics': payload_metrics,
                    'tx_wall_sec': round(tx_wall_sec, 6),
                    'wire_size': len(wire_payload),
                    'received_wire_size': len(received_wire),
                    'received_plain_size': len(received_plain),
                    'received_wire_sha256': sha256_file(received_wire_path),
                    'received_wire_path': str(received_wire_path),
                    'fetch_method': fetch_method,
                    'fetch_error': fetch_error,
                    'local_tx_log': str(local_tx_log),
                    'remote_log': str(remote_log),
                })
                print(
                    f'[Rate {int(rate)}][Job {job_index}] '
                    f'{"PASS" if sha_match else "FAIL"} '
                    f'wire_match={wire_match} plain_match={sha_match} '
                    f'latent_effective_snr_db={payload_metrics["effective_snr_db_text"]} '
                    f'tx_wall={tx_wall_sec:.3f}s attempt={attempt_index}',
                    flush=True,
                )
                if not sha_match:
                    rate_ok = False
                    break
                job_success = True
                break

            if not rate_ok or not job_success:
                if rate_ok and not job_success:
                    rate_ok = False
                break

        if rate_ok:
            try:
                remote_proc.wait(timeout=min(60.0, args.remote_wait_timeout))
            except subprocess.TimeoutExpired:
                terminate_process(remote_proc)
        else:
            terminate_process(remote_proc)

        remote_wall_sec = time.perf_counter() - remote_started
        result = {
            'rate': rate,
            'count': int(args.count),
            'success': bool(
                rate_ok
                and len(job_results) == int(args.count)
                and all(bool(item.get('success')) for item in job_results)
            ),
            'jobs_completed': sum(1 for item in job_results if bool(item.get('success'))),
            'tx_wall_total_sec': round(tx_wall_total_sec, 6),
            'remote_wall_sec': round(remote_wall_sec, 6),
            'remote_log': str(remote_log),
            'job_results': job_results,
        }
        if args.count == 1 and job_results:
            first_job = job_results[0]
            result['wire_match'] = first_job.get('wire_match')
            result['sha_match'] = first_job.get('sha_match')
            result['tx_wall_sec'] = first_job.get('tx_wall_sec')
            result['wire_size'] = first_job.get('wire_size')
            result['received_wire_size'] = first_job.get('received_wire_size')
            result['received_plain_size'] = first_job.get('received_plain_size')
            result['received_wire_sha256'] = first_job.get('received_wire_sha256')
            result['payload_metrics'] = first_job.get('payload_metrics')
            result['local_tx_log'] = first_job.get('local_tx_log')
        results.append(result)

        cleanup_remote_spool(
            ssh_prefix=ssh_prefix,
            remote_spool_dir=remote_spool_dir,
        )
        print(
            f'[Rate {int(rate)}] {"PASS" if result["success"] else "FAIL"} '
            f'jobs_completed={result["jobs_completed"]}/{args.count} '
            f'tx_total={tx_wall_total_sec:.3f}s '
            f'remote_total={remote_wall_sec:.3f}s',
            flush=True,
        )
        if result['success']:
            break

    summary = {
        'input_latent': str(source_copy),
        'single_image_bytes': len(source_bytes),
        'single_image_sha256': source_sha256,
        'chunk_bytes': args.chunk_bytes,
        'count': int(args.count),
        'rates': rates,
        'profile': base_profile,
        'results': results,
    }
    summary_path = run_dir / 'summary.json'
    with summary_path.open('w', encoding='utf-8') as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write('\n')

    print()
    print('=' * 60)
    print('[Spool Smoke] 完成')
    print(f'  summary : {summary_path}')
    print('=' * 60)
    return 0 if any(bool(item.get('success')) for item in results) else 2


if __name__ == '__main__':
    raise SystemExit(main())
