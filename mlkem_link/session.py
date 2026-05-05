"""
ML-KEM 会话管理模块

会话生命周期：
  INITIATOR                          RESPONDER
  (上位机)                            (飞腾派)
     │                                    │
     │──── public_key ───────────────────>│  start_handshake()
     │                                    │
     │<──── ciphertext ──────────────────│  respond_handshake()
     │                                    │
  complete_handshake()                    │
     │                                    │
  [双方派生会话密钥，进入 READY 状态]      │
     │                                    │
     │<===== 加密通信 (AES/SM4-GCM) =====>│
"""

import hashlib
from enum import Enum
from .kem import KEMBackend, KEMKeyPair
from .crypto import CipherSuite, LinkEncryptor, EncryptedPayload
from .kdf import hkdf_sha256


class SessionState(Enum):
    IDLE = "idle"
    WAITING_CT = "waiting_ciphertext"   # 发起方等待密文
    READY = "ready"
    ERROR = "error"


class SessionRole(Enum):
    INITIATOR = "initiator"   # 上位机
    RESPONDER = "responder"   # 飞腾派


class MLKEMSession:
    """ML-KEM 安全会话"""

    def __init__(self, role: SessionRole, backend: KEMBackend,
                 suite: CipherSuite = CipherSuite.SM4_GCM):
        self._role = role
        self._backend = backend
        self._suite = suite
        self._state = SessionState.IDLE
        self._keypair: KEMKeyPair = None
        self._session_key: bytes = None
        self._shared_secret: bytes = None
        self._encryptor = LinkEncryptor(suite)

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == SessionState.READY

    @property
    def role(self) -> SessionRole:
        return self._role

    @property
    def cipher_suite(self) -> CipherSuite:
        return self._suite

    @property
    def cipher_suite_name(self) -> str:
        return self._suite.value

    @property
    def shared_secret(self) -> bytes:
        if not self.is_ready:
            raise RuntimeError("会话未就绪，无法获取共享密钥")
        return self._shared_secret

    # ── 发起方（上位机）──

    def start_handshake(self) -> bytes:
        """发起方：生成密钥对，返回公钥"""
        if self._role != SessionRole.INITIATOR:
            raise RuntimeError("仅发起方可调用 start_handshake()")
        if self._state != SessionState.IDLE:
            raise RuntimeError(f"状态错误：当前 {self._state.value}，需要 idle")
        self._keypair = self._backend.keygen()
        self._state = SessionState.WAITING_CT
        return self._keypair.public_key

    def complete_handshake(self, ciphertext: bytes) -> None:
        """发起方：收到密文后完成握手"""
        if self._state != SessionState.WAITING_CT:
            raise RuntimeError(f"状态错误：当前 {self._state.value}，需要 waiting_ciphertext")
        shared_secret = self._backend.decaps(
            self._keypair.secret_key, ciphertext,
            public_key=self._keypair.public_key,
        )
        self._derive_session_key(shared_secret)
        self._state = SessionState.READY

    # ── 响应方（飞腾派）──

    def respond_handshake(self, public_key: bytes) -> bytes:
        """响应方：收到公钥后封装，返回密文"""
        if self._role != SessionRole.RESPONDER:
            raise RuntimeError("仅响应方可调用 respond_handshake()")
        if self._state != SessionState.IDLE:
            raise RuntimeError(f"状态错误：当前 {self._state.value}，需要 idle")
        enc_result = self._backend.encaps(public_key)
        self._derive_session_key(enc_result.shared_secret)
        self._state = SessionState.READY
        return enc_result.ciphertext

    # ── 加密通信 ──

    def encrypt(self, plaintext: bytes, aad: bytes = None) -> EncryptedPayload:
        """加密明文"""
        if not self.is_ready:
            raise RuntimeError("会话未就绪，无法加密")
        return self._encryptor.encrypt(self._session_key, plaintext, aad)

    def decrypt(self, payload: EncryptedPayload, aad: bytes = None) -> bytes:
        """解密载荷"""
        if not self.is_ready:
            raise RuntimeError("会话未就绪，无法解密")
        return self._encryptor.decrypt(self._session_key, payload, aad)

    # ── 内部 ──

    def _derive_session_key(self, shared_secret: bytes) -> None:
        """从 ML-KEM 共享密钥派生会话密钥

        使用 HKDF-SHA256，以密码套件名称作为上下文信息，
        确保不同套件派生出不同的密钥。
        """
        self._shared_secret = shared_secret
        info = f"mlkem-link|{self._suite.value}".encode()
        self._session_key = hkdf_sha256(
            ikm=shared_secret,
            salt=None,
            info=info,
            length=self._encryptor.key_bytes,
        )
