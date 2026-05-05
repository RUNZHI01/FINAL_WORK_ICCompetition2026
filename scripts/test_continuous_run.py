#!/usr/bin/env python3
"""
连续运行稳定性测试 — ML-KEM-768 + AEAD 安全语义通信

对 N 轮完整的「握手 → 加密 → 解密 → 校验」流程进行压力测试，
收集每轮延迟，最终输出统计信息并判定 PASS/FAIL。

用法:
  OQS_INSTALL_PATH=./liboqs-dist python scripts/test_continuous_run.py --rounds 100
  OQS_INSTALL_PATH=./liboqs-dist python scripts/test_continuous_run.py --rounds 50 --suite SM4_GCM
"""

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite, EncryptedPayload
from mlkem_link.session import SessionRole, SessionState
from mlkem_link.session import MLKEMSession


# ── 常量 ──

LATENT_SIZE = 49152  # 1 × 3 × 64 × 64 × float32 = 49152 bytes
LATENT_SHAPE = [1, 3, 64, 64]
LATENT_DTYPE = "float32"

RESULTS_DIR = os.environ.get(
    "RESULTS_DIR",
    os.path.join(os.path.expanduser("~"), "artifacts", "evidence", "continuous_run"),
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="连续运行稳定性测试 — ML-KEM-768 + AEAD 安全语义通信"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=100,
        help="测试轮数（默认 100）",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default="SM4_GCM",
        choices=["AES_256_GCM", "SM4_GCM"],
        help="密码套件（默认 SM4_GCM）",
    )
    return parser.parse_args()


