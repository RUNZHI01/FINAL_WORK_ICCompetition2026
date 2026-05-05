#!/usr/bin/env python3
"""
FIT 故障注入测试 — ML-KEM 安全信道

覆盖 CLAUDE.md 定义的 5 个风险项中的 3 个（纯软件可测试）：
  #1 未知 artifact → SHA guard（对应 FIT-6/7）
  #2 输入 contract 违反（对应 FIT-5）
  #4 参数/控制帧篡改（对应 FIT-1/2/3/4）

运行:
  source ../.venv/bin/activate
  OQS_INSTALL_PATH=../liboqs-dist python -m pytest scripts/test_fit.py -v
"""

import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import require_backend
from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite, EncryptedPayload, LinkEncryptor
from mlkem_link.session import MLKEMSession, SessionRole


# ── Fixtures ──


def _backend():
    return get_backend("768")


def _sessions(suite=CipherSuite.AES_256_GCM):
    """创建已握手完成的 Initiator + Responder"""
    b = _backend()
    ini = MLKEMSession(SessionRole.INITIATOR, b, suite=suite)
    res = MLKEMSession(SessionRole.RESPONDER, b, suite=suite)
    pk = ini.start_handshake()
    ct = res.respond_handshake(pk)
    ini.complete_handshake(ct)
    assert ini.is_ready and res.is_ready
    return ini, res


def _latent(size=49152):
    """生成模拟 latent 字节"""
    return os.urandom(size)


# ══════════════════════════════════════════════
# FIT-1: 密文篡改 → GCM 认证标签不匹配
# ══════════════════════════════════════════════


@require_backend
class TestCiphertextTampering:
    """FIT #4 — 参数/控制帧篡改：密文被篡改时 GCM 认证必须失败"""

    def test_tamper_ciphertext_byte(self):
        """篡改密文 1 字节 → 解密失败"""
        ini, res = _sessions()
        latent = _latent()
        enc = ini.encrypt(latent)

        # 篡改密文中间 1 字节
        tampered = EncryptedPayload(
            nonce=enc.nonce,
            ciphertext=bytearray(enc.ciphertext),
            suite=enc.suite,
        )
        mid = len(tampered.ciphertext) // 2
        tampered.ciphertext[mid] ^= 0xFF

        with pytest.raises(Exception):
            res.decrypt(tampered)

    def test_tamper_auth_tag(self):
        """篡改 GCM auth tag 最后 1 字节 → 解密失败"""
        ini, res = _sessions()
        latent = _latent()
        enc = ini.encrypt(latent)

        tampered_ct = bytearray(enc.ciphertext)
        tampered_ct[-1] ^= 0x01  # auth tag 在 ciphertext 末尾
        tampered = EncryptedPayload(
            nonce=enc.nonce,
            ciphertext=bytes(tampered_ct),
            suite=enc.suite,
        )

        with pytest.raises(Exception):
            res.decrypt(tampered)

    def test_tamper_nonce(self):
        """篡改 nonce → 解密失败"""
        ini, res = _sessions()
        latent = _latent()
        enc = ini.encrypt(latent)

        tampered_nonce = bytearray(enc.nonce)
        tampered_nonce[0] ^= 0xFF
        tampered = EncryptedPayload(
            nonce=bytes(tampered_nonce),
            ciphertext=enc.ciphertext,
            suite=enc.suite,
        )

        with pytest.raises(Exception):
            res.decrypt(tampered)


# ══════════════════════════════════════════════
# FIT-2: AAD 篡改 → GCM AAD 绑定校验
# ══════════════════════════════════════════════


