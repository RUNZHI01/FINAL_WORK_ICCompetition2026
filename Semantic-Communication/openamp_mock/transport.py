from __future__ import annotations

from typing import Any

from .protocol import ControlMessage, fault_name, fault_tag, msg_name


class MockTransport:
    """In-memory duplex transport for Linux <-> safety_guard messages."""

    def __init__(self) -> None:
        self._linux_to_guard: list[ControlMessage] = []
        self._guard_to_linux: list[ControlMessage] = []
        self.ctrl_log: list[dict[str, Any]] = []

    def send_from_linux(self, message: ControlMessage, now_ms: int) -> None:
        self._linux_to_guard.append(message)
        self.ctrl_log.append(self._log_entry("linux->guard", message, now_ms))

    def send_from_guard(self, message: ControlMessage, now_ms: int) -> None:
        self._guard_to_linux.append(message)
        self.ctrl_log.append(self._log_entry("guard->linux", message, now_ms))

    def pop_for_guard(self) -> ControlMessage:
        return self._linux_to_guard.pop(0)

    def pop_for_linux(self) -> ControlMessage:
        return self._guard_to_linux.pop(0)

    def has_pending(self) -> bool:
        return bool(self._linux_to_guard or self._guard_to_linux)

    def has_linux_pending(self) -> bool:
        return bool(self._linux_to_guard)

    def has_guard_pending(self) -> bool:
        return bool(self._guard_to_linux)

    @staticmethod
    def _log_entry(direction: str, message: ControlMessage, now_ms: int) -> dict[str, Any]:
        payload = dict(message.payload)
        entry = {
            "at_ms": now_ms,
            "direction": direction,
            "msg_type": msg_name(message.header.msg_type),
            "seq": message.header.seq,
            "job_id": message.header.job_id,
            "payload": payload,
        }
        if "fault_code" in payload:
            entry["fault_tag"] = fault_tag(int(payload["fault_code"]))
            entry["fault_name"] = fault_name(int(payload["fault_code"]))
        return entry
