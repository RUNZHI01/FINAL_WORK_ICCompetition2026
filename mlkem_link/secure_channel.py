"""
安全信道协议 — 基于 ML-KEM 会话的 TCP 加密通信层

线协议:
  帧格式: 4B big-endian 长度 + payload

握手阶段:
  Initiator → Responder: pk  (ML-KEM-768 公钥, 1184B)
  Responder → Initiator: ct  (ML-KEM-768 密文, 1088B)

数据阶段:
  发送方 → 接收方: EncryptedPayload.to_bytes()
"""

import struct
import socket
import time
import os

from .session import MLKEMSession, SessionRole, SessionState
from .crypto import CipherSuite, EncryptedPayload
from .kem import KEMBackend
from .auth import (
    IdentityConfig,
    ClientHello,
    ServerHelloAuth,
    PROTO_VERSION,
    NONCE_BYTES,
    SigPolicy,
    build_transcript,
    sign_transcript,
    verify_transcript,
    derive_finished_keys,
    create_finished_message,
    verify_finished_message,
    get_sm2_backend,
    get_mldsa_backend,
    encode_client_hello,
    decode_client_hello,
    encode_server_hello_auth,
    decode_server_hello_auth,
)

# 帧头: 4 字节 big-endian 无符号整数
_FRAME_HEADER = struct.Struct("!I")
_FRAME_HEADER_SIZE = _FRAME_HEADER.size  # 4

# 安全限制: 单帧最大 64 MB
_MAX_FRAME_SIZE = 64 * 1024 * 1024


