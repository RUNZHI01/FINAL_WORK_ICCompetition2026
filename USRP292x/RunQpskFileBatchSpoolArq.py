#!/usr/bin/env python3
"""Batch-spool USRP292x QPSK selective-ARQ runner.

This is the first step from "persistent device control" to "persistent data
flow": one RX capture covers a batch of TX bursts, then the capture is sliced
and decoded per image. The default decoder remains QpskFileLink.py; the C++
decoder can be selected explicitly after offline parity/performance checks.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / 'USRP292x' / 'payloads' / 'source_latent_wire_blob.bin'
DEFAULT_RUN_ROOT = PROJECT_ROOT / 'USRP292x' / 'qpsk_batch_spool_arq_runs'
QPSK_LINK = PROJECT_ROOT / 'USRP292x' / 'QpskFileLink.py'
QPSK_CPP_DECODE = PROJECT_ROOT / 'USRP292x' / 'QpskFileDecode'
RX_CONTROL = PROJECT_ROOT / 'USRP292x' / 'OtaRxControl.py'
TX_CONTROL = PROJECT_ROOT / 'USRP292x' / 'OtaTxControl.py'
SAMPLE_BYTES = 4
MAX_SAFE_BATCH_SIZE = 20
MAX_SAFE_DECODE_WORKERS = 2
HEAVY_ARTIFACT_SUFFIXES = ('.sc16',)
CHILD_THREAD_ENV = {
    'OMP_NUM_THREADS': '1',
    'OPENBLAS_NUM_THREADS': '1',
    'MKL_NUM_THREADS': '1',
    'NUMEXPR_NUM_THREADS': '1',
    'VECLIB_MAXIMUM_THREADS': '1',
}
FAST_ARQ_DEFAULTS = {
    'warmup_samples': 50_000,
    'tail_samples': 50_000,
    'batch_gap_samples': 50_000,
    'rx_tail_sec': 0.18,
    'slice_pre_sec': 0.05,
    'slice_post_sec': 0.08,
    'search_window_sec': 0.60,
}


@dataclass
class ImageState:
    index: int
    input_path: Path
    image_dir: Path
    summary_paths: list[Path] = field(default_factory=list)
    decoded_paths: list[Path] = field(default_factory=list)
    merge_summary: Path | None = None
    missing_chunks: list[int] = field(default_factory=list)
    passed: bool = False
    status: int = 0
    rounds: int = 0
    round_records: list[dict] = field(default_factory=list)


@dataclass
class ScheduledBurst:
    image: ImageState
    round_idx: int
    round_dir: Path
    tx_sc16: Path
    manifest: Path
    batch_offset_samples: int
    waveform_samples: int
    only_chunks: list[int]
    make_wall_sec: float = 0.0


@dataclass(frozen=True)
class RoundParams:
    warmup_samples: int
    tail_samples: int
    batch_gap_samples: int
    tx_delay_sec: float
    rx_tail_sec: float
    slice_pre_sec: float
    slice_post_sec: float
    search_window_sec: float


def env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == '':
        return None
    return int(raw)


def env_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == '':
        return None
    return float(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='USRP292x batch-spool QPSK selective ARQ runner.')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--input', type=Path, default=None)
    source.add_argument('--input-list', type=Path, default=None)
    source.add_argument('--input-dir', type=Path, default=None)
    parser.add_argument('--pattern', default='*.bin')
    parser.add_argument('--count', type=int, default=5)
    parser.add_argument('--cycle-inputs', action='store_true')
    parser.add_argument('--run-id', default=time.strftime('spool_%Y%m%d_%H%M%S'))
    parser.add_argument('--run-root', type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument('--max-arq-rounds', type=int, default=2)
    parser.add_argument('--stop-on-fail', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--fast-arq-profile',
        action='store_true',
        help='use shorter round1+ guard/slice/search defaults to reduce retransmission overhead without touching round0 parameters',
    )
    parser.add_argument(
        '--artifact-mode',
        choices=('minimal', 'full', 'board'),
        default=os.environ.get('USRP_ARTIFACT_MODE', 'minimal'),
        help='minimal deletes heavy sc16 intermediates after use; board also drops decoded/merged bins at the end; full keeps all evidence.',
    )

    parser.add_argument('--rate', type=float, default=float(os.environ.get('RATE', '5000000')))
    parser.add_argument('--chunk-bytes', type=int, default=int(os.environ.get('CHUNK_BYTES', '4096')))
    parser.add_argument('--amplitude', type=float, default=float(os.environ.get('AMPLITUDE', '3000')))
    parser.add_argument('--warmup-samples', type=int, default=int(os.environ.get('WARMUP_SAMPLES', '100000')))
    parser.add_argument('--tail-samples', type=int, default=int(os.environ.get('TAIL_SAMPLES', '100000')))
    parser.add_argument('--batch-gap-samples', type=int, default=int(os.environ.get('BATCH_GAP_SAMPLES', '100000')))
    parser.add_argument(
        '--arq-warmup-samples',
        type=int,
        default=env_int('ARQ_WARMUP_SAMPLES'),
        help='round1+ override; defaults to round0 warmup, or fast-arq-profile preset when enabled',
    )
    parser.add_argument(
        '--arq-tail-samples',
        type=int,
        default=env_int('ARQ_TAIL_SAMPLES'),
        help='round1+ override; defaults to round0 tail, or fast-arq-profile preset when enabled',
    )
    parser.add_argument(
        '--arq-batch-gap-samples',
        type=int,
        default=env_int('ARQ_BATCH_GAP_SAMPLES'),
        help='round1+ override; defaults to round0 batch gap, or fast-arq-profile preset when enabled',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=int(os.environ.get('BATCH_SIZE', '0')),
        help=f'max images per RF capture in each ARQ round; 0 means auto, capped at {MAX_SAFE_BATCH_SIZE}',
    )
    parser.add_argument('--frame-candidates', type=int, default=int(os.environ.get('FRAME_CANDIDATES', '64')))
    parser.add_argument('--decode-workers', type=int, default=int(os.environ.get('BATCH_DECODE_WORKERS', '1')))
    parser.add_argument(
        '--decode-backend',
        choices=('python', 'cpp'),
        default=os.environ.get('QPSK_DECODE_BACKEND', 'python'),
        help='python keeps the original QpskFileLink.py decoder; cpp uses QpskFileDecode.',
    )
    parser.add_argument(
        '--cpp-sync-mode',
        choices=('header', 'hybrid', 'sync'),
        default=os.environ.get('QPSK_CPP_SYNC_MODE', 'header'),
        help='C++ decoder mode: header is fastest and uses control-plane manifest metadata; hybrid is closer to Python.',
    )

    parser.add_argument('--rx-control-host', default=os.environ.get('RX_CONTROL_HOST', '127.0.0.1'))
    parser.add_argument('--rx-control-port', type=int, default=int(os.environ.get('RX_CONTROL_PORT', '29220')))
    parser.add_argument('--tx-control-host', default=os.environ.get('TX_CONTROL_HOST', '127.0.0.1'))
    parser.add_argument('--tx-control-port', type=int, default=int(os.environ.get('TX_CONTROL_PORT', '29221')))
    parser.add_argument(
        '--tx-file-path-prefix-from',
        default=os.environ.get('TX_FILE_PATH_PREFIX_FROM', ''),
        help='local path prefix to rewrite before sending TX file paths to a containerized TX server.',
    )
    parser.add_argument(
        '--tx-file-path-prefix-to',
        default=os.environ.get('TX_FILE_PATH_PREFIX_TO', ''),
        help='TX server-visible replacement prefix for --tx-file-path-prefix-from.',
    )
    parser.add_argument(
        '--rx-capture-mode',
        choices=('local', 'remote-pull', 'remote-decode'),
        default=os.environ.get('RX_CAPTURE_MODE', 'local'),
        help='local: batch_rx.sc16 directly lands on this host; remote-pull: RX host captures remotely, then TX host pulls the file back over SSH/SCP; remote-decode: RX host captures and decodes remotely, only results are pulled back.',
    )
    parser.add_argument(
        '--remote-rx-ssh-target',
        default=os.environ.get('REMOTE_RX_SSH_TARGET', ''),
        help='SSH/SCP target for remote RX host when --rx-capture-mode=remote-pull, e.g. user@100.x.y.z',
    )
    parser.add_argument(
        '--remote-rx-run-root',
        default=os.environ.get('REMOTE_RX_RUN_ROOT', '/tmp/usrp292x_remote_runs'),
        help='remote RX host directory used to store transient batch_rx.sc16 files before pulling them back.',
    )
    parser.add_argument(
        '--remote-rx-keep-files',
        action='store_true',
        default=os.environ.get('REMOTE_RX_KEEP_FILES', '0') == '1',
        help='keep remote batch_rx.sc16 files after successful pull; default is to delete them to reduce remote disk usage.',
    )
    parser.add_argument(
        '--remote-decode-bin',
        default=os.environ.get('REMOTE_DECODE_BIN', '/home/user/USRP292x/QpskFileDecode'),
        help='path to QpskFileDecode binary on the remote RX host (used by remote-decode mode).',
    )
    parser.add_argument('--tx-delay-sec', type=float, default=float(os.environ.get('PERSISTENT_RX_TX_DELAY', '0.05')))
    parser.add_argument('--rx-tail-sec', type=float, default=float(os.environ.get('BATCH_RX_TAIL_SEC', '0.30')))
    parser.add_argument('--slice-pre-sec', type=float, default=float(os.environ.get('BATCH_SLICE_PRE_SEC', '0.08')))
    parser.add_argument('--slice-post-sec', type=float, default=float(os.environ.get('BATCH_SLICE_POST_SEC', '0.12')))
    parser.add_argument('--search-window-sec', type=float, default=float(os.environ.get('BATCH_SEARCH_WINDOW_SEC', '0.80')))
    parser.add_argument(
        '--arq-rx-tail-sec',
        type=float,
        default=env_float('ARQ_RX_TAIL_SEC'),
        help='round1+ override; defaults to round0 rx-tail-sec, or fast-arq-profile preset when enabled',
    )
    parser.add_argument(
        '--arq-slice-pre-sec',
        type=float,
        default=env_float('ARQ_SLICE_PRE_SEC'),
        help='round1+ override; defaults to round0 slice-pre-sec, or fast-arq-profile preset when enabled',
    )
    parser.add_argument(
        '--arq-slice-post-sec',
        type=float,
        default=env_float('ARQ_SLICE_POST_SEC'),
        help='round1+ override; defaults to round0 slice-post-sec, or fast-arq-profile preset when enabled',
    )
    parser.add_argument(
        '--arq-search-window-sec',
        type=float,
        default=env_float('ARQ_SEARCH_WINDOW_SEC'),
        help='round1+ override; defaults to round0 search-window-sec, or fast-arq-profile preset when enabled',
    )
    parser.add_argument('--rx-timeout-sec', type=float, default=float(os.environ.get('BATCH_RX_TIMEOUT_SEC', '120')))
    parser.add_argument('--tx-timeout-sec', type=float, default=float(os.environ.get('BATCH_TX_TIMEOUT_SEC', '120')))
    args = parser.parse_args()
    if args.decode_workers < 1:
        raise RuntimeError('--decode-workers must be positive')
    if args.decode_workers > MAX_SAFE_DECODE_WORKERS:
        print(
            f'warning: --decode-workers={args.decode_workers} exceeds safe limit; '
            f'using {MAX_SAFE_DECODE_WORKERS}',
            file=sys.stderr,
        )
        args.decode_workers = MAX_SAFE_DECODE_WORKERS
    if args.batch_size < 0:
        raise RuntimeError('--batch-size must be non-negative')
    if args.batch_size > MAX_SAFE_BATCH_SIZE:
        print(
            f'warning: --batch-size={args.batch_size} exceeds safe limit; '
            f'using {MAX_SAFE_BATCH_SIZE}',
            file=sys.stderr,
        )
        args.batch_size = MAX_SAFE_BATCH_SIZE
    if args.batch_size == 0 and args.count > MAX_SAFE_BATCH_SIZE:
        args.batch_size = MAX_SAFE_BATCH_SIZE
    if args.decode_backend == 'cpp' and not QPSK_CPP_DECODE.is_file():
        raise RuntimeError(f'C++ decoder not built: {QPSK_CPP_DECODE}; run ./USRP292x/BuildOtaTools.sh first')
    if args.rx_capture_mode == 'remote-pull' and not args.remote_rx_ssh_target.strip():
        raise RuntimeError('--rx-capture-mode=remote-pull requires --remote-rx-ssh-target')
    if args.rx_capture_mode == 'remote-decode' and not args.remote_rx_ssh_target.strip():
        raise RuntimeError('--rx-capture-mode=remote-decode requires --remote-rx-ssh-target')
    return args


def resolve_round_value(
    base_value: int | float,
    override_value: int | float | None,
    *,
    round_idx: int,
    fast_key: str,
    fast_profile: bool,
) -> int | float:
    if round_idx == 0:
        return base_value
    if override_value is not None:
        return override_value
    if fast_profile:
        return FAST_ARQ_DEFAULTS[fast_key]
    return base_value


def resolve_round_params(args: argparse.Namespace, round_idx: int) -> RoundParams:
    return RoundParams(
        warmup_samples=int(resolve_round_value(
            args.warmup_samples,
            args.arq_warmup_samples,
            round_idx=round_idx,
            fast_key='warmup_samples',
            fast_profile=args.fast_arq_profile,
        )),
        tail_samples=int(resolve_round_value(
            args.tail_samples,
            args.arq_tail_samples,
            round_idx=round_idx,
            fast_key='tail_samples',
            fast_profile=args.fast_arq_profile,
        )),
        batch_gap_samples=int(resolve_round_value(
            args.batch_gap_samples,
            args.arq_batch_gap_samples,
            round_idx=round_idx,
            fast_key='batch_gap_samples',
            fast_profile=args.fast_arq_profile,
        )),
        tx_delay_sec=float(args.tx_delay_sec),
        rx_tail_sec=float(resolve_round_value(
            args.rx_tail_sec,
            args.arq_rx_tail_sec,
            round_idx=round_idx,
            fast_key='rx_tail_sec',
            fast_profile=args.fast_arq_profile,
        )),
        slice_pre_sec=float(resolve_round_value(
            args.slice_pre_sec,
            args.arq_slice_pre_sec,
            round_idx=round_idx,
            fast_key='slice_pre_sec',
            fast_profile=args.fast_arq_profile,
        )),
        slice_post_sec=float(resolve_round_value(
            args.slice_post_sec,
            args.arq_slice_post_sec,
            round_idx=round_idx,
            fast_key='slice_post_sec',
            fast_profile=args.fast_arq_profile,
        )),
        search_window_sec=float(resolve_round_value(
            args.search_window_sec,
            args.arq_search_window_sec,
            round_idx=round_idx,
            fast_key='search_window_sec',
            fast_profile=args.fast_arq_profile,
        )),
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def split_payload(payload: bytes, chunk_bytes: int) -> list[bytes]:
    return [payload[i:i + chunk_bytes] for i in range(0, len(payload), chunk_bytes)]


def count_bit_errors(left: bytes, right: bytes) -> int:
    return sum((a ^ b).bit_count() for a, b in zip(left, right))


def remove_file_if_present(path: Path) -> int:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return 0
    path.unlink()
    return size


def cleanup_heavy_files(paths: list[Path], *, enabled: bool) -> int:
    if not enabled:
        return 0
    removed = 0
    for path in paths:
        if path.suffix in HEAVY_ARTIFACT_SUFFIXES:
            removed += remove_file_if_present(path)
    return removed


def run_command(cmd: list[str], log_path: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    if log_path is None:
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            check=False,
        )
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('w', encoding='utf-8') as log:
            proc = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
    if check and proc.returncode != 0:
        raise RuntimeError(f'command failed ({proc.returncode}): {" ".join(cmd)}')
    return proc


def _send_tcp_command(host: str, port: int, line: str, timeout: float) -> str:
    """Send a single-line command to a persistent server and return the response.

    This replaces the previous approach of spawning ``python3 OtaRxControl.py``
    / ``OtaTxControl.py`` as a subprocess for every command.  Eliminating the
    Python interpreter startup (~100-150 ms each) saves ~450 ms per image.
    """
    import socket as _socket
    try:
        with _socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((line.rstrip() + '\n').encode('utf-8'))
            chunks: list[bytes] = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                if b'\n' in data:
                    break
        return b''.join(chunks).decode('utf-8', errors='replace').strip()
    except ConnectionRefusedError:
        return f'ERR_CONNECTION_REFUSED host={host} port={port}'
    except (_socket.timeout, OSError):
        return f'ERR_TIMEOUT host={host} port={port}'


def run_control_inline(
    host: str,
    port: int,
    line: str,
    log_path: Path,
    *,
    timeout: float = 10.0,
    check: bool = True,
) -> str:
    """In-process TCP control command — no subprocess."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    response = _send_tcp_command(host, port, line, timeout)
    log_path.write_text(response + '\n', encoding='utf-8')
    if check and not response.startswith('OK'):
        raise RuntimeError(f'control command failed: {line}\n{response}')
    return response


