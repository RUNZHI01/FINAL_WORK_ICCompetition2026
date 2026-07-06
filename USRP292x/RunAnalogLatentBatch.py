#!/usr/bin/env python3
"""Batch runner for analog latent-IQ USRP292x transport.

The output layout intentionally matches RunQpskFileBatchSpoolArq.py:

  run_dir/image_0000/merged_round0.bin

so existing usrp_runtime.py remote decode staging can keep scanning
image_*/merged_round*.bin without knowing the PHY changed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALOG_LINK = PROJECT_ROOT / "USRP292x" / "AnalogLatentLink.py"
DEFAULT_INPUT = PROJECT_ROOT / "USRP292x" / "payloads" / "source_latent_wire_blob.bin"
DEFAULT_RUN_ROOT = PROJECT_ROOT / "USRP292x" / "analog_latent_runs"
CHILD_THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}


@dataclass
class ImageRecord:
    index: int
    input_path: Path
    image_dir: Path
    passed: bool = False
    status: int = 0
    error: str = ""
    records: list[dict[str, Any]] = field(default_factory=list)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return default if raw is None or str(raw).strip() == "" else float(raw)


def env_optional_float(name: str) -> float | None:
    raw = os.environ.get(name)
    return None if raw is None or str(raw).strip() == "" else float(raw)


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None or str(raw).strip() == "" else int(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="USRP292x analog latent-IQ batch runner.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, default=None)
    source.add_argument("--input-list", type=Path, default=None)
    source.add_argument("--input-dir", type=Path, default=None)
    parser.add_argument("--pattern", default="*.bin")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--cycle-inputs", action="store_true")
    parser.add_argument("--run-id", default=time.strftime("analog_%Y%m%d_%H%M%S"))
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    parser.add_argument("--artifact-mode", choices=("minimal", "full", "board"), default=os.environ.get("USRP_ARTIFACT_MODE", "minimal"))

    # Compatibility arguments accepted from usrp_runtime.py/QPSK runner.
    parser.add_argument("--max-arq-rounds", type=int, default=0)
    parser.add_argument("--decode-backend", default="python")
    parser.add_argument("--cpp-sync-mode", default="header")
    parser.add_argument("--decode-workers", type=int, default=1)
    parser.add_argument("--chunk-bytes", type=int, default=0)
    parser.add_argument("--fast-arq-profile", action="store_true")
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--rx-capture-mode", choices=("local", "remote-pull", "remote-decode"), default=os.environ.get("RX_CAPTURE_MODE", "local"))
    parser.add_argument("--remote-rx-ssh-target", default=os.environ.get("REMOTE_RX_SSH_TARGET", ""))
    parser.add_argument("--remote-rx-run-root", default=os.environ.get("REMOTE_RX_RUN_ROOT", "/tmp/usrp292x_remote_runs"))
    parser.add_argument("--remote-decode-bin", default=os.environ.get("REMOTE_DECODE_BIN", ""))

    parser.add_argument("--rx-control-host", default=os.environ.get("RX_CONTROL_HOST", "127.0.0.1"))
    parser.add_argument("--rx-control-port", type=int, default=env_int("RX_CONTROL_PORT", 29220))
    parser.add_argument("--tx-control-host", default=os.environ.get("TX_CONTROL_HOST", "127.0.0.1"))
    parser.add_argument("--tx-control-port", type=int, default=env_int("TX_CONTROL_PORT", 29221))
    parser.add_argument("--tx-delay-sec", type=float, default=env_float("PERSISTENT_RX_TX_DELAY", 0.010))
    parser.add_argument("--rx-timeout-sec", type=float, default=env_float("BATCH_RX_TIMEOUT_SEC", 30.0))
    parser.add_argument("--tx-timeout-sec", type=float, default=env_float("BATCH_TX_TIMEOUT_SEC", 30.0))

    parser.add_argument("--rate", type=float, default=env_float("RATE", 5_000_000.0))
    parser.add_argument("--sps", type=int, default=env_int("ANALOG_SPS", 4))
    parser.add_argument("--rrc-beta", type=float, default=env_float("ANALOG_RRC_BETA", 0.35))
    parser.add_argument("--rrc-span", type=int, default=env_int("ANALOG_RRC_SPAN", 8))
    parser.add_argument("--amp", type=int, default=env_int("AMPLITUDE", 3000))
    parser.add_argument("--zero-guard-samples", type=int, default=env_int("ANALOG_ZERO_GUARD_SAMPLES", 4096))
    parser.add_argument("--tail-guard-samples", type=int, default=env_int("ANALOG_TAIL_GUARD_SAMPLES", 4096))
    parser.add_argument("--cfo-pilot-symbols", type=int, default=env_int("ANALOG_CFO_PILOT_SYMBOLS", 1024))
    parser.add_argument("--sync-pilot-symbols", type=int, default=env_int("ANALOG_SYNC_PILOT_SYMBOLS", 1024))
    parser.add_argument("--data-block-symbols", type=int, default=env_int("ANALOG_DATA_BLOCK_SYMBOLS", 4096))
    parser.add_argument("--mid-pilot-symbols", type=int, default=env_int("ANALOG_MID_PILOT_SYMBOLS", 128))
    parser.add_argument("--capture-margin-samples", type=int, default=env_int("ANALOG_CAPTURE_MARGIN_SAMPLES", 20_000))
    parser.add_argument("--rx-post-quantize", dest="rx_post_quantize", action="store_true", default=os.environ.get("ANALOG_RX_POST_QUANTIZE", "1") != "0")
    parser.add_argument("--no-rx-post-quantize", dest="rx_post_quantize", action="store_false")
    parser.add_argument("--scramble-key", default=os.environ.get("ANALOG_SCRAMBLE_KEY", ""))
    parser.add_argument("--scramble-key-hex", default=os.environ.get("ANALOG_SCRAMBLE_KEY_HEX", ""))
    parser.add_argument("--scramble-context", default=os.environ.get("ANALOG_SCRAMBLE_CONTEXT", ""))

    parser.add_argument("--sim-cfo-hz", type=float, default=env_float("ANALOG_SIM_CFO_HZ", 0.0))
    parser.add_argument("--sim-snr-db", type=float, default=env_optional_float("ANALOG_SIM_SNR_DB"))
    parser.add_argument("--sim-gain", type=float, default=env_float("ANALOG_SIM_GAIN", 1.0))
    parser.add_argument("--sim-phase-deg", type=float, default=env_float("ANALOG_SIM_PHASE_DEG", 0.0))
    parser.add_argument("--sim-phase-drift-deg", type=float, default=env_float("ANALOG_SIM_PHASE_DRIFT_DEG", 0.0))
    parser.add_argument("--sim-dc-real", type=float, default=env_float("ANALOG_SIM_DC_REAL", 0.0))
    parser.add_argument("--sim-dc-imag", type=float, default=env_float("ANALOG_SIM_DC_IMAG", 0.0))
    parser.add_argument("--sim-seed", type=int, default=env_int("ANALOG_SIM_SEED", 1))
    parser.add_argument("--sync-candidates", type=int, default=env_int("ANALOG_SYNC_CANDIDATES", 12))
    parser.add_argument("--min-sync-metric", type=float, default=env_float("ANALOG_MIN_SYNC_METRIC", 0.25))
    parser.add_argument("--robust-sync", dest="robust_sync", action="store_true", default=os.environ.get("ANALOG_ROBUST_SYNC", "1") != "0")
    parser.add_argument("--no-robust-sync", dest="robust_sync", action="store_false")
    parser.add_argument("--robust-cfo-max-hz", type=float, default=env_float("ANALOG_ROBUST_CFO_MAX_HZ", 8000.0))
    parser.add_argument("--robust-cfo-step-hz", type=float, default=env_float("ANALOG_ROBUST_CFO_STEP_HZ", 500.0))
    args = parser.parse_args()
    if args.count < 1:
        raise RuntimeError("--count must be positive")
    return args


def load_inputs(args: argparse.Namespace) -> list[Path]:
    if args.input is not None:
        paths = [args.input]
    elif args.input_list is not None:
        paths = [
            Path(line.strip())
            for line in args.input_list.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    elif args.input_dir is not None:
        paths = sorted(path for path in args.input_dir.rglob(args.pattern) if path.is_file())
    else:
        paths = [DEFAULT_INPUT]

    if not paths:
        raise RuntimeError("no analog latent inputs found")
    resolved = [path.resolve() for path in paths]
    missing = [str(path) for path in resolved if not path.is_file()]
    if missing:
        raise RuntimeError(f"input payload not found: {missing[:3]}")

    if len(resolved) >= args.count:
        return resolved[:args.count]
    if len(resolved) == 1:
        return [resolved[0] for _ in range(args.count)]
    if args.cycle_inputs:
        return [resolved[idx % len(resolved)] for idx in range(args.count)]
    raise RuntimeError(f"count={args.count} requires {args.count} inputs, got {len(resolved)}")


def run_command(cmd: list[str], log_path: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(CHILD_THREAD_ENV)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stdout}")
    return proc


def send_tcp_command(host: str, port: int, line: str, timeout: float) -> str:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((line.rstrip() + "\n").encode("utf-8"))
            chunks: list[bytes] = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                if b"\n" in data:
                    break
        return b"".join(chunks).decode("utf-8", errors="replace").strip()
    except ConnectionRefusedError:
        return f"ERR_CONNECTION_REFUSED host={host} port={port}"
    except (socket.timeout, OSError):
        return f"ERR_TIMEOUT host={host} port={port}"


def run_control(host: str, port: int, line: str, log_path: Path, timeout: float) -> str:
    response = send_tcp_command(host, port, line, timeout)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(response + "\n", encoding="utf-8")
    if not response.startswith("OK"):
        raise RuntimeError(f"control command failed: {line}\n{response}")
    return response


def analog_make_args(args: argparse.Namespace, image: ImageRecord, tx_sc16: Path, manifest: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(ANALOG_LINK),
        "make",
        "--input",
        str(image.input_path),
        "--out-sc16",
        str(tx_sc16),
        "--manifest",
        str(manifest),
        "--job-id",
        f"image_{image.index:04d}",
        "--rate",
        str(args.rate),
        "--sps",
        str(args.sps),
        "--rrc-beta",
        str(args.rrc_beta),
        "--rrc-span",
        str(args.rrc_span),
        "--amp",
        str(args.amp),
        "--zero-guard-samples",
        str(args.zero_guard_samples),
        "--tail-guard-samples",
        str(args.tail_guard_samples),
        "--cfo-pilot-symbols",
        str(args.cfo_pilot_symbols),
        "--sync-pilot-symbols",
        str(args.sync_pilot_symbols),
        "--data-block-symbols",
        str(args.data_block_symbols),
        "--mid-pilot-symbols",
        str(args.mid_pilot_symbols),
        "--capture-margin-samples",
        str(args.capture_margin_samples),
        "--rx-post-quantize" if args.rx_post_quantize else "--no-rx-post-quantize",
    ]
    if args.scramble_key:
        cmd.extend(["--scramble-key", str(args.scramble_key)])
    if args.scramble_key_hex:
        cmd.extend(["--scramble-key-hex", str(args.scramble_key_hex)])
    if args.scramble_context:
        cmd.extend(["--scramble-context", str(args.scramble_context)])
    return cmd


def analog_decode_args(args: argparse.Namespace, batch_rx: Path, manifest: Path, out_npz: Path, out_wire: Path, summary: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(ANALOG_LINK),
        "decode",
        "--rx-sc16",
        str(batch_rx),
        "--manifest",
        str(manifest),
        "--out-npz",
        str(out_npz),
        "--out-wire",
        str(out_wire),
        "--summary-json",
        str(summary),
        "--sync-candidates",
        str(args.sync_candidates),
        "--min-sync-metric",
        str(args.min_sync_metric),
        "--robust-cfo-max-hz",
        str(args.robust_cfo_max_hz),
        "--robust-cfo-step-hz",
        str(args.robust_cfo_step_hz),
    ]
    cmd.append("--robust-sync" if args.robust_sync else "--no-robust-sync")
    if args.scramble_key:
        cmd.extend(["--scramble-key", str(args.scramble_key)])
    if args.scramble_key_hex:
        cmd.extend(["--scramble-key-hex", str(args.scramble_key_hex)])
    if args.scramble_context:
        cmd.extend(["--scramble-context", str(args.scramble_context)])
    return cmd


def simulated_channel_enabled(args: argparse.Namespace) -> bool:
    return (
        abs(float(args.sim_cfo_hz)) > 0.0
        or args.sim_snr_db is not None
        or abs(float(args.sim_gain) - 1.0) > 0.0
        or abs(float(args.sim_phase_deg)) > 0.0
        or abs(float(args.sim_phase_drift_deg)) > 0.0
        or abs(float(args.sim_dc_real)) > 0.0
        or abs(float(args.sim_dc_imag)) > 0.0
    )


def analog_simulate_args(args: argparse.Namespace, tx_sc16: Path, manifest: Path, batch_rx: Path, summary: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(ANALOG_LINK),
        "simulate-channel",
        "--tx-sc16",
        str(tx_sc16),
        "--manifest",
        str(manifest),
        "--out-sc16",
        str(batch_rx),
        "--cfo-hz",
        str(args.sim_cfo_hz),
        "--gain",
        str(args.sim_gain),
        "--phase-deg",
        str(args.sim_phase_deg),
        "--phase-drift-deg",
        str(args.sim_phase_drift_deg),
        "--dc-real",
        str(args.sim_dc_real),
        "--dc-imag",
        str(args.sim_dc_imag),
        "--seed",
        str(args.sim_seed),
        "--summary-json",
        str(summary),
    ]
    if args.sim_snr_db is not None:
        cmd.extend(["--snr-db", str(args.sim_snr_db)])
    return cmd


def process_image(args: argparse.Namespace, image: ImageRecord) -> ImageRecord:
    started = time.monotonic()
    image.image_dir.mkdir(parents=True, exist_ok=True)
    tx_sc16 = image.image_dir / "tx_analog.sc16"
    batch_rx = image.image_dir / "batch_rx.sc16"
    manifest_path = image.image_dir / "manifest.json"
    out_npz = image.image_dir / "received_latent.npz"
    out_wire = image.image_dir / "merged_round0.bin"
    decode_summary = image.image_dir / "decode_summary.json"

    try:
        make_started = time.monotonic()
        run_command(analog_make_args(args, image, tx_sc16, manifest_path), image.image_dir / "make.log")
        make_wall_sec = time.monotonic() - make_started
        manifest = read_json(manifest_path)

        if args.dry_run:
            if simulated_channel_enabled(args):
                run_command(
                    analog_simulate_args(args, tx_sc16, manifest_path, batch_rx, image.image_dir / "simulate_channel_summary.json"),
                    image.image_dir / "simulate_channel.log",
                )
            else:
                shutil.copy2(tx_sc16, batch_rx)
            rx_capture_wall_sec = 0.0
            tx_wall_sec = 0.0
        else:
            if args.rx_capture_mode != "local":
                raise RuntimeError(
                    "RunAnalogLatentBatch.py currently supports --rx-capture-mode=local for real RF; "
                    f"got {args.rx_capture_mode}"
                )
            capture_nsamps = int(manifest["capture_nsamps"])
            capture_timeout = max(args.rx_timeout_sec, capture_nsamps / float(args.rate) + 5.0)
            rx_started = time.monotonic()
            run_control(
                args.rx_control_host,
                args.rx_control_port,
                f"CAPTURE file={batch_rx} duration=0 nsamps={capture_nsamps}",
                image.image_dir / "rx_capture.log",
                capture_timeout,
            )
            time.sleep(max(0.0, float(args.tx_delay_sec)))
            tx_started = time.monotonic()
            run_control(
                args.tx_control_host,
                args.tx_control_port,
                f"SEND file={tx_sc16}",
                image.image_dir / "tx_send.log",
                args.tx_timeout_sec,
            )
            tx_wall_sec = time.monotonic() - tx_started
            run_control(
                args.rx_control_host,
                args.rx_control_port,
                f"WAIT timeout={capture_nsamps / float(args.rate) + 1.0:.6f}",
                image.image_dir / "rx_wait.log",
                capture_timeout,
            )
            rx_capture_wall_sec = time.monotonic() - rx_started

        decode_started = time.monotonic()
        proc = run_command(
            analog_decode_args(args, batch_rx, manifest_path, out_npz, out_wire, decode_summary),
            image.image_dir / "decode.log",
            check=False,
        )
        decode_wall_sec = time.monotonic() - decode_started
        image.status = int(proc.returncode)
        image.passed = proc.returncode == 0 and out_wire.is_file() and decode_summary.is_file()
        if not image.passed:
            image.error = f"analog decode failed with status {proc.returncode}"
        summary_data = read_json(decode_summary) if decode_summary.is_file() else {}
        image.records.append({
            "round": 0,
            "input": str(image.input_path),
            "tx_sc16": str(tx_sc16),
            "batch_rx": str(batch_rx),
            "manifest": str(manifest_path),
            "merged_bin": str(out_wire),
            "decode_summary": str(decode_summary),
            "waveform_samples": int(manifest.get("tx_waveform_samples") or 0),
            "capture_nsamps": int(manifest.get("capture_nsamps") or 0),
            "detected_airtime_ms": summary_data.get("detected_airtime_ms"),
            "sync_success": summary_data.get("sync_success"),
            "sync_search_mode": summary_data.get("sync_search_mode"),
            "sync_metric": summary_data.get("sync_metric"),
            "estimated_cfo_hz": summary_data.get("estimated_cfo_hz"),
            "evm_rms": summary_data.get("evm_rms"),
            "estimated_snr_db": summary_data.get("estimated_snr_db"),
            "rx_clipping_ratio": summary_data.get("rx_clipping_ratio"),
            "simulated_cfo_hz": float(args.sim_cfo_hz) if args.dry_run and simulated_channel_enabled(args) else None,
            "simulated_snr_db": float(args.sim_snr_db) if args.dry_run and simulated_channel_enabled(args) and args.sim_snr_db is not None else None,
            "make_wall_sec": make_wall_sec,
            "tx_wall_sec": tx_wall_sec,
            "rx_capture_wall_sec": rx_capture_wall_sec,
            "decode_wall_sec": decode_wall_sec,
            "total_wall_sec": time.monotonic() - started,
            "payload_is_bit_exact": False,
        })
    except Exception as exc:
        image.status = 1
        image.passed = False
        image.error = str(exc)
        image.records.append({
            "round": 0,
            "input": str(image.input_path),
            "error": image.error,
            "total_wall_sec": time.monotonic() - started,
            "payload_is_bit_exact": False,
        })
    return image


def main() -> int:
    args = parse_args()
    inputs = load_inputs(args)
    run_dir = args.run_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    images = [
        ImageRecord(index=idx, input_path=path, image_dir=run_dir / f"image_{idx:04d}")
        for idx, path in enumerate(inputs)
    ]

    started = time.monotonic()
    completed: list[ImageRecord] = []
    for image in images:
        result = process_image(args, image)
        completed.append(result)
        if args.stop_on_fail and not result.passed:
            break

    summary = {
        "version": 1,
        "phy": "analog-latent-iq",
        "runner": str(Path(__file__).resolve()),
        "run_id": args.run_id,
        "run_dir": str(run_dir),
        "target_count": int(args.count),
        "completed_count": len(completed),
        "passed_count": sum(1 for image in completed if image.passed),
        "failed_count": sum(1 for image in completed if not image.passed),
        "payload_is_bit_exact": False,
        "dry_run": bool(args.dry_run),
        "channel_mode": os.environ.get("JSCC_CHANNEL_MODE", ""),
        "rate": float(args.rate),
        "sps": int(args.sps),
        "rx_post_quantize": bool(args.rx_post_quantize),
        "robust_sync": bool(args.robust_sync),
        "sync_candidates": int(args.sync_candidates),
        "min_sync_metric": float(args.min_sync_metric),
        "robust_cfo_max_hz": float(args.robust_cfo_max_hz),
        "robust_cfo_step_hz": float(args.robust_cfo_step_hz),
        "scrambling_enabled": bool(args.scramble_key or args.scramble_key_hex),
        "simulated_channel": {
            "enabled": bool(args.dry_run and simulated_channel_enabled(args)),
            "cfo_hz": float(args.sim_cfo_hz),
            "snr_db": None if args.sim_snr_db is None else float(args.sim_snr_db),
            "gain": float(args.sim_gain),
            "phase_deg": float(args.sim_phase_deg),
            "phase_drift_deg": float(args.sim_phase_drift_deg),
            "dc_real": float(args.sim_dc_real),
            "dc_imag": float(args.sim_dc_imag),
            "seed": int(args.sim_seed),
        },
        "wall_sec": time.monotonic() - started,
        "images": [
            {
                "index": image.index,
                "input": str(image.input_path),
                "image_dir": str(image.image_dir),
                "passed": image.passed,
                "status": image.status,
                "error": image.error,
                "rounds": len(image.records),
                "round_records": image.records,
            }
            for image in completed
        ],
    }
    write_json(run_dir / "batch_spool_summary.json", summary)
    print(json.dumps({
        "status": "ok" if summary["failed_count"] == 0 else "failed",
        "run_dir": str(run_dir),
        "passed_count": summary["passed_count"],
        "failed_count": summary["failed_count"],
    }, ensure_ascii=False))
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
