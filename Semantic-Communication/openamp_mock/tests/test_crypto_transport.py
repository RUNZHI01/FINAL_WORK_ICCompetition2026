from __future__ import annotations

import unittest

from openamp_mock.crypto_guard import CryptoGuard
from openamp_mock.crypto_transport import CryptoTransport
from openamp_mock.demo import (
    MockSession,
    run_allow_scenario,
    run_input_contract_deny_scenario,
    run_timeout_scenario,
    run_wrong_sha_deny_scenario,
)
from openamp_mock.guard import SafetyGuard
from openamp_mock.orchestrator import Orchestrator
from openamp_mock.protocol import FORMAL_TRUSTED_CURRENT_SHA, JobSpec, MessageType, build_message
from openamp_mock.transport import MockTransport

try:
    from mlkem_link.crypto import CipherSuite
    _HAS_MLKEM = True
except ImportError:
    _HAS_MLKEM = False


def _skip_if_no_mlkem(test_func):
    import functools

    @functools.wraps(test_func)
    def wrapper(self, *args, **kwargs):
        if not _HAS_MLKEM:
            self.skipTest("mlkem_link not available")
        return test_func(self, *args, **kwargs)

    return wrapper


def _sm4_available() -> bool:
    if not _HAS_MLKEM:
        return False
    try:
        from mlkem_link.crypto import LinkEncryptor
        LinkEncryptor(CipherSuite.SM4_GCM)
        return True
    except (RuntimeError, Exception):
        return False


# ══════════════════════════════════════════════
# AES-256-GCM（原有用例，保持不变）
# ══════════════════════════════════════════════

class CryptoTransportTest(unittest.TestCase):
    def test_encrypt_and_decrypt_roundtrip(self) -> None:
        guard = CryptoGuard(shared_secret=b"k" * 32)
        message = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=42,
            payload={"expected_sha256": FORMAL_TRUSTED_CURRENT_SHA},
        )
        encrypted = guard.encrypt(message)
        self.assertEqual(encrypted.header.msg_type, int(MessageType.ENCRYPTED_CTRL))
        decrypted = guard.decrypt(encrypted)
        self.assertEqual(decrypted.header.msg_type, int(MessageType.JOB_REQ))
        self.assertEqual(decrypted.payload, message.payload)

    def test_mock_closed_loop_still_passes_with_crypto_transport(self) -> None:
        transport = CryptoTransport(MockTransport(), CryptoGuard(shared_secret=b"s" * 32))
        guard = SafetyGuard(trusted_sha256=FORMAL_TRUSTED_CURRENT_SHA)
        orchestrator = Orchestrator()

        now_ms = 0
        job = JobSpec(job_id=7001, expected_sha256=FORMAL_TRUSTED_CURRENT_SHA, flags="payload")
        orchestrator.submit_job(job, now_ms, transport)

        while transport.has_pending():
            while transport.has_linux_pending():
                guard.handle(transport.pop_for_guard(), now_ms, transport)
            while transport.has_guard_pending():
                orchestrator.handle(transport.pop_for_linux(), now_ms)

        self.assertEqual(orchestrator.state.value, "ALLOWED")
        self.assertEqual(guard.state.value, "JOB_ACTIVE")
        self.assertGreater(transport.stats["encrypt_tx"], 0)
        self.assertGreater(transport.stats["decrypt_rx"], 0)

    def test_existing_plain_mock_scenario_unchanged(self) -> None:
        _, result = run_allow_scenario()
        self.assertTrue(result["passed"])

    def test_mock_session_can_enable_crypto_transport(self) -> None:
        session = MockSession(use_crypto_transport=True)
        job = JobSpec(job_id=7002, expected_sha256=FORMAL_TRUSTED_CURRENT_SHA, flags="payload")
        session.orchestrator.submit_job(job, session.now_ms, session.transport)
        session.pump()
        self.assertEqual(session.orchestrator.state.value, "ALLOWED")
        self.assertEqual(session.guard.state.value, "JOB_ACTIVE")

    def test_all_core_scenarios_pass_with_crypto_transport(self) -> None:
        for runner in (
            run_allow_scenario,
            run_wrong_sha_deny_scenario,
            run_input_contract_deny_scenario,
            run_timeout_scenario,
        ):
            _, result = runner(use_crypto_transport=True)
            self.assertTrue(result["passed"])
            self.assertTrue(result["control_plane_encrypted"])
            crypto_stats = result["control_plane_crypto_stats"]
            self.assertGreater(crypto_stats["encrypt_tx"], 0)


