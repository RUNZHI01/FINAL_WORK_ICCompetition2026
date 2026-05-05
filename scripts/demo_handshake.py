#!/usr/bin/env python3
"""
ML-KEM 链路安全原型演示

模拟上位机（发起方）与飞腾派（响应方）的完整会话流程：
1. ML-KEM-768 密钥协商
2. AES-256-GCM / SM4-GCM 双轨加密
3. 模拟 latent 传输
4. 模拟故障注入（密文篡改）
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.crypto import CipherSuite, EncryptedPayload
from mlkem_link.session import MLKEMSession, SessionRole
from mlkem_link.kem import get_backend

def demo(suite: CipherSuite):
    suite_name = suite.value
    print(f"\n{'='*60}")
    print(f"  ML-KEM Link Demo — {suite_name}")
    print(f"{'='*60}")

    backend = get_backend("768")

    # ── 1. 创建会话 ──
    print(f"\n[1] KEM 后端: {backend.name}")
    print(f"    参数集: ML-KEM-{backend.param_set}")
    print(f"    公钥: {backend.pk_bytes} bytes")
    print(f"    密文: {backend.ct_bytes} bytes")

    initiator = MLKEMSession(SessionRole.INITIATOR, backend, suite=suite)
    responder = MLKEMSession(SessionRole.RESPONDER, backend, suite=suite)
    print(f"\n[2] 会话创建")
    print(f"    发起方: {initiator.role.value} (上位机)")
    print(f"    响应方: {responder.role.value} (飞腾派)")
    print(f"    密码套件: {suite_name}")

    # ── 2. 握手 ──
    print(f"\n[3] ML-KEM 握手开始")
    t0 = time.perf_counter()
    pk = initiator.start_handshake()
    print(f"    发起方 → 响应方: public_key ({len(pk)} bytes)")

    t1 = time.perf_counter()
    ct = responder.respond_handshake(pk)
    print(f"    响应方 → 发起方: ciphertext ({len(ct)} bytes)")

    t2 = time.perf_counter()
    initiator.complete_handshake(ct)
    t3 = time.perf_counter()

    print(f"    握手完成 ✓  ({(t3-t0)*1000:.1f} ms)")
    print(f"      发起方生成密钥对: {(t1-t0)*1000:.1f} ms")
    print(f"      响应方封装:       {(t2-t1)*1000:.1f} ms")
    print(f"      发起方解封装:     {(t3-t2)*1000:.1f} ms")

    # ── 3. 模拟 latent 传输 ──
    latent = os.urandom(4096)
    print(f"\n[4] 模拟 latent 传输 ({len(latent)} bytes)")

    t4 = time.perf_counter()
    encrypted = initiator.encrypt(latent, aad=b"job_id:001|shape:1x3x64x64")
    t5 = time.perf_counter()
    print(f"    加密耗时: {(t5-t4)*1000:.2f} ms")
    print(f"    密文大小: {len(encrypted.ciphertext)} bytes (含 16 bytes tag)")

    wire = encrypted.to_bytes()
    print(f"    序列化载荷: {len(wire)} bytes")

    t6 = time.perf_counter()
    restored = EncryptedPayload.from_bytes(wire, suite)
    decrypted = responder.decrypt(restored, aad=b"job_id:001|shape:1x3x64x64")
    t7 = time.perf_counter()
    print(f"    解密耗时: {(t7-t6)*1000:.2f} ms")

    if decrypted == latent:
        print(f"    ✓ 解密成功，数据完整")
    else:
        print(f"    ✗ 解密失败！")
        return False

    # ── 4. 反向消息 ──
    result_msg = b"RECONSTRUCTION_OK|psnr:28.5|ssim:0.89"
    payload_back = responder.encrypt(result_msg, aad=b"job_id:001|status:done")
    decrypted_back = initiator.decrypt(payload_back, aad=b"job_id:001|status:done")
    print(f"\n[5] 反向消息 (飞腾派 → 上位机)")
    print(f"    内容: {decrypted_back.decode()}")

    # ── 5. 故障注入 ──
    print(f"\n[6] 故障注入：密文篡改")
    tampered = EncryptedPayload(
        nonce=encrypted.nonce,
        ciphertext=encrypted.ciphertext[:-4] + b"\xff\xff\xff\xff",
        suite=encrypted.suite,
    )
    try:
        responder.decrypt(tampered, aad=b"job_id:001|shape:1x3x64x64")
        print(f"    ✗ 篡改未检出！")
    except Exception as e:
        print(f"    ✓ 篡改已检出，拒绝解密")
        print(f"    异常: {type(e).__name__}")

    # ── 6. 故障注入：错误密钥 ──
    print(f"\n[7] 故障注入：错误密钥")
    fake_payload = EncryptedPayload(
        nonce=os.urandom(12),
        ciphertext=os.urandom(64),
        suite=suite,
    )
    try:
        responder.decrypt(fake_payload)
        print(f"    ✗ 未检出！")
    except Exception as e:
        print(f"    ✓ 错误密钥已检出")
        print(f"    异常: {type(e).__name__}")

    print(f"\n{'='*60}")
    print(f"  Demo 完成 — {suite_name}")
    print(f"{'='*60}\n")
    return True


if __name__ == "__main__":
    print("ML-KEM Link 原型演示")
    print("=" * 60)

    ok_aes = demo(CipherSuite.AES_256_GCM)

    try:
        from cryptography.hazmat.primitives.ciphers import algorithms
        algorithms.SM4(b"\x00" * 16)
        has_sm4 = True
    except (ImportError, AttributeError):
        has_sm4 = False

    if has_sm4:
        ok_sm4 = demo(CipherSuite.SM4_GCM)
    else:
        print("\n[跳过] SM4-GCM: 当前 cryptography 版本不支持 SM4")
        ok_sm4 = None

    print("=" * 60)
    print("总结:")
    print(f"  AES-256-GCM: {'✓ 通过' if ok_aes else '✗ 失败'}")
    print(f"  SM4-GCM:     {'✓ 通过' if ok_sm4 else '✗ 失败' if ok_sm4 is False else '— 不可用'}")
    print("=" * 60)
