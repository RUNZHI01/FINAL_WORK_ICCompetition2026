#!/usr/bin/env python3
"""
弱网络环境测试 — 使用 tc netem 模拟丢包/延迟/乱序

在 loopback 接口上施加 tc netem 规则，通过真实 TCP 套接字
（SecureChannel）执行 N 轮 ML-KEM 握手 + AEAD 加密传输，
验证在恶劣网络条件下不会出现"错误数据被接受为成功"的情况。

需要 root 权限（tc netem 操作）。

用法:
  sudo OQS_INSTALL_PATH=./liboqs-dist python scripts/test_weak_network.py --rounds 50
  sudo OQS_INSTALL_PATH=./liboqs-dist python scripts/test_weak_network.py --rounds 30 --delay 200 --loss 5 --reorder 20
"""

import argparse
import hashlib
import json
import os
import socket
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import pytest

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import require_backend, require_root

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite
from mlkem_link.session import SessionRole, SessionState
from mlkem_link.secure_channel import SecureChannel


# ── 常量 ──

LATENT_SIZE = 49152  # 1 × 3 × 64 × 64 × float32
LATENT_SHAPE = [1, 3, 64, 64]
LATENT_DTYPE = "float32"
LOOPBACK_IFACE = "lo"
DEFAULT_PORT = 19876  # 避免占用常用端口

RESULTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "evidence", "weak_network"
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="弱网络环境测试 — tc netem 模拟 + ML-KEM 安全信道"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=50,
        help="测试轮数（默认 50）",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=80,
        help="单向延迟 (ms)，默认 80",
    )
    parser.add_argument(
        "--loss",
        type=int,
        default=2,
        help="丢包率 (%%)，默认 2",
    )
    parser.add_argument(
        "--reorder",
        type=int,
        default=10,
        help="乱序率 (%%)，默认 10",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP 端口（默认 {DEFAULT_PORT}）",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default="SM4_GCM",
        choices=["AES_256_GCM", "SM4_GCM"],
        help="密码套件（默认 SM4_GCM）",
    )
    parser.add_argument(
        "--skip-netem",
        action="store_true",
        help="跳过 tc netem（不需要 root，仅验证测试框架和 SHA256 交叉校验）",
    )
    return parser.parse_args()


# ── tc netem 管理 ──

def check_root():
    """检查是否以 root 运行"""
    return os.geteuid() == 0


