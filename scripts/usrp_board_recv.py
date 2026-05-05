#!/usr/bin/env python3
"""usrp_board_recv.py — 板端 USRP 接收 + TVM 推理

启动 usrp_tensor_rx daemon → 收到文件 → 解包 [4B meta_len][JSON][latent bytes]
→ SHA256 校验 → 保存 .npz → （可选）调用 TVM 推理。

用法（板端）:
  # 仅接收，不跑 TVM
  python scripts/usrp_board_recv.py --output-dir /tmp/mlkem_recv

  # 接收 + TVM 推理
  python scripts/usrp_board_recv.py --output-dir /tmp/mlkem_recv \
      --tvm-artifact /home/user/decoder.so

  # 本地测试（SIM 模式，无需 USRP 硬件）
  python scripts/usrp_board_recv.py --output-dir /tmp/mlkem_recv --sim
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from latent_transport import (
    decode_transport_payload,
    save_decoded_npz,
    unpack_transport_frame,
)

# ── USRP 二进制构建路径 ──

_USRP_BUILD = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'usrp_tensor', 'build',
)


def _bin(name: str) -> str:
    """定位 usrp_tensor 构建产物"""
    path = os.path.join(_USRP_BUILD, name)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"找不到 {path}，请先编译: cd usrp_tensor && mkdir -p build && cd build && cmake .. && make")
    return path


# ── TVM 推理 ──

def run_tvm_inference(decoded, meta: dict,
                      output_dir: str, artifact_path: str,
                      tvm_python: str = '',
                      snr: float = 10.0) -> dict | None:
    """调用 TVM 子进程推理

    复用 tcp_server.py 中 run_tvm_inference 的逻辑。
    """
    job_id = meta.get('job_id', 'unknown')

    input_npz = os.path.join(output_dir, f'{job_id}_input.npz')
    output_npy = os.path.join(output_dir, f'{job_id}_output.npy')
    save_decoded_npz(decoded, input_npz)

    helper_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'tvm_inference_helper.py')
    if not os.path.exists(helper_script):
        print(f'[TVM] 找不到 helper: {helper_script}')
        return None

    if not tvm_python:
        tvm_python = sys.executable

    cmd = [
        tvm_python, helper_script,
        '--artifact-path', artifact_path,
        '--input', input_npz,
        '--output', output_npy,
        '--snr', str(snr),
    ]

    print(
        f'[TVM] 启动推理: {os.path.basename(artifact_path)} '
        f'jscc_awgn_snr_db={snr}'
    )

    t1 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print('[TVM] 推理超时 (120s)')
        return None
    t2 = time.perf_counter()

    if proc.returncode != 0:
        print(f'[TVM] 推理失败: {proc.stderr[-200:] if proc.stderr else "unknown"}')
        return None

    try:
        result = json.loads(proc.stdout.strip().split('\n')[-1])
    except (json.JSONDecodeError, IndexError):
        print('[TVM] 输出解析失败')
        return None

    if result.get('status') != 'ok':
        print(f'[TVM] 错误: {result.get("message")}')
        return None

    result['output_path'] = output_npy
    wall_ms = (t2 - t1) * 1000
    realized_snr = result.get('jscc_realized_awgn_snr_db')
    awgn_note = str(result.get('jscc_awgn_note') or '').strip()
    if realized_snr is None:
        realized_snr_text = f'undefined({awgn_note})' if awgn_note else 'undefined'
    else:
        realized_snr_text = f'{float(realized_snr):.3f}'
    print(
        f'[TVM] 完成: {result.get("inference_ms", 0):.1f}ms (推理), '
        f'{wall_ms:.1f}ms (含加载), shape={result.get("output_shape")} '
        f'jscc_awgn_config_db={result.get("jscc_configured_awgn_snr_db", snr)} '
        f'jscc_awgn_realized_db={realized_snr_text}'
    )
    return result


# ── RX daemon 交互 ──

def parse_rx_status(line: str) -> dict:
    """解析 usrp_tensor_rx daemon 输出的 tab-separated 状态行

    格式: OK\telapsed_sec=...\treceived_bytes=...\t...
    或: ERR\tmessage=...
    """
    fields = line.strip().split('\t')
    result: dict = {'status': fields[0]}
    for f in fields[1:]:
        if '=' in f:
            k, v = f.split('=', 1)
            result[k] = v
    return result


def recv_once_via_daemon(rx_proc: subprocess.Popen,
                         output_path: str,
                         timeout: float = 30.0) -> dict:
    """通过 daemon 协议发送 RECV 指令，等待结果

    Args:
        rx_proc: usrp_tensor_rx --daemon 子进程
        output_path: 接收文件输出路径
        timeout: 接收超时秒数

    Returns:
        解析后的状态 dict
    """
    cmd = f'RECV\t{output_path}\t{timeout}'
    rx_proc.stdin.write(cmd + '\n')
    rx_proc.stdin.flush()

    # 等待 OK/ERR 响应
    while True:
        line = rx_proc.stdout.readline()
        if not line:
            return {'status': 'EOF', 'error': 'RX daemon 退出'}
        line = line.strip()
        if not line:
            continue
        if line == 'READY':
            continue
        return parse_rx_status(line)


# ── 单次接收处理 ──

def process_received(bin_path: str, output_dir: str,
                     tvm_config: dict | None = None) -> bool:
    """处理接收到的二进制文件: 解包 → SHA256 → 保存 → TVM

    Returns:
        True 表示处理成功
    """
    if not os.path.exists(bin_path) or os.path.getsize(bin_path) == 0:
        print(f'[recv] 文件为空或不存在: {bin_path}')
        return False

    try:
        blob_bytes = open(bin_path, 'rb').read()
        meta, payload_bytes = unpack_transport_frame(blob_bytes)
    except Exception as e:
        print(f'[recv] 解包失败: {e}')
        return False

    job_id = meta.get('job_id', 'unknown')
    payload_codec = str(meta.get('payload_codec') or 'float32-raw')
    print(f'[recv] job_id={job_id}, shape={meta.get("shape")}, '
          f'dtype={meta.get("dtype")}, codec={payload_codec}, '
          f'payload={len(payload_bytes)}B')

    # SHA256 校验
    recv_sha = hashlib.sha256(payload_bytes).hexdigest()
    orig_sha = meta.get('sha256', '')
    sha_match = recv_sha == orig_sha

    if sha_match:
        print(f'[recv] ✓ SHA256 匹配: {recv_sha[:16]}...')
        print('[recv] latent 链路: byte_exact=yes => effective_snr_db=inf (数字链路无失真)')
    else:
        print(f'[recv] ✗ SHA256 不匹配: '
              f'原文={orig_sha[:16]}... 收到={recv_sha[:16]}...')
        # JSCC 模型有 BER 容忍度，不匹配时仍可尝试推理
        print('[recv] JSCC 模型具有 BER 容忍能力，继续处理...')
        print('[recv] latent 链路: byte_exact=no => effective_snr_db=unknown (板端缺少原始参考 payload)')

    os.makedirs(output_dir, exist_ok=True)

    try:
        npz_path = os.path.join(output_dir, f'{job_id}.npz')
        decoded = decode_transport_payload(
            meta,
            payload_bytes,
            verify_latent_sha=sha_match,
        )
        save_decoded_npz(decoded, npz_path)
        print(f'[recv] 已保存解码结果: {npz_path} '
              f'(storage={decoded.storage_format})')
    except Exception as e:
        print(f'[recv] transport payload 解码/保存失败: {e}')
        return False

    # TVM 推理（可选）
    if tvm_config and tvm_config.get('artifact_path'):
        result = run_tvm_inference(
            decoded, meta, output_dir,
            artifact_path=tvm_config['artifact_path'],
            tvm_python=tvm_config.get('tvm_python', ''),
            snr=tvm_config.get('snr', 10.0),
        )
        if result:
            print(f'[recv] TVM 结果: {result.get("output_path")}')
        else:
            print('[recv] TVM 推理未成功')

    return True


# ── main ──

def main() -> None:
    parser = argparse.ArgumentParser(
        description='板端 USRP 接收 + TVM 推理')
    parser.add_argument('--output-dir', required=True,
                        help='接收文件输出目录')
    parser.add_argument('--tvm-artifact', default=None,
                        help='TVM artifact .so 路径（启用 TVM 推理）')
    parser.add_argument('--tvm-python', default='',
                        help='TVM 推理用 Python 路径（默认当前 Python）')
    parser.add_argument('--snr', type=float, default=10.0,
                        help='TVM helper 的 JSCC/AWGN 仿真 SNR (默认 10)')
    parser.add_argument('--rx-args', default='',
                        help='UHD 设备参数 (例: "serial=31DDAB3")')
    parser.add_argument('--rx-gain', type=float, default=60.0,
                        help='RX 增益 dB (默认 60)')
    parser.add_argument('--timeout', type=float, default=30.0,
                        help='每次接收超时秒数 (默认 30)')
    parser.add_argument('--sim', action='store_true',
                        help='SIM 模式（使用 loopback --sim，用于本地测试）')
    parser.add_argument('--file', default=None,
                        help='直接处理已有的接收文件（跳过 USRP 接收）')
    args = parser.parse_args()

    print('=' * 60)
    print('USRP 板端接收')
    print('=' * 60)

    tvm_config = None
    if args.tvm_artifact:
        tvm_config = {
            'artifact_path': args.tvm_artifact,
            'tvm_python': args.tvm_python,
            'snr': args.snr,
        }

    # ── 直接处理已有文件 ──
    if args.file:
        ok = process_received(args.file, args.output_dir, tvm_config)
        sys.exit(0 if ok else 1)

    # ── SIM 模式: 使用 loopback --sim ──
    if args.sim:
        loopback = _bin('usrp_tensor_loopback')
        bin_path = os.path.join(args.output_dir, 'sim_received.bin')
        os.makedirs(args.output_dir, exist_ok=True)

        # SIM 模式下需要 TX 发送一个测试文件
        # 这里假设用户已经生成了 blob.bin 并通过 loopback 接收
        print('[SIM] 使用 loopback --sim 模式，需要手动传入 --file')
        print('[SIM] 或与 usrp_send.py --mode sim 配合使用')
        sys.exit(0)

    # ── 启动 RX daemon ──
    rx_bin = _bin('usrp_tensor_rx')
    cmd = [rx_bin, '--daemon']
    if args.rx_args:
        cmd += ['--args', args.rx_args]
    cmd += ['--gain', str(args.rx_gain)]

    print(f'[RX] 启动 daemon: {" ".join(cmd)}')

    rx_proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # 等待 READY
    ready_line = rx_proc.stdout.readline().strip()
    if ready_line != 'READY':
        print(f'[RX] 未收到 READY: {ready_line}')
        rx_proc.terminate()
        sys.exit(1)

    print('[RX] daemon 就绪，开始接收...')
    print()

    try:
        recv_count = 0
        while True:
            bin_path = os.path.join(
                args.output_dir, f'usrp_recv_{recv_count}.bin')

            status = recv_once_via_daemon(
                rx_proc, bin_path, timeout=args.timeout)

            if status.get('status') == 'EOF':
                print('[RX] daemon 退出')
                break

            if status.get('status') == 'ERR':
                print(f'[RX] 接收失败: {status.get("message", "")}')
                continue

            if status.get('status') == 'OK':
                print(f'[RX] 接收完成: {status.get("received_bytes", "?")}B, '
                      f'frames_ok={status.get("frames_ok", "?")}, '
                      f'elapsed={status.get("elapsed_sec", "?")}s')

                process_received(bin_path, args.output_dir, tvm_config)
                recv_count += 1

    except KeyboardInterrupt:
        print('\n[RX] 用户中断')
    finally:
        # 优雅关闭 daemon
        try:
            rx_proc.stdin.write('QUIT\n')
            rx_proc.stdin.flush()
            rx_proc.wait(timeout=5)
        except Exception:
            rx_proc.terminate()

    print()
    print('=' * 60)
    print(f'共接收 {recv_count} 个文件')
    print('=' * 60)


if __name__ == '__main__':
    main()
