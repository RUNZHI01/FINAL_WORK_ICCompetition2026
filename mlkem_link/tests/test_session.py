"""
端到端会话测试

验证完整的 ML-KEM 握手 + AES-256-GCM / SM4-GCM 加解密流程。

后端选择：
- 优先使用 Tongsuo
- 其次使用 liboqs
- 若均不可用则跳过测试
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mlkem_link.kem import KEMBackend
from mlkem_link.crypto import CipherSuite, EncryptedPayload, LinkEncryptor
from mlkem_link.session import MLKEMSession, SessionRole, SessionState


def _get_backend() -> KEMBackend:
    """优先使用 Tongsuo，其次 liboqs；均不可用时跳过测试"""
    try:
        from mlkem_link.kem import TongsuoBackend
        b = TongsuoBackend("768")
        b.keygen()  # 健康检查
        return b
    except Exception:
        pass
    try:
        from mlkem_link.kem import LibOQSBackend
        return LibOQSBackend("768")
    except Exception:
        pass
    pytest.skip("无可信 KEM 后端（Tongsuo/liboqs 均不可用），跳过测试")


# ── 辅助 ──

def _make_sessions(suite: CipherSuite):
    backend = _get_backend()
    initiator = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
    responder = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)
    return initiator, responder


def _do_handshake(initiator: MLKEMSession, responder: MLKEMSession):
    pk = initiator.start_handshake()
    assert initiator.state == SessionState.WAITING_CT
    ct = responder.respond_handshake(pk)
    assert responder.state == SessionState.READY
    initiator.complete_handshake(ct)
    assert initiator.state == SessionState.READY


# ── KEM 正确性 ──

class TestKEM:
    def test_keygen_sizes(self):
        kem = _get_backend()
        kp = kem.keygen()
        assert len(kp.public_key) == kem.pk_bytes
        assert len(kp.secret_key) == kem.sk_bytes

    def test_encaps_decaps_match(self):
        kem = _get_backend()
        kp = kem.keygen()
        enc = kem.encaps(kp.public_key)
        assert len(enc.ciphertext) == kem.ct_bytes
        assert len(enc.shared_secret) == kem.ss_bytes
        ss2 = kem.decaps(kp.secret_key, enc.ciphertext)
        assert enc.shared_secret == ss2


# ── 对称加密：AES-256-GCM ──

class TestCryptoAES:
    def test_encrypt_decrypt_roundtrip(self):
        enc = LinkEncryptor(CipherSuite.AES_256_GCM)
        key = os.urandom(32)
        plaintext = b"Hello, Phytium! This is a test of AES-256-GCM."
        payload = enc.encrypt(key, plaintext)
        decrypted = enc.decrypt(key, payload)
        assert decrypted == plaintext

    def test_encrypt_decrypt_with_aad(self):
        enc = LinkEncryptor(CipherSuite.AES_256_GCM)
        key = os.urandom(32)
        plaintext = b"test data"
        aad = b"job_id:42"
        payload = enc.encrypt(key, plaintext, aad=aad)
        decrypted = enc.decrypt(key, payload, aad=aad)
        assert decrypted == plaintext

    def test_tampered_ciphertext_fails(self):
        enc = LinkEncryptor(CipherSuite.AES_256_GCM)
        key = os.urandom(32)
        plaintext = b"sensitive data"
        payload = enc.encrypt(key, plaintext)
        tampered = EncryptedPayload(
            nonce=payload.nonce,
            ciphertext=payload.ciphertext[:-4] + b"\xff\xff\xff\xff",
            suite=payload.suite,
        )
        with pytest.raises(Exception):
            enc.decrypt(key, tampered)

    def test_serialization_roundtrip(self):
        enc = LinkEncryptor(CipherSuite.AES_256_GCM)
        key = os.urandom(32)
        plaintext = b"serialization test"
        payload = enc.encrypt(key, plaintext)
        raw = payload.to_bytes()
        restored = EncryptedPayload.from_bytes(raw, CipherSuite.AES_256_GCM)
        decrypted = enc.decrypt(key, restored)
        assert decrypted == plaintext

    def test_wrong_key_fails(self):
        enc = LinkEncryptor(CipherSuite.AES_256_GCM)
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        payload = enc.encrypt(key1, b"secret")
        with pytest.raises(Exception):
            enc.decrypt(key2, payload)


# ── 对称加密：SM4-GCM ──

class TestCryptoSM4:
    @pytest.fixture(autouse=True)
    def _check_sm4(self):
        try:
            from cryptography.hazmat.primitives.ciphers import algorithms
            algorithms.SM4(b"\x00" * 16)
        except (ImportError, AttributeError):
            pytest.skip("当前环境不支持 SM4")

    def test_encrypt_decrypt_roundtrip(self):
        enc = LinkEncryptor(CipherSuite.SM4_GCM)
        key = os.urandom(16)
        plaintext = b"Hello, SM4-GCM on Phytium!"
        payload = enc.encrypt(key, plaintext)
        decrypted = enc.decrypt(key, payload)
        assert decrypted == plaintext

    def test_encrypt_decrypt_with_aad(self):
        enc = LinkEncryptor(CipherSuite.SM4_GCM)
        key = os.urandom(16)
        plaintext = b"test with aad"
        aad = b"job_id:99"
        payload = enc.encrypt(key, plaintext, aad=aad)
        decrypted = enc.decrypt(key, payload, aad=aad)
        assert decrypted == plaintext

    def test_tampered_ciphertext_fails(self):
        enc = LinkEncryptor(CipherSuite.SM4_GCM)
        key = os.urandom(16)
        plaintext = b"sensitive sm4 data"
        payload = enc.encrypt(key, plaintext)
        tampered = EncryptedPayload(
            nonce=payload.nonce,
            ciphertext=payload.ciphertext[:-4] + b"\xff\xff\xff\xff",
            suite=payload.suite,
        )
        with pytest.raises(Exception):
            enc.decrypt(key, tampered)


# ── 会话端到端：AES-256-GCM ──

class TestSessionAES:
    def test_full_handshake_and_encrypt(self):
        initiator, responder = _make_sessions(CipherSuite.AES_256_GCM)
        _do_handshake(initiator, responder)

        # 发起方加密 → 响应方解密
        plaintext = b"latent tensor data from upper computer"
        payload = initiator.encrypt(plaintext)
        decrypted = responder.decrypt(payload)
        assert decrypted == plaintext

        # 反向
        plaintext2 = b"reconstruction result from Phytium board"
        payload2 = responder.encrypt(plaintext2)
        decrypted2 = initiator.decrypt(payload2)
        assert decrypted2 == plaintext2

    def test_state_transitions(self):
        initiator, responder = _make_sessions(CipherSuite.AES_256_GCM)
        assert initiator.state == SessionState.IDLE
        assert responder.state == SessionState.IDLE

        pk = initiator.start_handshake()
        assert initiator.state == SessionState.WAITING_CT
        assert responder.state == SessionState.IDLE

        ct = responder.respond_handshake(pk)
        assert responder.state == SessionState.READY
        assert initiator.state == SessionState.WAITING_CT

        initiator.complete_handshake(ct)
        assert initiator.state == SessionState.READY

    def test_encrypt_before_ready_fails(self):
        initiator, _ = _make_sessions(CipherSuite.AES_256_GCM)
        with pytest.raises(RuntimeError):
            initiator.encrypt(b"test")

    def test_wrong_role_handshake(self):
        initiator, _ = _make_sessions(CipherSuite.AES_256_GCM)
        with pytest.raises(RuntimeError):
            initiator.respond_handshake(b"pk")

    def test_multiple_messages(self):
        initiator, responder = _make_sessions(CipherSuite.AES_256_GCM)
        _do_handshake(initiator, responder)
        for i in range(10):
            msg = f"message {i}".encode()
            payload = initiator.encrypt(msg)
            decrypted = responder.decrypt(payload)
            assert decrypted == msg

    def test_serialized_transmission(self):
        """模拟真实网络传输：序列化 → 字节流 → 反序列化 → 解密"""
        initiator, responder = _make_sessions(CipherSuite.AES_256_GCM)
        _do_handshake(initiator, responder)

        plaintext = b"latent data over the wire"
        aad = b"job_id:001|shape:1x3x64x64"
        payload = initiator.encrypt(plaintext, aad=aad)

        # 序列化 → 模拟传输 → 反序列化
        wire_bytes = payload.to_bytes()
        restored = EncryptedPayload.from_bytes(wire_bytes, CipherSuite.AES_256_GCM)
        decrypted = responder.decrypt(restored, aad=aad)
        assert decrypted == plaintext


# ── 会话端到端：SM4-GCM ──

class TestSessionSM4:
    @pytest.fixture(autouse=True)
    def _check_sm4(self):
        try:
            from cryptography.hazmat.primitives.ciphers import algorithms
            algorithms.SM4(b"\x00" * 16)
        except (ImportError, AttributeError):
            pytest.skip("当前环境不支持 SM4")

    def test_full_handshake_and_encrypt(self):
        initiator, responder = _make_sessions(CipherSuite.SM4_GCM)
        _do_handshake(initiator, responder)

        plaintext = b"latent data with SM4-GCM national cipher"
        payload = initiator.encrypt(plaintext)
        decrypted = responder.decrypt(payload)
        assert decrypted == plaintext

    def test_cross_suite_fails(self):
        """不同套件的会话不能互相解密"""
        init_aes, resp_aes = _make_sessions(CipherSuite.AES_256_GCM)
        init_sm4, resp_sm4 = _make_sessions(CipherSuite.SM4_GCM)
        _do_handshake(init_aes, resp_aes)
        _do_handshake(init_sm4, resp_sm4)

        payload = init_aes.encrypt(b"test")
        with pytest.raises(Exception):
            resp_sm4.decrypt(payload)
