#!/usr/bin/env python3
"""
ML-KEM 安全信道性能基准测试

测量完整链路各阶段延迟：
  握手 (keygen + encaps + decaps)
  加密 (AEAD encrypt)
  解密 (AEAD decrypt)
  端到端 (握手 + 加密 + 解密)

支持三组对比：AES-256-GCM / SM4-128-GCM / 无加密 baseline

用法:
  source ../.venv/bin/activate
  OQS_INSTALL_PATH=../liboqs-dist python scripts/benchmark.py --rounds 100
  OQS_INSTALL_PATH=../liboqs-dist python scripts/benchmark.py --rounds 50 --suite SM4_GCM
  OQS_INSTALL_PATH=../liboqs-dist python scripts/benchmark.py --rounds 50 --no-encrypt
"""

import argparse
import csv
import json
import os
import sys
import time
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite, LinkEncryptor
from mlkem_link.session import MLKEMSession, SessionRole
from mlkem_link.kdf import hkdf_sha256


def create_sessions(suite: CipherSuite):
    """创建一对完成握手的 session"""
    backend = get_backend("768")
    ini = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
    res = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)
    pk = ini.start_handshake()
    ct = res.respond_handshake(pk)
    ini.complete_handshake(ct)
    return ini, res, backend


def bench_handshake(suite: CipherSuite):
    """测量握手各阶段延迟"""
    backend = get_backend("768")

    t0 = time.perf_counter()
    keypair = backend.keygen()
    t_keygen = time.perf_counter()

    enc_result = backend.encaps(keypair.public_key)
    t_encaps = time.perf_counter()

    backend.decaps(keypair.secret_key, enc_result.ciphertext,
                   public_key=keypair.public_key)
    t_decaps = time.perf_counter()

    return {
        "keygen_ms": (t_keygen - t0) * 1000,
        "encaps_ms": (t_encaps - t_keygen) * 1000,
        "decaps_ms": (t_decaps - t_encaps) * 1000,
        "handshake_total_ms": (t_decaps - t0) * 1000,
    }


def bench_encrypt(suite: CipherSuite, data: bytes):
    """测量加密延迟"""
    key_len = 32 if suite == CipherSuite.AES_256_GCM else 16
    key = hkdf_sha256(os.urandom(32), info=b"bench", length=key_len)
    enc = LinkEncryptor(suite)

    t0 = time.perf_counter()
    payload = enc.encrypt(key, data)
    t_enc = time.perf_counter()

    t1 = time.perf_counter()
    enc.decrypt(key, payload)
    t_dec = time.perf_counter()

    return {
        "encrypt_ms": (t_enc - t0) * 1000,
        "decrypt_ms": (t_dec - t1) * 1000,
        "payload_overhead_bytes": len(payload.to_bytes()) - len(data),
    }


def bench_full_round(suite: CipherSuite, data: bytes, aad: bytes = None):
    """测量完整一轮：握手 + 加密 + 解密"""
    t0 = time.perf_counter()
    ini, res, _ = create_sessions(suite)
    t_handshake = time.perf_counter()

    t1 = time.perf_counter()
    encrypted = ini.encrypt(data, aad=aad)
    t_encrypt = time.perf_counter()

    t2 = time.perf_counter()
    decrypted = res.decrypt(encrypted, aad=aad)
    t_decrypt = time.perf_counter()

    assert decrypted == data, "数据完整性校验失败"

    return {
        "handshake_ms": (t_handshake - t0) * 1000,
        "encrypt_ms": (t_encrypt - t1) * 1000,
        "decrypt_ms": (t_decrypt - t2) * 1000,
        "e2e_ms": (t_decrypt - t0) * 1000,
    }


def bench_baseline(data: bytes):
    """无加密 baseline：仅测量数据拷贝开销"""
    t0 = time.perf_counter()
    _ = bytes(data)  # 模拟传输（内存拷贝）
    t1 = time.perf_counter()
    return {
        "handshake_ms": 0.0,
        "encrypt_ms": 0.0,
        "decrypt_ms": 0.0,
        "e2e_ms": (t1 - t0) * 1000,
    }


def fmt_stat(values):
    """返回均值/中位/标准差/最小/最大"""
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def print_summary(label: str, stats: dict, unit: str = "ms"):
    """打印一组统计数据"""
    print(f"  {label}:")
    for name, vals in stats.items():
        s = fmt_stat(vals)
        print(f"    {name:20s}  "
              f"mean={s['mean']:8.2f} {unit}  "
              f"med={s['median']:8.2f}  "
              f"std={s['stdev']:6.2f}  "
              f"min={s['min']:8.2f}  "
              f"max={s['max']:8.2f}")


