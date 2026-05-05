from __future__ import annotations

from typing import Any


_AUTH_PATTERNS = (
    "permission denied (publickey",
    "publickey,password",
    "please try again",
    "authentication failed",
    "access denied",
)

_HOST_ENV_PATTERNS = (
    "socket: operation not permitted",
    "ssh_bridge_launch_failed",
)

_PERMISSION_PATTERNS = (
    "linux_bridge_permission_guard",
    "permission_gate",
    "passwordless sudo",
    "sudo: a password is required",
    "sudo: no tty present",
    "/dev/rpmsg",
    "operation not permitted",
)

_CONFIG_PATTERNS = (
    "no such file or directory",
    "could not resolve hostname",
    "name or service not known",
    "host key verification failed",
    "connection refused",
    "no route to host",
    "network is unreachable",
    "bad configuration option",
)

_TIMEOUT_PATTERNS = (
    "timed out",
    "timeout",
)

_ARTIFACT_MISMATCH_PATTERNS = (
    "artifact sha256 mismatch",
    "artifact_sha256 mismatch",
)

_BOARD_BUSY_PATTERNS = (
    "duplicate_job_id",
    "job_active",
)

_MESSAGE_TEMPLATES = {
    "probe": {
        "auth_error": "板卡 SSH 认证失败，请检查用户名、密码或 SSH 端口设置。",
        "config_error": "板卡探测配置不可用，请检查环境文件、主机和端口设置。",
        "host_env_error": "当前主机环境禁止建立 SSH socket，无法发起真机探板，请换到允许 SSH 出站的主机后重试。",
        "permission_error": "板端命令权限不足，请检查当前用户权限或非交互 sudo 配置。",
        "timeout": "板卡探测超时，请确认板卡在线后重试。",
        "error": "板卡探测失败，请查看诊断信息。",
    },
    "inference": {
        "auth_error": "远端推理认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
        "board_busy": "板端当前 guard_state=JOB_ACTIVE，OpenAMP 已拒绝重复 live launch。当前 demo 不会自动 SAFE_STOP；请等待现有作业完成或由操作员手动 SAFE_STOP 后再重试。",
        "config_error": "远端推理配置不完整或不可用，请检查连接信息和推理环境参数。",
        "artifact_mismatch": "远端 current 工件与界面展示的 trusted current SHA 不一致，请同步板端 optimized_model.so 后重试。",
        "host_env_error": "当前主机环境禁止建立 SSH socket，无法验证真机 OpenAMP 链路。",
        "permission_error": "板端 RPMsg 设备当前只允许 root 或 passwordless sudo 访问，请为演示 SSH 用户开放权限后重试。",
        "timeout": "远端推理超时，请确认板卡在线后重试。",
        "error": "远端推理执行失败，请查看诊断信息。",
    },
    "status": {
        "auth_error": "远端状态查询认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
        "config_error": "远端状态查询配置不可用，请检查板卡连接信息和本机脚本环境。",
        "host_env_error": "当前主机环境禁止建立 SSH socket，无法发起真机状态查询。",
        "permission_error": "远端状态查询缺少 RPMsg 设备访问权限，请检查当前用户权限或非交互 sudo 配置。",
        "timeout": "远端状态查询超时，请确认板卡在线后重试。",
        "error": "远端状态查询失败，请查看诊断信息。",
    },
    "fault": {
        "auth_error": "远端故障注入认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
        "config_error": "远端故障注入配置不可用，请检查板卡连接信息和本机脚本环境。",
        "host_env_error": "当前主机环境禁止建立 SSH socket，无法发起真机故障注入。",
        "permission_error": "远端故障注入缺少 RPMsg 设备访问权限，请检查当前用户权限或非交互 sudo 配置。",
        "timeout": "远端故障注入超时，请确认板卡在线后重试。",
        "error": "远端故障注入失败，请查看诊断信息。",
    },
    "recover": {
        "auth_error": "远端恢复认证失败，请检查板卡用户名、密码或 SSH 端口设置。",
        "config_error": "远端恢复配置不可用，请检查板卡连接信息和本机脚本环境。",
        "host_env_error": "当前主机环境禁止建立 SSH socket，无法发起真机恢复。",
        "permission_error": "远端恢复缺少 RPMsg 设备访问权限，请检查当前用户权限或非交互 sudo 配置。",
        "timeout": "远端恢复超时，请确认板卡在线后重试。",
        "error": "远端恢复失败，请查看诊断信息。",
    },
}

_FALLBACK_SUFFIX = {
    "inference": " 当前已回退到预录结果。",
    "fault": " 当前已切换到回放结果。",
    "recover": " 当前已切换到安全恢复回放。",
}

_ACTION_KIND = {
    "probe": "probe",
    "inference": "inference",
    "status": "status",
    "wrong_sha": "fault",
    "illegal_param": "fault",
    "heartbeat_timeout": "fault",
    "recover": "recover",
}


def _normalize_text(*values: str) -> str:
    return "\n".join(str(value or "").strip().lower() for value in values if str(value or "").strip())


def classify_status_category(
    *,
    status: str,
    stdout: str = "",
    stderr: str = "",
    error: str = "",
    missing_fields: list[str] | None = None,
) -> str:
    if status == "success":
        return "success"
    if status == "timeout":
        return "timeout"
    if missing_fields:
        return "config_error"

    text = _normalize_text(stderr, stdout, error)
    if any(pattern in text for pattern in _HOST_ENV_PATTERNS):
        return "host_env_error"
    if all(pattern in text for pattern in _BOARD_BUSY_PATTERNS):
        return "board_busy"
    if any(pattern in text for pattern in _AUTH_PATTERNS):
        return "auth_error"
    if any(pattern in text for pattern in _TIMEOUT_PATTERNS):
        return "timeout"
    if any(pattern in text for pattern in _ARTIFACT_MISMATCH_PATTERNS):
        return "artifact_mismatch"
    if any(pattern in text for pattern in _PERMISSION_PATTERNS):
        return "permission_error"
    if "permission denied" in text:
        return "auth_error"
    if status == "launch_error":
        return "config_error"
    if any(pattern in text for pattern in _CONFIG_PATTERNS):
        return "config_error"
    return "error"


def build_operator_message(action: str, status_category: str, *, include_fallback: bool = False) -> str:
    action_kind = _ACTION_KIND.get(action, action)
    templates = _MESSAGE_TEMPLATES.get(action_kind, _MESSAGE_TEMPLATES["status"])
    message = templates.get(status_category, templates["error"])
    if include_fallback:
        message += _FALLBACK_SUFFIX.get(action_kind, "")
    return message


def build_diagnostics(
    *,
    stdout: str = "",
    stderr: str = "",
    error: str = "",
    returncode: int | None = None,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    if stdout.strip():
        diagnostics["stdout"] = stdout.strip()
    if stderr.strip():
        diagnostics["stderr"] = stderr.strip()
    if error.strip():
        diagnostics["error"] = error.strip()
    if returncode is not None:
        diagnostics["returncode"] = returncode
    if missing_fields:
        diagnostics["missing_fields"] = list(missing_fields)
    return diagnostics
