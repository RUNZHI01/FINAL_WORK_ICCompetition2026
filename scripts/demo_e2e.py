#!/usr/bin/env python3
"""
端到端模拟：上位机 → 飞腾派 latent 加密传输全流程

模拟场景：
1. 上位机编码 semantic latent（模拟为随机字节）
2. ML-KEM-768 握手建立后量子会话密钥
3. AES-256-GCM / SM4-128-GCM 加密 latent
4. 通过"网络"传输密文（本地内存模拟）
5. 飞腾派解密 → 送入 TVM 重建（模拟为 pass-through）

用法:
  LD_LIBRARY_PATH=../tongsuo-dist/lib64 python3 demo_e2e.py
  # 或在 Docker 中运行
"""

import os
import sys
import time
import json
import hashlib

# 添加项目根目录到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite, EncryptedPayload
from mlkem_link.session import MLKEMSession, SessionRole, SessionState
from mlkem_link.kdf import derive_session_keys


def simulate_latent(shape=(1, 3, 64, 64), dtype="float32") -> bytes:
    """模拟 TVM 编码器输出的 latent 张量"""
    import struct
    # 用随机字节模拟 latent 数据
    size = 1
    for d in shape:
        size *= d
    bytes_per = 4 if dtype == "float32" else 2
    return os.urandom(size * bytes_per)


def simulate_network_transfer(data: bytes, latency_ms: float = 5.0) -> bytes:
    """模拟网络传输延迟"""
    time.sleep(latency_ms / 1000.0)
    return data  # 完美传输，无丢包


def main():
    suite_name = os.environ.get("CIPHER_SUITE", "SM4_GCM")
    suite = CipherSuite[suite_name]

    print("=" * 60)
    print("ML-KEM 安全语义通信 — 端到端模拟")
    print("=" * 60)
    print(f"密码套件: {suite.value}")
    print(f"KEM 后端: 自动选择（Tongsuo > liboqs；不可用则拒绝通信）")
    print()

    # ── 1. 生成模拟 latent ──
    latent = simulate_latent()
    latent_sha = hashlib.sha256(latent).hexdigest()[:16]
    print(f"[上位机] 生成 latent: {len(latent)} bytes (SHA256: {latent_sha}...)")

    # ── 2. 创建 KEM 后端和会话 ──
    backend = get_backend("768")
    print(f"[系统] KEM 后端: {backend.name}")

    initiator = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
    responder = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)

    # ── 3. ML-KEM 握手 ──
    t0 = time.perf_counter()
    pk = initiator.start_handshake()
    t_pk = time.perf_counter()

    ct = responder.respond_handshake(pk)
    t_ct = time.perf_counter()

    initiator.complete_handshake(ct)
    t_done = time.perf_counter()

    assert initiator.state == SessionState.READY
    assert responder.state == SessionState.READY

    print(f"[握手] pk={len(pk)}B, ct={len(ct)}B")
    print(f"[握手] 延迟: 发送pk={((t_pk-t0)*1000):.1f}ms, "
          f"响应ct={((t_ct-t_pk)*1000):.1f}ms, "
          f"完成={((t_done-t_ct)*1000):.1f}ms, "
          f"总计={((t_done-t0)*1000):.1f}ms")

    # ── 4. 上位机加密 latent ──
    job_metadata = json.dumps({
        "job_id": "demo-001",
        "shape": [1, 3, 64, 64],
        "dtype": "float32",
        "snr_db": 10,
    }).encode()

    t_enc = time.perf_counter()
    encrypted_payload = initiator.encrypt(latent, aad=job_metadata)
    t_enc_done = time.perf_counter()

    wire_bytes = encrypted_payload.to_bytes()
    print(f"[上位机] 加密: {len(latent)}B → {len(wire_bytes)}B "
          f"(+{len(wire_bytes)-len(latent)}B overhead) "
          f"耗时={((t_enc_done-t_enc)*1000):.1f}ms")

    # ── 5. 模拟网络传输 ──
    t_transfer_start = time.perf_counter()
    received_bytes = simulate_network_transfer(wire_bytes, latency_ms=50.0)
    t_transfer_done = time.perf_counter()
    print(f"[网络] 传输 {len(wire_bytes)}B, "
          f"耗时={((t_transfer_done-t_transfer_start)*1000):.1f}ms")

    # ── 6. 飞腾派解密 ──
    t_dec = time.perf_counter()
    restored_payload = EncryptedPayload.from_bytes(received_bytes, suite)
    decrypted_latent = responder.decrypt(restored_payload, aad=job_metadata)
    t_dec_done = time.perf_counter()

    decrypted_sha = hashlib.sha256(decrypted_latent).hexdigest()[:16]
    print(f"[飞腾派] 解密: {len(decrypted_latent)}B (SHA256: {decrypted_sha}...) "
          f"耗时={((t_dec_done-t_dec)*1000):.1f}ms")

    # ── 7. 验证 ──
    assert decrypted_latent == latent, "解密后数据与原文不匹配！"
    assert decrypted_sha == latent_sha

    # ── 8. 反向：飞腾派 → 上位机（重建结果） ──
    result = b"RECONSTRUCTION_OK_PSNR_32.5dB"
    enc_result = responder.encrypt(result)
    dec_result = initiator.decrypt(enc_result)
    assert dec_result == result

    # ── 汇总 ──
    total = (t_enc_done - t0) + (t_transfer_done - t_transfer_start) + (t_dec_done - t_dec)
    print()
    print("=" * 60)
    print(f"✓ 端到端验证通过")
    print(f"  握手: {(t_done-t0)*1000:.1f}ms (一次性开销)")
    print(f"  加密: {(t_enc_done-t_enc)*1000:.1f}ms")
    print(f"  传输: {(t_transfer_done-t_transfer_start)*1000:.1f}ms (模拟)")
    print(f"  解密: {(t_dec_done-t_dec)*1000:.1f}ms")
    print(f"  数据完整性: SHA256 匹配")
    print(f"  双向通信: 正常")
    print("=" * 60)


if __name__ == "__main__":
    main()