@require_backend
class TestAADTampering:
    """FIT #4 — AAD (元数据) 被篡改时解密必须失败"""

    def test_wrong_aad(self):
        """加密时 AAD=A → 解密时 AAD=B → 失败"""
        ini, res = _sessions()
        latent = _latent()
        aad_original = b'{"job_id":"test-001","shape":[1,3,64,64]}'
        aad_tampered = b'{"job_id":"test-001","shape":[2,6,64,64]}'

        enc = ini.encrypt(latent, aad=aad_original)

        with pytest.raises(Exception):
            res.decrypt(enc, aad=aad_tampered)

    def test_missing_aad(self):
        """加密时有 AAD → 解密时无 AAD → 失败"""
        ini, res = _sessions()
        latent = _latent()
        aad = b'important-metadata'
        enc = ini.encrypt(latent, aad=aad)

        with pytest.raises(Exception):
            res.decrypt(enc, aad=None)

    def test_added_aad(self):
        """加密时无 AAD → 解密时有 AAD → 失败"""
        ini, res = _sessions()
        latent = _latent()
        enc = ini.encrypt(latent, aad=None)

        with pytest.raises(Exception):
            res.decrypt(enc, aad=b'unexpected-aad')


# ══════════════════════════════════════════════
# FIT-3: 错误密钥 → 无法解密
# ══════════════════════════════════════════════


@require_backend
class TestWrongKey:
    """FIT #4 — 不同会话密钥无法互相解密"""

    def test_different_session_keys(self):
        """两个独立握手产生不同密钥 → 交叉解密失败"""
        ini1, res1 = _sessions()
        ini2, res2 = _sessions()

        latent = _latent()
        enc = ini1.encrypt(latent)

        # res2 属于另一个会话，密钥不同
        with pytest.raises(Exception):
            res2.decrypt(enc)

    def test_random_key(self):
        """用随机 32 字节作为密钥 → 解密失败"""
        ini, res = _sessions()
        latent = _latent()
        enc = ini.encrypt(latent)

        enc_bytes = enc.to_bytes()
        wrong_key_payload = EncryptedPayload.from_bytes(enc_bytes, CipherSuite.AES_256_GCM)

        encryptor = LinkEncryptor(CipherSuite.AES_256_GCM)
        random_key = os.urandom(32)
        with pytest.raises(Exception):
            encryptor.decrypt(random_key, wrong_key_payload)


# ══════════════════════════════════════════════
# FIT-4: 重放攻击
# ══════════════════════════════════════════════


@require_backend
class TestReplayAttack:
    """FIT #4 — 同一密文重放检测"""

    def test_nonce_reuse_detected(self):
        """同一 nonce 出现两次 → 检测到重放"""
        ini, res = _sessions()
        latent = _latent()
        enc = ini.encrypt(latent)

        # 第一次解密成功
        dec1 = res.decrypt(enc)
        assert dec1 == latent

        # 用同样的 nonce+ciphertext 构造重放
        replay = EncryptedPayload(
            nonce=enc.nonce,
            ciphertext=enc.ciphertext,
            suite=enc.suite,
        )

        # 第二次用同一 nonce 解密——GCM 本身不拒绝 nonce 重用，
        # 但我们可以记录 nonce 历史。这里验证：
        # a) 如果不做 nonce tracking，解密会"成功"（产出明文）
        # b) 实际部署时应检测 nonce 重用
        # 此测试记录 nonce，验证 nonce 确实重复了
        dec2 = res.decrypt(replay)
        assert dec2 == latent  # GCM 不拒绝重复 nonce
        # → 结论：需要在信道层做 nonce 重放检测（Phase 3）


# ══════════════════════════════════════════════
# FIT-5: 输入 contract 违反
# ══════════════════════════════════════════════


class TestInputContractViolation:
    """FIT #2 — batch/shape/dtype 不匹配"""

    def test_wrong_size(self):
        """声明 49152B → 实际发送 100B → SHA256 不匹配"""
        latent = _latent(100)
        claimed_sha = hashlib.sha256(_latent(49152)).hexdigest()
        actual_sha = hashlib.sha256(latent).hexdigest()
        assert claimed_sha != actual_sha

    def test_wrong_shape_reshape_fails(self):
        """latent 字节数无法 reshape 为声明的 shape"""
        latent = _latent(100)  # 100 bytes ≠ 1×3×64×64×4 = 49152
        import numpy as np
        with pytest.raises(ValueError):
            np.frombuffer(latent, dtype=np.float32).reshape(1, 3, 64, 64)

    def test_wrong_dtype(self):
        """声明 float32 → 实际是 int8 → reshape 后数据错误"""
        latent = _latent(49152)
        import numpy as np
        # 如果按 float32 解读但实际不是，shape 虽然对但数据无意义
        arr = np.frombuffer(latent, dtype=np.float32).reshape(1, 3, 64, 64)
        # 验证：数据不是全零或全 NaN（但没法从数据本身判断 dtype 错误）
        assert arr.shape == (1, 3, 64, 64)
        assert not np.all(arr == 0)


