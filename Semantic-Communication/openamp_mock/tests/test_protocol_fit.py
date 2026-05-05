#!/usr/bin/env python3
"""
OpenAMP 协议级 FIT — CRC 篡改、不完整结果、非法参数

覆盖 3 个协议级故障注入场景：
  FIT-P04: 控制帧 CRC32 篡改 → Guard 检测并触发安全停止
  FIT-P05: 不完整结果（result_code != 0 / output_count 不匹配）→ FAULT_LATCHED
  FIT-P06: 非法参数范围（snr_db_x100 / expected_outputs 越界）→ DENY

运行:
  python -m pytest Semantic-Communication/openamp_mock/tests/test_protocol_fit.py -v
"""

import sys
import os

import pytest

# 确保 openamp_mock 包可导入（从 Semantic-Communication/ 层）
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from openamp_mock.protocol import (
    MessageType, FaultCode, GuardState,
    build_message, validate_header,
)
from openamp_mock.guard import SafetyGuard
from openamp_mock.transport import MockTransport


# ── 共享辅助 ──


TRUSTED_SHA = "a" * 64  # 64 位 hex SHA256


def _make_guard(heartbeat_timeout_ms=250):
    """创建一个标准 SafetyGuard 实例"""
    return SafetyGuard(trusted_sha256=TRUSTED_SHA, heartbeat_timeout_ms=heartbeat_timeout_ms)


def _make_transport():
    """创建 MockTransport"""
    return MockTransport()


def _valid_job_payload(job_id=1, **overrides):
    """构造合法的 JOB_REQ payload"""
    payload = {
        "expected_sha256": TRUSTED_SHA,
        "input_shape_n": 1,
        "input_shape_c": 3,
        "input_shape_h": 64,
        "input_shape_w": 64,
        "input_dtype": 1,
        "snr_db_x100": 1000,
        "expected_outputs": 300,
        "deadline_ms": 5000,
    }
    payload.update(overrides)
    return payload


def _submit_job(guard, transport, job_id=1, now_ms=0, **payload_overrides):
    """提交一个合法作业并推进到 JOB_ACTIVE 状态"""
    payload = _valid_job_payload(job_id=job_id, **payload_overrides)
    msg = build_message(
        msg_type=MessageType.JOB_REQ,
        seq=guard._tx_seq + 1,
        job_id=job_id,
        payload=payload,
    )
    guard.handle(msg, now_ms, transport)
    return msg


def _send_heartbeat(guard, transport, job_id=1, now_ms=100):
    """发送心跳包"""
    msg = build_message(
        msg_type=MessageType.HEARTBEAT,
        seq=guard._tx_seq + 1,
        job_id=job_id,
        payload={},
    )
    guard.handle(msg, now_ms, transport)


def _send_job_done(guard, transport, job_id=1, now_ms=200, result_code=0, output_count=300):
    """发送 JOB_DONE"""
    msg = build_message(
        msg_type=MessageType.JOB_DONE,
        seq=guard._tx_seq + 1,
        job_id=job_id,
        payload={"result_code": result_code, "output_count": output_count},
    )
    guard.handle(msg, now_ms, transport)


def _send_reset(guard, transport, job_id=0, now_ms=300):
    """发送 RESET_REQ"""
    msg = build_message(
        msg_type=MessageType.RESET_REQ,
        seq=guard._tx_seq + 1,
        job_id=job_id,
        payload={},
    )
    guard.handle(msg, now_ms, transport)


# ══════════════════════════════════════════════
# FIT-P04: 控制帧 CRC32 篡改
# ══════════════════════════════════════════════


