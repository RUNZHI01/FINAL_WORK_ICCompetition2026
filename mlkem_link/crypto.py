"""
双轨对称加密模块

支持：
- AES-256-GCM（国际标准，飞腾派 ARMv8 硬件加速）
- SM4-GCM  （国密标准，飞腾派 SM4 硬件支持，体现自主可控）

两者均提供 AEAD（认证加密），同时保证机密性和完整性。
"""

import os
from enum import Enum
from dataclasses import dataclass


class CipherSuite(Enum):
    AES_256_GCM = "aes-256-gcm"
    SM4_GCM = "sm4-gcm"


@dataclass
class EncryptedPayload:
    """加密后的载荷"""
    nonce: bytes          # 12 字节 GCM nonce
    ciphertext: bytes     # 密文 + 16 字节认证标签
    suite: CipherSuite

    def to_bytes(self) -> bytes:
        """序列化为字节流（nonce_len[1] + nonce + ciphertext）"""
        return bytes([len(self.nonce)]) + self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes, suite: CipherSuite) -> "EncryptedPayload":
        """从字节流反序列化"""
        nonce_len = data[0]
        nonce = data[1:1 + nonce_len]
        ciphertext = data[1 + nonce_len:]
        return cls(nonce=nonce, ciphertext=ciphertext, suite=suite)


def _aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes,
                     aad: bytes = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key).encrypt(nonce, plaintext, aad)


def _aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes,
                     aad: bytes = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key).decrypt(nonce, ciphertext, aad)


def _sm4_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes,
                     aad: bytes = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    enc = Cipher(algorithms.SM4(key), modes.GCM(nonce)).encryptor()
    if aad is not None:
        enc.authenticate_additional_data(aad)
    return enc.update(plaintext) + enc.finalize() + enc.tag


def _sm4_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes,
                     aad: bytes = None) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    tag = ciphertext[-16:]
    ct = ciphertext[:-16]
    dec = Cipher(algorithms.SM4(key), modes.GCM(nonce, tag)).decryptor()
    if aad is not None:
        dec.authenticate_additional_data(aad)
    return dec.update(ct) + dec.finalize()


class LinkEncryptor:
    """链路层 AEAD 加密器"""

    _KEY_BYTES = {
        CipherSuite.AES_256_GCM: 32,
        CipherSuite.SM4_GCM: 16,
    }

    def __init__(self, suite: CipherSuite = CipherSuite.SM4_GCM):
        self._suite = suite
        # 检查 SM4 支持
        if suite == CipherSuite.SM4_GCM:
            try:
                from cryptography.hazmat.primitives.ciphers import algorithms
                algorithms.SM4(b"\x00" * 16)
            except (ImportError, AttributeError):
                raise RuntimeError(
                    "当前 cryptography 版本不支持 SM4。"
                    "需要 cryptography >= 45.0.7（wheel 内置 OpenSSL 3.5.0+）。"
                )

    @property
    def suite(self) -> CipherSuite:
        return self._suite

    @property
    def key_bytes(self) -> int:
        return self._KEY_BYTES[self._suite]

    @property
    def nonce_bytes(self) -> int:
        return 12  # GCM 标准 nonce

    def encrypt(self, key: bytes, plaintext: bytes,
                aad: bytes = None) -> EncryptedPayload:
        nonce = os.urandom(self.nonce_bytes)
        if self._suite == CipherSuite.AES_256_GCM:
            ct = _aes_gcm_encrypt(key, nonce, plaintext, aad)
        else:
            ct = _sm4_gcm_encrypt(key, nonce, plaintext, aad)
        return EncryptedPayload(nonce=nonce, ciphertext=ct, suite=self._suite)

    def decrypt(self, key: bytes, payload: EncryptedPayload,
                aad: bytes = None) -> bytes:
        if payload.suite != self._suite:
            raise ValueError(
                f"套件不匹配：加密器={self._suite.value}，载荷={payload.suite.value}"
            )
        if self._suite == CipherSuite.AES_256_GCM:
            return _aes_gcm_decrypt(key, payload.nonce, payload.ciphertext, aad)
        else:
            return _sm4_gcm_decrypt(key, payload.nonce, payload.ciphertext, aad)
