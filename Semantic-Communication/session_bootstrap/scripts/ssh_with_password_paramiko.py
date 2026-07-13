#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import sys
import time

import paramiko


def _write_bytes(stream: object, data: bytes) -> None:
    if not data:
        return
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
        return
    text = data.decode("utf-8", errors="replace")
    stream.write(text)  # type: ignore[attr-defined]
    stream.flush()  # type: ignore[attr-defined]


def collect_remote_result(stdout: object, stderr: object, *, timeout_sec: float) -> tuple[int, bytes, bytes]:
    channel = getattr(stdout, "channel", None)
    if not all(
        hasattr(channel, name)
        for name in ("exit_status_ready", "recv_exit_status", "recv_ready", "recv", "recv_stderr_ready", "recv_stderr")
    ):
        stdout_bytes = stdout.read()  # type: ignore[attr-defined]
        stderr_bytes = stderr.read()  # type: ignore[attr-defined]
        return int(stdout.channel.recv_exit_status()), stdout_bytes, stderr_bytes  # type: ignore[attr-defined]

    deadline = time.monotonic() + max(1.0, timeout_sec)
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    while True:
        while channel.recv_ready():
            stdout_chunks.append(channel.recv(65536))
        while channel.recv_stderr_ready():
            stderr_chunks.append(channel.recv_stderr(65536))
        if channel.exit_status_ready():
            exit_status = int(channel.recv_exit_status())
            while channel.recv_ready():
                stdout_chunks.append(channel.recv(65536))
            while channel.recv_stderr_ready():
                stderr_chunks.append(channel.recv_stderr(65536))
            return exit_status, b"".join(stdout_chunks), b"".join(stderr_chunks)
        if time.monotonic() >= deadline:
            raise TimeoutError(f"remote command did not finish within {timeout_sec:.1f}s")
        time.sleep(0.02)


def run_remote_command(
    *,
    host: str,
    user: str,
    password: str,
    port: int,
    command: str,
    stdin_bytes: bytes,
    timeout_sec: float,
) -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=user,
            password=password,
            timeout=timeout_sec,
            banner_timeout=timeout_sec,
            auth_timeout=timeout_sec,
            look_for_keys=False,
            allow_agent=False,
        )
        stdin, stdout, stderr = client.exec_command(
            command,
            get_pty=False,
            timeout=timeout_sec,
        )
        try:
            if stdin_bytes:
                stdin.write(stdin_bytes)
                stdin.flush()
            try:
                stdin.channel.shutdown_write()
            except Exception:
                pass
        finally:
            try:
                stdin.close()
            except Exception:
                pass

        exit_status, stdout_bytes, stderr_bytes = collect_remote_result(stdout, stderr, timeout_sec=timeout_sec)
        _write_bytes(sys.stdout, stdout_bytes)
        _write_bytes(sys.stderr, stderr_bytes)
        return exit_status
    finally:
        client.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one SSH command with a password via Paramiko.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--pass-env", required=True, help="Environment variable containing the SSH password.")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--timeout-sec", type=float, default=float(os.environ.get("OPENAMP_SSH_TIMEOUT_SEC", "900")))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    command_parts = list(args.command)
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        print("ERROR: remote command is required after --", file=sys.stderr)
        return 2
    password = os.environ.get(args.pass_env, "")
    if not password:
        print(f"ERROR: password env {args.pass_env} is empty", file=sys.stderr)
        return 2
    command = command_parts[0] if len(command_parts) == 1 else shlex.join(command_parts)
    stdin_bytes = sys.stdin.buffer.read()
    return run_remote_command(
        host=str(args.host),
        user=str(args.user),
        password=password,
        port=int(args.port),
        command=command,
        stdin_bytes=stdin_bytes,
        timeout_sec=float(args.timeout_sec),
    )


if __name__ == "__main__":
    raise SystemExit(main())