def main():
    parser = argparse.ArgumentParser(description="ML-KEM 安全信道性能基准")
    parser.add_argument("--rounds", type=int, default=50, help="每组的测试轮数")
    parser.add_argument("--suite", choices=["AES_256_GCM", "SM4_GCM"], default=None,
                        help="密码套件（不指定则两组都跑）")
    parser.add_argument("--no-encrypt", action="store_true",
                        help="跑无加密 baseline")
    parser.add_argument("--payload-size", type=int, default=49152,
                        help="模拟 latent 大小（字节，默认 49152 = 1×3×64×64×4）")
    parser.add_argument("--output", default=None, help="CSV 输出路径")
    parser.add_argument("--json-output", default=None, help="JSON 输出路径")
    args = parser.parse_args()

    suites_to_run = []
    if args.no_encrypt:
        suites_to_run.append(("baseline", None))
    elif args.suite:
        suites_to_run.append((args.suite, CipherSuite[args.suite]))
    else:
        suites_to_run.append(("AES_256_GCM", CipherSuite.AES_256_GCM))
        suites_to_run.append(("SM4_GCM", CipherSuite.SM4_GCM))

    data = os.urandom(args.payload_size)
    aad = b'{"job_id":"bench","shape":[1,3,64,64]}'

    print("=" * 70)
    print("ML-KEM 安全信道性能基准")
    print("=" * 70)
    print(f"后端: {get_backend('768').name}")
    print(f"载荷: {args.payload_size} bytes ({args.payload_size / 1024:.1f} KB)")
    print(f"轮数: {args.rounds}")
    print()

    all_rows = []
    all_stats = {}

    for suite_name, suite in suites_to_run:
        print(f"── {suite_name} ──")
        rows = []

        # 握手 benchmark（仅加密组）
        handshake_rows = []
        if suite is not None:
            for i in range(args.rounds):
                h = bench_handshake(suite)
                handshake_rows.append(h)
                rows.append({
                    "round": i, "suite": suite_name,
                    "handshake_ms": h["handshake_total_ms"],
                    "encrypt_ms": 0, "decrypt_ms": 0,
                    "e2e_ms": h["handshake_total_ms"],
                })

            hs = {
                "keygen": [r["keygen_ms"] for r in handshake_rows],
                "encaps": [r["encaps_ms"] for r in handshake_rows],
                "decaps": [r["decaps_ms"] for r in handshake_rows],
                "handshake_total": [r["handshake_total_ms"] for r in handshake_rows],
            }
            print_summary("握手 (每轮独立)", hs)

            # 纯加密 benchmark
            enc_rows = []
            for _ in range(args.rounds):
                e = bench_encrypt(suite, data)
                enc_rows.append(e)
            es = {
                "encrypt": [r["encrypt_ms"] for r in enc_rows],
                "decrypt": [r["decrypt_ms"] for r in enc_rows],
            }
            print_summary("AEAD 加解密 (49KB)", es)
            overhead = enc_rows[0]["payload_overhead_bytes"]
            print(f"    overhead: {overhead} bytes "
                  f"({overhead / args.payload_size * 100:.1f}%)")

        # 完整轮 benchmark
        full_rows = []
        for i in range(args.rounds):
            if suite is None:
                f = bench_baseline(data)
            else:
                f = bench_full_round(suite, data, aad)
            full_rows.append(f)
            if suite is not None:
                rows.append({
                    "round": i, "suite": suite_name,
                    "handshake_ms": f["handshake_ms"],
                    "encrypt_ms": f["encrypt_ms"],
                    "decrypt_ms": f["decrypt_ms"],
                    "e2e_ms": f["e2e_ms"],
                })
            else:
                rows.append({
                    "round": i, "suite": "baseline",
                    "handshake_ms": 0, "encrypt_ms": 0,
                    "decrypt_ms": 0, "e2e_ms": f["e2e_ms"],
                })

        fs = {
            "handshake": [r["handshake_ms"] for r in full_rows],
            "encrypt": [r["encrypt_ms"] for r in full_rows],
            "decrypt": [r["decrypt_ms"] for r in full_rows],
            "e2e_total": [r["e2e_ms"] for r in full_rows],
        }
        print_summary("完整轮 (握手+加密+解密)", fs)
        print()

        all_rows.extend(rows)
        all_stats[suite_name] = {
            "handshake": fmt_stat(fs["handshake"]),
            "encrypt": fmt_stat(fs["encrypt"]),
            "decrypt": fmt_stat(fs["decrypt"]),
            "e2e": fmt_stat(fs["e2e_total"]),
        }

    # 输出 CSV
    if args.output:
        with open(args.output, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "round", "suite", "handshake_ms", "encrypt_ms",
                "decrypt_ms", "e2e_ms",
            ])
            w.writeheader()
            w.writerows(all_rows)
        print(f"CSV 已保存: {args.output}")

    # 输出 JSON
    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump({
                "backend": get_backend("768").name,
                "payload_bytes": args.payload_size,
                "rounds": args.rounds,
                "suites": all_stats,
            }, f, indent=2)
        print(f"JSON 已保存: {args.json_output}")

    print("=" * 70)
    print("基准测试完成")


if __name__ == "__main__":
    main()
