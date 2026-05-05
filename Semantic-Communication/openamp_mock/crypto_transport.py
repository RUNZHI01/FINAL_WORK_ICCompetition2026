from __future__ import annotations

from typing import Any

from .crypto_guard import CryptoGuard
from .protocol import ControlMessage, msg_name
from .transport import MockTransport


class CryptoTransport:
    """Transport wrapper that applies AEAD on control-plane payloads."""

    def __init__(self, transport: MockTransport, crypto_guard: CryptoGuard) -> None:
        self._transport = transport
        self._crypto_guard = crypto_guard
        self.ctrl_log: list[dict[str, Any]] = []
        self.stats = {
            "encrypt_tx": 0,
            "decrypt_rx": 0,
            "passthrough_rx": 0,
        }

    def send_from_linux(self, message: ControlMessage, now_ms: int) -> None:
        encrypted = self._crypto_guard.encrypt(message)
        self.stats["encrypt_tx"] += 1
        self._transport.send_from_linux(encrypted, now_ms)
        self.ctrl_log.append(self._crypto_log_entry("linux->guard", message, now_ms))

    def send_from_guard(self, message: ControlMessage, now_ms: int) -> None:
        encrypted = self._crypto_guard.encrypt(message)
        self.stats["encrypt_tx"] += 1
        self._transport.send_from_guard(encrypted, now_ms)
        self.ctrl_log.append(self._crypto_log_entry("guard->linux", message, now_ms))

    def pop_for_guard(self) -> ControlMessage:
        encrypted = self._transport.pop_for_guard()
        return self._decrypt_or_passthrough(encrypted)

    def pop_for_linux(self) -> ControlMessage:
        encrypted = self._transport.pop_for_linux()
        return self._decrypt_or_passthrough(encrypted)

    def has_pending(self) -> bool:
        return self._transport.has_pending()

    def has_linux_pending(self) -> bool:
        return self._transport.has_linux_pending()

    def has_guard_pending(self) -> bool:
        return self._transport.has_guard_pending()

    def _decrypt_or_passthrough(self, message: ControlMessage) -> ControlMessage:
        decrypted = self._crypto_guard.decrypt(message)
        if decrypted is message:
            self.stats["passthrough_rx"] += 1
            return decrypted
        self.stats["decrypt_rx"] += 1
        return decrypted

    @staticmethod
    def _crypto_log_entry(direction: str, message: ControlMessage, now_ms: int) -> dict[str, Any]:
        return {
            "at_ms": now_ms,
            "direction": direction,
            "msg_type": msg_name(message.header.msg_type),
            "seq": message.header.seq,
            "job_id": message.header.job_id,
            "encrypted": True,
        }
