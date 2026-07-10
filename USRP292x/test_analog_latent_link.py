#!/usr/bin/env python3
"""Regression tests for the analog latent-IQ USRP path."""

import json
import os
import subprocess
import sys
import threading
import time
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ANALOG_LINK = PROJECT_ROOT / "USRP292x" / "AnalogLatentLink.py"
ANALOG_BATCH = PROJECT_ROOT / "USRP292x" / "RunAnalogLatentBatch.py"
OTA_RX_SERVER = PROJECT_ROOT / "USRP292x" / "OtaRxPersistentServer.cpp"
OTA_RX_SERVER_SCRIPT = PROJECT_ROOT / "USRP292x" / "OtaRxPersistentServer.sh"

from USRP292x import AnalogLatentLink as analog  # noqa: E402
from USRP292x import RunAnalogLatentBatch as analog_batch  # noqa: E402


def test_persistent_rx_startup_drain_can_be_stopped_before_stream_start():
    source = OTA_RX_SERVER.read_text(encoding="utf-8")
    drain_start = source.index("// Drain any residual samples from a previous capture.")
    drain_end = source.index("std::vector<std::complex<std::int16_t>> buff", drain_start)
    drain_block = source[drain_start:drain_end]

    assert "stop_requested_.load()" in drain_block
    assert "drain_deadline" in drain_block
    assert "recv(&drain_buf.front(), drain_buf.size(), drain_md, 0.0)" in drain_block


def test_persistent_rx_capture_arm_wait_is_configurable():
    source = OTA_RX_SERVER.read_text(encoding="utf-8")

    assert "arm_wait_ms" in source
    assert "--arm-wait-ms" in source
    assert "std::chrono::milliseconds(opts_.arm_wait_ms)" in source
    assert "std::chrono::seconds(2)" not in source


def test_persistent_rx_stop_waits_for_worker_before_replying():
    source = OTA_RX_SERVER.read_text(encoding="utf-8")
    script = OTA_RX_SERVER_SCRIPT.read_text(encoding="utf-8")
    stop_branch = source[source.index('} else if (cmd == "STOP")'):source.index('} else if (cmd == "QUIT")')]

    assert "stop_wait_ms" in source
    assert "--stop-wait-ms" in source
    assert "invalid --stop-wait-ms" in source
    assert 'STOP_WAIT_MS="${STOP_WAIT_MS:-8000}"' in script
    assert '--stop-wait-ms "${STOP_WAIT_MS}"' in script
    assert "Snapshot stop_and_wait" in source
    assert "rx.stop_and_wait" in stop_branch
    assert "rx.stop()" not in stop_branch


def test_persistent_rx_snapshot_reports_server_stage_timings():
    source = OTA_RX_SERVER.read_text(encoding="utf-8")
    format_block = source[source.index("std::string format_snapshot"):source.index("bool has_sensor")]

    for field in (
        "arm_wait_sec",
        "drain_sec",
        "stream_cmd_sec",
        "receive_sec",
        "stop_cmd_sec",
        "stop_wait_sec",
    ):
        assert f"double {field}" in source
        assert f'<< " {field}="' in format_block


def test_load_latent_accepts_quantized_pt_jscc_output(tmp_path):
    quant = torch.arange(1 * 4 * 4 * 4, dtype=torch.uint8).reshape(1, 4, 4, 4)
    scale = torch.tensor(0.25, dtype=torch.float32)
    zero_point = torch.tensor(8.0, dtype=torch.float32)
    input_path = tmp_path / "quantized_latent.pt"
    torch.save({"quant": quant, "scale": scale, "zero_point": zero_point}, input_path)

    latent, info = analog.load_latent(input_path)

    expected = (quant.numpy().astype(np.float32) - 8.0) * 0.25
    assert latent.shape == expected.shape
    assert np.allclose(latent, expected)
    assert info["dtype"] == "float32"
    assert info["source_format"] == "pt"


def test_make_decode_clean_sc16_loopback_recovers_float_latent(tmp_path):
    rng = np.random.default_rng(123)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    out_wire = tmp_path / "merged_round0.bin"
    summary = tmp_path / "decode_summary.json"
    np.savez(input_path, latent=latent)

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "make",
            "--input",
            str(input_path),
            "--out-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--rate",
            "5000000",
            "--sps",
            "4",
            "--amp",
            "3000",
            "--cfo-pilot-symbols",
            "128",
            "--sync-pilot-symbols",
            "128",
            "--data-block-symbols",
            "256",
            "--mid-pilot-symbols",
            "32",
            "--zero-guard-samples",
            "256",
            "--tail-guard-samples",
            "256",
            "--no-rx-post-quantize",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(out_npz),
            "--out-wire",
            str(out_wire),
            "--summary-json",
            str(summary),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    with np.load(out_npz) as payload:
        recovered = payload["latent"]
    summary_data = json.loads(summary.read_text(encoding="utf-8"))
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))

    assert summary_data["sync_success"] is True
    assert summary_data["payload_is_bit_exact"] is False
    assert summary_data["decode_total_ms"] >= 0.0
    assert "initial_sync" in summary_data["decode_timing_ms"]
    assert "matched_filter" in summary_data["decode_timing_ms"]
    assert manifest_data["payload_is_bit_exact"] is False
    assert recovered.shape == latent.shape
    assert out_wire.is_file()
    assert float(np.mean(np.square(recovered - latent))) < 5.0e-4


def test_atomic_savez_publishes_final_npz_with_replace(tmp_path, monkeypatch):
    final_npz = tmp_path / "received_latent.npz"
    save_paths: list[Path] = []
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = analog.os.replace

    def fake_savez(path, **_items):
        save_path = Path(path)
        save_paths.append(save_path)
        save_path.write_bytes(b"complete-npz")

    def fake_replace(src, dst):
        src_path = Path(src)
        dst_path = Path(dst)
        replace_calls.append((src_path, dst_path))
        real_replace(src_path, dst_path)

    monkeypatch.setattr(analog.np, "savez", fake_savez)
    monkeypatch.setattr(analog.os, "replace", fake_replace)

    analog.atomic_savez(final_npz, latent=np.zeros((1, 1, 1, 1), dtype=np.float32))

    assert final_npz.read_bytes() == b"complete-npz"
    assert save_paths and save_paths[0] != final_npz
    assert save_paths[0].name.endswith(".tmp.npz")
    assert replace_calls == [(save_paths[0], final_npz)]
    assert not save_paths[0].exists()


def test_atomic_savez_can_publish_latent_npy_with_replace(tmp_path, monkeypatch):
    final_npy = tmp_path / "received_latent.npy"
    latent = np.arange(12, dtype=np.float32).reshape(1, 3, 2, 2)
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = analog.os.replace

    def fake_replace(src, dst):
        src_path = Path(src)
        dst_path = Path(dst)
        replace_calls.append((src_path, dst_path))
        real_replace(src_path, dst_path)

    monkeypatch.setattr(analog.os, "replace", fake_replace)

    analog.atomic_savez(final_npy, latent=latent)

    np.testing.assert_array_equal(np.load(final_npy), latent)
    assert replace_calls and replace_calls[0][1] == final_npy
    assert replace_calls[0][0].name.endswith(".tmp.npy")
    assert not replace_calls[0][0].exists()


def test_remote_decoded_output_path_honors_configured_format():
    args = Namespace(remote_decoded_format="npy")

    assert (
        analog_batch.remote_decoded_output_path(args, "/home/user/cockpit_usrp_rx/run42_rx", 7)
        == "/home/user/cockpit_usrp_rx/run42_rx/00000007.npy"
    )

    args.remote_decoded_format = "bad"
    assert (
        analog_batch.remote_decoded_output_path(args, "/home/user/cockpit_usrp_rx/run42_rx", 7)
        == "/home/user/cockpit_usrp_rx/run42_rx/00000007.npz"
    )


def test_find_sync_candidates_uses_fft_for_large_search_when_available():
    scipy_signal = analog.scipy_signal_module()
    rng = np.random.default_rng(125)
    sync = (
        rng.standard_normal(1024).astype(np.float32)
        + 1j * rng.standard_normal(1024).astype(np.float32)
    ).astype(np.complex64)
    sps = 4
    phase = 2
    sync_start = 700
    stream = (
        0.01 * rng.standard_normal(2400).astype(np.float32)
        + 1j * 0.01 * rng.standard_normal(2400).astype(np.float32)
    ).astype(np.complex64)
    stream[sync_start:sync_start + sync.size] += sync
    mf = np.zeros(stream.size * sps, dtype=np.complex64)
    mf[phase::sps] = stream

    candidates = analog.find_sync_candidates(
        mf,
        sync,
        sps,
        max_candidates=1,
        search_center_symbol=sync_start,
        search_window_symbols=1024,
    )

    assert candidates
    assert candidates[0]["phase"] == phase
    assert abs(candidates[0]["sync_start"] - sync_start) <= 1
    expected_method = "scipy-fft" if scipy_signal is not None else "numpy-direct"
    assert candidates[0]["sync_correlation_method"] == expected_method


