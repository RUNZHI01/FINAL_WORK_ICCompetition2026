#!/usr/bin/env python3
"""
CE-03: 资源压力测试 — CPU/内存压力下的安全语义通信

在 stress-ng 施加 CPU/内存压力的同时，运行 secure E2E 测试，
验证飞腾派负载波动下系统仍可控。

用法:
  # 需要先安装 stress-ng: sudo apt-get install -y stress-ng
  # 然后运行:
  OQS_INSTALL_PATH=../liboqs-dist python scripts/test_resource_stress.py --rounds 30

  # 如果没有 stress-ng，用 --no-stress 跳过压力注入（仅跑基准）
  OQS_INSTALL_PATH=../liboqs-dist python scripts/test_resource_stress.py --rounds 30 --no-stress
"""

import argparse
import json
import math
import multiprocessing
import os
import subprocess
import sys
import time
import hashlib
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite
from mlkem_link.session import MLKEMSession, SessionRole


# ── Python-based CPU stressor (fallback when stress-ng unavailable) ──

def _cpu_burn_worker(stop_event):
    """子进程：持续 CPU 密集计算，直到 stop_event 被设置。"""
    while not stop_event.is_set():
        for _ in range(10000):
            math.factorial(100)


class PythonCPUStress:
    """用 Python 多进程模拟 CPU 压力，作为 stress-ng 的 fallback。"""

    def __init__(self, cpu_workers=3):
        self.cpu_workers = cpu_workers
        self.stop_event = multiprocessing.Event()
        self.processes = []

    def start(self):
        for _ in range(self.cpu_workers):
            p = multiprocessing.Process(
                target=_cpu_burn_worker, args=(self.stop_event,), daemon=True)
            p.start()
            self.processes.append(p)
        time.sleep(0.5)
        alive = sum(1 for p in self.processes if p.is_alive())
        return alive > 0

    def stop(self):
        self.stop_event.set()
        for p in self.processes:
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()
        self.processes.clear()


