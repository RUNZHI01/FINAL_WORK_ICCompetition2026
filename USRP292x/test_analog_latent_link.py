#!/usr/bin/env python3
"""Regression tests for the analog latent-IQ USRP path."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ANALOG_LINK = PROJECT_ROOT / "USRP292x" / "AnalogLatentLink.py"
ANALOG_BATCH = PROJECT_ROOT / "USRP292x" / "RunAnalogLatentBatch.py"

from USRP292x import AnalogLatentLink as analog  # noqa: E402


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
    assert manifest_data["payload_is_bit_exact"] is False
    assert recovered.shape == latent.shape
    assert out_wire.is_file()
    assert float(np.mean(np.square(recovered - latent))) < 5.0e-4


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
