#!/usr/bin/env python3
"""健康检查：板端 SM2 + ML-DSA 双签 + verify 全链路。

在板端跑（aarch64）。读 /home/user/keys/ 下的身份密钥，签一段 transcript，
然后用对应公钥验签。用于验证板端 keygen + sign + verify 都通。

用法（板端）：
    python3 /home/user/scripts/healthcheck_sign_verify.py
    python3 /home/user/scripts/healthcheck_sign_verify.py \\
        --keys-dir /home/user/keys \\
        --transcript "mlkem-link self-test"

退出码：
    0 = SM2 + ML-DSA 都 sign + verify 通过
    1 = 任一环节失败
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keys-dir", default="/home/user/keys", help="密钥目录")
    parser.add_argument(
        "--transcript",
        default="mlkem-link self-test transcript",
        help="签名原文（一段可重复的字符串）",
    )
    args = parser.parse_args()

    keys = Path(args.keys_dir)
    sm2_sk = (keys / "server_sm2_identity.key").read_bytes()
    sm2_pk = (keys / "server_sm2_identity.pub").read_bytes()
    mldsa_sk = (keys / "server_mldsa_identity.key").read_bytes()
    mldsa_pk = (keys / "server_mldsa_identity.pub").read_bytes()
    print(f"sm2:   sk={len(sm2_sk)}B  pk={len(sm2_pk)}B")
    print(f"mldsa: sk={len(mldsa_sk)}B  pk={len(mldsa_pk)}B")

    sys.path.insert(0, "/home/user")
    from mlkem_link.auth import (  # type: ignore
        SigPolicy,
        get_mldsa_backend,
        get_sm2_backend,
        sign_transcript,
        verify_transcript,
    )

    print("loading sm2 backend...")
    sm2 = get_sm2_backend()
    print(f"  -> {sm2.name}")
    print("loading mldsa backend...")
    mldsa = get_mldsa_backend()
    print(f"  -> {mldsa.name}")

    transcript = args.transcript.encode("utf-8")
    if len(transcript) < 32:
        transcript = transcript.ljust(32, b"\x00")

    print("signing with DUAL_REQUIRED...")
    t0 = time.perf_counter()
    sm2_sig, mldsa_sig = sign_transcript(
        sm2, mldsa, sm2_sk, mldsa_sk, transcript, SigPolicy.DUAL_REQUIRED
    )
    sign_ms = (time.perf_counter() - t0) * 1000
    print(f"  sign: {sign_ms:.1f}ms (sm2={len(sm2_sig)}B, mldsa={len(mldsa_sig)}B)")

    print("verifying...")
    t0 = time.perf_counter()
    result = verify_transcript(
        sm2,
        mldsa,
        sm2_pk,
        mldsa_pk,
        transcript,
        sm2_sig,
        mldsa_sig,
        SigPolicy.DUAL_REQUIRED,
    )
    verify_ms = (time.perf_counter() - t0) * 1000
    print(f"  verify: {verify_ms:.1f}ms (ok={result.verified} sm2={result.sm2_ok} "
          f"mldsa={result.mldsa_ok} err={result.error})")

    if not result.verified:
        print("FAIL: verify failed", file=sys.stderr)
        return 1
    print("OK: DUAL_REQUIRED sign+verify roundtrip passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
