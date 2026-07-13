#!/usr/bin/env python3
"""
飞腾派端 ML-KEM 安全接收服务

监听 TCP 端口，等待上位机连接后：
1. 完成 ML-KEM-768 握手
2. 接收加密的 latent 数据
3. 解密 + SHA256 完整性校验
4. 保存解密后的文件
5. (--tvm 模式) 调用 TVM 推理，加密回传重建结果
6. 返回 ACK 确认

用法:
  # 纯接收模式
  python tcp_server.py --host 0.0.0.0 --port 9527 --output-dir /tmp/mlkem_recv

  # TVM 推理模式（解密后调 TVM，加密回传结果）
  python tcp_server.py --host 0.0.0.0 --port 9527 --tvm \
      --tvm-python /home/user/anaconda3/envs/tvm310_safe/bin/python \
      --artifact-path /home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so \
      --snr 10
"""

import argparse
import base64
import hashlib
import json
import os
import select
import subprocess
import sys
import threading
import time
import tempfile
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mlkem_link.kem import get_backend
from mlkem_link.crypto import CipherSuite
from mlkem_link.session import SessionRole
from mlkem_link.secure_channel import SecureChannel
from mlkem_link.auth import IdentityConfig, SigPolicy

# T5: artifact 可信准入 + T6: 统一 JSONL 日志
sys.path.insert(0, os.path.dirname(__file__))
from artifact_guard import preflight_check, get_trusted_sha
from latent_transport import decode_transport_payload, save_decoded_npz
from replay_guard import ReplayGuard, validate_metadata
from run_logger import RunLogger


# ---------------------------------------------------------------------------
# 共享密码通道状态 (供 HTTP /status 端点读取)
# ---------------------------------------------------------------------------
_status_lock = threading.Lock()
_crypto_status: dict = {
    "kem_backend": "",
    "cipher_suite": "",
    "channel_state": "idle",
    "auth_enabled": False,
    "sig_policy": "",
    "server_id": "",
    "handshake_ms": None,
    "encrypt_ms": None,
    "decrypt_ms": None,
    "inference_ms": None,
    "bytes_sent": 0,
    "bytes_received": 0,
    "last_sha256_match": None,
    "session_count": 0,
    "last_session_at": None,
    "error": None,
}


def _update_crypto_status(**kwargs) -> None:
    """线程安全地更新密码通道状态"""
    with _status_lock:
        _crypto_status.update(kwargs)


def _env_flag(name: str) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _read_file_bytes(path: str) -> bytes | None:
    target = str(path or "").strip()
    if not target:
        return None
    with open(target, "rb") as handle:
        return handle.read()


def _parse_sig_policy(raw: str) -> SigPolicy:
    value = str(raw or "").strip() or SigPolicy.DUAL_REQUIRED.value
    try:
        return SigPolicy(value)
    except ValueError as exc:
        raise RuntimeError(f"不支持的 ML-KEM 身份认证策略: {value}") from exc


def _load_auth_config() -> IdentityConfig | None:
    if not _env_flag("MLKEM_AUTH_ENABLED"):
        return None

    config = IdentityConfig(
        role=SessionRole.RESPONDER,
        server_id=str(os.environ.get("MLKEM_AUTH_SERVER_ID", "") or "").strip() or "phytium-board",
        server_sm2_sk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_SM2_KEY", "") or "")),
        server_sm2_pk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_SM2_PUB", "") or "")),
        server_mldsa_sk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_MLDSA_KEY", "") or "")),
        server_mldsa_pk=_read_file_bytes(str(os.environ.get("MLKEM_AUTH_SERVER_MLDSA_PUB", "") or "")),
        sig_policy=_parse_sig_policy(str(os.environ.get("MLKEM_AUTH_SIG_POLICY", "") or "")),
    )
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY} and not config.server_sm2_sk:
        raise RuntimeError("已启用身份认证，但缺少 MLKEM_AUTH_SERVER_SM2_KEY")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.SM2_ONLY} and not config.server_sm2_pk:
        raise RuntimeError("已启用身份认证，但缺少 MLKEM_AUTH_SERVER_SM2_PUB")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY} and not config.server_mldsa_sk:
        raise RuntimeError("已启用身份认证，但缺少 MLKEM_AUTH_SERVER_MLDSA_KEY")
    if config.sig_policy in {SigPolicy.DUAL_REQUIRED, SigPolicy.MLDSA_ONLY} and not config.server_mldsa_pk:
        raise RuntimeError("已启用身份认证，但缺少 MLKEM_AUTH_SERVER_MLDSA_PUB")
    return config


