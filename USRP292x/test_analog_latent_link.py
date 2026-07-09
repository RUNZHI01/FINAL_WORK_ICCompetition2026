#!/usr/bin/env python3
"""Regression tests for the analog latent-IQ USRP path."""

import json
import subprocess
import sys
import threading
from argparse import Namespace
from pathlib import Path

import numpy as np
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ANALOG_LINK = PROJECT_ROOT / "USRP292x" / "AnalogLatentLink.py"
ANALOG_BATCH = PROJECT_ROOT / "USRP292x" / "RunAnalogLatentBatch.py"

from USRP292x import AnalogLatentLink as analog  # noqa: E402
from USRP292x import RunAnalogLatentBatch as analog_batch  # noqa: E402


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
    assert manifest_data["payload_is_bit_exact"] is False
    assert recovered.shape == latent.shape
    assert out_wire.is_file()
    assert float(np.mean(np.square(recovered - latent))) < 5.0e-4


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
        "python3",
        "/home/user/USRP292x/AnalogLatentLink.py",
    ]
    assert "--sync-search-center-symbol" not in argv
    assert "--sync-search-window-symbols" in argv
    assert argv.count("--sync-search-window-symbols") == 1
    window_index = argv.index("--sync-search-window-symbols") + 1
    assert argv[window_index] == "4096"


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
            "rx_capture_wall_sec": 0.030,
            "decode_wall_sec": 0.060,
            "remote_dir_publish_wall_sec": 0.004,
            "retry_wait_wall_sec": 0.0,
            "total_wall_sec": 0.120,
        }
    )
    image_b.records.append(
        {
            "tx_wall_sec": 0.020,
            "rx_capture_wall_sec": 0.050,
            "decode_wall_sec": 0.080,
            "remote_dir_publish_wall_sec": 0.006,
            "retry_wait_wall_sec": 0.020,
            "total_wall_sec": 0.180,
        }
    )

    benchmark = analog_batch.build_iq_stage_benchmark([image_a, image_b])

    assert benchmark["tx_control_ms"]["median_ms"] == 15.0
    assert benchmark["rx_capture_ms"]["p95_ms"] == 50.0
    assert benchmark["remote_decode_ms"]["mean_ms"] == 70.0
    assert benchmark["remote_dir_publish_ms"]["median_ms"] == 5.0
    assert benchmark["retry_wait_ms"]["max_ms"] == 20.0
    assert benchmark["total_transport_ms"]["median_ms"] == 150.0


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