def test_decode_server_reuses_process_for_json_decode_command(tmp_path):
    rng = np.random.default_rng(124)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    out_wire = tmp_path / "merged_round0.bin"
    summary = tmp_path / "decode_summary.json"
    np.savez(input_path, latent=latent)

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "make",
            "--input",
            str(input_path),
            "--out-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--rate",
            "5000000",
            "--sps",
            "4",
            "--amp",
            "3000",
            "--cfo-pilot-symbols",
            "128",
            "--sync-pilot-symbols",
            "128",
            "--data-block-symbols",
            "256",
            "--mid-pilot-symbols",
            "32",
            "--zero-guard-samples",
            "256",
            "--tail-guard-samples",
            "256",
            "--no-rx-post-quantize",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    proc = subprocess.Popen(
        [sys.executable, str(ANALOG_LINK), "decode-server"],
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdin is not None
    request = {
        "cmd": "decode",
        "rx_sc16": str(tx_sc16),
        "manifest": str(manifest),
        "out_npz": str(out_npz),
        "out_wire": str(out_wire),
        "summary_json": str(summary),
    }
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
    proc.stdin.close()
    stdout, stderr = proc.communicate(timeout=30)

    assert proc.returncode == 0, stderr
    responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    assert responses[0]["status"] == "ready"
    assert responses[1]["status"] == "ok"
    assert responses[1]["summary_json"] == str(summary)
    assert responses[1]["summary"]["sync_success"] is True
    assert responses[-1]["status"] == "bye"
    assert out_npz.is_file()
    assert out_wire.is_file()
    assert summary.is_file()


def test_decode_server_request_can_write_inline_manifest_json(tmp_path):
    manifest_path = tmp_path / "remote" / "image_0000" / "manifest.json"
    request = {
        "rx_sc16": "/tmp/run/image_0000/batch_rx.sc16",
        "manifest": str(manifest_path),
        "manifest_json": {
            "version": 1,
            "phy": "analog-latent-iq",
            "capture_nsamps": 1234,
        },
        "out_npz": "/tmp/run/image_0000/received_latent.npz",
        "out_wire": "",
        "summary_json": "/tmp/run/image_0000/decode_summary.json",
    }

    namespace = analog.decode_namespace_from_request(request)

    assert namespace.manifest == str(manifest_path)
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["capture_nsamps"] == 1234


def test_decode_pipeline_warmup_runs_representative_decode(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALOG_DECODE_PIPELINE_WARMUP", "1")
    monkeypatch.setenv("ANALOG_DECODE_WARMUP_DIR", str(tmp_path / "warmup"))
    monkeypatch.setenv("ANALOG_DECODE_WARMUP_SHAPE", "1,4,4,4")
    monkeypatch.setenv("ANALOG_SPS", "2")
    monkeypatch.setenv("ANALOG_AMPLITUDE", "3000")
    monkeypatch.setenv("ANALOG_SYNC_SEARCH_WINDOW_SYMBOLS", "1024")

    payload = analog.warm_decode_pipeline()

    assert payload["decode_pipeline_warmup_enabled"] is True
    assert payload["decode_pipeline_warmup_status"] == "ok"
    assert payload["decode_pipeline_warmup_decode_total_ms"] >= 0.0


def test_remote_decode_worker_serializes_requests_as_ascii(tmp_path):
    writes: list[str] = []

    class FakeStdin:
        def write(self, text: str) -> None:
            text.encode("ascii")
            writes.append(text)

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeProc:
        stdin = FakeStdin()
        returncode = None

        def poll(self) -> None:
            return None

    class FakeHandle:
        def close(self) -> None:
            return None

    responses: "queue.Queue[str]" = analog_batch.queue.Queue()
    responses.put(json.dumps({"status": "ok"}))
    worker = analog_batch.RemoteAnalogDecodeWorker(
        FakeProc(),
        FakeHandle(),
        responses,
        None,
        {"status": "ready"},
        0.0,
    )

    worker.decode(
        {"manifest_json": {"source_path": "E:/Main/Career/集创赛/input.bin"}},
        tmp_path / "remote_decode.log",
        timeout=1.0,
    )

    assert writes
    assert "\\u96c6\\u521b\\u8d5b" in writes[0]


def test_remote_decode_worker_ignores_stale_response_for_previous_request(tmp_path):
    writes: list[str] = []

    class FakeStdin:
        def write(self, text: str) -> None:
            writes.append(text)

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeProc:
        stdin = FakeStdin()
        returncode = None

        def poll(self) -> None:
            return None

    class FakeHandle:
        def close(self) -> None:
            return None

    responses: "queue.Queue[str]" = analog_batch.queue.Queue()
    responses.put(json.dumps({
        "status": "ok",
        "summary_json": "/tmp/old/decode_summary.json",
        "summary": {"status": "ok", "sync_metric": 0.1},
    }))
    responses.put(json.dumps({
        "status": "ok",
        "summary_json": "/tmp/current/decode_summary.json",
        "summary": {"status": "ok", "sync_metric": 0.9},
    }))
    worker = analog_batch.RemoteAnalogDecodeWorker(
        FakeProc(),
        FakeHandle(),
        responses,
        None,
        {"status": "ready"},
        0.0,
    )

    result = worker.decode(
        {"summary_json": "/tmp/current/decode_summary.json"},
        tmp_path / "remote_decode.log",
        timeout=1.0,
    )

    payload = json.loads(result.stdout)
    logged = json.loads((tmp_path / "remote_decode.log").read_text(encoding="utf-8"))
    assert payload["summary_json"] == "/tmp/current/decode_summary.json"
    assert logged["summary"]["sync_metric"] == 0.9
    assert writes


def test_remote_analog_decode_request_includes_request_id_without_summary_json():
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=False,
        sync_search_window_symbols=4096,
        dry_run=False,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        remote_decode_response_mode="minimal",
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        retry_on_burst_miss=False,
        retry_on_low_sync=False,
        low_sync_retry_threshold=0.08,
        max_arq_rounds=2,
        current_decode_attempt_index=0,
        current_decode_max_attempts=3,
    )

    request = analog_batch.remote_analog_decode_request(
        args,
        "/tmp/run/image_0000/batch_rx.sc16",
        "/tmp/run/image_0000/manifest.json",
        "/home/user/cockpit_usrp_rx/run_rx/00000000.npz",
        "",
        "",
    )

    assert request["summary_json"] == ""
    assert request["request_id"]


def test_decode_worker_response_echoes_request_id():
    response = analog.decode_worker_response(
        {"status": "ok", "sync_success": True},
        "",
        mode="minimal",
        request_id="decode-1",
    )

    assert response["request_id"] == "decode-1"
    assert response["summary_json"] == ""


def test_remote_decode_worker_uses_soft_completion_when_response_lags(tmp_path):
    writes: list[str] = []
    soft_completion_calls = 0

    class FakeStdin:
        def write(self, text: str) -> None:
            writes.append(text)

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeProc:
        stdin = FakeStdin()
        returncode = None

        def poll(self) -> None:
            return None

    class FakeHandle:
        def close(self) -> None:
            return None

    def soft_completion() -> dict[str, object]:
        nonlocal soft_completion_calls
        soft_completion_calls += 1
        return {
            "status": "ok",
            "summary_json": "/tmp/current/decode_summary.json",
            "summary": {"status": "ok", "sync_metric": 0.8},
        }

    worker = analog_batch.RemoteAnalogDecodeWorker(
        FakeProc(),
        FakeHandle(),
        analog_batch.queue.Queue(),
        None,
        {"status": "ready"},
        0.0,
    )

    result = worker.decode(
        {"summary_json": "/tmp/current/decode_summary.json"},
        tmp_path / "remote_decode.log",
        timeout=1.0,
        soft_timeout=0.01,
        soft_completion=soft_completion,
    )

    payload = json.loads(result.stdout)
    assert soft_completion_calls == 1
    assert payload["summary"]["sync_metric"] == 0.8
    assert writes


def test_remote_dir_soft_completion_returns_worker_shaped_response(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_ssh_base_args(*, timeout=10, control_socket=None):
        return ["ssh", "-T"]

    def fake_run(cmd, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps({
                "status": "ok",
                "frame_complete": True,
                "sync_metric": 0.7,
                "estimated_cfo_hz": 12.5,
            }).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(analog_batch, "_ssh_base_args", fake_ssh_base_args)
    monkeypatch.setattr(analog_batch.subprocess, "run", fake_run)

    response = analog_batch.try_remote_dir_decode_soft_completion(
        "user@board",
        "/remote/out/00000001.npz",
        "/remote/run/decode_summary.json",
        tmp_path / "soft_completion.log",
        control_socket=None,
        timeout=2.0,
    )

    assert response is not None
    assert response["status"] == "ok"
    assert response["soft_completed"] is True
    assert response["summary_json"] == "/remote/run/decode_summary.json"
    assert response["summary"]["sync_metric"] == 0.7
    assert commands
    assert "test -s /remote/out/00000001.npz" in commands[0][-1]
    assert "cat /remote/run/decode_summary.json" in commands[0][-1]


def test_remote_dir_soft_completion_can_use_output_only_for_summaryless_request(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_ssh_base_args(*, timeout=10, control_socket=None):
        return ["ssh", "-T"]

    def fake_run(cmd, **kwargs):
        commands.append(list(cmd))
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=b"",
            stderr=b"",
        )

    monkeypatch.setattr(analog_batch, "_ssh_base_args", fake_ssh_base_args)
    monkeypatch.setattr(analog_batch.subprocess, "run", fake_run)

    response = analog_batch.try_remote_dir_decode_soft_completion(
        "user@board",
        "/remote/out/00000001.npz",
        "",
        tmp_path / "soft_completion.log",
        control_socket=None,
        timeout=2.0,
        request_id="decode-1",
    )

    assert response is not None
    assert response["status"] == "ok"
    assert response["soft_completed"] is True
    assert response["request_id"] == "decode-1"
    assert response["summary_json"] == ""
    assert response["summary"]["status"] == "ok"
    assert response["summary"]["frame_complete"] is True
    assert commands
    assert "test -s /remote/out/00000001.npz" in commands[0][-1]
    assert "cat " not in commands[0][-1]


def test_remote_decode_worker_start_skips_non_json_stdout_preamble(tmp_path, monkeypatch):
    popen_commands: list[list[str]] = []

    class FakeStdin:
        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeStdout:
        def __iter__(self):
            return iter([
                "\x1b[?9001l\x1b[?1004l\n",
                json.dumps({"status": "ready"}) + "\n",
            ])

    class FakeProc:
        stdin = FakeStdin()
        stdout = FakeStdout()
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    def fake_popen(command, *_args, **_kwargs):
        popen_commands.append(list(command))
        return FakeProc()

    monkeypatch.setattr(analog_batch.subprocess, "Popen", fake_popen)

    worker = analog_batch.RemoteAnalogDecodeWorker.start(
        "user@board",
        Namespace(
            rate=5_000_000.0,
            sps=2,
            amp=6000,
            rrc_beta=0.35,
            rrc_span=8,
            zero_guard_samples=4096,
            tail_guard_samples=4096,
            cfo_pilot_symbols=1024,
            sync_pilot_symbols=1024,
            data_block_symbols=4096,
            mid_pilot_symbols=128,
            capture_margin_samples=20000,
            rx_post_quantize=True,
            sync_candidates=12,
            min_sync_metric=0.05,
            robust_sync=False,
            sync_search_window_symbols=4096,
        ),
        tmp_path / "remote_decode_worker.log",
    )

    assert worker.ready_response == {"status": "ready"}
    remote_command = popen_commands[0][-1]
    assert "ANALOG_DECODE_PIPELINE_WARMUP=1" in remote_command
    assert "ANALOG_DECODE_WARMUP_SHAPE=1,32,32,32" in remote_command
    assert "ANALOG_SPS=2" in remote_command
    assert "ANALOG_AMPLITUDE=6000" in remote_command
    assert "ANALOG_MIN_SYNC_METRIC=0.05" in remote_command
    assert "ANALOG_ROBUST_SYNC=0" in remote_command
    worker.close()


def test_remote_decode_worker_start_applies_command_prefix(tmp_path, monkeypatch):
    popen_commands: list[list[str]] = []

    class FakeStdin:
        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeStdout:
        def __iter__(self):
            return iter([json.dumps({"status": "ready"}) + "\n"])

    class FakeProc:
        stdin = FakeStdin()
        stdout = FakeStdout()
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    def fake_popen(command, *_args, **_kwargs):
        popen_commands.append(list(command))
        return FakeProc()

    monkeypatch.setenv("ANALOG_REMOTE_DECODE_WORKER_PREFIX", "taskset -c 2")
    monkeypatch.setenv("REMOTE_DECODE_PYTHON", "/home/user/venv/bin/python")
    monkeypatch.setattr(analog_batch.subprocess, "Popen", fake_popen)

    worker = analog_batch.RemoteAnalogDecodeWorker.start(
        "user@board",
        Namespace(
            rate=5_000_000.0,
            sps=2,
            amp=6000,
            rrc_beta=0.35,
            rrc_span=8,
            zero_guard_samples=4096,
            tail_guard_samples=4096,
            cfo_pilot_symbols=1024,
            sync_pilot_symbols=1024,
            data_block_symbols=4096,
            mid_pilot_symbols=128,
            capture_margin_samples=20000,
            rx_post_quantize=True,
            sync_candidates=12,
            min_sync_metric=0.05,
            robust_sync=False,
            sync_search_window_symbols=4096,
        ),
        tmp_path / "remote_decode_worker.log",
    )

    assert worker.ready_response == {"status": "ready"}
    remote_command = popen_commands[0][-1]
    assert "taskset -c 2 /home/user/venv/bin/python -u" in remote_command
    worker.close()


def test_remote_decode_worker_start_omits_command_prefix_by_default(tmp_path, monkeypatch):
    popen_commands: list[list[str]] = []

    class FakeStdin:
        def write(self, _text: str) -> None:
            return None

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeStdout:
        def __iter__(self):
            return iter([json.dumps({"status": "ready"}) + "\n"])

    class FakeProc:
        stdin = FakeStdin()
        stdout = FakeStdout()
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    def fake_popen(command, *_args, **_kwargs):
        popen_commands.append(list(command))
        return FakeProc()

    monkeypatch.delenv("ANALOG_REMOTE_DECODE_WORKER_PREFIX", raising=False)
    monkeypatch.setenv("REMOTE_DECODE_PYTHON", "/home/user/venv/bin/python")
    monkeypatch.setattr(analog_batch.subprocess, "Popen", fake_popen)

    worker = analog_batch.RemoteAnalogDecodeWorker.start(
        "user@board",
        Namespace(
            rate=5_000_000.0,
            sps=2,
            amp=6000,
            rrc_beta=0.35,
            rrc_span=8,
            zero_guard_samples=4096,
            tail_guard_samples=4096,
            cfo_pilot_symbols=1024,
            sync_pilot_symbols=1024,
            data_block_symbols=4096,
            mid_pilot_symbols=128,
            capture_margin_samples=20000,
            rx_post_quantize=True,
            sync_candidates=12,
            min_sync_metric=0.05,
            robust_sync=False,
            sync_search_window_symbols=4096,
        ),
        tmp_path / "remote_decode_worker.log",
    )

    assert worker.ready_response == {"status": "ready"}
    remote_command = popen_commands[0][-1]
    assert "taskset" not in remote_command
    assert "/home/user/venv/bin/python -u" in remote_command
    worker.close()


def test_remote_python_for_decode_rejects_tvm_composite_env(monkeypatch):
    monkeypatch.setenv(
        "REMOTE_DECODE_PYTHON",
        "env OMP_NUM_THREADS=3 /home/user/anaconda3/envs/tvm310_safe/bin/python",
    )

    assert analog_batch.remote_python_for_decode(Namespace()) == "/home/user/venv/bin/python"


def test_find_sync_candidates_respects_symbol_search_window():
    sps = 4
    sync = analog.make_pilot_symbols(32, 1002)
    mf = np.zeros(500 * sps, dtype=np.complex64)
    mf[80 * sps:(80 + sync.size) * sps:sps] = (4.0 * sync).astype(np.complex64)
    mf[260 * sps:(260 + sync.size) * sps:sps] = sync

    candidates = analog.find_sync_candidates(
        mf,
        sync,
        sps,
        max_candidates=1,
        search_center_symbol=260,
        search_window_symbols=64,
    )

    assert candidates
    assert candidates[0]["sync_start"] == 260


def test_decode_waveform_auto_centers_window_from_burst_power(tmp_path, monkeypatch):
    rng = np.random.default_rng(321)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    rx_sc16 = tmp_path / "rx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    out_wire = tmp_path / "merged_round0.bin"
    summary = tmp_path / "decode_summary.json"
    np.savez(input_path, latent=latent)

    analog.make_waveform(
        Namespace(
            input=str(input_path),
            out_sc16=str(tx_sc16),
            manifest=str(manifest),
            job_id="windowed",
            rate=5_000_000.0,
            sps=4,
            rrc_beta=0.35,
            rrc_span=8,
            amp=3000,
            zero_guard_samples=256,
            tail_guard_samples=256,
            cfo_pilot_symbols=128,
            sync_pilot_symbols=128,
            data_block_symbols=256,
            mid_pilot_symbols=32,
            cfo_seed=1001,
            sync_seed=1002,
            mid_pilot_seed=1003,
            capture_margin_samples=256,
            rx_post_quantize=False,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )
    prefix = np.zeros(12000, dtype=np.int16)
    suffix = np.zeros(8000, dtype=np.int16)
    tx_raw = np.fromfile(tx_sc16, dtype=np.int16)
    np.concatenate([prefix, tx_raw, suffix]).astype(np.int16).tofile(rx_sc16)

    def reject_full_sc16_to_complex(*_args, **_kwargs):
        raise AssertionError("windowed decode should crop raw sc16 before complex conversion")

    monkeypatch.setattr(analog, "sc16_to_complex", reject_full_sc16_to_complex)

    result = analog.decode_waveform(
        Namespace(
            rx_sc16=str(rx_sc16),
            manifest=str(manifest),
            out_npz=str(out_npz),
            out_wire=str(out_wire),
            summary_json=str(summary),
            sync_candidates=12,
            min_sync_metric=0.25,
            robust_sync=True,
            robust_cfo_max_hz=8000.0,
            robust_cfo_step_hz=500.0,
            sync_search_center_symbol=-1,
            sync_search_window_symbols=256,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )

    assert result["sync_success"] is True
    assert result["sync_search_window_enabled"] is True
    assert result["sync_search_raw_sc16_crop_enabled"] is True
    assert result["sync_search_power_decimation"] >= 2
    assert result["sync_search_center_source"] == "burst_power"
    assert result["sync_search_cropped_samples"] < result["sync_search_original_samples"]
    with np.load(out_npz) as payload:
        recovered = payload["latent"]
    assert float(np.mean(np.square(recovered - latent))) < 5.0e-4


def test_decode_waveform_fast_first_falls_back_and_records_pass_metrics(tmp_path, monkeypatch):
    rng = np.random.default_rng(126)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    summary_json = tmp_path / "decode_summary.json"
    np.savez(input_path, latent=latent)

    analog.make_waveform(
        Namespace(
            input=str(input_path),
            out_sc16=str(tx_sc16),
            manifest=str(manifest),
            job_id="fast-first-fallback",
            rate=5_000_000.0,
            sps=4,
            rrc_beta=0.35,
            rrc_span=8,
            amp=3000,
            zero_guard_samples=4096,
            tail_guard_samples=4096,
            cfo_pilot_symbols=128,
            sync_pilot_symbols=128,
            data_block_symbols=256,
            mid_pilot_symbols=32,
            cfo_seed=1001,
            sync_seed=1002,
            mid_pilot_seed=1003,
            capture_margin_samples=20_000,
            rx_post_quantize=False,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )

    original_find_sync_candidates = analog.find_sync_candidates
    observed_windows: list[int] = []

    def fake_find_sync_candidates(*args, **kwargs):
        window = int(kwargs.get("search_window_symbols", 0) or 0)
        observed_windows.append(window)
        candidates = original_find_sync_candidates(*args, **kwargs)
        if window == 1024 and candidates:
            lowered = dict(candidates[0])
            lowered["sync_metric"] = 0.05
            return [lowered]
        return candidates

    monkeypatch.setattr(analog, "find_sync_candidates", fake_find_sync_candidates)

    result = analog.decode_waveform(
        Namespace(
            rx_sc16=str(tx_sc16),
            manifest=str(manifest),
            out_npz=str(out_npz),
            out_wire="",
            summary_json=str(summary_json),
            sync_candidates=12,
            min_sync_metric=0.25,
            robust_sync=False,
            robust_cfo_max_hz=8000.0,
            robust_cfo_step_hz=500.0,
            sync_search_center_symbol=-1,
            sync_search_window_symbols=4096,
            sync_profile="fast-first",
            fast_sync_candidates=4,
            fast_sync_search_window_symbols=1024,
            fallback_sync_candidates=12,
            fallback_sync_search_window_symbols=4096,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )

    assert 1024 in observed_windows
    assert 4096 in observed_windows
    assert result["sync_profile"] == "fast-first"
    assert result["sync_pass"] == 2
    assert result["fast_sync_metric"] == 0.05
    assert result["fallback_sync_metric"] == result["selected_sync_metric"]
    assert result["fallback_sync_metric"] >= 0.25
    assert result["fast_sync_ms"] >= 0.0
    assert result["fallback_sync_ms"] >= 0.0
    assert out_npz.is_file()


def test_decode_waveform_retry_on_burst_miss_skips_full_sync_search(tmp_path, monkeypatch):
    rng = np.random.default_rng(127)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    np.savez(input_path, latent=latent)

    analog.make_waveform(
        Namespace(
            input=str(input_path),
            out_sc16=str(tx_sc16),
            manifest=str(manifest),
            job_id="burst-miss",
            rate=5_000_000.0,
            sps=4,
            rrc_beta=0.35,
            rrc_span=8,
            amp=3000,
            zero_guard_samples=4096,
            tail_guard_samples=4096,
            cfo_pilot_symbols=128,
            sync_pilot_symbols=128,
            data_block_symbols=256,
            mid_pilot_symbols=32,
            cfo_seed=1001,
            sync_seed=1002,
            mid_pilot_seed=1003,
            capture_margin_samples=20_000,
            rx_post_quantize=False,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )

    def fake_burst_miss(*_args, **_kwargs):
        return None, {
            "sync_search_center_source": "none",
            "sync_search_center_error": "burst threshold not crossed",
        }

    def reject_sync_search(*_args, **_kwargs):
        raise AssertionError("burst miss retry should skip sync search")

    monkeypatch.setattr(analog, "estimate_sync_center_from_sc16_power", fake_burst_miss)
    monkeypatch.setattr(analog, "find_sync_candidates", reject_sync_search)

    with pytest.raises(RuntimeError, match="burst threshold not crossed"):
        analog.decode_waveform(
            Namespace(
                rx_sc16=str(tx_sc16),
                manifest=str(manifest),
                out_npz=str(out_npz),
                out_wire="",
                summary_json="",
                sync_candidates=12,
                min_sync_metric=0.25,
                robust_sync=False,
                robust_cfo_max_hz=8000.0,
                robust_cfo_step_hz=500.0,
                sync_search_center_symbol=-1,
                sync_search_window_symbols=4096,
                sync_profile="fast-first",
                fast_sync_candidates=4,
                fast_sync_search_window_symbols=1024,
                fallback_sync_candidates=12,
                fallback_sync_search_window_symbols=4096,
                retry_on_burst_miss=True,
                scramble_key="",
                scramble_key_hex="",
                scramble_context="",
            )
        )


def test_decode_waveform_retry_on_low_sync_skips_payload_and_fallback(tmp_path, monkeypatch):
    rng = np.random.default_rng(128)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    np.savez(input_path, latent=latent)

    analog.make_waveform(
        Namespace(
            input=str(input_path),
            out_sc16=str(tx_sc16),
            manifest=str(manifest),
            job_id="low-sync-retry",
            rate=5_000_000.0,
            sps=4,
            rrc_beta=0.35,
            rrc_span=8,
            amp=3000,
            zero_guard_samples=4096,
            tail_guard_samples=4096,
            cfo_pilot_symbols=128,
            sync_pilot_symbols=128,
            data_block_symbols=256,
            mid_pilot_symbols=32,
            cfo_seed=1001,
            sync_seed=1002,
            mid_pilot_seed=1003,
            capture_margin_samples=20_000,
            rx_post_quantize=False,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )

    original_find_sync_candidates = analog.find_sync_candidates
    observed_windows: list[int] = []

    def fake_find_sync_candidates(*args, **kwargs):
        window = int(kwargs.get("search_window_symbols", 0) or 0)
        observed_windows.append(window)
        if window == 4096:
            raise AssertionError("low sync retry should skip fallback sync search")
        candidates = original_find_sync_candidates(*args, **kwargs)
        if window == 1024 and candidates:
            lowered = dict(candidates[0])
            lowered["sync_metric"] = 0.06
            return [lowered]
        return candidates

    def reject_payload_recovery(*_args, **_kwargs):
        raise AssertionError("low sync retry should skip payload recovery")

    monkeypatch.setattr(analog, "find_sync_candidates", fake_find_sync_candidates)
    monkeypatch.setattr(analog, "recover_payload_with_fixed_cfo", reject_payload_recovery)

    with pytest.raises(RuntimeError, match="low sync metric .*retry threshold"):
        analog.decode_waveform(
            Namespace(
                rx_sc16=str(tx_sc16),
                manifest=str(manifest),
                out_npz=str(out_npz),
                out_wire="",
                summary_json="",
                sync_candidates=12,
                min_sync_metric=0.05,
                robust_sync=False,
                robust_cfo_max_hz=8000.0,
                robust_cfo_step_hz=500.0,
                sync_search_center_symbol=-1,
                sync_search_window_symbols=4096,
                sync_profile="fast-first",
                fast_sync_candidates=4,
                fast_sync_search_window_symbols=1024,
                fallback_sync_candidates=12,
                fallback_sync_search_window_symbols=4096,
                retry_on_burst_miss=False,
                retry_on_low_sync=True,
                low_sync_retry_threshold=0.08,
                scramble_key="",
                scramble_key_hex="",
                scramble_context="",
            )
        )

    assert 1024 in observed_windows
    assert 4096 not in observed_windows
    assert not out_npz.exists()


def test_decimated_sc16_power_center_matches_full_scan(tmp_path):
    rng = np.random.default_rng(654)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    rx_sc16 = tmp_path / "rx_analog.sc16"
    manifest_path = tmp_path / "manifest.json"
    np.savez(input_path, latent=latent)

    analog.make_waveform(
        Namespace(
            input=str(input_path),
            out_sc16=str(tx_sc16),
            manifest=str(manifest_path),
            job_id="decimated-power",
            rate=5_000_000.0,
            sps=4,
            rrc_beta=0.35,
            rrc_span=8,
            amp=3000,
            zero_guard_samples=256,
            tail_guard_samples=256,
            cfo_pilot_symbols=128,
            sync_pilot_symbols=128,
            data_block_symbols=256,
            mid_pilot_symbols=32,
            cfo_seed=1001,
            sync_seed=1002,
            mid_pilot_seed=1003,
            capture_margin_samples=256,
            rx_post_quantize=False,
            scramble_key="",
            scramble_key_hex="",
            scramble_context="",
        )
    )
    tx_raw = np.fromfile(tx_sc16, dtype=np.int16)
    np.concatenate([np.zeros(10000, dtype=np.int16), tx_raw, np.zeros(8000, dtype=np.int16)]).tofile(rx_sc16)
    manifest = analog.read_json(manifest_path)
    raw, _clip = analog.read_sc16_raw(rx_sc16)
    dc = analog.estimate_dc_from_sc16_raw(raw, int(manifest["zero_guard_samples"]), int(manifest["sc16_amplitude"]))

    full_center, _full_metrics = analog.estimate_sync_center_from_sc16_power(
        raw,
        manifest,
        sps=int(manifest["sps"]),
        amplitude=int(manifest["sc16_amplitude"]),
        dc=dc,
        decimation=1,
    )
    fast_center, fast_metrics = analog.estimate_sync_center_from_sc16_power(
        raw,
        manifest,
        sps=int(manifest["sps"]),
        amplitude=int(manifest["sc16_amplitude"]),
        dc=dc,
        decimation=8,
    )

    assert full_center is not None
    assert fast_center is not None
    assert abs(fast_center - full_center) <= 8
    assert fast_metrics["sync_search_power_decimation"] == 8


def test_batch_runner_dry_run_writes_usrp_runtime_compatible_outputs(tmp_path):
    latent = np.linspace(-0.5, 0.5, num=1 * 4 * 4 * 4, dtype=np.float32).reshape(1, 4, 4, 4)
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    np.savez(input_dir / "case0.npz", latent=latent)
    run_root = tmp_path / "runs"

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_BATCH),
            "--input-dir",
            str(input_dir),
            "--pattern",
            "*.npz",
            "--count",
            "1",
            "--run-root",
            str(run_root),
            "--run-id",
            "dry",
            "--dry-run",
            "--cfo-pilot-symbols",
            "128",
            "--sync-pilot-symbols",
            "128",
            "--data-block-symbols",
            "256",
            "--mid-pilot-symbols",
            "32",
            "--zero-guard-samples",
            "256",
            "--tail-guard-samples",
            "256",
            "--no-rx-post-quantize",
        ],
        check=True,
        cwd=PROJECT_ROOT,
        env={**os.environ, "ANALOG_REMOTE_DECODE_RESPONSE_MODE": "minimal"},
    )

    image_dir = run_root / "dry" / "image_0000"
    summary = json.loads((run_root / "dry" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert (image_dir / "tx_analog.sc16").is_file()
    assert (image_dir / "batch_rx.sc16").is_file()
    assert (image_dir / "manifest.json").is_file()
    assert (image_dir / "decode_summary.json").is_file()
    assert (image_dir / "merged_round0.bin").is_file()
    assert summary["phy"] == "analog-latent-iq"
    assert summary["images"][0]["passed"] is True
    assert summary["pass_count"] == 1
    assert summary["all_pass"] is True
    assert summary["in_process_local_codec"] is True
    assert summary["codec_warmup_wall_sec"] >= 0.0
    assert summary["remote_decode_response_mode"] == "minimal"
    assert summary["per_image_sec"] > 0.0
    assert summary["payload_airtime_ms_mean"] > 0.0
    assert summary["decode_total_wall_sec_mean"] > 0.0


def test_process_image_dry_run_uses_in_process_local_codec(tmp_path, monkeypatch):
    latent = np.linspace(-0.5, 0.5, num=1 * 4 * 4 * 4, dtype=np.float32).reshape(1, 4, 4, 4)
    input_path = tmp_path / "case0.npz"
    np.savez(input_path, latent=latent)
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=True,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        rate=5_000_000.0,
        sps=4,
        rrc_beta=0.35,
        rrc_span=8,
        amp=3000,
        zero_guard_samples=256,
        tail_guard_samples=256,
        cfo_pilot_symbols=128,
        sync_pilot_symbols=128,
        data_block_symbols=256,
        mid_pilot_symbols=32,
        capture_margin_samples=256,
        rx_post_quantize=False,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_sync=True,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
    )

    def fail_run_command(*_args, **_kwargs):
        raise AssertionError("dry-run local codec should not spawn AnalogLatentLink subprocesses")

    monkeypatch.setattr(analog_batch, "run_command", fail_run_command)

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert (image.image_dir / "tx_analog.sc16").is_file()
    assert (image.image_dir / "decode_summary.json").is_file()
    assert (image.image_dir / "merged_round0.bin").is_file()


def test_tx_control_file_path_maps_workspace_path_to_container_mount(tmp_path):
    repo_root = tmp_path / "repo"
    tx_file = repo_root / "USRP292x" / "analog_latent_runs" / "run1" / "image_0000" / "tx_analog.sc16"

    mapped = analog_batch.translate_tx_control_file_path(tx_file, str(repo_root), "/host_workspace")

    assert mapped == "/host_workspace/USRP292x/analog_latent_runs/run1/image_0000/tx_analog.sc16"


def test_ssh_base_args_uses_docker_runner_when_requested(monkeypatch):
    monkeypatch.setenv("OPENAMP_SSH_RUNNER", "docker")
    monkeypatch.setenv("OPENAMP_SSH_DOCKER_IMAGE", "iccomp-usrp-tx:latest")

    args = analog_batch._ssh_base_args(timeout=30)

    assert args[:6] == ["docker", "run", "--rm", "-i", "-e", "SSHPASS"]
    assert "iccomp-usrp-tx:latest" in args
    assert "LogLevel=ERROR" in args
    assert args[-4:] == ["-o", "ConnectTimeout=30", "-o", "PreferredAuthentications=password,keyboard-interactive"]


def test_ssh_base_args_uses_stable_password_options_for_local_runner(monkeypatch):
    monkeypatch.delenv("OPENAMP_SSH_RUNNER", raising=False)
    monkeypatch.setenv("SSHPASS", "demo-pass")

    args = analog_batch._ssh_base_args(timeout=30)

    assert args[:3] == ["sshpass", "-e", "ssh"]
    assert "StrictHostKeyChecking=no" in args
    assert "UserKnownHostsFile=/dev/null" in args
    assert "LogLevel=ERROR" in args
    assert "BatchMode=no" in args
    assert "ConnectTimeout=30" in args
    assert "PreferredAuthentications=password,keyboard-interactive" in args


def test_ssh_start_control_master_skips_docker_runner(monkeypatch):
    monkeypatch.setenv("OPENAMP_SSH_RUNNER", "docker")

    result = analog_batch._ssh_start_control_master("user@board")

    assert result is None


def test_ssh_start_control_master_honors_disable_env(monkeypatch):
    monkeypatch.delenv("OPENAMP_SSH_RUNNER", raising=False)
    monkeypatch.setenv("SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER", "1")

    def fail_popen(*_args, **_kwargs):
        raise AssertionError("ControlMaster must not start when disabled")

    monkeypatch.setattr(analog_batch.subprocess, "Popen", fail_popen)

    result = analog_batch._ssh_start_control_master("user@board")

    assert result is None


def test_remote_analog_decode_args_sets_pythonpath_for_board_layout(monkeypatch):
    monkeypatch.setenv("REMOTE_USRP_PROJECT_ROOT", "/home/user")
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        tx_delay_sec=0.010,
        rate=5_000_000.0,
        sps=16,
        zero_guard_samples=4096,
        cfo_pilot_symbols=1024,
        sync_search_window_symbols=4096,
    )

    argv = analog_batch.remote_analog_decode_args(
        args,
        "/tmp/run/batch_rx.sc16",
        "/tmp/run/manifest.json",
        "/tmp/run/received_latent.npz",
        "/tmp/run/merged_round0.bin",
        "/tmp/run/decode_summary.json",
    )

    assert argv[:4] == [
        "env",
        "PYTHONPATH=/home/user/scripts:/home/user",
        "/home/user/venv/bin/python",
        "/home/user/USRP292x/AnalogLatentLink.py",
    ]
    assert "--sync-search-center-symbol" not in argv
    assert "--sync-search-window-symbols" in argv
    assert argv.count("--sync-search-window-symbols") == 1
    window_index = argv.index("--sync-search-window-symbols") + 1
    assert argv[window_index] == "4096"


def test_remote_analog_decode_request_carries_fast_first_sync_profile(monkeypatch):
    monkeypatch.setenv("REMOTE_USRP_PROJECT_ROOT", "/home/user")
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=False,
        sync_search_window_symbols=4096,
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        dry_run=False,
    )

    request = analog_batch.remote_analog_decode_request(
        args,
        "/tmp/run/batch_rx.sc16",
        "/tmp/run/manifest.json",
        "/tmp/run/received_latent.npz",
        "/tmp/run/merged_round0.bin",
        "/tmp/run/decode_summary.json",
    )

    assert request["sync_profile"] == "fast-first"
    assert request["fast_sync_candidates"] == 4
    assert request["fast_sync_search_window_symbols"] == 1024
    assert request["fallback_sync_candidates"] == 12
    assert request["fallback_sync_search_window_symbols"] == 4096


def test_remote_analog_decode_request_can_request_minimal_worker_response(monkeypatch):
    monkeypatch.setenv("ANALOG_REMOTE_DECODE_RESPONSE_MODE", "minimal")
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=False,
        sync_search_window_symbols=4096,
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        dry_run=False,
    )

    request = analog_batch.remote_analog_decode_request(
        args,
        "/tmp/run/batch_rx.sc16",
        "/tmp/run/manifest.json",
        "/tmp/run/received_latent.npz",
        "/tmp/run/merged_round0.bin",
        "/tmp/run/decode_summary.json",
    )

    assert request["response_mode"] == "minimal"


def test_decode_worker_minimal_response_keeps_runner_summary_fields():
    summary = {
        "status": "ok",
        "sync_success": True,
        "frame_complete": True,
        "sync_metric": 0.91,
        "estimated_cfo_hz": 12.5,
        "detected_airtime_ms": 9.5,
        "evm_rms": 0.02,
        "estimated_snr_db": 31.0,
        "rx_clipping_ratio": 0.0,
        "decode_total_ms": 41.2,
        "decode_timing_ms": {"write_npz": 1.5},
        "debug_large_array": list(range(128)),
    }

    response = analog.decode_worker_response(summary, "/tmp/run/decode_summary.json", mode="minimal")

    assert response["status"] == "ok"
    assert response["summary_json"] == "/tmp/run/decode_summary.json"
    assert response["sync_metric"] == 0.91
    assert response["estimated_cfo_hz"] == 12.5
    assert response["summary"] == {
        "status": "ok",
        "sync_success": True,
        "frame_complete": True,
        "sync_metric": 0.91,
        "estimated_cfo_hz": 12.5,
        "detected_airtime_ms": 9.5,
        "evm_rms": 0.02,
        "estimated_snr_db": 31.0,
        "rx_clipping_ratio": 0.0,
        "decode_total_ms": 41.2,
        "decode_timing_ms": {"write_npz": 1.5},
    }


def test_remote_analog_decode_request_enables_low_sync_retry_only_before_final_attempt(monkeypatch):
    monkeypatch.setenv("REMOTE_USRP_PROJECT_ROOT", "/home/user")
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=False,
        sync_search_window_symbols=4096,
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        retry_on_burst_miss=False,
        retry_on_low_sync=True,
        low_sync_retry_threshold=0.08,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        dry_run=False,
    )

    first_request = analog_batch.remote_analog_decode_request(
        args,
        "/tmp/run/batch_rx.sc16",
        "/tmp/run/manifest.json",
        "/tmp/run/received_latent.npz",
        "/tmp/run/merged_round0.bin",
        "/tmp/run/decode_summary.json",
        attempt_index=0,
        max_attempts=2,
    )
    final_request = analog_batch.remote_analog_decode_request(
        args,
        "/tmp/run/batch_rx.sc16",
        "/tmp/run/manifest.json",
        "/tmp/run/received_latent.npz",
        "/tmp/run/merged_round0.bin",
        "/tmp/run/decode_summary.json",
        attempt_index=1,
        max_attempts=2,
    )

    assert first_request["retry_on_low_sync"] is True
    assert first_request["low_sync_retry_threshold"] == 0.08
    assert final_request["retry_on_low_sync"] is False
    assert final_request["low_sync_retry_threshold"] == 0.08


def test_analog_decode_args_carries_fast_first_sync_profile():
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=False,
        sync_search_window_symbols=4096,
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
    )

    argv = analog_batch.analog_decode_args(
        args,
        Path("/tmp/run/batch_rx.sc16"),
        Path("/tmp/run/manifest.json"),
        Path("/tmp/run/received_latent.npz"),
        Path("/tmp/run/merged_round0.bin"),
        Path("/tmp/run/decode_summary.json"),
    )

    assert "--sync-profile" in argv
    assert argv[argv.index("--sync-profile") + 1] == "fast-first"
    assert "--fast-sync-candidates" in argv
    assert argv[argv.index("--fast-sync-candidates") + 1] == "4"
    assert "--fast-sync-search-window-symbols" in argv
    assert argv[argv.index("--fast-sync-search-window-symbols") + 1] == "1024"
    assert "--fallback-sync-candidates" in argv
    assert argv[argv.index("--fallback-sync-candidates") + 1] == "12"
    assert "--fallback-sync-search-window-symbols" in argv
    assert argv[argv.index("--fallback-sync-search-window-symbols") + 1] == "4096"


def test_analog_decode_args_enables_low_sync_retry_only_before_final_attempt():
    args = Namespace(
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=False,
        sync_search_window_symbols=4096,
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        retry_on_burst_miss=False,
        retry_on_low_sync=True,
        low_sync_retry_threshold=0.08,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
    )

    first_argv = analog_batch.analog_decode_args(
        args,
        Path("/tmp/run/batch_rx.sc16"),
        Path("/tmp/run/manifest.json"),
        Path("/tmp/run/received_latent.npz"),
        Path("/tmp/run/merged_round0.bin"),
        Path("/tmp/run/decode_summary.json"),
        attempt_index=0,
        max_attempts=2,
    )
    final_argv = analog_batch.analog_decode_args(
        args,
        Path("/tmp/run/batch_rx.sc16"),
        Path("/tmp/run/manifest.json"),
        Path("/tmp/run/received_latent.npz"),
        Path("/tmp/run/merged_round0.bin"),
        Path("/tmp/run/decode_summary.json"),
        attempt_index=1,
        max_attempts=2,
    )

    assert "--retry-on-low-sync" in first_argv
    assert first_argv[first_argv.index("--low-sync-retry-threshold") + 1] == "0.08"
    assert "--retry-on-low-sync" not in final_argv
    assert "--low-sync-retry-threshold" in final_argv
    assert final_argv[final_argv.index("--low-sync-retry-threshold") + 1] == "0.08"


def test_cleanup_remote_file_treats_timeout_as_best_effort_failure(tmp_path, monkeypatch):
    def fake_run_external(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["ssh"], timeout=15.0)

    monkeypatch.setattr(analog_batch, "_run_external", fake_run_external)

    ok = analog_batch.cleanup_remote_file(
        "user@board",
        "/tmp/run/batch_rx.sc16",
        tmp_path / "cleanup.log",
    )

    assert ok is False


def test_run_external_timeout_kills_windows_process_tree(tmp_path, monkeypatch):
    class HangingPopen:
        pid = 23456
        returncode = None

        def __init__(self, command, **_kwargs):
            self.args = command

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(self.args, timeout)

        def kill(self):
            self.returncode = -9

    taskkill_calls: list[list[str]] = []

    def fake_taskkill(command, **_kwargs):
        taskkill_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(analog_batch.os, "name", "nt")
    monkeypatch.setattr(analog_batch.subprocess, "Popen", HangingPopen)
    monkeypatch.setattr(analog_batch.subprocess, "run", fake_taskkill)

    try:
        analog_batch._run_external(["ssh", "demo"], tmp_path / "external.log", timeout=1.0)
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("_run_external should raise for checked timeout")

    assert "command failed (124)" in message
    assert "TimeoutExpired: command timed out after 1.0s" in (tmp_path / "external.log").read_text(encoding="utf-8")
    assert taskkill_calls == [["taskkill", "/F", "/T", "/PID", "23456"]]


def test_push_file_to_remote_uses_ssh_stdin_with_docker_runner(tmp_path, monkeypatch):
    source = tmp_path / "tx_analog.sc16"
    source.write_bytes(b"iq")
    completed = subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"OK\n", stderr=b"")
    monkeypatch.setenv("OPENAMP_SSH_RUNNER", "docker")
    monkeypatch.setenv("OPENAMP_SSH_DOCKER_IMAGE", "iccomp-usrp-tx:latest")

    with monkeypatch.context() as m:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed

        m.setattr(analog_batch.subprocess, "run", fake_run)
        analog_batch.push_file_to_remote(
            "user@board",
            source,
            "/tmp/run/tx_analog.sc16",
            tmp_path / "push.log",
        )

    command, kwargs = calls[0]
    assert command[:6] == ["docker", "run", "--rm", "-i", "-e", "SSHPASS"]
    assert command[-2:] == ["user@board", "mkdir -p /tmp/run && cat > /tmp/run/tx_analog.sc16"]
    assert kwargs["input"] == b"iq"
    assert kwargs["shell"] is False


def test_pull_file_from_remote_uses_ssh_stdout_with_docker_runner(tmp_path, monkeypatch):
    destination = tmp_path / "received_latent.npz"
    completed = subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"rx", stderr=b"")
    monkeypatch.setenv("OPENAMP_SSH_RUNNER", "docker")
    monkeypatch.setenv("OPENAMP_SSH_DOCKER_IMAGE", "iccomp-usrp-tx:latest")

    with monkeypatch.context() as m:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return completed

        m.setattr(analog_batch.subprocess, "run", fake_run)
        analog_batch.pull_file_from_remote(
            "user@board",
            "/tmp/run/received_latent.npz",
            destination,
            tmp_path / "pull.log",
        )

    command, kwargs = calls[0]
    assert command[:6] == ["docker", "run", "--rm", "-i", "-e", "SSHPASS"]
    assert command[-2:] == ["user@board", "cat /tmp/run/received_latent.npz"]
    assert kwargs["shell"] is False
    assert destination.read_bytes() == b"rx"


