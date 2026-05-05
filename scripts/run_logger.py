#!/usr/bin/env python3
"""
run_logger.py — 统一 JSONL 运行日志记录器（客户端/服务端共用）

为语义通信全链路（握手 → 加密传输 → TVM 推理 → 结果回传）提供
结构化 JSONL 日志记录，方便事后审计、FIT 回归分析和性能追踪。

标准事件（event）:
  session_start  — 会话开始
  session_ready  — 会话就绪（握手完成）
  meta_validated — 元数据校验通过
  artifact_guard_ok — artifact SHA256 校验通过
  tvm_start      — TVM 推理开始
  tvm_done       — TVM 推理完成
  result_sent    — 结果已发送
  reject         — 请求被拒绝
  error          — 运行时错误
  run_end        — 运行结束

用法:
  from run_logger import RunLogger

  logger = RunLogger(role="server", log_dir="artifacts/evidence/logs")
  run_id = logger.new_run(job_id="job-001", backend="tvm", suite="AES_256_GCM")
  logger.log("session_start")
  logger.log("tvm_start", input_shape=[1,3,64,64])
  logger.log("tvm_done", latency_ms=230.3, result_shape=[1,3,256,256])
  logger.log("result_sent", status="ok")
  logger.close()
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ── 默认日志根目录 ──

def _default_log_root() -> str:
    home_dir = os.path.expanduser("~")
    if home_dir and home_dir != "~":
        return os.path.join(home_dir, "artifacts", "evidence", "logs")
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "artifacts", "evidence", "logs")
    )


_DEFAULT_LOG_ROOT = _default_log_root()


class RunLogger:
    """统一 JSONL 运行日志记录器。

    每次运行（run）产生一组 JSONL 日志行，所有行共享同一个 run_id。
    日志文件按日期分子目录存放，文件名包含 role 和创建时间。

    Args:
        role: 角色标识，如 "client" / "server" / "board"
        log_dir: 日志根目录，默认 artifacts/evidence/logs
    """

    def __init__(self, role: str, log_dir: str = ""):
        self.role = role
        self.log_root = log_dir or os.environ.get(
            "RUN_LOGGER_DIR", _DEFAULT_LOG_ROOT
        )

        # 按日期创建子目录: YYYY-MM-DD
        date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        self._log_dir = os.path.join(self.log_root, date_str)
        os.makedirs(self._log_dir, exist_ok=True)

        # 当前运行的上下文
        self._run_id: str | None = None
        self._job_id: str | None = None
        self._backend: str = ""
        self._suite: str = ""
        self._line_count: int = 0
        self._closed: bool = False

        # 日志文件路径
        ts_str = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._log_path = os.path.join(
            self._log_dir, f"{role}_{ts_str}.jsonl"
        )
        self._file = open(self._log_path, "a", encoding="utf-8")

    @property
    def run_id(self) -> str | None:
        """当前 run_id（new_run 之前为 None）。"""
        return self._run_id

    @property
    def log_path(self) -> str:
        """日志文件绝对路径。"""
        return os.path.abspath(self._log_path)

    def new_run(
        self,
        job_id: str | None = None,
        backend: str = "",
        suite: str = "",
    ) -> str:
        """开始一次新的运行，返回 UUID4 格式的 run_id。

        Args:
            job_id: 作业标识（可选）
            backend: 后端类型，如 "tvm" / "pytorch"
            suite: 加密套件，如 "AES_256_GCM" / "SM4_128_GCM"

        Returns:
            本次运行的 run_id（UUID4 字符串）
        """
        self._run_id = str(uuid.uuid4())
        self._job_id = job_id
        self._backend = backend
        self._suite = suite
        self._line_count = 0
        self._closed = False

        self.log("session_start")
        return self._run_id

    def log(self, event: str, **kwargs) -> None:
        """写入一条 JSONL 日志。

        每行包含标准字段 + 任意 kwargs 扩展字段。

        Args:
            event: 事件名称（见模块文档的标准事件列表）
            **kwargs: 任意扩展字段，直接合并到日志行中
        """
        if self._closed:
            return

        entry = {
            "ts": time.time(),
            "run_id": self._run_id or "",
            "job_id": self._job_id or "",
            "role": self.role,
            "backend": self._backend,
            "suite": self._suite,
            "event": event,
        }
        entry.update(kwargs)

        line = json.dumps(entry, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()
        self._line_count += 1

    def close(self) -> None:
        """写入 run_end 事件并关闭日志文件。"""
        if self._closed:
            return

        self.log("run_end", total_lines=self._line_count)
        self._closed = True
        self._file.close()

    def __del__(self):
        """析构时确保文件已关闭。"""
        if hasattr(self, "_file") and not self._file.closed:
            self.close()


# ── 命令行入口（可选，用于快速测试日志格式）──

if __name__ == "__main__":
    import sys

    print("run_logger 自测: 写入 3 条示例日志后关闭")
    logger = RunLogger(role="test")
    rid = logger.new_run(job_id="demo-001", backend="tvm", suite="AES_256_GCM")
    print(f"  run_id = {rid}")

    logger.log("session_ready", detail="握手完成")
    logger.log("artifact_guard_ok", artifact_sha_expected="abc123", artifact_sha_actual="abc123")
    logger.log(
        "tvm_done",
        latency_ms=230.339,
        input_shape=[1, 3, 64, 64],
        result_shape=[1, 3, 256, 256],
    )
    logger.log("result_sent", status="ok")
    logger.close()

    print(f"  日志写入: {logger.log_path}")
    sys.exit(0)
