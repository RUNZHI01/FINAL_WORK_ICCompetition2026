#!/usr/bin/env python3
"""e2e_usrp.py — USRP OTA 编排入口（主推明文 raw-file；历史兼容保留加密闭环）

当前主线:
  latent / quant npz / raw file → USRP TX → RX → output file

历史兼容链路:
  latent npz → ML-KEM 加密 → 密文 binary → USRP TX → RX → 密文 binary → ML-KEM 解密 → latent npz

支持两种传输模式:
  --mode sim    : 调用 usrp_tensor_loopback --sim (纯软件，无需硬件)
  --mode loopback: 调用 usrp_tensor_loopback (单设备 SMA 回环)
  --mode ota    : 分别调用 usrp_tensor_tx + usrp_tensor_rx (双设备 OTA)

用法:
  # SIM 模式 (无需 USRP 硬件)
  source .venv/bin/activate
  python scripts/e2e_usrp.py --mode sim --input test_latent.npz

  # 回环模式 (单设备 + SMA 跳线)
  python scripts/e2e_usrp.py --mode loopback --input test_latent.npz --tx-args "serial=31E74E3"

  # OTA 模式 (双设备, 自动启动 TX/RX)
  python scripts/e2e_usrp.py --mode ota --input test_latent.npz \
      --tx-args "serial=31DDAB3" --rx-args "serial=31E74E3"

  # 加密模式 (仅加密，输出 binary 给 TX 手动使用)
  python scripts/e2e_usrp.py --mode encrypt --input test_latent.npz --output encrypted.bin

  # 解密模式 (仅解密，读取 RX 输出 binary)
  python scripts/e2e_usrp.py --mode decrypt --input received.bin --output decrypted.npz \
      --session session.json
"""

import argparse
import base64
import hashlib
import json
import os
import re
import select
import shlex
import signal
import statistics
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite, EncryptedPayload
from mlkem_link.session import MLKEMSession, SessionRole, SessionState

DEFAULT_REMOTE_BUILD_DIR = '/home/user/usrp_tensor_codex_20260421/usrp_tensor/build'
DEFAULT_OTA_CHUNK_ALIGN_BYTES = 219
_LOCAL_USRP_PRIME_CACHE: dict[tuple[str, str], bool] = {}
_REMOTE_USRP_PRIME_CACHE: dict[tuple[str, str, str, str], tuple[bool, bool]] = {}
INLINE_FETCH_MAX_BYTES = 16 * 1024


def mlkem_encrypt(plaintext: bytes, suite: CipherSuite):
    """执行 ML-KEM 握手 + 加密，返回 (密文 bytes, responder session, suite)

    responder session 保存用于后续解密。握手数据 (pk, ct) 隐含在 session 内部。
    """
    backend = get_backend("768")
    initiator = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
    responder = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)

    t0 = time.perf_counter()
    pk = initiator.start_handshake()
    ct = responder.respond_handshake(pk)
    initiator.complete_handshake(ct)
    t_hs = (time.perf_counter() - t0) * 1000

    payload = initiator.encrypt(plaintext)
    wire_bytes = payload.to_bytes()
    t_enc = (time.perf_counter() - t0 - t_hs / 1000) * 1000

    return wire_bytes, responder, suite, t_hs, t_enc


def mlkem_decrypt(ciphertext: bytes, session: MLKEMSession,
                  suite: CipherSuite) -> bytes:
    """用已建立的 ML-KEM 会话解密密文"""
    payload = EncryptedPayload.from_bytes(ciphertext, suite)
    return session.decrypt(payload)


def save_session(responder: MLKEMSession, suite: CipherSuite,
                 path: str) -> None:
    """保存 responder 会话状态到 JSON 文件 (用于解密模式)

    注意: 这仅用于演示/测试，真实场景中不应导出会话密钥。
    """
    state = {
        "suite": suite.value,
        "session_key_hex": responder._session_key.hex(),
    }
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def load_session(path: str) -> tuple:
    """从 JSON 文件加载会话状态，返回 (suite, session_key_bytes)"""
    with open(path) as f:
        state = json.load(f)
    suite = CipherSuite(state["suite"])
    key = bytes.fromhex(state["session_key_hex"])
    return suite, key


def decrypt_with_loaded_key(ciphertext: bytes, suite: CipherSuite,
                            session_key: bytes) -> bytes:
    """用加载的会话密钥直接解密 (绕过 MLKEMSession)"""
    from mlkem_link.crypto import LinkEncryptor
    payload = EncryptedPayload.from_bytes(ciphertext, suite)
    encryptor = LinkEncryptor(suite)
    return encryptor.decrypt(session_key, payload)


def extract_radio_metrics(log_text: str) -> dict[str, object]:
    """从 usrp_tensor_rx 日志中提取可上抛的无线统计。"""
    metrics: dict[str, object] = {
        'phy_mode': None,
        'snr_db': None,
        'noise_var': None,
        'multipath': None,
        'rms_delay': None,
        'coh': None,
        'amp': None,
        'frames_ok': None,
        'frames_duplicate': None,
        'frames_bad_crc': None,
        'frames_bad_hdr': None,
        'frames_fec_fail': None,
        'max_unique_seen': None,
        'max_payload_seen': None,
        'expected_payload': None,
        'frame_error_rate': None,
        'duplicate_rate': None,
        'payload_completion': None,
        'post_fec_ber': None,
        'byte_error_rate': None,
        'bit_errors': None,
        'byte_errors': None,
        'compared_bytes': None,
        'elapsed_sec': None,
        'arq_nack_rounds': None,
        'arq_throughput_kib_s': None,
        'arq_data_kib': None,
        'arq_still_missing_frames': None,
        'received_size': None,
    }

    preamble = re.search(
        r'PREAMBLE CHAN: snr=([-\d.]+) dB noise_var=([-\deE.+]+) '
        r'multipath=(\d+) rms_delay=([-\deE.+]+) coh=([-\deE.+]+) amp=([-\deE.+]+)',
        log_text,
    )
    if preamble:
        metrics['phy_mode'] = 'plain'
        metrics['snr_db'] = round(float(preamble.group(1)), 3)
        metrics['rf_preamble_snr_db_est'] = metrics['snr_db']
        metrics['noise_var'] = round(float(preamble.group(2)), 6)
        metrics['multipath'] = int(preamble.group(3))
        metrics['rms_delay'] = round(float(preamble.group(4)), 6)
        metrics['coh'] = round(float(preamble.group(5)), 3)
        metrics['amp'] = round(float(preamble.group(6)), 3)

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
        max_payload, expected_payload = max(
            ((int(payload), int(total)) for payload, total in payload_matches),
            key=lambda item: item[0],
        )
        metrics['max_payload_seen'] = max_payload
        metrics['expected_payload'] = expected_payload

    unique_matches = re.findall(r'unique=(\d+)', log_text)
    if unique_matches:
        metrics['max_unique_seen'] = max(int(value) for value in unique_matches)

    elapsed = re.search(r'耗时:\s*([-\d.]+)\s*s', log_text)
    if elapsed:
        metrics['elapsed_sec'] = round(float(elapsed.group(1)), 6)

    nack_rounds = re.search(r'NACK 轮次:\s*(\d+)', log_text)
    if nack_rounds:
        metrics['phy_mode'] = 'arq'
        metrics['arq_nack_rounds'] = int(nack_rounds.group(1))

    throughput = re.search(r'吞吐:\s*([-\d.]+)\s*KB/s', log_text)
    if throughput:
        metrics['phy_mode'] = 'arq'
        metrics['arq_throughput_kib_s'] = round(float(throughput.group(1)), 6)

    data_kib = re.search(r'数据量:\s*([-\d.]+)\s*KB', log_text)
    if data_kib:
        metrics['phy_mode'] = 'arq'
        metrics['arq_data_kib'] = round(float(data_kib.group(1)), 6)

    still_missing = re.search(r'仍缺失:\s*(\d+)\s*帧', log_text)
    if still_missing:
        metrics['phy_mode'] = 'arq'
        metrics['arq_still_missing_frames'] = int(still_missing.group(1))

    received_size = re.search(r'写入\s+(\d+)\s+bytes', log_text)
    if received_size:
        metrics['received_size'] = int(received_size.group(1))

    return metrics


def print_radio_metrics(metrics: dict[str, object]) -> None:
    """输出上层 wrapper 可解析的无线统计摘要。"""
    if metrics.get('snr_db') is not None:
        print(
            '[OTA] 无线前导码残差SNR估计: '
            f'{float(metrics["snr_db"]):.3f} dB '
            f'noise_var={metrics["noise_var"]} '
            f'multipath={metrics["multipath"]} '
            f'rms_delay={metrics["rms_delay"]} '
            f'coh={metrics["coh"]} '
            f'amp={metrics["amp"]}'
        )

    if metrics.get('expected_payload') is not None:
        print(
            '[OTA] 无线统计: '
            f'frames_ok={metrics["frames_ok"]} '
            f'duplicates={metrics["frames_duplicate"]} '
            f'hdr_crc={metrics["frames_bad_hdr"]} '
            f'frame_crc={metrics["frames_bad_crc"]} '
            f'fec_fail={metrics["frames_fec_fail"]} '
            f'unique={metrics["max_unique_seen"]} '
            f'payload={metrics["max_payload_seen"]}/{metrics["expected_payload"]}'
        )

    if (
        metrics.get('arq_nack_rounds') is not None
        or metrics.get('arq_throughput_kib_s') is not None
        or metrics.get('arq_data_kib') is not None
        or metrics.get('arq_still_missing_frames') is not None
    ):
        print(
            '[OTA] ARQ统计: '
            f'nack_rounds={metrics.get("arq_nack_rounds")} '
            f'throughput_kib_s={metrics.get("arq_throughput_kib_s")} '
            f'data_kib={metrics.get("arq_data_kib")} '
            f'still_missing_frames={metrics.get("arq_still_missing_frames", 0)} '
            f'received_size={metrics.get("received_size")}'
        )


def print_channel_metrics(metrics: dict[str, object]) -> None:
    """输出 BER / 误帧率等链路质量指标。"""
    if metrics.get('chunk_total') is not None:
        print(
            '[OTA] 分块统计: '
            f'chunk_completed={metrics.get("chunk_completed")} '
            f'chunk_total={metrics.get("chunk_total")} '
            f'chunk_retry_used={metrics.get("chunk_retry_used", 0)}'
        )

    if metrics.get('frame_error_rate') is not None:
        print(
            '[OTA] 无线质量: '
            f'frame_error_rate={metrics.get("frame_error_rate")} '
            f'duplicate_rate={metrics.get("duplicate_rate")} '
            f'payload_completion={metrics.get("payload_completion")}'
        )

    if metrics.get('post_fec_ber') is not None:
        print(
            '[OTA] 无线BER: '
            f'post_fec_ber={metrics["post_fec_ber"]} '
            f'byte_error_rate={metrics["byte_error_rate"]} '
            f'bit_errors={metrics["bit_errors"]} '
            f'byte_errors={metrics["byte_errors"]} '
            f'compared_bytes={metrics["compared_bytes"]}'
        )


def summarize_metric_samples(
    samples: list[dict[str, object]],
    *,
    prefix: str = '',
    count_key: str = 'sample_count',
) -> dict[str, object]:
    """汇总一组数值型无线统计样本。"""
    if not samples:
        return {}

    numeric_values: dict[str, list[float]] = {}
    for sample in samples:
        for key, value in sample.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                numeric_values.setdefault(key, []).append(float(value))

    summary: dict[str, object] = {
        count_key: len(samples),
    }
    for key, values in numeric_values.items():
        summary[f'{prefix}{key}_mean'] = round(sum(values) / len(values), 6)
        summary[f'{prefix}{key}_min'] = round(min(values), 6)
        summary[f'{prefix}{key}_max'] = round(max(values), 6)

    for total_key in (
        'frames_ok',
        'frames_duplicate',
        'frames_bad_crc',
        'frames_bad_hdr',
        'frames_fec_fail',
        'overflow_events',
        'chunk_retry_used',
        'bit_errors',
        'byte_errors',
        'compared_bytes',
    ):
        values = numeric_values.get(total_key) or []
        if values:
            summary[f'{prefix}{total_key}_total'] = int(round(sum(values)))

    return summary


def extract_remote_log_progress(log_text: str) -> dict[str, bool]:
    """从远端 RX 日志尾部提取轻量进展标记。"""
    if not log_text:
        return {}

    return {
        'rx_log_saw_waiting': (
            '[RX] 等待信号' in log_text or '[RX] 离线回放' in log_text
        ),
        'rx_log_saw_preamble': ('PREAMBLE CHAN' in log_text),
        'rx_log_saw_header': (
            'HEADER OK' in log_text or 'HEADER CRC FAIL' in log_text
        ),
        'rx_log_saw_need_more': (
            'NEED MORE:' in log_text or 'NEED MORE 放弃:' in log_text
        ),
        'rx_log_saw_async_decode': (
            '开始异步解码' in log_text or '→ 异步解码' in log_text
        ),
        'rx_log_saw_decode_ok': ('decode_search:' in log_text and ' OK' in log_text),
        'rx_log_saw_output_write': ('[RX] 写入 ' in log_text),
    }


def extract_relevant_remote_log_window(log_text: str) -> str:
    """从日志尾部提取与最近一次有效进展最相关的窗口。"""
    if not log_text:
        return ''

    lines = [line.rstrip() for line in log_text.splitlines() if line.strip()]
    if not lines:
        return ''

    marker_groups = (
        ('[RX] 写入 ',),
        ('decode_search:',),
        ('开始异步解码', '→ 异步解码'),
        ('HEADER OK', 'NEED MORE:', 'NEED MORE 放弃:'),
        ('HEADER FAIL', 'PREAMBLE CHAN'),
    )
    target_index = -1
    for markers in marker_groups:
        for index in range(len(lines) - 1, -1, -1):
            if any(marker in lines[index] for marker in markers):
                target_index = index
                break
        if target_index >= 0:
            break

    if target_index < 0:
        return '\n'.join(lines[-12:])

    start = max(0, target_index - 10)
    end = min(len(lines), target_index + 6)
    return '\n'.join(lines[start:end]).strip()


def format_remote_log_excerpt(
    log_text: str,
    *,
    max_lines: int = 8,
    max_chars: int = 1200,
) -> str:
    """压缩远端日志尾部，便于写入 JSON 留档。"""
    if not log_text:
        return ''

    lines = [line.rstrip() for line in log_text.splitlines() if line.strip()]
    if not lines:
        return ''

    excerpt = '\n'.join(lines[-max(1, int(max_lines)):])
    if len(excerpt) > max_chars:
        excerpt = excerpt[-max_chars:]
    return excerpt


def compact_daemon_attempt_metrics(metrics: dict[str, object]) -> dict[str, object]:
    """抽取 daemon 模式单次 attempt 的核心诊断字段。"""
    selected_keys = (
        'typical_sec',
        'rx_timeout_sec',
        'no_frame_timeout_sec',
        'wait_timeout_sec',
        'tx_wall_sec',
        'elapsed_sec',
        'attempt_wall_sec',
        'frames_ok',
        'frames_duplicate',
        'frames_bad_crc',
        'frames_bad_hdr',
        'frames_fec_fail',
        'expected_payload',
        'max_payload_seen',
        'max_unique_seen',
        'snr_db',
        'noise_var',
        'rms_delay',
        'coh',
        'amp',
        'frame_error_rate',
        'duplicate_rate',
        'payload_completion',
        'post_fec_ber',
        'byte_error_rate',
        'remote_no_signal_abort',
        'remote_saw_preamble',
        'remote_saw_header',
        'remote_saw_payload',
        'rx_late_wait_sec',
        'rx_late_wait_hit',
        'rx_late_ok',
        'rx_late_message',
        'rx_async_grace_wait_sec',
        'rx_async_grace_wait_hit',
        'rx_async_grace_wait_ok',
        'rx_async_grace_wait_message',
        'rx_output_salvaged',
        'rx_output_salvaged_bytes',
        'rx_output_salvage_grace_sec',
        'rx_output_remote_exists',
        'rx_output_remote_size',
        'rx_daemon_ready_after_timeout',
        'rx_daemon_proc_count_after_timeout',
        'rx_daemon_proc_pids_after_timeout',
        'rx_session_reused_after_failure',
        'daemon_error',
        'rx_fetch_error',
        'rx_late_wait_error',
        'rx_async_grace_wait_error',
        'rx_status_error',
        'rx_log_error',
        'rx_cleanup_error',
        'rx_log_saw_waiting',
        'rx_log_saw_preamble',
        'rx_log_saw_header',
        'rx_log_saw_need_more',
        'rx_log_saw_async_decode',
        'rx_log_saw_decode_ok',
        'rx_log_saw_output_write',
        'remote_log_excerpt',
    )
    compact: dict[str, object] = {}
    for key in selected_keys:
        if key not in metrics:
            continue
        value = metrics.get(key)
        if value is None:
            continue
        compact[key] = value
    return compact


def enrich_channel_metrics(
    metrics: dict[str, object],
    expected_bytes: bytes,
    received_bytes: bytes,
) -> dict[str, object]:
    """基于原始密文与接收密文，补齐 BER / 误帧率等质量指标。"""
    frames_ok = int(metrics.get('frames_ok') or 0)
    frames_duplicate = int(metrics.get('frames_duplicate') or 0)
    frames_bad_crc = int(metrics.get('frames_bad_crc') or 0)
    frames_bad_hdr = int(metrics.get('frames_bad_hdr') or 0)
    frames_fec_fail = int(metrics.get('frames_fec_fail') or 0)

    observed_frames = frames_ok + frames_bad_crc + frames_bad_hdr + frames_fec_fail
    total_rx_events = observed_frames + frames_duplicate
    if observed_frames > 0:
        metrics['frame_error_rate'] = round(
            (frames_bad_crc + frames_bad_hdr + frames_fec_fail) / observed_frames,
            6,
        )
    if total_rx_events > 0:
        metrics['duplicate_rate'] = round(frames_duplicate / total_rx_events, 6)

    expected_payload = int(metrics.get('expected_payload') or 0)
    max_payload_seen = int(metrics.get('max_payload_seen') or 0)
    if expected_payload > 0:
        metrics['payload_completion'] = round(max_payload_seen / expected_payload, 6)

    if not expected_bytes:
        return metrics

    expected_len = len(expected_bytes)
    compared = received_bytes[:expected_len]
    if len(compared) < expected_len:
        compared = compared + (b'\x00' * (expected_len - len(compared)))

    byte_errors = sum(1 for left, right in zip(expected_bytes, compared) if left != right)
    bit_errors = sum((left ^ right).bit_count() for left, right in zip(expected_bytes, compared))
    metrics['bit_errors'] = bit_errors
    metrics['byte_errors'] = byte_errors
    metrics['compared_bytes'] = expected_len
    metrics['byte_error_rate'] = round(byte_errors / expected_len, 8)
    metrics['post_fec_ber'] = round(bit_errors / (expected_len * 8), 8)
    return metrics


def build_ssh_prefix(host: str, user: str, password: str, port: str) -> list[str]:
    """构造 sshpass + ssh 前缀。"""
    return [
        'sshpass', '-p', password,
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'LogLevel=ERROR',
        '-p', str(port),
        f'{user}@{host}',
    ]


def build_scp_prefix(host: str, user: str, password: str, port: str) -> list[str]:
    """构造 sshpass + scp 前缀。"""
    return [
        'sshpass', '-p', password,
        'scp',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        '-o', 'LogLevel=ERROR',
        '-P', str(port),
    ]


def remote_read_file_base64_command(remote_path: str) -> str:
    """在远端把小文件编码成 base64 输出到 stdout。"""
    return (
        'python3 - <<\'PY\'\n'
        'import base64, os, sys\n'
        f'path={remote_path!r}\n'
        'if not os.path.exists(path):\n'
        '    raise SystemExit(2)\n'
        'with open(path, "rb") as handle:\n'
        '    data = handle.read()\n'
        'sys.stdout.write(base64.b64encode(data).decode("ascii"))\n'
        'PY'
    )


