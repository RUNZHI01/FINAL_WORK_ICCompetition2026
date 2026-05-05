#!/usr/bin/env python3
"""
replay_guard.py — 服务端重放 / 重复请求防护模块

为 ML-KEM + AEAD 安全通信链路提供基于 job_id + seq 的
重放检测机制，使用 LRU 滑动窗口记录最近处理过的请求，
防止已处理的作业被重放攻击重复提交。

错误码:
  E_DUPLICATE_JOB    — (job_id, seq) 与窗口内已记录条目完全重复
  E_SEQ_WINDOW_EXPIRED — seq 已超出 LRU 窗口范围（太旧）
  E_REPLAY_SEQ       — 通用重放检测标识（用于日志分类）

用法:
  from replay_guard import ReplayGuard, validate_metadata

  guard = ReplayGuard(window_size=256)
  status, err = guard.check_and_record("job-001", 42)
  # status="allow", err=None

  status, err = guard.check_and_record("job-001", 42)
  # status="deny", err="E_DUPLICATE_JOB"

  # 集成辅助：从元数据字典中提取 job_id / seq
  status, err = validate_metadata({"job_id": "job-001", "seq": 42}, guard)
"""

import json
import os
import threading
import time
import uuid
from collections import OrderedDict


# ── 错误码常量 ──

E_DUPLICATE_JOB = "E_DUPLICATE_JOB"
E_SEQ_WINDOW_EXPIRED = "E_SEQ_WINDOW_EXPIRED"
E_REPLAY_SEQ = "E_REPLAY_SEQ"

# ── 默认日志目录 ──

_DEFAULT_LOG_DIR = os.path.join(
    os.path.expanduser("~"), "artifacts", "evidence", "logs"
)


class ReplayGuard:
    """基于 LRU 滑动窗口的重放防护器。

    使用 collections.OrderedDict 维护 (job_id, seq) 的 LRU 窗口，
    线程安全。每次 check_and_record 调用均会写入 JSONL 审计日志。

    Args:
        window_size: LRU 窗口容量，默认 256 条记录。
    """

    def __init__(self, window_size: int = 256):
        self.window_size = window_size
        self._window: OrderedDict[tuple[str, int], float] = OrderedDict()
        self._lock = threading.Lock()

        # 日志目录：环境变量 > 默认值
        log_dir = os.environ.get("ARTIFACT_GUARD_LOG_DIR", _DEFAULT_LOG_DIR)
        os.makedirs(log_dir, exist_ok=True)
        self._log_path = os.path.join(log_dir, "replay_guard.jsonl")
        self._log_file = open(self._log_path, "a", encoding="utf-8")

    # ── 内部日志 ──

    def _write_log(
        self,
        job_id: str,
        seq: int,
        status: str,
        error_code: str | None,
        detail: str,
    ) -> None:
        """向 JSONL 日志追加一行审计记录。

        Args:
            job_id: 作业标识
            seq: 序列号
            status: "allow" 或 "deny"
            error_code: 错误码或 None
            detail: 人类可读的补充说明
        """
        entry = {
            "ts": time.time(),
            "job_id": job_id,
            "seq": seq,
            "status": status,
            "error_code": error_code,
            "detail": detail,
            "window_size": self.window_size,
            "window_used": len(self._window),
        }
        line = json.dumps(entry, ensure_ascii=False)
        self._log_file.write(line + "\n")
        self._log_file.flush()

    # ── 核心检测 ──

    def check_and_record(
        self, job_id: str, seq: int
    ) -> tuple[str, str | None]:
        """检查 (job_id, seq) 是否为重放，并记录到窗口。

        判定逻辑（按优先级）:
          1. 若 (job_id, seq) 已存在于窗口中 → E_DUPLICATE_JOB
          2. 若 seq 比窗口中最老条目的 seq 还旧 → E_SEQ_WINDOW_EXPIRED
          3. 否则 → 放行，插入窗口并淘汰最老条目

        Args:
            job_id: 作业唯一标识
            seq: 该作业内的单调递增序列号

        Returns:
            (status, error_code) 二元组:
              status="allow", error_code=None  — 放行
              status="deny", error_code=具体错误码 — 拒绝
        """
        key = (job_id, seq)

        with self._lock:
            # 情况 1：完全重复
            if key in self._window:
                self._write_log(
                    job_id, seq, "deny", E_DUPLICATE_JOB,
                    f"重复请求: ({job_id}, {seq}) 已在窗口中",
                )
                return ("deny", E_DUPLICATE_JOB)

            # 情况 2：seq 过旧（比窗口中最老记录还小）
            if len(self._window) >= self.window_size:
                oldest_key = next(iter(self._window))
                oldest_job, oldest_seq = oldest_key
                if seq < oldest_seq:
                    self._write_log(
                        job_id, seq, "deny", E_SEQ_WINDOW_EXPIRED,
                        f"序列号过旧: seq={seq} < 窗口最老 seq={oldest_seq}",
                    )
                    return ("deny", E_SEQ_WINDOW_EXPIRED)

            # 情况 3：放行，插入 LRU 窗口
            self._window[key] = time.time()
            self._window.move_to_end(key)

            # 淘汰超出窗口容量的最老条目
            while len(self._window) > self.window_size:
                self._window.popitem(last=False)

            self._write_log(
                job_id, seq, "allow", None,
                f"请求放行，窗口已记录 ({job_id}, {seq})",
            )
            return ("allow", None)

    # ── 查询窗口状态 ──

    @property
    def window_used(self) -> int:
        """当前窗口中已记录的条目数。"""
        with self._lock:
            return len(self._window)

    def close(self) -> None:
        """关闭日志文件句柄。"""
        if hasattr(self, "_log_file") and not self._log_file.closed:
            self._log_file.close()

    def __del__(self):
        """析构时确保文件已关闭。"""
        if hasattr(self, "_log_file") and not self._log_file.closed:
            self._log_file.close()


