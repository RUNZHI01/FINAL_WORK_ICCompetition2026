from __future__ import annotations

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import ssh_with_password_paramiko  # noqa: E402


class FakeChannel:
    def __init__(self, exit_status: int) -> None:
        self._exit_status = exit_status
        self.shutdown_write_called = False

    def shutdown_write(self) -> None:
        self.shutdown_write_called = True

    def recv_exit_status(self) -> int:
        return self._exit_status


class FakeStdin:
    def __init__(self) -> None:
        self.buffer = b""
        self.channel = FakeChannel(0)
        self.closed = False

    def write(self, data: bytes) -> int:
        self.buffer += data
        return len(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class FakeStream:
    def __init__(self, data: bytes, exit_status: int = 0) -> None:
        self._data = data
        self.channel = FakeChannel(exit_status)

    def read(self) -> bytes:
        return self._data


class FakePollingChannel:
    def __init__(self, *, stdout_chunks: list[bytes], stderr_chunks: list[bytes], exit_status: int) -> None:
        self.stdout_chunks = list(stdout_chunks)
        self.stderr_chunks = list(stderr_chunks)
        self.exit_status = exit_status

    def recv_ready(self) -> bool:
        return bool(self.stdout_chunks)

    def recv(self, _size: int) -> bytes:
        return self.stdout_chunks.pop(0)

    def recv_stderr_ready(self) -> bool:
        return bool(self.stderr_chunks)

    def recv_stderr(self, _size: int) -> bytes:
        return self.stderr_chunks.pop(0)

    def exit_status_ready(self) -> bool:
        return True

    def recv_exit_status(self) -> int:
        return self.exit_status


class NoReadStream:
    def __init__(self, channel: FakePollingChannel) -> None:
        self.channel = channel

    def read(self) -> bytes:
        raise AssertionError("polling channel path should not block on read()")


class SshWithPasswordParamikoTest(unittest.TestCase):
    def test_parse_args_defaults_to_long_timeout_for_tvm_pipeline(self) -> None:
        with patch.dict("ssh_with_password_paramiko.os.environ", {}, clear=True):
            args = ssh_with_password_paramiko.parse_args(
                [
                    "--host",
                    "demo-board",
                    "--user",
                    "demo-user",
                    "--pass-env",
                    "SSH_PASS",
                    "--",
                    "echo ok",
                ]
            )

        self.assertEqual(args.timeout_sec, 900)

    def test_run_remote_command_writes_stdin_and_returns_remote_exit_status(self) -> None:
        fake_client = Mock()
        fake_stdin = FakeStdin()
        fake_stdout = FakeStream(b"remote stdout\n", exit_status=7)
        fake_stderr = FakeStream(b"remote stderr\n")
        fake_client.exec_command.return_value = (fake_stdin, fake_stdout, fake_stderr)

        with (
            patch("ssh_with_password_paramiko.paramiko.SSHClient", return_value=fake_client),
            patch("ssh_with_password_paramiko.sys.stdout", io.TextIOWrapper(io.BytesIO(), encoding="utf-8")),
            patch("ssh_with_password_paramiko.sys.stderr", io.TextIOWrapper(io.BytesIO(), encoding="utf-8")),
        ):
            rc = ssh_with_password_paramiko.run_remote_command(
                host="demo-board",
                user="demo-user",
                password="demo-secret",
                port=2202,
                command="cat > /tmp/demo",
                stdin_bytes=b"payload\n",
                timeout_sec=12.5,
            )

        self.assertEqual(rc, 7)
        fake_client.set_missing_host_key_policy.assert_called()
        fake_client.connect.assert_called_once_with(
            hostname="demo-board",
            port=2202,
            username="demo-user",
            password="demo-secret",
            timeout=12.5,
            banner_timeout=12.5,
            auth_timeout=12.5,
            look_for_keys=False,
            allow_agent=False,
        )
        fake_client.exec_command.assert_called_once_with(
            "cat > /tmp/demo",
            get_pty=False,
            timeout=12.5,
        )
        self.assertEqual(fake_stdin.buffer, b"payload\n")
        self.assertTrue(fake_stdin.channel.shutdown_write_called)
        self.assertTrue(fake_stdin.closed)
        fake_client.close.assert_called_once()

    def test_collect_remote_result_uses_exit_status_polling_without_waiting_for_eof(self) -> None:
        channel = FakePollingChannel(
            stdout_chunks=[b"daemon started\n"],
            stderr_chunks=[b"warn\n"],
            exit_status=0,
        )

        rc, stdout_bytes, stderr_bytes = ssh_with_password_paramiko.collect_remote_result(
            NoReadStream(channel),
            NoReadStream(channel),
            timeout_sec=1.0,
        )

        self.assertEqual(rc, 0)
        self.assertEqual(stdout_bytes, b"daemon started\n")
        self.assertEqual(stderr_bytes, b"warn\n")


if __name__ == "__main__":
    unittest.main()
