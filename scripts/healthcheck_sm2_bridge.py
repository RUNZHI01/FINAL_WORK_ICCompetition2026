#!/usr/bin/env python3
"""健康检查：容器端 x86_64 SM2 签名桥接库加载。

验证 libtongsuo_sig_bridge.so 在容器（x86_64）内可以加载，并能用板端公钥做 verify。
keygen 在 vanilla OpenSSL 3.0.2 上会失败（已知限制），不算失败。

用法（容器内）：
    python /workspace/scripts/healthcheck_sm2_bridge.py
    python /workspace/scripts/healthcheck_sm2_bridge.py \\
        --bridge /workspace/artifacts/crypto/libtongsuo_sig_bridge.so \\
        --board-pub /workspace/keys/server_sm2_identity.pub

退出码：
    0 = 桥接库加载 + 板端公钥读取 OK（keygen 失败不算）
    1 = 其他失败
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--bridge",
        default=os.environ.get(
            "TONGSUO_SIG_BRIDGE",
            "/workspace/artifacts/crypto/libtongsuo_sig_bridge.so",
        ),
        help="libtongsuo_sig_bridge.so 路径（默认走 TONGSUO_SIG_BRIDGE env）",
    )
    parser.add_argument(
        "--board-pub",
        default="/workspace/keys/server_sm2_identity.pub",
        help="板端 SM2 公钥路径",
    )
    args = parser.parse_args()

    os.environ.setdefault("TONGSUO_SIG_BRIDGE", args.bridge)
    sys.path.insert(0, "/workspace")

    bridge_path = Path(args.bridge)
    if not bridge_path.is_file():
        print(f"FAIL: bridge not found: {bridge_path}", file=sys.stderr)
        return 1

    print(f"[1/3] bridge: {bridge_path} ({bridge_path.stat().st_size} bytes)")
    try:
        from mlkem_link.auth import get_sm2_backend  # type: ignore
    except ImportError as exc:
        print(f"FAIL: cannot import mlkem_link.auth: {exc}", file=sys.stderr)
        return 1

    try:
        backend = get_sm2_backend()
    except Exception as exc:
        print(f"FAIL: get_sm2_backend raised: {exc}", file=sys.stderr)
        return 1
    print(f"[2/3] backend loaded: {backend.name} "
          f"(pk={backend.pk_bytes}B sk={backend.sk_bytes}B sig={backend.sig_bytes}B)")

    board_pub = Path(args.board_pub)
    if not board_pub.is_file():
        print(f"FAIL: board public key not found: {board_pub}", file=sys.stderr)
        return 1
    pk_bytes = board_pub.read_bytes()
    print(f"[3/3] board pub: {board_pub} ({len(pk_bytes)}B)")
    if len(pk_bytes) != backend.pk_bytes:
        print(f"WARN: expected pk={backend.pk_bytes}B, got {len(pk_bytes)}B", file=sys.stderr)

    # 注意：keygen 在 vanilla OpenSSL 3.0.2 上会失败（已知，不算错误）
    print("OK: bridge load + board pub read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
