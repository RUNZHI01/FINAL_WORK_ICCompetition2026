#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
from pathlib import Path


def _find_mlkem_runtime_root() -> Path | None:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]
    candidates: list[Path] = []

    for key in ("MLKEM_LOCAL_REPO_ROOT", "MLKEM_REPO_ROOT", "COCKPIT_REPO_ROOT"):
        raw_value = str(os.environ.get(key, "")).strip()
        if raw_value:
            candidates.append(Path(raw_value).expanduser())

    candidates.extend(
        [
            repo_root,
            repo_root.parent / "ICCompetition2026",
            Path.cwd(),
            Path.cwd().parent,
        ]
    )

    parent = repo_root.parent
    try:
        candidates.extend(child for child in parent.iterdir())
    except OSError:
        pass

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (resolved / "mlkem_link").is_dir():
            return resolved
    return None


_MLKEM_RUNTIME_ROOT = _find_mlkem_runtime_root()
if _MLKEM_RUNTIME_ROOT is not None and str(_MLKEM_RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(_MLKEM_RUNTIME_ROOT))

try:
    from mlkem_link.crypto import CipherSuite
    from mlkem_link.kem import get_backend
    from mlkem_link.secure_channel import SecureChannel
    from mlkem_link.session import SessionRole
except ImportError as exc:
    runtime_hint = str(_MLKEM_RUNTIME_ROOT) if _MLKEM_RUNTIME_ROOT is not None else "not found"
    raise SystemExit(
        "mlkem_link import failed. "
        "Set MLKEM_LOCAL_REPO_ROOT to the ML-KEM runtime repo. "
        f"detected_runtime_root={runtime_hint}. error={exc}"
    ) from exc


_LEGACY_BIN_SHAPE = [1, 3, 64, 64]
_MODERN_BIN_SHAPE = [1, 32, 32, 32]


def _load_bin_latent_info(raw: bytes) -> dict[str, object]:
    override = str(
        os.environ.get("MLKEM_BIN_SHAPE_JSON")
        or os.environ.get("MLKEM_INPUT_SHAPE_JSON")
        or ""
    ).strip()
    if override:
        try:
            shape = json.loads(override)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid MLKEM_BIN_SHAPE_JSON: {override}") from exc
        if not isinstance(shape, list) or not shape:
            raise ValueError("MLKEM_BIN_SHAPE_JSON must be a non-empty JSON array")
        return {"shape": shape, "dtype": "float32"}

    if len(raw) == 1 * 3 * 64 * 64 * 4:
        return {"shape": list(_LEGACY_BIN_SHAPE), "dtype": "float32"}
    if len(raw) == 1 * 32 * 32 * 32 * 4:
        return {"shape": list(_MODERN_BIN_SHAPE), "dtype": "float32"}

    raise ValueError(
        "unsupported .bin latent size "
        f"{len(raw)} bytes; set MLKEM_BIN_SHAPE_JSON for custom shapes"
    )


def load_latent(path: str) -> tuple[bytes, dict[str, object]]:
    if path.endswith(".bin"):
        raw = Path(path).read_bytes()
        return raw, _load_bin_latent_info(raw)

    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("numpy is required for .npz/.npy inputs") from exc

    if path.endswith(".npz"):
        data = np.load(path)
        if "quant" in data and "scale" in data and "zero_point" in data:
            quant = np.asarray(data["quant"], dtype=np.float32)
            scale = np.asarray(data["scale"], dtype=np.float32)
            zero_point = np.asarray(data["zero_point"], dtype=np.float32)
            array = (quant - zero_point) * scale
        elif "latent" in data:
            array = np.asarray(data["latent"])
        else:
            first_key = list(data.keys())[0]
            array = np.asarray(data[first_key])
    elif path.endswith(".npy"):
        array = np.load(path)
    else:
        raise ValueError(f"unsupported input format: {path}")

    array = array.astype(np.float32)
    return array.tobytes(), {"shape": list(array.shape), "dtype": "float32"}


def _result_output_path(job_id: str, requested_output: str | None) -> Path:
    if requested_output:
        return Path(requested_output)
    return Path(f"/tmp/mlkem_result_{job_id}.bin")


