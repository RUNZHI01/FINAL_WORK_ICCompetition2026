#!/usr/bin/env python3
"""
TUI 专用飞腾派端 TCP server。

目标：
1. 复用派端现有 mlkem_link_v2 与身份密钥
2. 支持 ML-KEM 握手与可选的 SM2 / ML-DSA 服务端认证
3. 仅覆盖 TUI 所需的基础数据链路验证
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path


REMOTE_PACKAGE_ROOTS = (
    "/home/user",
    str(Path(__file__).resolve().parents[1]),
)
for root in REMOTE_PACKAGE_ROOTS:
    if root and root not in sys.path:
        sys.path.insert(0, root)


try:
    from mlkem_link_v2.auth import IdentityConfig, SigPolicy
    from mlkem_link_v2.crypto import CipherSuite
    from mlkem_link_v2.kem import get_backend
    from mlkem_link_v2.secure_channel import SecureChannel
    from mlkem_link_v2.session import SessionRole
except ImportError:
    from mlkem_link.auth import IdentityConfig, SigPolicy
    from mlkem_link.crypto import CipherSuite
    from mlkem_link.kem import get_backend
    from mlkem_link.secure_channel import SecureChannel
    from mlkem_link.session import SessionRole


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "") or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_file_bytes(path: str) -> bytes | None:
    target = str(path or "").strip()
    if not target:
        return None
    return Path(target).read_bytes()


def _parse_sig_policy(raw: str) -> SigPolicy:
    value = str(raw or "").strip() or SigPolicy.DUAL_REQUIRED.value
    try:
        return SigPolicy(value)
    except ValueError as exc:
        raise RuntimeError(f"不支持的认证策略: {value}") from exc


def _load_auth_config() -> IdentityConfig | None:
    if not _env_flag("MLKEM_AUTH_ENABLED"):
        return None

    config = IdentityConfig(
        role=SessionRole.RESPONDER,
        server_id=str(os.environ.get("MLKEM_AUTH_SERVER_ID", "") or "").strip() or "phytium-board",
        server_sm2_sk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_SM2_KEY", "") or "")),
        server_sm2_pk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_SM2_PUB", "") or "")),
        server_mldsa_sk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_MLDSA_KEY", "") or "")),
        server_mldsa_pk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_MLDSA_PUB", "") or "")),
        sig_policy=_parse_sig_policy(str(os.environ.get("MLKEM_AUTH_SIG_POLICY", "") or "")),
    )
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY} and not config.server_sm2_sk:
        raise RuntimeError("已启用认证，但缺少 MLKEM_AUTH_SERVER_SM2_KEY")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY} and not config.server_sm2_pk:
        raise RuntimeError("已启用认证，但缺少 MLKEM_AUTH_SERVER_SM2_PUB")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY} and not config.server_mldsa_sk:
        raise RuntimeError("已启用认证，但缺少 MLKEM_AUTH_SERVER_MLDSA_KEY")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY} and not config.server_mldsa_pk:
        raise RuntimeError("已启用认证，但缺少 MLKEM_AUTH_SERVER_MLDSA_PUB")
    return config


def _suite_from_arg(raw: str) -> CipherSuite:
    value = str(raw or "").strip()
    if not value:
        return CipherSuite.SM4_GCM
    for item in CipherSuite:
        if value in {item.name, item.value}:
            return item
    raise ValueError(f"不支持的套件: {raw}")


def _connection_closed_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    markers = ("连接关闭", "connection closed", "reset by peer", "broken pipe", "timed out", "已读 0 字节")
    return any(marker in text for marker in markers)


def _serve_one_client(
    conn: socket.socket,
    *,
    backend: object,
    suite: CipherSuite,
    output_dir: Path,
    auth_config: IdentityConfig | None,
    conn_id: int,
) -> None:
    channel = SecureChannel(conn, SessionRole.RESPONDER, backend, suite)
    hs_ms = (
        channel.authenticated_handshake(auth_config)
        if auth_config is not None
        else channel.handshake()
    )
    print(
        f"[连接 #{conn_id}] 握手完成: {hs_ms:.1f}ms "
        f"(suite={channel.cipher_suite.value}, auth={'on' if auth_config else 'off'})",
        flush=True,
    )
    if auth_config is not None:
        print(
            f"[连接 #{conn_id}] 服务端认证: policy={auth_config.sig_policy.value} "
            f"server_id={auth_config.server_id}",
            flush=True,
        )

    msg_idx = 0
    while True:
        try:
            meta_raw = channel.recv_encrypted(aad=b"metadata")
        except Exception as exc:
            if msg_idx > 0 and _connection_closed_error(exc):
                print(f"[连接 #{conn_id}] 客户端已关闭会话", flush=True)
                return
            raise

        msg_idx += 1
        meta = json.loads(meta_raw.decode("utf-8"))
        latent_bytes = channel.recv_encrypted(aad=meta_raw)

        output_dir.mkdir(parents=True, exist_ok=True)
        job_id = meta.get("job_id", f"job-{conn_id}-{msg_idx}")
        out_path = output_dir / f"{job_id}.bin"
        out_path.write_bytes(latent_bytes)

        original_sha = meta.get("sha256", "")
        received_sha = hashlib.sha256(latent_bytes).hexdigest()
        sha_match = received_sha == original_sha

        ack = {
            "status": "ok" if sha_match else "sha256_mismatch",
            "sha256_match": sha_match,
            "bytes_received": len(latent_bytes),
            "timestamp": time.time(),
        }
        channel.send_encrypted(json.dumps(ack, ensure_ascii=False).encode("utf-8"), aad=b"ack")
        print(
            f"[连接 #{conn_id}][任务 {msg_idx}] "
            f"job_id={job_id} bytes={len(latent_bytes)} sha={'ok' if sha_match else 'fail'} "
            f"saved={out_path}",
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="TUI 专用飞腾派端 TCP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9527)
    parser.add_argument("--output-dir", default="/tmp/mlkem_tui_recv")
    parser.add_argument("--kem", default="768")
    parser.add_argument("--suite", default="SM4_GCM")
    args = parser.parse_args()

    backend = get_backend(str(args.kem))
    suite = _suite_from_arg(args.suite)
    auth_config = _load_auth_config()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(8)
    print(
        f"监听 {args.host}:{args.port} "
        f"kem={backend.name} suite={suite.value} auth={auth_config.sig_policy.value if auth_config else 'OFF'}",
        flush=True,
    )
    try:
        conn_id = 0
        while True:
            conn, addr = sock.accept()
            conn_id += 1
            print(f"[连接 #{conn_id}] 来自 {addr[0]}:{addr[1]}", flush=True)
            with conn:
                try:
                    _serve_one_client(
                        conn,
                        backend=backend,
                        suite=suite,
                        output_dir=Path(args.output_dir),
                        auth_config=auth_config,
                        conn_id=conn_id,
                    )
                except Exception as exc:
                    if _connection_closed_error(exc):
                        # Readiness probes may open and close a raw TCP socket before any frame is sent.
                        print(f"[连接 #{conn_id}] 握手前对端已关闭，忽略并继续监听", flush=True)
                        continue
                    raise
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