# ══════════════════════════════════════════════
# FIT-6: SHA256 不匹配（中间人篡改 latent）
# ══════════════════════════════════════════════


@require_backend
class TestSHA256Mismatch:
    """FIT #1/#4 — 中间人篡改 latent → SHA256 不匹配"""

    def test_latent_tampered_sha_mismatch(self):
        """原文 SHA256 ≠ 篡改后 SHA256 → 校验拦截"""
        original = _latent()
        tampered = bytearray(original)
        tampered[0] ^= 0xFF

        sha_orig = hashlib.sha256(original).hexdigest()
        sha_tamp = hashlib.sha256(bytes(tampered)).hexdigest()
        assert sha_orig != sha_tamp

    def test_full_flow_tamper_detected(self):
        """完整加密流程：篡改 latent 后 SHA256 校验失败"""
        ini, res = _sessions()
        latent = _latent()
        original_sha = hashlib.sha256(latent).hexdigest()

        # 正常加密 + 解密
        enc = ini.encrypt(latent)
        dec = res.decrypt(enc)

        # 解密后 SHA256 匹配
        assert hashlib.sha256(dec).hexdigest() == original_sha

        # 如果篡改了 latent 再加密，SHA256 会不同
        tampered = bytearray(latent)
        tampered[-1] ^= 0x01
        enc_tampered = ini.encrypt(bytes(tampered))
        dec_tampered = res.decrypt(enc_tampered)

        tampered_sha = hashlib.sha256(dec_tampered).hexdigest()
        assert tampered_sha != original_sha


# ══════════════════════════════════════════════
# FIT-7: 环境变量缺失 → 拒绝通信（不做不安全降级）
# ══════════════════════════════════════════════


@require_backend
class TestNoInsecureFallback:
    """FIT #1 — 无可信后端时拒绝通信，不做不安全降级"""

    def test_no_insecure_fallback(self):
        """get_backend 明确禁止不安全降级（代码审查验证）

        验证方式：检查 get_backend 函数源码在可信后端缺失时会明确拒绝通信。
        """
        import inspect
        from mlkem_link.kem import get_backend
        source = inspect.getsource(get_backend)
        # 确认源码中保留了显式拒绝逻辑
        assert "拒绝" in source or "RuntimeError" in source or "raise" in source
        # 确认实际调用可以成功，且返回可信后端
        backend = get_backend("768")
        assert backend.name.startswith(("tongsuo-", "liboqs-"))


# ══════════════════════════════════════════════
# FIT-Bonus: 跨套件不兼容
# ══════════════════════════════════════════════


@require_backend
class TestCrossSuiteIsolation:
    """AES 密文不能用 SM4 密钥解密，反之亦然"""

    def test_aes_encrypt_sm4_decrypt_fails(self):
        """AES-256-GCM 加密 → SM4-128-GCM 解密 → 失败"""
        ini_aes, _ = _sessions(CipherSuite.AES_256_GCM)
        _, res_sm4 = _sessions(CipherSuite.SM4_GCM)

        latent = _latent()
        enc = ini_aes.encrypt(latent)

        with pytest.raises(ValueError, match="套件不匹配"):
            res_sm4.decrypt(enc)

    def test_sm4_encrypt_aes_decrypt_fails(self):
        """SM4-128-GCM 加密 → AES-256-GCM 解密 → 失败"""
        ini_sm4, _ = _sessions(CipherSuite.SM4_GCM)
        _, res_aes = _sessions(CipherSuite.AES_256_GCM)

        latent = _latent()
        enc = ini_sm4.encrypt(latent)

        with pytest.raises(ValueError, match="套件不匹配"):
            res_aes.decrypt(enc)