class TestFITP04CRCFrameTampering:
    """FIT-P04 — 威胁场景：恶意固件或信道错误导致控制帧 CRC 损坏

    故事线：比赛中对手通过物理层干扰或固件篡改，向飞腾派的 RPMsg
    通道注入 CRC 校验失败的控制帧。如果 Guard 不做 CRC 校验，可能
    将损坏的帧当作合法指令执行（如错误的 JOB_REQ 参数），导致
    TVM 推理使用错误参数甚至加载恶意 artifact。

    攻击手段：构造 force_bad_crc=True 的控制帧。
    防御机制：validate_header() 检测 CRC 不匹配；Guard 在 JOB_ACTIVE
    状态下触发 SAFE_STOP，在其他状态下触发 FAULT_LATCHED。
    验证方法：坏 CRC 帧被 validate_header() 拒绝；Guard 状态正确转移。
    """

    def test_bad_crc_frame_rejected_by_validate_header(self):
        """故事线：坏 CRC 帧无法通过 validate_header() 校验"""
        print("\n[FIT-P04] 故事：构造 CRC 损坏的控制帧")

        msg = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=1,
            payload=_valid_job_payload(),
            force_bad_crc=True,
        )

        is_valid = validate_header(msg.header)
        assert not is_valid, "force_bad_crc=True 的帧不应通过 validate_header()"

        # 对比：正常帧应通过
        msg_ok = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=1,
            payload=_valid_job_payload(),
        )
        assert validate_header(msg_ok.header), "正常帧应通过 validate_header()"

        print(f"  [validate_header] 坏 CRC → False，正常 CRC → True")
        print(f"  [FIT-P04] 验证通过：CRC 校验拦截损坏帧")

    def test_bad_crc_during_active_job_triggers_safe_stop(self):
        """故事线：作业执行中收到 CRC 损坏帧 → Guard 触发 SAFE_STOP"""
        print("\n[FIT-P04] 故事：作业执行中 CRC 损坏 → SAFE_STOP")

        guard = _make_guard()
        transport = _make_transport()

        # 正常提交作业
        _submit_job(guard, transport, job_id=1, now_ms=0)
        assert guard.state == GuardState.JOB_ACTIVE

        # 发送心跳保持活跃
        _send_heartbeat(guard, transport, job_id=1, now_ms=100)

        # 发送 CRC 损坏的帧
        bad_msg = build_message(
            msg_type=MessageType.HEARTBEAT,
            seq=guard._tx_seq + 1,
            job_id=1,
            payload={},
            force_bad_crc=True,
        )
        guard.handle(bad_msg, 150, transport)

        assert guard.state == GuardState.FAULT_LATCHED
        assert guard.last_fault_code == FaultCode.CONTROL_CRC_ERROR
        assert guard.sticky_fault is True

        # 验证 transport 收到了 SAFE_STOP
        safe_stop_sent = any(
            m.header.msg_type == MessageType.SAFE_STOP
            for m in transport._guard_to_linux
        )
        assert safe_stop_sent, "JOB_ACTIVE 状态下 CRC 错误应触发 SAFE_STOP"

        print(f"  [Guard] 状态: FAULT_LATCHED, fault_code: CONTROL_CRC_ERROR")
        print(f"  [Guard] SAFE_STOP 已发送")
        print(f"  [FIT-P04] 验证通过：作业中 CRC 损坏触发 SAFE_STOP")

    def test_bad_crc_in_ready_state_triggers_fault_latch(self):
        """故事线：空闲状态下收到 CRC 损坏帧 → FAULT_LATCHED（非 SAFE_STOP）"""
        print("\n[FIT-P04] 故事：空闲状态 CRC 损坏 → FAULT_LATCHED")

        guard = _make_guard()
        transport = _make_transport()

        assert guard.state == GuardState.READY

        bad_msg = build_message(
            msg_type=MessageType.STATUS_REQ,
            seq=1,
            job_id=0,
            payload={},
            force_bad_crc=True,
        )
        guard.handle(bad_msg, 0, transport)

        assert guard.state == GuardState.FAULT_LATCHED
        assert guard.last_fault_code == FaultCode.CONTROL_CRC_ERROR

        # READY 状态下不应发送 SAFE_STOP，而应发送 FAULT_REPORT
        safe_stop_sent = any(
            m.header.msg_type == MessageType.SAFE_STOP
            for m in transport._guard_to_linux
        )
        fault_report_sent = any(
            m.header.msg_type == MessageType.FAULT_REPORT
            for m in transport._guard_to_linux
        )
        assert not safe_stop_sent, "READY 状态下不应发 SAFE_STOP"
        assert fault_report_sent, "READY 状态下应发 FAULT_REPORT"

        print(f"  [Guard] 状态: FAULT_LATCHED, FAULT_REPORT 已发送")
        print(f"  [FIT-P04] 验证通过：空闲 CRC 损坏触发 FAULT_LATCHED")

    def test_valid_crc_after_bad_crc_still_latched(self):
        """故事线：CRC 损坏触发 FAULT_LATCHED 后，正常帧仍被拒绝（sticky fault）"""
        print("\n[FIT-P04] 故事：FAULT_LATCHED 后正常帧无法恢复")

        guard = _make_guard()
        transport = _make_transport()

        # 触发 CRC 故障
        bad_msg = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=1,
            payload=_valid_job_payload(),
            force_bad_crc=True,
        )
        guard.handle(bad_msg, 0, transport)
        assert guard.state == GuardState.FAULT_LATCHED

        # 尝试提交正常作业 → 进入 DENY_PENDING（Guard 对 FAULT_LATCHED 收到 JOB_REQ 走 _deny）
        _submit_job(guard, transport, job_id=2, now_ms=100)
        assert guard.state == GuardState.DENY_PENDING

        # 只有 RESET 才能恢复
        _send_reset(guard, transport, now_ms=200)
        assert guard.state == GuardState.READY

        print(f"  [Guard] FAULT_LATCHED → RESET → READY")
        print(f"  [FIT-P04] 验证通过：sticky fault 需 RESET 恢复")


