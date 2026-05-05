"""
ML-KEM 身份认证增强模块

在既有 ML-KEM + HKDF + AEAD 之上增加：
1. SM2 签名身份认证
2. ML-DSA 签名身份认证
3. Finished 消息密钥确认
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .crypto import CipherSuite, EncryptedPayload, LinkEncryptor
from .kdf import hkdf_sha256
from .session import SessionRole


PROTO_VERSION = b"\x02"
TRANSCRIPT_PREFIX = b"mlkem-link-auth/v2"
NONCE_BYTES = 16

FINISHED_LABEL_C2S = b"mlkem-link|finished|c2s"
FINISHED_LABEL_S2C = b"mlkem-link|finished|s2c"

_LEN16 = struct.Struct("!H")


class SigPolicy(Enum):
    DUAL_REQUIRED = "DUAL_REQUIRED"
    SM2_ONLY = "SM2_ONLY"
    MLDSA_ONLY = "MLDSA_ONLY"


@dataclass
class IdentityConfig:
    role: SessionRole
    server_id: str
    server_sm2_sk: bytes | None = None
    server_sm2_pk: bytes | None = None
    server_mldsa_sk: bytes | None = None
    server_mldsa_pk: bytes | None = None
    peer_sm2_pk: bytes | None = None
    peer_mldsa_pk: bytes | None = None
    sig_policy: SigPolicy = SigPolicy.DUAL_REQUIRED


@dataclass
class ClientHello:
    proto_version: bytes
    suite: CipherSuite
    client_nonce: bytes
    kem_pk: bytes


@dataclass
class ServerHelloAuth:
    server_id: bytes
    server_nonce: bytes
    kem_ct: bytes
    sig_policy: SigPolicy
    sm2_signature: bytes | None
    mldsa_signature: bytes | None


@dataclass
class AuthResult:
    verified: bool
    sm2_ok: bool = False
    mldsa_ok: bool = False
    error: str | None = None


class SigBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def sig_bytes(self) -> int: ...

    @property
    @abstractmethod
    def pk_bytes(self) -> int: ...

    @property
    @abstractmethod
    def sk_bytes(self) -> int: ...

    @abstractmethod
    def keygen(self) -> tuple[bytes, bytes]: ...

    @abstractmethod
    def sign(self, private_key: bytes, message: bytes) -> bytes: ...

    @abstractmethod
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


def _find_sig_bridge() -> str:
    candidates = [
        Path(__file__).resolve().parents[1] / "tongsuo-dist" / "lib64" / "libtongsuo_sig_bridge.so",
        Path("/usr/local/tongsuo/lib64/libtongsuo_sig_bridge.so"),
        Path("/usr/local/tongsuo/lib/libtongsuo_sig_bridge.so"),
    ]
    env_path = os.environ.get("TONGSUO_SIG_BRIDGE")
    if env_path:
        candidates.insert(0, Path(env_path))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise ImportError(
        "找不到 libtongsuo_sig_bridge.so。\n"
        "请先编译 Tongsuo + 签名桥接库，"
        "或设置环境变量 TONGSUO_SIG_BRIDGE。"
    )


class SM2SigBackend(SigBackend):
    _PK_SIZE = 65
    _SK_SIZE = 32
    _SIG_MAX = 72

    def __init__(self, bridge_path: str | None = None):
        path = bridge_path or _find_sig_bridge()
        self._lib = self._load_bridge(path)

    @staticmethod
    def _load_bridge(path: str):
        import ctypes
        from ctypes import POINTER, c_char_p, c_int, c_void_p

        lib = ctypes.CDLL(path)

        lib.tongsuo_sm2_keygen.argtypes = [
            c_void_p, POINTER(c_int), c_void_p, POINTER(c_int),
            c_int, c_int,
        ]
        lib.tongsuo_sm2_keygen.restype = c_int

        lib.tongsuo_sm2_sign.argtypes = [
            c_char_p, c_int, c_char_p, c_int,
            c_void_p, POINTER(c_int), c_int,
        ]
        lib.tongsuo_sm2_sign.restype = c_int

        lib.tongsuo_sm2_verify.argtypes = [
            c_char_p, c_int, c_char_p, c_int, c_char_p, c_int,
        ]
        lib.tongsuo_sm2_verify.restype = c_int

        return lib

    @property
    def name(self) -> str:
        return "tongsuo-sm2"

    @property
    def sig_bytes(self) -> int:
        return self._SIG_MAX

    @property
    def pk_bytes(self) -> int:
        return self._PK_SIZE

    @property
    def sk_bytes(self) -> int:
        return self._SK_SIZE

    def keygen(self) -> tuple[bytes, bytes]:
        import ctypes
        from ctypes import c_int, create_string_buffer

        pk_buf = create_string_buffer(self._PK_SIZE)
        sk_buf = create_string_buffer(self._SK_SIZE)
        pk_len = c_int()
        sk_len = c_int()

        rc = self._lib.tongsuo_sm2_keygen(
            pk_buf, ctypes.byref(pk_len),
            sk_buf, ctypes.byref(sk_len),
            self._PK_SIZE, self._SK_SIZE,
        )
        if rc != 0:
            raise RuntimeError(f"Tongsuo SM2 keygen 失败: rc={rc}")
        return pk_buf.raw[:pk_len.value], sk_buf.raw[:sk_len.value]

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        import ctypes
        from ctypes import c_int, create_string_buffer

        sig_buf = create_string_buffer(self._SIG_MAX)
        sig_len = c_int()

        rc = self._lib.tongsuo_sm2_sign(
            private_key, len(private_key),
            message, len(message),
            sig_buf, ctypes.byref(sig_len),
            self._SIG_MAX,
        )
        if rc != 0:
            raise RuntimeError(f"Tongsuo SM2 sign 失败: rc={rc}")
        return sig_buf.raw[:sig_len.value]

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            rc = self._lib.tongsuo_sm2_verify(
                public_key, len(public_key),
                message, len(message),
                signature, len(signature),
            )
            return rc == 1
        except Exception:
            return False


class MLDSASigBackend(SigBackend):
    _ALG = "ML-DSA-65"

    def __init__(self):
        import oqs

        self._oqs = oqs
        enabled = oqs.get_enabled_sig_mechanisms()
        if self._ALG not in enabled:
            raise RuntimeError(
                f"liboqs 未启用 {self._ALG}，编译时需设置 "
                '-DOQS_ALGS_ENABLED="ML-KEM;ML-DSA"'
            )

    @property
    def name(self) -> str:
        return f"liboqs-{self._ALG}"

    @property
    def sig_bytes(self) -> int:
        return 3309

    @property
    def pk_bytes(self) -> int:
        return 1952

    @property
    def sk_bytes(self) -> int:
        return 4032

    def keygen(self) -> tuple[bytes, bytes]:
        with self._oqs.Signature(self._ALG) as signer:
            pk = signer.generate_keypair()
            sk = signer.export_secret_key()
            return pk, sk

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        with self._oqs.Signature(self._ALG, private_key) as signer:
            return signer.sign(message)

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        try:
            with self._oqs.Signature(self._ALG) as verifier:
                return bool(verifier.verify(message, signature, public_key))
        except Exception:
            return False


class MockSigBackend(SigBackend):
    @property
    def name(self) -> str:
        return "mock-hmac-sha256"

    @property
    def sig_bytes(self) -> int:
        return 32

    @property
    def pk_bytes(self) -> int:
        return 32

    @property
    def sk_bytes(self) -> int:
        return 32

    def keygen(self) -> tuple[bytes, bytes]:
        key = os.urandom(32)
        return key, key

    def sign(self, private_key: bytes, message: bytes) -> bytes:
        return hmac.new(private_key, message, hashlib.sha256).digest()

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        expected = hmac.new(public_key, message, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)


def get_sm2_backend() -> SM2SigBackend:
    try:
        return SM2SigBackend()
    except (ImportError, OSError, AttributeError) as exc:
        raise ImportError(
            f"SM2 签名后端不可用: {exc}。需要 Tongsuo + libtongsuo_sig_bridge.so"
        ) from exc


def get_mldsa_backend() -> MLDSASigBackend:
    try:
        return MLDSASigBackend()
    except (ImportError, RuntimeError) as exc:
        raise ImportError(
            f"ML-DSA 签名后端不可用: {exc}。需要 liboqs-python 且编译时启用 ML-DSA"
        ) from exc


def build_transcript(
    proto_version: bytes,
    suite: CipherSuite,
    client_nonce: bytes,
    server_nonce: bytes,
    kem_pk: bytes,
    kem_ct: bytes,
    server_id: bytes,
    sig_policy: SigPolicy,
) -> bytes:
    parts = [
        TRANSCRIPT_PREFIX,
        _LEN16.pack(len(proto_version)) + proto_version,
        _LEN16.pack(len(suite.value)) + suite.value.encode(),
        client_nonce,
        server_nonce,
        _LEN16.pack(len(kem_pk)) + kem_pk,
        _LEN16.pack(len(kem_ct)) + kem_ct,
        _LEN16.pack(len(server_id)) + server_id,
        _LEN16.pack(len(sig_policy.value)) + sig_policy.value.encode(),
    ]
    return b"".join(parts)


def sign_transcript(
    sm2_backend: SigBackend | None,
    mldsa_backend: SigBackend | None,
    sm2_sk: bytes | None,
    mldsa_sk: bytes | None,
    transcript: bytes,
    policy: SigPolicy,
) -> tuple[bytes | None, bytes | None]:
    sm2_sig = None
    mldsa_sig = None

    if policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY}:
        if sm2_backend is None or sm2_sk is None:
            raise RuntimeError(f"策略 {policy.value} 要求 SM2 签名，但后端或私钥缺失")
        sm2_sig = sm2_backend.sign(sm2_sk, transcript)

    if policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY}:
        if mldsa_backend is None or mldsa_sk is None:
            raise RuntimeError(f"策略 {policy.value} 要求 ML-DSA 签名，但后端或私钥缺失")
        mldsa_sig = mldsa_backend.sign(mldsa_sk, transcript)

    return sm2_sig, mldsa_sig


def verify_transcript(
    sm2_backend: SigBackend | None,
    mldsa_backend: SigBackend | None,
    sm2_pk: bytes | None,
    mldsa_pk: bytes | None,
    transcript: bytes,
    sm2_signature: bytes | None,
    mldsa_signature: bytes | None,
    policy: SigPolicy,
) -> AuthResult:
    sm2_ok = False
    mldsa_ok = False
    errors: list[str] = []

    if policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY}:
        if sm2_backend is None or sm2_pk is None or sm2_signature is None:
            return AuthResult(False, error="策略要求 SM2 验签，但缺少后端/公钥/签名")
        sm2_ok = sm2_backend.verify(sm2_pk, transcript, sm2_signature)
        if not sm2_ok:
            errors.append("SM2 验签失败")

    if policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY}:
        if mldsa_backend is None or mldsa_pk is None or mldsa_signature is None:
            return AuthResult(False, sm2_ok=sm2_ok, error="策略要求 ML-DSA 验签，但缺少后端/公钥/签名")
        mldsa_ok = mldsa_backend.verify(mldsa_pk, transcript, mldsa_signature)
        if not mldsa_ok:
            errors.append("ML-DSA 验签失败")

    return AuthResult(
        verified=not errors,
        sm2_ok=sm2_ok,
        mldsa_ok=mldsa_ok,
        error="; ".join(errors) if errors else None,
    )


def derive_finished_keys(shared_secret: bytes, suite: CipherSuite) -> tuple[bytes, bytes]:
    key_len = 32 if suite == CipherSuite.AES_256_GCM else 16
    return (
        hkdf_sha256(shared_secret, info=FINISHED_LABEL_C2S, length=key_len),
        hkdf_sha256(shared_secret, info=FINISHED_LABEL_S2C, length=key_len),
    )


def create_finished_message(
    finished_key: bytes,
    label: bytes,
    transcript: bytes,
    suite: CipherSuite,
) -> bytes:
    encryptor = LinkEncryptor(suite)
    return encryptor.encrypt(finished_key, label, aad=transcript).to_bytes()


def verify_finished_message(
    finished_key: bytes,
    label: bytes,
    transcript: bytes,
    suite: CipherSuite,
    finished_msg_bytes: bytes,
) -> bool:
    try:
        encryptor = LinkEncryptor(suite)
        payload = EncryptedPayload.from_bytes(finished_msg_bytes, suite)
        return encryptor.decrypt(finished_key, payload, aad=transcript) == label
    except Exception:
        return False


def encode_client_hello(msg: ClientHello) -> bytes:
    suite_bytes = msg.suite.value.encode()
    return b"".join(
        [
            msg.proto_version,
            _LEN16.pack(len(suite_bytes)) + suite_bytes,
            msg.client_nonce,
            _LEN16.pack(len(msg.kem_pk)) + msg.kem_pk,
        ]
    )


def decode_client_hello(data: bytes) -> ClientHello:
    off = 0
    proto_version = data[off:off + 1]
    off += 1

    suite_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    suite = CipherSuite(data[off:off + suite_len].decode())
    off += suite_len

    client_nonce = data[off:off + NONCE_BYTES]
    off += NONCE_BYTES

    pk_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    kem_pk = data[off:off + pk_len]
    return ClientHello(proto_version=proto_version, suite=suite, client_nonce=client_nonce, kem_pk=kem_pk)


def encode_server_hello_auth(msg: ServerHelloAuth) -> bytes:
    policy_bytes = msg.sig_policy.value.encode()
    sm2_sig = msg.sm2_signature or b""
    mldsa_sig = msg.mldsa_signature or b""
    return b"".join(
        [
            _LEN16.pack(len(msg.server_id)) + msg.server_id,
            msg.server_nonce,
            _LEN16.pack(len(msg.kem_ct)) + msg.kem_ct,
            _LEN16.pack(len(policy_bytes)) + policy_bytes,
            _LEN16.pack(len(sm2_sig)) + sm2_sig,
            _LEN16.pack(len(mldsa_sig)) + mldsa_sig,
        ]
    )


def decode_server_hello_auth(data: bytes) -> ServerHelloAuth:
    off = 0

    server_id_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    server_id = data[off:off + server_id_len]
    off += server_id_len

    server_nonce = data[off:off + NONCE_BYTES]
    off += NONCE_BYTES

    kem_ct_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    kem_ct = data[off:off + kem_ct_len]
    off += kem_ct_len

    policy_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    sig_policy = SigPolicy(data[off:off + policy_len].decode())
    off += policy_len

    sm2_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    sm2_signature = data[off:off + sm2_len] if sm2_len > 0 else None
    off += sm2_len

    mldsa_len = _LEN16.unpack(data[off:off + 2])[0]
    off += 2
    mldsa_signature = data[off:off + mldsa_len] if mldsa_len > 0 else None

    return ServerHelloAuth(
        server_id=server_id,
        server_nonce=server_nonce,
        kem_ct=kem_ct,
        sig_policy=sig_policy,
        sm2_signature=sm2_signature,
        mldsa_signature=mldsa_signature,
    )
