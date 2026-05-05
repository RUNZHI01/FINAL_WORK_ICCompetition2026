"""
mlkem_link — 上位机 ↔ 飞腾派后量子安全链路模块

提供：
- ML-KEM-768 密钥封装（抗量子密钥协商）
- AES-256-GCM / SM4-GCM 双轨对称加密（国际标准 + 国密）
- SM2 + ML-DSA 可选身份认证
- 会话握手状态机
- HKDF-SHA256 密钥派生

后端（按优先级）：Tongsuo > liboqs
"""

from .kem import (
    KEMKeyPair, KEMEncapsulation, KEMBackend,
    TongsuoBackend, LibOQSBackend, get_backend,
)
from .crypto import CipherSuite, EncryptedPayload, LinkEncryptor
from .session import MLKEMSession, SessionRole, SessionState
from .kdf import hkdf_sha256, derive_session_keys
from .secure_channel import SecureChannel
from .auth import (
    SigPolicy, IdentityConfig,
    ClientHello, ServerHelloAuth, AuthResult,
    SigBackend, SM2SigBackend, MLDSASigBackend, MockSigBackend,
    build_transcript, sign_transcript, verify_transcript,
    derive_finished_keys, create_finished_message, verify_finished_message,
    encode_client_hello, decode_client_hello,
    encode_server_hello_auth, decode_server_hello_auth,
    get_sm2_backend, get_mldsa_backend,
)

__all__ = [
    "KEMKeyPair", "KEMEncapsulation", "KEMBackend",
    "TongsuoBackend", "LibOQSBackend", "get_backend",
    "CipherSuite", "EncryptedPayload", "LinkEncryptor",
    "MLKEMSession", "SessionRole", "SessionState",
    "hkdf_sha256", "derive_session_keys",
    "SecureChannel",
    "SigPolicy", "IdentityConfig",
    "ClientHello", "ServerHelloAuth", "AuthResult",
    "SigBackend", "SM2SigBackend", "MLDSASigBackend", "MockSigBackend",
    "build_transcript", "sign_transcript", "verify_transcript",
    "derive_finished_keys", "create_finished_message", "verify_finished_message",
    "encode_client_hello", "decode_client_hello",
    "encode_server_hello_auth", "decode_server_hello_auth",
    "get_sm2_backend", "get_mldsa_backend",
]