# ── 集成辅助函数 ──

def validate_metadata(
    meta: dict, guard: ReplayGuard
) -> tuple[str, str | None]:
    """从元数据字典中提取 job_id / seq 并执行重放检测。

    适合在服务端收到请求后直接调用，将 meta 字典传入即可。

    Args:
        meta: 请求元数据字典，应包含 "job_id" 键，
              可选 "seq" 键（默认为 0）
        guard: 已初始化的 ReplayGuard 实例

    Returns:
        (status, error_code) 二元组，含义同 ReplayGuard.check_and_record
    """
    job_id = meta.get("job_id", "")
    seq = meta.get("seq", 0)
    return guard.check_and_record(job_id, seq)


# ── 自测入口 ──

def _self_test() -> None:
    """自测流程：插入 100 条记录，尝试重放其中 5 条，验证全部被拦截。"""
    print("replay_guard 自测开始")
    guard = ReplayGuard(window_size=256)

    base_job = "test-job"
    passed = 0
    failed = 0

    # 阶段 1：插入 100 条正常记录
    print("  阶段 1: 插入 100 条正常记录 ...")
    for i in range(100):
        status, err = guard.check_and_record(base_job, i)
        if status != "allow" or err is not None:
            print(f"    [FAIL] seq={i} 预期放行，实际: ({status}, {err})")
            failed += 1
        else:
            passed += 1

    # 阶段 2：重放 5 条（seq=10,25,50,77,99）
    replay_seqs = [10, 25, 50, 77, 99]
    print(f"  阶段 2: 重放 seq={replay_seqs} ...")
    for seq in replay_seqs:
        status, err = guard.check_and_record(base_job, seq)
        if status != "deny" or err != E_DUPLICATE_JOB:
            print(f"    [FAIL] seq={seq} 预期拦截，实际: ({status}, {err})")
            failed += 1
        else:
            print(f"    [OK]   seq={seq} 已拦截 ({err})")
            passed += 1

    # 阶段 3：插入新条目，确认窗口正常
    print("  阶段 3: 插入新条目确认窗口正常 ...")
    status, err = guard.check_and_record(base_job, 100)
    if status != "allow":
        print(f"    [FAIL] seq=100 预期放行，实际: ({status}, {err})")
        failed += 1
    else:
        passed += 1

    guard.close()

    total = passed + failed
    print(f"  结果: {passed}/{total} 通过, {failed} 失败")
    if failed == 0:
        print("replay_guard 自测全部通过")
    else:
        print("replay_guard 自测存在失败项，请检查")

    return failed == 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        ok = _self_test()
        sys.exit(0 if ok else 1)
    else:
        print("用法: python replay_guard.py test")
        print("  test — 运行自测（插入 100 条，重放 5 条，验证全部拦截）")
        sys.exit(1)