def test_process_image_wait_command_uses_rx_timeout_budget(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    control_lines: list[str] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    analog_batch.process_image(args, image)

    capture_line = next(line for line in control_lines if line.startswith("CAPTURE "))
    capture_parts = dict(part.split("=", 1) for part in capture_line.split() if "=" in part)
    assert float(capture_parts["duration"]) >= 0.3
    assert int(capture_parts["nsamps"]) == 0
    wait_line = next(line for line in control_lines if line.startswith("WAIT timeout="))
    wait_timeout = float(wait_line.split("=", 1)[1])
    assert wait_timeout >= 30.0


def test_process_image_wait_command_can_use_short_rx_wait_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALOG_RX_ARM_STATUS_TIMEOUT_SEC", "0.75")
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    control_calls: list[tuple[str, float]] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_calls.append((line, float(_timeout)))
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    analog_batch.process_image(args, image)

    control_lines = [line for line, _timeout in control_calls]
    wait_line = next(line for line in control_lines if line.startswith("WAIT timeout="))
    wait_timeout = float(wait_line.split("=", 1)[1])
    assert wait_timeout == 0.5
    wait_call_timeout = next(timeout for line, timeout in control_calls if line.startswith("WAIT timeout="))
    assert wait_call_timeout == 1.5
    assert image.records[0]["rx_arm_status_timeout_sec"] == 0.75


def test_process_image_records_rx_server_stage_timings(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True, "decode_total_ms": 42.0}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        if line.startswith("CAPTURE "):
            return (
                "OK busy=1 started=1 done=0 ok=1 job_id=7 target_samps=107584 written_samps=0 "
                "arm_wait_sec=0.012 drain_sec=0.004 stream_cmd_sec=0.006 receive_sec=0.000 "
                "stop_cmd_sec=0.000 stop_wait_sec=0.000 wall_sec=0.000"
            )
        if line.startswith("WAIT "):
            return (
                "OK busy=0 started=1 done=1 ok=1 job_id=7 target_samps=107584 written_samps=107584 "
                "arm_wait_sec=0.012 drain_sec=0.004 stream_cmd_sec=0.006 receive_sec=0.041 "
                "stop_cmd_sec=0.000 stop_wait_sec=0.000 wall_sec=0.052"
            )
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed
    record = image.records[0]
    assert record["rx_server_arm_wait_wall_sec"] == 0.012
    assert record["rx_server_drain_wall_sec"] == 0.004
    assert record["rx_server_stream_cmd_wall_sec"] == 0.006
    assert record["rx_server_receive_wall_sec"] == 0.041
    assert record["rx_server_capture_wall_sec"] == 0.052
    assert record["rx_server_target_samps"] == 107584
    assert record["rx_server_written_samps"] == 107584


@pytest.mark.parametrize(
    "wait_error",
    [
        "control command failed: WAIT timeout=0.500000\nERR_TIMEOUT host=127.0.0.1 port=29220",
        (
            "control command failed: WAIT timeout=0.500000\n"
            "ERR busy=1 started=0 done=0 ok=1 job_id=3099 file=/tmp/image_0218/batch_rx.sc16"
        ),
    ],
)
def test_process_image_stops_rx_after_wait_timeout(tmp_path, monkeypatch, wait_error):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    control_lines: list[str] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line.startswith("WAIT "):
            raise RuntimeError(wait_error)
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is False
    assert any(line == "STOP" for line in control_lines)
    assert control_lines.index("STOP") > next(i for i, line in enumerate(control_lines) if line.startswith("WAIT "))


def test_process_image_records_rx_stop_timing_after_wait_timeout(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        if line.startswith("WAIT "):
            raise RuntimeError(
                "control command failed: WAIT timeout=0.500000\n"
                "ERR busy=1 started=1 done=0 ok=1 job_id=9 target_samps=107584 written_samps=47553 "
                "receive_sec=0.501 stop_cmd_sec=0.000 stop_wait_sec=0.000 wall_sec=0.000"
            )
        if line == "STOP":
            return (
                "OK busy=0 started=1 done=1 ok=0 job_id=9 target_samps=107584 written_samps=47553 "
                "stop_cmd_sec=0.003 stop_wait_sec=0.208 wall_sec=0.716"
            )
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert not result.passed
    record = image.records[0]
    assert record["rx_server_receive_wall_sec"] == 0.501
    assert record["rx_server_stop_cmd_wall_sec"] == 0.003
    assert record["rx_server_stop_wait_wall_sec"] == 0.208
    assert record["rx_server_written_samps"] == 47553


def test_stop_rx_capture_allows_full_drain_budget(tmp_path, monkeypatch):
    args = Namespace(
        rx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
    )
    timeouts: list[float] = []

    def fake_run_control(_host, _port, line, _log_path, timeout):
        timeouts.append(timeout)
        assert line == "STOP"
        return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.004 stop_wait_sec=7.800 wall_sec=7.804"

    monkeypatch.setenv("ANALOG_RX_STOP_DRAIN_TIMEOUT_SEC", "8.0")
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    response = analog_batch.stop_rx_capture(args, tmp_path / "rx_stop.log")

    assert "stop_wait_sec=7.800" in response
    assert timeouts == pytest.approx([8.5])


def test_process_image_waits_for_rx_started_before_tx(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    control_lines: list[str] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line.startswith("CAPTURE "):
            return "OK busy=1 started=0 done=0 ok=1 job_id=1"
        if line == "STATUS":
            return "OK busy=1 started=1 done=0 ok=1 job_id=1"
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert control_lines.index("STATUS") < next(i for i, line in enumerate(control_lines) if line.startswith("SEND "))


def test_wait_for_rx_capture_armed_falls_back_after_sent_session_status_timeout(tmp_path, monkeypatch):
    args = Namespace(
        rx_arm_status_timeout_sec=0.2,
        rx_arm_status_poll_sec=0.001,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
    )
    events: list[str] = []

    class FlakySession:
        def command(self, line, log_path, _timeout):
            events.append(f"session:{line}")
            log_path.write_text("session timeout\n", encoding="utf-8")
            raise analog_batch.ControlSessionUnavailable("timed out", command_sent=True)

        def close(self):
            events.append("session:close")

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line}")
        log_path.write_text("OK busy=1 started=1 done=0 ok=1 job_id=42\n", encoding="utf-8")
        return "OK busy=1 started=1 done=0 ok=1 job_id=42"

    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    response = analog_batch.wait_for_rx_capture_armed(
        args,
        "OK busy=1 started=0 done=0 ok=1 job_id=42",
        tmp_path / "rx_arm_status.log",
        30.0,
        session=FlakySession(),
    )

    assert "started=1" in response
    assert "session:STATUS" in events
    assert "session:close" in events
    assert "direct:STATUS" in events


def test_process_image_stops_rx_when_arm_status_times_out_before_tx(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    control_lines: list[str] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line.startswith("CAPTURE "):
            return "OK busy=1 started=0 done=0 ok=1 job_id=1"
        if line == "STATUS":
            raise RuntimeError("control command failed: STATUS\nERR_TIMEOUT host=board port=29220")
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is False
    assert any(line == "STOP" for line in control_lines)
    assert not any(line.startswith("SEND ") for line in control_lines)


def test_pipeline_capture_attempt_stops_rx_after_capture_busy(tmp_path, monkeypatch):
    image = analog_batch.ImageRecord(index=218, input_path=tmp_path / "case218.bin", image_dir=tmp_path / "image_0218")
    image.input_path.write_bytes(b"payload")
    args = Namespace(
        remote_rx_ssh_target="user@board",
        ssh_control_socket="",
        in_process_local_codec=True,
        remote_cleanup_mode="skip",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/test_rx",
        remote_decode_worker=object(),
        run_id="capture-busy",
        remote_rx_run_root="/tmp/usrp292x_remote_runs",
        tx_delay_sec=0.0,
        rate=5_000_000.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        preconnect_control=False,
        rx_session_control=False,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        tx_timeout_sec=30.0,
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
    )
    control_lines: list[str] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 67888, "job_id": "case218"}), encoding="utf-8")
        return {"capture_nsamps": 67888, "job_id": "case218"}

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line.startswith("CAPTURE "):
            raise RuntimeError("control command failed: CAPTURE file=/tmp/image_0218/batch_rx.sc16\nERR error=capture_already_running")
        return "OK"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    with pytest.raises(RuntimeError, match="capture_already_running"):
        analog_batch._capture_remote_decode_pipeline_attempt(
            args,
            image,
            attempt_index=0,
            max_attempts=3,
            slot_index=0,
            pipeline_depth=2,
        )

    assert any(line == "STOP" for line in control_lines)
    assert control_lines.index("STOP") > next(i for i, line in enumerate(control_lines) if line.startswith("CAPTURE "))


