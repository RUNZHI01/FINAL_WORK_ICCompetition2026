#!/usr/bin/env python3
"""
上位机 ML-KEM 安全发送客户端

连接飞腾派服务端后：
1. 完成 ML-KEM-768 握手
2. 发送加密的 latent 数据 + 元数据
3. 等待 ACK 确认

用法:
  # 连接飞腾派
  python tcp_client.py --host 100.121.87.73 --port 9527 --input latent.npz

  # 本地测试
  python tcp_client.py --host 127.0.0.1 --port 9527 --input latent.npz

  # 指定套件
  python tcp_client.py --host 127.0.0.1 --port 9527 --input latent.npz --suite SM4_GCM
"""

import argparse
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite
from mlkem_link.session import SessionRole
from mlkem_link.secure_channel import SecureChannel
from mlkem_link.auth import IdentityConfig, SigPolicy
from latent_transport import SUPPORTED_PAYLOAD_CODECS, build_transport_payload


def _env_flag(name: str) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _read_file_bytes(path: str) -> bytes | None:
    target = str(path or "").strip()
    if not target:
        return None
    with open(target, "rb") as handle:
        return handle.read()


def _parse_sig_policy(raw: str) -> SigPolicy:
    value = str(raw or "").strip() or SigPolicy.DUAL_REQUIRED.value
    try:
        return SigPolicy(value)
    except ValueError as exc:
        raise RuntimeError(f"不支持的 ML-KEM 身份认证策略: {value}") from exc


def _load_auth_config() -> IdentityConfig | None:
    if not _env_flag("MLKEM_AUTH_ENABLED"):
        return None

    config = IdentityConfig(
        role=SessionRole.INITIATOR,
        server_id=str(os.environ.get("MLKEM_AUTH_SERVER_ID", "") or "").strip() or "phytium-board",
        peer_sm2_pk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_PEER_SM2_PUB", "") or "")),
        peer_mldsa_pk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_PEER_MLDSA_PUB", "") or "")),
        sig_policy=_parse_sig_policy(str(os.environ.get("MLKEM_AUTH_SIG_POLICY", "") or "")),
    )
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY} and not config.peer_sm2_pk:
        raise RuntimeError("已启用身份认证，但缺少 MLKEM_AUTH_PEER_SM2_PUB")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY} and not config.peer_mldsa_pk:
        raise RuntimeError("已启用身份认证，但缺少 MLKEM_AUTH_PEER_MLDSA_PUB")
    return config


def send_one_image(
    channel,
    payload_bytes: bytes,
    payload_meta: dict,
    output_path: str | None = None,
) -> dict:
    """在已握手的 SecureChannel 上发送单张图片，返回 ACK dict

    Args:
        channel: 已完成握手的 SecureChannel
        payload_bytes: 实际发送的 payload 字节
        payload_meta: 打包后的传输元数据
        output_path: 重建结果保存路径（None 时自动生成）

    Returns:
        ACK 响应 dict（含 status, sha256_match, tvm 等）
    """
    job_id = str(payload_meta.get('job_id') or 'job')
    payload_codec = str(payload_meta.get('payload_codec') or 'float32-raw')
    meta = json.dumps(payload_meta, separators=(',', ':')).encode()

    # ── 2. 单帧合并：4B meta_len + meta JSON + latent bytes（省 1 RTT） ──
    combined = len(meta).to_bytes(4, "big") + meta + payload_bytes
    t_send = time.perf_counter()
    channel.send_encrypted(combined, aad=b"metadata")
    t_sent = time.perf_counter()
    print(f"  [{job_id}] 加密发送: {len(payload_bytes)}B "
          f"(codec={payload_codec}), "
          f"耗时 {((t_sent - t_send) * 1000):.1f}ms")

    # ── 3. 等待 ACK ──
    ack_enc = channel.recv_encrypted(aad=b"ack")
    ack = json.loads(ack_enc)

    if ack.get("status") == "ok" and ack.get("sha256_match"):
        print(f"  [{job_id}] ✓ SHA256 匹配, "
              f"接收 {ack.get('bytes_received', '?')}B")
    else:
        print(f"  [{job_id}] ✗ 传输失败: "
              f"status={ack.get('status')}, "
              f"sha256={ack.get('sha256_match')}")

    # ── 4. 接收 TVM 重建结果（如果服务端启用了 --tvm）──
    if ack.get("tvm") and ack.get("result_bytes"):
        print(f"  [{job_id}] TVM 推理: {ack.get('inference_ms', '?')}ms, "
              f"输出: {ack.get('output_shape', '?')}")

        result_bytes = channel.recv_encrypted(
            aad=json.dumps(ack).encode())
        print(f"  [{job_id}] 接收结果: {len(result_bytes)}B")

        out = output_path or _allocate_result_output_path(job_id)
        with open(out, "wb") as f:
            f.write(result_bytes)
        print(f"  [{job_id}] 已保存: {out}")

        # 发送 RESULT_ACK
        channel.send_encrypted(
            json.dumps({"status": "result_received"}).encode(),
            aad=b"result_ack",
        )

    return ack