# ══════════════════════════════════════════════
# FIT-P05: 不完整结果
# ══════════════════════════════════════════════


class TestFITP05IncompleteResults:
    """FIT-P05 — 威胁场景：TVM 推理中断或输出不完整

    故事线：飞腾派 TVM 推理过程中因内存不足、模型异常或超时导致
    部分输出丢失。如果 Guard 不检查 JOB_DONE 中的 result_code
    和 output_count，可能将不完整的结果当作成功交付给上位机，
    导致重建图像出现大面积黑块或伪影。

    攻击手段：发送 result_code != 0 或 output_count != expected 的 JOB_DONE。
    防御机制：Guard 检查 result_code 和 output_count，不匹配时记录
    OUTPUT_INCOMPLETE 故障并进入 FAULT_LATCHED。
    验证方法：不完整结果触发 FAULT_LATCHED，后续作业被拒绝。
    """

    def test_job_done_with_nonzero_result_code(self):
        """故事线：TVM 返回 result_code=1（失败）→ Guard 检测到不完整结果"""
        print("\n[FIT-P05] 故事：TVM 推理失败，result_code=1")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0, expected_outputs=300)
        assert guard.state == GuardState.JOB_ACTIVE

        _send_heartbeat(guard, transport, job_id=1, now_ms=100)

        # TVM 返回失败
        _send_job_done(guard, transport, job_id=1, now_ms=200, result_code=1, output_count=0)

        assert guard.state == GuardState.FAULT_LATCHED
        assert guard.last_fault_code == FaultCode.OUTPUT_INCOMPLETE
        assert guard.sticky_fault is True

        fault_report_sent = any(
            m.header.msg_type == MessageType.FAULT_REPORT
            for m in transport._guard_to_linux
        )
        assert fault_report_sent, "不完整结果应发送 FAULT_REPORT"

        print(f"  [Guard] 状态: FAULT_LATCHED, fault_code: OUTPUT_INCOMPLETE")
        print(f"  [FIT-P05] 验证通过：TVM 失败被检测")

    def test_job_done_with_output_count_mismatch(self):
        """故事线：TVM 只输出了 150/300 张图 → Guard 检测到数量不匹配"""
        print("\n[FIT-P05] 故事：TVM 输出不完整（150/300）")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0, expected_outputs=300)
        assert guard.state == GuardState.JOB_ACTIVE

        _send_heartbeat(guard, transport, job_id=1, now_ms=100)

        # 输出数量不匹配
        _send_job_done(guard, transport, job_id=1, now_ms=200, result_code=0, output_count=150)

        assert guard.state == GuardState.FAULT_LATCHED
        assert guard.last_fault_code == FaultCode.OUTPUT_INCOMPLETE

        print(f"  [Guard] 期望 300 张，实际 150 张 → OUTPUT_INCOMPLETE")
        print(f"  [FIT-P05] 验证通过：输出数量不匹配被检测")

    def test_incomplete_result_requires_reset(self):
        """故事线：不完整结果后 FAULT_LATCHED → 需 RESET 才能恢复"""
        print("\n[FIT-P05] 故事：不完整结果后系统锁定，需 RESET 恢复")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0)
        _send_job_done(guard, transport, job_id=1, now_ms=200, result_code=1, output_count=0)

        assert guard.state == GuardState.FAULT_LATCHED

        # 尝试提交新作业 → 进入 DENY_PENDING
        _submit_job(guard, transport, job_id=2, now_ms=300)
        assert guard.state == GuardState.DENY_PENDING

        # RESET 恢复
        _send_reset(guard, transport, now_ms=400)
        assert guard.state == GuardState.READY

        # 恢复后可以提交新作业
        _submit_job(guard, transport, job_id=3, now_ms=500)
        assert guard.state == GuardState.JOB_ACTIVE

        # 正常完成
        _send_job_done(guard, transport, job_id=3, now_ms=600, result_code=0, output_count=300)
        assert guard.state == GuardState.READY

        print(f"  [Guard] FAULT_LATCHED → RESET → READY → JOB_ACTIVE → READY")
        print(f"  [FIT-P05] 验证通过：RESET 后系统恢复正常")

    def test_omitted_result_code_treated_as_failure(self):
        """故事线：JOB_DONE 未携带 result_code → 默认视为失败"""
        print("\n[FIT-P05] 故事：JOB_DONE 缺少 result_code 字段")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0)

        # JOB_DONE 不带 result_code（payload.get 默认为 1）
        msg = build_message(
            msg_type=MessageType.JOB_DONE,
            seq=guard._tx_seq + 1,
            job_id=1,
            payload={"output_count": 300},  # 无 result_code
        )
        guard.handle(msg, 200, transport)

        assert guard.state == GuardState.FAULT_LATCHED
        assert guard.last_fault_code == FaultCode.OUTPUT_INCOMPLETE

        print(f"  [Guard] 缺少 result_code → 默认视为失败 → OUTPUT_INCOMPLETE")
        print(f"  [FIT-P05] 验证通过：缺省 result_code 被正确处理")


