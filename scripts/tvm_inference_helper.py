#!/usr/bin/env python3
"""
TVM 推理辅助脚本 — 供 tcp_server.py 通过子进程调用

在 tvm310_safe 环境中运行：
  /home/user/anaconda3/envs/tvm310_safe/bin/python tvm_inference_helper.py \
      --artifact-path /path/to/optimized_model.so \
      --input /path/to/latent.npz \
      --output /path/to/result.npy \
      --snr 10

输出 JSON 到 stdout：
  {"status": "ok", "inference_ms": 231.5, "output_shape": [1,3,256,256], ...}
"""

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

try:
    import tvm
    from tvm import relax
except ImportError:
    print(json.dumps({"status": "error", "message": "tvm not importable"}))
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    Image = None


# ── 核心函数（从 current_real_reconstruction.py 精简）──

def ensure_batched(latent):
    latent = np.asarray(latent, dtype=np.float32)
    if latent.ndim == 3:
        latent = np.expand_dims(latent, axis=0)
    return latent


def load_npz(path_or_bytes):
    source = path_or_bytes
    if isinstance(source, (bytes, bytearray, memoryview)):
        source = io.BytesIO(bytes(source))

    with np.load(source) as payload:
        if "latent" in payload:
            return ensure_batched(payload["latent"])
        q = np.asarray(payload["quant"], dtype=np.float32)
        s = np.asarray(payload["scale"], dtype=np.float32)
        zp = np.asarray(payload["zero_point"], dtype=np.float32)
        return ensure_batched((q - zp) * s)


def awgn_channel(latent, snr):
    latent = np.asarray(latent, dtype=np.float32)
    power = np.mean(np.square(latent), axis=(-3, -2, -1), keepdims=True) * 2.0
    noise_power = power * (10.0 ** (-snr / 10.0))
    noise = np.sqrt(noise_power / 2.0) * np.random.standard_normal(latent.shape).astype(np.float32)
    noisy = latent + noise

    latent64 = latent.astype(np.float64, copy=False)
    noisy64 = noisy.astype(np.float64, copy=False)
    noise64 = noisy64 - latent64
    signal_power = float(np.mean(np.square(latent64)) * 2.0)
    realized_noise_power = float(np.mean(np.square(noise64)) * 2.0)
    realized_snr_db = None
    awgn_note = ''
    awgn_valid = signal_power > 0.0
    if not awgn_valid:
        awgn_note = 'zero_signal_input'
    elif realized_noise_power > 0.0:
        realized_snr_db = float(10.0 * np.log10(max(signal_power, 1e-30) / realized_noise_power))
    else:
        realized_snr_db = float('inf')

    metrics = {
        'jscc_configured_awgn_snr_db': float(snr),
        'jscc_realized_awgn_snr_db': realized_snr_db,
        'jscc_awgn_snr_valid': awgn_valid,
        'jscc_awgn_note': awgn_note,
        'jscc_awgn_signal_power': signal_power,
        'jscc_awgn_target_noise_power': float(np.mean(noise_power)),
        'jscc_awgn_realized_noise_power': realized_noise_power,
    }
    return noisy, metrics


def apply_channel(latent, snr, channel_mode):
    mode = str(channel_mode or "sim-awgn").strip().lower()
    if mode == "sim-awgn":
        noisy, metrics = awgn_channel(latent, snr)
        metrics.update({
            "channel_mode": mode,
            "awgn_injected": True,
        })
        return noisy.astype(np.float32), metrics
    if mode in ("real-usrp", "none"):
        metrics = {
            "channel_mode": mode,
            "awgn_injected": False,
            "jscc_configured_awgn_snr_db": float(snr),
            "jscc_realized_awgn_snr_db": None,
            "jscc_awgn_snr_valid": False,
            "jscc_awgn_note": "software_awgn_disabled",
        }
        return np.asarray(latent, dtype=np.float32), metrics
    raise ValueError(f"unsupported channel_mode: {channel_mode}")


def runtime_tensor(array, dev):
    rt = getattr(tvm, "runtime", None)
    fn = getattr(rt, "tensor", None) if rt is not None else None
    if fn is None and rt is not None:
        nd = getattr(rt, "ndarray", None)
        if nd is not None:
            fn = lambda arr, device: nd.array(arr, device)
    if fn is None:
        raise AttributeError("tvm.runtime has neither tensor nor ndarray.array")
    return fn(array, dev)


def load_runtime(
    artifact_path: str,
):
    """加载 TVM runtime，返回 (device, fn, load_ms)。"""
    t0 = time.perf_counter()
    dev = tvm.cpu(0)
    lib = tvm.runtime.load_module(artifact_path)
    vm = relax.VirtualMachine(lib, dev)
    fn = vm["main"]
    load_ms = (time.perf_counter() - t0) * 1000
    return dev, fn, load_ms