def _allocate_result_output_path(job_id: str) -> str:
    safe_job_id = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_"
        for ch in str(job_id or "job")
    ).strip("._-") or "job"
    fd, raw_path = tempfile.mkstemp(
        prefix=f"mlkem_result_{safe_job_id[:48]}_",
        suffix=".bin",
    )
    os.close(fd)
    return raw_path


def daemon_loop(sock: "socket.socket", channel: "SecureChannel",
                handshake_ms: float, suite: "CipherSuite",
                default_payload_codec: str) -> None:
    """守护进程主循环：从 stdin 读 JSON 指令，通过 SecureChannel 发送

    协议（每行一个 JSON）:
      stdin  -> {"action": "send",    "input": "/path/file.bin", "job_id": "xxx"}
      stdout <- {"status": "ok",      "job_id": "...", "sha256_match": true,
                 "inference_ms": ..., "total_ms": ...}
      stdin  -> {"action": "ping"}
      stdout <- {"status": "alive",   "handshake_ms": ..., "images_sent": N}
      stdin  -> {"action": "quit"}
      (进程退出)
    """
    images_sent = 0

    def _write(obj: dict) -> None:
        json.dump(obj, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")
        sys.stdout.flush()

    # 首行输出：通知调用方 daemon 就绪
    _write({
        "status": "ready",
        "handshake_ms": round(handshake_ms, 1),
        "suite": suite.value,
        "auth_enabled": channel.auth_enabled,
        "sig_policy": channel.auth_sig_policy,
        "server_id": channel.peer_server_id,
    })

    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            break
        if not line:  # EOF
            break
        line = line.strip()
        if not line:
            continue

        try:
            cmd = json.loads(line)
        except json.JSONDecodeError as e:
            _write({"status": "error", "message": f"invalid JSON: {e}"})
            continue

        action = cmd.get("action", "")

        if action == "ping":
            _write({
                "status": "alive",
                "handshake_ms": round(handshake_ms, 1),
                "images_sent": images_sent,
            })
            continue

        if action == "quit":
            _write({"status": "bye"})
            break

        if action == "send":
            input_path = cmd.get("input", "")
            job_id = cmd.get("job_id", "daemon")
            payload_codec = str(cmd.get('payload_codec') or default_payload_codec)
            try:
                t0 = time.perf_counter()
                payload_bytes, payload_meta, _ = build_transport_payload(
                    input_path,
                    job_id=job_id,
                    payload_codec=payload_codec,
                )
                # send_one_image 内部 print 到 stderr，不污染 stdout JSON 协议
                old_stdout = sys.stdout
                sys.stdout = sys.stderr
                try:
                    ack = send_one_image(
                        channel, payload_bytes, payload_meta, output_path=None)
                finally:
                    sys.stdout = old_stdout
                t_done = time.perf_counter()
                images_sent += 1
                _write({
                    "status": "ok" if ack.get("status") == "ok" else "error",
                    "job_id": job_id,
                    "sha256_match": ack.get("sha256_match", False),
                    "inference_ms": ack.get("inference_ms"),
                    "total_ms": round((t_done - t0) * 1000, 1),
                })
            except Exception as e:
                _write({
                    "status": "error",
                    "job_id": job_id,
                    "message": str(e),
                })
            continue

        _write({"status": "error", "message": f"unknown action: {action}"})

    # 优雅关闭 ML-KEM session
    try:
        close_meta = json.dumps({"close_session": True}).encode()
        channel.send_encrypted(close_meta, aad=b"metadata")
        channel.recv_encrypted(aad=b"ack")
    except Exception:
        pass
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description="上位机 ML-KEM 安全发送客户端")
    parser.add_argument("--host", required=True,
                        help="服务端地址 (飞腾派 IP)")
    parser.add_argument("--port", type=int, default=9527,
                        help="服务端端口 (默认 9527)")
    parser.add_argument("--input", default=None,
                        help="待发送的 latent 文件 (.npz / .npy / .bin)")
    parser.add_argument("--suite", default="SM4_GCM",
                        choices=["AES_256_GCM", "SM4_GCM"],
                        help="AEAD 密码套件 (默认 SM4-GCM 国密)")
    parser.add_argument("--job-id", default=None,
                        help="任务 ID (默认取文件名)")
    parser.add_argument("--output", default=None,
                        help="重建结果保存路径 (启用 TVM 时有效)")
    parser.add_argument("--count", type=int, default=1,
                        help="发送次数，复用同一 ML-KEM session (默认 1)")
    parser.add_argument("--json-summary", action="store_true",
                        help="最后输出 JSON 摘要（便于 server.py 解析）")
    parser.add_argument("--daemon", action="store_true",
                        help="守护进程模式: 保持 ML-KEM session 活跃, "
                             "通过 stdin 接收 JSON 指令, stdout 输出 JSON 结果")
    parser.add_argument(
        '--payload-codec',
        choices=SUPPORTED_PAYLOAD_CODECS,
        default='float32-raw',
        help='传输 payload 编码方式 (默认 float32-raw)',
    )
    args = parser.parse_args()

    if args.daemon and args.count > 1:
        parser.error("--daemon 与 --count 不可同时使用")
    if args.daemon and not args.input:
        pass  # daemon 模式下 input 按需从指令读取
    elif not args.daemon and not args.input:
        parser.error("非 daemon 模式需要 --input")

    suite = CipherSuite[args.suite]
    base_job_id = args.job_id or (
        os.path.splitext(os.path.basename(args.input))[0]
        if args.input else "daemon")

    if args.daemon:
        # ── daemon 模式：连接 + 握手后进入交互循环 ──
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((args.host, args.port))
            backend = get_backend("768")
            channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)
            auth_config = _load_auth_config()
            hs_ms = (
                channel.authenticated_handshake(auth_config)
                if auth_config is not None
                else channel.handshake()
            )
            # daemon_loop 内部处理优雅关闭和 sock.close()
            daemon_loop(sock, channel, hs_ms, suite, args.payload_codec)
        finally:
            try:
                sock.close()
            except Exception:
                pass
        return

    # ── 普通模式（原有逻辑）──
    payload_bytes, payload_meta, payload_stats = build_transport_payload(
        args.input,
        job_id=base_job_id,
        payload_codec=args.payload_codec,
    )

    print("=" * 60)
    print("ML-KEM 安全发送客户端 (上位机)")
    print("=" * 60)
    print(f"目标:      {args.host}:{args.port}")
    print(f"密码套件:  {suite.value}")
    print(f"输入文件:  {args.input}")
    print(f"传输编码:  {payload_stats['payload_codec']}")
    print(f"数据大小:  {payload_stats['payload_bytes']} bytes")
    print(f"latent:    {payload_stats['latent_bytes']} bytes")
    print(f"SHA256:    {str(payload_stats['payload_sha256'])[:16]}...")
    print(f"形状:      {payload_meta['shape']} ({payload_meta['dtype']})")
    print(f"发送次数:  {args.count}")
    print()

    # 连接服务端
    import socket
    t_connect = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((args.host, args.port))
    t_connected = time.perf_counter()
    print(f"已连接: {args.host}:{args.port} "
          f"({((t_connected - t_connect) * 1000):.1f}ms)")

    results = []
    try:
        backend = get_backend("768")
        print(f"KEM 后端:  {backend.name}")

        channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)
        auth_config = _load_auth_config()

        # ── ML-KEM 握手（仅一次）──
        hs_ms = (
            channel.authenticated_handshake(auth_config)
            if auth_config is not None
            else channel.handshake()
        )
        print(f"握手完成: {hs_ms:.1f}ms")
        if auth_config is not None:
            print(f"身份认证:  已启用 ({auth_config.sig_policy.value})")
            print(f"服务端标识: {channel.peer_server_id or auth_config.server_id}")
        print()

        t_batch_start = time.perf_counter()

        for i in range(args.count):
            job_id = f"{base_job_id}" if args.count == 1 else f"{base_job_id}_{i:04d}"
            output = args.output if args.count == 1 else None

            if args.count > 1 and i % 50 == 0:
                print(f"[{i+1}/{args.count}]")

            ack = send_one_image(
                channel, payload_bytes, payload_meta | {'job_id': job_id}, output)
            results.append(ack)

        t_batch_done = time.perf_counter()
        total_ms = (t_batch_done - t_batch_start) * 1000

        # ── 发送 session 关闭信号 ──
        try:
            close_meta = json.dumps({"close_session": True}).encode()
            channel.send_encrypted(close_meta, aad=b"metadata")
            channel.recv_encrypted(aad=b"ack")
        except Exception:
            pass

        print()
        print("=" * 60)
        ok_count = sum(1 for r in results
                       if r.get("status") == "ok" and r.get("sha256_match"))
        print(f"完成: {ok_count}/{args.count} 成功, "
              f"总计 {total_ms:.0f}ms "
              f"(握手 {hs_ms:.0f}ms + 传输 {total_ms - hs_ms:.0f}ms)")
        if args.count > 1:
            per_img_ms = (t_batch_done - t_batch_start) * 1000 / args.count
            print(f"每张平均: {per_img_ms:.1f}ms")
        print("=" * 60)

        if args.json_summary:
            import sys
            summary = {
                "total": args.count,
                "success": ok_count,
                "handshake_ms": round(hs_ms, 1),
                "total_ms": round(total_ms, 1),
                "per_image_ms": round(total_ms / args.count, 1),
                "results": results,
                "auth_enabled": channel.auth_enabled,
                "sig_policy": channel.auth_sig_policy or None,
                "server_id": channel.peer_server_id or None,
            }
            json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
            print()

    finally:
        sock.close()


if __name__ == "__main__":
    main()