class _StatusHTTPHandler(BaseHTTPRequestHandler):
    """轻量 HTTP handler — 只响应 GET /status"""

    def do_GET(self):
        if self.path != "/status":
            self.send_error(404)
            return
        with _status_lock:
            payload = dict(_crypto_status)
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 静默，不污染 stdout


# 模块级 replay guard 单例（线程安全）
_replay_guard = ReplayGuard()


def _handle_one_message(channel: SecureChannel, output_dir: str,
                        conn_id: int, msg_idx: int,
                        tvm_config: dict = None,
                        logger: "RunLogger" = None) -> bool:
    """处理单个消息（接收 → 校验 → TVM → 回传）

    Args:
        msg_idx: 当前连接内的消息序号（从 0 开始）

    Returns:
        True 表示继续接收下一条消息，False 表示连接应关闭
    """
    label = f"#{conn_id}.{msg_idx}"

    # ── 1. 接收首帧 ──
    t_recv = time.perf_counter()
    first_frame = channel.recv_encrypted(aad=b"metadata")
    t_dec = time.perf_counter()

    # 自动检测帧格式: 单帧 (4B meta_len + meta + latent) vs 旧双帧 (纯 JSON meta)
    if first_frame[0:1] == b'{':
        # 旧格式: 首帧是纯 JSON meta，需要再收一次 latent
        meta_raw = first_frame
        meta = json.loads(meta_raw)
        aad = meta_raw
        latent_bytes = channel.recv_encrypted(aad=aad)
        t_dec2 = time.perf_counter()
        dec_ms = round((t_dec2 - t_recv) * 1000, 2)
    else:
        # 新格式: 4B meta_len + meta JSON + latent binary
        meta_len = int.from_bytes(first_frame[:4], "big")
        meta_raw = first_frame[4:4 + meta_len]
        latent_bytes = first_frame[4 + meta_len:]
        meta = json.loads(meta_raw)
        dec_ms = round((t_dec - t_recv) * 1000, 2)

    print(f"[连接 {label}] 元数据: job_id={meta.get('job_id')}, "
          f"shape={meta.get('shape')}, dtype={meta.get('dtype')}, "
          f"codec={meta.get('payload_codec', 'float32-raw')}, "
          f"payload={len(latent_bytes)}B")

    # ── R7: 重放检测 ──
    replay_status, replay_code = validate_metadata(meta, _replay_guard)
    if replay_status == "deny":
        print(f"[连接 {label}] ⚠ 重放拒绝: job_id={meta.get('job_id')}, "
              f"code={replay_code}")
        channel.send_encrypted(
            json.dumps({"status": "replay_denied",
                        "error_code": replay_code}).encode(), aad=b"ack")
        return True  # 拒绝当前请求，但不关闭连接

    # 检测客户端发送的结束信号
    if meta.get("close_session"):
        print(f"[连接 {label}] 客户端请求关闭 session")
        channel.send_encrypted(
            json.dumps({"status": "bye"}).encode(), aad=b"ack")
        return False

    _update_crypto_status(
        decrypt_ms=dec_ms,
        bytes_received=_crypto_status["bytes_received"] + len(latent_bytes),
    )
    print(f"[连接 {label}] 接收+解密: {len(latent_bytes)}B "
          f"(codec={meta.get('payload_codec', 'float32-raw')}), "
          f"耗时 {dec_ms:.1f}ms")

    # ── 3. SHA256 校验 ──
    original_sha = meta.get("sha256", "")
    received_sha = hashlib.sha256(latent_bytes).hexdigest()
    sha_match = received_sha == original_sha
    _update_crypto_status(last_sha256_match=sha_match)
    status = "ok" if sha_match else "sha256_mismatch"

    if sha_match:
        print(f"[连接 {label}] SHA256 校验通过: {received_sha[:16]}...")
    else:
        print(f"[连接 {label}] SHA256 不匹配! "
              f"原文={original_sha[:16]}... 收到={received_sha[:16]}...")

    # ── 4. 保存解密后的数据 ──
    os.makedirs(output_dir, exist_ok=True)
    job_id = meta.get("job_id", f"job-{label}")
    out_path = os.path.join(output_dir, f"{job_id}.bin")
    with open(out_path, "wb") as f:
        f.write(latent_bytes)
    print(f"[连接 {label}] 已保存 transport payload: {out_path}")

    # ── 4b. Artifact 可信准入 (T5) ──
    if tvm_config and sha_match:
        artifact_path = tvm_config.get("artifact_path", "")
        expected_sha = get_trusted_sha()
        if expected_sha and artifact_path:
            run_id = logger.run_id if logger else f"conn-{label}"
            guard_result = preflight_check(
                artifact_path, expected_sha, run_id=run_id)
            if guard_result["status"] == "deny":
                print(f"[连接 {label}] artifact 拒绝: "
                      f"{guard_result.get('error_code')} "
                      f"{guard_result.get('detail', '')}")
                if logger:
                    logger.log("reject", status="deny",
                               error_code=guard_result.get("error_code"),
                               artifact_path=artifact_path,
                               artifact_sha_expected=expected_sha,
                               artifact_sha_actual=guard_result.get("actual_sha", ""))
                deny_ack = {"status": "deny",
                            "error_code": guard_result.get("error_code"),
                            "detail": guard_result.get("detail", "")}
                channel.send_encrypted(
                    json.dumps(deny_ack).encode(), aad=b"ack")
                return True  # artifact 拒绝不影响 session 继续接收
            print(f"[连接 {label}] artifact 校验通过")
            if logger:
                logger.log("artifact_guard_ok",
                           artifact_path=artifact_path,
                           artifact_sha_expected=expected_sha,
                           artifact_sha_actual=guard_result.get("actual_sha", ""))

    # ── 5. TVM 推理（可选）──
    tvm_result = None
    if tvm_config and sha_match:
        if logger:
            logger.log("tvm_start", artifact_path=tvm_config.get("artifact_path", ""))
        tvm_result = run_tvm_inference(
            latent_bytes, meta, output_dir, conn_id, tvm_config)
        if tvm_result:
            _update_crypto_status(inference_ms=tvm_result.get("inference_ms"))
        if logger and tvm_result:
            logger.log("tvm_done",
                       latency_ms=tvm_result.get("inference_ms"),
                       result_shape=tvm_result.get("output_shape"))

    # ── 6. 返回 ACK ──
    ack_data = {
        "status": status,
        "sha256_match": sha_match,
        "bytes_received": len(latent_bytes),
        "timestamp": time.time(),
    }
    if tvm_result:
        ack_data["tvm"] = True
        ack_data["inference_ms"] = tvm_result.get("inference_ms")
        ack_data["output_shape"] = tvm_result.get("output_shape")
        ack_data["result_bytes"] = tvm_result.get("output_bytes")
    channel.send_encrypted(
            json.dumps(ack_data).encode(), aad=b"ack")
    enc_ms = round((time.perf_counter() - t_dec) * 1000, 2)
    _update_crypto_status(encrypt_ms=enc_ms)

    # ── 7. 加密回传 TVM 结果 ──
    if tvm_result and tvm_result.get("status") == "ok":
        result_path = tvm_result["output_path"]
        with open(result_path, "rb") as f:
            result_bytes = f.read()
        channel.send_encrypted(result_bytes, aad=json.dumps(ack_data).encode())
        _update_crypto_status(
            bytes_sent=_crypto_status["bytes_sent"] + len(result_bytes))
        print(f"[连接 {label}] 已回传重建结果: {len(result_bytes)}B")
        if logger:
            logger.log("result_sent", status="ok",
                       result_bytes=len(result_bytes))

        # 等待客户端 RESULT_ACK
        try:
            channel.recv_encrypted(aad=b"result_ack")
        except Exception:
            pass

    return True