def test_pipeline_session_capture_arm_failure_closes_session_before_stop(tmp_path, monkeypatch):
    image = analog_batch.ImageRecord(index=150, input_path=tmp_path / "case150.bin", image_dir=tmp_path / "image_0150")
    image.input_path.write_bytes(b"payload")
    args = Namespace(
        remote_rx_ssh_target="user@board",
        ssh_control_socket="",
        in_process_local_codec=True,
        remote_cleanup_mode="skip",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/test_rx",
        remote_decode_worker=object(),
        run_id="session-arm-fail",
        remote_rx_run_root="/tmp/usrp292x_remote_runs",
        tx_delay_sec=0.0,
        rate=5_000_000.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        rx_arm_status_timeout_sec=0.01,
        rx_arm_status_poll_sec=0.001,
        preconnect_control=False,
        preconnect_rx_capture_control=False,
        rx_session_control=True,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        tx_timeout_sec=30.0,
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
    )
    events: list[str] = []

    class FakeSession:
        def command(self, line, log_path, _timeout):
            events.append(f"session:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            if line.startswith("CAPTURE "):
                return "OK busy=1 started=0 done=0 ok=1 job_id=150"
            if line == "STATUS":
                return "OK busy=1 started=0 done=0 ok=1 job_id=150"
            return "OK"

        def close(self):
            events.append("close:session")

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 67888, "job_id": "case150"}), encoding="utf-8")
        return {"capture_nsamps": 67888, "job_id": "case150"}

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        return "OK busy=0 started=0 done=1 ok=0 error=stopped"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "open_control_session", lambda *_args: FakeSession())
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    with pytest.raises(RuntimeError, match="RX CAPTURE did not arm before TX"):
        analog_batch._capture_remote_decode_pipeline_attempt(
            args,
            image,
            attempt_index=0,
            max_attempts=3,
            slot_index=0,
            pipeline_depth=1,
        )

    assert "close:session" in events
    assert "direct:STOP" in events
    assert events.index("close:session") < events.index("direct:STOP")


def test_pipeline_session_wait_timeout_closes_session_before_stop(tmp_path, monkeypatch):
    image = analog_batch.ImageRecord(index=196, input_path=tmp_path / "case196.bin", image_dir=tmp_path / "image_0196")
    image.input_path.write_bytes(b"payload")
    args = Namespace(
        remote_rx_ssh_target="user@board",
        ssh_control_socket="",
        in_process_local_codec=True,
        remote_cleanup_mode="skip",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/test_rx",
        remote_decode_worker=object(),
        run_id="session-wait-fail",
        remote_rx_run_root="/tmp/usrp292x_remote_runs",
        tx_delay_sec=0.0,
        rate=5_000_000.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        preconnect_control=False,
        preconnect_rx_capture_control=False,
        rx_session_control=True,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        tx_timeout_sec=30.0,
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
    )
    events: list[str] = []

    class FakeSession:
        def command(self, line, log_path, _timeout):
            events.append(f"session:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            if line.startswith("WAIT "):
                raise RuntimeError(
                    "control command failed: WAIT timeout=0.500000\n"
                    "ERR busy=1 started=1 done=0 ok=1 job_id=196 target_samps=67888 written_samps=58000"
                )
            return "OK busy=1 started=1 done=0 ok=1 job_id=196"

        def close(self):
            events.append("close:session")

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 67888, "job_id": "case196"}), encoding="utf-8")
        return {"capture_nsamps": 67888, "job_id": "case196"}

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.003 stop_wait_sec=0.208 wall_sec=0.211"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "open_control_session", lambda *_args: FakeSession())
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    with pytest.raises(RuntimeError, match="WAIT timeout"):
        analog_batch._capture_remote_decode_pipeline_attempt(
            args,
            image,
            attempt_index=0,
            max_attempts=3,
            slot_index=0,
            pipeline_depth=1,
        )

    assert "close:session" in events
    assert "direct:STOP" in events
    assert events.index("close:session") < events.index("direct:STOP")


def test_stop_rx_capture_polls_status_until_idle(tmp_path, monkeypatch):
    args = Namespace(rx_control_host="127.0.0.1", rx_control_port=29220, rx_timeout_sec=30.0)
    control_lines: list[str] = []
    status_responses = ["OK busy=1 started=1 done=0 ok=1", "OK busy=0 started=1 done=1 ok=0 error=stopped"]

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line == "STOP":
            return "OK busy=1 started=1 done=0 ok=1"
        if line == "STATUS":
            return status_responses.pop(0)
        return "OK"

    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    analog_batch.stop_rx_capture(args, tmp_path / "stop.log")

    assert control_lines == ["STOP", "STATUS", "STATUS"]


def test_control_session_close_shutdowns_socket_before_close(monkeypatch):
    events: list[tuple[str, object | None]] = []

    class FakeSocket:
        def settimeout(self, _timeout):
            pass

        def shutdown(self, how):
            events.append(("shutdown", how))

        def close(self):
            events.append(("close", None))

    monkeypatch.setattr(analog_batch.socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())

    session = analog_batch.ControlSession("127.0.0.1", 29220, 1.0)
    session.close()

    assert events == [("shutdown", analog_batch.socket.SHUT_RDWR), ("close", None)]


def test_control_session_close_still_closes_when_shutdown_fails(monkeypatch):
    events: list[str] = []

    class FakeSocket:
        def settimeout(self, _timeout):
            pass

        def shutdown(self, _how):
            events.append("shutdown")
            raise OSError("already closed")

        def close(self):
            events.append("close")

    monkeypatch.setattr(analog_batch.socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())

    session = analog_batch.ControlSession("127.0.0.1", 29220, 1.0)
    session.close()

    assert events == ["shutdown", "close"]


