from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from mlkem_link.auth import IdentityConfig, SigPolicy, get_mldsa_backend, get_sm2_backend
from mlkem_link.crypto import CipherSuite
from mlkem_link.kem import get_backend
from mlkem_link.secure_channel import SecureChannel
from mlkem_link.session import SessionRole


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REMOTE_HELPER = PROJECT_ROOT / "scripts" / "tui_remote_tcp_server.py"


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _start_helper(*, tmp_path: Path, extra_env: dict[str, str] | None = None) -> tuple[subprocess.Popen[str], int]:
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if extra_env:
        env.update(extra_env)
    proc = subprocess.Popen(
        [
            sys.executable,
            str(REMOTE_HELPER),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--output-dir",
            str(tmp_path / "recv"),
            "--suite",
            "SM4_GCM",
            "--kem",
            "768",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    assert proc.stdout is not None
    first_line = proc.stdout.readline().strip()
    assert first_line.startswith("监听 "), first_line
    return proc, port


def _stop_helper(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _run_client(*, port: int, client_config: IdentityConfig | None) -> tuple[dict, SecureChannel]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(("127.0.0.1", port))
    channel = SecureChannel(sock, SessionRole.INITIATOR, get_backend("768"), CipherSuite.SM4_GCM)
    if client_config is None:
        channel.handshake()
    else:
        channel.authenticated_handshake(client_config)

    payload = b"payload-for-test"
    meta = json.dumps(
        {
            "job_id": "pytest-smoke",
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    ).encode("utf-8")
    channel.send_encrypted(meta, aad=b"metadata")
    channel.send_encrypted(payload, aad=meta)
    ack = json.loads(channel.recv_encrypted(aad=b"ack"))
    sock.close()
    return ack, channel


def test_tui_remote_tcp_server_plain(tmp_path: Path) -> None:
    proc, port = _start_helper(tmp_path=tmp_path)
    try:
        ack, _channel = _run_client(port=port, client_config=None)
        assert ack["status"] == "ok"
        assert ack["sha256_match"] is True
        saved = tmp_path / "recv" / "pytest-smoke.bin"
        assert saved.read_bytes() == b"payload-for-test"
    finally:
        _stop_helper(proc)


def test_tui_remote_tcp_server_with_dual_auth(tmp_path: Path) -> None:
    try:
        sm2_backend = get_sm2_backend()
        mldsa_backend = get_mldsa_backend()
    except Exception as exc:
        pytest.skip(f"认证后端不可用: {exc}")

    sm2_pk, sm2_sk = sm2_backend.keygen()
    mldsa_pk, mldsa_sk = mldsa_backend.keygen()
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    (key_dir / "server_sm2_identity.key").write_bytes(sm2_sk)
    (key_dir / "server_sm2_identity.pub").write_bytes(sm2_pk)
    (key_dir / "server_mldsa_identity.key").write_bytes(mldsa_sk)
    (key_dir / "server_mldsa_identity.pub").write_bytes(mldsa_pk)

    proc, port = _start_helper(
        tmp_path=tmp_path,
        extra_env={
            "MLKEM_AUTH_ENABLED": "1",
            "MLKEM_AUTH_SERVER_ID": "phytium-board",
            "MLKEM_AUTH_SIG_POLICY": "DUAL_REQUIRED",
            "MLKEM_AUTH_SERVER_SM2_KEY": str(key_dir / "server_sm2_identity.key"),
            "MLKEM_AUTH_SERVER_SM2_PUB": str(key_dir / "server_sm2_identity.pub"),
            "MLKEM_AUTH_SERVER_MLDSA_KEY": str(key_dir / "server_mldsa_identity.key"),
            "MLKEM_AUTH_SERVER_MLDSA_PUB": str(key_dir / "server_mldsa_identity.pub"),
        },
    )
    try:
        ack, channel = _run_client(
            port=port,
            client_config=IdentityConfig(
                role=SessionRole.INITIATOR,
                server_id="phytium-board",
                peer_sm2_pk=sm2_pk,
                peer_mldsa_pk=mldsa_pk,
                sig_policy=SigPolicy.DUAL_REQUIRED,
            ),
        )
        assert channel.peer_server_id == "phytium-board"
        assert ack["status"] == "ok"
        assert ack["sha256_match"] is True
        saved = tmp_path / "recv" / "pytest-smoke.bin"
        assert saved.read_bytes() == b"payload-for-test"
    finally:
        _stop_helper(proc)


def test_tui_remote_tcp_server_ignores_readiness_probe_disconnect(tmp_path: Path) -> None:
    proc, port = _start_helper(tmp_path=tmp_path)
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(5)
        probe.connect(("127.0.0.1", port))
        probe.close()
        time.sleep(0.2)

        ack, _channel = _run_client(port=port, client_config=None)
        assert ack["status"] == "ok"
        assert ack["sha256_match"] is True
    finally:
        _stop_helper(proc)