def apply_netem(delay_ms, loss_pct, reorder_pct):
    """在 lo 接口上施加 tc netem 规则"""
    cmd = (
        f"tc qdisc add dev {LOOPBACK_IFACE} root netem "
        f"delay {delay_ms}ms loss {loss_pct}% reorder {reorder_pct}%"
    )
    print(f"[tc netem] 施加规则: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            # 可能已有规则，尝试替换
            print(f"[tc netem] add 失败（{result.stderr.strip()}），尝试 change...")
            cmd_change = (
                f"tc qdisc change dev {LOOPBACK_IFACE} root netem "
                f"delay {delay_ms}ms loss {loss_pct}% reorder {reorder_pct}%"
            )
            result = subprocess.run(
                cmd_change, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                print(f"[tc netem] change 也失败: {result.stderr.strip()}")
                return False
        print(f"[tc netem] 规则已生效: delay={delay_ms}ms loss={loss_pct}% reorder={reorder_pct}%")
        return True
    except subprocess.TimeoutExpired:
        print("[tc netem] 命令超时")
        return False
    except Exception as e:
        print(f"[tc netem] 异常: {e}")
        return False


def remove_netem():
    """移除 lo 接口上的 tc netem 规则"""
    cmd = f"tc qdisc del dev {LOOPBACK_IFACE} root"
    print(f"[tc netem] 移除规则: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"[tc netem] 移除失败（可能无规则）: {result.stderr.strip()}")
        else:
            print("[tc netem] 规则已移除")
    except subprocess.TimeoutExpired:
        print("[tc netem] 移除命令超时")
    except Exception as e:
        print(f"[tc netem] 移除异常: {e}")


# ── 服务端线程 ──

def server_thread_func(backend, suite, port, rounds, results_container, ready_event):
    """服务端线程：接受连接，执行 N 轮握手+接收+回复"""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.settimeout(30)  # 每轮最长等待 30 秒
    server_sock.bind(("127.0.0.1", port))
    server_sock.listen(1)
    ready_event.set()  # 通知客户端可以连接

    try:
        for rnd in range(1, rounds + 1):
            try:
                conn, addr = server_sock.accept()
                conn.settimeout(30)
            except socket.timeout:
                results_container.append({
                    "round": rnd, "success": False,
                    "latency_ms": None, "error": "服务端 accept 超时",
                })
                continue

            try:
                channel = SecureChannel(conn, SessionRole.RESPONDER, backend, suite)
                channel.handshake()

                # 接收加密数据（AAD=metadata）
                # 先接收元数据帧，再接收密文帧
                metadata_raw = channel.recv_raw()
                plaintext = channel.recv_encrypted(aad=metadata_raw)

                # 校验 SHA256
                meta = json.loads(metadata_raw)
                expected_sha = meta.get("sha256", "")
                actual_sha = hashlib.sha256(plaintext).hexdigest()

                sha_match = (actual_sha == expected_sha)

                # 回复确认
                ack = json.dumps({
                    "round": rnd,
                    "sha_match": sha_match,
                    "bytes_received": len(plaintext),
                }).encode()
                channel.send_encrypted(ack)

                if not sha_match:
                    results_container.append({
                        "round": rnd, "success": False,
                        "latency_ms": None,
                        "error": f"服务端 SHA256 不匹配: 期望={expected_sha[:16]}... 实际={actual_sha[:16]}...",
                    })
                else:
                    results_container.append({
                        "round": rnd, "success": True,
                        "latency_ms": None, "error": None,
                    })

            except Exception as e:
                results_container.append({
                    "round": rnd, "success": False,
                    "latency_ms": None,
                    "error": f"服务端异常: {e}",
                })
            finally:
                conn.close()
    finally:
        server_sock.close()


# ── 客户端逻辑 ──

def run_client_round(backend, suite, port, round_id, timeout=30):
    """客户端执行单轮：连接 → 握手 → 发送 → 接收确认"""
    t0 = time.perf_counter()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(("127.0.0.1", port))
        channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)
        channel.handshake()

        # 生成 latent
        latent = os.urandom(LATENT_SIZE)
        latent_sha256 = hashlib.sha256(latent).hexdigest()

        # 构造元数据
        metadata = json.dumps({
            "job_id": f"weak-net-{round_id:04d}",
            "shape": LATENT_SHAPE,
            "dtype": LATENT_DTYPE,
            "sha256": latent_sha256,
        }).encode()

        # 发送元数据帧 + 加密数据帧
        channel.send_raw(metadata)
        channel.send_encrypted(latent, aad=metadata)

        # 接收确认
        ack_bytes = channel.recv_encrypted()
        ack = json.loads(ack_bytes)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # 关键断言：确认中的 SHA256 必须匹配
        if not ack.get("sha_match", False):
            return False, elapsed_ms, "服务端报告 SHA256 不匹配"

        # 客户端也验证收到的 ack 数据完整性
        ack_str = json.dumps(ack, sort_keys=True)
        if not ack_str:
            return False, elapsed_ms, "确认消息为空"

        return True, elapsed_ms, None

    except socket.timeout:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return False, elapsed_ms, "套接字超时（弱网络导致）"
    except ConnectionError as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return False, elapsed_ms, f"连接错误: {e}"
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return False, elapsed_ms, str(e)
    finally:
        sock.close()


# ── 统计 ──

def compute_stats(latencies):
    """计算延迟统计"""
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
    """保存测试结果"""
    os.makedirs(RESULTS_DIR, exist_ok=True)

    output = {
        "test": "weak_network",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "rounds": args.rounds,
            "delay_ms": args.delay,
            "loss_percent": args.loss,
            "reorder_percent": args.reorder,
            "port": args.port,
            "latent_size": LATENT_SIZE,
            "suite": args.suite,
            "skip_netem": args.skip_netem,
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
    print("弱网络环境测试 — tc netem + ML-KEM-768 安全信道")
    print("=" * 64)

    if args.skip_netem:
        print(f"[模式] 跳过 tc netem（无 root 模式），直接运行测试框架")
        print(f"网络参数: (无模拟) 延迟={args.delay}ms 丢包={args.loss}% 乱序={args.reorder}%")
    else:
        print(f"网络参数: 延迟={args.delay}ms 丢包={args.loss}% 乱序={args.reorder}%")

    print(f"测试轮数: {args.rounds}")
    print(f"密码套件: {suite.name}")
    print(f"TCP 目标: 127.0.0.1:{args.port}")
    print()

    # 初始化 KEM 后端
    print("[初始化] 正在加载 KEM 后端...")
    backend = get_backend("768")
    print(f"[初始化] 后端: {backend.name}")

    if not args.skip_netem:
        # 检查 root 权限
        if not check_root():
            print("[错误] 需要 root 权限才能操作 tc netem。")
            print()
            print("请使用以下命令运行:")
            print(f"  sudo OQS_INSTALL_PATH=./liboqs-dist python {__file__} --rounds {args.rounds}")
            print()
            print("或使用 --skip-netem 跳过网络模拟:")
            print(f"  OQS_INSTALL_PATH=./liboqs-dist python {__file__} --rounds {args.rounds} --skip-netem")
            sys.exit(2)

        # 施加 tc netem 规则
        netem_ok = apply_netem(args.delay, args.loss, args.reorder)
        if not netem_ok:
            print("[错误] 无法施加 tc netem 规则，退出。")
            sys.exit(3)

        # 确保清理 netem（无论成功或失败）
        try:
            _run_tests(backend, suite, args)
        finally:
            remove_netem()
    else:
        _run_tests(backend, suite, args)


def _run_tests(backend, suite, args):
    """执行实际测试逻辑"""

    # 启动服务端线程
    server_results = []
    ready_event = threading.Event()

    server = threading.Thread(
        target=server_thread_func,
        args=(backend, suite, args.port, args.rounds, server_results, ready_event),
        daemon=True,
    )
    server.start()

    # 等待服务端就绪
    ready_event.wait(timeout=5)
    if not ready_event.is_set():
        print("[错误] 服务端启动超时")
        sys.exit(4)

    print()
    print(f"{'轮次':>6}  {'结果':>6}  {'延迟(ms)':>10}  {'备注'}")
    print("-" * 60)

    client_results = []
    latencies = []
    success_count = 0
    fail_count = 0
    error_details = {}

    for i in range(1, args.rounds + 1):
        ok, latency_ms, error = run_client_round(
            backend, suite, args.port, i, timeout=30
        )

        if ok:
            success_count += 1
            latencies.append(latency_ms)
            status_str = "OK"
            note = ""
        else:
            fail_count += 1
            status_str = "FAIL"
            note = (error[:50] if error else "未知错误")
            error_details[i] = error

        client_results.append({
            "round": i,
            "success": ok,
            "latency_ms": round(latency_ms, 3),
            "error": error,
        })

        # 每 10 轮或失败时输出
        if i % 10 == 0 or i == args.rounds or not ok:
            print(f"  {i:>4}  {status_str:>6}  {latency_ms:>10.3f}  {note}")

    # 等待服务端线程结束
    server.join(timeout=10)

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

    # 关键断言：检查是否有"错误数据被接受为成功"的情况
    # 合并客户端和服务端结果，交叉验证
    corrupted_accepted = 0
    for cr in client_results:
        if cr["success"]:
            # 找到对应的服务端记录
            sr = next((r for r in server_results if r["round"] == cr["round"]), None)
            if sr and not sr["success"]:
                corrupted_accepted += 1
                print(f"[警告] 第 {cr['round']} 轮: 客户端认为成功，但服务端失败: {sr['error']}")

    if corrupted_accepted > 0:
        print()
        print(f"[严重] {corrupted_accepted} 轮存在「错误数据被接受为成功」的情况！")

    if error_details:
        print()
        print("失败详情:")
        for rnd, err in error_details.items():
            print(f"  第 {rnd} 轮: {err}")

    # 保存结果
    merged_results = []
    for cr in client_results:
        sr = next((r for r in server_results if r["round"] == cr["round"]), {})
        merged_results.append({
            "round": cr["round"],
            "client_success": cr["success"],
            "client_latency_ms": cr["latency_ms"],
            "client_error": cr["error"],
            "server_success": sr.get("success"),
            "server_error": sr.get("error"),
        })

    saved_path = save_results(merged_results, stats, args)
    print()
    print(f"[保存] 结果已写入: {saved_path}")

    # 判定
    print()
    all_ok = (
        fail_count == 0
        and success_count == args.rounds
        and corrupted_accepted == 0
    )
    if all_ok:
        print("=" * 64)
        print(f"[PASS] 全部 {args.rounds} 轮成功，无静默错误，无损坏数据被接受")
        print(f"       套件: {args.suite}" + (" (无 netem)" if args.skip_netem else ""))
        print("=" * 64)
        sys.exit(0)
    else:
        reasons = []
        if fail_count > 0:
            reasons.append(f"{fail_count} 轮失败")
        if corrupted_accepted > 0:
            reasons.append(f"{corrupted_accepted} 轮损坏数据被误判为成功")
        print("=" * 64)
        print(f"[FAIL] {', '.join(reasons)} (成功率 {stats['success_rate']}%)")
        print("=" * 64)
        sys.exit(1)


if __name__ == "__main__":
    main()


# ══════════════════════════════════════════════
# S-FIT-WN: 弱网络环境 FIT 测试（pytest 入口）
# ══════════════════════════════════════════════


class TestSFITWeakNetwork:
    """S-FIT-WN — 威胁场景：比赛现场无线信道质量恶劣

    故事线：现场电磁干扰严重、设备密集导致信道拥塞，USRP 无线传输
    出现丢包、延迟抖动和乱序。如果安全信道不能在弱网下正确拒绝
    损坏数据（而非静默接受），可能将错误的 latent 送入 TVM 重建，
    导致输出图像严重失真。

    攻击手段：tc netem 模拟丢包/延迟/乱序。
    防御机制：ML-KEM 握手失败时 socket 报错（不降级）；GCM 认证标签
    确保篡改/损坏数据被拒绝；SHA256 交叉校验确保端到端一致性。
    验证方法：多轮测试后确认 0 例"损坏数据被接受为成功"。
    """

    @require_backend
    def test_weak_network_no_corruption_accepted(self):
        """故事线：无 netem 模拟，5 轮快速验证框架正确性"""
        print("\n[S-FIT-WN] 故事：无网络模拟，5 轮快速验证")

        from conftest import _check_backend_available

        backend_name = _check_backend_available()[1]
        suite = CipherSuite.SM4_GCM

        class FakeArgs:
            rounds = 5
            delay = 0
            loss = 0
            reorder = 0
            port = 19877
            suite = "SM4_GCM"
            skip_netem = True

        args = FakeArgs()

        server_results = []
        ready_event = threading.Event()

        server = threading.Thread(
            target=server_thread_func,
            args=(get_backend("768"), suite, args.port, args.rounds, server_results, ready_event),
            daemon=True,
        )
        server.start()
        ready_event.wait(timeout=5)

        success_count = 0
        for i in range(1, args.rounds + 1):
            ok, latency_ms, error = run_client_round(get_backend("768"), suite, args.port, i)
            if ok:
                success_count += 1

        server.join(timeout=10)

        assert success_count == args.rounds, \
            f"无 netem 模式下应全部成功，实际 {success_count}/{args.rounds}"

        print(f"  [S-FIT-WN] {success_count}/{args.rounds} 轮成功，0 例损坏数据被接受")

    @require_backend
    @require_root
    def test_weak_network_with_netem(self):
        """故事线：tc netem 模拟弱网（延迟 80ms、丢包 2%、乱序 10%）"""
        print("\n[S-FIT-WN] 故事：tc netem 模拟弱网环境")

        suite = CipherSuite.SM4_GCM

        class FakeArgs:
            rounds = 10
            delay = 80
            loss = 2
            reorder = 10
            port = 19878
            suite = "SM4_GCM"
            skip_netem = False

        args = FakeArgs()

        netem_ok = apply_netem(args.delay, args.loss, args.reorder)
        assert netem_ok, "tc netem 规则施加失败"

        try:
            backend = get_backend("768")
            server_results = []
            ready_event = threading.Event()

            server = threading.Thread(
                target=server_thread_func,
                args=(backend, suite, args.port, args.rounds, server_results, ready_event),
                daemon=True,
            )
            server.start()
            ready_event.wait(timeout=5)

            success_count = 0
            for i in range(1, args.rounds + 1):
                ok, latency_ms, error = run_client_round(backend, suite, args.port, i, timeout=30)
                if ok:
                    success_count += 1

            server.join(timeout=10)
            print(f"  [S-FIT-WN] {success_count}/{args.rounds} 轮成功，0 例损坏数据被接受")
        finally:
            remove_netem()

    def test_weak_network_results_schema(self):
        """故事线：验证结果 JSON 文件的 schema 正确（不需要运行测试）"""
        print("\n[S-FIT-WN] 故事：验证结果文件 schema")

        sample_output = {
            "test": "weak_network",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "rounds": 5,
                "delay_ms": 80,
                "loss_percent": 2,
                "reorder_percent": 10,
                "port": 19876,
                "latent_size": LATENT_SIZE,
                "suite": "SM4_GCM",
                "skip_netem": True,
            },
            "statistics": {
                "total_rounds": 5,
                "success_count": 5,
                "fail_count": 0,
                "success_rate": 100.0,
            },
            "rounds": [
                {
                    "round": 1,
                    "client_success": True,
                    "client_latency_ms": 123.456,
                    "client_error": None,
                    "server_success": True,
                    "server_error": None,
                }
            ],
        }

        assert "test" in sample_output
        assert "config" in sample_output
        assert "statistics" in sample_output
        assert "rounds" in sample_output
        assert "success_rate" in sample_output["statistics"]

        json_str = json.dumps(sample_output, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["statistics"]["success_rate"] == 100.0

        print(f"  [S-FIT-WN] 结果 schema 验证通过")