def run_text_command(cmd: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """执行文本命令。"""
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def run_text_command_best_effort(
    cmd: list[str],
    timeout: float,
    label: str,
) -> subprocess.CompletedProcess[str] | None:
    """执行文本命令；若超时则仅告警，不再向上抛异常。"""
    try:
        return run_text_command(cmd, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f'[OTA] {label} 超时，忽略并继续')
        return None


def kill_process_group_best_effort(
    proc: subprocess.Popen[str],
    label: str,
) -> None:
    """尽力终止通过 start_new_session 启动的子进程组。"""
    if proc.poll() is not None:
        return

    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        print(f'[OTA] {label} 本地进程组清理被拒绝，忽略并继续')
        return

    deadline = time.monotonic() + 5.0
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)

    if proc.poll() is None:
        print(f'[OTA] {label} 本地进程组仍未退出，继续后续远端回收')


def communicate_with_deadline(
    proc: subprocess.Popen[str],
    timeout: float,
) -> tuple[str, bool]:
    """按总时限轮询等待子进程，避免单次 communicate 卡死。"""
    stdout_text = ''
    deadline = time.monotonic() + max(0.1, float(timeout))

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return stdout_text, True

        try:
            stdout_text, _ = proc.communicate(timeout=min(1.0, remaining))
            return stdout_text, False
        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout or stdout_text or ''


def read_process_line(
    proc: subprocess.Popen[str],
    *,
    timeout: float,
    label: str,
) -> str:
    """按行读取 daemon stdout，支持超时。"""
    if proc.stdout is None:
        raise RuntimeError(f'{label} stdout 不可用')

    fd = proc.stdout.fileno()
    deadline = time.monotonic() + max(0.1, float(timeout))
    chunks: list[bytes] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f'{label} 读取超时 ({timeout}s)')
        ready, _, _ = select.select([fd], [], [], min(remaining, 0.5))
        if not ready:
            if proc.poll() is not None:
                raise RuntimeError(f'{label} 已退出 (rc={proc.returncode})')
            continue
        raw = os.read(fd, 1)
        if not raw:
            raise RuntimeError(f'{label} stdout 已关闭')
        if raw == b'\n':
            return b''.join(chunks).decode('utf-8', errors='ignore')
        chunks.append(raw)


def read_file_tail(path: str, max_bytes: int = 4000) -> str:
    """读取本地日志尾部。"""
    if not path or not os.path.exists(path):
        return ''
    with open(path, 'rb') as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size > max_bytes:
            handle.seek(size - max_bytes)
        data = handle.read()
    return data.decode('utf-8', errors='ignore').strip()


def parse_daemon_status_line(line: str) -> tuple[str, dict[str, str]]:
    """解析 daemon 单行响应。"""
    fields = [field for field in line.strip().split('\t') if field]
    if not fields:
        return '', {}
    status = fields[0]
    payload: dict[str, str] = {}
    for field in fields[1:]:
        if '=' not in field:
            continue
        key, value = field.split('=', 1)
        payload[key] = value
    return status, payload


def parse_rx_daemon_metrics(
    status: str,
    fields: dict[str, str],
) -> tuple[bool, int, dict[str, object], str, bytes]:
    """将 RX daemon 响应转换为 OTA 统计口径。"""
    def _int(name: str) -> int | None:
        value = fields.get(name)
        if value is None or value == '':
            return None
        return int(float(value))

    def _float(name: str) -> float | None:
        value = fields.get(name)
        if value is None or value == '':
            return None
        return float(value)

    radio_metrics: dict[str, object] = {
        'elapsed_sec': _float('elapsed_sec'),
        'frames_ok': _int('frames_ok'),
        'frames_duplicate': _int('frames_duplicate'),
        'frames_bad_crc': _int('frames_bad_crc'),
        'frames_bad_hdr': _int('frames_bad_hdr'),
        'frames_fec_fail': _int('frames_fec_fail'),
        'expected_payload': _int('expected_payload'),
        'max_payload_seen': _int('max_payload_seen'),
        'max_unique_seen': _int('max_unique_seen'),
        'overflow_events': _int('overflow_events'),
    }
    if 'snr_db' in fields:
        radio_metrics['snr_db'] = round(float(fields['snr_db']), 3)
    if 'noise_var' in fields:
        radio_metrics['noise_var'] = round(float(fields['noise_var']), 6)
    if 'multipath' in fields:
        radio_metrics['multipath'] = int(float(fields['multipath']))
    if 'rms_delay' in fields:
        radio_metrics['rms_delay'] = round(float(fields['rms_delay']), 6)
    if 'coh' in fields:
        radio_metrics['coh'] = round(float(fields['coh']), 3)
    if 'amp' in fields:
        radio_metrics['amp'] = round(float(fields['amp']), 3)

    received_bytes = _int('received_bytes') or 0
    message = fields.get('message', '')
    output_hex = fields.get('output_hex', '')
    payload_bytes = bytes.fromhex(output_hex) if output_hex else b''
    return status == 'OK', received_bytes, radio_metrics, message, payload_bytes


class LocalTxDaemonSession:
    """复用本地 TX 进程，避免重复设备初始化。"""

    def __init__(
        self,
        *,
        tx_bin: str,
        tx_args: str,
        rate: float,
        freq: float,
        tx_gain: float,
        log_path: str,
    ) -> None:
        self._tx_bin = tx_bin
        self._tx_args = tx_args
        self._rate = rate
        self._freq = freq
        self._tx_gain = tx_gain
        self._log_path = log_path
        self._log_handle = None
        self._proc: subprocess.Popen[str] | None = None

    def ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)
        self._log_handle = open(self._log_path, 'a', encoding='utf-8')
        cmd = [
            self._tx_bin,
            '--daemon',
            '--args', self._tx_args,
            '--rate', str(self._rate),
            '--freq', str(self._freq),
            '--gain', str(self._tx_gain),
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log_handle,
            text=True,
            bufsize=1,
        )
        ready_line = read_process_line(self._proc, timeout=30.0, label='本地 TX daemon')
        if ready_line.strip() != 'READY':
            detail = read_file_tail(self._log_path)
            self.close()
            raise RuntimeError(f'本地 TX daemon 未就绪: {ready_line}\n{detail}')

    def send(
        self,
        *,
        file_path: str,
        repeat: int,
        frame_repeat: int,
        start_pad_samps: int,
        round_gap_ms: int,
        warmup_frames: int,
        warmup_repeats: int,
        warmup_rounds: int,
        tail_pad_samps: int,
        last_frame_extra_repeats: int,
        first_frame_extra_repeats: int,
        timeout: float,
    ) -> dict[str, str]:
        self.ensure_started()
        assert self._proc is not None and self._proc.stdin is not None
        command = '\t'.join([
            'SEND',
            file_path,
            str(repeat),
            str(frame_repeat),
            str(start_pad_samps),
            str(round_gap_ms),
            str(warmup_frames),
            str(warmup_repeats),
            str(warmup_rounds),
            str(tail_pad_samps),
            str(last_frame_extra_repeats),
            str(first_frame_extra_repeats),
        ]) + '\n'
        self._proc.stdin.write(command)
        self._proc.stdin.flush()
        line = read_process_line(self._proc, timeout=timeout, label='本地 TX daemon')
        status, fields = parse_daemon_status_line(line)
        if status != 'OK':
            detail = read_file_tail(self._log_path)
            message = fields.get('message', line.strip())
            raise RuntimeError(f'本地 TX daemon 发送失败: {message}\n{detail}')
        return fields

    def close(self) -> None:
        if self._proc is not None:
            try:
                if self._proc.stdin is not None and self._proc.poll() is None:
                    self._proc.stdin.write('QUIT\n')
                    self._proc.stdin.flush()
                    read_process_line(self._proc, timeout=5.0, label='本地 TX daemon')
            except Exception:
                pass
            try:
                self._proc.kill()
                self._proc.wait(timeout=5.0)
            except Exception:
                pass
            self._proc = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None