def run_single_round(backend, suite, round_id):
    """执行单轮完整安全通信流程，返回 (成功与否, 延迟ms, 错误信息)"""
    try:
        t0 = time.perf_counter()

        # 1. 创建 Initiator + Responder 会话
        initiator = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
        responder = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)

        # 2. 握手
        pk = initiator.start_handshake()
        ct = responder.respond_handshake(pk)
        initiator.complete_handshake(ct)

        if initiator.state != SessionState.READY or responder.state != SessionState.READY:
            return False, 0.0, f"握手后状态异常: ini={initiator.state}, res={responder.state}"

        # 3. 生成随机 latent (1×3×64×64 float32)
        latent = os.urandom(LATENT_SIZE)
        latent_sha256 = hashlib.sha256(latent).hexdigest()

        # 4. 构造元数据 JSON
        metadata = json.dumps({
            "job_id": f"continuous-{round_id:04d}",
            "shape": LATENT_SHAPE,
            "dtype": LATENT_DTYPE,
            "sha256": latent_sha256,
        }).encode()

        # 5. 加密（AAD=metadata）
        encrypted = initiator.encrypt(latent, aad=metadata)

        # 模拟"传输"：序列化 → 反序列化
        wire_bytes = encrypted.to_bytes()
        restored_payload = EncryptedPayload.from_bytes(wire_bytes, suite)

        # 6. 解密并校验 SHA256
        decrypted = responder.decrypt(restored_payload, aad=metadata)
        decrypted_sha256 = hashlib.sha256(decrypted).hexdigest()

        if decrypted_sha256 != latent_sha256:
            return False, 0.0, (
                f"SHA256 不匹配: 原文={latent_sha256[:16]}... "
                f"解密={decrypted_sha256[:16]}..."
            )

        if len(decrypted) != LATENT_SIZE:
            return False, 0.0, (
                f"长度不匹配: 原文={LATENT_SIZE}, 解密={len(decrypted)}"
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return True, elapsed_ms, None

    except Exception as e:
        return False, 0.0, str(e)


def compute_stats(latencies):
    """计算延迟统计信息"""
    if not latencies:
        return {}
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    p95_idx = int(n * 0.95)
    return {
        "count": n,
        "min_ms": round(sorted_l[0], 3),
        "max_ms": round(sorted_l[-1], 3),
        "mean_ms": round(statistics.mean(sorted_l), 3),
        "median_ms": round(statistics.median(sorted_l), 3),
        "stdev_ms": round(statistics.stdev(sorted_l), 3) if n > 1 else 0.0,
        "p95_ms": round(sorted_l[min(p95_idx, n - 1)], 3),
    }


def save_results(results, stats, args):
    """保存测试结果到 artifacts/evidence/continuous_run/results.json"""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    output = {
        "test": "continuous_run",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "rounds": args.rounds,
            "suite": args.suite,
            "latent_size": LATENT_SIZE,
            "latent_shape": LATENT_SHAPE,
            "latent_dtype": LATENT_DTYPE,
        },
        "statistics": stats,
        "rounds": results,
    }

    path = os.path.join(RESULTS_DIR, "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return path


def main():
    args = parse_args()
    suite = CipherSuite[args.suite]

    print("=" * 64)
    print("连续运行稳定性测试 — ML-KEM-768 + AEAD 安全语义通信")
    print("=" * 64)
    print(f"密码套件: {suite.value}")
    print(f"测试轮数: {args.rounds}")
    print(f"Latent:   {LATENT_SIZE} bytes ({LATENT_SHAPE}, {LATENT_DTYPE})")
    print()

    # 初始化 KEM 后端
    print("[初始化] 正在加载 KEM 后端...")
    backend = get_backend("768")
    print(f"[初始化] 后端: {backend.name}")
    print()

    # 运行测试轮次
    results = []
    latencies = []
    success_count = 0
    fail_count = 0
    error_details = {}

    print(f"{'轮次':>6}  {'结果':>6}  {'延迟(ms)':>10}  {'备注'}")
    print("-" * 50)

    for i in range(1, args.rounds + 1):
        ok, latency_ms, error = run_single_round(backend, suite, i)

        if ok:
            success_count += 1
            latencies.append(latency_ms)
            status_str = "OK"
            note = ""
        else:
            fail_count += 1
            status_str = "FAIL"
            note = error[:40] if error else "未知错误"
            error_details[i] = error

        results.append({
            "round": i,
            "success": ok,
            "latency_ms": round(latency_ms, 3) if ok else None,
            "error": error,
        })

        # 每 10 轮或最后一轮输出进度
        if i % 10 == 0 or i == args.rounds or not ok:
            print(f"  {i:>4}  {status_str:>6}  {latency_ms:>10.3f}  {note}")

    print()

    # 统计
    stats = compute_stats(latencies)
    stats["total_rounds"] = args.rounds
    stats["success_count"] = success_count
    stats["fail_count"] = fail_count
    stats["success_rate"] = round(success_count / args.rounds * 100, 2) if args.rounds > 0 else 0.0

    print("=" * 64)
    print("统计结果")
    print("=" * 64)
    print(f"  总轮数:     {stats['total_rounds']}")
    print(f"  成功:       {stats['success_count']}")
    print(f"  失败:       {stats['fail_count']}")
    print(f"  成功率:     {stats['success_rate']}%")
    if latencies:
        print(f"  最小延迟:   {stats['min_ms']:.3f} ms")
        print(f"  最大延迟:   {stats['max_ms']:.3f} ms")
        print(f"  平均延迟:   {stats['mean_ms']:.3f} ms")
        print(f"  中位延迟:   {stats['median_ms']:.3f} ms")
        print(f"  标准差:     {stats['stdev_ms']:.3f} ms")
        print(f"  P95 延迟:   {stats['p95_ms']:.3f} ms")

    if error_details:
        print()
        print("失败详情:")
        for rnd, err in error_details.items():
            print(f"  第 {rnd} 轮: {err}")

    # 保存结果
    saved_path = save_results(results, stats, args)
    print()
    print(f"[保存] 结果已写入: {saved_path}")

    # 判定
    print()
    all_ok = (fail_count == 0) and (success_count == args.rounds)
    if all_ok:
        print("=" * 64)
        print("[PASS] 全部 {0} 轮成功，无静默错误".format(args.rounds))
        print("=" * 64)
        sys.exit(0)
    else:
        print("=" * 64)
        print(
            f"[FAIL] {fail_count}/{args.rounds} 轮失败 "
            f"(成功率 {stats['success_rate']}%)"
        )
        print("=" * 64)
        sys.exit(1)


if __name__ == "__main__":
    main()
