import os
import socket
import threading
from unittest.mock import patch

import pytest

from mlkem_link.auth import (
    PROTO_VERSION,
    NONCE_BYTES,
    AuthResult,
    ClientHello,
    IdentityConfig,
    MockSigBackend,
    ServerHelloAuth,
    SigPolicy,
    build_transcript,
    create_finished_message,
    decode_client_hello,
    decode_server_hello_auth,
    derive_finished_keys,
    encode_client_hello,
    encode_server_hello_auth,
    sign_transcript,
    verify_finished_message,
    verify_transcript,
)
from mlkem_link.crypto import CipherSuite
from mlkem_link.kem import get_backend
from mlkem_link.secure_channel import SecureChannel
from mlkem_link.session import SessionRole


def _mock_pair() -> tuple[MockSigBackend, MockSigBackend]:
    return MockSigBackend(), MockSigBackend()


def _kem_backend():
    try:
        return get_backend("768")
    except RuntimeError:
        pytest.skip("无可用 KEM 后端，跳过认证握手测试")


class TestTranscript:
    def test_transcript_is_deterministic(self) -> None:
        t1 = build_transcript(
            PROTO_VERSION,
            CipherSuite.SM4_GCM,
            b"A" * NONCE_BYTES,
            b"B" * NONCE_BYTES,
            b"C" * 1184,
            b"D" * 1088,
            b"board-01",
            SigPolicy.DUAL_REQUIRED,
        )
        t2 = build_transcript(
            PROTO_VERSION,
            CipherSuite.SM4_GCM,
            b"A" * NONCE_BYTES,
            b"B" * NONCE_BYTES,
            b"C" * 1184,
            b"D" * 1088,
            b"board-01",
            SigPolicy.DUAL_REQUIRED,
        )
        assert t1 == t2

    def test_transcript_changes_when_input_changes(self) -> None:
        base = build_transcript(
            PROTO_VERSION,
            CipherSuite.SM4_GCM,
            b"A" * NONCE_BYTES,
            b"B" * NONCE_BYTES,
            b"C" * 1184,
            b"D" * 1088,
            b"board-01",
            SigPolicy.DUAL_REQUIRED,
        )
        changed = build_transcript(
            PROTO_VERSION,
            CipherSuite.SM4_GCM,
            b"A" * NONCE_BYTES,
            b"X" * NONCE_BYTES,
            b"C" * 1184,
            b"D" * 1088,
            b"board-01",
            SigPolicy.DUAL_REQUIRED,
        )
        assert base != changed


class TestWireCodec:
    def test_client_hello_roundtrip(self) -> None:
        hello = ClientHello(
            proto_version=PROTO_VERSION,
            suite=CipherSuite.SM4_GCM,
            client_nonce=os.urandom(NONCE_BYTES),
            kem_pk=os.urandom(1184),
        )
        restored = decode_client_hello(encode_client_hello(hello))
        assert restored == hello

    def test_server_hello_roundtrip(self) -> None:
        payload = ServerHelloAuth(
            server_id=b"phytium-board-01",
            server_nonce=os.urandom(NONCE_BYTES),
            kem_ct=os.urandom(1088),
            sig_policy=SigPolicy.DUAL_REQUIRED,
            sm2_signature=os.urandom(64),
            mldsa_signature=os.urandom(3309),
        )
        restored = decode_server_hello_auth(encode_server_hello_auth(payload))
        assert restored == payload