def _round_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


_DEFAULT_SOCKET_TIMEOUT_SEC = 20.0


def _open_channel(
    *,
    host: str,
    port: int,
    suite: CipherSuite,
    verbose: bool,
) -> tuple[socket.socket, SecureChannel, float]:
    connect_t0 = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(_DEFAULT_SOCKET_TIMEOUT_SEC)
    sock.connect((host, port))
    connect_t1 = time.perf_counter()
    if verbose:
        print(f"已连接: {host}:{port} ({((connect_t1 - connect_t0) * 1000):.1f}ms)")

    backend = get_backend("768")
    if verbose:
        print(f"KEM 后端:  {backend.name}")

    channel = SecureChannel(sock, SessionRole.INITIATOR, backend, suite)
    handshake_ms = float(channel.handshake())
    if verbose:
        print(f"握手完成: {handshake_ms:.1f}ms")

    return sock, channel, handshake_ms


def _send_job_over_channel(
    channel: SecureChannel,
    *,
    input_path: str,
    job_id: str,
    requested_output: str | None,
    run_tvm: bool,
    expect_result: bool,
    verbose: bool,
) -> dict[str, object]:
    latent_bytes, latent_info = load_latent(input_path)
    latent_sha = hashlib.sha256(latent_bytes).hexdigest()

    if verbose:
        print(f"输入文件:  {input_path}")
        print(f"数据大小:  {len(latent_bytes)} bytes")
        print(f"SHA256:    {latent_sha[:16]}...")
        print(f"形状:      {latent_info['shape']} ({latent_info['dtype']})")
        print()

    metadata = json.dumps(
        {
            "job_id": job_id,
            "shape": latent_info["shape"],
            "dtype": latent_info["dtype"],
            "sha256": latent_sha,
            "size": len(latent_bytes),
            "run_tvm": run_tvm,
            "expect_result": expect_result,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    send_t0 = time.perf_counter()
    channel.send_encrypted(metadata, aad=b"metadata")
    channel.send_encrypted(latent_bytes, aad=metadata)
    send_t1 = time.perf_counter()
    encrypt_ms = (send_t1 - send_t0) * 1000
    if verbose:
        print(f"加密发送: {len(latent_bytes)}B, 耗时 {encrypt_ms:.1f}ms")

    ack_raw = channel.recv_encrypted(aad=b"ack")
    ack = json.loads(ack_raw.decode("utf-8"))

    result_received = bool(ack.get("tvm") and ack.get("result_bytes"))
    inference_ms = ack.get("inference_ms")
    if inference_ms is not None:
        inference_ms = float(inference_ms)

    decrypt_ms = None
    if verbose:
        print()
        print("=" * 60)

    sha256_match = bool(ack.get("status") == "ok" and ack.get("sha256_match"))
    if verbose:
        if sha256_match:
            print("✓ 传输成功")
            print("  对端 SHA256 匹配: 是")
            print(f"  对端接收字节数: {ack.get('bytes_received', '?')}")
        else:
            print("✗ 传输失败")
            print(f"  状态: {ack.get('status')}")
            print(f"  SHA256 匹配: {ack.get('sha256_match')}")
            detail = str(ack.get("detail") or "").strip()
            if detail:
                print(f"  详情: {detail}")

        print(f"  板端重建结果: {'已回传' if result_received else '未回传'}")

    output_path: str | None = None
    if result_received:
        if verbose:
            print(f"  TVM 推理耗时: {ack.get('inference_ms', '?')}ms")
            print(f"  输出形状: {ack.get('output_shape', '?')}")

        recv_t0 = time.perf_counter()
        result_bytes = channel.recv_encrypted(aad=ack_raw)
        recv_t1 = time.perf_counter()
        decrypt_ms = (recv_t1 - recv_t0) * 1000
        if verbose:
            print(f"  接收重建结果: {len(result_bytes)}B, 耗时 {decrypt_ms:.1f}ms")

        output_file = _result_output_path(job_id, requested_output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(result_bytes)
        output_path = str(output_file)
        if verbose:
            print(f"  已保存: {output_file}")

        result_ack = json.dumps({"status": "result_received"}, ensure_ascii=False).encode("utf-8")
        channel.send_encrypted(result_ack, aad=b"result_ack")

    if verbose:
        print("=" * 60)

    ok = sha256_match and (not expect_result or result_received)
    total_ms = encrypt_ms
    if inference_ms is not None:
        total_ms += inference_ms
    if decrypt_ms is not None:
        total_ms += decrypt_ms

    detail = str(ack.get("detail") or "").strip()
    error_message = ""
    if not ok:
        if expect_result and not result_received:
            error_message = "board result not returned"
        elif detail:
            error_message = detail
        else:
            error_message = f"status={ack.get('status')} sha256_match={ack.get('sha256_match')}"

    return {
        "ok": ok,
        "status": "ok" if ok else str(ack.get("status") or "error"),
        "message": "" if ok else error_message,
        "sha256_match": bool(ack.get("sha256_match")),
        "result_received": result_received,
        "handshake_ms": None,
        "encrypt_ms": _round_or_none(encrypt_ms),
        "decrypt_ms": _round_or_none(decrypt_ms),
        "inference_ms": _round_or_none(inference_ms),
        "total_ms": _round_or_none(total_ms),
        "detail": detail,
        "error": error_message,
        "output_path": output_path,
    }


def _transmit_once(
    *,
    host: str,
    port: int,
    input_path: str,
    suite: CipherSuite,
    job_id: str,
    requested_output: str | None,
    run_tvm: bool,
    expect_result: bool,
    verbose: bool,
) -> dict[str, object]:
    if verbose:
        print("=" * 60)
        print("ML-KEM 安全发送客户端 (兼容板端新协议)")
        print("=" * 60)
        print(f"目标:      {host}:{port}")
        print(f"密码套件:  {suite.value}")
        print()

    sock = None
    try:
        sock, channel, handshake_ms = _open_channel(host=host, port=port, suite=suite, verbose=verbose)
        result = _send_job_over_channel(
            channel,
            input_path=input_path,
            job_id=job_id,
            requested_output=requested_output,
            run_tvm=run_tvm,
            expect_result=expect_result,
            verbose=verbose,
        )
        result["handshake_ms"] = _round_or_none(handshake_ms)
        return result
    finally:
        if sock is not None:
            sock.close()


def _run_daemon(*, host: str, port: int, suite: CipherSuite) -> int:
    sock = None
    try:
        sock, channel, handshake_ms = _open_channel(host=host, port=port, suite=suite, verbose=False)
        print(json.dumps({"status": "ready", "handshake_ms": _round_or_none(handshake_ms)}, ensure_ascii=False), flush=True)
        while True:
            raw_line = sys.stdin.readline()
            if raw_line == "":
                return 0
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                print(json.dumps({"status": "error", "message": "invalid json"}, ensure_ascii=False), flush=True)
                continue

            action = str(request.get("action") or "").strip().lower()
            if action == "ping":
                print(json.dumps({"status": "ok", "handshake_ms": _round_or_none(handshake_ms)}, ensure_ascii=False), flush=True)
                continue
            if action == "quit":
                return 0
            if action != "send":
                print(json.dumps({"status": "error", "message": f"unsupported action: {action}"}, ensure_ascii=False), flush=True)
                continue

            input_path = str(request.get("input") or "").strip()
            job_id = str(request.get("job_id") or Path(input_path or "latent.bin").stem).strip()
            expect_result = bool(request.get("expect_result"))
            run_tvm = bool(request.get("run_tvm", expect_result))
            if not input_path:
                print(json.dumps({"status": "error", "message": "missing input"}, ensure_ascii=False), flush=True)
                continue

            try:
                result = _send_job_over_channel(
                    channel,
                    input_path=input_path,
                    job_id=job_id,
                    requested_output=None,
                    run_tvm=run_tvm,
                    expect_result=expect_result,
                    verbose=False,
                )
            except Exception as exc:
                print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), flush=True)
                return 1

            print(json.dumps(result, ensure_ascii=False), flush=True)
            if result.get("status") != "ok":
                return 1
    finally:
        if sock is not None:
            sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ML-KEM secure sender for the cockpit demo")
    parser.add_argument("--host", required=True, help="board host")
    parser.add_argument("--port", type=int, default=9527, help="board TCP port")
    parser.add_argument("--input", required=False, help="latent input (.bin/.npy/.npz)")
    parser.add_argument(
        "--suite",
        default="SM4_GCM",
        choices=["AES_256_GCM", "SM4_GCM"],
        help="AEAD suite",
    )
    parser.add_argument("--job-id", default=None, help="job identifier")
    parser.add_argument("--output", default=None, help="reconstruction output path")
    parser.add_argument("--count", type=int, default=1, help="repeat the same input N times")
    parser.add_argument("--daemon", action="store_true", help="reuse one ML-KEM session via stdin/stdout JSON")
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="emit a final JSON summary for batch-mode callers",
    )
    parser.add_argument(
        "--run-tvm",
        action="store_true",
        help="request the board to execute TVM even when the result payload is not returned",
    )
    parser.add_argument(
        "--expect-result",
        action="store_true",
        help="require the board to return a TVM reconstruction result",
    )
    args = parser.parse_args()

    suite = CipherSuite[args.suite]

    if args.daemon:
        return _run_daemon(host=args.host, port=args.port, suite=suite)

    if not args.input:
        parser.error("the following arguments are required: --input")

    base_job_id = args.job_id or Path(args.input).stem
    count = max(1, int(args.count))
    run_tvm = bool(args.run_tvm or args.expect_result)

    if count > 1 and args.output:
        print("--count>1 does not support --output", file=sys.stderr)
        return 2

    if count == 1 and not args.json_summary:
        result = _transmit_once(
            host=args.host,
            port=args.port,
            input_path=args.input,
            suite=suite,
            job_id=base_job_id,
            requested_output=args.output,
            run_tvm=run_tvm,
            expect_result=args.expect_result,
            verbose=True,
        )
        if args.expect_result and not result.get("result_received"):
            return 2
        return 0 if result.get("ok") else 1

    successes = 0
    handshake_samples: list[float] = []
    encrypt_samples: list[float] = []
    decrypt_samples: list[float] = []
    inference_samples: list[float] = []
    total_samples: list[float] = []
    sha_all_ok = True

    for index in range(count):
        iter_job_id = base_job_id if count == 1 else f"{base_job_id}_{index:04d}"
        result = _transmit_once(
            host=args.host,
            port=args.port,
            input_path=args.input,
            suite=suite,
            job_id=iter_job_id,
            requested_output=None,
            run_tvm=run_tvm,
            expect_result=args.expect_result,
            verbose=False,
        )
        if result.get("ok"):
            successes += 1
            print(f"✓ {iter_job_id}")
            for key, bucket in (
                ("handshake_ms", handshake_samples),
                ("encrypt_ms", encrypt_samples),
                ("decrypt_ms", decrypt_samples),
                ("inference_ms", inference_samples),
                ("total_ms", total_samples),
            ):
                value = result.get(key)
                if value is not None:
                    bucket.append(float(value))
        else:
            sha_all_ok = False
            error_text = str(result.get("error") or result.get("detail") or "unknown error")
            print(f"✗ {iter_job_id}: {error_text}", file=sys.stderr)
            if result.get("sha256_match") is False:
                sha_all_ok = False
        if result.get("sha256_match") is False:
            sha_all_ok = False

    if args.json_summary:
        def _avg(values: list[float]) -> float | None:
            if not values:
                return None
            return round(sum(values) / len(values), 3)

        print(
            json.dumps(
                {
                    "success": successes,
                    "total": count,
                    "handshake_ms": _avg(handshake_samples),
                    "encrypt_ms": _avg(encrypt_samples),
                    "decrypt_ms": _avg(decrypt_samples),
                    "inference_ms": _avg(inference_samples),
                    "per_image_ms": _avg(total_samples),
                    "sha256_match": sha_all_ok and successes == count,
                },
                ensure_ascii=False,
            )
        )

    return 0 if successes == count else 1


if __name__ == "__main__":
    raise SystemExit(main())