def start_stress_ng(cpu_workers: int = 3, vm_workers: int = 1,
                    vm_bytes: str = "512M", timeout: int = 300):
    """启动 stress-ng 压力进程。

    Returns:
        subprocess.Popen 对象，或 None（如果 stress-ng 不可用）
    """
    try:
        cmd = [
            "stress-ng",
            f"--cpu", str(cpu_workers),
            f"--vm", str(vm_workers),
            f"--vm-bytes", vm_bytes,
            "--timeout", str(timeout),
            "--metrics-brief",
        ]
        print(f"[压力] 启动 stress-ng: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 等一小段时间让压力生效
        time.sleep(1)
        if proc.poll() is not None:
            print("[压力] stress-ng 启动后立即退出，可能不可用")
            return None
        print(f"[压力] stress-ng PID={proc.pid} 运行中")
        return proc
    except FileNotFoundError:
        print("[压力] stress-ng 未安装，跳过压力注入")
        print("       安装: sudo apt-get install -y stress-ng")
        return None


def stop_stress_ng(proc):
    """停止 stress-ng 进程。"""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[压力] stress-ng 已停止")


def run_single_round(backend, suite, round_id):
    """运行单轮 secure E2E。

    Returns:
        dict: {round, status, latency_ms, error_code, detail}
    """
    t0 = time.perf_counter()
    try:
        # 创建会话
        ini = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
        res = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)

        # KEM 握手
        pk = ini.start_handshake()
        ct = res.respond_handshake(pk)
        ini.complete_handshake(ct)
        assert ini.is_ready and res.is_ready

        # 加密 latent
        latent = os.urandom(49152)
        aad = json.dumps({
            "job_id": f"ce03-{round_id:04d}",
            "shape": [1, 3, 64, 64],
            "dtype": "float32",
        }).encode()
        enc = ini.encrypt(latent, aad=aad)

        # 解密验证
        dec = res.decrypt(enc, aad=aad)

        # SHA256 校验
        sha_orig = hashlib.sha256(latent).hexdigest()
        sha_dec = hashlib.sha256(dec).hexdigest()
        assert sha_orig == sha_dec, "SHA256 不匹配！"

        ms = (time.perf_counter() - t0) * 1000
        return {"round": round_id, "status": "ok", "latency_ms": round(ms, 3),
                "error_code": "", "detail": ""}

    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return {"round": round_id, "status": "fail", "latency_ms": round(ms, 3),
                "error_code": "E_STRESS_ROUND_FAIL", "detail": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="CE-03: 资源压力下的安全语义通信测试")
    parser.add_argument("--rounds", type=int, default=30,
                        help="测试轮数 (默认 30)")
    parser.add_argument("--suite", default="SM4_GCM",
                        choices=["AES_256_GCM", "SM4_GCM"],
                        help="密码套件 (默认 SM4_GCM)")
    parser.add_argument("--cpu", type=int, default=3,
                        help="stress-ng CPU 压力线程数 (默认 3)")
    parser.add_argument("--vm", type=int, default=1,
                        help="stress-ng 内存压力线程数 (默认 1)")
    parser.add_argument("--vm-bytes", default="512M",
                        help="stress-ng 每线程内存分配 (默认 512M)")
    parser.add_argument("--no-stress", action="store_true",
                        help="跳过 stress-ng，仅跑基准")
    args = parser.parse_args()

    suite = CipherSuite[args.suite]

    print("=" * 64)
    print("CE-03: 资源压力测试 — 安全语义通信")
    print("=" * 64)
    print(f"测试轮数:   {args.rounds}")
    print(f"密码套件:   {suite.value}")
    print(f"压力参数:   CPU={args.cpu}, VM={args.vm}x{args.vm_bytes}")
    print(f"跳过压力:   {'是' if args.no_stress else '否'}")
    print()

    # 初始化后端
    backend = get_backend("768")
    print(f"KEM 后端:   {backend.name}")
    print()

    # 启动压力
    stress_proc = None
    py_stress = None
    stress_mode = "none"
    if not args.no_stress:
        stress_proc = start_stress_ng(
            cpu_workers=args.cpu, vm_workers=args.vm,
            vm_bytes=args.vm_bytes, timeout=args.rounds * 2 + 60)
        if stress_proc:
            stress_mode = "stress-ng"
        else:
            # Fallback: Python CPU stress
            print("[压力] 使用 Python 多进程 CPU 压力替代 stress-ng")
            py_stress = PythonCPUStress(cpu_workers=args.cpu)
            if py_stress.start():
                stress_mode = "python-cpu"
                print(f"[压力] Python CPU 压力已启动 ({args.cpu} workers)")
            else:
                print("[压力] Python CPU 压力启动失败，跑基准模式")

    try:
        # 运行测试
        results = []
        ok_count = 0
        fail_count = 0
        silent_errors = 0

        for i in range(1, args.rounds + 1):
            r = run_single_round(backend, suite, i)
            results.append(r)

            if r["status"] == "ok":
                ok_count += 1
            else:
                fail_count += 1
                if not r.get("error_code"):
                    silent_errors += 1

            if i % 10 == 0:
                recent = [x["latency_ms"] for x in results[-10:]
                          if x["status"] == "ok"]
                if recent:
                    med = statistics.median(recent)
                    print(f"  [{i:3d}/{args.rounds}] 成功={ok_count} "
                          f"失败={fail_count} 最近中位={med:.2f}ms")

        # 停止压力
        stop_stress_ng(stress_proc)
        if py_stress:
            py_stress.stop()
            print("[压力] Python CPU 压力已停止")

        # 统计
        latencies = [x["latency_ms"] for x in results if x["status"] == "ok"]
        print()
        print("=" * 64)
        print("统计结果")
        print("=" * 64)
        print(f"总轮数:     {args.rounds}")
        print(f"成功:       {ok_count}")
        print(f"失败:       {fail_count}")
        print(f"成功率:     {ok_count/args.rounds*100:.1f}%")
        print(f"静默错误:   {silent_errors}")

        if latencies:
            print(f"延迟统计 (ms):")
            print(f"  中位: {statistics.median(latencies):.3f}")
            print(f"  均值: {statistics.mean(latencies):.3f}")
            print(f"  P95:  {sorted(latencies)[int(len(latencies)*0.95)]:.3f}")
            print(f"  最小: {min(latencies):.3f}")
            print(f"  最大: {max(latencies):.3f}")
            if len(latencies) > 1:
                print(f"  标准差: {statistics.stdev(latencies):.3f}")

        # 判定
        print()
        all_ok = fail_count == 0 and silent_errors == 0
        if all_ok:
            print(f"[PASS] 全部 {args.rounds} 轮成功，无静默错误")
        else:
            print(f"[FAIL] 成功 {ok_count}/{args.rounds}，"
                  f"失败 {fail_count}，静默错误 {silent_errors}")

        # 保存结果
        out_dir = os.path.join(
            os.path.dirname(__file__), "..",
            "artifacts", "evidence", "resource_stress")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "test": "CE-03",
                "rounds": args.rounds,
                "suite": suite.value,
                "stress": {
                    "mode": stress_mode,
                    "cpu": args.cpu,
                    "vm": args.vm,
                    "vm_bytes": args.vm_bytes,
                    "enabled": not args.no_stress,
                },
                "success": ok_count,
                "fail": fail_count,
                "silent_errors": silent_errors,
                "pass": all_ok,
                "details": results,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] 结果已写入: {os.path.abspath(out_path)}")

        sys.exit(0 if all_ok else 1)

    except KeyboardInterrupt:
        stop_stress_ng(stress_proc)
        if py_stress:
            py_stress.stop()
        print("\n[中断] 测试被中断")
        sys.exit(2)


if __name__ == "__main__":
    main()