class TestSignVerify:
    def test_dual_required_success(self) -> None:
        sm2_be, mldsa_be = _mock_pair()
        sm2_pk, sm2_sk = sm2_be.keygen()
        mldsa_pk, mldsa_sk = mldsa_be.keygen()
        transcript = b"test transcript"

        sm2_sig, mldsa_sig = sign_transcript(
            sm2_be,
            mldsa_be,
            sm2_sk,
            mldsa_sk,
            transcript,
            SigPolicy.DUAL_REQUIRED,
        )
        result = verify_transcript(
            sm2_be,
            mldsa_be,
            sm2_pk,
            mldsa_pk,
            transcript,
            sm2_sig,
            mldsa_sig,
            SigPolicy.DUAL_REQUIRED,
        )
        assert result == AuthResult(verified=True, sm2_ok=True, mldsa_ok=True, error=None)

    def test_tampered_transcript_is_rejected(self) -> None:
        sm2_be, mldsa_be = _mock_pair()
        sm2_pk, sm2_sk = sm2_be.keygen()
        mldsa_pk, mldsa_sk = mldsa_be.keygen()

        sm2_sig, mldsa_sig = sign_transcript(
            sm2_be,
            mldsa_be,
            sm2_sk,
            mldsa_sk,
            b"original",
            SigPolicy.DUAL_REQUIRED,
        )
        result = verify_transcript(
            sm2_be,
            mldsa_be,
            sm2_pk,
            mldsa_pk,
            b"tampered",
            sm2_sig,
            mldsa_sig,
            SigPolicy.DUAL_REQUIRED,
        )
        assert not result.verified


class TestFinished:
    def test_finished_roundtrip(self) -> None:
        fk_c2s, fk_s2c = derive_finished_keys(os.urandom(32), CipherSuite.AES_256_GCM)
        assert len(fk_c2s) == 32
        assert len(fk_s2c) == 32
        assert fk_c2s != fk_s2c

        transcript = b"transcript"
        payload = create_finished_message(
            fk_c2s,
            b"client_finished",
            transcript,
            CipherSuite.AES_256_GCM,
        )
        assert verify_finished_message(
            fk_c2s,
            b"client_finished",
            transcript,
            CipherSuite.AES_256_GCM,
            payload,
        )


class TestAuthenticatedSecureChannel:
    def test_authenticated_handshake_with_mock_backends(self) -> None:
        kem = _kem_backend()
        client_sock, server_sock = socket.socketpair()
        initiator = SecureChannel(client_sock, SessionRole.INITIATOR, kem, CipherSuite.AES_256_GCM)
        responder = SecureChannel(server_sock, SessionRole.RESPONDER, kem, CipherSuite.AES_256_GCM)

        sm2_backend = MockSigBackend()
        mldsa_backend = MockSigBackend()
        sm2_pk, sm2_sk = sm2_backend.keygen()
        mldsa_pk, mldsa_sk = mldsa_backend.keygen()

        client_cfg = IdentityConfig(
            role=SessionRole.INITIATOR,
            server_id="test-board",
            peer_sm2_pk=sm2_pk,
            peer_mldsa_pk=mldsa_pk,
            sig_policy=SigPolicy.DUAL_REQUIRED,
        )
        server_cfg = IdentityConfig(
            role=SessionRole.RESPONDER,
            server_id="test-board",
            server_sm2_sk=sm2_sk,
            server_sm2_pk=sm2_pk,
            server_mldsa_sk=mldsa_sk,
            server_mldsa_pk=mldsa_pk,
            sig_policy=SigPolicy.DUAL_REQUIRED,
        )

        results: dict[str, object] = {}

        def run_responder() -> None:
            try:
                results["server_ms"] = responder.authenticated_handshake(server_cfg)
            except Exception as exc:  # pragma: no cover - surfaced via assertion below
                results["server_error"] = exc

        thread = threading.Thread(target=run_responder, daemon=True)
        thread.start()
        try:
            with (
                patch("mlkem_link.secure_channel.get_sm2_backend", return_value=sm2_backend),
                patch("mlkem_link.secure_channel.get_mldsa_backend", return_value=mldsa_backend),
            ):
                client_ms = initiator.authenticated_handshake(client_cfg)
        finally:
            thread.join(timeout=10)
            client_sock.close()
            server_sock.close()

        assert "server_error" not in results
        assert isinstance(results.get("server_ms"), float)
        assert client_ms > 0
        assert initiator.is_ready
        assert responder.is_ready
        assert initiator.auth_enabled
        assert responder.auth_enabled
        assert initiator.auth_sig_policy == "DUAL_REQUIRED"
        assert responder.auth_sig_policy == "DUAL_REQUIRED"
        assert initiator.peer_server_id == "test-board"