def run_inference(
    *,
    fn,
    dev,
    input_payload,
    snr: float,
    channel_mode: str = "sim-awgn",
    include_output: bool = False,
) -> tuple[dict[str, object], np.ndarray]:
    """执行一次推理并返回摘要，可选内联输出 .npy 字节。"""
    latent = load_npz(input_payload)
    model_input, channel_metrics = apply_channel(latent, snr, channel_mode)

    t0 = time.perf_counter()
    output = fn(runtime_tensor(model_input, dev))
    output_np = output.numpy() if hasattr(output, "numpy") else np.asarray(output)
    inference_ms = (time.perf_counter() - t0) * 1000

    result: dict[str, object] = {
        "status": "ok",
        "inference_ms": inference_ms,
        "output_shape": list(output_np.shape),
        "output_dtype": str(output_np.dtype),
        "output_bytes": int(output_np.nbytes),
        "input_shape": list(latent.shape),
        "snr": float(snr),
    }
    result.update(channel_metrics)
    if include_output:
        output_buffer = io.BytesIO()
        np.save(output_buffer, output_np)
        result["output_npy_b64"] = base64.b64encode(output_buffer.getvalue()).decode("ascii")
    return result, output_np


def daemon_loop(*, artifact_path: str, snr: float, channel_mode: str) -> int:
    """守护模式：加载一次模型，通过 stdin JSON 连续推理。"""
    requests_served = 0
    dev, fn, load_ms = load_runtime(artifact_path)

    def _write(payload: dict[str, object]) -> None:
        json.dump(payload, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")
        sys.stdout.flush()

    _write(
        {
            "status": "ready",
            "load_ms": round(float(load_ms), 3),
            "artifact_path": artifact_path,
        }
    )

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            command = json.loads(line)
        except json.JSONDecodeError as exc:
            _write({"status": "error", "message": f"invalid JSON: {exc}"})
            continue

        action = str(command.get("action") or "").strip().lower()
        if action == "ping":
            _write(
                {
                    "status": "alive",
                    "load_ms": round(float(load_ms), 3),
                    "requests_served": requests_served,
                }
            )
            continue
        if action == "quit":
            _write({"status": "bye", "requests_served": requests_served})
            break
        if action != "infer":
            _write({"status": "error", "message": f"unknown action: {action}"})
            continue

        try:
            input_b64 = str(command.get("input_b64") or "").strip()
            if not input_b64:
                raise RuntimeError("missing input_b64")
            payload = base64.b64decode(input_b64.encode("ascii"))
            include_output = bool(command.get("expect_result"))
            result, _ = run_inference(
                fn=fn,
                dev=dev,
                input_payload=payload,
                snr=float(command.get("snr") or snr),
                channel_mode=str(command.get("channel_mode") or channel_mode),
                include_output=include_output,
            )
            requests_served += 1
            result["load_ms"] = round(float(load_ms), 3)
            result["requests_served"] = requests_served
            _write(result)
        except Exception as exc:
            _write({"status": "error", "message": str(exc), "requests_served": requests_served})

    return 0


def main():
    parser = argparse.ArgumentParser(description="TVM 单文件推理辅助")
    parser.add_argument("--artifact-path", required=True, help="TVM 模型 .so 路径")
    parser.add_argument("--input", required=False, help="输入 .npz latent 文件")
    parser.add_argument("--output", required=False, help="输出 .npy 结果路径")
    parser.add_argument("--snr", type=float, default=10.0, help="JSCC/AWGN 仿真 SNR (dB)")
    parser.add_argument(
        "--channel-mode",
        choices=["sim-awgn", "real-usrp", "none"],
        default=os.environ.get("JSCC_CHANNEL_MODE", "sim-awgn"),
        help="sim-awgn 注入软件 AWGN；real-usrp/none 直接使用输入 latent",
    )
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--daemon", action="store_true", help="常驻模式：stdin JSON 请求，stdout JSON 响应")
    args = parser.parse_args()

    if args.seed is not None:
        np.random.seed(args.seed)

    if args.daemon:
        return daemon_loop(artifact_path=args.artifact_path, snr=args.snr, channel_mode=args.channel_mode)

    if not args.input or not args.output:
        parser.error("非 daemon 模式需要 --input 和 --output")

    result = {"status": "error"}

    try:
        dev, fn, load_ms = load_runtime(args.artifact_path)
        result, output_np = run_inference(
            fn=fn,
            dev=dev,
            input_payload=args.input,
            snr=args.snr,
            channel_mode=args.channel_mode,
            include_output=False,
        )

        # 保存
        np.save(args.output, output_np)

        result["load_ms"] = load_ms
        result["output_path"] = args.output

    except Exception as e:
        result = {"status": "error", "message": str(e)}

    print(json.dumps(result))
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