def test_process_image_preconnects_tx_and_wait_control(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class FakePreconnected:
        def __init__(self, label: str):
            self.label = label

        def command(self, line, log_path, timeout):
            del timeout
            events.append(f"preconnected:{self.label}:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            return "OK"

        def close(self):
            events.append(f"close:{self.label}")

    def fake_preconnect(_host, port, _timeout):
        label = "rx" if int(port) == 29220 else "tx"
        events.append(f"preconnect:{label}")
        return FakePreconnected(label)

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        events.append("make")
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        events.append("decode")
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        return "OK"

    monkeypatch.setattr(analog_batch, "preconnect_control", fake_preconnect)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed
    assert "direct:CAPTURE" in events
    assert "direct:SEND" not in events
    assert "direct:WAIT" not in events
    assert events.index("preconnect:tx") < events.index("direct:CAPTURE")
    assert events.index("direct:CAPTURE") < events.index("preconnect:rx")
    assert events.index("preconnect:rx") < events.index("preconnected:tx:SEND")
    assert events.index("preconnected:tx:SEND") < events.index("preconnected:rx:WAIT")


def test_process_image_can_preconnect_rx_capture_control(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=True,
        preconnect_rx_capture_control=True,
        rx_session_control=False,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class FakePreconnected:
        def __init__(self, label: str):
            self.label = label

        def command(self, line, log_path, timeout):
            del timeout
            events.append(f"preconnected:{self.label}:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            return "OK"

        def close(self):
            events.append(f"close:{self.label}")

    def fake_preconnect(_host, port, _timeout):
        label = "rx" if int(port) == 29220 else "tx"
        events.append(f"preconnect:{label}")
        return FakePreconnected(label)

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        events.append("make")
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        return "OK"

    monkeypatch.setattr(analog_batch, "preconnect_control", fake_preconnect)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed
    assert events.index("preconnect:rx") < events.index("make")
    assert "preconnected:rx:CAPTURE" in events
    assert "direct:CAPTURE" not in events
    assert image.records[0]["rx_capture_preconnect_enabled"] is True


def test_process_image_reuses_rx_control_session_for_capture_and_wait(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=False,
        rx_session_control=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class FakeSession:
        def command(self, line, log_path, timeout):
            del timeout
            events.append(f"session:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            return "OK"

        def close(self):
            events.append("session:close")

    def fake_open_session(_host, _port, _timeout):
        events.append("session:open")
        return FakeSession()

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        return "OK"

    monkeypatch.setattr(analog_batch, "open_control_session", fake_open_session)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed
    assert "session:CAPTURE" in events
    assert "session:WAIT" in events
    assert "direct:CAPTURE" not in events
    assert "direct:WAIT" not in events
    assert "direct:SEND" in events
    assert events.index("session:CAPTURE") < events.index("direct:SEND")
    assert events.index("direct:SEND") < events.index("session:WAIT")


def test_process_image_reuses_shared_rx_control_session_across_images(tmp_path, monkeypatch):
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=False,
        rx_session_control=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class SharedSession:
        def command(self, line, log_path, timeout):
            del timeout
            events.append(f"shared:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            return "OK"

        def close(self):
            events.append("shared:close")

    shared_session = SharedSession()
    args.rx_control_session = shared_session

    def fail_open_session(*_args, **_kwargs):
        raise AssertionError("process_image should use the shared RX control session")

    def fake_make(_args, image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": f"case{image.index}"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": True}), encoding="utf-8")
        return 0

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        return "OK"

    monkeypatch.setattr(analog_batch, "open_control_session", fail_open_session)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    image_a = analog_batch.ImageRecord(index=0, input_path=tmp_path / "case0.bin", image_dir=tmp_path / "image_0000")
    image_b = analog_batch.ImageRecord(index=1, input_path=tmp_path / "case1.bin", image_dir=tmp_path / "image_0001")
    image_a.input_path.write_bytes(b"payload")
    image_b.input_path.write_bytes(b"payload")

    assert analog_batch.process_image(args, image_a).passed
    assert analog_batch.process_image(args, image_b).passed

    assert events.count("shared:CAPTURE") == 2
    assert events.count("shared:WAIT") == 2
    assert "shared:close" not in events
    assert getattr(args, "rx_control_session") is shared_session


def test_process_image_session_wait_timeout_closes_session_before_stop(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=False,
        rx_session_control=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class FakeSession:
        def command(self, line, log_path, _timeout):
            events.append(f"session:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            if line.startswith("WAIT "):
                raise RuntimeError(
                    "control command failed: WAIT timeout=0.500000\n"
                    "ERR busy=1 started=1 done=0 ok=1 job_id=9 target_samps=107584 written_samps=47553 "
                    "receive_sec=0.501 wall_sec=0.000"
                )
            return "OK busy=1 started=1 done=0 ok=1 job_id=9"

        def close(self):
            events.append("close:session")

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        if line == "STOP":
            return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.003 stop_wait_sec=0.208 wall_sec=0.211"
        return "OK"

    monkeypatch.setattr(analog_batch, "open_control_session", lambda *_args: FakeSession())
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert not result.passed
    assert "close:session" in events
    assert "direct:STOP" in events
    assert events.index("close:session") < events.index("direct:STOP")


def test_process_image_shared_session_wait_timeout_clears_batch_session(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=False,
        rx_session_control=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class SharedSession:
        def command(self, line, log_path, _timeout):
            events.append(f"shared:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            if line.startswith("WAIT "):
                raise RuntimeError(
                    "control command failed: WAIT timeout=0.500000\n"
                    "ERR busy=1 started=1 done=0 ok=1 job_id=9 target_samps=107584 written_samps=47553 "
                    "receive_sec=0.501 wall_sec=0.000"
                )
            return "OK busy=1 started=1 done=0 ok=1 job_id=9"

        def close(self):
            events.append("shared:close")

    shared_session = SharedSession()
    args.rx_control_session = shared_session

    def fail_open_session(*_args, **_kwargs):
        raise AssertionError("process_image should use the shared RX control session")

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        if line == "STOP":
            return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.003 stop_wait_sec=0.208 wall_sec=0.211"
        return "OK"

    monkeypatch.setattr(analog_batch, "open_control_session", fail_open_session)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert not result.passed
    assert "shared:close" in events
    assert "direct:STOP" in events
    assert events.index("shared:close") < events.index("direct:STOP")
    assert getattr(args, "rx_control_session", None) is None


def test_process_image_shared_session_decode_failure_closes_before_stop(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        preconnect_control=False,
        rx_session_control=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    events: list[str] = []

    class SharedSession:
        def command(self, line, log_path, _timeout):
            events.append(f"shared:{line.split()[0]}")
            log_path.write_text("OK\n", encoding="utf-8")
            return "OK busy=1 started=1 done=1 ok=1 job_id=0"

        def close(self):
            events.append("shared:close")

    shared_session = SharedSession()
    args.rx_control_session = shared_session

    def fail_open_session(*_args, **_kwargs):
        raise AssertionError("process_image should use the shared RX control session")

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, _out_wire, summary, _log_path):
        summary.write_text(json.dumps({"payload_is_bit_exact": False}), encoding="utf-8")
        return 1

    def fake_run_control(_host, _port, line, log_path, _timeout):
        events.append(f"direct:{line.split()[0]}")
        log_path.write_text("OK\n", encoding="utf-8")
        if line == "STOP":
            return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.003 stop_wait_sec=0.208 wall_sec=0.211"
        return "OK"

    monkeypatch.setattr(analog_batch, "open_control_session", fail_open_session)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert not result.passed
    assert "shared:close" in events
    assert "direct:STOP" in events
    assert events.index("shared:close") < events.index("direct:STOP")
    assert getattr(args, "rx_control_session", None) is None


def test_process_image_remote_pull_avoids_unneeded_remote_staging_commands(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-pull",
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    pushed: list[str] = []
    pulled: list[str] = []
    cleaned_batches: list[list[str]] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": False}), encoding="utf-8")
        return 0

    def fake_run_remote_command(_target, remote_argv, _log_path, **_kwargs):
        raise AssertionError(f"remote-pull should not run SSH setup commands: {remote_argv}")

    def fake_push_file_to_remote(_target, _local_path, remote_path, _log_path, **_kwargs):
        pushed.append(remote_path)

    def fake_pull_file_from_remote(_target, remote_path, local_path, _log_path, **_kwargs):
        pulled.append(remote_path)
        local_path.write_bytes(b"rx")

    def fake_cleanup_remote_file(_target, remote_path, _log_path, **_kwargs):
        raise AssertionError(f"remote-pull should batch cleanup, got {remote_path}")

    def fake_cleanup_remote_files(_target, remote_paths, _log_path, **_kwargs):
        cleaned_batches.append(list(remote_paths))
        return True

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_remote_command", fake_run_remote_command)
    monkeypatch.setattr(analog_batch, "push_file_to_remote", fake_push_file_to_remote)
    monkeypatch.setattr(analog_batch, "pull_file_from_remote", fake_pull_file_from_remote)
    monkeypatch.setattr(analog_batch, "cleanup_remote_file", fake_cleanup_remote_file)
    monkeypatch.setattr(analog_batch, "cleanup_remote_files", fake_cleanup_remote_files)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert pushed == []
    assert pulled == ["/tmp/analog_runs/run42/image_0000/batch_rx.sc16"]
    assert cleaned_batches == [["/tmp/analog_runs/run42/image_0000/batch_rx.sc16"]]
    record = result.records[0]
    assert record["rx_pull_wall_sec"] >= 0.0
    assert record["remote_cleanup_wall_sec"] >= 0.0


def test_transport_metrics_break_out_remote_pull_and_cleanup_wall_time(tmp_path):
    image = analog_batch.ImageRecord(
        index=0,
        input_path=tmp_path / "case0.bin",
        image_dir=tmp_path / "image_0000",
    )
    image.records.append(
        {
            "total_wall_sec": 10.0,
            "detected_airtime_ms": 100.0,
            "decode_wall_sec": 2.0,
            "merge_wall_sec": 0.3,
            "rx_pull_wall_sec": 3.0,
            "remote_cleanup_wall_sec": 0.7,
        }
    )

    metrics = analog_batch.build_transport_metrics([image])

    assert metrics["rx_pull_wall_sec_mean"] == 3.0
    assert metrics["remote_cleanup_wall_sec_mean"] == 0.7
    assert abs(metrics["estimated_non_airtime_non_decode_non_merge_wall_sec_mean"] - 3.9) < 1e-9


def test_iq_stage_benchmark_aggregates_runner_records(tmp_path):
    image_a = analog_batch.ImageRecord(
        index=0,
        input_path=tmp_path / "case0.bin",
        image_dir=tmp_path / "image_0000",
    )
    image_b = analog_batch.ImageRecord(
        index=1,
        input_path=tmp_path / "case1.bin",
        image_dir=tmp_path / "image_0001",
    )
    image_a.records.append(
        {
            "tx_wall_sec": 0.010,
            "rx_arm_wall_sec": 0.003,
            "rx_session_open_wall_sec": 0.001,
            "rx_capture_command_wall_sec": 0.002,
            "rx_capture_wall_sec": 0.030,
            "rx_wait_wall_sec": 0.017,
            "rx_server_arm_wait_wall_sec": 0.002,
            "rx_server_drain_wall_sec": 0.004,
            "rx_server_stream_cmd_wall_sec": 0.006,
            "rx_server_receive_wall_sec": 0.020,
            "rx_server_capture_wall_sec": 0.026,
            "rx_server_stop_cmd_wall_sec": 0.0,
            "rx_server_stop_wait_wall_sec": 0.0,
            "decode_wall_sec": 0.060,
            "remote_decode_reported_wall_sec": 0.041,
            "remote_decode_timing_ms": {
                "matched_filter": 2.0,
                "initial_sync": 8.0,
                "cfo_estimate": 3.0,
                "payload_recovery": 20.0,
                "write_npz": 1.5,
            },
            "remote_decode_restart_wall_sec": 0.0,
            "decode_queue_wall_sec": 0.005,
            "remote_dir_publish_wall_sec": 0.004,
            "retry_wait_wall_sec": 0.0,
            "total_wall_sec": 0.120,
        }
    )
    image_b.records.append(
        {
            "tx_wall_sec": 0.020,
            "rx_arm_wall_sec": 0.005,
            "rx_session_open_wall_sec": 0.002,
            "rx_capture_command_wall_sec": 0.003,
            "rx_capture_wall_sec": 0.050,
            "rx_wait_wall_sec": 0.055,
            "rx_server_arm_wait_wall_sec": 0.004,
            "rx_server_drain_wall_sec": 0.006,
            "rx_server_stream_cmd_wall_sec": 0.010,
            "rx_server_receive_wall_sec": 0.034,
            "rx_server_capture_wall_sec": 0.046,
            "rx_server_stop_cmd_wall_sec": 0.003,
            "rx_server_stop_wait_wall_sec": 0.012,
            "decode_wall_sec": 0.080,
            "remote_decode_reported_wall_sec": 0.043,
            "remote_decode_timing_ms": {
                "matched_filter": 4.0,
                "initial_sync": 12.0,
                "cfo_estimate": 5.0,
                "payload_recovery": 32.0,
                "write_npz": 2.5,
            },
            "remote_decode_restart_wall_sec": 0.030,
            "decode_queue_wall_sec": 0.015,
            "remote_dir_publish_wall_sec": 0.006,
            "retry_wait_wall_sec": 0.020,
            "total_wall_sec": 0.180,
        }
    )

    benchmark = analog_batch.build_iq_stage_benchmark([image_a, image_b])

    assert benchmark["tx_control_ms"]["median_ms"] == 15.0
    assert benchmark["rx_arm_ms"]["median_ms"] == 4.0
    assert benchmark["rx_session_open_ms"]["median_ms"] == 1.5
    assert benchmark["rx_capture_command_ms"]["median_ms"] == 2.5
    assert benchmark["rx_capture_ms"]["p95_ms"] == 50.0
    assert benchmark["rx_wait_ms"]["median_ms"] == 36.0
    assert benchmark["rx_server_arm_wait_ms"]["median_ms"] == 3.0
    assert benchmark["rx_server_drain_ms"]["median_ms"] == 5.0
    assert benchmark["rx_server_stream_cmd_ms"]["median_ms"] == 8.0
    assert benchmark["rx_server_receive_ms"]["median_ms"] == 27.0
    assert benchmark["rx_server_capture_ms"]["median_ms"] == 36.0
    assert benchmark["rx_arm_control_overhead_ms"]["median_ms"] == 1.0
    assert benchmark["rx_post_arm_to_wait_ms"]["median_ms"] == 5.0
    assert benchmark["rx_wait_response_overhead_ms"]["median_ms"] == 5.0
    assert benchmark["rx_wait_response_overhead_ms"]["p95_ms"] == 9.0
    assert benchmark["rx_capture_control_overhead_ms"]["median_ms"] == 4.0
    assert "rx_wait_minus_server_receive_ms" not in benchmark
    assert benchmark["rx_server_stop_cmd_ms"]["max_ms"] == 3.0
    assert benchmark["rx_server_stop_wait_ms"]["max_ms"] == 12.0
    assert benchmark["remote_decode_ms"]["mean_ms"] == 70.0
    assert benchmark["remote_decode_reported_ms"]["median_ms"] == 42.0
    assert benchmark["remote_decode_matched_filter_ms"]["median_ms"] == 3.0
    assert benchmark["remote_decode_initial_sync_ms"]["p95_ms"] == 12.0
    assert benchmark["remote_decode_cfo_estimate_ms"]["median_ms"] == 4.0
    assert benchmark["remote_decode_payload_recovery_ms"]["median_ms"] == 26.0
    assert benchmark["remote_decode_write_npz_ms"]["max_ms"] == 2.5
    assert benchmark["remote_decode_restart_ms"]["max_ms"] == 30.0
    assert benchmark["remote_decode_response_overhead_ms"]["median_ms"] == 23.0
    assert benchmark["remote_decode_queue_ms"]["median_ms"] == 10.0
    assert benchmark["remote_dir_publish_ms"]["median_ms"] == 5.0
    assert benchmark["retry_wait_ms"]["max_ms"] == 20.0
    assert benchmark["total_transport_ms"]["median_ms"] == 150.0


def test_iq_stage_benchmark_skips_derived_metrics_without_complete_inputs(tmp_path):
    image = analog_batch.ImageRecord(
        index=0,
        input_path=tmp_path / "case0.bin",
        image_dir=tmp_path / "image_0000",
    )
    image.records.append(
        {
            "rx_capture_wall_sec": 0.120,
            "rx_wait_wall_sec": 0.080,
            "decode_wall_sec": 0.090,
            "remote_decode_reported_wall_sec": 0.040,
        }
    )

    benchmark = analog_batch.build_iq_stage_benchmark([image])

    assert "rx_capture_ms" in benchmark
    assert "remote_decode_ms" in benchmark
    assert "rx_capture_control_overhead_ms" not in benchmark
    assert "rx_arm_control_overhead_ms" not in benchmark
    assert "rx_session_open_ms" not in benchmark
    assert "rx_capture_command_ms" not in benchmark
    assert "rx_post_arm_to_wait_ms" not in benchmark
    assert "rx_wait_response_overhead_ms" not in benchmark
    assert "rx_wait_minus_server_receive_ms" not in benchmark
    assert "remote_decode_response_overhead_ms" not in benchmark


def test_iq_stage_benchmark_skips_decode_response_overhead_without_reported_decode(tmp_path):
    image = analog_batch.ImageRecord(
        index=0,
        input_path=tmp_path / "case0.bin",
        image_dir=tmp_path / "image_0000",
    )
    image.records.append(
        {
            "decode_wall_sec": 0.090,
            "remote_decode_reported_wall_sec": 0.0,
            "remote_dir_publish_wall_sec": 0.004,
        }
    )

    benchmark = analog_batch.build_iq_stage_benchmark([image])

    assert benchmark["remote_decode_ms"]["median_ms"] == 90.0
    assert benchmark["remote_decode_reported_ms"]["median_ms"] == 0.0
    assert "remote_decode_response_overhead_ms" not in benchmark


def test_pipeline_error_record_preserves_stage_timings(tmp_path):
    image = analog_batch.ImageRecord(
        index=3,
        input_path=tmp_path / "case3.bin",
        image_dir=tmp_path / "image_0003",
    )
    started = time.monotonic() - 0.25

    analog_batch._append_pipeline_error_record(
        image,
        RuntimeError("decode failed"),
        started=started,
        attempt_index=1,
        max_attempts=3,
        slot_index=0,
        pipeline_depth=2,
        stage_timings={
            "make_wall_sec": 0.010,
            "tx_wall_sec": 0.020,
            "rx_arm_wall_sec": 0.012,
            "rx_capture_wall_sec": 0.090,
            "rx_wait_wall_sec": 0.058,
            "decode_queue_wall_sec": 0.030,
            "decode_wall_sec": 0.110,
            "remote_dir_publish_wall_sec": 0.0,
        },
    )

    record = image.records[0]
    assert record["attempt"] == 2
    assert record["error"] == "decode failed"
    assert record["rx_arm_wall_sec"] == 0.012
    assert record["rx_capture_wall_sec"] == 0.090
    assert record["rx_wait_wall_sec"] == 0.058
    assert record["decode_queue_wall_sec"] == 0.030
    assert record["decode_wall_sec"] == 0.110


def test_remote_stall_snapshot_records_board_status_for_slow_record(tmp_path, monkeypatch):
    record = {
        "total_wall_sec": 1.50,
        "rx_wait_wall_sec": 1.20,
        "decode_wall_sec": 0.050,
    }
    args = Namespace(
        remote_stall_snapshot=True,
        remote_stall_snapshot_threshold_sec=1.0,
        remote_stall_snapshot_limit=2,
    )
    launched: list[tuple[list[str], Path]] = []

    class FakePopen:
        pid = 4242

    def fake_popen(argv, **kwargs):
        launched.append((argv, Path(kwargs["stdout"].name)))
        return FakePopen()

    monkeypatch.setattr(analog_batch.subprocess, "Popen", fake_popen)

    captured = analog_batch.maybe_capture_remote_stall_snapshot(
        args,
        record,
        remote_target="user@board",
        image_dir=tmp_path,
        log_name="remote_stall_snapshot.log",
        control_socket="ctrl.sock",
    )

    assert captured is True
    assert launched
    assert "user@board" in launched[0][0]
    assert any("ctrl.sock" in part for part in launched[0][0])
    assert launched[0][1] == tmp_path / "remote_stall_snapshot.log"
    assert record["remote_stall_snapshot_log"] == str(tmp_path / "remote_stall_snapshot.log")
    assert record["remote_stall_snapshot_reason"] == "total_wall_sec,rx_wait_wall_sec"
    assert record["remote_stall_snapshot_async"] is True
    assert record["remote_stall_snapshot_pid"] == 4242
    assert record["remote_stall_snapshot_wall_sec"] >= 0.0
    assert getattr(args, "_remote_stall_snapshots_taken") == 1


def test_remote_stall_snapshot_starts_async_without_waiting_for_ssh(tmp_path, monkeypatch):
    record = {
        "total_wall_sec": 1.50,
        "decode_queue_wall_sec": 1.20,
    }
    args = Namespace(
        remote_stall_snapshot=True,
        remote_stall_snapshot_threshold_sec=1.0,
        remote_stall_snapshot_limit=2,
    )
    launched: list[list[str]] = []

    def fail_sync_snapshot(*_args, **_kwargs):
        raise AssertionError("snapshot must not block on run_remote_command")

    class FakePopen:
        pid = 4242

    def fake_popen(argv, **_kwargs):
        launched.append(argv)
        return FakePopen()

    monkeypatch.setattr(analog_batch, "run_remote_command", fail_sync_snapshot)
    monkeypatch.setattr(analog_batch.subprocess, "Popen", fake_popen)

    captured = analog_batch.maybe_capture_remote_stall_snapshot(
        args,
        record,
        remote_target="user@board",
        image_dir=tmp_path,
        log_name="remote_stall_snapshot.log",
        control_socket="ctrl.sock",
    )

    assert captured is True
    assert launched
    assert record["remote_stall_snapshot_async"] is True
    assert record["remote_stall_snapshot_pid"] == 4242
    assert "remote_stall_snapshot_error" not in record


def test_remote_stall_snapshot_skips_when_disabled_or_under_threshold(tmp_path, monkeypatch):
    args = Namespace(
        remote_stall_snapshot=False,
        remote_stall_snapshot_threshold_sec=1.0,
        remote_stall_snapshot_limit=1,
    )

    def fail_run_remote_command(*_args, **_kwargs):
        raise AssertionError("snapshot should not run")

    monkeypatch.setattr(analog_batch, "run_remote_command", fail_run_remote_command)

    record = {"total_wall_sec": 5.0, "rx_wait_wall_sec": 2.0}
    assert analog_batch.maybe_capture_remote_stall_snapshot(
        args,
        record,
        remote_target="user@board",
        image_dir=tmp_path,
        log_name="remote_stall_snapshot.log",
    ) is False

    args.remote_stall_snapshot = True
    record = {"total_wall_sec": 0.20, "rx_wait_wall_sec": 0.10}
    assert analog_batch.maybe_capture_remote_stall_snapshot(
        args,
        record,
        remote_target="user@board",
        image_dir=tmp_path,
        log_name="remote_stall_snapshot.log",
    ) is False


def test_process_image_remote_pull_can_launch_cleanup_async(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-pull",
        remote_cleanup_mode="async",
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    async_cleaned_batches: list[list[str]] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, out_wire, summary, _log_path):
        out_wire.write_bytes(b"payload")
        summary.write_text(json.dumps({"payload_is_bit_exact": False}), encoding="utf-8")
        return 0

    def fake_cleanup_remote_file(*_args, **_kwargs):
        raise AssertionError("async cleanup must not call blocking cleanup")

    def fake_cleanup_remote_file_async(_target, remote_path, _log_path, **_kwargs):
        raise AssertionError(f"async cleanup should batch paths, got {remote_path}")

    def fake_cleanup_remote_files_async(_target, remote_paths, _log_path, **_kwargs):
        async_cleaned_batches.append(list(remote_paths))
        return True

    def fake_pull_file_from_remote(_target, _remote_path, local_path, _log_path, **_kwargs):
        local_path.write_bytes(b"rx")

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "pull_file_from_remote", fake_pull_file_from_remote)
    monkeypatch.setattr(analog_batch, "cleanup_remote_file", fake_cleanup_remote_file)
    monkeypatch.setattr(analog_batch, "cleanup_remote_file_async", fake_cleanup_remote_file_async, raising=False)
    monkeypatch.setattr(analog_batch, "cleanup_remote_files_async", fake_cleanup_remote_files_async)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert async_cleaned_batches == [["/tmp/analog_runs/run42/image_0000/batch_rx.sc16"]]
    assert result.records[0]["remote_cleanup_mode"] == "async"


def test_process_image_remote_decode_batches_remote_file_operations(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
    )
    remote_commands: list[list[str]] = []
    pushed: list[str] = []
    pulled_batches: list[tuple[str, list[str]]] = []
    cleaned_batches: list[list[str]] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_run_remote_command(_target, remote_argv, _log_path, **_kwargs):
        remote_commands.append(remote_argv)
        return subprocess.CompletedProcess(args=remote_argv, returncode=0, stdout="", stderr="")

    def fake_push_file_to_remote(_target, _local_path, remote_path, _log_path, **_kwargs):
        pushed.append(remote_path)

    def fake_pull_files_from_remote_tar(_target, remote_dir, remote_to_local, _log_path, **_kwargs):
        pulled_batches.append((remote_dir, list(remote_to_local)))
        for remote_name, local_path in remote_to_local.items():
            if remote_name == "decode_summary.json":
                local_path.write_text(json.dumps({"payload_is_bit_exact": False}), encoding="utf-8")
            else:
                local_path.write_bytes(b"payload")

    def fake_cleanup_remote_files(_target, remote_paths, _log_path, **_kwargs):
        cleaned_batches.append(list(remote_paths))
        return True

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_remote_command", fake_run_remote_command)
    monkeypatch.setattr(analog_batch, "push_file_to_remote", fake_push_file_to_remote)
    monkeypatch.setattr(analog_batch, "pull_file_from_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("remote-decode should batch result pulls")))
    monkeypatch.setattr(analog_batch, "pull_files_from_remote_tar", fake_pull_files_from_remote_tar, raising=False)
    monkeypatch.setattr(analog_batch, "cleanup_remote_file", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("remote-decode should batch cleanup")))
    monkeypatch.setattr(analog_batch, "cleanup_remote_file_async", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("remote-decode should batch cleanup")))
    monkeypatch.setattr(analog_batch, "cleanup_remote_files", fake_cleanup_remote_files, raising=False)
    monkeypatch.setattr(analog_batch, "cleanup_remote_files_async", fake_cleanup_remote_files, raising=False)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert not any(command[:2] == ["mkdir", "-p"] for command in remote_commands)
    assert pushed == ["/tmp/analog_runs/run42/image_0000/manifest.json"]
    assert pulled_batches == [
        (
            "/tmp/analog_runs/run42/image_0000",
            ["received_latent.npz", "merged_round0.bin", "decode_summary.json"],
        )
    ]
    assert cleaned_batches == [[
        "/tmp/analog_runs/run42/image_0000/batch_rx.sc16",
        "/tmp/analog_runs/run42/image_0000/manifest.json",
        "/tmp/analog_runs/run42/image_0000/received_latent.npz",
        "/tmp/analog_runs/run42/image_0000/merged_round0.bin",
        "/tmp/analog_runs/run42/image_0000/decode_summary.json",
    ]]


def test_process_image_remote_decode_uses_persistent_worker_when_available(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    worker_requests: list[dict[str, object]] = []
    worker_timeouts: list[float] = []

    class FakeWorker:
        def decode(self, request, log_path, *, timeout):
            worker_requests.append(dict(request))
            worker_timeouts.append(float(timeout))
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {"status": "ok", "frame_complete": True, "sync_success": True},
                }),
                stderr="",
            )

    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_decode_worker=FakeWorker(),
        remote_decode_request_timeout_sec=2.5,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_pull_files_from_remote_tar(_target, _remote_dir, remote_to_local, _log_path, **_kwargs):
        for remote_name, local_path in remote_to_local.items():
            if remote_name == "decode_summary.json":
                local_path.write_text(json.dumps({"payload_is_bit_exact": False}), encoding="utf-8")
            else:
                local_path.write_bytes(b"payload")

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_remote_command", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("persistent worker should handle remote decode")))
    monkeypatch.setattr(analog_batch, "push_file_to_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("worker mode should send manifest inline")))
    monkeypatch.setattr(analog_batch, "pull_files_from_remote_tar", fake_pull_files_from_remote_tar)
    monkeypatch.setattr(analog_batch, "cleanup_remote_files", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert worker_requests
    assert worker_requests[0]["rx_sc16"] == "/tmp/analog_runs/run42/image_0000/batch_rx.sc16"
    assert worker_requests[0]["sync_search_window_symbols"] == 4096
    assert worker_requests[0]["manifest_json"]["job_id"] == "case0"
    assert worker_timeouts == [2.5]


def test_process_image_records_remote_decode_soft_completion(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")

    class SoftCompletedWorker:
        def decode(self, request, log_path, *, timeout, soft_timeout=0.0, soft_completion=None):
            del timeout, soft_timeout, soft_completion
            log_path.write_text(json.dumps({"status": "ok", "soft_completed": True}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "soft_completed": True,
                    "summary_json": request["summary_json"],
                    "summary": {
                        "status": "ok",
                        "frame_complete": True,
                        "sync_success": True,
                        "decode_total_ms": 42.0,
                        "decode_timing_ms": {
                            "matched_filter": 2.5,
                            "initial_sync": 7.0,
                            "payload_recovery": 20.0,
                        },
                    },
                }),
                stderr="",
            )

    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/run42_rx",
        remote_decode_worker=SoftCompletedWorker(),
        remote_decode_request_timeout_sec=2.5,
        remote_decode_soft_complete_sec=0.25,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        remote_cleanup_mode="skip",
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "push_file_to_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("worker mode should send manifest inline")))
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert result.records[0]["remote_decode_soft_completed"] is True
    assert result.records[0]["remote_decode_timing_ms"]["matched_filter"] == 2.5
    assert result.records[0]["remote_decode_timing_ms"]["initial_sync"] == 7.0


def test_process_image_restarts_remote_decode_worker_after_timeout(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    closed: list[bool] = []
    restarts: list[tuple[str, Path]] = []

    class TimeoutWorker:
        def decode(self, _request, _log_path, *, timeout):
            raise analog_batch.RemoteDecodeWorkerTimeout(f"remote decode worker timed out after {timeout:.1f}s")

        def close(self, *, kill=False):
            closed.append(bool(kill))

    class ReplacementWorker:
        pass

    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/run42_rx",
        remote_decode_worker=TimeoutWorker(),
        remote_decode_request_timeout_sec=1.0,
        remote_decode_restart_on_timeout=True,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        remote_cleanup_mode="skip",
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_start(_cls, target, _args, log_path, *, control_socket=None):
        del control_socket
        restarts.append((target, log_path))
        return ReplacementWorker()

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "push_file_to_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("worker mode should send manifest inline")))
    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", classmethod(fake_start))
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    result = analog_batch.process_image(args, image)

    assert result.passed is False
    assert "timed out" in result.error
    assert closed == [True]
    assert restarts and restarts[0][0] == "user@board"
    assert isinstance(args.remote_decode_worker, ReplacementWorker)
    assert result.records[0]["remote_decode_restart_wall_sec"] >= 0.0


def test_process_image_remote_decode_error_preserves_stage_timings(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")

    class FailingWorker:
        def decode(self, _request, _log_path, *, timeout):
            del timeout
            time.sleep(0.01)
            raise RuntimeError("no sync candidate had a complete frame")

    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/run42_rx",
        remote_decode_worker=FailingWorker(),
        remote_decode_request_timeout_sec=0.0,
        remote_decode_restart_on_timeout=True,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        remote_cleanup_mode="skip",
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    control_lines: list[str] = []

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line == "STOP":
            return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.004 stop_wait_sec=0.125 wall_sec=0.129"
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "push_file_to_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("worker mode should send manifest inline")))
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is False
    assert "no sync candidate" in result.error
    record = result.records[0]
    assert record["make_wall_sec"] >= 0.0
    assert record["tx_wall_sec"] >= 0.0
    assert record["rx_arm_wall_sec"] >= 0.0
    assert record["rx_capture_wall_sec"] >= 0.0
    assert record["rx_wait_wall_sec"] >= 0.0
    assert record["decode_wall_sec"] >= 0.005
    assert record["remote_decode_restart_wall_sec"] == 0.0
    assert any(line == "STOP" for line in control_lines)
    assert control_lines.index("STOP") > next(i for i, line in enumerate(control_lines) if line.startswith("WAIT "))
    assert record["rx_server_stop_cmd_wall_sec"] == 0.004
    assert record["rx_server_stop_wait_wall_sec"] == 0.125


def test_process_image_stops_rx_after_decode_status_failure(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="local",
        remote_rx_ssh_target="",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        rx_wait_timeout_sec=0.5,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
    )
    control_lines: list[str] = []

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest_path.write_text(json.dumps({"capture_nsamps": 107584, "job_id": "case0"}), encoding="utf-8")
        return {"capture_nsamps": 107584, "job_id": "case0"}

    def fake_decode(_args, _batch_rx, _manifest_path, _out_npz, _out_wire, summary, _log_path):
        summary.write_text(json.dumps({"status": "error", "frame_complete": False}), encoding="utf-8")
        return 1

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        control_lines.append(line)
        if line == "STOP":
            return "OK busy=0 started=1 done=1 ok=0 stop_cmd_sec=0.002 stop_wait_sec=0.040 wall_sec=0.042"
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_in_process_decode", fake_decode)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    result = analog_batch.process_image(args, image)

    assert result.passed is False
    assert any(line == "STOP" for line in control_lines)
    assert control_lines.index("STOP") > next(i for i, line in enumerate(control_lines) if line.startswith("WAIT "))
    record = result.records[0]
    assert record["rx_server_stop_cmd_wall_sec"] == 0.002
    assert record["rx_server_stop_wait_wall_sec"] == 0.040


def test_pipeline_finalize_restarts_remote_decode_worker_after_timeout(tmp_path, monkeypatch):
    image = analog_batch.ImageRecord(
        index=7,
        input_path=tmp_path / "case7.bin",
        image_dir=tmp_path / "image_0007",
    )
    image.input_path.write_bytes(b"payload")
    closed: list[bool] = []
    restarts: list[tuple[str, Path]] = []

    class TimeoutWorker:
        def decode(self, _request, _log_path, *, timeout):
            raise analog_batch.RemoteDecodeWorkerTimeout(f"remote decode worker timed out after {timeout:.1f}s")

        def close(self, *, kill=False):
            closed.append(bool(kill))

    class ReplacementWorker:
        pass

    args = Namespace(
        remote_decode_worker=TimeoutWorker(),
        remote_decode_request_timeout_sec=1.0,
        remote_decode_restart_on_timeout=True,
        in_process_local_codec=True,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        sync_profile="fast-first",
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        retry_on_burst_miss=False,
        retry_on_low_sync=False,
        low_sync_retry_threshold=0.08,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
    )
    ctx = {
        "image": image,
        "attempt_index": 0,
        "max_attempts": 2,
        "slot_index": 1,
        "pipeline_depth": 2,
        "started": time.monotonic() - 0.2,
        "tx_sc16": tmp_path / "tx_analog.sc16",
        "batch_rx": tmp_path / "batch_rx.sc16",
        "manifest_path": tmp_path / "manifest.json",
        "out_npz": tmp_path / "received_latent.npz",
        "out_wire": tmp_path / "merged_round0.bin",
        "decode_summary": tmp_path / "decode_summary.json",
        "manifest": {"capture_nsamps": 107584, "job_id": "case7"},
        "make_wall_sec": 0.01,
        "tx_wall_sec": 0.02,
        "rx_arm_wall_sec": 0.03,
        "rx_capture_wall_sec": 0.10,
        "rx_wait_wall_sec": 0.04,
        "rx_pull_wall_sec": 0.0,
        "merge_wall_sec": 0.0,
        "remote_cleanup_wall_sec": 0.0,
        "remote_cleanup_mode": "skip",
        "remote_decode_result_mode": "remote-dir",
        "remote_decoded_dir": "/home/user/cockpit_usrp_rx/run42_rx",
        "remote_received_npz": "",
        "remote_target": "user@board",
        "ssh_control_socket": None,
        "remote_run_dir": "/tmp/analog_runs/run42/image_0007",
        "remote_batch_rx": "/tmp/analog_runs/run42/image_0007/batch_rx.sc16",
        "remote_tx": "",
        "remote_manifest": "/tmp/analog_runs/run42/image_0007/manifest.json",
        "capture_timeout": 30.0,
        "capture_completed_at": time.monotonic(),
        "decode_queue_wall_sec": 0.0,
        "slot_wait_wall_sec": 0.0,
    }

    def fake_start(_cls, target, _args, log_path, *, control_socket=None):
        del control_socket
        restarts.append((target, log_path))
        return ReplacementWorker()

    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", classmethod(fake_start))

    result = analog_batch._finalize_remote_decode_pipeline_attempt(args, ctx)

    assert result.passed is False
    assert "timed out" in result.error
    assert closed == [True]
    assert restarts and restarts[0][0] == "user@board"
    assert isinstance(args.remote_decode_worker, ReplacementWorker)
    assert result.records[0]["remote_decode_restart_wall_sec"] >= 0.0


def test_process_image_remote_decode_can_publish_board_decoded_outputs_without_local_pull(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    worker_requests: list[dict[str, object]] = []
    pulled: list[dict[str, Path]] = []
    cleaned: list[list[str]] = []

    class FakeWorker:
        def decode(self, request, log_path, *, timeout):
            worker_requests.append(dict(request))
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {"status": "ok", "frame_complete": True, "sync_success": True},
                }),
                stderr="",
            )

    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/run42_rx",
        remote_decode_worker=FakeWorker(),
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        remote_cleanup_mode="sync",
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_pull_files_from_remote_tar(_target, _remote_dir, remote_to_local, _log_path, **_kwargs):
        pulled.append(dict(remote_to_local))
        raise AssertionError("worker remote-dir mode should use inline summary instead of tar pull")

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "push_file_to_remote", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("worker mode should send manifest inline")))
    monkeypatch.setattr(analog_batch, "pull_files_from_remote_tar", fake_pull_files_from_remote_tar)
    monkeypatch.setattr(analog_batch, "cleanup_remote_files", lambda _target, paths, *_args, **_kwargs: cleaned.append(list(paths)) or True)
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert worker_requests[0]["out_npz"] == "/home/user/cockpit_usrp_rx/run42_rx/00000000.npz"
    assert worker_requests[0]["out_wire"] == ""
    assert worker_requests[0]["manifest_json"]["job_id"] == "case0"
    assert not pulled
    assert json.loads((image.image_dir / "decode_summary.json").read_text(encoding="utf-8"))["sync_success"] is True
    assert not (image.image_dir / "received_latent.npz").exists()
    assert not (image.image_dir / "merged_round0.bin").exists()
    assert result.records[0]["remote_decoded_output_dir"] == "/home/user/cockpit_usrp_rx/run42_rx"
    assert result.records[0]["remote_received_latent_npz"] == "/home/user/cockpit_usrp_rx/run42_rx/00000000.npz"
    assert cleaned and "/home/user/cockpit_usrp_rx/run42_rx/00000000.npz" not in cleaned[0]


def test_process_image_remote_decode_can_skip_board_summary_file_when_response_only(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    image = analog_batch.ImageRecord(index=0, input_path=input_path, image_dir=tmp_path / "image_0000")
    worker_requests: list[dict[str, object]] = []

    class FakeWorker:
        def decode(self, request, log_path, *, timeout):
            worker_requests.append(dict(request))
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {
                        "status": "ok",
                        "frame_complete": True,
                        "sync_success": True,
                        "decode_total_ms": 43.0,
                    },
                }),
                stderr="",
            )

    args = Namespace(
        dry_run=False,
        in_process_local_codec=True,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decode_response_only_summary=True,
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/run42_rx",
        remote_decode_worker=FakeWorker(),
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        run_id="run42",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        tx_delay_sec=0.0,
        rx_tail_sec=0.3,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        robust_sync=True,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        remote_cleanup_mode="skip",
    )

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {"capture_nsamps": 107584, "job_id": "case0"}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: None)
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    result = analog_batch.process_image(args, image)

    assert result.passed is True
    assert worker_requests[0]["summary_json"] == ""
    assert worker_requests[0]["out_npz"] == "/home/user/cockpit_usrp_rx/run42_rx/00000000.npz"
    assert json.loads((image.image_dir / "decode_summary.json").read_text(encoding="utf-8"))["decode_total_ms"] == 43.0
    assert result.records[0]["remote_decode_response_only_summary"] is True


def test_batch_runner_retries_failed_iq_images_with_max_arq_rounds(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=None,
        pattern="*.bin",
        count=1,
        cycle_inputs=False,
        run_root=run_root,
        run_id="retry-run",
        dry_run=True,
        rx_capture_mode="local",
        max_arq_rounds=1,
        stop_on_fail=False,
        in_process_local_codec=True,
        rate=5_000_000.0,
        sps=16,
        rx_post_quantize=True,
        robust_sync=False,
        sync_candidates=12,
        min_sync_metric=0.08,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        scramble_key="",
        scramble_key_hex="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    calls = 0

    def fake_process_image(_args, image):
        nonlocal calls
        calls += 1
        if calls == 1:
            image.status = 1
            image.passed = False
            image.error = "sync metric below threshold"
            image.records.append({"round": 0, "error": image.error, "total_wall_sec": 1.0})
        else:
            image.status = 0
            image.passed = True
            image.error = ""
            image.records.append({"round": 0, "sync_metric": 0.92, "total_wall_sec": 0.5})
        return image

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "load_inputs", lambda _args: [input_path])
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "process_image", fake_process_image)

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "retry-run" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert calls == 2
    assert summary["passed_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["images"][0]["rounds"] == 2
    assert [record["round"] for record in summary["images"][0]["round_records"]] == [0, 1]


def test_batch_runner_marks_decode_attempt_before_process_image(tmp_path, monkeypatch):
    input_path = tmp_path / "case0.bin"
    input_path.write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=None,
        pattern="*.bin",
        count=1,
        cycle_inputs=False,
        run_root=run_root,
        run_id="attempt-run",
        dry_run=True,
        rx_capture_mode="local",
        max_arq_rounds=1,
        stop_on_fail=False,
        in_process_local_codec=True,
        rate=5_000_000.0,
        sps=16,
        rx_post_quantize=True,
        robust_sync=False,
        sync_candidates=12,
        min_sync_metric=0.08,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        scramble_key="",
        scramble_key_hex="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
        retry_on_low_sync=True,
        low_sync_retry_threshold=0.08,
    )
    seen_attempts: list[tuple[int, int, bool]] = []

    def fake_process_image(_args, image):
        index = int(getattr(_args, "current_decode_attempt_index", -1))
        maximum = int(getattr(_args, "current_decode_max_attempts", -1))
        enabled = analog_batch.low_sync_retry_enabled_for_attempt(_args)
        seen_attempts.append((index, maximum, enabled))
        image.status = 1 if index == 0 else 0
        image.passed = index != 0
        image.error = "" if image.passed else "low sync metric below retry threshold"
        image.records.append({"round": 0, "error": image.error, "total_wall_sec": 0.1})
        return image

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "load_inputs", lambda _args: [input_path])
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "process_image", fake_process_image)

    assert analog_batch.main() == 0

    assert seen_attempts == [(0, 2, True), (1, 2, False)]


