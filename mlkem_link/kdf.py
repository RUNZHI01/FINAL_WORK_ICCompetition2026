"""
HKDF-SHA256 密钥派生模块

从 ML-KEM shared_secret 派生多套对称加密密钥。
"""

import hashlib
import hmac


def hkdf_sha256(ikm: bytes, salt: bytes = None, info: bytes = b"",
                length: int = 32) -> bytes:
    """HKDF-SHA256 (RFC 5869)

    Args:
        ikm: 输入密钥材料（ML-KEM shared_secret，32 bytes）
        salt: 可选盐值（None 时使用全零）
        info: 上下文信息（区分不同密钥用途）
        length: 输出字节长度

    Returns:
        派生密钥（length bytes）
    """
    if salt is None:
        salt = b"\x00" * 32
    # Extract
    prk = _hmac_sha256(salt, ikm)
    # Expand
    n = (length + 31) // 32
    okm = b""
    t = b""
    for i in range(1, n + 1):
        t = _hmac_sha256(prk, t + info + bytes([i]))
        okm += t
    return okm[:length]


def _hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def derive_session_keys(shared_secret: bytes, suite_info: bytes = b"") -> dict:
    """从 ML-KEM 共享密钥派生双套件对称密钥

    Args:
        shared_secret: ML-KEM 协商出的 32 bytes 共享密钥
        suite_info: 额外的上下文信息

    Returns:
        {"aes256": bytes(32), "sm4": bytes(16)}
    """
    base_info = b"mlkem-link|" + suite_info
    return {
        "aes256": hkdf_sha256(shared_secret, info=base_info + b"|aes-256-gcm", length=32),
        "sm4": hkdf_sha256(shared_secret, info=base_info + b"|sm4-128-gcm", length=16),
    }