def handle_client(channel: SecureChannel, output_dir: str,
                  conn_id: int,
                  auth_config: IdentityConfig | None = None,
                  tvm_config: dict = None,
                  logger: "RunLogger" = None) -> None:
    """处理单个客户端连接

    支持多轮消息复用同一 ML-KEM session：
      握手一次 → N 次收发 → 客户端发 close_session → 连接关闭

    tvm_config 非空时启用 TVM 推理模式：
      解密 → 保存 .npz → 子进程调 TVM → 读推理结果 → 加密回传
    """
    print(f"\n[连接 #{conn_id}] 开始处理")

    # ── 1. ML-KEM 握手（仅一次）──
    _update_crypto_status(channel_state="handshaking", error=None)
    t0 = time.perf_counter()
    hs_ms = (
        channel.authenticated_handshake(auth_config)
        if auth_config is not None
        else channel.handshake()
    )
    _update_crypto_status(
        channel_state="ready",
        kem_backend=channel._session._backend.name,
        cipher_suite=channel.cipher_suite.value,
        auth_enabled=bool(auth_config),
        sig_policy=(auth_config.sig_policy.value if auth_config is not None else ""),
        server_id=(auth_config.server_id if auth_config is not None else ""),
        handshake_ms=round(hs_ms, 2),
    )
    print(f"[连接 #{conn_id}] 握手完成: {hs_ms:.1f}ms "
          f"(套件: {channel.cipher_suite.value})")
    if auth_config is not None:
        print(f"[连接 #{conn_id}] 身份认证已启用: {auth_config.sig_policy.value} "
              f"(server_id={auth_config.server_id})")

    if logger:
        logger.log("session_ready", latency_ms=round(hs_ms, 2))

    # ── 2. 消息循环（支持多轮复用）──
    msg_count = 0
    try:
        while True:
            if not _handle_one_message(
                    channel, output_dir, conn_id, msg_count,
                    tvm_config=tvm_config, logger=logger):
                break
            msg_count += 1
    except ConnectionError as e:
        print(f"[连接 #{conn_id}] 连接断开: {e}")
    except Exception as e:
        print(f"[连接 #{conn_id}] 消息处理错误: {e}")
        _update_crypto_status(channel_state="closed", error=str(e))
        logger.log("error", error_code="E_CONNECTION",
                   detail=str(e))

    total_ms = (time.perf_counter() - t0) * 1000
    _update_crypto_status(
        channel_state="idle",
        session_count=_crypto_status["session_count"] + 1,
        last_session_at=datetime.now(timezone.utc).isoformat(),
    )
    print(f"[连接 #{conn_id}] session 完成: {msg_count} 条消息, "
          f"总耗时 {total_ms:.1f}ms")


