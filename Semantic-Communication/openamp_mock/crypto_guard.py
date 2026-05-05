from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from mlkem_link.crypto import CipherSuite, EncryptedPayload, LinkEncryptor
from mlkem_link.kdf import hkdf_sha256

from .protocol import ControlMessage, MessageType, build_message

_CTRL_INFO_PREFIX = b"mlkem-link|ctrl-plane|"


@dataclass(frozen=True)
class CryptoGuard:
    """Encrypt/decrypt helper for control-plane messages."""

    shared_secret: bytes
    suite: CipherSuite = CipherSuite.AES_256_GCM

    def __post_init__(self) -> None:
        encryptor = LinkEncryptor(self.suite)
        key = hkdf_sha256(
            self.shared_secret,
            info=_CTRL_INFO_PREFIX + self.suite.value.encode("utf-8"),
            length=encryptor.key_bytes,
        )
        object.__setattr__(self, "_encryptor", encryptor)
        object.__setattr__(self, "_key", key)

    def encrypt(self, message: ControlMessage) -> ControlMessage:
        plaintext = json.dumps(message.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        aad = self._build_aad(message.header.seq, message.header.job_id, message.header.msg_type)
        sealed = self._encryptor.encrypt(self._key, plaintext, aad=aad)
        outer_payload = {
            "inner_type": int(message.header.msg_type),
            "inner_version": int(message.header.version),
            "nonce_b64": base64.b64encode(sealed.nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(sealed.ciphertext).decode("ascii"),
            "suite": self.suite.value,
        }
        return build_message(
            msg_type=MessageType.ENCRYPTED_CTRL,
            seq=message.header.seq,
            job_id=message.header.job_id,
            payload=outer_payload,
            version=message.header.version,
        )

    def decrypt(self, message: ControlMessage) -> ControlMessage:
        if message.header.msg_type != int(MessageType.ENCRYPTED_CTRL):
            return message
        payload = message.payload
        inner_type = int(payload["inner_type"])
        inner_version = int(payload.get("inner_version", message.header.version))
        nonce = base64.b64decode(str(payload["nonce_b64"]).encode("ascii"), validate=True)
        ciphertext = base64.b64decode(str(payload["ciphertext_b64"]).encode("ascii"), validate=True)
        aad = self._build_aad(message.header.seq, message.header.job_id, inner_type)
        sealed = EncryptedPayload(nonce=nonce, ciphertext=ciphertext, suite=self.suite)
        plaintext = self._encryptor.decrypt(self._key, sealed, aad=aad)
        try:
            inner_payload = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid decrypted control payload") from exc
        if not isinstance(inner_payload, dict):
            raise ValueError("invalid decrypted control payload type")
        return build_message(
            msg_type=MessageType(inner_type),
            seq=message.header.seq,
            job_id=message.header.job_id,
            payload=inner_payload,
            version=inner_version,
        )

    @staticmethod
    def _build_aad(seq: int, job_id: int, msg_type: int) -> bytes:
        return f"ctrl:{seq}:{job_id}:{msg_type}".encode("utf-8")