def translate_tx_control_file_path(path: Path, prefix_from: str, prefix_to: str) -> str:
    source_text = str(prefix_from or '').strip()
    target_text = str(prefix_to or '').strip()
    if not source_text or not target_text:
        return str(path)
    try:
        source_root = Path(source_text).resolve()
        path_resolved = Path(path).resolve()
        relative = path_resolved.relative_to(source_root)
    except (OSError, ValueError):
        return str(path)
    target_root = target_text.rstrip("/\\")
    return f"{target_root}/{relative.as_posix()}"


def run_control(cmd: list[str], log_path: Path, check: bool = True) -> str:
    """Legacy subprocess-based control — kept as fallback."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding='utf-8')
    if check and (proc.returncode != 0 or not proc.stdout.startswith('OK')):
        raise RuntimeError(f'control command failed ({proc.returncode}): {" ".join(cmd)}\n{proc.stdout}')
    return proc.stdout.strip()


def _ssh_base_args(timeout: int = 10, control_socket: str | None = None) -> list[str]:
    """Build SSH/SCP base args, using sshpass if SSHPASS env var is set."""
    if os.environ.get('OPENAMP_SSH_RUNNER', '').strip().lower() == 'docker':
        image = os.environ.get('OPENAMP_SSH_DOCKER_IMAGE', 'iccomp-usrp-tx:latest')
        return [
            'docker',
            'run',
            '--rm',
            '-i',
            '-e',
            'SSHPASS',
            image,
            'sshpass',
            '-e',
            'ssh',
            '-o',
            'StrictHostKeyChecking=no',
            '-o',
            'UserKnownHostsFile=/dev/null',
            '-o',
            'BatchMode=no',
            '-o',
            'ConnectTimeout={}'.format(timeout),
            '-o',
            'PreferredAuthentications=password,keyboard-interactive',
        ]
    sshpass = os.environ.get('SSHPASS')
    if sshpass is not None:
        args = ['sshpass', '-e', 'ssh', '-o', 'ConnectTimeout={}'.format(timeout)]
    else:
        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout={}'.format(timeout)]
    if control_socket:
        args += ['-o', 'ControlPath={}'.format(control_socket), '-o', 'ControlMaster=no']
    return args


def _scp_base_args(timeout: int = 10, control_socket: str | None = None) -> list[str]:
    sshpass = os.environ.get('SSHPASS')
    if sshpass is not None:
        args = ['sshpass', '-e', 'scp', '-o', 'ConnectTimeout={}'.format(timeout)]
    else:
        args = ['scp', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout={}'.format(timeout)]
    if control_socket:
        args += ['-o', 'ControlPath={}'.format(control_socket), '-o', 'ControlMaster=no']
    return args


def _ssh_shell_prefix(target: str, timeout: int = 10, control_socket: str | None = None) -> str:
    """Build shell SSH prefix for tar-pipe commands, using sshpass if SSHPASS is set."""
    sshpass = os.environ.get('SSHPASS')
    ctrl = ''
    if control_socket:
        ctrl = ' -o ControlPath={} -o ControlMaster=no'.format(shlex.quote(control_socket))
    if sshpass is not None:
        return f'sshpass -e ssh -o ConnectTimeout={timeout}{ctrl} {shlex.quote(target)}'
    return f'ssh -o BatchMode=yes -o ConnectTimeout={timeout}{ctrl} {shlex.quote(target)}'


def tar_directory_bytes(source_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for path in sorted(source_dir.rglob('*')):
            if not path.is_file():
                continue
            archive.add(path, arcname=path.relative_to(source_dir).as_posix())
    return buffer.getvalue()


def extract_tar_bytes(payload: bytes, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_root = output_dir.resolve()
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:*') as archive:
        members = archive.getmembers()
        for member in members:
            target = (output_dir / member.name).resolve()
            if output_root != target and output_root not in target.parents:
                raise RuntimeError(f'refusing to extract tar member outside destination: {member.name}')
        archive.extractall(output_dir, members=members)


def push_directory_to_remote(
    source_dir: Path,
    *,
    target: str,
    remote_dir: str,
    log_path: Path,
    control_socket: str | None,
    timeout: int = 30,
) -> None:
    payload = tar_directory_bytes(source_dir)
    remote_cmd = f'mkdir -p {shlex.quote(remote_dir)} && cd {shlex.quote(remote_dir)} && tar xf -'
    cmd = _ssh_base_args(timeout=timeout, control_socket=control_socket) + [target, remote_cmd]
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text((proc.stdout or b'').decode('utf-8', errors='replace'), encoding='utf-8')
    if proc.returncode != 0:
        raise RuntimeError(f'remote tar push failed ({proc.returncode}): {" ".join(cmd)}')


def pull_remote_directory_to_local(
    *,
    target: str,
    remote_dir: str,
    output_dir: Path,
    log_path: Path,
    control_socket: str | None,
    timeout: int = 30,
) -> None:
    remote_cmd = f'cd {shlex.quote(remote_dir)} && tar cf - .'
    cmd = _ssh_base_args(timeout=timeout, control_socket=control_socket) + [target, remote_cmd]
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_text = (proc.stderr or b'').decode('utf-8', errors='replace')
    log_path.write_text(log_text, encoding='utf-8')
    if proc.returncode != 0:
        raise RuntimeError(f'remote tar pull failed ({proc.returncode}): {" ".join(cmd)}\n{log_text}')
    extract_tar_bytes(proc.stdout or b'', output_dir)


def _ssh_control_socket_path() -> str:
    """Return a deterministic path for the SSH ControlMaster socket."""
    return '/tmp/usrp_ssh_ctrl_{}'.format(os.getpid())


def _ssh_start_control_master(target: str) -> subprocess.Popen | None:
    """Start a persistent SSH ControlMaster connection to the remote target.

    Returns the background Popen holding the master connection, or None if
    the target is empty. The master authenticates once (including sshpass if
    SSHPASS is set); subsequent connections via the control socket skip the
    full SSH handshake.
    """
    if not target or os.environ.get('OPENAMP_SSH_RUNNER', '').strip().lower() == 'docker':
        return None
    sock = _ssh_control_socket_path()
    # Clean up any stale socket from a previous run with the same PID.
    subprocess.run(
        ['ssh', '-O', 'exit', '-S', sock, target],
        capture_output=True,
        timeout=5,
    )
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass
    # Build the master command. sshpass is needed here for password auth;
    # subsequent multiplexed connections reuse the authenticated master.
    base = _ssh_base_args(timeout=15)
    cmd = base + [
        '-o', 'ControlPath={}'.format(sock),
        '-o', 'ControlMaster=yes',
        '-o', 'ControlPersist=300',
        '-o', 'ServerAliveInterval=30',
        '-N',
        target,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Wait for the socket file to appear (up to 10 seconds for slow ARM targets).
    for _ in range(100):
        if os.path.exists(sock):
            return proc
        time.sleep(0.1)
    # Socket did not appear — master likely failed; clean up.
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    return None


def _ssh_stop_control_master(target: str, proc: subprocess.Popen | None) -> None:
    """Shut down the SSH ControlMaster gracefully."""
    if proc is None:
        return
    sock = _ssh_control_socket_path()
    subprocess.run(
        ['ssh', '-O', 'exit', '-S', sock, target],
        capture_output=True,
        timeout=5,
    )
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    try:
        os.unlink(sock)
    except FileNotFoundError:
        pass


def run_external_command(
    cmd: list[str],
    log_path: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding='utf-8')
    if check and proc.returncode != 0:
        raise RuntimeError(f'command failed ({proc.returncode}): {" ".join(cmd)}\n{proc.stdout}')
    return proc


def build_remote_batch_rx_path(args: argparse.Namespace, *, round_idx: int, batch_idx: int) -> str:
    return (
        f'{args.remote_rx_run_root.rstrip("/")}/'
        f'{args.run_id}/round{round_idx}/batch_{batch_idx:04d}/batch_rx.sc16'
    )


def pull_remote_batch_rx(
    args: argparse.Namespace,
    remote_path: str,
    local_path: Path,
    batch_dir: Path,
) -> dict[str, object]:
    started = time.monotonic()
    ctrl = getattr(args, 'ssh_control_socket', None)
    scp_log = batch_dir / 'rx_pull.log'
    local_path.parent.mkdir(parents=True, exist_ok=True)
    remote_spec = f'{args.remote_rx_ssh_target}:{remote_path}'
    run_external_command(
        _scp_base_args(control_socket=ctrl) + [remote_spec, str(local_path)],
        scp_log,
        check=True,
    )
    if not local_path.is_file():
        raise RuntimeError(f'remote RX pull completed but local file is missing: {local_path}')
    cleanup_log = batch_dir / 'rx_remote_cleanup.log'
    cleanup_performed = False
    if not args.remote_rx_keep_files:
        remote_cmd = 'bash -lc ' + shlex.quote(f'rm -f {shlex.quote(remote_path)}')
        run_external_command(
            _ssh_base_args(control_socket=ctrl) + [args.remote_rx_ssh_target, remote_cmd],
            cleanup_log,
            check=True,
        )
        cleanup_performed = True
    return {
        'remote_path': remote_path,
        'local_path': str(local_path),
        'pull_wall_sec': time.monotonic() - started,
        'cleanup_performed': cleanup_performed,
    }


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


_qpsk_link_module = None


def _get_qpsk_link():
    """Lazy-import QpskFileLink module to avoid numpy startup cost at process launch."""
    global _qpsk_link_module
    if _qpsk_link_module is None:
        import importlib.util
        os.environ.update(CHILD_THREAD_ENV)
        spec = importlib.util.spec_from_file_location('QpskFileLink', str(QPSK_LINK))
        _qpsk_link_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_qpsk_link_module)
    return _qpsk_link_module


def make_waveform(
    args: argparse.Namespace,
    image: ImageState,
    round_idx: int,
    only_chunks: list[int],
    round_params: RoundParams,
) -> ScheduledBurst:
    started = time.monotonic()
    round_dir = image.image_dir / f'round{round_idx}'
    tx_sc16 = round_dir / 'tx_qpsk.sc16'
    manifest = round_dir / 'manifest.json'
    only_csv = ','.join(str(item) for item in only_chunks)
    qpsk = _get_qpsk_link()
    ns = argparse.Namespace(
        input=image.input_path,
        out_sc16=tx_sc16,
        manifest=manifest,
        rate=args.rate,
        sps=qpsk.DEFAULT_SPS,
        chunk_bytes=args.chunk_bytes,
        amplitude=args.amplitude,
        gap_samples=qpsk.DEFAULT_GAP_SAMPLES,
        warmup_samples=round_params.warmup_samples,
        tail_samples=round_params.tail_samples,
        only_chunks=only_csv,
    )
    qpsk.make_waveform(ns)
    make_wall_sec = time.monotonic() - started
    data = read_json(manifest)
    return ScheduledBurst(
        image=image,
        round_idx=round_idx,
        round_dir=round_dir,
        tx_sc16=tx_sc16,
        manifest=manifest,
        batch_offset_samples=0,
        waveform_samples=int(data['waveform_samples']),
        only_chunks=only_chunks,
        make_wall_sec=make_wall_sec,
    )


def copy_file(src: Path, dst_file) -> None:
    with src.open('rb') as f:
        shutil.copyfileobj(f, dst_file, length=1024 * 1024)


def write_zero_samples(dst_file, samples: int) -> None:
    if samples <= 0:
        return
    block = bytes(min(samples, 1024 * 1024 // SAMPLE_BYTES) * SAMPLE_BYTES)
    left = samples
    while left > 0:
        n = min(left, len(block) // SAMPLE_BYTES)
        dst_file.write(block[:n * SAMPLE_BYTES])
        left -= n


def build_batch_tx(
    run_dir: Path,
    round_idx: int,
    batch_idx: int,
    bursts: list[ScheduledBurst],
    gap_samples: int,
) -> tuple[Path, int]:
    batch_tx = run_dir / f'round{round_idx}' / f'batch_{batch_idx:04d}' / 'batch_tx.sc16'
    batch_tx.parent.mkdir(parents=True, exist_ok=True)
    offset = 0
    with batch_tx.open('wb') as out:
        for pos, burst in enumerate(bursts):
            burst.batch_offset_samples = offset
            copy_file(burst.tx_sc16, out)
            offset += burst.waveform_samples
            if pos != len(bursts) - 1 and gap_samples > 0:
                write_zero_samples(out, gap_samples)
                offset += gap_samples
    return batch_tx, offset


def sample_count(path: Path) -> int:
    return path.stat().st_size // SAMPLE_BYTES


def copy_sample_range(src: Path, dst: Path, start_sample: int, end_sample: int) -> None:
    start_sample = max(0, start_sample)
    end_sample = max(start_sample, end_sample)
    dst.parent.mkdir(parents=True, exist_ok=True)
    left_bytes = (end_sample - start_sample) * SAMPLE_BYTES
    with src.open('rb') as f, dst.open('wb') as out:
        f.seek(start_sample * SAMPLE_BYTES)
        while left_bytes > 0:
            chunk = f.read(min(left_bytes, 1024 * 1024))
            if not chunk:
                break
            out.write(chunk)
            left_bytes -= len(chunk)


def decode_slice(args: argparse.Namespace, batch_rx: Path, burst: ScheduledBurst, round_params: RoundParams) -> dict:
    started = time.monotonic()
    image_start_sec = round_params.tx_delay_sec + burst.batch_offset_samples / args.rate
    slice_start_sec = max(0.0, image_start_sec - round_params.slice_pre_sec)
    slice_end_sec = image_start_sec + burst.waveform_samples / args.rate + round_params.slice_post_sec
    rx_samples = sample_count(batch_rx)
    start_sample = int(round(slice_start_sec * args.rate))
    end_sample = min(rx_samples, int(round(slice_end_sec * args.rate)))
    rx_length_samples = max(0, end_sample - start_sample)
    rx_decode_input = batch_rx
    slice_copy_wall_sec = 0.0

    image_start_in_slice = image_start_sec - (start_sample / args.rate)
    search_start = max(0.0, image_start_in_slice)
    search_end = search_start + round_params.search_window_sec
    decoded = burst.round_dir / 'decoded_wire_blob.bin'
    summary = burst.round_dir / 'decode_summary.json'
    if args.decode_backend == 'cpp':
        cmd = [
            str(QPSK_CPP_DECODE),
            'decode',
            '--sync-mode',
            args.cpp_sync_mode,
            '--rx-sc16',
            str(rx_decode_input),
            '--rx-offset-samples',
            str(start_sample),
            '--rx-length-samples',
            str(rx_length_samples),
            '--manifest',
            str(burst.manifest),
            '--reference',
            str(burst.image.input_path),
            '--out-bin',
            str(decoded),
            '--summary-json',
            str(summary),
            '--search-start-sec',
            f'{search_start:.6f}',
            '--search-end-sec',
            f'{search_end:.6f}',
            '--frame-candidates',
            str(args.frame_candidates),
        ]
    else:
        cmd = [
            sys.executable,
            str(QPSK_LINK),
            'decode',
            '--rx-sc16',
            str(rx_decode_input),
            '--rx-offset-samples',
            str(start_sample),
            '--rx-length-samples',
            str(rx_length_samples),
            '--manifest',
            str(burst.manifest),
            '--reference',
            str(burst.image.input_path),
            '--out-bin',
            str(decoded),
            '--summary-json',
            str(summary),
            '--search-start-sec',
            f'{search_start:.6f}',
            '--search-end-sec',
            f'{search_end:.6f}',
            '--frame-candidates',
            str(args.frame_candidates),
        ]
    decode_started = time.monotonic()
    proc = run_command(cmd, burst.round_dir / 'decode.log', check=False)
    decode_command_wall_sec = time.monotonic() - decode_started
    burst.image.summary_paths.append(summary)
    burst.image.decoded_paths.append(decoded)
    burst.image.rounds += 1
    record = {
        'round': burst.round_idx,
        'only_chunks': burst.only_chunks,
        'batch_offset_samples': burst.batch_offset_samples,
        'waveform_samples': burst.waveform_samples,
        'slice_start_sample': start_sample,
        'slice_end_sample': end_sample,
        'slice_length_samples': rx_length_samples,
        'slice_source': str(rx_decode_input),
        'search_start_sec': search_start,
        'search_end_sec': search_end,
        'round_params': {
            'warmup_samples': round_params.warmup_samples,
            'tail_samples': round_params.tail_samples,
            'batch_gap_samples': round_params.batch_gap_samples,
            'tx_delay_sec': round_params.tx_delay_sec,
            'rx_tail_sec': round_params.rx_tail_sec,
            'slice_pre_sec': round_params.slice_pre_sec,
            'slice_post_sec': round_params.slice_post_sec,
            'search_window_sec': round_params.search_window_sec,
        },
        'decode_backend': args.decode_backend,
        'cpp_sync_mode': args.cpp_sync_mode if args.decode_backend == 'cpp' else '',
        'decode_status': proc.returncode,
        'make_wall_sec': burst.make_wall_sec,
        'slice_copy_wall_sec': slice_copy_wall_sec,
        'decode_command_wall_sec': decode_command_wall_sec,
        'decode_total_wall_sec': time.monotonic() - started,
    }
    if summary.is_file():
        data = read_json(summary)
        record.update({
            'crc_ok': data.get('crc_ok'),
            'frames_transmitted': data.get('frames_transmitted'),
            'missing_chunks': data.get('missing_chunks'),
            'detected_airtime_ms': data.get('detected_airtime_ms'),
            'effective_payload_mbps': data.get('effective_payload_mbps'),
        })
    record['cleanup_removed_bytes'] = 0
    burst.image.round_records.append(record)
    return record


def _remote_decode_params(
    args: argparse.Namespace,
    burst: ScheduledBurst,
    round_params: RoundParams,
    batch_total_samples: int,
) -> dict:
    """Compute decode parameters for one burst."""
    image_start_sec = round_params.tx_delay_sec + burst.batch_offset_samples / args.rate
    slice_start_sec = max(0.0, image_start_sec - round_params.slice_pre_sec)
    slice_end_sec = image_start_sec + burst.waveform_samples / args.rate + round_params.slice_post_sec
    start_sample = int(round(slice_start_sec * args.rate))
    end_sample_offset = min(batch_total_samples, int(round(slice_end_sec * args.rate))) if batch_total_samples > 0 else int(round(slice_end_sec * args.rate))
    rx_length_samples = max(0, end_sample_offset - start_sample)
    image_start_in_slice = image_start_sec - (start_sample / args.rate)
    search_start = max(0.0, image_start_in_slice)
    search_end = search_start + round_params.search_window_sec
    return {
        'start_sample': start_sample,
        'end_sample_offset': end_sample_offset,
        'rx_length_samples': rx_length_samples,
        'search_start': search_start,
        'search_end': search_end,
    }


def decode_batch_remote(
    args: argparse.Namespace,
    remote_rx_sc16: str,
    bursts: list[ScheduledBurst],
    round_params: RoundParams,
    batch_total_samples: int,
) -> list[dict]:
    """Decode entire batch on remote RX host — batch-level I/O to minimize SSH round-trips.

    Instead of per-burst SSH (7 connections × N bursts), does:
      1 SSH mkdir  +  1 tar-pipe SCP push  +  1 SSH decode-all  +  1 tar-pipe SCP pull  +  1 SSH cleanup
    """
    import shlex as _shlex
    import shutil
    target = args.remote_rx_ssh_target
    ctrl = getattr(args, 'ssh_control_socket', None)
    remote_decode_bin = args.remote_decode_bin
    remote_batch_dir = os.path.dirname(remote_rx_sc16)
    remote_base = f'{args.remote_rx_run_root.rstrip("/")}/_decode_b{bursts[0].round_idx}'

    # Combined SSH #0+#1: stat remote file size AND mkdir all remote dirs in ONE SSH call.
    actual_total_samples = batch_total_samples
    bp_list = []
    for i, burst in enumerate(bursts):
        dp = _remote_decode_params(args, burst, round_params, actual_total_samples)
        bp_list.append({
            'burst': burst,
            'remote_work': f'{remote_base}/{i:03d}',
            'local_summary': burst.round_dir / 'decode_summary.json',
            'local_decoded': burst.round_dir / 'decoded_wire_blob.bin',
            **dp,
        })
    scp_to_started = time.monotonic()
    all_dirs = [bp['remote_work'] for bp in bp_list] + [remote_batch_dir]
    combined_cmd = (
        f'stat -c %s {_shlex.quote(remote_rx_sc16)} 2>/dev/null || true; '
        f'mkdir -p {" ".join(_shlex.quote(d) for d in all_dirs)}'
    )
    combined_proc = run_external_command(
        _ssh_base_args(control_socket=ctrl) + [target, combined_cmd],
        bursts[0].round_dir / 'remote_stat_mkdir.log',
        check=False,
    )
    if combined_proc.returncode == 0 and combined_proc.stdout:
        for line in combined_proc.stdout.strip().splitlines():
            line = line.strip()
            if line.isdigit():
                try:
                    actual_total_samples = int(line) // 4
                except (ValueError, ZeroDivisionError):
                    pass
                break
    # Re-compute decode params with actual total samples if it changed.
    if actual_total_samples != batch_total_samples:
        for i, burst in enumerate(bursts):
            dp = _remote_decode_params(args, burst, round_params, actual_total_samples)
            bp_list[i].update(dp)

    # 2. tar-pipe all inputs (manifest+reference) to remote in ONE pipe
    local_staging = bursts[0].round_dir / '_remote_staging'
    local_staging.mkdir(parents=True, exist_ok=True)
    for i, bp in enumerate(bp_list):
        sub = local_staging / f'{i:03d}'
        sub.mkdir(exist_ok=True)
        shutil.copy2(str(bp['burst'].manifest), str(sub / 'manifest.json'))
        shutil.copy2(str(bp['burst'].image.input_path), str(sub / 'reference.bin'))
    push_directory_to_remote(
        local_staging,
        target=target,
        remote_dir=remote_base,
        log_path=bursts[0].round_dir / 'remote_push.log',
        control_socket=ctrl,
        timeout=30,
    )
    scp_to_wall_sec = time.monotonic() - scp_to_started

    # 3. Run ALL decodes in ONE SSH session (respect decode_workers limit for remote CPU)
    decode_started = time.monotonic()
    remote_workers = min(max(1, args.decode_workers), len(bp_list))
    decode_lines = []
    for i, bp in enumerate(bp_list):
        decode_cmd = (
            f'{_shlex.quote(remote_decode_bin)} decode'
            f' --sync-mode {_shlex.quote(args.cpp_sync_mode)}'
            f' --rx-sc16 {_shlex.quote(remote_rx_sc16)}'
            f' --rx-offset-samples {bp["start_sample"]}'
            f' --rx-length-samples {bp["rx_length_samples"]}'
            f' --manifest {_shlex.quote(bp["remote_work"] + "/manifest.json")}'
            f' --reference {_shlex.quote(bp["remote_work"] + "/reference.bin")}'
            f' --out-bin {_shlex.quote(bp["remote_work"] + "/decoded_wire_blob.bin")}'
            f' --summary-json {_shlex.quote(bp["remote_work"] + "/decode_summary.json")}'
            f' --search-start-sec {bp["search_start"]:.6f}'
            f' --search-end-sec {bp["search_end"]:.6f}'
            f' --frame-candidates {args.frame_candidates}'
        )
        decode_lines.append(f'( {decode_cmd}; rc=$?; echo "EXIT:{i}:$rc" )')

    # Split the batch into balanced lanes. With batch=6 and workers=2 this is 3+3.
    all_exit_codes = [1] * len(bp_list)
    lane_size = max(1, (len(decode_lines) + remote_workers - 1) // remote_workers)
    lane_scripts = []
    for lane_start in range(0, len(decode_lines), lane_size):
        lane = decode_lines[lane_start:lane_start + lane_size]
        lane_scripts.append('( ' + '; '.join(lane) + ' )')
    parallel_script = ''.join(f'{lane} & ' for lane in lane_scripts) + 'wait'
    proc = run_external_command(
        _ssh_base_args(timeout=60, control_socket=ctrl) + [target, parallel_script],
        bursts[0].round_dir / 'remote_decode.log',
        check=False,
    )
    for line in (proc.stdout or '').splitlines():
        line = line.strip()
        if line.startswith('EXIT:'):
            parts = line.split(':', 2)
            if len(parts) == 3:
                try:
                    idx = int(parts[1])
                    rc = int(parts[2])
                except ValueError:
                    continue
                if 0 <= idx < len(all_exit_codes):
                    all_exit_codes[idx] = rc
    decode_wall_sec = time.monotonic() - decode_started

    # 4. tar-pipe pull all results back in ONE pipe
    scp_from_started = time.monotonic()
    pull_remote_directory_to_local(
        target=target,
        remote_dir=remote_base,
        output_dir=local_staging,
        log_path=bursts[0].round_dir / 'remote_pull.log',
        control_socket=ctrl,
        timeout=30,
    )
    for i, bp in enumerate(bp_list):
        bp['burst'].round_dir.mkdir(parents=True, exist_ok=True)
        src = local_staging / f'{i:03d}'
        s = src / 'decode_summary.json'
        d = src / 'decoded_wire_blob.bin'
        if s.exists():
            shutil.copy2(str(s), str(bp['local_summary']))
        if d.exists():
            shutil.copy2(str(d), str(bp['local_decoded']))
    scp_from_wall_sec = time.monotonic() - scp_from_started

    # 5. Cleanup remote + local staging (non-critical, best-effort)
    run_external_command(
        _ssh_base_args(control_socket=ctrl) + [target,
         f'rm -rf {_shlex.quote(remote_base)}'],
        bursts[0].round_dir / 'remote_cleanup.log',
        check=False,
    )
    shutil.rmtree(str(local_staging), ignore_errors=True)

    # 6. Build per-burst records
    n = len(bp_list)
    records = []
    for i, bp in enumerate(bp_list):
        burst = bp['burst']
        summary = bp['local_summary']
        burst.image.summary_paths.append(summary)
        burst.image.decoded_paths.append(bp['local_decoded'])
        burst.image.rounds += 1
        rc = all_exit_codes[i] if i < len(all_exit_codes) else 1
        record = {
            'round': burst.round_idx,
            'only_chunks': burst.only_chunks,
            'batch_offset_samples': burst.batch_offset_samples,
            'waveform_samples': burst.waveform_samples,
            'slice_start_sample': bp['start_sample'],
            'slice_end_sample': bp['end_sample_offset'],
            'slice_length_samples': bp['rx_length_samples'],
            'slice_source': remote_rx_sc16,
            'search_start_sec': bp['search_start'],
            'search_end_sec': bp['search_end'],
            'round_params': {
                'warmup_samples': round_params.warmup_samples,
                'tail_samples': round_params.tail_samples,
                'batch_gap_samples': round_params.batch_gap_samples,
                'tx_delay_sec': round_params.tx_delay_sec,
                'rx_tail_sec': round_params.rx_tail_sec,
                'slice_pre_sec': round_params.slice_pre_sec,
                'slice_post_sec': round_params.slice_post_sec,
                'search_window_sec': round_params.search_window_sec,
            },
            'decode_backend': args.decode_backend,
            'cpp_sync_mode': args.cpp_sync_mode if args.decode_backend == 'cpp' else '',
            'decode_status': rc,
            'make_wall_sec': burst.make_wall_sec,
            'slice_copy_wall_sec': 0.0,
            'decode_command_wall_sec': decode_wall_sec / n,
            'decode_total_wall_sec': 0.0,
            'remote_decode': {
                'scp_to_wall_sec': scp_to_wall_sec / n,
                'remote_decode_wall_sec': decode_wall_sec / n,
                'scp_from_wall_sec': scp_from_wall_sec / n,
                'remote_decode_bin': remote_decode_bin,
            },
        }
        if summary.is_file():
            data = read_json(summary)
            record.update({
                'crc_ok': data.get('crc_ok'),
                'frames_transmitted': data.get('frames_transmitted'),
                'missing_chunks': data.get('missing_chunks'),
                'detected_airtime_ms': data.get('detected_airtime_ms'),
                'effective_payload_mbps': data.get('effective_payload_mbps'),
            })
        record['cleanup_removed_bytes'] = 0
        burst.image.round_records.append(record)
        records.append(record)
    return records


def merge_image(args: argparse.Namespace, image: ImageState, round_idx: int) -> float:
    started = time.monotonic()
    merge_summary = image.image_dir / f'merge_round{round_idx}.json'
    merged_bin = image.image_dir / f'merged_round{round_idx}.bin'
    reference = image.input_path.read_bytes()
    source_chunks = split_payload(reference, args.chunk_bytes)
    merged_by_seq: dict[int, bytes] = {}
    accepted_by_round: list[dict] = []

    for record_idx, (summary_path, decoded_path) in enumerate(zip(image.summary_paths, image.decoded_paths)):
        summary = read_json(summary_path)
        decoded = decoded_path.read_bytes()
        accepted: list[int] = []
        rejected: list[dict] = []

        for item in summary.get('chunk_results', []):
            if not item.get('crc_ok', False):
                continue
            seq = int(item.get('protocol_seq', item.get('chunk', -1)))
            if seq < 0 or seq >= len(source_chunks):
                rejected.append({'seq': seq, 'reason': 'seq out of range'})
                continue
            payload_len = int(item.get('protocol_payload_len') or len(source_chunks[seq]))
            start = seq * args.chunk_bytes
            chunk = decoded[start:start + payload_len]
            if len(chunk) != payload_len:
                rejected.append({'seq': seq, 'reason': 'decoded chunk truncated'})
                continue
            protocol_crc32 = item.get('protocol_crc32')
            if protocol_crc32 is not None and (zlib.crc32(chunk) & 0xFFFFFFFF) != int(protocol_crc32):
                rejected.append({'seq': seq, 'reason': 'crc mismatch after slicing decoded-bin'})
                continue
            if seq not in merged_by_seq:
                merged_by_seq[seq] = chunk
            accepted.append(seq)

        accepted_by_round.append({
            'round': record_idx,
            'summary_json': str(summary_path),
            'decoded_bin': str(decoded_path),
            'accepted_chunks': sorted(set(accepted)),
            'rejected_chunks': rejected,
        })

    merged_parts = [merged_by_seq.get(seq, bytes(len(chunk))) for seq, chunk in enumerate(source_chunks)]
    merged = b''.join(merged_parts)
    merged_bin.parent.mkdir(parents=True, exist_ok=True)
    merged_bin.write_bytes(merged)

    crc_ok_indices = sorted(merged_by_seq)
    missing_chunks = [seq for seq in range(len(source_chunks)) if seq not in merged_by_seq]
    byte_errors = sum(a != b for a, b in zip(merged, reference))
    bit_errors = count_bit_errors(merged, reference)
    exact = byte_errors == 0 and not missing_chunks and len(merged) == len(reference)
    summary = {
        'reference': str(image.input_path),
        'out_bin': str(merged_bin),
        'total_chunks': len(source_chunks),
        'crc_ok_indices': crc_ok_indices,
        'missing_chunks': missing_chunks,
        'byte_errors': byte_errors,
        'bit_errors': bit_errors,
        'exact': exact,
        'sha256': hashlib.sha256(merged).hexdigest(),
        'reference_sha256': hashlib.sha256(reference).hexdigest(),
        'rounds': accepted_by_round,
    }
    write_json(merge_summary, summary)

    image.status = 0 if exact else 2
    image.merge_summary = merge_summary
    image.missing_chunks = [int(item) for item in missing_chunks]
    image.passed = bool(exact)
    return time.monotonic() - started


def cleanup_board_small_bins(images: list[ImageState]) -> int:
    removed = 0
    for image in images:
        for path in image.decoded_paths:
            removed += remove_file_if_present(path)
        for path in image.image_dir.glob('merged_round*.bin'):
            removed += remove_file_if_present(path)
    return removed


def collect_result(image: ImageState) -> dict:
    merge = read_json(image.merge_summary) if image.merge_summary and image.merge_summary.is_file() else {}
    payload_airtime = 0.0
    compared_bytes = 0
    for summary_path in image.summary_paths:
        if summary_path.is_file():
            summary = read_json(summary_path)
            payload_airtime += float(summary.get('detected_airtime_ms', 0.0))
            compared_bytes += int(summary.get('compared_transmitted_bytes', 0))
    return {
        'index': image.index,
        'input': str(image.input_path),
        'input_sha256': sha256_file(image.input_path),
        'run_dir': str(image.image_dir),
        'status': image.status,
        'pass': image.passed,
        'rounds': image.rounds,
        'missing_chunks': image.missing_chunks,
        'byte_errors': int(merge.get('byte_errors', -1)),
        'bit_errors': int(merge.get('bit_errors', -1)),
        'merge_summary': str(image.merge_summary) if image.merge_summary else '',
        'payload_airtime_ms': payload_airtime,
        'compared_transmitted_bytes': compared_bytes,
        'round_records': image.round_records,
        'merge': {
            'exact': merge.get('exact', False),
            'crc_ok_indices': merge.get('crc_ok_indices', []),
            'sha256': merge.get('sha256', ''),
            'reference_sha256': merge.get('reference_sha256', ''),
        },
    }


def aggregate_result_metrics(results: list[dict], elapsed_sec: float) -> dict:
    completed = len(results)
    if completed == 0:
        return {
            'per_image_sec': 0.0,
            'payload_airtime_ms_sum': 0.0,
            'payload_airtime_ms_mean': 0.0,
            'compared_transmitted_bytes_sum': 0,
            'compared_transmitted_bytes_mean': 0.0,
            'round_record_count': 0,
            'decode_total_wall_sec_sum': 0.0,
            'decode_total_wall_sec_mean': 0.0,
            'decode_command_wall_sec_sum': 0.0,
            'decode_command_wall_sec_mean': 0.0,
            'merge_wall_sec_sum': 0.0,
            'merge_wall_sec_mean': 0.0,
            'estimated_non_airtime_non_decode_non_merge_wall_sec_mean': 0.0,
        }

    payload_airtime_ms_sum = 0.0
    compared_transmitted_bytes_sum = 0
    round_record_count = 0
    decode_total_wall_sec_sum = 0.0
    decode_command_wall_sec_sum = 0.0
    merge_wall_sec_sum = 0.0

    for item in results:
        payload_airtime_ms_sum += float(item.get('payload_airtime_ms', 0.0) or 0.0)
        compared_transmitted_bytes_sum += int(item.get('compared_transmitted_bytes', 0) or 0)
        for record in item.get('round_records', []):
            round_record_count += 1
            decode_total_wall_sec_sum += float(record.get('decode_total_wall_sec', 0.0) or 0.0)
            decode_command_wall_sec_sum += float(record.get('decode_command_wall_sec', 0.0) or 0.0)
            merge_wall_sec_sum += float(record.get('merge_wall_sec', 0.0) or 0.0)

    per_image_sec = elapsed_sec / completed
    payload_airtime_ms_mean = payload_airtime_ms_sum / completed
    decode_total_wall_sec_mean = decode_total_wall_sec_sum / completed
    merge_wall_sec_mean = merge_wall_sec_sum / completed
    return {
        'per_image_sec': per_image_sec,
        'payload_airtime_ms_sum': payload_airtime_ms_sum,
        'payload_airtime_ms_mean': payload_airtime_ms_mean,
        'compared_transmitted_bytes_sum': compared_transmitted_bytes_sum,
        'compared_transmitted_bytes_mean': compared_transmitted_bytes_sum / completed,
        'round_record_count': round_record_count,
        'decode_total_wall_sec_sum': decode_total_wall_sec_sum,
        'decode_total_wall_sec_mean': decode_total_wall_sec_mean,
        'decode_command_wall_sec_sum': decode_command_wall_sec_sum,
        'decode_command_wall_sec_mean': decode_command_wall_sec_sum / completed,
        'merge_wall_sec_sum': merge_wall_sec_sum,
        'merge_wall_sec_mean': merge_wall_sec_mean,
        'estimated_non_airtime_non_decode_non_merge_wall_sec_mean': (
            per_image_sec - payload_airtime_ms_mean / 1000.0 - decode_total_wall_sec_mean - merge_wall_sec_mean
        ),
    }


def write_summary(run_dir: Path, summary: dict, images: list[ImageState], started: float) -> None:
    results = [collect_result(image) for image in images]
    completed = sum(
        1
        for image, item in zip(images, results)
        if image.rounds > 0 or bool(item.get('merge_summary'))
    )
    passed = sum(1 for item in results if item.get('pass'))
    elapsed_sec = time.time() - started
    target_count = int(summary.get('target_count') or len(results))
    summary.update({
        'results': results,
        'completed_count': completed,
        'pass_count': passed,
        'fail_count': max(0, completed - passed),
        'pending_count': max(0, target_count - completed),
        'all_pass': completed == target_count and passed == target_count,
        'elapsed_sec': elapsed_sec,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    })
    summary.update(aggregate_result_metrics(results, elapsed_sec))
    write_json(run_dir / 'batch_spool_summary.json', summary)


def run_round(args: argparse.Namespace, run_dir: Path, round_idx: int, images: list[ImageState]) -> dict:
    round_params = resolve_round_params(args, round_idx)
    active = [
        image for image in images
        if (round_idx == 0) or (not image.passed and image.missing_chunks)
    ]
    if not active:
        return {'round': round_idx, 'active_count': 0, 'skipped': True}

    round_started = time.monotonic()
    group_size = args.batch_size if args.batch_size > 0 else len(active)
    active_groups = [active[i:i + group_size] for i in range(0, len(active), group_size)]
    batch_records = []
    decode_statuses = []
    total_batch_samples = 0
    max_workers_used = 1
    for batch_idx, group in enumerate(active_groups):
        batch_started = time.monotonic()
        batch_dir = run_dir / f'round{round_idx}' / f'batch_{batch_idx:04d}'
        make_started = time.monotonic()
        bursts = [
            make_waveform(
                args,
                image,
                round_idx,
                [] if round_idx == 0 else image.missing_chunks,
                round_params,
            )
            for image in group
        ]
        make_wall_sec = time.monotonic() - make_started
        build_started = time.monotonic()
        batch_tx, batch_samples = build_batch_tx(
            run_dir, round_idx, batch_idx, bursts, round_params.batch_gap_samples
        )
        build_batch_wall_sec = time.monotonic() - build_started
        cleanup_removed_after_build = cleanup_heavy_files(
            [burst.tx_sc16 for burst in bursts],
            enabled=args.artifact_mode in ('minimal', 'board'),
        )
        total_batch_samples += batch_samples
        batch_rx = batch_dir / 'batch_rx.sc16'
        rx_capture_file = str(batch_rx)
        if args.rx_capture_mode in ('remote-pull', 'remote-decode'):
            rx_capture_file = build_remote_batch_rx_path(args, round_idx=round_idx, batch_idx=batch_idx)
        rx_duration = round_params.tx_delay_sec + batch_samples / args.rate + round_params.rx_tail_sec

        rx_start_started = time.monotonic()
        rx_start = run_control_inline(
            args.rx_control_host,
            int(args.rx_control_port),
            f'CAPTURE file={rx_capture_file} duration={rx_duration:.6f} nsamps=0',
            batch_dir / 'rx_start.log',
            timeout=args.rx_timeout_sec,
        )
        rx_start_wall_sec = time.monotonic() - rx_start_started
        time.sleep(round_params.tx_delay_sec)
        tx_send_started = time.monotonic()
        tx_control_file = translate_tx_control_file_path(
            batch_tx,
            args.tx_file_path_prefix_from,
            args.tx_file_path_prefix_to,
        )
        tx_send = run_control_inline(
            args.tx_control_host,
            int(args.tx_control_port),
            f'SEND file={tx_control_file}',
            batch_dir / 'tx_send.log',
            timeout=args.tx_timeout_sec,
        )
        tx_send_wall_sec = time.monotonic() - tx_send_started
        cleanup_removed_after_tx = cleanup_heavy_files(
            [batch_tx],
            enabled=args.artifact_mode in ('minimal', 'board'),
        )
        rx_wait_started = time.monotonic()
        rx_wait = run_control_inline(
            args.rx_control_host,
            int(args.rx_control_port),
            f'WAIT timeout={args.rx_timeout_sec}',
            batch_dir / 'rx_wait.log',
            timeout=args.rx_timeout_sec + 5.0,
        )
        rx_wait_wall_sec = time.monotonic() - rx_wait_started
        remote_pull_record: dict[str, object] | None = None
        if args.rx_capture_mode == 'remote-pull':
            remote_pull_record = pull_remote_batch_rx(args, rx_capture_file, batch_rx, batch_dir)
            print(
                'remote_rx_pull '
                f'round={round_idx} '
                f'batch={batch_idx + 1}/{len(active_groups)} '
                f'target={args.remote_rx_ssh_target} '
                f'wall_sec={float(remote_pull_record["pull_wall_sec"]):.3f}'
            )

        workers = max(1, min(args.decode_workers, len(bursts)))
        max_workers_used = max(max_workers_used, workers)
        batch_decode_statuses = []
        batch_decode_records = []
        decode_started = time.monotonic()
        if args.rx_capture_mode == 'remote-decode':
            records = decode_batch_remote(args, rx_capture_file, bursts, round_params, batch_total_samples=batch_samples)
            for record in records:
                status = int(record['decode_status'])
                decode_statuses.append(status)
                batch_decode_statuses.append(status)
                batch_decode_records.append(record)
        elif workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(decode_slice, args, batch_rx, burst, round_params) for burst in bursts]
                for future in as_completed(futures):
                    record = future.result()
                    status = int(record['decode_status'])
                    decode_statuses.append(status)
                    batch_decode_statuses.append(status)
                    batch_decode_records.append(record)
        else:
            for burst in bursts:
                record = decode_slice(args, batch_rx, burst, round_params)
                status = int(record['decode_status'])
                decode_statuses.append(status)
                batch_decode_statuses.append(status)
                batch_decode_records.append(record)

        decode_wall_sec = time.monotonic() - decode_started

        merge_started = time.monotonic()
        merge_wall_secs = []
        for burst in bursts:
            merge_wall_sec = merge_image(args, burst.image, round_idx)
            merge_wall_secs.append(merge_wall_sec)
            if burst.image.round_records:
                burst.image.round_records[-1]['merge_wall_sec'] = merge_wall_sec
        merge_wall_sec = time.monotonic() - merge_started
        cleanup_removed_after_decode = cleanup_heavy_files(
            [batch_rx],
            enabled=args.artifact_mode in ('minimal', 'board'),
        )
        cleanup_removed_decode_slices = sum(
            int(item.get('cleanup_removed_bytes', 0)) for item in batch_decode_records
        )

        batch_records.append({
            'batch': batch_idx,
            'active_count': len(group),
            'batch_tx': str(batch_tx),
            'batch_rx': str(batch_rx),
            'rx_capture_mode': args.rx_capture_mode,
            'rx_capture_file': rx_capture_file,
            'batch_samples': batch_samples,
            'rx_duration_sec': rx_duration,
            'wall_sec': time.monotonic() - batch_started,
            'round_params': {
                'warmup_samples': round_params.warmup_samples,
                'tail_samples': round_params.tail_samples,
                'batch_gap_samples': round_params.batch_gap_samples,
                'tx_delay_sec': round_params.tx_delay_sec,
                'rx_tail_sec': round_params.rx_tail_sec,
                'slice_pre_sec': round_params.slice_pre_sec,
                'slice_post_sec': round_params.slice_post_sec,
                'search_window_sec': round_params.search_window_sec,
            },
            'make_wall_sec': make_wall_sec,
            'build_batch_wall_sec': build_batch_wall_sec,
            'rx_start_wall_sec': rx_start_wall_sec,
            'tx_delay_wall_sec': round_params.tx_delay_sec,
            'tx_send_wall_sec': tx_send_wall_sec,
            'rx_wait_wall_sec': rx_wait_wall_sec,
            'rx_pull_wall_sec': float(remote_pull_record['pull_wall_sec']) if remote_pull_record else 0.0,
            'decode_wall_sec': decode_wall_sec,
            'merge_wall_sec': merge_wall_sec,
            'decode_command_wall_sec_sum': sum(
                float(item.get('decode_command_wall_sec', 0.0)) for item in batch_decode_records
            ),
            'slice_copy_wall_sec_sum': sum(
                float(item.get('slice_copy_wall_sec', 0.0)) for item in batch_decode_records
            ),
            'merge_wall_sec_sum': sum(merge_wall_secs),
            'cleanup_removed_bytes': (
                cleanup_removed_after_build
                + cleanup_removed_after_tx
                + cleanup_removed_decode_slices
                + cleanup_removed_after_decode
            ),
            'decode_workers': workers,
            'rx_start': rx_start,
            'tx_send': tx_send,
            'rx_wait': rx_wait,
            'remote_pull': remote_pull_record,
            'decode_statuses': batch_decode_statuses,
            'decode_records': batch_decode_records,
        })
        processed_once = sum(1 for image in images if image.rounds > 0)
        passed_now = sum(1 for image in images if image.passed)
        pending_now = sum(1 for image in images if not image.passed)
        print(
            'batch_progress '
            f'round={round_idx} '
            f'batch={batch_idx + 1}/{len(active_groups)} '
            f'processed={processed_once}/{len(images)} '
            f'pass={passed_now} '
            f'pending={pending_now}'
        )

    return {
        'round': round_idx,
        'active_count': len(active),
        'batch_count': len(batch_records),
        'batch_size': args.batch_size,
        'batch_samples': total_batch_samples,
        'wall_sec': time.monotonic() - round_started,
        'round_params': {
            'warmup_samples': round_params.warmup_samples,
            'tail_samples': round_params.tail_samples,
            'batch_gap_samples': round_params.batch_gap_samples,
            'tx_delay_sec': round_params.tx_delay_sec,
            'rx_tail_sec': round_params.rx_tail_sec,
            'slice_pre_sec': round_params.slice_pre_sec,
            'slice_post_sec': round_params.slice_post_sec,
            'search_window_sec': round_params.search_window_sec,
        },
        'decode_workers': max_workers_used,
        'batches': batch_records,
        'decode_statuses': decode_statuses,
    }


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise RuntimeError('--count must be positive')
    if args.max_arq_rounds < 0:
        raise RuntimeError('--max-arq-rounds must be non-negative')

    # Start SSH ControlMaster for remote modes to avoid per-call handshake overhead.
    ssh_master_proc = None
    args.ssh_control_socket = None
    if args.rx_capture_mode in ('remote-pull', 'remote-decode') and args.remote_rx_ssh_target:
        ssh_master_proc = _ssh_start_control_master(args.remote_rx_ssh_target)
        if ssh_master_proc is not None:
            args.ssh_control_socket = _ssh_control_socket_path()

    try:
        return _main_inner(args)
    finally:
        _ssh_stop_control_master(
            args.remote_rx_ssh_target if hasattr(args, 'remote_rx_ssh_target') else '',
            ssh_master_proc,
        )


def _main_inner(args: argparse.Namespace) -> int:
    inputs = load_inputs(args)
    run_dir = (args.run_root / args.run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    images = [
        ImageState(index=idx, input_path=input_path, image_dir=run_dir / f'image_{idx:04d}')
        for idx, input_path in enumerate(inputs)
    ]
    summary = {
        'run_id': args.run_id,
        'run_root': str(run_dir),
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'target_count': args.count,
        'max_arq_rounds': args.max_arq_rounds,
        'dry_run': args.dry_run,
        'rate': args.rate,
        'chunk_bytes': args.chunk_bytes,
        'batch_gap_samples': args.batch_gap_samples,
        'batch_size': args.batch_size,
        'decode_backend': args.decode_backend,
        'cpp_sync_mode': args.cpp_sync_mode if args.decode_backend == 'cpp' else '',
        'artifact_mode': args.artifact_mode,
        'fast_arq_profile': args.fast_arq_profile,
        'rx_capture_mode': args.rx_capture_mode,
        'remote_rx_ssh_target': args.remote_rx_ssh_target,
        'remote_rx_run_root': args.remote_rx_run_root,
        'tx_delay_sec': args.tx_delay_sec,
        'rx_tail_sec': args.rx_tail_sec,
        'arq_overrides': {
            'warmup_samples': args.arq_warmup_samples,
            'tail_samples': args.arq_tail_samples,
            'batch_gap_samples': args.arq_batch_gap_samples,
            'rx_tail_sec': args.arq_rx_tail_sec,
            'slice_pre_sec': args.arq_slice_pre_sec,
            'slice_post_sec': args.arq_slice_post_sec,
            'search_window_sec': args.arq_search_window_sec,
        },
        'rounds': [],
        'results': [],
    }
    started = time.time()
    write_summary(run_dir, summary, images, started)

    if args.dry_run:
        summary['dry_run_inputs'] = [str(path) for path in inputs]
        summary['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        write_summary(run_dir, summary, images, started)
        print(f'batch_spool_summary={run_dir / "batch_spool_summary.json"}')
        print('dry_run=true')
        return 0

    for round_idx in range(args.max_arq_rounds + 1):
        print(f'round={round_idx}')
        round_record = run_round(args, run_dir, round_idx, images)
        summary['rounds'].append(round_record)
        write_summary(run_dir, summary, images, started)
        passed = sum(1 for image in images if image.passed)
        failed = len(images) - passed
        print(f'round_result round={round_idx} pass={passed} fail={failed}')
        if failed == 0:
            break
        if args.stop_on_fail and round_idx >= args.max_arq_rounds:
            break

    summary['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    if args.artifact_mode == 'board':
        summary['board_cleanup_removed_bytes'] = cleanup_board_small_bins(images)
    write_summary(run_dir, summary, images, started)
    all_pass = all(image.passed for image in images)
    print(f'batch_spool_summary={run_dir / "batch_spool_summary.json"}')
    print(f'completed_count={len(images)}')
    print(f'pass_count={sum(1 for image in images if image.passed)}')
    print(f'fail_count={sum(1 for image in images if not image.passed)}')
    print(f'all_pass={str(all_pass).lower()}')
    return 0 if all_pass else 2


if __name__ == '__main__':
    raise SystemExit(main())