# ══════════════════════════════════════════════
# FIT-P06: 非法参数范围
# ══════════════════════════════════════════════


class TestFITP06IllegalParam:
    """FIT-P06 — 威胁场景：上位机发送非法参数的作业请求

    故事线：恶意上位机或协议实现 bug 导致 JOB_REQ 携带越界参数
    （如 snr_db_x100=-100 表示极端噪声，或 expected_outputs=42
    不在合法值 1/300 之中）。如果 Guard 不校验参数范围，TVM 可能
    使用荒谬参数执行推理，浪费算力或产生无意义结果。

    攻击手段：发送 snr_db_x100 < 0 或 > 3000，或 expected_outputs 不在 {1, 300}。
    防御机制：Guard._validate_input_contract() 校验参数范围，
    越界时返回 ILLEGAL_PARAM_RANGE 并拒绝作业。
    验证方法：非法参数被 DENY，error_code 为 ILLEGAL_PARAM_RANGE。
    """

    def test_negative_snr_rejected(self):
        """故事线：snr_db_x100=-100（极端噪声）→ DENY"""
        print("\n[FIT-P06] 故事：攻击者发送 snr_db_x100=-100")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0, snr_db_x100=-100)

        assert guard.state == GuardState.DENY_PENDING
        assert guard.last_fault_code == FaultCode.ILLEGAL_PARAM_RANGE

        print(f"  [Guard] DENY, fault_code: ILLEGAL_PARAM_RANGE")
        print(f"  [FIT-P06] 验证通过：负 SNR 被拒绝")

    def test_excessive_snr_rejected(self):
        """故事线：snr_db_x100=5000（超范围）→ DENY"""
        print("\n[FIT-P06] 故事：攻击者发送 snr_db_x100=5000")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0, snr_db_x100=5000)

        assert guard.state == GuardState.DENY_PENDING
        assert guard.last_fault_code == FaultCode.ILLEGAL_PARAM_RANGE

        print(f"  [Guard] DENY, fault_code: ILLEGAL_PARAM_RANGE")
        print(f"  [FIT-P06] 验证通过：超大 SNR 被拒绝")

    def test_invalid_expected_outputs_rejected(self):
        """故事线：expected_outputs=42（不在合法值 {1, 300} 中）→ DENY"""
        print("\n[FIT-P06] 故事：攻击者发送 expected_outputs=42")

        guard = _make_guard()
        transport = _make_transport()

        _submit_job(guard, transport, job_id=1, now_ms=0, expected_outputs=42)

        assert guard.state == GuardState.DENY_PENDING
        assert guard.last_fault_code == FaultCode.ILLEGAL_PARAM_RANGE

        print(f"  [Guard] DENY, fault_code: ILLEGAL_PARAM_RANGE")
        print(f"  [FIT-P06] 验证通过：非法 expected_outputs 被拒绝")

    def test_boundary_snr_accepted(self):
        """故事线：边界值 snr_db_x100=0 和 3000 → 均被接受"""
        print("\n[FIT-P06] 故事：边界值参数应被接受")

        guard = _make_guard()
        transport = _make_transport()

        # snr_db_x100=0
        _submit_job(guard, transport, job_id=1, now_ms=0, snr_db_x100=0)
        assert guard.state == GuardState.JOB_ACTIVE
        _send_job_done(guard, transport, job_id=1, now_ms=100, result_code=0, output_count=300)
        assert guard.state == GuardState.READY

        # snr_db_x100=3000
        _submit_job(guard, transport, job_id=2, now_ms=200, snr_db_x100=3000)
        assert guard.state == GuardState.JOB_ACTIVE

        print(f"  [Guard] snr_db_x100=0 → ALLOW, snr_db_x100=3000 → ALLOW")
        print(f"  [FIT-P06] 验证通过：边界值参数被正确接受")

    def test_missing_snr_defaults_to_invalid(self):
        """故事线：JOB_REQ 未携带 snr_db_x100 → 默认 -1 → DENY"""
        print("\n[FIT-P06] 故事：缺少 snr_db_x100 字段")

        guard = _make_guard()
        transport = _make_transport()

        payload = _valid_job_payload(job_id=1)
        del payload["snr_db_x100"]

        msg = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=1,
            payload=payload,
        )
        guard.handle(msg, 0, transport)

        assert guard.state == GuardState.DENY_PENDING
        assert guard.last_fault_code == FaultCode.ILLEGAL_PARAM_RANGE

        print(f"  [Guard] 缺少 snr_db_x100 → 默认 -1 → ILLEGAL_PARAM_RANGE")
        print(f"  [FIT-P06] 验证通过：缺失参数默认值被正确处理")