def run_tvm_inference(latent_bytes: bytes, meta: dict,
                      output_dir: str, conn_id: int,
                      config: dict) -> dict | None:
    """通过子进程调用 TVM 推理（守护进程模式优先，单次回退）。"""

    if config.get("tvm_daemon_proc") is not None:
        result = _run_tvm_inference_daemon(latent_bytes, meta, output_dir, conn_id, config)
        if result is not None:
            return result
        print(f"[连接 #{conn_id}] daemon 不可用，回退到 one-shot 模式")
        _stop_tvm_daemon(config)

    return _run_tvm_inference_oneshot(latent_bytes, meta, output_dir, conn_id, config)


# ── 守护进程管理 ──


def _start_tvm_daemon(config: dict) -> None:
    """启动 TVM 推理守护进程并确认就绪。"""
    tvm_python = config["tvm_python"]
    artifact_path = config["artifact_path"]
    snr = config.get("snr", 10.0)
    tvm_env = config.get("tvm_env", {})
    channel_mode = config.get("tvm_channel_mode", "sim-awgn")
    big_core = config.get("tvm_big_core")

    helper_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "tvm_inference_helper.py")

    cmd = [tvm_python, helper_script,
           "--artifact-path", artifact_path,
           "--snr", str(snr),
           "--channel-mode", channel_mode,
           "--daemon"]
    if big_core is not None:
        cmd.extend(["--cpu-affinity", str(big_core)])

    env = {**os.environ, **tvm_env}
    print(f"[tvm_daemon] 启动: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
    except Exception as exc:
        print(f"[tvm_daemon] 启动失败: {exc}，将使用 one-shot 模式")
        return

    config["tvm_daemon_proc"] = proc

    ready_line = proc.stdout.readline()
    try:
        ready_msg = json.loads(ready_line.strip())
    except (json.JSONDecodeError, ValueError):
        ready_msg = {}

    if ready_msg.get("status") == "ready":
        print(f"[tvm_daemon] 就绪 load_ms={ready_msg.get('load_ms', '?')}ms "
              f"affinity={big_core}")
    else:
        print(f"[tvm_daemon] 启动异常: {ready_line[:200]}, stderr={_read_stderr_nonblock(proc)[:200]}")
        config["tvm_daemon_proc"] = None
        proc.kill()
        proc.wait()


def _stop_tvm_daemon(config: dict) -> None:
    """关闭 TVM 守护进程。"""
    proc = config.get("tvm_daemon_proc")
    if proc is None:
        return
    config["tvm_daemon_proc"] = None
    try:
        proc.stdin.write(json.dumps({"action": "quit"}, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
        proc.wait()
    print("[tvm_daemon] 已关闭")


def _read_stderr_nonblock(proc) -> str:
    """非阻塞读取 stderr。"""
    try:
        readable, _, _ = select.select([proc.stderr], [], [], 0.1)
        if readable:
            return proc.stderr.read(4096) or ""
    except Exception:
        pass
    return ""


def _run_tvm_inference_daemon(latent_bytes: bytes, meta: dict,
                               output_dir: str, conn_id: int,
                               config: dict) -> dict | None:
    """通过守护进程 (stdin/stdout JSON) 执行 TVM 推理。"""
    proc = config.get("tvm_daemon_proc")
    lock: threading.Lock = config.get("tvm_daemon_lock")
    if proc is None or proc.poll() is not None:
        return None

    snr = config.get("snr", 10.0)
    channel_mode = config.get("tvm_channel_mode", "sim-awgn")

    try:
        decoded = decode_transport_payload(meta, latent_bytes)
    except Exception as e:
        print(f"[连接 #{conn_id}] transport payload 解码失败: {e}")
        return None

    try:
        job_id = meta.get("job_id", f"job-{conn_id}")
    except Exception:
        job_id = f"job-{conn_id}"
    input_npz = os.path.join(output_dir, f"{job_id}_input.npz")
    output_npy = os.path.join(output_dir, f"{job_id}_output.npy")

    import io as _io_module
    buf = _io_module.BytesIO()
    np_items = getattr(decoded, "npz_items", None)
    if np_items is not None:
        import numpy as _np
        _np.savez(buf, **np_items)
    else:
        import numpy as _np
        _np.savez(buf, latent=getattr(decoded, "latent", None) or _np.frombuffer(latent_bytes, dtype=_np.float32))
    input_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    request = {
        "action": "infer",
        "input_b64": input_b64,
        "snr": float(snr),
        "channel_mode": channel_mode,
        "expect_result": True,
    }

    t1 = time.perf_counter()
    with lock:
        proc.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        response_line = proc.stdout.readline()
    t2 = time.perf_counter()

    if not response_line:
        stderr_tail = _read_stderr_nonblock(proc)
        print(f"[连接 #{conn_id}] daemon 无响应, stderr={stderr_tail[:200]}")
        _stop_tvm_daemon(config)
        return None

    try:
        result = json.loads(response_line.strip())
    except json.JSONDecodeError:
        print(f"[连接 #{conn_id}] daemon 输出解析失败: {response_line[:200]}")
        return None

    if result.get("status") != "ok":
        print(f"[连接 #{conn_id}] daemon 错误: {result.get('message', result)}")
        return None

    output_b64 = result.get("output_npy_b64")
    if output_b64:
        with open(output_npy, "wb") as f:
            f.write(base64.b64decode(output_b64.encode("ascii")))

    result["output_path"] = output_npy
    wall_ms = (t2 - t1) * 1000
    print(
        f"[连接 #{conn_id}] TVM(daemon) 完成: "
        f"{result.get('inference_ms', 0):.1f}ms (推理), "
        f"{wall_ms:.1f}ms (含IPC), "
        f"shape={result.get('output_shape')}"
    )
    return result


def _run_tvm_inference_oneshot(latent_bytes: bytes, meta: dict,
                                output_dir: str, conn_id: int,
                                config: dict) -> dict | None:
    """通过一次性子进程调用 TVM 推理（原始回退路径）。"""
    tvm_python = config["tvm_python"]
    artifact_path = config["artifact_path"]
    snr = config.get("snr", 10.0)
    tvm_env = config.get("tvm_env", {})
    channel_mode = config.get("tvm_channel_mode", "sim-awgn")

    # 保存解码后的 latent/quant npz 供 TVM 进程读取
    try:
        decoded = decode_transport_payload(meta, latent_bytes)
    except Exception as e:
        print(f"[连接 #{conn_id}] transport payload 解码失败: {e}")
        return None

    try:
        job_id = meta.get("job_id", f"job-{conn_id}")
    except Exception:
        job_id = f"job-{conn_id}"
    input_npz = os.path.join(output_dir, f"{job_id}_input.npz")
    output_npy = os.path.join(output_dir, f"{job_id}_output.npy")
    save_decoded_npz(decoded, input_npz)

    # 定位 helper 脚本（和 tcp_server.py 同目录）
    helper_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "tvm_inference_helper.py")

    cmd = [
        tvm_python, helper_script,
        "--artifact-path", artifact_path,
        "--input", input_npz,
        "--output", output_npy,
        "--snr", str(snr),
        "--channel-mode", channel_mode,
    ]

    print(
        f"[连接 #{conn_id}] 启动 TVM 推理: {os.path.basename(artifact_path)} "
        f"jscc_awgn_snr_db={snr} "
        f"payload_codec={meta.get('payload_codec', 'float32-raw')}"
    )

    t1 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            env={**os.environ, **tvm_env})
    except subprocess.TimeoutExpired:
        print(f"[连接 #{conn_id}] TVM 推理超时 (120s)")
        return None
    t2 = time.perf_counter()

    if proc.returncode != 0:
        print(f"[连接 #{conn_id}] TVM 推理失败: {proc.stderr[-200:] if proc.stderr else 'unknown'}")
        return None

    try:
        result = json.loads(proc.stdout.strip().split("\n")[-1])
    except (json.JSONDecodeError, IndexError):
        print(f"[连接 #{conn_id}] TVM 输出解析失败")
        return None

    if result.get("status") != "ok":
        print(f"[连接 #{conn_id}] TVM 错误: {result.get('message')}")
        return None

    result["output_path"] = output_npy
    wall_ms = (t2 - t1) * 1000
    realized_snr = result.get("jscc_realized_awgn_snr_db")
    awgn_note = str(result.get("jscc_awgn_note") or "").strip()
    if realized_snr is None:
        realized_snr_text = f"undefined({awgn_note})" if awgn_note else "undefined"
    else:
        realized_snr_text = f"{float(realized_snr):.3f}"
    print(
        f"[连接 #{conn_id}] TVM 推理完成: "
        f"{result.get('inference_ms', 0):.1f}ms (推理), "
        f"{wall_ms:.1f}ms (含加载), "
        f"shape={result.get('output_shape')} "
        f"jscc_awgn_config_db={result.get('jscc_configured_awgn_snr_db', snr)} "
        f"jscc_awgn_realized_db={realized_snr_text}"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="飞腾派端 ML-KEM 安全接收服务")
    parser.add_argument("--host", default="0.0.0.0",
                        help="监听地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9527,
                        help="监听端口 (默认 9527)")
    parser.add_argument("--output-dir", default="/tmp/mlkem_recv",
                        help="接收文件保存目录")
    parser.add_argument("--suite", default="SM4_GCM",
                        choices=["AES_256_GCM", "SM4_GCM"],
                        help="AEAD 密码套件 (默认 SM4-GCM 国密)")
    parser.add_argument("--once", action="store_true",
                        help="只处理一个连接后退出（调试用）")
    # TVM 推理参数
    parser.add_argument("--tvm", action="store_true",
                        help="启用 TVM 推理（解密后调 TVM，加密回传结果）")
    parser.add_argument("--tvm-python",
                        default="/home/user/anaconda3/envs/tvm310_safe/bin/python",
                        help="TVM 环境 Python 路径")
    parser.add_argument("--artifact-path",
                        default="/home/user/Downloads/jscc-test/jscc/tvm_tune_logs/optimized_model.so",
                        help="TVM 模型 .so 路径")
    parser.add_argument("--snr", type=float, default=10.0,
                        help="JSCC/AWGN 仿真 SNR (dB, 默认 10)")
    parser.add_argument("--status-port", type=int, default=8080,
                        help="HTTP 状态端口 (默认 8080, 0=关闭)")
    # TVM 守护进程参数
    parser.add_argument("--tvm-daemon", action="store_true",
                        help="以守护进程模式运行 TVM（加载一次模型，stdin/stdout 通信）")
    parser.add_argument("--tvm-big-core", type=int,
                        default=int(os.environ.get("BIG_LITTLE_BIG_CORES", "2") or 2),
                        help="TVM 守护进程绑定的大核 CPU (默认 2，从 BIG_LITTLE_BIG_CORES 读取)")
    parser.add_argument("--tvm-channel-mode", default="sim-awgn",
                        choices=["sim-awgn", "real-usrp", "none"],
                        help="信道模式: sim-awgn=软件AWGN, real-usrp/none=直通 (默认 sim-awgn)")
    args = parser.parse_args()

    suite = CipherSuite[args.suite]
    backend = get_backend("768")
    auth_config = _load_auth_config()

    # 构建 TVM 配置
    tvm_config = None
    if args.tvm:
        tvm_env = {
            "TVM_FFI_DISABLE_TORCH_C_DLPACK": "1",
            "LD_LIBRARY_PATH": "/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages/tvm_ffi/lib:"
                               "/home/user/tvm_samegen_safe_20260309/build",
            "TVM_LIBRARY_PATH": "/home/user/tvm_samegen_safe_20260309/build",
            "PYTHONPATH": "/home/user/tvm_samegen_20260307/python:"
                          "/home/user/anaconda3/envs/tvm310_safe/lib/python3.10/site-packages",
        }
        tvm_config = {
            "tvm_python": args.tvm_python,
            "artifact_path": args.artifact_path,
            "snr": args.snr,
            "tvm_env": tvm_env,
            "tvm_channel_mode": args.tvm_channel_mode,
            "tvm_daemon": args.tvm_daemon,
            "tvm_big_core": args.tvm_big_core,
            "tvm_daemon_proc": None,
            "tvm_daemon_lock": threading.Lock(),
        }

    print("=" * 60)
    print("ML-KEM 安全接收服务 (飞腾派端)")
    print("=" * 60)
    print(f"监听:      {args.host}:{args.port}")
    print(f"KEM 后端:  {backend.name}")
    print(f"密码套件:  {suite.value}")
    print(f"保存目录:  {args.output_dir}")
    print(f"状态端口:  {args.status_port if args.status_port else '关闭'}")
    if auth_config is not None:
        print(f"身份认证:  启用 ({auth_config.sig_policy.value})")
        print(f"  server_id: {auth_config.server_id}")
    else:
        print("身份认证:  未启用")
    if tvm_config:
        daemon_label = "守护进程" if args.tvm_daemon else "one-shot"
        print(f"TVM 推理:  启用 ({daemon_label})")
        print(f"  模型:    {args.artifact_path}")
        print(f"  SNR:     {args.snr} dB")
        print(f"  信道:    {args.tvm_channel_mode}")
        print(f"  Python:  {args.tvm_python}")
        if args.tvm_daemon:
            print(f"  大核:    CPU{args.tvm_big_core}")
    else:
        print(f"TVM 推理:  未启用（纯接收模式）")
    print()

    # T6: 初始化统一日志记录器
    logger = RunLogger(role="server")
    print(f"JSONL 日志: {logger.log_path}")

    # 初始化共享状态并启动 HTTP 状态线程
    _update_crypto_status(
        kem_backend=backend.name,
        cipher_suite=suite.value,
        auth_enabled=bool(auth_config),
        sig_policy=(auth_config.sig_policy.value if auth_config is not None else ""),
        server_id=(auth_config.server_id if auth_config is not None else ""),
    )
    if args.status_port:
        import socketserver as _socketserver
        _socketserver.TCPServer.allow_reuse_address = True
        status_http = ThreadingHTTPServer(('', args.status_port), _StatusHTTPHandler)
        threading.Thread(target=status_http.serve_forever, daemon=True).start()
        print(f"状态 HTTP: http://0.0.0.0:{args.status_port}/status")

    # ── 启动 TVM 守护进程（如果启用）──
    if tvm_config and tvm_config["tvm_daemon"]:
        _start_tvm_daemon(tvm_config)

    import socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(1)
    print(f"等待连接...")

    conn_id = 0
    try:
        while True:
            conn, addr = server.accept()
            conn_id += 1
            print(f"[连接 #{conn_id}] 来自 {addr[0]}:{addr[1]}")
            run_id = logger.new_run(
                backend=backend.name, suite=suite.value)
            try:
                channel = SecureChannel(
                    conn, SessionRole.RESPONDER, backend, suite)
                handle_client(channel, args.output_dir, conn_id,
                              auth_config=auth_config,
                              tvm_config=tvm_config, logger=logger)
            except Exception as e:
                print(f"[连接 #{conn_id}] 错误: {e}")
                _update_crypto_status(channel_state="closed", error=str(e))
                logger.log("error", error_code="E_CONNECTION",
                           detail=str(e))
            finally:
                conn.close()
                print(f"[连接 #{conn_id}] 连接已关闭")
                logger.log("run_end", status="closed")

            if args.once:
                break
    except KeyboardInterrupt:
        print("\n服务停止")
    finally:
        server.close()
        if tvm_config:
            _stop_tvm_daemon(tvm_config)
        logger.close()


if __name__ == "__main__":
    main()
