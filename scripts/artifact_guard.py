#!/usr/bin/env python3
"""
artifact_guard.py — TVM 推理前 artifact 完整性校验模块

在 TVM 推理执行之前，对部署的 .so artifact 做 SHA256 校验，
防止未知/被篡改的 artifact 被加载执行（安全风险项 #1）。

用法:
  from artifact_guard import preflight_check, get_trusted_sha

  sha = get_trusted_sha()  # 从环境变量读取受信 SHA256
  result = preflight_check("model.so", sha, run_id="abc-123")
  if result["status"] == "deny":
      sys.exit(1)

日志输出为 JSONL 格式，追加到 artifacts/evidence/logs/artifact_guard.jsonl。
"""

import hashlib
import json
import os
import time
from pathlib import Path


# ── 默认日志路径 ──

_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "artifacts", "evidence", "logs"
)


# ── 核心函数 ──


def verify_artifact(artifact_path: str, expected_sha256: str) -> dict:
    """校验 artifact 文件的 SHA256 是否与期望值匹配。

    Args:
        artifact_path: artifact 文件路径（TVM .so 等）
        expected_sha256: 期望的 SHA256 十六进制摘要

    Returns:
        dict，包含以下字段：
          - status: "allow" 或 "deny"
          - actual_sha: 实际计算的 SHA256（出错时为空字符串）
          - expected_sha: 期望的 SHA256
          - error_code: 仅 deny 时出现，取值为
              E_ARTIFACT_SHA_MISMATCH / E_ARTIFACT_NOT_FOUND / E_ARTIFACT_GUARD_IO
          - detail: 仅 deny 时出现，人类可读的错误描述
    """
    result = {
        "status": "allow",
        "actual_sha": "",
        "expected_sha": expected_sha256,
    }

    try:
        path = Path(artifact_path)
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1 << 20)  # 1 MiB 分块读取
                if not chunk:
                    break
                sha256.update(chunk)

        actual = sha256.hexdigest()
        result["actual_sha"] = actual

        if actual != expected_sha256.lower():
            result["status"] = "deny"
            result["error_code"] = "E_ARTIFACT_SHA_MISMATCH"
            result["detail"] = (
                f"SHA256 不匹配: 期望 {expected_sha256.lower()}, "
                f"实际 {actual}"
            )

    except FileNotFoundError:
        result["status"] = "deny"
        result["error_code"] = "E_ARTIFACT_NOT_FOUND"
        result["detail"] = f"artifact 文件不存在: {artifact_path}"

    except IOError as exc:
        result["status"] = "deny"
        result["error_code"] = "E_ARTIFACT_GUARD_IO"
        result["detail"] = f"artifact 读取 I/O 错误: {exc}"

    return result


def preflight_check(
    artifact_path: str,
    expected_sha256: str,
    run_id: str,
    log_path: str | None = None,
) -> dict:
    """执行 artifact 预检并写入 JSONL 审计日志。

    在 verify_artifact 基础上增加日志记录，方便事后审计和 FIT 用例回溯。

    Args:
        artifact_path: artifact 文件路径
        expected_sha256: 期望的 SHA256 十六进制摘要
        run_id: 当前运行的唯一标识（UUID4）
        log_path: 日志文件路径，默认 artifacts/evidence/logs/artifact_guard.jsonl

    Returns:
        与 verify_artifact 相同的 dict
    """
    result = verify_artifact(artifact_path, expected_sha256)

    # 构造日志条目
    log_entry = {
        "ts": time.time(),
        "run_id": run_id,
        "event": "artifact_guard_check",
        "artifact_path": artifact_path,
        "expected_sha": expected_sha256,
        "actual_sha": result["actual_sha"],
        "status": result["status"],
        "error_code": result.get("error_code", ""),
        "detail": result.get("detail", ""),
    }

    # 写入 JSONL（追加模式）
    if log_path is None:
        log_dir = os.environ.get(
            "ARTIFACT_GUARD_LOG_DIR",
            os.path.join(os.path.expanduser("~"), "artifacts", "evidence", "logs"),
        )
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "artifact_guard.jsonl")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return result


def get_trusted_sha() -> str | None:
    """从环境变量 TRUSTED_ARTIFACT_SHA256 读取受信 SHA256。

    Returns:
        SHA256 十六进制字符串，环境变量未设置时返回 None。
    """
    return os.environ.get("TRUSTED_ARTIFACT_SHA256")


# ── 命令行入口（可选，用于快速手动校验）──


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <artifact_path> <expected_sha256>")
        print("  或设置环境变量 TRUSTED_ARTIFACT_SHA256 后:")
        print(f"  {sys.argv[0]} <artifact_path>")
        sys.exit(2)

    artifact = sys.argv[1]
    expected = sys.argv[2] if len(sys.argv) >= 3 else get_trusted_sha()

    if expected is None:
        print("错误: 未提供 expected_sha256 且环境变量 TRUSTED_ARTIFACT_SHA256 未设置")
        sys.exit(2)

    result = preflight_check(artifact, expected, run_id="cli-manual")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["status"] == "allow" else 1)
