#!/usr/bin/env python3
"""Regression tests for the QPSK batch-spool runner."""

from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from USRP292x import RunQpskFileBatchSpoolArq as qpsk_batch  # noqa: E402


def test_tx_control_file_path_maps_workspace_path_to_container_mount(tmp_path):
    repo_root = tmp_path / "repo"
    tx_file = repo_root / "USRP292x" / "qpsk_batch_spool_arq_runs" / "run1" / "batch_tx.sc16"

    mapped = qpsk_batch.translate_tx_control_file_path(tx_file, str(repo_root), "/host_workspace")

    assert mapped == "/host_workspace/USRP292x/qpsk_batch_spool_arq_runs/run1/batch_tx.sc16"


def test_tx_control_file_path_without_prefix_uses_original_path(tmp_path):
    tx_file = tmp_path / "run1" / "batch_tx.sc16"

    mapped = qpsk_batch.translate_tx_control_file_path(tx_file, "", "")

    assert mapped == str(tx_file)


def test_tar_directory_bytes_round_trips_nested_files(tmp_path):
    source = tmp_path / "source"
    nested = source / "000"
    nested.mkdir(parents=True)
    (nested / "manifest.json").write_text('{"ok": true}', encoding="utf-8")
    (nested / "reference.bin").write_bytes(b"abc")
    destination = tmp_path / "destination"

    payload = qpsk_batch.tar_directory_bytes(source)
    qpsk_batch.extract_tar_bytes(payload, destination)

    assert (destination / "000" / "manifest.json").read_text(encoding="utf-8") == '{"ok": true}'
    assert (destination / "000" / "reference.bin").read_bytes() == b"abc"


def test_push_directory_to_remote_uses_ssh_stdin_without_shell(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text("{}", encoding="utf-8")
    expected_payload = qpsk_batch.tar_directory_bytes(source)
    completed = subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=b"", stderr=b"")

    with patch.object(qpsk_batch.subprocess, "run", return_value=completed) as run:
        qpsk_batch.push_directory_to_remote(
            source,
            target="user@board",
            remote_dir="/tmp/decode",
            log_path=tmp_path / "push.log",
            control_socket=None,
        )

    command = run.call_args.args[0]
    kwargs = run.call_args.kwargs
    assert command[-2:] == ["user@board", "mkdir -p /tmp/decode && cd /tmp/decode && tar xf -"]
    assert kwargs["input"] == expected_payload
    assert kwargs["shell"] is False


def test_ssh_base_args_uses_docker_runner_when_requested(monkeypatch):
    monkeypatch.setenv("OPENAMP_SSH_RUNNER", "docker")
    monkeypatch.setenv("OPENAMP_SSH_DOCKER_IMAGE", "iccomp-usrp-tx:latest")

    args = qpsk_batch._ssh_base_args(timeout=30)

    assert args[:6] == ["docker", "run", "--rm", "-i", "-e", "SSHPASS"]
    assert "iccomp-usrp-tx:latest" in args
    assert args[-4:] == ["-o", "ConnectTimeout=30", "-o", "PreferredAuthentications=password,keyboard-interactive"]