# ══════════════════════════════════════════════
# SM4-128-GCM 套件覆盖（国密路径）
# ══════════════════════════════════════════════

class SM4CryptoTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        if not _sm4_available():
            self.skipTest("SM4-GCM 不可用（需要 cryptography >= 46.0 + OpenSSL 3.x）")

    def test_sm4_encrypt_and_decrypt_roundtrip(self) -> None:
        """SM4-GCM 控制面消息加解密往返"""
        guard = CryptoGuard(shared_secret=b"k" * 32, suite=CipherSuite.SM4_GCM)
        message = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=42,
            payload={"expected_sha256": FORMAL_TRUSTED_CURRENT_SHA},
        )
        encrypted = guard.encrypt(message)
        self.assertEqual(encrypted.header.msg_type, int(MessageType.ENCRYPTED_CTRL))
        self.assertEqual(encrypted.payload["suite"], "sm4-gcm")
        decrypted = guard.decrypt(encrypted)
        self.assertEqual(decrypted.header.msg_type, int(MessageType.JOB_REQ))
        self.assertEqual(decrypted.payload, message.payload)

    def test_sm4_suite_tag_in_payload(self) -> None:
        """加密后外层 payload 中 suite 字段必须为 sm4-gcm"""
        guard = CryptoGuard(shared_secret=b"x" * 32, suite=CipherSuite.SM4_GCM)
        message = build_message(
            msg_type=MessageType.HEARTBEAT,
            seq=5,
            job_id=99,
            payload={"elapsed_ms": 100},
        )
        encrypted = guard.encrypt(message)
        self.assertEqual(encrypted.payload.get("suite"), "sm4-gcm")

    def test_sm4_suite_mismatch_raises(self) -> None:
        """AES 加密 + SM4 解密应抛出异常（套件不匹配）"""
        aes_guard = CryptoGuard(shared_secret=b"k" * 32)
        sm4_guard = CryptoGuard(shared_secret=b"k" * 32, suite=CipherSuite.SM4_GCM)
        message = build_message(
            msg_type=MessageType.JOB_REQ,
            seq=1,
            job_id=1,
            payload={"expected_sha256": FORMAL_TRUSTED_CURRENT_SHA},
        )
        encrypted_with_aes = aes_guard.encrypt(message)
        with self.assertRaises(Exception):
            sm4_guard.decrypt(encrypted_with_aes)

    def test_sm4_mock_session_closed_loop(self) -> None:
        """SM4 套件下控制面完整闭环：JOB_REQ → JOB_ACK(ALLOW) → JOB_DONE"""
        session = MockSession(use_crypto_transport=True, suite=CipherSuite.SM4_GCM)
        job = JobSpec(job_id=8001, expected_sha256=FORMAL_TRUSTED_CURRENT_SHA, flags="payload")
        session.orchestrator.submit_job(job, session.now_ms, session.transport)
        session.pump()
        self.assertEqual(session.orchestrator.state.value, "ALLOWED")
        self.assertEqual(session.guard.state.value, "JOB_ACTIVE")
        stats = session.transport.stats
        self.assertGreater(stats["encrypt_tx"], 0)
        self.assertGreater(stats["decrypt_rx"], 0)

    def test_sm4_all_core_scenarios(self) -> None:
        """SM4 套件下四个核心场景全部通过"""
        for runner in (
            run_allow_scenario,
            run_wrong_sha_deny_scenario,
            run_input_contract_deny_scenario,
            run_timeout_scenario,
        ):
            _, result = runner(use_crypto_transport=True)
            self.assertTrue(result["passed"], msg=f"场景 {result['scenario']} 未通过")
            self.assertTrue(result["control_plane_encrypted"])
            self.assertGreater(result["control_plane_crypto_stats"]["encrypt_tx"], 0)

    def test_sm4_default_in_mock_session(self) -> None:
        """MockSession 默认应使用 SM4_GCM（与 crypto_runtime 默认保持一致）"""
        session = MockSession(use_crypto_transport=True)
        # 取第一条 ctrl_log 消息验证 suite 字段
        job = JobSpec(job_id=8002, expected_sha256=FORMAL_TRUSTED_CURRENT_SHA, flags="payload")
        session.orchestrator.submit_job(job, session.now_ms, session.transport)
        session.pump()
        # 直接检查 CryptoGuard 的 suite
        crypto_guard = session.transport._crypto_guard
        self.assertEqual(crypto_guard.suite, CipherSuite.SM4_GCM)


if __name__ == "__main__":
    unittest.main()