class SecureChannel:
    """基于 ML-KEM 会话的安全信道

    用法 (Initiator / 上位机):
        channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)
        channel.handshake()
        channel.send_encrypted(data, aad=metadata)
        ack = channel.recv_encrypted()

    用法 (Responder / 飞腾派):
        channel = SecureChannel(sock, SessionRole.RESPONDER, backend, suite)
        channel.handshake()
        data = channel.recv_encrypted(aad=metadata)
        channel.send_encrypted(ack)
    """

    def __init__(self, conn: socket.socket, role: SessionRole,
                 backend: KEMBackend,
                 suite: CipherSuite = CipherSuite.SM4_GCM):
        self._conn = conn
        self._session = MLKEMSession(role, backend, suite)
        self._auth_enabled = False
        self._auth_sig_policy = ""
        self._peer_server_id = ""

    @property
    def state(self) -> SessionState:
        return self._session.state

    @property
    def is_ready(self) -> bool:
        return self._session.is_ready

    @property
    def cipher_suite(self) -> CipherSuite:
        return self._session.cipher_suite

    @property
    def auth_enabled(self) -> bool:
        return self._auth_enabled

    @property
    def auth_sig_policy(self) -> str:
        return self._auth_sig_policy

    @property
    def peer_server_id(self) -> str:
        return self._peer_server_id

    # ── 帧读写 ──

    @staticmethod
    def send_frame(sock: socket.socket, data: bytes) -> None:
        """发送一帧: 4B 长度头 + payload"""
        header = _FRAME_HEADER.pack(len(data))
        sock.sendall(header + data)

    @staticmethod
    def recv_frame(sock: socket.socket,
                   max_size: int = _MAX_FRAME_SIZE) -> bytes:
        """接收一帧: 读取 4B 长度头，再读取对应长度的 payload"""
        header = _recv_exact(sock, _FRAME_HEADER_SIZE)
        length = _FRAME_HEADER.unpack(header)[0]
        if length > max_size:
            raise ValueError(
                f"帧过大: {length} bytes (上限 {max_size} bytes)")
        return _recv_exact(sock, length)

    # ── 握手 ──

    def handshake(self) -> float:
        """完成 ML-KEM 握手，返回耗时 (ms)

        Initiator: 发送 pk → 等待 ct → complete
        Responder: 等待 pk → 发送 ct
        """
        t0 = time.perf_counter()

        if self._session.role == SessionRole.INITIATOR:
            pk = self._session.start_handshake()
            self.send_frame(self._conn, pk)
            ct = self.recv_frame(self._conn)
            self._session.complete_handshake(ct)
        else:
            pk = self.recv_frame(self._conn)
            ct = self._session.respond_handshake(pk)
            self.send_frame(self._conn, ct)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        return elapsed_ms

    def authenticated_handshake(self, auth: IdentityConfig) -> float:
        """完成带身份认证和 Finished 确认的握手。"""
        t0 = time.perf_counter()

        if self._session.role == SessionRole.INITIATOR:
            self._auth_initiator(auth)
        else:
            self._auth_responder(auth)

        self._auth_enabled = True
        self._auth_sig_policy = auth.sig_policy.value
        self._peer_server_id = str(auth.server_id or "")
        return (time.perf_counter() - t0) * 1000

    def _auth_initiator(self, auth: IdentityConfig) -> None:
        pk = self._session.start_handshake()
        client_nonce = os.urandom(NONCE_BYTES)
        hello = ClientHello(
            proto_version=PROTO_VERSION,
            suite=self._session.cipher_suite,
            client_nonce=client_nonce,
            kem_pk=pk,
        )
        self.send_frame(self._conn, encode_client_hello(hello))

        response = decode_server_hello_auth(self.recv_frame(self._conn))
        if auth.sig_policy == SigPolicy.DUAL_REQUIRED and response.sig_policy != SigPolicy.DUAL_REQUIRED:
            raise RuntimeError(
                f"策略降级拒绝：本地要求 DUAL_REQUIRED，服务端返回 {response.sig_policy.value}"
            )

        transcript = build_transcript(
            PROTO_VERSION,
            self._session.cipher_suite,
            client_nonce,
            response.server_nonce,
            pk,
            response.kem_ct,
            response.server_id,
            response.sig_policy,
        )

        sm2_backend = None if auth.sig_policy == SigPolicy.MLDSA_ONLY else get_sm2_backend()
        mldsa_backend = None if auth.sig_policy == SigPolicy.SM2_ONLY else get_mldsa_backend()
        verify_result = verify_transcript(
            sm2_backend,
            mldsa_backend,
            auth.peer_sm2_pk,
            auth.peer_mldsa_pk,
            transcript,
            response.sm2_signature,
            response.mldsa_signature,
            auth.sig_policy,
        )
        if not verify_result.verified:
            raise RuntimeError(f"身份认证失败: {verify_result.error}")

        self._session.complete_handshake(response.kem_ct)
        self._peer_server_id = response.server_id.decode("utf-8", errors="replace")

        fk_c2s, fk_s2c = derive_finished_keys(self._session.shared_secret, self._session.cipher_suite)
        client_finished = create_finished_message(
            fk_c2s,
            b"client_finished",
            transcript,
            self._session.cipher_suite,
        )
        self.send_frame(self._conn, client_finished)
        server_finished = self.recv_frame(self._conn)
        if not verify_finished_message(
            fk_s2c,
            b"server_finished",
            transcript,
            self._session.cipher_suite,
            server_finished,
        ):
            raise RuntimeError("服务端 Finished 验证失败，密钥确认未通过")

    def _auth_responder(self, auth: IdentityConfig) -> None:
        hello = decode_client_hello(self.recv_frame(self._conn))
        ct = self._session.respond_handshake(hello.kem_pk)

        server_nonce = os.urandom(NONCE_BYTES)
        server_id_bytes = auth.server_id.encode()
        transcript = build_transcript(
            hello.proto_version,
            hello.suite,
            hello.client_nonce,
            server_nonce,
            hello.kem_pk,
            ct,
            server_id_bytes,
            auth.sig_policy,
        )

        sm2_backend = None if auth.sig_policy == SigPolicy.MLDSA_ONLY else get_sm2_backend()
        mldsa_backend = None if auth.sig_policy == SigPolicy.SM2_ONLY else get_mldsa_backend()
        sm2_sig, mldsa_sig = sign_transcript(
            sm2_backend,
            mldsa_backend,
            auth.server_sm2_sk,
            auth.server_mldsa_sk,
            transcript,
            auth.sig_policy,
        )
        response = ServerHelloAuth(
            server_id=server_id_bytes,
            server_nonce=server_nonce,
            kem_ct=ct,
            sig_policy=auth.sig_policy,
            sm2_signature=sm2_sig,
            mldsa_signature=mldsa_sig,
        )
        self.send_frame(self._conn, encode_server_hello_auth(response))

        fk_c2s, fk_s2c = derive_finished_keys(self._session.shared_secret, self._session.cipher_suite)
        client_finished = self.recv_frame(self._conn)
        if not verify_finished_message(
            fk_c2s,
            b"client_finished",
            transcript,
            self._session.cipher_suite,
            client_finished,
        ):
            raise RuntimeError("客户端 Finished 验证失败，密钥确认未通过")

        server_finished = create_finished_message(
            fk_s2c,
            b"server_finished",
            transcript,
            self._session.cipher_suite,
        )
        self.send_frame(self._conn, server_finished)

    # ── 加密收发 ──

    def send_encrypted(self, plaintext: bytes,
                       aad: bytes = None) -> None:
        """加密并通过信道发送"""
        payload = self._session.encrypt(plaintext, aad)
        self.send_frame(self._conn, payload.to_bytes())

    def recv_encrypted(self, aad: bytes = None) -> bytes:
        """从信道接收并解密"""
        raw = self.recv_frame(self._conn)
        payload = EncryptedPayload.from_bytes(raw, self._session.cipher_suite)
        return self._session.decrypt(payload, aad)

    # ── 原始帧读写（便捷别名）──

    def send_raw(self, data: bytes) -> None:
        """发送未加密的原始帧（用于元数据等非敏感信息）"""
        self.send_frame(self._conn, data)

    def recv_raw(self, max_size: int = _MAX_FRAME_SIZE) -> bytes:
        """接收未加密的原始帧"""
        return self.recv_frame(self._conn, max_size)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """从 socket 精确读取 n 字节"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(
                f"连接关闭: 期望 {n} 字节，已读 {len(buf)} 字节")
        buf.extend(chunk)
    return bytes(buf)