class RemoteRxDaemonSession:
    """复用远端 RX daemon，避免每块重复 SSH + UHD 初始化。"""

    def __init__(
        self,
        *,
        board_host: str,
        board_user: str,
        board_pass: str,
        board_port: str,
        remote_build_dir: str,
        rx_args: str,
        rx_gain: float,
        rate: float,
        freq: float,
        rx_spb: int,
        rx_setup: float,
        rx_ant: str,
        payload_search_order: str,
        decode_workers: int,
        default_no_frame_timeout: float,
        remote_use_sudo: bool,
        session_tag: str,
    ) -> None:
        self._board_host = board_host
        self._board_user = board_user
        self._board_pass = board_pass
        self._board_port = board_port
        self._remote_build_dir = remote_build_dir
        self._rx_args = rx_args
        self._rx_gain = rx_gain
        self._rate = rate
        self._freq = freq
        self._rx_spb = rx_spb
        self._rx_setup = rx_setup
        self._rx_ant = rx_ant
        self._payload_search_order = payload_search_order
        self._decode_workers = decode_workers
        self._default_no_frame_timeout = default_no_frame_timeout
        self._remote_use_sudo = remote_use_sudo
        self._session_tag = session_tag
        self._remote_proc_tag = f'usrp_rx_daemon_{session_tag}'
        self._remote_output = f'/tmp/{session_tag}.bin'
        self._remote_log = f'/tmp/{session_tag}.log'
        self._ssh_prefix = build_ssh_prefix(board_host, board_user, board_pass, board_port)
        self._proc: subprocess.Popen[str] | None = None
        self._pending_receive = False

    @property
    def remote_output(self) -> str:
        return self._remote_output

    def _build_remote_cmd(self) -> str:
        rx_bin = f'{self._remote_build_dir.rstrip("/")}/usrp_tensor_rx'
        ant_clause = f' --ant {shlex.quote(self._rx_ant)}' if self._rx_ant else ''
        base_cmd = (
            f'cd {shlex.quote(self._remote_build_dir)} && '
            f'rm -f {shlex.quote(self._remote_output)} {shlex.quote(self._remote_log)} && '
            f'exec -a {shlex.quote(self._remote_proc_tag)} {shlex.quote(rx_bin)} --daemon '
            f'--args {shlex.quote(self._rx_args)} '
            f'--rate {self._rate} '
            f'--freq {self._freq} '
            f'--gain {self._rx_gain} '
            f'{ant_clause} '
            f'--spb {self._rx_spb} '
            f'--setup {self._rx_setup} '
            f'--timeout {self._default_no_frame_timeout} '
            f'--decode-workers {self._decode_workers} '
            f'--payload-search-order {shlex.quote(self._payload_search_order)} '
            f'2>> {shlex.quote(self._remote_log)}'
        )
        shell_cmd = f'bash -lc {shlex.quote(base_cmd)}'
        return wrap_remote_shell_command(
            shell_cmd,
            self._board_pass if self._remote_use_sudo else '',
        )

    def _kill_remote_daemon(self) -> None:
        run_text_command_best_effort(
            self._ssh_prefix + [wrap_remote_shell_command(
                remote_kill_command(
                    self._remote_proc_tag,
                    match_mode='argv0_prefix',
                ),
                self._board_pass if self._remote_use_sudo else '',
            )],
            timeout=8.0,
            label='远端 RX daemon kill',
        )

    def ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        self._kill_remote_daemon()
        self._proc = subprocess.Popen(
            self._ssh_prefix + [self._build_remote_cmd()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready_line = read_process_line(self._proc, timeout=40.0, label='远端 RX daemon')
        if ready_line.strip() != 'READY':
            detail = self.read_remote_log_tail()
            self.close()
            raise RuntimeError(f'远端 RX daemon 未就绪: {ready_line}\n{detail}')

    def begin_receive(self, *, no_frame_timeout: float) -> None:
        self.ensure_started()
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(
            f'RECV\t{self._remote_output}\t{float(no_frame_timeout)}\n'
        )
        self._proc.stdin.flush()
        self._pending_receive = True

    def wait_receive(self, *, timeout: float) -> tuple[bool, int, dict[str, object], str, bytes]:
        if not self._pending_receive:
            raise RuntimeError('远端 RX daemon 当前没有待完成的 RECV')
        assert self._proc is not None
        line = read_process_line(self._proc, timeout=timeout, label='远端 RX daemon')
        self._pending_receive = False
        status, fields = parse_daemon_status_line(line)
        return parse_rx_daemon_metrics(status, fields)

    def wait_receive_grace(
        self,
        *,
        timeout: float,
    ) -> tuple[bool, int, dict[str, object], str, bytes] | None:
        """在超时后再给 daemon 一个短窗口，等待迟到的 RECV 结果。"""
        if not self._pending_receive:
            return None
        try:
            return self.wait_receive(timeout=timeout)
        except TimeoutError:
            return None

    def fetch_output(self, local_path: str, *, timeout: float = 6.0) -> bool:
        return fetch_remote_file(
            self._board_host,
            self._board_user,
            self._board_pass,
            self._board_port,
            self._remote_output,
            local_path,
            timeout=timeout,
        )

    def fetch_output_immediate(
        self,
        *,
        local_path: str,
        expected_size: int,
        attempts: int = 3,
        fetch_timeout: float = 6.0,
        prefer_inline: bool = False,
    ) -> bool:
        for _ in range(max(1, int(attempts))):
            fetched = False
            if (
                prefer_inline
                and expected_size > 0
                and expected_size <= INLINE_FETCH_MAX_BYTES
            ):
                fetched = fetch_remote_file_inline_base64(
                    self._board_host,
                    self._board_user,
                    self._board_pass,
                    self._board_port,
                    self._remote_output,
                    local_path,
                    timeout=max(4.0, float(fetch_timeout)),
                )

            if not fetched:
                fetched = self.fetch_output(local_path, timeout=fetch_timeout)

            if fetched:
                if expected_size <= 0:
                    return True
                if os.path.exists(local_path) and os.path.getsize(local_path) >= expected_size:
                    return True
            time.sleep(0.25)
        return False

    def fetch_output_until_ready(
        self,
        *,
        local_path: str,
        expected_size: int,
        timeout: float,
        poll_interval: float = 0.75,
        fetch_timeout: float = 6.0,
        prefer_inline: bool = False,
    ) -> bool:
        deadline = time.monotonic() + max(0.1, float(timeout))
        while time.monotonic() < deadline:
            if self.fetch_output_immediate(
                local_path=local_path,
                expected_size=expected_size,
                attempts=1,
                fetch_timeout=fetch_timeout,
                prefer_inline=prefer_inline,
            ):
                return True
            time.sleep(max(0.1, float(poll_interval)))
        return False

    def fetch_output_when_ready(
        self,
        *,
        local_path: str,
        expected_size: int,
        timeout: float,
        attempts: int = 3,
    ) -> bool:
        status = self.wait_output_ready(
            expected_size=expected_size,
            timeout=timeout,
        )
        del status

        return self.fetch_output_immediate(
            local_path=local_path,
            expected_size=expected_size,
            attempts=attempts,
        )

    def query_status(self, *, timeout: float = 5.0) -> dict[str, str]:
        return query_remote_status(
            ssh_prefix=self._ssh_prefix,
            board_pass=self._board_pass,
            remote_output=self._remote_output,
            remote_log=self._remote_log,
            remote_use_sudo=self._remote_use_sudo,
            timeout=timeout,
            label='远端 RX daemon 状态查询',
            remote_tag=self._remote_proc_tag,
            remote_match_mode='argv0_prefix',
        )

    def wait_output_ready(self, *, expected_size: int, timeout: float) -> dict[str, str]:
        if expected_size <= 0:
            return {}

        deadline = time.monotonic() + max(0.1, float(timeout))
        last_status: dict[str, str] = {}
        while time.monotonic() < deadline:
            status = self.query_status(timeout=min(3.0, max(1.0, deadline - time.monotonic())))
            if status:
                last_status = status
                if status.get('exists', '0') == '1':
                    size = int(status.get('size', '0') or '0')
                    if size >= expected_size:
                        return status
            time.sleep(0.25)
        return last_status

    def cleanup_output(self) -> None:
        run_text_command_best_effort(
            self._ssh_prefix + [wrap_remote_shell_command(
                f'rm -f {shlex.quote(self._remote_output)}',
                self._board_pass if self._remote_use_sudo else '',
            )],
            timeout=4.0,
            label='远端 RX 输出清理',
        )

    def read_remote_log_tail(self) -> str:
        result = run_text_command_best_effort(
            self._ssh_prefix + [wrap_remote_shell_command(
                f'tail -n 40 {shlex.quote(self._remote_log)} 2>/dev/null || true',
                self._board_pass if self._remote_use_sudo else '',
            )],
            timeout=4.0,
            label='远端 RX 日志读取',
        )
        return (result.stdout or '').strip() if result else ''

    def close(self) -> None:
        if self._proc is not None:
            try:
                if (
                    not self._pending_receive
                    and self._proc.stdin is not None
                    and self._proc.poll() is None
                ):
                    self._proc.stdin.write('QUIT\n')
                    self._proc.stdin.flush()
                    read_process_line(self._proc, timeout=5.0, label='远端 RX daemon')
            except Exception:
                pass
            try:
                self._proc.kill()
                self._proc.wait(timeout=3.0)
            except Exception:
                pass
            self._proc = None
            self._pending_receive = False

        self._kill_remote_daemon()
        run_text_command_best_effort(
            self._ssh_prefix + [wrap_remote_shell_command(
                f'rm -f {shlex.quote(self._remote_output)} {shlex.quote(self._remote_log)}',
                self._board_pass if self._remote_use_sudo else '',
            )],
            timeout=5.0,
            label='远端 RX daemon 清理',
        )


class ChunkedRemoteOtaDaemonSession:
    """跨多次发送复用本地 TX / 远端 RX daemon。"""

    def __init__(
        self,
        *,
        tx_args: str,
        rx_args: str,
        tx_gain: float,
        rx_gain: float,
        rate: float,
        freq: float,
        repeat: int,
        rx_timeout: float,
        ota_wait: float,
        start_pad_samps: int,
        round_gap_ms: int,
        frame_repeat: int,
        rx_spb: int,
        rx_setup: float,
        no_frame_timeout: float,
        rx_ant: str,
        payload_search_order: str,
        decode_workers: int,
        warmup_frames: int,
        warmup_repeats: int,
        warmup_rounds: int,
        tail_pad_samps: int,
        last_frame_extra_repeats: int,
        first_frame_extra_repeats: int,
        board_host: str,
        board_user: str,
        board_pass: str,
        board_port: str,
        remote_build_dir: str,
    ) -> None:
        self._tx_args = tx_args
        self._rx_args = rx_args
        self._tx_gain = tx_gain
        self._rx_gain = rx_gain
        self._rate = rate
        self._freq = freq
        self._repeat = repeat
        self._rx_timeout = rx_timeout
        self._ota_wait = ota_wait
        self._start_pad_samps = start_pad_samps
        self._round_gap_ms = round_gap_ms
        self._frame_repeat = frame_repeat
        self._rx_spb = rx_spb
        self._rx_setup = rx_setup
        self._no_frame_timeout = no_frame_timeout
        self._rx_ant = rx_ant
        self._payload_search_order = payload_search_order
        self._decode_workers = decode_workers
        self._warmup_frames = warmup_frames
        self._warmup_repeats = warmup_repeats
        self._warmup_rounds = warmup_rounds
        self._tail_pad_samps = tail_pad_samps
        self._last_frame_extra_repeats = last_frame_extra_repeats
        self._first_frame_extra_repeats = first_frame_extra_repeats
        self._board_host = board_host
        self._board_user = board_user
        self._board_pass = board_pass
        self._board_port = board_port
        self._remote_build_dir = remote_build_dir

        build_dir = os.path.join(os.path.dirname(__file__), '..', 'usrp_tensor', 'build')
        self._tx_bin = os.path.join(build_dir, 'usrp_tensor_tx')
        self._remote_use_sudo = False
        self._ready = False
        self._tx_session: LocalTxDaemonSession | None = None
        self._rx_session: RemoteRxDaemonSession | None = None
        self._success_elapsed_sec: list[float] = []
        self._temp_dir_obj = tempfile.TemporaryDirectory(prefix='e2e_ota_daemon_')
        self._temp_dir = self._temp_dir_obj.name
        self._session_tag = f'e2e_usrp_daemon_{int(time.time())}_{os.getpid()}'
        self._transfer_seq = 0

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        if not os.path.exists(self._tx_bin):
            raise RuntimeError(f'找不到 TX: {self._tx_bin}，请先编译')

        remote_ready, remote_use_sudo = prime_remote_usrp(
            self._board_host,
            self._board_user,
            self._board_pass,
            self._board_port,
            self._rx_args,
            'RX',
        )
        if not remote_ready:
            raise RuntimeError('远端 USRP 未就绪')
        if not prime_local_usrp(self._tx_args, 'TX'):
            raise RuntimeError('本地 USRP 未就绪')

        self._remote_use_sudo = remote_use_sudo
        self._ready = True

    def _close_tx_session(self) -> None:
        if self._tx_session is not None:
            self._tx_session.close()
            self._tx_session = None

    def _close_rx_session(self) -> None:
        if self._rx_session is not None:
            self._rx_session.close()
            self._rx_session = None

    def _close_sessions(self) -> None:
        self._close_tx_session()
        self._close_rx_session()

    def _ensure_sessions(self) -> tuple[LocalTxDaemonSession, RemoteRxDaemonSession]:
        self._ensure_ready()

        if self._tx_session is None:
            self._tx_session = LocalTxDaemonSession(
                tx_bin=self._tx_bin,
                tx_args=self._tx_args,
                rate=self._rate,
                freq=self._freq,
                tx_gain=self._tx_gain,
                log_path=os.path.join(self._temp_dir, 'tx_daemon.log'),
            )
            self._tx_session.ensure_started()

        if self._rx_session is None:
            self._rx_session = RemoteRxDaemonSession(
                board_host=self._board_host,
                board_user=self._board_user,
                board_pass=self._board_pass,
                board_port=self._board_port,
                remote_build_dir=self._remote_build_dir,
                rx_args=self._rx_args,
                rx_gain=self._rx_gain,
                rate=self._rate,
                freq=self._freq,
                rx_spb=self._rx_spb,
                rx_setup=self._rx_setup,
                rx_ant=self._rx_ant or 'TX/RX',
                payload_search_order=self._payload_search_order,
                decode_workers=self._decode_workers,
                default_no_frame_timeout=self._no_frame_timeout,
                remote_use_sudo=self._remote_use_sudo,
                session_tag=self._session_tag,
            )
            self._rx_session.ensure_started()

        return self._tx_session, self._rx_session

    def _salvage_rx_output_after_failure(
        self,
        *,
        rx_daemon: RemoteRxDaemonSession,
        chunk_output: str,
        expected_size: int,
        metrics: dict[str, object],
        error: Exception,
    ) -> tuple[str, bool]:
        remote_tail = ''
        fetched_output = False
        late_status_consumed = False
        cleanup_done = False

        def handle_late_result(
            late_result: tuple[bool, int, dict[str, object], str, bytes],
            *,
            wait_key: str,
        ) -> None:
            nonlocal fetched_output, late_status_consumed, cleanup_done

            rx_ok, _received_bytes, radio_metrics, rx_message, rx_payload = late_result
            late_status_consumed = True
            metrics[f'{wait_key}_hit'] = True
            metrics[f'{wait_key}_ok'] = rx_ok
            if rx_message:
                metrics[f'{wait_key}_message'] = rx_message
            metrics.update(radio_metrics)

            if rx_ok:
                if rx_payload:
                    with open(chunk_output, 'wb') as handle:
                        handle.write(rx_payload)
                    fetched_output = True
                else:
                    try:
                        fetched_output = rx_daemon.fetch_output_immediate(
                            local_path=chunk_output,
                            expected_size=expected_size,
                            attempts=2,
                            prefer_inline=(expected_size <= INLINE_FETCH_MAX_BYTES),
                        )
                    except Exception as exc:
                        metrics['rx_fetch_error'] = str(exc)

            try:
                rx_daemon.cleanup_output()
                cleanup_done = True
            except Exception as exc:
                metrics['rx_cleanup_error'] = str(exc)

        if isinstance(error, TimeoutError):
            late_wait_sec = max(
                2.0,
                min(
                    6.0,
                    float(metrics.get('wait_timeout_sec') or 0.0) * 0.2,
                ),
            )
            metrics['rx_late_wait_sec'] = round(late_wait_sec, 6)
            try:
                late_result = rx_daemon.wait_receive_grace(timeout=late_wait_sec)
            except Exception as exc:
                metrics['rx_late_wait_error'] = str(exc)
                late_result = None

            if late_result is not None:
                handle_late_result(late_result, wait_key='rx_late_wait')
            else:
                metrics['rx_late_wait_hit'] = False

        try:
            remote_tail = rx_daemon.read_remote_log_tail()
        except Exception as exc:
            metrics['rx_log_error'] = str(exc)
            remote_tail = ''

        if remote_tail:
            metrics.update(extract_remote_log_progress(remote_tail))
            current_receive_tail = extract_relevant_remote_log_window(remote_tail)
            tail_metrics = extract_radio_metrics(current_receive_tail)
            for key, value in tail_metrics.items():
                if value is not None:
                    metrics[key] = value
            log_excerpt = format_remote_log_excerpt(current_receive_tail)
            if log_excerpt:
                metrics['remote_log_excerpt'] = log_excerpt

            if (
                not late_status_consumed
                and not fetched_output
                and metrics.get('rx_log_saw_async_decode')
            ):
                async_grace_sec = max(
                    4.0,
                    min(
                        8.0,
                        float(metrics.get('no_frame_timeout_sec') or 0.0) + 2.0,
                    ),
                )
                metrics['rx_async_grace_wait_sec'] = round(async_grace_sec, 6)
                try:
                    late_result = rx_daemon.wait_receive_grace(timeout=async_grace_sec)
                except Exception as exc:
                    metrics['rx_async_grace_wait_error'] = str(exc)
                    late_result = None

                if late_result is not None:
                    handle_late_result(late_result, wait_key='rx_async_grace_wait')
                else:
                    metrics['rx_async_grace_wait_hit'] = False

        status: dict[str, str] = {}
        if not fetched_output:
            salvage_fetch_sec = 0.0
            if metrics.get('rx_log_saw_async_decode'):
                salvage_fetch_sec = 6.0
            elif metrics.get('rx_log_saw_header'):
                salvage_fetch_sec = 2.0

            try:
                status = rx_daemon.query_status(timeout=1.5)
            except Exception as exc:
                metrics['rx_status_error'] = str(exc)
                status = {}

            if status:
                metrics['rx_output_remote_exists'] = (status.get('exists', '0') == '1')
                metrics['rx_output_remote_size'] = int(status.get('size', '0') or '0')
                metrics['rx_daemon_ready_after_timeout'] = (status.get('ready', '0') == '1')
                metrics['rx_daemon_proc_count_after_timeout'] = int(status.get('proc_count', '0') or '0')
                metrics['rx_daemon_proc_pids_after_timeout'] = str(status.get('proc_pids', ''))

            try:
                if (
                    status.get('exists', '0') == '1'
                    and int(status.get('size', '0') or '0') >= expected_size
                ):
                    fetched_output = rx_daemon.fetch_output_immediate(
                        local_path=chunk_output,
                        expected_size=expected_size,
                        attempts=2,
                        fetch_timeout=10.0 if metrics.get('rx_log_saw_output_write') else 6.0,
                        prefer_inline=bool(metrics.get('rx_log_saw_output_write')),
                    )
                elif salvage_fetch_sec > 0:
                    fetched_output = rx_daemon.fetch_output_until_ready(
                        local_path=chunk_output,
                        expected_size=expected_size,
                        timeout=salvage_fetch_sec,
                        poll_interval=0.5,
                        fetch_timeout=10.0 if metrics.get('rx_log_saw_output_write') else 6.0,
                        prefer_inline=bool(metrics.get('rx_log_saw_output_write')),
                    )
            except Exception as exc:
                metrics['rx_fetch_error'] = str(exc)
                fetched_output = False

        if fetched_output and os.path.exists(chunk_output):
            if not cleanup_done:
                try:
                    rx_daemon.cleanup_output()
                except Exception as exc:
                    metrics['rx_cleanup_error'] = str(exc)
            salvaged_size = os.path.getsize(chunk_output)
            metrics['rx_output_salvaged'] = True
            metrics['rx_output_salvaged_bytes'] = salvaged_size
            salvage_grace_sec = 0.0
            if isinstance(error, TimeoutError):
                salvage_grace_sec += float(metrics.get('rx_late_wait_sec') or 0.0)
                salvage_grace_sec += float(metrics.get('rx_async_grace_wait_sec') or 0.0)
            if metrics.get('rx_log_saw_async_decode'):
                salvage_grace_sec += 6.0
            elif metrics.get('rx_log_saw_header'):
                salvage_grace_sec += 2.0
            metrics['rx_output_salvage_grace_sec'] = round(salvage_grace_sec, 6)
            print(f'[OTA] 远端 RX 超时后补抓输出成功: {salvaged_size}B')
        return remote_tail, late_status_consumed

    def transmit(
        self,
        wire_bytes: bytes,
        *,
        chunk_bytes: int,
        min_chunk_bytes: int = 0,
        chunk_retries: int = 0,
        chunk_align_bytes: int = DEFAULT_OTA_CHUNK_ALIGN_BYTES,
    ) -> tuple[bool, bytes, dict[str, object]]:
        self._ensure_ready()
        self._transfer_seq += 1
        transfer_tag = f'{self._transfer_seq:04d}'

        effective_min_chunk_bytes = int(min_chunk_bytes)
        if effective_min_chunk_bytes == 0 and chunk_align_bytes > 0 and chunk_bytes > chunk_align_bytes:
            effective_min_chunk_bytes = int(chunk_align_bytes)
            print(
                '[OTA] 未显式指定最小分块，启用自动降级: '
                f'min_chunk_bytes={effective_min_chunk_bytes}'
            )

        total_len = len(wire_bytes)
        retry_limit = max(0, int(chunk_retries))
        received_parts: list[tuple[int, bytes]] = []
        last_radio_metrics: dict[str, object] = {}
        pending_chunks: list[tuple[int, bytes]] = [
            (offset, wire_bytes[offset:offset + chunk_bytes])
            for offset in range(0, total_len, chunk_bytes)
        ]
        tail_rebalance_min_bytes = 0
        if chunk_align_bytes > 1:
            tail_rebalance_min_bytes = max(
                effective_min_chunk_bytes,
                int(chunk_align_bytes) * 2,
            )
        rebalanced_chunks = rebalance_tail_chunk_plan(
            pending_chunks,
            tail_min_bytes=tail_rebalance_min_bytes,
            shift_align_bytes=chunk_align_bytes,
        )
        if rebalanced_chunks != pending_chunks and len(rebalanced_chunks) >= 2:
            print(
                '[OTA] 尾块回填: '
                f'prev={len(pending_chunks[-2][1])}B tail={len(pending_chunks[-1][1])}B -> '
                f'{len(rebalanced_chunks[-2][1])}B + {len(rebalanced_chunks[-1][1])}B'
            )
        pending_chunks = rebalanced_chunks
        processed_chunks = 0
        chunk_retry_used = 0
        attempt_metric_samples: list[dict[str, object]] = []
        success_metric_samples: list[dict[str, object]] = []
        attempt_records: list[dict[str, object]] = []

        while pending_chunks:
            offset, chunk = pending_chunks.pop(0)
            chunk_input = os.path.join(
                self._temp_dir,
                f'{transfer_tag}_chunk_{offset:08d}.bin',
            )
            with open(chunk_input, 'wb') as handle:
                handle.write(chunk)

            chunk_ok = False
            typical_sec, chunk_rx_timeout, chunk_no_frame_timeout = choose_chunk_time_budget(
                success_elapsed_sec=self._success_elapsed_sec,
                chunk_len=len(chunk),
            )
            if self._rx_timeout > 0:
                chunk_rx_timeout = min(chunk_rx_timeout, float(self._rx_timeout))
            if self._no_frame_timeout > 0:
                chunk_no_frame_timeout = min(chunk_no_frame_timeout, float(self._no_frame_timeout))
            chunk_no_frame_timeout = min(chunk_no_frame_timeout, chunk_rx_timeout)
            chunk_wait_timeout = choose_chunk_wait_timeout(
                typical_sec=typical_sec,
                rx_timeout_sec=chunk_rx_timeout,
                no_frame_timeout_sec=chunk_no_frame_timeout,
            )

            print(
                '[OTA] 分块时限: '
                f'typical={typical_sec:.3f}s '
                f'rx_timeout={chunk_rx_timeout:.3f}s '
                f'no_frame_timeout={chunk_no_frame_timeout:.3f}s '
                f'wait_timeout={chunk_wait_timeout:.3f}s '
                'mode=daemon'
            )

            chunk_start_pad_samps, chunk_round_gap_ms = choose_chunk_tx_profile(
                chunk_len=len(chunk),
                start_pad_samps=self._start_pad_samps,
                round_gap_ms=self._round_gap_ms,
            )
            if (
                chunk_start_pad_samps != self._start_pad_samps
                or chunk_round_gap_ms != self._round_gap_ms
            ):
                print(
                    '[OTA] 分块 TX 加速: '
                    f'start_pad_samps={self._start_pad_samps}->{chunk_start_pad_samps} '
                    f'round_gap_ms={self._round_gap_ms}->{chunk_round_gap_ms}'
                )

            for attempt in range(retry_limit + 1):
                chunk_output = os.path.join(
                    self._temp_dir,
                    f'{transfer_tag}_chunk_{offset:08d}.rx.bin',
                )
                if os.path.exists(chunk_output):
                    os.unlink(chunk_output)

                print(
                    f'[OTA] 分块 {processed_chunks + 1}: '
                    f'offset={offset} len={len(chunk)}B '
                    f'attempt={attempt + 1}/{retry_limit + 1} '
                    'via daemon'
                )
                attempt_started = time.perf_counter()
                attempt_budget_metrics = {
                    'typical_sec': round(float(typical_sec), 6),
                    'rx_timeout_sec': round(float(chunk_rx_timeout), 6),
                    'no_frame_timeout_sec': round(float(chunk_no_frame_timeout), 6),
                    'wait_timeout_sec': round(float(chunk_wait_timeout), 6),
                }
                last_radio_metrics = dict(attempt_budget_metrics)
                received_chunk = b''
                tx_completed = False

                try:
                    tx_daemon, rx_daemon = self._ensure_sessions()
                    rx_daemon.begin_receive(no_frame_timeout=chunk_no_frame_timeout)
                    time.sleep(max(0.05, min(float(self._ota_wait), 0.5)))

                    tx_fields = tx_daemon.send(
                        file_path=chunk_input,
                        repeat=self._repeat,
                        frame_repeat=self._frame_repeat,
                        start_pad_samps=chunk_start_pad_samps,
                        round_gap_ms=chunk_round_gap_ms,
                        warmup_frames=self._warmup_frames,
                        warmup_repeats=self._warmup_repeats,
                        warmup_rounds=self._warmup_rounds,
                        tail_pad_samps=self._tail_pad_samps,
                        last_frame_extra_repeats=self._last_frame_extra_repeats,
                        first_frame_extra_repeats=self._first_frame_extra_repeats,
                        timeout=max(60.0, chunk_rx_timeout + 20.0),
                    )
                    tx_completed = True
                    last_radio_metrics['tx_wall_sec'] = round(
                        float(tx_fields.get('elapsed_sec') or 0.0), 6
                    )

                    rx_ok, _, radio_metrics, rx_message, rx_payload = rx_daemon.wait_receive(
                        timeout=chunk_wait_timeout
                    )
                    last_radio_metrics.update(radio_metrics)
                    print_radio_metrics(last_radio_metrics)

                    if rx_ok:
                        fetched_output = False
                        if rx_payload:
                            with open(chunk_output, 'wb') as handle:
                                handle.write(rx_payload)
                            fetched_output = True
                        elif os.path.exists(chunk_output):
                            fetched_output = True
                        else:
                            fetched_output = rx_daemon.fetch_output_immediate(
                                local_path=chunk_output,
                                expected_size=len(chunk),
                                attempts=3,
                            )
                        rx_daemon.cleanup_output()
                        if not fetched_output:
                            print(f'[OTA] 未取回远端输出文件: {chunk_output}')
                    else:
                        rx_daemon.cleanup_output()
                        if rx_message:
                            print(f'[OTA] 远端 RX 失败: {rx_message}')
                        remote_tail = rx_daemon.read_remote_log_tail()
                        if remote_tail:
                            for line in remote_tail.splitlines()[-20:]:
                                if line.strip():
                                    print(f'  [RX] {line}')
                except Exception as exc:
                    print(f'[OTA] daemon 会话失败: {exc}')
                    remote_tail = ''
                    session_reusable = False
                    if tx_completed and self._rx_session is not None:
                        remote_tail, session_reusable = self._salvage_rx_output_after_failure(
                            rx_daemon=self._rx_session,
                            chunk_output=chunk_output,
                            expected_size=len(chunk),
                            metrics=last_radio_metrics,
                            error=exc,
                        )
                        if not session_reusable:
                            self._close_rx_session()
                    else:
                        if self._rx_session is not None:
                            remote_tail = self._rx_session.read_remote_log_tail()
                        self._close_sessions()
                        last_radio_metrics = dict(attempt_budget_metrics)
                    last_radio_metrics['rx_session_reused_after_failure'] = session_reusable
                    if remote_tail:
                        for line in remote_tail.splitlines()[-20:]:
                            if line.strip():
                                print(f'  [RX] {line}')
                    last_radio_metrics['daemon_error'] = str(exc)

                attempt_wall_sec = round(time.perf_counter() - attempt_started, 6)
                last_radio_metrics['attempt_wall_sec'] = attempt_wall_sec

                if os.path.exists(chunk_output):
                    with open(chunk_output, 'rb') as handle:
                        received_chunk = handle.read()
                    enrich_channel_metrics(last_radio_metrics, chunk, received_chunk)
                    print_channel_metrics(last_radio_metrics)

                radio_elapsed = last_radio_metrics.get('elapsed_sec')
                if radio_elapsed is not None:
                    print(
                        '[OTA] 分块耗时: '
                        f'wall={attempt_wall_sec:.3f}s '
                        f'radio={float(radio_elapsed):.3f}s'
                    )
                else:
                    print(f'[OTA] 分块耗时: wall={attempt_wall_sec:.3f}s')

                attempt_metric_samples.append(dict(last_radio_metrics))
                attempt_records.append(
                    {
                        'chunk_index': processed_chunks + 1,
                        'offset': offset,
                        'length': len(chunk),
                        'attempt_index': attempt + 1,
                        'success': (received_chunk == chunk),
                        'received_size': len(received_chunk),
                        'metrics': compact_daemon_attempt_metrics(last_radio_metrics),
                    }
                )

                if received_chunk == chunk:
                    learned_from_salvage = bool(
                        last_radio_metrics.get('rx_output_salvaged')
                        or last_radio_metrics.get('daemon_error')
                    )
                    success_elapsed = last_radio_metrics.get('elapsed_sec')
                    if not learned_from_salvage:
                        if isinstance(success_elapsed, (int, float)) and float(success_elapsed) > 0:
                            self._success_elapsed_sec.append(float(success_elapsed))
                        elif attempt_wall_sec > 0:
                            self._success_elapsed_sec.append(float(attempt_wall_sec))
                    success_metric_samples.append(dict(last_radio_metrics))
                    received_parts.append((offset, received_chunk))
                    processed_chunks += 1
                    chunk_retry_used += attempt
                    chunk_ok = True
                    break

                if received_chunk:
                    print(
                        f'[OTA] 分块校验失败: '
                        f'sent={len(chunk)}B received={len(received_chunk)}B'
                    )
                else:
                    print('[OTA] 分块未收到有效输出')

            if not chunk_ok:
                if effective_min_chunk_bytes > 0 and len(chunk) > effective_min_chunk_bytes:
                    chunk_retry_used += retry_limit
                    split_point = choose_chunk_split_point(
                        len(chunk),
                        effective_min_chunk_bytes,
                        chunk_align_bytes,
                    )
                    if 0 < split_point < len(chunk):
                        left = chunk[:split_point]
                        right = chunk[split_point:]
                        print(
                            '[OTA] 分块失败，自动降级切分: '
                            f'offset={offset} len={len(chunk)}B -> '
                            f'{len(left)}B + {len(right)}B'
                            + (
                                f' (align={chunk_align_bytes}B)'
                                if chunk_align_bytes > 1 else ''
                            )
                        )
                        pending_chunks.insert(0, (offset + split_point, right))
                        pending_chunks.insert(0, (offset, left))
                        continue

                last_radio_metrics['chunk_total'] = processed_chunks + len(pending_chunks) + 1
                last_radio_metrics['chunk_completed'] = processed_chunks
                last_radio_metrics['chunk_retry_used'] = chunk_retry_used + retry_limit
                last_radio_metrics['attempt_records'] = attempt_records
                last_radio_metrics.update(
                    summarize_metric_samples(
                        attempt_metric_samples,
                        count_key='attempt_sample_count',
                    )
                )
                last_radio_metrics.update(
                    summarize_metric_samples(
                        success_metric_samples,
                        prefix='success_',
                        count_key='success_sample_count',
                    )
                )
                ordered_parts = b''.join(
                    part for _, part in sorted(received_parts, key=lambda item: item[0])
                )
                return False, ordered_parts, last_radio_metrics

        ordered_parts = b''.join(
            part for _, part in sorted(received_parts, key=lambda item: item[0])
        )
        last_radio_metrics['chunk_total'] = processed_chunks
        last_radio_metrics['chunk_completed'] = processed_chunks
        last_radio_metrics['chunk_retry_used'] = chunk_retry_used
        last_radio_metrics['attempt_records'] = attempt_records
        last_radio_metrics.update(
            summarize_metric_samples(
                attempt_metric_samples,
                count_key='attempt_sample_count',
            )
        )
        last_radio_metrics.update(
            summarize_metric_samples(
                success_metric_samples,
                prefix='success_',
                count_key='success_sample_count',
            )
        )
        return True, ordered_parts, last_radio_metrics

    def close(self) -> None:
        self._close_sessions()
        self._temp_dir_obj.cleanup()


def choose_chunk_split_point(
    chunk_len: int,
    min_chunk_bytes: int,
    chunk_align_bytes: int,
) -> int:
    """为失败分块选择更稳妥的切分点。"""
    if chunk_len <= 1:
        return 0

    target = max(min_chunk_bytes, chunk_len // 2)
    if chunk_align_bytes <= 1:
        if target <= 0 or target >= chunk_len:
            return 0
        if min_chunk_bytes > 0 and (chunk_len - target) < min_chunk_bytes:
            return 0
        return target

    base_units = max(1, target // chunk_align_bytes)
    candidate_units = [
        base_units,
        base_units + 1,
        base_units - 1,
        base_units + 2,
        base_units - 2,
    ]
    candidates: list[int] = []
    for units in candidate_units:
        if units <= 0:
            continue
        candidate = units * chunk_align_bytes
        if candidate <= 0 or candidate >= chunk_len:
            continue
        if candidate < min_chunk_bytes:
            continue
        right_len = chunk_len - candidate
        if min_chunk_bytes > 0 and right_len < min_chunk_bytes:
            continue
        candidates.append(candidate)

    if not candidates:
        return 0
    return min(candidates, key=lambda item: abs(item - target))


def rebalance_tail_chunk_plan(
    chunks: list[tuple[int, bytes]],
    *,
    tail_min_bytes: int,
    shift_align_bytes: int,
) -> list[tuple[int, bytes]]:
    """避免最后一块过小，必要时从倒数第二块借一段给尾块。"""
    if len(chunks) < 2 or tail_min_bytes <= 0:
        return chunks

    prev_offset, prev_chunk = chunks[-2]
    last_offset, last_chunk = chunks[-1]
    del last_offset
    if len(last_chunk) >= tail_min_bytes or len(prev_chunk) <= 1:
        return chunks

    shift_needed = tail_min_bytes - len(last_chunk)
    align = max(1, int(shift_align_bytes))
    shift = shift_needed if align <= 1 else ((shift_needed + align - 1) // align) * align
    max_shift = len(prev_chunk) - 1
    if shift > max_shift:
        return chunks

    new_prev_len = len(prev_chunk) - shift
    if align > 1 and new_prev_len < align:
        return chunks

    new_prev = prev_chunk[:-shift]
    new_last = prev_chunk[-shift:] + last_chunk
    new_last_offset = prev_offset + len(new_prev)
    rebalanced = list(chunks)
    rebalanced[-2] = (prev_offset, new_prev)
    rebalanced[-1] = (new_last_offset, new_last)
    return rebalanced


def choose_chunk_time_budget(
    *,
    success_elapsed_sec: list[float],
    chunk_len: int,
) -> tuple[float, float, float]:
    """为分块 OTA 选择更激进的 fail-fast 超时时间。

    返回:
        typical_sec: 近期正常块耗时估计
        rx_timeout_sec: 当前块允许的总等待时间
        no_frame_timeout_sec: 当前块收到首帧后的无新帧等待
    """
    if success_elapsed_sec:
        window = success_elapsed_sec[-6:]
        typical_sec = float(statistics.median(window))
    else:
        typical_sec = 4.0 if chunk_len >= 1024 else 3.0

    frame_count = max(1, (int(chunk_len) + 8191) // 8192)
    if frame_count > 1:
        typical_sec = max(typical_sec, 4.0 + (frame_count - 1) * 4.0)
        rx_timeout_sec = max(20.0, min(90.0, typical_sec * 3.0))
        no_frame_timeout_sec = max(6.0, min(20.0, 4.0 + frame_count * 2.0))
    else:
        rx_timeout_sec = max(6.0, min(20.0, typical_sec * 2.5))
        no_frame_timeout_sec = max(4.0, min(8.0, typical_sec * 1.5))
    return round(typical_sec, 3), round(rx_timeout_sec, 3), round(no_frame_timeout_sec, 3)


def choose_chunk_wait_timeout(
    *,
    typical_sec: float,
    rx_timeout_sec: float,
    no_frame_timeout_sec: float,
) -> float:
    """为 daemon wait_receive 选择 fail-fast 等待上限。"""
    wait_timeout_sec = max(
        float(rx_timeout_sec) + 8.0,
        float(no_frame_timeout_sec) + 7.0,
        float(typical_sec) * 3.0,
    )
    max_wait_timeout_sec = 120.0 if float(rx_timeout_sec) > 20.0 else 45.0
    wait_timeout_sec = max(12.0, min(max_wait_timeout_sec, wait_timeout_sec))
    return round(wait_timeout_sec, 3)


def choose_chunk_tx_profile(
    *,
    chunk_len: int,
    start_pad_samps: int,
    round_gap_ms: int,
) -> tuple[int, int]:
    """为小分块选择更低固定开销的 TX 参数。"""
    effective_start_pad_samps = max(0, int(start_pad_samps))
    effective_round_gap_ms = max(0, int(round_gap_ms))

    if chunk_len <= 1024:
        effective_start_pad_samps = min(effective_start_pad_samps, 100000)
        effective_round_gap_ms = min(effective_round_gap_ms, 64)

    return effective_start_pad_samps, effective_round_gap_ms


def load_plaintext_input(
    input_path: str,
    *,
    raw_file_input: bool,
) -> tuple[bytes, bool]:
    """读取待加密明文；可按 .npz latent 或原始文件字节加载。"""
    input_is_npz = input_path.endswith('.npz')

    if raw_file_input:
        with open(input_path, 'rb') as handle:
            plaintext = handle.read()
        return plaintext, input_is_npz

    if input_is_npz:
        import numpy as np

        with np.load(input_path) as data:
            key = 'latent'
            if key not in data:
                key = list(data.keys())[0]
            tensor = data[key]
        return tensor.tobytes(), True

    with open(input_path, 'rb') as handle:
        plaintext = handle.read()
    return plaintext, False


def write_plaintext_output(
    output_path: str,
    plaintext: bytes,
    *,
    input_is_npz: bool,
    raw_file_input: bool,
) -> None:
    """写出解密后的明文；原样文件模式直接落盘字节。"""
    if raw_file_input:
        with open(output_path, 'wb') as handle:
            handle.write(plaintext)
        print(f'       输出 raw: {output_path}, {len(plaintext)} bytes')
        return

    if input_is_npz and output_path.endswith('.npz'):
        import numpy as np

        tensor = np.frombuffer(plaintext, dtype=np.float32)
        np.savez(output_path, latent=tensor)
        print(f'       输出 npz: {output_path}, shape={tensor.shape}')
        return

    with open(output_path, 'wb') as handle:
        handle.write(plaintext)
    print(f'       输出 bin: {output_path}, {len(plaintext)} bytes')


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


def remote_needs_sudo(result: subprocess.CompletedProcess[str]) -> bool:
    """判断远端命令是否因为 USB 权限不足失败。"""
    text = ((result.stdout or '') + '\n' + (result.stderr or '')).lower()
    return 'insufficient permissions' in text or 'libusb_error_access' in text


def wrap_remote_shell_command(command: str, sudo_password: str = '') -> str:
    """按需包一层 sudo bash -lc，保证复杂 shell 命令可安全远端执行。"""
    if not sudo_password:
        return command
    return (
        f'printf %s\\\\n {shlex.quote(sudo_password)} | '
        f"sudo -S -p '' bash -lc {shlex.quote(command)}"
    )


def prime_local_usrp(device_args: str, role: str) -> bool:
    """本地执行一次 UHD probe，触发固件/FPGA 预热。"""
    probe_args = normalize_probe_args(device_args)
    cache_key = (role, probe_args)
    if _LOCAL_USRP_PRIME_CACHE.get(cache_key):
        print(f'[OTA] 本地 {role} 预热已缓存，跳过重复 probe')
        return True

    cmd = ['uhd_usrp_probe', '--args', probe_args]
    print(f'[OTA] 本地 {role} 预热: {" ".join(cmd)}')
    result = run_text_command(cmd, timeout=45.0)
    if result.returncode == 0:
        _LOCAL_USRP_PRIME_CACHE[cache_key] = True
        return True

    print(f'[OTA] 本地 {role} 预热失败 (rc={result.returncode})')
    tail = summarize_probe_output(result)
    if tail:
        print(tail)
    return False


def prime_remote_usrp(
    host: str,
    user: str,
    password: str,
    port: str,
    device_args: str,
    role: str,
) -> tuple[bool, bool]:
    """远端执行一次 UHD probe，避免 RX 启动时才加载固件/FPGA。"""
    probe_args = normalize_probe_args(device_args)
    cache_key = (host, port, role, probe_args)
    cached = _REMOTE_USRP_PRIME_CACHE.get(cache_key)
    if cached and cached[0]:
        cached_use_sudo = bool(cached[1])
        print(
            f'[OTA] 远端 {role} 预热已缓存，跳过重复 probe'
            + (' (sudo)' if cached_use_sudo else '')
        )
        return True, cached_use_sudo

    ssh_prefix = build_ssh_prefix(host, user, password, port)
    remote_cmd = f'uhd_usrp_probe --args {probe_args!r}'
    print(f'[OTA] 远端 {role} 预热: ssh {user}@{host} "{remote_cmd}"')
    result = run_text_command(ssh_prefix + [remote_cmd], timeout=60.0)
    if result.returncode == 0:
        _REMOTE_USRP_PRIME_CACHE[cache_key] = (True, False)
        return True, False

    if remote_needs_sudo(result) and password:
        print(f'[OTA] 远端 {role} 预热命中 USB 权限限制，切换 sudo 重试...')
        sudo_cmd = wrap_remote_shell_command(remote_cmd, password)
        sudo_result = run_text_command(ssh_prefix + [sudo_cmd], timeout=60.0)
        if sudo_result.returncode == 0:
            _REMOTE_USRP_PRIME_CACHE[cache_key] = (True, True)
            return True, True

        print(f'[OTA] 远端 {role} sudo 预热失败 (rc={sudo_result.returncode})')
        tail = summarize_probe_output(sudo_result)
        if tail:
            print(tail)
        return False, True

    print(f'[OTA] 远端 {role} 预热失败 (rc={result.returncode})')
    tail = summarize_probe_output(result)
    if tail:
        print(tail)
    return False, False


def remote_status_command(
    remote_output: str,
    remote_log: str,
    remote_tag: str = '',
    remote_match_mode: str = 'contains',
) -> str:
    """查询远端 RX 输出 / 日志状态。"""
    return (
        'python3 - <<\'PY\'\n'
        'import hashlib, os, subprocess\n'
        f'out_path={remote_output!r}\n'
        f'log_path={remote_log!r}\n'
        f'remote_tag={remote_tag!r}\n'
        f'remote_match_mode={remote_match_mode!r}\n'
        'def match_remote_proc(args: str) -> bool:\n'
        '    args = args.strip()\n'
        '    if not remote_tag or not args:\n'
        '        return False\n'
        '    if remote_match_mode == "argv0_prefix":\n'
        '        argv0 = args.split(None, 1)[0]\n'
        '        return argv0 == remote_tag or argv0.startswith(remote_tag)\n'
        '    return remote_tag in args\n'
        'proc_pids=[]\n'
        'if remote_tag:\n'
        '    try:\n'
        '        ps = subprocess.run(["ps", "-eo", "pid=,args="], text=True, capture_output=True, check=False)\n'
        '        for line in ps.stdout.splitlines():\n'
        '            line = line.strip()\n'
        '            if not line:\n'
        '                continue\n'
        '            parts = line.split(None, 1)\n'
        '            if len(parts) != 2:\n'
        '                continue\n'
        '            pid_text, args = parts\n'
        '            if match_remote_proc(args):\n'
        '                proc_pids.append(pid_text)\n'
        '    except Exception:\n'
        '        proc_pids=[]\n'
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
        '    if "[RX] 等待信号" in scan_text or "[RX] 离线回放" in scan_text:\n'
        '        ready=1\n'
        '    saw_preamble=int("PREAMBLE CHAN" in scan_text)\n'
        '    saw_header=int("HEADER OK" in scan_text or "HEADER CRC FAIL" in scan_text)\n'
        '    saw_payload=int("decode_search:" in scan_text or "NEED MORE:" in scan_text or "→ 异步解码" in scan_text)\n'
        'print(\n'
        '    f"exists={int(exists)} size={size} sha={sha} "\n'
        '    f"log_exists={int(log_exists)} log_size={log_size} ready={ready} "\n'
        '    f"saw_preamble={saw_preamble} saw_header={saw_header} saw_payload={saw_payload} "\n'
        '    f"proc_count={len(proc_pids)} proc_pids={",".join(proc_pids)}"\n'
        ')\n'
        'PY'
    )


def remote_cleanup_command(remote_output: str, remote_log: str) -> str:
    """清理远端临时文件。"""
    return f'rm -f {remote_output!r} {remote_log!r}'


def remote_kill_command(
    remote_tag: str,
    match_mode: str = 'contains',
) -> str:
    """按唯一 tag 清理远端残留的 RX 进程。"""
    return (
        'python3 - <<\'PY\'\n'
        'import os, signal, subprocess, time\n'
        f'remote_tag={remote_tag!r}\n'
        f'match_mode={match_mode!r}\n'
        'def match_remote_proc(args: str) -> bool:\n'
        '    args = args.strip()\n'
        '    if not remote_tag or not args:\n'
        '        return False\n'
        '    if match_mode == "argv0_prefix":\n'
        '        argv0 = args.split(None, 1)[0]\n'
        '        return argv0 == remote_tag or argv0.startswith(remote_tag)\n'
        '    return remote_tag in args\n'
        'def find_pids():\n'
        '    ps = subprocess.run(["ps", "-eo", "pid=,args="], text=True, capture_output=True, check=False)\n'
        '    pids=[]\n'
        '    for line in ps.stdout.splitlines():\n'
        '        line = line.strip()\n'
        '        if not line:\n'
        '            continue\n'
        '        parts = line.split(None, 1)\n'
        '        if len(parts) != 2:\n'
        '            continue\n'
        '        pid_text, args = parts\n'
        '        try:\n'
        '            pid = int(pid_text)\n'
        '        except ValueError:\n'
        '            continue\n'
        '        if pid in (os.getpid(), os.getppid()):\n'
        '            continue\n'
        '        if match_remote_proc(args):\n'
        '            pids.append(pid)\n'
        '    return pids\n'
        'for sig, wait_sec in ((signal.SIGTERM, 2.5), (signal.SIGKILL, 1.5)):\n'
        '    pids = find_pids()\n'
        '    if not pids:\n'
        '        break\n'
        '    for pid in pids:\n'
        '        try:\n'
        '            os.kill(pid, sig)\n'
        '        except (ProcessLookupError, PermissionError):\n'
        '            pass\n'
        '    deadline = time.time() + wait_sec\n'
        '    while time.time() < deadline:\n'
        '        if not find_pids():\n'
        '            break\n'
        '        time.sleep(0.2)\n'
        'PY'
    )


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
    *,
    ssh_prefix: list[str],
    board_pass: str,
    remote_output: str,
    remote_log: str,
    remote_use_sudo: bool,
    timeout: float,
    label: str,
    remote_tag: str = '',
    remote_match_mode: str = 'contains',
) -> dict[str, str]:
    """查询远端输出 / 日志状态。"""
    status_result = run_text_command_best_effort(
        ssh_prefix + [wrap_remote_shell_command(
            remote_status_command(
                remote_output,
                remote_log,
                remote_tag=remote_tag,
                remote_match_mode=remote_match_mode,
            ),
            board_pass if remote_use_sudo else '',
        )],
        timeout=timeout,
        label=label,
    )
    if not status_result:
        return {}
    return parse_remote_status(status_result.stdout or '')


def wait_remote_output_ready(
    *,
    proc: subprocess.Popen[str],
    ssh_prefix: list[str],
    board_pass: str,
    remote_output: str,
    remote_log: str,
    remote_use_sudo: bool,
    expected_size: int,
    timeout: float,
) -> bool:
    """轮询远端输出文件，若大小已达到预期则认为可提前回收。"""
    if expected_size <= 0:
        return False

    deadline = time.monotonic() + max(0.0, float(timeout))
    while proc.poll() is None and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        status = query_remote_status(
            ssh_prefix=ssh_prefix,
            board_pass=board_pass,
            remote_output=remote_output,
            remote_log=remote_log,
            remote_use_sudo=remote_use_sudo,
            timeout=min(3.0, max(1.0, remaining)),
            label='远端 RX 就绪轮询',
        )
        if status.get('exists', '0') == '1':
            size = int(status.get('size', '0') or '0')
            if size >= expected_size:
                return True
        time.sleep(1.0)
    return False


def wait_remote_rx_progress(
    *,
    proc: subprocess.Popen[str],
    ssh_prefix: list[str],
    board_pass: str,
    remote_output: str,
    remote_log: str,
    remote_use_sudo: bool,
    timeout: float,
) -> dict[str, str]:
    """等待远端 RX 出现前导/头部/解码迹象，用于尽早区分“没锁到帧”。"""
    deadline = time.monotonic() + max(0.0, float(timeout))
    last_status: dict[str, str] = {}
    while proc.poll() is None and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        status = query_remote_status(
            ssh_prefix=ssh_prefix,
            board_pass=board_pass,
            remote_output=remote_output,
            remote_log=remote_log,
            remote_use_sudo=remote_use_sudo,
            timeout=min(3.0, max(1.0, remaining)),
            label='远端 RX 进展轮询',
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


def wait_remote_rx_ready(
    *,
    proc: subprocess.Popen[str],
    ssh_prefix: list[str],
    board_pass: str,
    remote_output: str,
    remote_log: str,
    remote_use_sudo: bool,
    timeout: float,
) -> bool:
    """轮询远端日志，等待 RX 真正进入“等待信号”状态。"""
    deadline = time.monotonic() + max(0.0, float(timeout))
    while proc.poll() is None and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        status = query_remote_status(
            ssh_prefix=ssh_prefix,
            board_pass=board_pass,
            remote_output=remote_output,
            remote_log=remote_log,
            remote_use_sudo=remote_use_sudo,
            timeout=min(3.0, max(1.0, remaining)),
            label='远端 RX ready 轮询',
        )
        if status.get('ready', '0') == '1':
            return True
        time.sleep(0.5)
    return False


def fetch_remote_artifacts(
    *,
    ssh_prefix: list[str],
    board_host: str,
    board_user: str,
    board_pass: str,
    board_port: str,
    remote_output: str,
    remote_log: str,
    output_bin: str,
    remote_use_sudo: bool,
) -> tuple[bool, int, bool, str, dict[str, object]]:
    """抓取远端输出文件与日志，并提取无线统计。"""
    status = query_remote_status(
        ssh_prefix=ssh_prefix,
        board_pass=board_pass,
        remote_output=remote_output,
        remote_log=remote_log,
        remote_use_sudo=remote_use_sudo,
        timeout=20.0,
        label='远端 RX 状态查询',
    )
    remote_exists = status.get('exists', '0') == '1'
    remote_size = int(status.get('size', '0') or '0')

    fetched_log = fetch_remote_file(
        board_host, board_user, board_pass, board_port, remote_log, output_bin + '.rx.log'
    )
    fetched_output = False
    if remote_exists and remote_size > 0:
        fetched_output = fetch_remote_file(
            board_host, board_user, board_pass, board_port, remote_output, output_bin
        )

    log_text = ''
    if fetched_log and os.path.exists(output_bin + '.rx.log'):
        with open(output_bin + '.rx.log', 'r', encoding='utf-8', errors='ignore') as f:
            log_text = f.read()
        for line in log_text.strip().split('\n')[-20:]:
            if line.strip():
                print(f'  [RX] {line}')

    radio_metrics = extract_radio_metrics(log_text)
    if log_text:
        print_radio_metrics(radio_metrics)
    return remote_exists, remote_size, fetched_output, log_text, radio_metrics


def fetch_remote_file(
    host: str,
    user: str,
    password: str,
    port: str,
    remote_path: str,
    local_path: str,
    timeout: float = 10.0,
) -> bool:
    """抓取远端文件到本地。"""
    cmd = build_scp_prefix(host, user, password, port) + [
        f'{user}@{host}:{remote_path}',
        local_path,
    ]
    result = run_text_command(cmd, timeout=timeout)
    return result.returncode == 0


def fetch_remote_file_inline_base64(
    host: str,
    user: str,
    password: str,
    port: str,
    remote_path: str,
    local_path: str,
    timeout: float = 8.0,
) -> bool:
    """通过 ssh + base64 抓回小文件，避免 scp 在病态场景下额外卡顿。"""
    cmd = build_ssh_prefix(host, user, password, port) + [
        wrap_remote_shell_command(remote_read_file_base64_command(remote_path)),
    ]
    result = run_text_command(cmd, timeout=timeout)
    if result.returncode != 0:
        return False

    payload_b64 = (result.stdout or '').strip()
    if not payload_b64:
        return False

    try:
        payload = base64.b64decode(payload_b64, validate=True)
    except Exception:
        return False

    with open(local_path, 'wb') as handle:
        handle.write(payload)
    return True


def run_sim_tx(encrypted_bin: str, output_bin: str, snr: float = 24.0,
                repeat: int = 1) -> bool:
    """调用 usrp_tensor_loopback --sim 进行软件回环传输"""
    loopback = os.path.join(
        os.path.dirname(__file__), "..", "usrp_tensor", "build",
        "usrp_tensor_loopback"
    )
    if not os.path.exists(loopback):
        print(f"[错误] 找不到 {loopback}，请先编译")
        return False

    cmd = [loopback, "--sim", "--file", encrypted_bin,
           "--snr", str(snr), "--repeat", str(repeat)]
    print(f"[SIM] {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[SIM] 失败 (rc={result.returncode})")
        if result.stderr:
            print(result.stderr[-2000:])
        return False

    # loopback --sim 模式自动对比并输出到 stdout
    print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
    return True


def run_loopback(encrypted_bin: str, tx_args: str = "",
                 tx_gain: float = 10.0, rx_gain: float = 30.0,
                 repeat: int = 1) -> bool:
    """调用 usrp_tensor_loopback 进行硬件回环传输"""
    loopback = os.path.join(
        os.path.dirname(__file__), "..", "usrp_tensor", "build",
        "usrp_tensor_loopback"
    )
    if not os.path.exists(loopback):
        print(f"[错误] 找不到 {loopback}，请先编译")
        return False

    cmd = [loopback, "--file", encrypted_bin,
           "--tx-gain", str(tx_gain), "--rx-gain", str(rx_gain),
           "--repeat", str(repeat)]
    if tx_args:
        cmd += ["--args", tx_args]

    print(f"[LOOPBACK] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"[LOOPBACK] 失败 (rc={result.returncode})")
        if result.stderr:
            print(result.stderr[-2000:])
        return False

    print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
    return True


def run_ota_remote(
    encrypted_bin: str,
    output_bin: str,
    *,
    board_host: str,
    board_user: str,
    board_pass: str,
    board_port: str,
    remote_build_dir: str,
    tx_args: str = "",
    rx_args: str = "",
    tx_gain: float = 60.0,
    rx_gain: float = 60.0,
    rate: float = 1e6,
    freq: float = 915e6,
    repeat: int = 1,
    rx_timeout: float = 120.0,
    ota_wait: float = 0.4,
    start_pad_samps: int = 100000,
    round_gap_ms: int = 500,
    frame_repeat: int = 1,
    rx_spb: int = 10000,
    rx_setup: float = 0.1,
    no_frame_timeout: float = 8.0,
    rx_ant: str = '',
    decode_workers: int = 2,
    payload_search_order: str = 'auto',
    warmup_frames: int = 2,
    warmup_repeats: int = 2,
    warmup_rounds: int = 1,
    tail_pad_samps: int = 2000,
    last_frame_extra_repeats: int = 0,
    first_frame_extra_repeats: int = 0,
    frame_order: str = 'normal',
    remote_kill_after: float | None = None,
) -> dict[str, object]:
    """本地 TX / 远端板端 RX 的 OTA 传输。"""
    build_dir = os.path.join(os.path.dirname(__file__), '..', 'usrp_tensor', 'build')
    tx_bin = os.path.join(build_dir, 'usrp_tensor_tx')
    if not os.path.exists(tx_bin):
        print(f'[错误] 找不到 TX: {tx_bin}，请先编译')
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    remote_ready_timeout = max(
        float(ota_wait),
        min(12.0, max(4.0, float(rx_setup) + 8.0)),
    )
    if remote_kill_after is None:
        remote_kill_after = max(float(rx_timeout) + 30.0, 60.0)
    else:
        remote_kill_after = max(
            float(remote_kill_after),
            remote_ready_timeout + max(float(rx_timeout), float(no_frame_timeout)) + 3.0,
        )
    ssh_wait_timeout = max(float(rx_timeout) + 2.0, remote_kill_after + 5.0)
    remote_tag = f'e2e_usrp_{int(time.time())}_{os.getpid()}'
    remote_output = f'/tmp/{remote_tag}.bin'
    remote_log = f'/tmp/{remote_tag}.log'
    rx_bin = f'{remote_build_dir.rstrip("/")}/usrp_tensor_rx'
    ssh_prefix = build_ssh_prefix(board_host, board_user, board_pass, board_port)
    expected_size = os.path.getsize(encrypted_bin) if os.path.exists(encrypted_bin) else 0

    remote_ready, remote_use_sudo = prime_remote_usrp(
        board_host, board_user, board_pass, board_port, rx_args, 'RX',
    )
    if not remote_ready:
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}
    if not prime_local_usrp(tx_args, 'TX'):
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    rx_cmd = (
        f'cd {remote_build_dir!r} && '
        f'rm -f {remote_output!r} {remote_log!r} && '
        f'timeout {remote_kill_after:.1f}s '
        f'{rx_bin!r} '
        f'--output {remote_output!r} '
        f'--args {rx_args!r} '
        f'--rate {rate} '
        f'--freq {freq} '
        f'--gain {rx_gain} '
        f'{"--ant " + repr(rx_ant) + " " if rx_ant else ""}'
        f'--spb {rx_spb} '
        f'--setup {rx_setup} '
        f'--timeout {no_frame_timeout} '
        f'--decode-workers {decode_workers} '
        f'--payload-search-order {payload_search_order!r} '
        f'> {remote_log!r} 2>&1'
    )
    rx_shell_cmd = wrap_remote_shell_command(
        rx_cmd,
        board_pass if remote_use_sudo else '',
    )
    print(f'[OTA] 远端 RX 启动: ssh {board_user}@{board_host} "{rx_cmd}"')
    if remote_use_sudo:
        print('[OTA] 远端 RX 以 sudo 运行')
    ready_wait_started = time.perf_counter()
    rx_proc = subprocess.Popen(
        ssh_prefix + [rx_shell_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    rx_ready = wait_remote_rx_ready(
        proc=rx_proc,
        ssh_prefix=ssh_prefix,
        board_pass=board_pass,
        remote_output=remote_output,
        remote_log=remote_log,
        remote_use_sudo=remote_use_sudo,
        timeout=remote_ready_timeout,
    )
    ready_wait_sec = round(time.perf_counter() - ready_wait_started, 6)
    if rx_ready:
        print(
            '[OTA] 远端 RX 已就绪，准备发射 '
            f'(ready_wait={ready_wait_sec:.3f}s, budget={remote_ready_timeout:.1f}s)'
        )
    else:
        print(
            f'[OTA] 远端 RX 未在 {remote_ready_timeout:.1f}s 内确认 ready，'
            '按既定窗口继续发射'
        )

    tx_cmd = [
        tx_bin, '--file', encrypted_bin,
        '--args', tx_args,
        '--rate', str(rate), '--freq', str(freq),
        '--gain', str(tx_gain),
        '--repeat', str(repeat),
        '--frame-repeat', str(frame_repeat),
        '--start-pad-samps', str(start_pad_samps),
        '--round-gap-ms', str(round_gap_ms),
        '--warmup-frames', str(warmup_frames),
        '--warmup-repeats', str(warmup_repeats),
        '--warmup-rounds', str(warmup_rounds),
        '--tail-pad-samps', str(tail_pad_samps),
        '--last-frame-extra-repeats', str(last_frame_extra_repeats),
        '--first-frame-extra-repeats', str(first_frame_extra_repeats),
        '--frame-order', str(frame_order),
    ]
    print(f'[OTA] 本地 TX 启动: {" ".join(tx_cmd)}')
    tx_started = time.perf_counter()
    tx_result = subprocess.run(tx_cmd, capture_output=True, text=True, timeout=300)
    tx_wall_sec = round(time.perf_counter() - tx_started, 6)
    if tx_result.returncode != 0:
        print(f'[OTA] TX 失败 (rc={tx_result.returncode})')
        if tx_result.stderr:
            print(tx_result.stderr[-2000:])
    else:
        print(f'[OTA] TX 发送完成 (wall={tx_wall_sec:.3f}s)')
    if tx_result.stdout:
        for line in tx_result.stdout.strip().split('\n')[-10:]:
            print(f'  [TX] {line}')

    print(
        '[OTA] 等待远端 RX 完成 '
        f'(SSH 超时 {ssh_wait_timeout}s, 远端 shell timeout {remote_kill_after}s)...'
    )
    wait_started = time.monotonic()
    rx_stdout = ''
    ssh_timed_out = False
    no_signal_abort = False
    progress_status: dict[str, str] = {}
    output_ready = wait_remote_output_ready(
        proc=rx_proc,
        ssh_prefix=ssh_prefix,
        board_pass=board_pass,
        remote_output=remote_output,
        remote_log=remote_log,
        remote_use_sudo=remote_use_sudo,
        expected_size=expected_size,
        timeout=min(10.0, ssh_wait_timeout),
    )
    if output_ready:
        print(f'[OTA] 远端输出已就绪 ({expected_size}B)，提前回收 SSH/RX')
        run_text_command_best_effort(
            ssh_prefix + [wrap_remote_shell_command(
                remote_kill_command(remote_tag),
                board_pass if remote_use_sudo else '',
            )],
            timeout=10.0,
            label='远端 RX 提前回收',
        )
        kill_process_group_best_effort(rx_proc, '远端 RX SSH')
        try:
            rx_stdout, _ = rx_proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired as exc:
            rx_stdout = exc.stdout or rx_stdout or ''
    else:
        if tx_result.returncode == 0 and rx_proc.poll() is None:
            progress_status = wait_remote_rx_progress(
                proc=rx_proc,
                ssh_prefix=ssh_prefix,
                board_pass=board_pass,
                remote_output=remote_output,
                remote_log=remote_log,
                remote_use_sudo=remote_use_sudo,
                timeout=min(4.0, max(2.5, float(rx_setup) + 2.5)),
            )
            if (
                progress_status
                and
                progress_status.get('exists', '0') != '1'
                and progress_status.get('saw_preamble', '0') != '1'
                and progress_status.get('saw_header', '0') != '1'
                and progress_status.get('saw_payload', '0') != '1'
            ):
                no_signal_abort = True
                print('[OTA] 发射后短窗口内仍无前导/帧迹象，提前回收远端 RX')
                run_text_command_best_effort(
                    ssh_prefix + [wrap_remote_shell_command(
                        remote_kill_command(remote_tag),
                        board_pass if remote_use_sudo else '',
                    )],
                    timeout=10.0,
                    label='远端 RX 无帧早停',
                )
                kill_process_group_best_effort(rx_proc, '远端 RX SSH')
                try:
                    rx_stdout, _ = rx_proc.communicate(timeout=5.0)
                except subprocess.TimeoutExpired as exc:
                    rx_stdout = exc.stdout or rx_stdout or ''
        if not no_signal_abort:
            remaining_wait = max(1.0, ssh_wait_timeout - (time.monotonic() - wait_started))
            rx_stdout, ssh_timed_out = communicate_with_deadline(
                rx_proc,
                timeout=remaining_wait,
            )
        if ssh_timed_out:
            print(
                f'[OTA] 远端 RX SSH 超时 ({ssh_wait_timeout}s)，'
                '尝试回收远端日志/输出后再判定'
            )
            kill_process_group_best_effort(rx_proc, '远端 RX SSH')
            try:
                rx_stdout, _ = rx_proc.communicate(timeout=5.0)
            except subprocess.TimeoutExpired as exc:
                rx_stdout = exc.stdout or rx_stdout or ''

    if rx_stdout:
        for line in rx_stdout.strip().split('\n')[-10:]:
            if line.strip():
                print(f'  [RX-SSH] {line}')

    remote_exists, remote_size, fetched_output, log_text, radio_metrics = fetch_remote_artifacts(
        ssh_prefix=ssh_prefix,
        board_host=board_host,
        board_user=board_user,
        board_pass=board_pass,
        board_port=board_port,
        remote_output=remote_output,
        remote_log=remote_log,
        output_bin=output_bin,
        remote_use_sudo=remote_use_sudo,
    )
    if not log_text:
        radio_metrics = extract_radio_metrics(rx_stdout or '')
        print_radio_metrics(radio_metrics)
    radio_metrics['remote_rx_ready'] = rx_ready
    radio_metrics['remote_ready_wait_sec'] = ready_wait_sec
    radio_metrics['remote_ready_timeout_sec'] = round(remote_ready_timeout, 6)
    radio_metrics['remote_saw_preamble'] = (progress_status.get('saw_preamble', '0') == '1')
    radio_metrics['remote_saw_header'] = (progress_status.get('saw_header', '0') == '1')
    radio_metrics['remote_saw_payload'] = (progress_status.get('saw_payload', '0') == '1')
    radio_metrics['remote_no_signal_abort'] = no_signal_abort
    radio_metrics['tx_wall_sec'] = tx_wall_sec
    radio_metrics['remote_kill_after_sec'] = round(remote_kill_after, 6)
    radio_metrics['ssh_wait_timeout_sec'] = round(ssh_wait_timeout, 6)

    if ssh_timed_out:
        run_text_command_best_effort(
            ssh_prefix + [wrap_remote_shell_command(
                remote_kill_command(remote_tag),
                board_pass if remote_use_sudo else '',
            )],
            timeout=10.0,
            label='远端 RX kill',
        )

    run_text_command_best_effort(
        ssh_prefix + [wrap_remote_shell_command(
            remote_cleanup_command(remote_output, remote_log),
            board_pass if remote_use_sudo else '',
        )],
        timeout=10.0,
        label='远端 RX 清理',
    )

    if tx_result.returncode != 0:
        print(f'[OTA] 远端 RX 退出码: {rx_proc.returncode}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    if rx_proc.returncode != 0 and fetched_output:
        print(
            f'[OTA] 远端 RX/SSH 返回非零 (rc={rx_proc.returncode})，'
            '但已取回输出文件，继续交由上层做字节校验'
        )
    elif rx_proc.returncode != 0:
        print(f'[OTA] 远端 RX 退出码: {rx_proc.returncode}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    if not fetched_output or not os.path.exists(output_bin):
        print(f'[OTA] 未取回远端输出文件: {output_bin}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}

    received_size = os.path.getsize(output_bin)
    if received_size == 0:
        print('[OTA] 远端输出文件为空')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}

    print(f'[OTA] 远端 RX 输出: {output_bin} ({received_size} bytes)')
    return {'ok': True, 'received_size': received_size, 'radio_metrics': radio_metrics}


def build_arq_tx_command(
    tx_bin: str,
    encrypted_bin: str,
    *,
    tx_args: str,
    tx_gain: float,
    rate: float,
    freq: float,
    rev_freq: float,
    rx_spb: int,
    nack_rx_gain: float,
    rx_ant: str,
) -> list[str]:
    """构造 ARQ TX 命令。"""
    cmd = [
        tx_bin,
        '--file', encrypted_bin,
        '--args', tx_args,
        '--rate', str(rate),
        '--fwd-freq', str(freq),
        '--rev-freq', str(rev_freq),
        '--tx-gain', str(tx_gain),
        '--rx-gain', str(nack_rx_gain),
        '--spb', str(rx_spb),
    ]
    if rx_ant:
        cmd.extend(['--rx-ant', rx_ant])
    return cmd


def build_arq_rx_command(
    rx_bin: str,
    output_bin: str,
    *,
    rx_args: str,
    rx_gain: float,
    rate: float,
    freq: float,
    rev_freq: float,
    rx_spb: int,
    no_frame_timeout: float,
    nack_tx_gain: float,
    rx_ant: str,
) -> list[str]:
    """构造 ARQ RX 命令。"""
    cmd = [
        rx_bin,
        '--output', output_bin,
        '--args', rx_args,
        '--rate', str(rate),
        '--fwd-freq', str(freq),
        '--rev-freq', str(rev_freq),
        '--rx-gain', str(rx_gain),
        '--tx-gain', str(nack_tx_gain),
        '--spb', str(rx_spb),
        '--timeout', str(no_frame_timeout),
    ]
    if rx_ant:
        cmd.extend(['--rx-ant', rx_ant])
    return cmd


def run_ota_remote_arq(
    encrypted_bin: str,
    output_bin: str,
    *,
    board_host: str,
    board_user: str,
    board_pass: str,
    board_port: str,
    remote_build_dir: str,
    tx_args: str = '',
    rx_args: str = '',
    tx_gain: float = 60.0,
    rx_gain: float = 60.0,
    rate: float = 1e6,
    freq: float = 915e6,
    rx_timeout: float = 120.0,
    ota_wait: float = 0.4,
    rx_spb: int = 10000,
    rx_setup: float = 0.1,
    no_frame_timeout: float = 8.0,
    rx_ant: str = '',
    arq_rev_freq: float = 915.5e6,
    arq_nack_tx_gain: float = 10.0,
    arq_nack_rx_gain: float = 30.0,
    remote_kill_after: float | None = None,
) -> dict[str, object]:
    """本地 ARQ TX / 远端板端 ARQ RX 的整包 OTA 传输。"""
    build_dir = os.path.join(os.path.dirname(__file__), '..', 'usrp_tensor', 'build')
    tx_bin = os.path.join(build_dir, 'usrp_tensor_arq_tx')
    if not os.path.exists(tx_bin):
        print(f'[错误] 找不到 ARQ TX: {tx_bin}，请先编译')
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    if remote_kill_after is None or abs(float(remote_kill_after) - 180.0) < 1e-6:
        remote_kill_after = max(float(rx_timeout) + 5.0, 30.0)
    else:
        remote_kill_after = max(float(remote_kill_after), float(rx_timeout) + 3.0)
    ssh_wait_timeout = max(float(rx_timeout) + 5.0, remote_kill_after + 5.0)
    remote_tag = f'e2e_usrp_arq_{int(time.time())}_{os.getpid()}'
    remote_output = f'/tmp/{remote_tag}.bin'
    remote_log = f'/tmp/{remote_tag}.log'
    rx_bin = f'{remote_build_dir.rstrip("/")}/usrp_tensor_arq_rx'
    ssh_prefix = build_ssh_prefix(board_host, board_user, board_pass, board_port)

    remote_ready, remote_use_sudo = prime_remote_usrp(
        board_host, board_user, board_pass, board_port, rx_args, 'RX',
    )
    if not remote_ready:
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}
    if not prime_local_usrp(tx_args, 'TX'):
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    remote_rx_cmd = build_arq_rx_command(
        rx_bin,
        remote_output,
        rx_args=rx_args,
        rx_gain=rx_gain,
        rate=rate,
        freq=freq,
        rev_freq=arq_rev_freq,
        rx_spb=rx_spb,
        no_frame_timeout=no_frame_timeout,
        nack_tx_gain=arq_nack_tx_gain,
        rx_ant=rx_ant,
    )
    rx_cmd = (
        f'cd {remote_build_dir!r} && '
        f'rm -f {remote_output!r} {remote_log!r} && '
        f'timeout {remote_kill_after:.1f}s '
        f'{shlex.join(remote_rx_cmd)} '
        f'> {remote_log!r} 2>&1'
    )
    rx_shell_cmd = wrap_remote_shell_command(
        rx_cmd,
        board_pass if remote_use_sudo else '',
    )
    print(f'[OTA][ARQ] 远端 RX 启动: ssh {board_user}@{board_host} "{rx_cmd}"')
    if remote_use_sudo:
        print('[OTA][ARQ] 远端 RX 以 sudo 运行')
    rx_proc = subprocess.Popen(
        ssh_prefix + [rx_shell_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    ready_wait_sec = round(
        max(float(ota_wait), min(5.0, max(2.0, float(rx_setup) + 1.5))),
        6,
    )
    print(f'[OTA][ARQ] 等待远端 RX 稳定: {ready_wait_sec:.3f}s')
    time.sleep(ready_wait_sec)

    tx_cmd = build_arq_tx_command(
        tx_bin,
        encrypted_bin,
        tx_args=tx_args,
        tx_gain=tx_gain,
        rate=rate,
        freq=freq,
        rev_freq=arq_rev_freq,
        rx_spb=rx_spb,
        nack_rx_gain=arq_nack_rx_gain,
        rx_ant=rx_ant,
    )
    print(f'[OTA][ARQ] 本地 TX 启动: {" ".join(tx_cmd)}')
    tx_started = time.perf_counter()
    tx_result = subprocess.run(
        tx_cmd,
        capture_output=True,
        text=True,
        timeout=max(300.0, float(rx_timeout) + 60.0),
    )
    tx_wall_sec = round(time.perf_counter() - tx_started, 6)
    tx_log_text = '\n'.join(part for part in (tx_result.stdout, tx_result.stderr) if part).strip()
    if tx_result.returncode != 0:
        print(f'[OTA][ARQ] TX 失败 (rc={tx_result.returncode})')
        if tx_log_text:
            print(tx_log_text[-2000:])
    else:
        print(f'[OTA][ARQ] TX 发送完成 (wall={tx_wall_sec:.3f}s)')
    if tx_log_text:
        for line in tx_log_text.split('\n')[-10:]:
            if line.strip():
                print(f'  [TX] {line}')

    print(
        '[OTA][ARQ] 等待远端 RX 完成 '
        f'(SSH 超时 {ssh_wait_timeout}s, 远端 shell timeout {remote_kill_after}s)...'
    )
    rx_stdout, ssh_timed_out = communicate_with_deadline(
        rx_proc,
        timeout=ssh_wait_timeout,
    )
    if ssh_timed_out:
        print(f'[OTA][ARQ] 远端 RX SSH 超时 ({ssh_wait_timeout}s)，尝试回收日志/输出')
        kill_process_group_best_effort(rx_proc, '远端 ARQ RX SSH')
        try:
            rx_stdout, _ = rx_proc.communicate(timeout=5.0)
        except subprocess.TimeoutExpired as exc:
            rx_stdout = exc.stdout or rx_stdout or ''

    if rx_stdout:
        for line in rx_stdout.strip().split('\n')[-10:]:
            if line.strip():
                print(f'  [RX-SSH] {line}')

    remote_exists, _, fetched_output, log_text, radio_metrics = fetch_remote_artifacts(
        ssh_prefix=ssh_prefix,
        board_host=board_host,
        board_user=board_user,
        board_pass=board_pass,
        board_port=board_port,
        remote_output=remote_output,
        remote_log=remote_log,
        output_bin=output_bin,
        remote_use_sudo=remote_use_sudo,
    )
    if not log_text:
        radio_metrics = extract_radio_metrics(rx_stdout or '')
        print_radio_metrics(radio_metrics)
    radio_metrics['phy_mode'] = 'arq'
    radio_metrics['remote_rx_ready'] = True
    radio_metrics['remote_ready_wait_sec'] = ready_wait_sec
    radio_metrics['tx_wall_sec'] = tx_wall_sec
    radio_metrics['remote_kill_after_sec'] = round(remote_kill_after, 6)
    radio_metrics['ssh_wait_timeout_sec'] = round(ssh_wait_timeout, 6)

    if ssh_timed_out:
        run_text_command_best_effort(
            ssh_prefix + [wrap_remote_shell_command(
                remote_kill_command(remote_tag),
                board_pass if remote_use_sudo else '',
            )],
            timeout=10.0,
            label='远端 ARQ RX kill',
        )

    run_text_command_best_effort(
        ssh_prefix + [wrap_remote_shell_command(
            remote_cleanup_command(remote_output, remote_log),
            board_pass if remote_use_sudo else '',
        )],
        timeout=10.0,
        label='远端 ARQ RX 清理',
    )

    if tx_result.returncode != 0:
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    if rx_proc.returncode != 0 and not fetched_output:
        print(f'[OTA][ARQ] 远端 RX 退出码: {rx_proc.returncode}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    if not remote_exists or not fetched_output or not os.path.exists(output_bin):
        print(f'[OTA][ARQ] 未取回远端输出文件: {output_bin}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}

    received_size = os.path.getsize(output_bin)
    radio_metrics['received_size'] = received_size
    print(f'[OTA][ARQ] 远端 RX 输出: {output_bin} ({received_size} bytes)')
    return {'ok': True, 'received_size': received_size, 'radio_metrics': radio_metrics}


def run_ota_arq(
    encrypted_bin: str,
    output_bin: str,
    *,
    tx_args: str = '',
    rx_args: str = '',
    tx_gain: float = 60.0,
    rx_gain: float = 60.0,
    rate: float = 1e6,
    freq: float = 915e6,
    rx_timeout: float = 120.0,
    ota_wait: float = 0.4,
    rx_spb: int = 10000,
    rx_setup: float = 0.1,
    no_frame_timeout: float = 8.0,
    rx_ant: str = '',
    board_host: str = '',
    board_user: str = '',
    board_pass: str = '',
    board_port: str = '22',
    remote_build_dir: str = DEFAULT_REMOTE_BUILD_DIR,
    remote_kill_after: float | None = None,
    arq_rev_freq: float = 915.5e6,
    arq_nack_tx_gain: float = 10.0,
    arq_nack_rx_gain: float = 30.0,
) -> dict[str, object]:
    """双设备 OTA ARQ 传输：整包首发 + 反向 NACK 选择性重传。"""
    explicit_rx_ant = str(rx_ant or '').strip()
    if board_host and board_user and board_pass:
        ota_result = run_ota_remote_arq(
            encrypted_bin,
            output_bin,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant=explicit_rx_ant,
            arq_rev_freq=arq_rev_freq,
            arq_nack_tx_gain=arq_nack_tx_gain,
            arq_nack_rx_gain=arq_nack_rx_gain,
            remote_kill_after=remote_kill_after,
        )
        if explicit_rx_ant or not should_retry_with_rx2(ota_result):
            return ota_result

        print('[OTA][ARQ] 默认 RX 天线未锁到有效帧，切换 RX2 重试一次...')
        return run_ota_remote_arq(
            encrypted_bin,
            output_bin,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant='RX2',
            arq_rev_freq=arq_rev_freq,
            arq_nack_tx_gain=arq_nack_tx_gain,
            arq_nack_rx_gain=arq_nack_rx_gain,
            remote_kill_after=remote_kill_after,
        )

    build_dir = os.path.join(os.path.dirname(__file__), '..', 'usrp_tensor', 'build')
    tx_bin = os.path.join(build_dir, 'usrp_tensor_arq_tx')
    rx_bin = os.path.join(build_dir, 'usrp_tensor_arq_rx')
    for path, name in ((tx_bin, 'ARQ TX'), (rx_bin, 'ARQ RX')):
        if not os.path.exists(path):
            print(f'[错误] 找不到 {name}: {path}，请先编译')
            return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    if not prime_local_usrp(rx_args, 'RX'):
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}
    if not prime_local_usrp(tx_args, 'TX'):
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    rx_cmd = build_arq_rx_command(
        rx_bin,
        output_bin,
        rx_args=rx_args,
        rx_gain=rx_gain,
        rate=rate,
        freq=freq,
        rev_freq=arq_rev_freq,
        rx_spb=rx_spb,
        no_frame_timeout=no_frame_timeout,
        nack_tx_gain=arq_nack_tx_gain,
        rx_ant=explicit_rx_ant,
    )
    print(f'[OTA][ARQ] RX 启动: {" ".join(rx_cmd)}')
    rx_proc = subprocess.Popen(
        rx_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    ready_wait_sec = round(
        max(float(ota_wait), min(5.0, max(2.0, float(rx_setup) + 1.5))),
        6,
    )
    print(f'[OTA][ARQ] 等待本地 RX 稳定: {ready_wait_sec:.3f}s')
    time.sleep(ready_wait_sec)

    tx_cmd = build_arq_tx_command(
        tx_bin,
        encrypted_bin,
        tx_args=tx_args,
        tx_gain=tx_gain,
        rate=rate,
        freq=freq,
        rev_freq=arq_rev_freq,
        rx_spb=rx_spb,
        nack_rx_gain=arq_nack_rx_gain,
        rx_ant=explicit_rx_ant,
    )
    print(f'[OTA][ARQ] TX 启动: {" ".join(tx_cmd)}')
    tx_started = time.perf_counter()
    tx_result = subprocess.run(
        tx_cmd,
        capture_output=True,
        text=True,
        timeout=max(300.0, float(rx_timeout) + 60.0),
    )
    tx_wall_sec = round(time.perf_counter() - tx_started, 6)
    tx_log_text = '\n'.join(part for part in (tx_result.stdout, tx_result.stderr) if part).strip()
    if tx_result.returncode != 0:
        print(f'[OTA][ARQ] TX 失败 (rc={tx_result.returncode})')
        if tx_log_text:
            print(tx_log_text[-2000:])
    else:
        print(f'[OTA][ARQ] TX 发送完成 (wall={tx_wall_sec:.3f}s)')
    if tx_log_text:
        for line in tx_log_text.split('\n')[-10:]:
            if line.strip():
                print(f'  [TX] {line}')

    print(f'[OTA][ARQ] 等待 RX 完成 (超时 {rx_timeout}s)...')
    try:
        rx_stdout, _ = rx_proc.communicate(timeout=rx_timeout)
        if rx_stdout:
            for line in rx_stdout.strip().split('\n')[-20:]:
                if line.strip():
                    print(f'  [RX] {line}')
    except subprocess.TimeoutExpired:
        print(f'[OTA][ARQ] RX 超时 ({rx_timeout}s)，终止进程')
        rx_proc.kill()
        rx_proc.communicate()
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    radio_metrics = extract_radio_metrics(rx_stdout or '')
    radio_metrics['phy_mode'] = 'arq'
    radio_metrics['remote_rx_ready'] = True
    radio_metrics['remote_ready_wait_sec'] = ready_wait_sec
    radio_metrics['tx_wall_sec'] = tx_wall_sec
    print_radio_metrics(radio_metrics)

    if tx_result.returncode != 0:
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    if rx_proc.returncode != 0:
        print(f'[OTA][ARQ] RX 退出码: {rx_proc.returncode}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    if not os.path.exists(output_bin):
        print(f'[OTA][ARQ] RX 未生成输出文件: {output_bin}')
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}

    received_size = os.path.getsize(output_bin)
    radio_metrics['received_size'] = received_size
    print(f'[OTA][ARQ] RX 输出: {output_bin} ({received_size} bytes)')
    return {'ok': True, 'received_size': received_size, 'radio_metrics': radio_metrics}


def should_retry_with_rx2(ota_result: dict[str, object]) -> bool:
    """在默认口位完全未锁到有效帧时，自动尝试 RX2。"""
    if bool(ota_result.get('ok')):
        return False

    metrics = dict(ota_result.get('radio_metrics') or {})
    frames_ok = int(metrics.get('frames_ok') or 0)
    max_payload_seen = int(metrics.get('max_payload_seen') or 0)
    expected_payload = int(metrics.get('expected_payload') or 0)
    return frames_ok == 0 and max_payload_seen == 0 and expected_payload == 0


def run_ota(encrypted_bin: str, output_bin: str,
            tx_args: str = "", rx_args: str = "",
            tx_gain: float = 60.0, rx_gain: float = 60.0,
            rate: float = 1e6, freq: float = 915e6,
            repeat: int = 1, rx_timeout: float = 120.0,
            ota_wait: float = 0.4,
            start_pad_samps: int = 100000,
            round_gap_ms: int = 500,
            frame_repeat: int = 1,
            rx_spb: int = 10000,
            rx_setup: float = 0.1,
            no_frame_timeout: float = 8.0,
            rx_ant: str = '',
            decode_workers: int = 2,
            payload_search_order: str = 'auto',
            warmup_frames: int = 2,
            warmup_repeats: int = 2,
            warmup_rounds: int = 1,
            tail_pad_samps: int = 2000,
            last_frame_extra_repeats: int = 0,
            first_frame_extra_repeats: int = 0,
            frame_order: str = 'normal',
            board_host: str = '',
            board_user: str = '',
            board_pass: str = '',
            board_port: str = '22',
            remote_build_dir: str = DEFAULT_REMOTE_BUILD_DIR,
            remote_kill_after: float | None = None,
            ota_phy_mode: str = 'plain',
            arq_rev_freq: float = 915.5e6,
            arq_nack_tx_gain: float = 10.0,
            arq_nack_rx_gain: float = 30.0) -> dict[str, object]:
    """双设备 OTA 传输：先启动 RX，再启动 TX，等待双方完成

    Returns:
        dict: {'ok': bool, 'received_size': int, 'radio_metrics': dict}
    """
    if str(ota_phy_mode or 'plain').strip().lower() == 'arq':
        return run_ota_arq(
            encrypted_bin,
            output_bin,
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant=rx_ant,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
            remote_kill_after=remote_kill_after,
            arq_rev_freq=arq_rev_freq,
            arq_nack_tx_gain=arq_nack_tx_gain,
            arq_nack_rx_gain=arq_nack_rx_gain,
        )

    explicit_rx_ant = str(rx_ant or '').strip()
    if board_host and board_user and board_pass:
        ota_result = run_ota_remote(
            encrypted_bin,
            output_bin,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            repeat=repeat,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            start_pad_samps=start_pad_samps,
            round_gap_ms=round_gap_ms,
            frame_repeat=frame_repeat,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant=explicit_rx_ant or 'TX/RX',
            decode_workers=decode_workers,
            payload_search_order=payload_search_order,
            warmup_frames=warmup_frames,
            warmup_repeats=warmup_repeats,
            warmup_rounds=warmup_rounds,
            tail_pad_samps=tail_pad_samps,
            last_frame_extra_repeats=last_frame_extra_repeats,
            first_frame_extra_repeats=first_frame_extra_repeats,
            frame_order=frame_order,
            remote_kill_after=remote_kill_after,
        )
        if explicit_rx_ant or not should_retry_with_rx2(ota_result):
            return ota_result

        print('[OTA] 默认 RX 天线未锁到有效帧，切换 RX2 重试一次...')
        return run_ota_remote(
            encrypted_bin,
            output_bin,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            repeat=repeat,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            start_pad_samps=start_pad_samps,
            round_gap_ms=round_gap_ms,
            frame_repeat=frame_repeat,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant='RX2',
            decode_workers=decode_workers,
            payload_search_order=payload_search_order,
            warmup_frames=warmup_frames,
            warmup_repeats=warmup_repeats,
            warmup_rounds=warmup_rounds,
            tail_pad_samps=tail_pad_samps,
            last_frame_extra_repeats=last_frame_extra_repeats,
            first_frame_extra_repeats=first_frame_extra_repeats,
            frame_order=frame_order,
            remote_kill_after=remote_kill_after,
        )

    build_dir = os.path.join(
        os.path.dirname(__file__), "..", "usrp_tensor", "build")
    tx_bin = os.path.join(build_dir, "usrp_tensor_tx")
    rx_bin = os.path.join(build_dir, "usrp_tensor_rx")

    for path, name in [(tx_bin, "TX"), (rx_bin, "RX")]:
        if not os.path.exists(path):
            print(f"[错误] 找不到 {name}: {path}，请先编译")
            return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    if not prime_local_usrp(rx_args, 'RX'):
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}
    if not prime_local_usrp(tx_args, 'TX'):
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    # 1. 先启动 RX（后台），等待 UHD 初始化
    rx_cmd = [rx_bin, "--output", output_bin,
              "--args", rx_args,
              "--rate", str(rate), "--freq", str(freq),
              "--gain", str(rx_gain),
              "--spb", str(rx_spb),
              "--setup", str(rx_setup),
              "--timeout", str(no_frame_timeout),
              "--decode-workers", str(decode_workers)]
    if explicit_rx_ant:
        rx_cmd.extend(['--ant', explicit_rx_ant])
    print(f"[OTA] RX 启动: {' '.join(rx_cmd)}")
    rx_proc = subprocess.Popen(rx_cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    time.sleep(ota_wait)

    # 2. 启动 TX（前台），TX 发完即退出
    tx_cmd = [tx_bin, "--file", encrypted_bin,
              "--args", tx_args,
              "--rate", str(rate), "--freq", str(freq),
              "--gain", str(tx_gain),
              "--repeat", str(repeat),
              "--frame-repeat", str(frame_repeat),
              "--start-pad-samps", str(start_pad_samps),
              "--round-gap-ms", str(round_gap_ms),
              "--warmup-frames", str(warmup_frames),
              "--warmup-repeats", str(warmup_repeats),
              "--warmup-rounds", str(warmup_rounds),
              "--tail-pad-samps", str(tail_pad_samps),
              "--last-frame-extra-repeats",
              str(last_frame_extra_repeats),
              "--first-frame-extra-repeats",
              str(first_frame_extra_repeats),
              "--frame-order", str(frame_order)]
    print(f"[OTA] TX 启动: {' '.join(tx_cmd)}")
    tx_result = subprocess.run(tx_cmd, capture_output=True, text=True,
                               timeout=300)
    if tx_result.returncode != 0:
        print(f"[OTA] TX 失败 (rc={tx_result.returncode})")
        if tx_result.stderr:
            print(tx_result.stderr[-2000:])
    else:
        print("[OTA] TX 发送完成")
    if tx_result.stdout:
        for line in tx_result.stdout.strip().split("\n")[-10:]:
            print(f"  [TX] {line}")

    # 3. 等待 RX 完成
    print(f"[OTA] 等待 RX 完成 (超时 {rx_timeout}s)...")
    try:
        rx_stdout, _ = rx_proc.communicate(timeout=rx_timeout)
        if rx_stdout:
            for line in rx_stdout.strip().split("\n")[-20:]:
                print(f"  [RX] {line}")
    except subprocess.TimeoutExpired:
        print(f"[OTA] RX 超时 ({rx_timeout}s)，终止进程")
        rx_proc.kill()
        rx_proc.communicate()
        return {'ok': False, 'received_size': 0, 'radio_metrics': {}}

    radio_metrics = extract_radio_metrics(rx_stdout or '')
    print_radio_metrics(radio_metrics)

    if rx_proc.returncode != 0:
        print(f"[OTA] RX 退出码: {rx_proc.returncode}")
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}

    # 4. 检查输出文件
    if not os.path.exists(output_bin):
        print(f"[OTA] RX 未生成输出文件: {output_bin}")
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}
    received_size = os.path.getsize(output_bin)
    if received_size == 0:
        print("[OTA] RX 输出文件为空")
        return {'ok': False, 'received_size': 0, 'radio_metrics': radio_metrics}

    print(f"[OTA] RX 输出: {output_bin} ({received_size} bytes)")
    return {'ok': True, 'received_size': received_size, 'radio_metrics': radio_metrics}


def run_ota_chunked_remote_daemon(
    wire_bytes: bytes,
    *,
    chunk_bytes: int,
    min_chunk_bytes: int = 0,
    chunk_retries: int = 0,
    chunk_align_bytes: int = DEFAULT_OTA_CHUNK_ALIGN_BYTES,
    tx_args: str = '',
    rx_args: str = '',
    tx_gain: float = 60.0,
    rx_gain: float = 60.0,
    rate: float = 1e6,
    freq: float = 915e6,
    repeat: int = 1,
    rx_timeout: float = 120.0,
    ota_wait: float = 0.4,
    start_pad_samps: int = 100000,
    round_gap_ms: int = 500,
    frame_repeat: int = 1,
    rx_spb: int = 10000,
    rx_setup: float = 0.1,
    no_frame_timeout: float = 8.0,
    rx_ant: str = '',
    decode_workers: int = 2,
    payload_search_order: str = 'auto',
    warmup_frames: int = 2,
    warmup_repeats: int = 2,
    warmup_rounds: int = 1,
    tail_pad_samps: int = 2000,
    last_frame_extra_repeats: int = 0,
    first_frame_extra_repeats: int = 0,
    board_host: str = '',
    board_user: str = '',
    board_pass: str = '',
    board_port: str = '22',
    remote_build_dir: str = DEFAULT_REMOTE_BUILD_DIR,
) -> tuple[bool, bytes, dict[str, object]]:
    """远端 RX + 本地 TX 常驻 daemon 复用版分块 OTA。"""
    try:
        session = ChunkedRemoteOtaDaemonSession(
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            repeat=repeat,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            start_pad_samps=start_pad_samps,
            round_gap_ms=round_gap_ms,
            frame_repeat=frame_repeat,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant=rx_ant,
            decode_workers=decode_workers,
            payload_search_order=payload_search_order,
            warmup_frames=warmup_frames,
            warmup_repeats=warmup_repeats,
            warmup_rounds=warmup_rounds,
            tail_pad_samps=tail_pad_samps,
            last_frame_extra_repeats=last_frame_extra_repeats,
            first_frame_extra_repeats=first_frame_extra_repeats,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
        )
        try:
            return session.transmit(
                wire_bytes,
                chunk_bytes=chunk_bytes,
                min_chunk_bytes=min_chunk_bytes,
                chunk_retries=chunk_retries,
                chunk_align_bytes=chunk_align_bytes,
            )
        finally:
            session.close()
    except Exception as exc:
        print(f'[OTA] 远端 daemon 会话初始化失败: {exc}')
        return False, b'', {'daemon_error': str(exc)}


def run_ota_chunked(
    wire_bytes: bytes,
    *,
    chunk_bytes: int,
    min_chunk_bytes: int = 0,
    chunk_retries: int = 0,
    chunk_align_bytes: int = DEFAULT_OTA_CHUNK_ALIGN_BYTES,
    tx_args: str = '',
    rx_args: str = '',
    tx_gain: float = 60.0,
    rx_gain: float = 60.0,
    rate: float = 1e6,
    freq: float = 915e6,
    repeat: int = 1,
    rx_timeout: float = 120.0,
    ota_wait: float = 0.4,
    start_pad_samps: int = 100000,
    round_gap_ms: int = 500,
    frame_repeat: int = 1,
    rx_spb: int = 10000,
    rx_setup: float = 0.1,
    no_frame_timeout: float = 8.0,
    rx_ant: str = '',
    decode_workers: int = 2,
    payload_search_order: str = 'auto',
    warmup_frames: int = 2,
    warmup_repeats: int = 2,
    warmup_rounds: int = 1,
    tail_pad_samps: int = 2000,
    last_frame_extra_repeats: int = 0,
    first_frame_extra_repeats: int = 0,
    board_host: str = '',
    board_user: str = '',
    board_pass: str = '',
    board_port: str = '22',
    remote_build_dir: str = DEFAULT_REMOTE_BUILD_DIR,
    remote_kill_after: float | None = None,
) -> tuple[bool, bytes, dict[str, object]]:
    """按固定分块大小重复调用 OTA，失败时可自动降级为更小分块。"""
    if chunk_bytes <= 0:
        raise ValueError('chunk_bytes 必须大于 0')
    if min_chunk_bytes < 0:
        raise ValueError('min_chunk_bytes 不能小于 0')
    if min_chunk_bytes > 0 and min_chunk_bytes > chunk_bytes:
        raise ValueError('min_chunk_bytes 不能大于 chunk_bytes')
    if chunk_align_bytes < 0:
        raise ValueError('chunk_align_bytes 不能小于 0')

    if board_host and board_user and board_pass:
        return run_ota_chunked_remote_daemon(
            wire_bytes,
            chunk_bytes=chunk_bytes,
            min_chunk_bytes=min_chunk_bytes,
            chunk_retries=chunk_retries,
            chunk_align_bytes=chunk_align_bytes,
            tx_args=tx_args,
            rx_args=rx_args,
            tx_gain=tx_gain,
            rx_gain=rx_gain,
            rate=rate,
            freq=freq,
            repeat=repeat,
            rx_timeout=rx_timeout,
            ota_wait=ota_wait,
            start_pad_samps=start_pad_samps,
            round_gap_ms=round_gap_ms,
            frame_repeat=frame_repeat,
            rx_spb=rx_spb,
            rx_setup=rx_setup,
            no_frame_timeout=no_frame_timeout,
            rx_ant=rx_ant,
            decode_workers=decode_workers,
            payload_search_order=payload_search_order,
            warmup_frames=warmup_frames,
            warmup_repeats=warmup_repeats,
            warmup_rounds=warmup_rounds,
            tail_pad_samps=tail_pad_samps,
            last_frame_extra_repeats=last_frame_extra_repeats,
            first_frame_extra_repeats=first_frame_extra_repeats,
            board_host=board_host,
            board_user=board_user,
            board_pass=board_pass,
            board_port=board_port,
            remote_build_dir=remote_build_dir,
        )

    effective_min_chunk_bytes = int(min_chunk_bytes)
    if effective_min_chunk_bytes == 0 and chunk_align_bytes > 0 and chunk_bytes > chunk_align_bytes:
        effective_min_chunk_bytes = int(chunk_align_bytes)
        print(
            '[OTA] 未显式指定最小分块，启用自动降级: '
            f'min_chunk_bytes={effective_min_chunk_bytes}'
        )

    total_len = len(wire_bytes)
    retry_limit = max(0, int(chunk_retries))
    received_parts: list[tuple[int, bytes]] = []
    last_radio_metrics: dict[str, object] = {}
    pending_chunks: list[tuple[int, bytes]] = [
        (offset, wire_bytes[offset:offset + chunk_bytes])
        for offset in range(0, total_len, chunk_bytes)
    ]
    tail_rebalance_min_bytes = 0
    if chunk_align_bytes > 1:
        tail_rebalance_min_bytes = max(
            effective_min_chunk_bytes,
            int(chunk_align_bytes) * 2,
        )
    rebalanced_chunks = rebalance_tail_chunk_plan(
        pending_chunks,
        tail_min_bytes=tail_rebalance_min_bytes,
        shift_align_bytes=chunk_align_bytes,
    )
    if rebalanced_chunks != pending_chunks and len(rebalanced_chunks) >= 2:
        print(
            '[OTA] 尾块回填: '
            f'prev={len(pending_chunks[-2][1])}B tail={len(pending_chunks[-1][1])}B -> '
            f'{len(rebalanced_chunks[-2][1])}B + {len(rebalanced_chunks[-1][1])}B'
        )
    pending_chunks = rebalanced_chunks
    processed_chunks = 0
    chunk_retry_used = 0
    success_elapsed_sec: list[float] = []
    attempt_metric_samples: list[dict[str, object]] = []
    success_metric_samples: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix='e2e_ota_chunks_') as temp_dir:
        while pending_chunks:
            offset, chunk = pending_chunks.pop(0)
            chunk_input = os.path.join(temp_dir, f'chunk_{offset:08d}.bin')
            with open(chunk_input, 'wb') as handle:
                handle.write(chunk)

            chunk_ok = False
            typical_sec, chunk_rx_timeout, chunk_no_frame_timeout = choose_chunk_time_budget(
                success_elapsed_sec=success_elapsed_sec,
                chunk_len=len(chunk),
            )
            if rx_timeout > 0:
                chunk_rx_timeout = min(chunk_rx_timeout, float(rx_timeout))
            if no_frame_timeout > 0:
                chunk_no_frame_timeout = min(chunk_no_frame_timeout, float(no_frame_timeout))
            chunk_no_frame_timeout = min(chunk_no_frame_timeout, chunk_rx_timeout)
            chunk_remote_kill_after = round(
                max(chunk_rx_timeout + 3.0, chunk_no_frame_timeout + 2.0),
                3,
            )
            print(
                '[OTA] 分块时限: '
                f'typical={typical_sec:.3f}s '
                f'rx_timeout={chunk_rx_timeout:.3f}s '
                f'no_frame_timeout={chunk_no_frame_timeout:.3f}s '
                f'remote_kill_after={chunk_remote_kill_after:.3f}s'
            )
            chunk_start_pad_samps, chunk_round_gap_ms = choose_chunk_tx_profile(
                chunk_len=len(chunk),
                start_pad_samps=start_pad_samps,
                round_gap_ms=round_gap_ms,
            )
            if chunk_start_pad_samps != start_pad_samps or chunk_round_gap_ms != round_gap_ms:
                print(
                    '[OTA] 分块 TX 加速: '
                    f'start_pad_samps={start_pad_samps}->{chunk_start_pad_samps} '
                    f'round_gap_ms={round_gap_ms}->{chunk_round_gap_ms}'
                )
            for attempt in range(retry_limit + 1):
                chunk_output = os.path.join(temp_dir, f'chunk_{offset:08d}.rx.bin')
                if os.path.exists(chunk_output):
                    os.unlink(chunk_output)

                print(
                    f'[OTA] 分块 {processed_chunks + 1}: '
                    f'offset={offset} len={len(chunk)}B '
                    f'attempt={attempt + 1}/{retry_limit + 1}'
                )
                attempt_started = time.perf_counter()
                ota_result = run_ota(
                    chunk_input,
                    chunk_output,
                    tx_args=tx_args,
                    rx_args=rx_args,
                    tx_gain=tx_gain,
                    rx_gain=rx_gain,
                    rate=rate,
                    freq=freq,
                    repeat=repeat,
                    rx_timeout=chunk_rx_timeout,
                    ota_wait=ota_wait,
                    start_pad_samps=chunk_start_pad_samps,
                    round_gap_ms=chunk_round_gap_ms,
                    frame_repeat=frame_repeat,
                    rx_spb=rx_spb,
                    rx_setup=rx_setup,
                    no_frame_timeout=chunk_no_frame_timeout,
                    rx_ant=rx_ant,
                    decode_workers=decode_workers,
                    payload_search_order=payload_search_order,
                    warmup_frames=warmup_frames,
                    warmup_repeats=warmup_repeats,
                    warmup_rounds=warmup_rounds,
                    tail_pad_samps=tail_pad_samps,
                    frame_order=frame_order,
                    last_frame_extra_repeats=last_frame_extra_repeats,
                    first_frame_extra_repeats=first_frame_extra_repeats,
                    board_host=board_host,
                    board_user=board_user,
                    board_pass=board_pass,
                    board_port=board_port,
                    remote_build_dir=remote_build_dir,
                    remote_kill_after=chunk_remote_kill_after,
                )
                last_radio_metrics = dict(ota_result.get('radio_metrics') or {})
                attempt_wall_sec = round(time.perf_counter() - attempt_started, 6)
                last_radio_metrics['attempt_wall_sec'] = attempt_wall_sec

                received_chunk = b''
                if os.path.exists(chunk_output):
                    with open(chunk_output, 'rb') as handle:
                        received_chunk = handle.read()
                    enrich_channel_metrics(last_radio_metrics, chunk, received_chunk)
                    print_channel_metrics(last_radio_metrics)

                radio_elapsed = last_radio_metrics.get('elapsed_sec')
                if radio_elapsed is not None:
                    print(
                        '[OTA] 分块耗时: '
                        f'wall={attempt_wall_sec:.3f}s '
                        f'radio={float(radio_elapsed):.3f}s'
                    )
                else:
                    print(f'[OTA] 分块耗时: wall={attempt_wall_sec:.3f}s')

                attempt_metric_samples.append(dict(last_radio_metrics))

                if received_chunk == chunk:
                    if attempt_wall_sec > 0:
                        success_elapsed_sec.append(float(attempt_wall_sec))
                    success_metric_samples.append(dict(last_radio_metrics))
                    received_parts.append((offset, received_chunk))
                    processed_chunks += 1
                    chunk_retry_used += attempt
                    chunk_ok = True
                    break

                if received_chunk:
                    print(
                        f'[OTA] 分块校验失败: '
                        f'sent={len(chunk)}B received={len(received_chunk)}B'
                    )
                else:
                    print('[OTA] 分块未收到有效输出')

            if not chunk_ok:
                if effective_min_chunk_bytes > 0 and len(chunk) > effective_min_chunk_bytes:
                    chunk_retry_used += retry_limit
                    split_point = choose_chunk_split_point(
                        len(chunk),
                        effective_min_chunk_bytes,
                        chunk_align_bytes,
                    )
                    if 0 < split_point < len(chunk):
                        left = chunk[:split_point]
                        right = chunk[split_point:]
                        print(
                            '[OTA] 分块失败，自动降级切分: '
                            f'offset={offset} len={len(chunk)}B -> '
                            f'{len(left)}B + {len(right)}B'
                            + (
                                f' (align={chunk_align_bytes}B)'
                                if chunk_align_bytes > 1 else ''
                            )
                        )
                        pending_chunks.insert(0, (offset + split_point, right))
                        pending_chunks.insert(0, (offset, left))
                        continue

                last_radio_metrics['chunk_total'] = processed_chunks + len(pending_chunks) + 1
                last_radio_metrics['chunk_completed'] = processed_chunks
                last_radio_metrics['chunk_retry_used'] = chunk_retry_used + retry_limit
                last_radio_metrics.update(
                    summarize_metric_samples(
                        attempt_metric_samples,
                        count_key='attempt_sample_count',
                    )
                )
                last_radio_metrics.update(
                    summarize_metric_samples(
                        success_metric_samples,
                        prefix='success_',
                        count_key='success_sample_count',
                    )
                )
                ordered_parts = b''.join(
                    part for _, part in sorted(received_parts, key=lambda item: item[0])
                )
                return False, ordered_parts, last_radio_metrics

    ordered_parts = b''.join(
        part for _, part in sorted(received_parts, key=lambda item: item[0])
    )
    last_radio_metrics['chunk_total'] = processed_chunks
    last_radio_metrics['chunk_completed'] = processed_chunks
    last_radio_metrics['chunk_retry_used'] = chunk_retry_used
    last_radio_metrics.update(
        summarize_metric_samples(
            attempt_metric_samples,
            count_key='attempt_sample_count',
        )
    )
    last_radio_metrics.update(
        summarize_metric_samples(
            success_metric_samples,
            prefix='success_',
            count_key='success_sample_count',
        )
    )
    return True, ordered_parts, last_radio_metrics


def main():
    parser = argparse.ArgumentParser(
        description="端到端闭环: ML-KEM 加密 → USRP 传输 → ML-KEM 解密")
    parser.add_argument("--mode", choices=["encrypt", "decrypt", "sim",
                                           "loopback", "ota"],
                        default="sim",
                        help="运行模式 (默认: sim)")
    parser.add_argument("--input", required=True,
                        help="输入文件 (.npz latent 或 .bin 密文)")
    parser.add_argument("-o", "--output",
                        help="输出文件 (加密模式: 密文.bin, 解密模式: latent.npz)")
    parser.add_argument("--session",
                        help="会话文件路径 (加密模式保存, 解密模式加载)")
    parser.add_argument("--suite", default="SM4_GCM",
                        choices=["AES_256_GCM", "SM4_GCM"],
                        help="密码套件 (默认: SM4_GCM)")
    parser.add_argument("--snr", type=float, default=24.0,
                        help="SIM 模式 SNR (dB, 默认: 24)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="重复轮数 (默认: 1)")
    parser.add_argument("--tx-args", default="",
                        help="TX UHD 设备参数")
    parser.add_argument("--rx-args", default="",
                        help="RX UHD 设备参数")
    parser.add_argument("--tx-gain", type=float, default=60.0,
                        help="TX 增益 (dB, 默认: 60)")
    parser.add_argument("--rx-gain", type=float, default=60.0,
                        help="RX 增益 (dB, 默认: 60)")
    parser.add_argument("--rate", type=float, default=1e6,
                        help="USRP 采样率 Hz (默认: 1e6)")
    parser.add_argument("--freq", type=float, default=915e6,
                        help="RF 中心频率 Hz (默认: 915e6)")
    parser.add_argument("--rx-timeout", type=float, default=120.0,
                        help="OTA RX 最大等待秒数 (默认: 120)")
    parser.add_argument("--ota-wait", type=float, default=0.4,
                        help="OTA 模式下 RX 启动后等待 TX 的秒数 (默认: 0.4)")
    parser.add_argument("--ota-phy-mode", choices=["plain", "arq"], default="plain",
                        help="OTA 物理链路模式：plain=单向重复，arq=整包首发+NACK补偿")
    parser.add_argument("--start-pad-samps", type=int, default=100000,
                        help="TX 起始静默样本数 (默认: 100000)")
    parser.add_argument("--round-gap-ms", type=int, default=500,
                        help="TX 重复轮之间的间隔毫秒数 (默认: 500)")
    parser.add_argument("--frame-repeat", type=int, default=1,
                        help="主发送阶段每帧紧邻重复次数 (默认: 1)")
    parser.add_argument("--first-frame-extra-repeats", type=int, default=0,
                        help="TX 每轮首帧主发送后额外重复首帧的次数 (默认: 0)")
    parser.add_argument("--frame-order", default="normal",
                        help="TX 主发送顺序: normal/tail-first")
    parser.add_argument("--rx-spb", type=int, default=10000,
                        help="OTA RX 每批次接收样本数 (默认: 10000)")
    parser.add_argument("--rx-setup", type=float, default=0.1,
                        help="OTA RX setup 等待秒数 (默认: 0.1)")
    parser.add_argument("--no-frame-timeout", type=float, default=8.0,
                        help="OTA RX 收到首帧后的无新帧超时秒数 (默认: 8)")
    parser.add_argument("--decode-workers", type=int, default=2,
                        help="OTA RX 异步 post-capture 解码 worker 数 (默认: 2)")
    parser.add_argument("--rx-ant", default="",
                        help="OTA RX 天线口位（留空时先用默认口位，必要时自动回退到 RX2）")
    parser.add_argument("--payload-search-order", default="auto",
                        help="OTA RX payload 搜索顺序: auto/gardner-first/phase-first/phase-only")
    parser.add_argument("--arq-rev-freq", type=float, default=915.5e6,
                        help="ARQ 反向 NACK 频率 Hz (默认: 915.5e6)")
    parser.add_argument("--arq-nack-tx-gain", type=float, default=10.0,
                        help="ARQ 反向 NACK 发射增益 dB (默认: 10)")
    parser.add_argument("--arq-nack-rx-gain", type=float, default=30.0,
                        help="ARQ 反向 NACK 接收增益 dB (默认: 30)")
    parser.add_argument("--warmup-frames", type=int, default=2,
                        help="TX 热机帧数 (默认: 2)")
    parser.add_argument("--warmup-repeats", type=int, default=2,
                        help="TX 热机重复轮数 (默认: 2)")
    parser.add_argument("--warmup-rounds", type=int, default=1,
                        help="TX 执行热机的发送轮数 (默认: 1)")
    parser.add_argument("--tail-pad-samps", type=int, default=2000,
                        help="TX 每轮最后一帧后补零样本数 (默认: 2000)")
    parser.add_argument("--last-frame-extra-repeats", type=int, default=0,
                        help="TX 每轮主发送结束后额外重复最后一帧的次数 (默认: 0)")
    parser.add_argument("--board-host", default="",
                        help="远端板端 SSH 主机地址（为空时使用本地 RX）")
    parser.add_argument("--board-user", default="",
                        help="远端板端 SSH 用户名")
    parser.add_argument("--board-pass", default="",
                        help="远端板端 SSH 密码")
    parser.add_argument("--board-port", default="22",
                        help="远端板端 SSH 端口 (默认: 22)")
    parser.add_argument("--remote-build-dir", default=DEFAULT_REMOTE_BUILD_DIR,
                        help="远端 usrp_tensor build 目录")
    parser.add_argument("--remote-kill-after", type=float, default=180.0,
                        help="远端 RX shell timeout 秒数 (默认: 180)")
    parser.add_argument("--ota-chunk-bytes", type=int, default=0,
                        help="OTA 模式下将密文切分为固定大小分块逐块传输（0=禁用）")
    parser.add_argument("--ota-min-chunk-bytes", type=int, default=0,
                        help="OTA 分块失败后自动降级的最小分块大小（0=禁用自动降级）")
    parser.add_argument("--ota-chunk-align-bytes", type=int, default=DEFAULT_OTA_CHUNK_ALIGN_BYTES,
                        help="OTA 分块自动降级时的对齐字节数（默认: 219，对齐 PHY payload）")
    parser.add_argument("--ota-chunk-retries", type=int, default=0,
                        help="OTA 分块逐块重试次数（默认: 0，仅首发一次）")
    parser.add_argument("--raw-file-input", action="store_true",
                        help="按原始文件字节读取输入，不展开 .npz latent")
    args = parser.parse_args()

    suite = CipherSuite[args.suite]

    if args.mode == "encrypt":
        # ── 加密模式 ──
        if not args.output:
            args.output = args.input.rsplit(".", 1)[0] + ".encrypted.bin"

        # 读取输入
        plaintext, input_is_npz = load_plaintext_input(
            args.input,
            raw_file_input=args.raw_file_input,
        )
        if args.raw_file_input:
            print(f'[加密] 读取原始文件 {args.input}: {len(plaintext)} bytes')
        elif input_is_npz:
            import numpy as np

            with np.load(args.input) as data:
                key = 'latent'
                if key not in data:
                    key = list(data.keys())[0]
                tensor = data[key]
            print(f'[加密] 读取 {args.input}: shape={tensor.shape}, '
                  f'{len(plaintext)} bytes')
        else:
            print(f'[加密] 读取 {args.input}: {len(plaintext)} bytes')

        sha_orig = hashlib.sha256(plaintext).hexdigest()[:16]
        wire_bytes, responder, _, t_hs, t_enc = mlkem_encrypt(plaintext, suite)

        with open(args.output, "wb") as f:
            f.write(wire_bytes)

        print(f"[加密] ML-KEM 握手: {t_hs:.1f}ms")
        print(f"[加密] AEAD 加密: {t_enc:.1f}ms")
        print(f"[加密] {len(plaintext)}B → {len(wire_bytes)}B "
              f"(+{len(wire_bytes)-len(plaintext)}B overhead)")
        print(f"[加密] SHA256: {sha_orig}...")
        print(f"[加密] 输出: {args.output}")

        if args.session:
            save_session(responder, suite, args.session)
            print(f"[加密] 会话已保存: {args.session}")

    elif args.mode == "decrypt":
        # ── 解密模式 ──
        if not args.session:
            print("[错误] 解密模式需要 --session 参数")
            sys.exit(1)

        with open(args.input, "rb") as f:
            ciphertext = f.read()
        print(f"[解密] 读取 {args.input}: {len(ciphertext)} bytes")

        suite_loaded, session_key = load_session(args.session)
        t0 = time.perf_counter()
        decrypted = decrypt_with_loaded_key(ciphertext, suite_loaded, session_key)
        t_dec = (time.perf_counter() - t0) * 1000

        sha_dec = hashlib.sha256(decrypted).hexdigest()[:16]
        print(f"[解密] AEAD 解密: {t_dec:.1f}ms")
        print(f"[解密] {len(ciphertext)}B → {len(decrypted)}B")
        print(f"[解密] SHA256: {sha_dec}...")

        if args.output:
            if args.raw_file_input:
                with open(args.output, 'wb') as f:
                    f.write(decrypted)
                print(f'[解密] 输出 raw: {args.output}, {len(decrypted)} bytes')
            elif args.output.endswith(".npz"):
                import numpy as np
                tensor = np.frombuffer(decrypted, dtype=np.float32)
                np.savez(args.output, latent=tensor)
                print(f"[解密] 输出 npz: {args.output}, shape={tensor.shape}")
            else:
                with open(args.output, "wb") as f:
                    f.write(decrypted)
                print(f"[解密] 输出 bin: {args.output}")

    elif args.mode in ("sim", "loopback", "ota"):
        # ── 完整闭环 ──
        print("=" * 60)
        print("ML-KEM + USRP 端到端闭环")
        print("=" * 60)
        print(f"密码套件: {suite.value}")
        print(f"传输模式: {args.mode}")
        print()

        # 1. 读取输入
        plaintext, input_is_npz = load_plaintext_input(
            args.input,
            raw_file_input=args.raw_file_input,
        )
        if args.raw_file_input:
            print(f'[1/5] 读取原始文件: {args.input}, {len(plaintext)} bytes')
        elif input_is_npz:
            import numpy as np

            with np.load(args.input) as data:
                key = 'latent'
                if key not in data:
                    key = list(data.keys())[0]
                tensor = data[key]
            print(f"[1/5] 读取 latent: shape={tensor.shape}, "
                  f"{len(plaintext)} bytes")
        else:
            print(f"[1/5] 读取 binary: {len(plaintext)} bytes")

        sha_orig = hashlib.sha256(plaintext).hexdigest()[:16]

        # 2. ML-KEM 加密
        print(f"[2/5] ML-KEM-768 握手 + {suite.value} 加密...")
        wire_bytes, responder, _, t_hs, t_enc = mlkem_encrypt(plaintext, suite)
        print(f"       握手: {t_hs:.1f}ms, 加密: {t_enc:.1f}ms, "
              f"密文: {len(wire_bytes)}B")

        # 3. USRP 传输
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False,
                                         prefix="e2e_enc_") as tmp_enc:
            tmp_enc.write(wire_bytes)
            tmp_enc_path = tmp_enc.name

        print(f"[3/5] USRP 传输 ({args.mode}, {len(wire_bytes)}B)...")

        received_ciphertext = b""  # OTA 模式下会被覆盖
        ota_result: dict[str, object] | None = None
        radio_metrics: dict[str, object] = {}

        if args.mode == "sim":
            ok = run_sim_tx(tmp_enc_path, None, snr=args.snr,
                             repeat=args.repeat)
        elif args.mode == "loopback":
            ok = run_loopback(tmp_enc_path, tx_args=args.tx_args,
                              tx_gain=args.tx_gain, rx_gain=args.rx_gain,
                              repeat=args.repeat)
        elif args.mode == "ota":
            if args.ota_phy_mode == 'arq':
                if args.ota_chunk_bytes > 0:
                    print('[OTA][ARQ] 已启用整包 ARQ，忽略分块参数')
                with tempfile.NamedTemporaryFile(suffix=".bin", delete=False,
                                                 prefix="e2e_rx_") as tmp_rx:
                    tmp_rx_path = tmp_rx.name

                ota_result = run_ota(tmp_enc_path, tmp_rx_path,
                                     tx_args=args.tx_args, rx_args=args.rx_args,
                                     tx_gain=args.tx_gain, rx_gain=args.rx_gain,
                                     rate=args.rate, freq=args.freq,
                                     repeat=args.repeat, rx_timeout=args.rx_timeout,
                                     ota_wait=args.ota_wait,
                                     start_pad_samps=args.start_pad_samps,
                                     round_gap_ms=args.round_gap_ms,
                                     frame_repeat=args.frame_repeat,
                                     rx_spb=args.rx_spb,
                                     rx_setup=args.rx_setup,
                                     no_frame_timeout=args.no_frame_timeout,
                                     rx_ant=args.rx_ant,
                                     decode_workers=args.decode_workers,
                                     payload_search_order=args.payload_search_order,
                                     warmup_frames=args.warmup_frames,
                                     warmup_repeats=args.warmup_repeats,
                                     warmup_rounds=args.warmup_rounds,
                                     tail_pad_samps=args.tail_pad_samps,
                                     frame_order=args.frame_order,
                                     last_frame_extra_repeats=args.last_frame_extra_repeats,
                                     first_frame_extra_repeats=args.first_frame_extra_repeats,
                                     board_host=args.board_host,
                                     board_user=args.board_user,
                                     board_pass=args.board_pass,
                                     board_port=args.board_port,
                                     remote_build_dir=args.remote_build_dir,
                                     remote_kill_after=args.remote_kill_after,
                                     ota_phy_mode=args.ota_phy_mode,
                                     arq_rev_freq=args.arq_rev_freq,
                                     arq_nack_tx_gain=args.arq_nack_tx_gain,
                                     arq_nack_rx_gain=args.arq_nack_rx_gain)
                ok = bool(ota_result.get("ok"))

                if ok:
                    with open(tmp_rx_path, "rb") as f:
                        received_ciphertext = f.read()
                    print(f"       RX 收到: {len(received_ciphertext)} bytes")

                if os.path.exists(tmp_rx_path):
                    os.unlink(tmp_rx_path)
                if os.path.exists(tmp_rx_path + '.rx.log'):
                    os.unlink(tmp_rx_path + '.rx.log')
            elif args.ota_chunk_bytes > 0 and len(wire_bytes) > args.ota_chunk_bytes:
                ota_ok, received_ciphertext, radio_metrics = run_ota_chunked(
                    wire_bytes,
                    chunk_bytes=args.ota_chunk_bytes,
                    min_chunk_bytes=args.ota_min_chunk_bytes,
                    chunk_retries=args.ota_chunk_retries,
                    chunk_align_bytes=args.ota_chunk_align_bytes,
                    tx_args=args.tx_args,
                    rx_args=args.rx_args,
                    tx_gain=args.tx_gain,
                    rx_gain=args.rx_gain,
                    rate=args.rate,
                    freq=args.freq,
                    repeat=args.repeat,
                    rx_timeout=args.rx_timeout,
                    ota_wait=args.ota_wait,
                    start_pad_samps=args.start_pad_samps,
                    round_gap_ms=args.round_gap_ms,
                    frame_repeat=args.frame_repeat,
                    rx_spb=args.rx_spb,
                    rx_setup=args.rx_setup,
                    no_frame_timeout=args.no_frame_timeout,
                    rx_ant=args.rx_ant,
                    decode_workers=args.decode_workers,
                    payload_search_order=args.payload_search_order,
                    warmup_frames=args.warmup_frames,
                    warmup_repeats=args.warmup_repeats,
                    warmup_rounds=args.warmup_rounds,
                    tail_pad_samps=args.tail_pad_samps,
                    last_frame_extra_repeats=args.last_frame_extra_repeats,
                    first_frame_extra_repeats=args.first_frame_extra_repeats,
                    board_host=args.board_host,
                    board_user=args.board_user,
                    board_pass=args.board_pass,
                    board_port=args.board_port,
                    remote_build_dir=args.remote_build_dir,
                    remote_kill_after=args.remote_kill_after,
                )
                ota_result = {'ok': ota_ok, 'radio_metrics': radio_metrics}
                ok = ota_ok
                if ok:
                    print(f"       RX 收到: {len(received_ciphertext)} bytes")
            else:
                with tempfile.NamedTemporaryFile(suffix=".bin", delete=False,
                                                 prefix="e2e_rx_") as tmp_rx:
                    tmp_rx_path = tmp_rx.name

                ota_result = run_ota(tmp_enc_path, tmp_rx_path,
                                     tx_args=args.tx_args, rx_args=args.rx_args,
                                     tx_gain=args.tx_gain, rx_gain=args.rx_gain,
                                     rate=args.rate, freq=args.freq,
                                     repeat=args.repeat, rx_timeout=args.rx_timeout,
                                     ota_wait=args.ota_wait,
                                     start_pad_samps=args.start_pad_samps,
                                     round_gap_ms=args.round_gap_ms,
                                     frame_repeat=args.frame_repeat,
                                     rx_spb=args.rx_spb,
                                     rx_setup=args.rx_setup,
                                     no_frame_timeout=args.no_frame_timeout,
                                     rx_ant=args.rx_ant,
                                     decode_workers=args.decode_workers,
                                     payload_search_order=args.payload_search_order,
                                     warmup_frames=args.warmup_frames,
                                     warmup_repeats=args.warmup_repeats,
                                     warmup_rounds=args.warmup_rounds,
                                     tail_pad_samps=args.tail_pad_samps,
                                     frame_order=args.frame_order,
                                     last_frame_extra_repeats=args.last_frame_extra_repeats,
                                     first_frame_extra_repeats=args.first_frame_extra_repeats,
                                     board_host=args.board_host,
                                     board_user=args.board_user,
                                     board_pass=args.board_pass,
                                     board_port=args.board_port,
                                     remote_build_dir=args.remote_build_dir,
                                     remote_kill_after=args.remote_kill_after,
                                     ota_phy_mode=args.ota_phy_mode,
                                     arq_rev_freq=args.arq_rev_freq,
                                     arq_nack_tx_gain=args.arq_nack_tx_gain,
                                     arq_nack_rx_gain=args.arq_nack_rx_gain)
                ok = bool(ota_result.get("ok"))

                if ok:
                    with open(tmp_rx_path, "rb") as f:
                        received_ciphertext = f.read()
                    print(f"       RX 收到: {len(received_ciphertext)} bytes")

                if os.path.exists(tmp_rx_path):
                    os.unlink(tmp_rx_path)
                if os.path.exists(tmp_rx_path + '.rx.log'):
                    os.unlink(tmp_rx_path + '.rx.log')

            radio_metrics = dict(ota_result.get("radio_metrics") or {})

            os.unlink(tmp_enc_path)

            if not ok:
                print()
                print("[失败] USRP OTA 传输失败")
                sys.exit(1)

            enrich_channel_metrics(radio_metrics, wire_bytes, received_ciphertext)
            print_channel_metrics(radio_metrics)

        if not ok:
            print()
            print("[失败] USRP 传输失败")
            sys.exit(1)

        # 清理临时加密文件 (SIM/loopback 模式)
        if args.mode in ("sim", "loopback"):
            os.unlink(tmp_enc_path)

        # 4. ML-KEM 解密
        # OTA: 用 RX 实际收到的密文解密; SIM/loopback: 用原始密文
        #      (loopback --sim 在内存中对比，不会写 output 文件)
        received_ciphertext = (received_ciphertext
                               if args.mode == "ota"
                               else wire_bytes)
        print(f"[4/5] ML-KEM 解密 ({len(received_ciphertext)}B)...")
        t0 = time.perf_counter()
        try:
            decrypted = mlkem_decrypt(received_ciphertext, responder, suite)
        except Exception as e:
            print(f"       解密失败: {e}")
            if args.mode == "ota":
                print("       (OTA 传输中比特错误导致 AEAD 认证失败)")
            sys.exit(1)
        t_dec = (time.perf_counter() - t0) * 1000

        sha_dec = hashlib.sha256(decrypted).hexdigest()[:16]
        print(f"       解密: {t_dec:.1f}ms, SHA256: {sha_dec}...")

        # 5. 验证
        print(f"[5/5] 数据完整性验证...")
        if decrypted == plaintext:
            print(f"       SHA256 匹配: {sha_orig} == {sha_dec}")
        else:
            print(f"[失败] SHA256 不匹配: {sha_orig} != {sha_dec}")
            sys.exit(1)

        if args.output:
            write_plaintext_output(
                args.output,
                decrypted,
                input_is_npz=input_is_npz,
                raw_file_input=args.raw_file_input,
            )

        print()
        print("=" * 60)
        print("[PASS] 端到端闭环验证通过")
        print(f"  链路: latent → ML-KEM 加密 → USRP {args.mode} → ML-KEM 解密")
        print(f"  数据: {len(plaintext)}B, 密文: {len(wire_bytes)}B")
        print(f"  性能: 握手 {t_hs:.1f}ms + 加密 {t_enc:.1f}ms + "
              f"解密 {t_dec:.1f}ms")
        print(f"  完整性: SHA256 匹配")
        print("=" * 60)


if __name__ == "__main__":
    main()