def test_batch_runner_remote_decode_reuses_one_ssh_control_master(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for idx in range(2):
        (input_dir / f"case{idx}.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=2,
        cycle_inputs=False,
        run_root=run_root,
        run_id="remote-batch",
        dry_run=False,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/remote-batch_rx",
        remote_cleanup_mode="skip",
        max_arq_rounds=0,
        stop_on_fail=False,
        in_process_local_codec=True,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        sps=2,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        rx_post_quantize=False,
        robust_sync=False,
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    master_starts: list[str] = []
    master_terminated: list[bool] = []
    worker_control_sockets: list[str | None] = []

    class FakeMaster:
        def terminate(self):
            master_terminated.append(True)

        def wait(self, timeout=None):
            return 0

    class FakeWorker:
        startup_wall_sec = 0.01
        ready_response = {"status": "ready"}

        def decode(self, request, log_path, *, timeout):
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {
                        "status": "ok",
                        "frame_complete": True,
                        "sync_success": True,
                        "detected_airtime_ms": 9.58,
                    },
                }),
                stderr="",
            )

        def close(self):
            return None

    def fake_start_master(target):
        master_starts.append(target)
        return FakeMaster()

    def fake_worker_start(target, start_args, log_path, *, control_socket=None):
        worker_control_sockets.append(control_socket)
        return FakeWorker()

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {
            "capture_nsamps": 67888,
            "tx_waveform_samples": 47888,
            "job_id": "case",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", fake_start_master)
    monkeypatch.setattr(analog_batch, "_ssh_control_socket_path", lambda: "shared-socket")
    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", staticmethod(fake_worker_start))
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "remote-batch" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert summary["passed_count"] == 2
    assert summary["iq_stage_benchmark"]["remote_decode_ms"]["n"] == 2
    assert summary["iq_stage_benchmark"]["total_transport_ms"]["n"] == 2
    assert master_starts == ["user@board"]
    assert worker_control_sockets == ["shared-socket"]
    assert len(master_terminated) == 1


def test_batch_runner_can_share_rx_control_session_across_sequential_images(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for idx in range(2):
        (input_dir / f"case{idx}.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=2,
        cycle_inputs=False,
        run_root=run_root,
        run_id="shared-rx-session",
        dry_run=False,
        rx_capture_mode="local",
        rx_batch_session_control=True,
        rx_session_control=True,
        max_arq_rounds=0,
        stop_on_fail=False,
        remote_rx_ssh_target="",
        sps=2,
        rate=5_000_000.0,
        rx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        rx_post_quantize=False,
        robust_sync=False,
        sync_profile="fast-first",
        sync_candidates=12,
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        retry_on_burst_miss=False,
        retry_on_low_sync=False,
        low_sync_retry_threshold=0.08,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        scramble_key="",
        scramble_key_hex="",
        channel_mode="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    opened: list[tuple[str, int]] = []
    closed: list[bool] = []
    seen_sessions: list[object | None] = []

    class SharedSession:
        def close(self):
            closed.append(True)

    shared_session = SharedSession()

    def fake_open_session(host, port, _timeout):
        opened.append((host, int(port)))
        return shared_session

    def fake_process_image(process_args, image):
        seen_sessions.append(getattr(process_args, "rx_control_session", None))
        image.passed = True
        image.status = 0
        image.records.append({
            "total_wall_sec": 0.1,
            "rx_capture_wall_sec": 0.02,
            "decode_wall_sec": 0.03,
            "detected_airtime_ms": 9.58,
        })
        return image

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "open_control_session", fake_open_session)
    monkeypatch.setattr(analog_batch, "process_image", fake_process_image)

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "shared-rx-session" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert opened == [("127.0.0.1", 29220)]
    assert seen_sessions == [shared_session, shared_session]
    assert closed == [True]
    assert summary["rx_batch_session_control_enabled"] is True


def test_batch_runner_can_recycle_shared_rx_control_session_by_window(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for idx in range(5):
        (input_dir / f"case{idx}.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=5,
        cycle_inputs=False,
        run_root=run_root,
        run_id="bounded-rx-session",
        dry_run=False,
        rx_capture_mode="local",
        rx_batch_session_control=True,
        rx_batch_session_max_images=2,
        rx_session_control=True,
        max_arq_rounds=0,
        stop_on_fail=False,
        remote_rx_ssh_target="",
        sps=2,
        rate=5_000_000.0,
        rx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        rx_post_quantize=False,
        robust_sync=False,
        sync_profile="fast-first",
        sync_candidates=12,
        fast_sync_candidates=4,
        fast_sync_search_window_symbols=1024,
        fallback_sync_candidates=12,
        fallback_sync_search_window_symbols=4096,
        retry_on_burst_miss=False,
        retry_on_low_sync=False,
        low_sync_retry_threshold=0.08,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        scramble_key="",
        scramble_key_hex="",
        channel_mode="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    opened: list[object] = []
    closed: list[object] = []
    seen_sessions: list[object | None] = []

    class SharedSession:
        def __init__(self, index: int):
            self.index = index

        def close(self):
            closed.append(self)

    def fake_open_session(_host, _port, _timeout):
        session = SharedSession(len(opened))
        opened.append(session)
        return session

    def fake_process_image(process_args, image):
        seen_sessions.append(getattr(process_args, "rx_control_session", None))
        image.passed = True
        image.status = 0
        image.records.append({
            "total_wall_sec": 0.1,
            "rx_capture_wall_sec": 0.02,
            "decode_wall_sec": 0.03,
            "detected_airtime_ms": 9.58,
        })
        return image

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "open_control_session", fake_open_session)
    monkeypatch.setattr(analog_batch, "process_image", fake_process_image)

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "bounded-rx-session" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert [session.index for session in opened] == [0, 1, 2]
    assert [session.index for session in seen_sessions] == [0, 0, 1, 1, 2]
    assert [session.index for session in closed] == [0, 1, 2]
    assert summary["rx_batch_session_control_enabled"] is True
    assert summary["rx_batch_session_max_images"] == 2


def test_batch_runner_does_not_retry_failed_ssh_control_master_per_image(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for idx in range(2):
        (input_dir / f"case{idx}.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=2,
        cycle_inputs=False,
        run_root=run_root,
        run_id="remote-batch",
        dry_run=False,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/remote-batch_rx",
        remote_cleanup_mode="skip",
        max_arq_rounds=0,
        stop_on_fail=False,
        in_process_local_codec=True,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        sps=2,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="127.0.0.1",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        rx_post_quantize=False,
        robust_sync=False,
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    master_starts: list[str] = []
    worker_control_sockets: list[str | None] = []

    class FakeWorker:
        startup_wall_sec = 0.01
        ready_response = {"status": "ready"}

        def decode(self, request, log_path, *, timeout):
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {
                        "status": "ok",
                        "frame_complete": True,
                        "sync_success": True,
                        "detected_airtime_ms": 9.58,
                    },
                }),
                stderr="",
            )

        def close(self):
            return None

    def fake_start_master(target):
        master_starts.append(target)
        return None

    def fake_worker_start(target, start_args, log_path, *, control_socket=None):
        worker_control_sockets.append(control_socket)
        return FakeWorker()

    def fake_make(_args, _image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {
            "capture_nsamps": 67888,
            "tx_waveform_samples": 47888,
            "job_id": "case",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", fake_start_master)
    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", staticmethod(fake_worker_start))
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", lambda _host, _port, line, _log_path, _timeout: f"OK {line}")

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "remote-batch" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert summary["passed_count"] == 2
    assert master_starts == ["user@board"]
    assert worker_control_sockets == [None]


def test_batch_runner_pipeline_depth_two_overlaps_next_capture_with_decode(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for idx in range(2):
        (input_dir / f"case{idx}.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=2,
        cycle_inputs=False,
        run_root=run_root,
        run_id="pipeline-depth-2",
        dry_run=False,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/pipeline-depth-2_rx",
        remote_cleanup_mode="skip",
        pipeline_depth=2,
        pipeline_rf_decode_overlap=True,
        max_arq_rounds=0,
        stop_on_fail=False,
        in_process_local_codec=True,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        sps=2,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="192.168.10.22",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        rx_post_quantize=False,
        robust_sync=False,
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    events: list[str] = []
    second_capture_seen = threading.Event()

    class FakeMaster:
        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    class FakeWorker:
        startup_wall_sec = 0.01
        ready_response = {"status": "ready"}

        def decode(self, request, log_path, *, timeout):
            del timeout
            out_name = str(request["out_npz"]).rsplit("/", 1)[-1]
            image_index = int(out_name.split(".", 1)[0])
            events.append(f"decode_start_{image_index}")
            if image_index == 0 and not second_capture_seen.wait(timeout=1.0):
                raise AssertionError("second capture did not start while first decode was in flight")
            events.append(f"decode_done_{image_index}")
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {
                        "status": "ok",
                        "frame_complete": True,
                        "sync_success": True,
                        "detected_airtime_ms": 9.58,
                    },
                }),
                stderr="",
            )

        def close(self):
            return None

    def fake_worker_start(target, start_args, log_path, *, control_socket=None):
        return FakeWorker()

    def fake_make(_args, image, tx_sc16, manifest_path, _log_path):
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {
            "capture_nsamps": 67888,
            "tx_waveform_samples": 47888,
            "job_id": f"case-{image.index}",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        if line.startswith("CAPTURE"):
            image_token = "image_0001" if "image_0001" in line else "image_0000"
            events.append(f"capture_{image_token[-4:]}")
            if image_token == "image_0001":
                second_capture_seen.set()
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: FakeMaster())
    monkeypatch.setattr(analog_batch, "_ssh_control_socket_path", lambda: "shared-socket")
    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", staticmethod(fake_worker_start))
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "pipeline-depth-2" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert summary["pipeline_enabled"] is True
    assert summary["pipeline_depth"] == 2
    assert summary["max_inflight"] == 2
    assert summary["passed_count"] == 2
    assert events.index("capture_0001") < events.index("decode_done_0")
    assert [image["round_records"][0]["pipeline_slot"] for image in summary["images"]] == [0, 1]


def test_batch_runner_pipeline_depth_two_guards_capture_from_decode_by_default(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for idx in range(2):
        (input_dir / f"case{idx}.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=2,
        cycle_inputs=False,
        run_root=run_root,
        run_id="pipeline-depth-2-guarded",
        dry_run=False,
        rx_capture_mode="remote-decode",
        remote_decode_result_mode="remote-dir",
        remote_decoded_output_dir="/home/user/cockpit_usrp_rx/pipeline-depth-2-guarded_rx",
        remote_cleanup_mode="skip",
        pipeline_depth=2,
        pipeline_rf_decode_overlap=False,
        max_arq_rounds=0,
        stop_on_fail=False,
        in_process_local_codec=True,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
        tx_file_path_prefix_from="",
        tx_file_path_prefix_to="",
        rate=5_000_000.0,
        sps=2,
        tx_delay_sec=0.0,
        rx_tail_sec=0.05,
        rx_timeout_sec=30.0,
        tx_timeout_sec=30.0,
        rx_control_host="192.168.10.22",
        rx_control_port=29220,
        tx_control_host="127.0.0.1",
        tx_control_port=29221,
        rx_post_quantize=False,
        robust_sync=False,
        sync_candidates=12,
        min_sync_metric=0.05,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        sync_search_window_symbols=4096,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
        sim_cfo_hz=0.0,
        sim_snr_db=None,
        sim_gain=1.0,
        sim_phase_deg=0.0,
        sim_phase_drift_deg=0.0,
        sim_dc_real=0.0,
        sim_dc_imag=0.0,
        sim_seed=1,
    )
    events: list[str] = []
    decode_started = threading.Event()
    second_capture_seen = threading.Event()

    class FakeMaster:
        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    class FakeWorker:
        startup_wall_sec = 0.01
        ready_response = {"status": "ready"}

        def decode(self, request, log_path, *, timeout):
            del timeout
            out_name = str(request["out_npz"]).rsplit("/", 1)[-1]
            image_index = int(out_name.split(".", 1)[0])
            events.append(f"decode_start_{image_index}")
            if image_index == 0:
                decode_started.set()
                assert not second_capture_seen.wait(timeout=0.05), "second capture overlapped guarded decode"
            events.append(f"decode_done_{image_index}")
            log_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return subprocess.CompletedProcess(
                args=["decode-server"],
                returncode=0,
                stdout=json.dumps({
                    "status": "ok",
                    "summary": {
                        "status": "ok",
                        "frame_complete": True,
                        "sync_success": True,
                        "detected_airtime_ms": 9.58,
                    },
                }),
                stderr="",
            )

        def close(self):
            return None

    def fake_worker_start(target, start_args, log_path, *, control_socket=None):
        return FakeWorker()

    def fake_make(_args, image, tx_sc16, manifest_path, _log_path):
        if image.index == 1:
            assert decode_started.wait(timeout=1.0), "first decode did not start before second make"
        tx_sc16.write_bytes(b"\0" * 128)
        manifest = {
            "capture_nsamps": 67888,
            "tx_waveform_samples": 47888,
            "job_id": f"case-{image.index}",
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def fake_run_control(_host, _port, line, _log_path, _timeout):
        if line.startswith("CAPTURE"):
            image_token = "image_0001" if "image_0001" in line else "image_0000"
            events.append(f"capture_{image_token[-4:]}")
            if image_token == "image_0001":
                second_capture_seen.set()
        return f"OK {line}"

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: FakeMaster())
    monkeypatch.setattr(analog_batch, "_ssh_control_socket_path", lambda: "shared-socket")
    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", staticmethod(fake_worker_start))
    monkeypatch.setattr(analog_batch, "run_in_process_make", fake_make)
    monkeypatch.setattr(analog_batch, "run_control", fake_run_control)

    assert analog_batch.main() == 0

    summary = json.loads((run_root / "pipeline-depth-2-guarded" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    assert summary["pipeline_enabled"] is True
    assert summary["pipeline_depth"] == 2
    assert summary["pipeline_rf_decode_overlap"] is False
    assert summary["max_inflight"] == 2
    assert summary["passed_count"] == 2
    assert events.index("decode_done_0") < events.index("capture_0001")


def test_remote_decode_pipeline_retries_capture_exception_in_same_slot(tmp_path, monkeypatch):
    image = analog_batch.ImageRecord(index=0, input_path=tmp_path / "case0.bin", image_dir=tmp_path / "image_0000")
    image.input_path.write_bytes(b"payload")
    args = Namespace(max_arq_rounds=1, remote_rx_ssh_target="user@board")
    capture_attempts: list[tuple[int, int, int]] = []

    def fake_capture(_args, item, *, attempt_index, max_attempts, slot_index, pipeline_depth):
        capture_attempts.append((item.index, attempt_index, slot_index))
        if attempt_index == 0:
            raise RuntimeError("control command failed: WAIT timeout=0.500000\nERR_TIMEOUT host=board port=29220")
        return {
            "image": item,
            "attempt_index": attempt_index,
            "max_attempts": max_attempts,
            "slot_index": slot_index,
            "pipeline_depth": pipeline_depth,
        }

    def fake_finalize(_args, ctx):
        item = ctx["image"]
        item.status = 0
        item.passed = True
        item.error = ""
        item.records.append({
            "attempt": int(ctx["attempt_index"]) + 1,
            "pipeline_slot": int(ctx["slot_index"]),
            "total_wall_sec": 0.1,
        })
        return item

    monkeypatch.setattr(analog_batch, "_capture_remote_decode_pipeline_attempt", fake_capture)
    monkeypatch.setattr(analog_batch, "_finalize_remote_decode_pipeline_attempt", fake_finalize)

    completed, stats = analog_batch._process_images_remote_decode_pipeline(args, [image], pipeline_depth=1)

    assert stats["pipeline_depth"] == 1
    assert completed[0].passed is True
    assert capture_attempts == [(0, 0, 0), (0, 1, 0)]
    assert completed[0].records[0]["error"].startswith("control command failed: WAIT timeout")
    assert completed[0].records[-1]["attempt"] == 2


def test_batch_runner_closes_shared_ssh_master_when_worker_start_fails(tmp_path, monkeypatch):
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    (input_dir / "case0.bin").write_bytes(b"payload")
    run_root = tmp_path / "runs"
    args = Namespace(
        input=None,
        input_list=None,
        input_dir=input_dir,
        pattern="*.bin",
        count=1,
        cycle_inputs=False,
        run_root=run_root,
        run_id="worker-fail",
        dry_run=False,
        rx_capture_mode="remote-decode",
        max_arq_rounds=0,
        stop_on_fail=False,
        remote_rx_ssh_target="user@board",
        remote_rx_run_root="/tmp/analog_runs",
    )
    master_terminated: list[bool] = []

    class FakeMaster:
        def terminate(self):
            master_terminated.append(True)

        def wait(self, timeout=None):
            return 0

    def fake_worker_start(target, start_args, log_path, *, control_socket=None):
        raise RuntimeError("worker failed")

    monkeypatch.setattr(analog_batch, "parse_args", lambda: args)
    monkeypatch.setattr(analog_batch, "_validate_rx_capture_config", lambda _args: None)
    monkeypatch.setattr(analog_batch, "warmup_local_codec", lambda _args, _inputs: 0.0)
    monkeypatch.setattr(analog_batch, "_ssh_start_control_master", lambda _target: FakeMaster())
    monkeypatch.setattr(analog_batch, "_ssh_control_socket_path", lambda: "shared-socket")
    monkeypatch.setattr(analog_batch.RemoteAnalogDecodeWorker, "start", staticmethod(fake_worker_start))

    try:
        analog_batch.main()
    except RuntimeError as exc:
        assert str(exc) == "worker failed"
    else:
        raise AssertionError("worker startup failure should propagate")

    assert master_terminated == [True]


def test_batch_runner_dry_run_can_inject_simulated_cfo_awgn(tmp_path):
    latent = np.linspace(-1.0, 1.0, num=1 * 8 * 8 * 8, dtype=np.float32).reshape(1, 8, 8, 8)
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    np.savez(input_dir / "case0.npz", latent=latent)
    run_root = tmp_path / "runs"

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_BATCH),
            "--input-dir",
            str(input_dir),
            "--pattern",
            "*.npz",
            "--count",
            "1",
            "--run-root",
            str(run_root),
            "--run-id",
            "sim",
            "--dry-run",
            "--sim-cfo-hz",
            "1000",
            "--sim-snr-db",
            "20",
            "--sim-phase-deg",
            "15",
            "--sim-gain",
            "0.90",
            "--cfo-pilot-symbols",
            "512",
            "--sync-pilot-symbols",
            "512",
            "--data-block-symbols",
            "256",
            "--mid-pilot-symbols",
            "64",
            "--zero-guard-samples",
            "512",
            "--tail-guard-samples",
            "512",
            "--no-rx-post-quantize",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    image_dir = run_root / "sim" / "image_0000"
    summary = json.loads((run_root / "sim" / "batch_spool_summary.json").read_text(encoding="utf-8"))
    decode_summary = json.loads((image_dir / "decode_summary.json").read_text(encoding="utf-8"))
    assert (image_dir / "simulate_channel.log").is_file()
    assert (image_dir / "simulate_channel_summary.json").is_file()
    assert summary["simulated_channel"]["enabled"] is True
    assert summary["images"][0]["round_records"][0]["simulated_cfo_hz"] == 1000.0
    assert abs(decode_summary["estimated_cfo_hz"] - 1000.0) < 150.0


def test_key_derived_scrambling_recovers_latent_without_storing_key(tmp_path):
    rng = np.random.default_rng(456)
    latent = rng.standard_normal((1, 4, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_scrambled.sc16"
    manifest = tmp_path / "manifest.json"
    out_npz = tmp_path / "received_latent.npz"
    summary = tmp_path / "decode_summary.json"
    np.savez(input_path, latent=latent)

    common = [
        "--rate",
        "5000000",
        "--sps",
        "4",
        "--amp",
        "3000",
        "--cfo-pilot-symbols",
        "128",
        "--sync-pilot-symbols",
        "128",
        "--data-block-symbols",
        "128",
        "--mid-pilot-symbols",
        "32",
        "--zero-guard-samples",
        "256",
        "--tail-guard-samples",
        "256",
        "--no-rx-post-quantize",
    ]
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "make",
            "--input",
            str(input_path),
            "--out-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--scramble-key",
            "session-key-for-test",
            "--scramble-context",
            "unit-test-context",
            *common,
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    missing_key = subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(tmp_path / "missing_key.npz"),
        ],
        check=False,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert missing_key.returncode != 0
    assert "scramble key" in missing_key.stdout.lower()

    wrong_context = subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(tmp_path / "wrong_context.npz"),
            "--scramble-key",
            "session-key-for-test",
            "--scramble-context",
            "wrong-context",
        ],
        check=False,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert wrong_context.returncode != 0
    assert "context" in wrong_context.stdout.lower()

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(out_npz),
            "--summary-json",
            str(summary),
            "--scramble-key",
            "session-key-for-test",
            "--scramble-context",
            "unit-test-context",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    with np.load(out_npz) as payload:
        recovered = payload["latent"]
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    summary_data = json.loads(summary.read_text(encoding="utf-8"))

    assert manifest_data["scrambling_enabled"] is True
    assert manifest_data["scrambling_mode"] == "keyed-permutation-sign-v1"
    assert "session-key-for-test" not in manifest.read_text(encoding="utf-8")
    assert summary_data["scrambling_enabled"] is True
    assert recovered.shape == latent.shape
    assert float(np.mean(np.square(recovered - latent))) < 5.0e-4


def test_simulated_cfo_awgn_loopback_estimates_cfo_and_records_quality(tmp_path):
    rng = np.random.default_rng(789)
    latent = rng.standard_normal((1, 8, 8, 8)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    rx_sc16 = tmp_path / "rx_impair.sc16"
    manifest = tmp_path / "manifest.json"
    impair_summary = tmp_path / "impair_summary.json"
    decode_summary = tmp_path / "decode_summary.json"
    out_npz = tmp_path / "received_latent.npz"
    np.savez(input_path, latent=latent)

    make_args = [
        sys.executable,
        str(ANALOG_LINK),
        "make",
        "--input",
        str(input_path),
        "--out-sc16",
        str(tx_sc16),
        "--manifest",
        str(manifest),
        "--rate",
        "5000000",
        "--sps",
        "4",
        "--amp",
        "3000",
        "--cfo-pilot-symbols",
        "512",
        "--sync-pilot-symbols",
        "512",
        "--data-block-symbols",
        "256",
        "--mid-pilot-symbols",
        "64",
        "--zero-guard-samples",
        "512",
        "--tail-guard-samples",
        "512",
        "--no-rx-post-quantize",
    ]
    subprocess.run(make_args, check=True, cwd=PROJECT_ROOT)
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "simulate-channel",
            "--tx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-sc16",
            str(rx_sc16),
            "--cfo-hz",
            "3000",
            "--snr-db",
            "20",
            "--gain",
            "0.85",
            "--phase-deg",
            "25",
            "--dc-real",
            "0.015",
            "--dc-imag",
            "-0.010",
            "--seed",
            "42",
            "--summary-json",
            str(impair_summary),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(rx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(out_npz),
            "--summary-json",
            str(decode_summary),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    impair = json.loads(impair_summary.read_text(encoding="utf-8"))
    summary = json.loads(decode_summary.read_text(encoding="utf-8"))
    with np.load(out_npz) as payload:
        recovered = payload["latent"]

    assert impair["simulated_cfo_hz"] == 3000.0
    assert summary["sync_success"] is True
    assert abs(summary["estimated_cfo_hz"] - 3000.0) < 250.0
    assert summary["evm_rms"] < 0.25
    assert summary["estimated_snr_db"] > 10.0
    assert recovered.shape == latent.shape


def test_robust_sync_recovers_3khz_cfo_at_15db_for_full_latent(tmp_path):
    rng = np.random.default_rng(2026)
    latent = rng.standard_normal((1, 32, 32, 32)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    rx_sc16 = tmp_path / "rx_impair.sc16"
    manifest = tmp_path / "manifest.json"
    decode_summary = tmp_path / "decode_summary.json"
    out_npz = tmp_path / "received_latent.npz"
    np.savez(input_path, latent=latent)

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "make",
            "--input",
            str(input_path),
            "--out-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--rate",
            "5000000",
            "--sps",
            "4",
            "--amp",
            "3000",
            "--cfo-pilot-symbols",
            "1024",
            "--sync-pilot-symbols",
            "1024",
            "--data-block-symbols",
            "4096",
            "--mid-pilot-symbols",
            "128",
            "--zero-guard-samples",
            "4096",
            "--tail-guard-samples",
            "4096",
            "--no-rx-post-quantize",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "simulate-channel",
            "--tx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-sc16",
            str(rx_sc16),
            "--cfo-hz",
            "3000",
            "--snr-db",
            "15",
            "--gain",
            "0.85",
            "--phase-deg",
            "25",
            "--dc-real",
            "0.015",
            "--dc-imag",
            "-0.010",
            "--seed",
            "42",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(rx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(out_npz),
            "--summary-json",
            str(decode_summary),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    summary = json.loads(decode_summary.read_text(encoding="utf-8"))
    with np.load(out_npz) as payload:
        recovered = payload["latent"]

    assert summary["sync_success"] is True
    assert summary["sync_search_mode"] in {"robust-cfo-grid", "normal"}
    assert abs(summary["estimated_cfo_hz"] - 3000.0) < 250.0
    assert summary["evm_rms"] < 0.15
    assert recovered.shape == latent.shape


def test_robust_sync_rejects_false_peak_then_recovers_3khz_cfo_at_5db(tmp_path):
    rng = np.random.default_rng(2026)
    latent = rng.standard_normal((1, 32, 32, 32)).astype(np.float32)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    rx_sc16 = tmp_path / "rx_impair.sc16"
    manifest = tmp_path / "manifest.json"
    np.savez(input_path, latent=latent)

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "make",
            "--input",
            str(input_path),
            "--out-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--rate",
            "5000000",
            "--sps",
            "4",
            "--amp",
            "3000",
            "--cfo-pilot-symbols",
            "1024",
            "--sync-pilot-symbols",
            "1024",
            "--data-block-symbols",
            "4096",
            "--mid-pilot-symbols",
            "128",
            "--zero-guard-samples",
            "4096",
            "--tail-guard-samples",
            "4096",
            "--no-rx-post-quantize",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "simulate-channel",
            "--tx-sc16",
            str(tx_sc16),
            "--manifest",
            str(manifest),
            "--out-sc16",
            str(rx_sc16),
            "--cfo-hz",
            "3000",
            "--snr-db",
            "5",
            "--gain",
            "0.85",
            "--phase-deg",
            "25",
            "--dc-real",
            "0.015",
            "--dc-imag",
            "-0.010",
            "--seed",
            "42",
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    subprocess.run(
        [
            sys.executable,
            str(ANALOG_LINK),
            "decode",
            "--rx-sc16",
            str(rx_sc16),
            "--manifest",
            str(manifest),
            "--out-npz",
            str(tmp_path / "received_latent.npz"),
            "--summary-json",
            str(tmp_path / "decode_summary.json"),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )

    summary = json.loads((tmp_path / "decode_summary.json").read_text(encoding="utf-8"))
    assert summary["sync_search_mode"] == "robust-cfo-grid"
    assert "sync metric" in summary["normal_sync_error"].lower()
    assert summary["sync_metric"] > 0.90
    assert abs(summary["estimated_cfo_hz"] - 3000.0) < 250.0
    assert summary["evm_rms"] < 0.30


def test_decode_rejects_cfo_estimate_when_it_degrades_existing_sync(tmp_path, monkeypatch):
    latent = np.linspace(-0.75, 0.75, num=1 * 4 * 8 * 8, dtype=np.float32).reshape(1, 4, 8, 8)
    input_path = tmp_path / "latent.npz"
    tx_sc16 = tmp_path / "tx_analog.sc16"
    manifest = tmp_path / "manifest.json"
    np.savez(input_path, latent=latent)

    common = {
        "rate": 5_000_000.0,
        "sps": 4,
        "rrc_beta": 0.35,
        "rrc_span": 8,
        "amp": 3000,
        "zero_guard_samples": 256,
        "tail_guard_samples": 256,
        "cfo_pilot_symbols": 128,
        "sync_pilot_symbols": 128,
        "data_block_symbols": 256,
        "mid_pilot_symbols": 32,
        "cfo_seed": 1001,
        "sync_seed": 1002,
        "mid_pilot_seed": 1003,
        "capture_margin_samples": 256,
        "rx_post_quantize": False,
        "scramble_key": "",
        "scramble_key_hex": "",
        "scramble_context": "",
    }
    analog.make_waveform(Namespace(
        input=str(input_path),
        out_sc16=str(tx_sc16),
        manifest=str(manifest),
        job_id="bad-cfo-guard",
        **common,
    ))

    def bad_cfo_estimate(*_args, **_kwargs):
        return 25000.0, "forced-bad"

    monkeypatch.setattr(analog, "estimate_cfo_from_known_pilot", bad_cfo_estimate)
    summary = analog.decode_waveform(Namespace(
        rx_sc16=str(tx_sc16),
        manifest=str(manifest),
        out_npz=str(tmp_path / "received_latent.npz"),
        out_wire="",
        summary_json=str(tmp_path / "decode_summary.json"),
        sync_candidates=12,
        min_sync_metric=0.25,
        robust_sync=False,
        robust_cfo_max_hz=8000.0,
        robust_cfo_step_hz=500.0,
        scramble_key="",
        scramble_key_hex="",
        scramble_context="",
    ))

    assert summary["sync_metric"] > 0.95
    assert summary["estimated_cfo_hz"] == 0.0
    assert summary["cfo_estimator"] == "forced-bad/rejected"


def test_mid_pilot_linear_phase_tracking_recovers_symbol_block():
    cfo_len = 8
    sync_len = 8
    mid_len = 4
    block_len = 12
    data = (
        np.linspace(-0.8, 0.9, num=block_len * 2, dtype=np.float32)[0::2]
        + 1j * np.linspace(0.7, -0.6, num=block_len * 2, dtype=np.float32)[1::2]
    ).astype(np.complex64)
    manifest = {
        "cfo_pilot_symbols": cfo_len,
        "sync_pilot_symbols": sync_len,
        "mid_pilot_symbols": mid_len,
        "data_block_symbols": block_len,
        "data_block_lengths": [block_len, block_len],
        "cfo_seed": 1001,
        "sync_seed": 1002,
        "mid_pilot_seed": 1003,
    }
    cfo = analog.make_pilot_symbols(cfo_len, 1001)
    sync = analog.make_pilot_symbols(sync_len, 1002)
    mid = analog.make_pilot_symbols(mid_len, 1003)
    gain0 = 0.72 * np.exp(1j * np.deg2rad(18.0))
    gain1 = 0.92 * np.exp(1j * np.deg2rad(78.0))

    alpha = (np.arange(block_len, dtype=np.float32) + 1.0) / np.float32(block_len + 1.0)
    phase0 = np.angle(gain0)
    phase1 = phase0 + np.angle(gain1 / gain0)
    amp = (1.0 - alpha) * abs(gain0) + alpha * abs(gain1)
    gain_track = amp * np.exp(1j * ((1.0 - alpha) * phase0 + alpha * phase1))

    sym_stream = np.concatenate(
        [
            cfo * gain0,
            cfo * gain0,
            sync * gain0,
            data * gain_track.astype(np.complex64),
            mid * gain1,
            data * gain1,
        ]
    ).astype(np.complex64)

    recovered, metrics = analog.recover_payload_symbols(sym_stream, 2 * cfo_len, manifest)

    assert metrics["phase_tracking_mode"] == "linear-mid-pilot"
    assert metrics["phase_corrections"][0]["end_phase_deg"] > metrics["phase_corrections"][0]["start_phase_deg"]
    np.testing.assert_allclose(recovered[:block_len], data, rtol=2.0e-5, atol=2.0e-5)
    np.testing.assert_allclose(recovered[block_len:], data, rtol=2.0e-5, atol=2.0e-5)
