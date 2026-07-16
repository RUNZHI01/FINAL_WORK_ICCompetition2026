from __future__ import annotations

import io
from pathlib import Path

import pytest

from scripts.board_image_compare.core import ResourceGate
from scripts.board_image_compare.remote import (
    BoardConnectionConfig,
    BoardSftpClient,
    ImageCache,
    ResourceAborted,
    calculate_cpu_percent,
    parse_meminfo_percent,
)


class FakeChannel:
    def recv_exit_status(self) -> int:
        return 0


class FakeStream(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.channel = FakeChannel()


class FakeSftp:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.download_calls: list[str] = []

    def get(self, remote: str, local: str, callback=None) -> None:
        self.download_calls.append(remote)
        payload = self.files[remote]
        Path(local).write_bytes(payload)
        if callback:
            callback(len(payload), len(payload))

    def close(self) -> None:
        return


class FakeSsh:
    def __init__(self, outputs: list[str], sftp: FakeSftp | None = None) -> None:
        self.outputs = list(outputs)
        self.sftp = sftp or FakeSftp()
        self.commands: list[str] = []

    def exec_command(self, command: str, timeout=None):
        self.commands.append(command)
        output = self.outputs.pop(0)
        return io.BytesIO(), FakeStream(output.encode()), FakeStream(b"")

    def open_sftp(self) -> FakeSftp:
        return self.sftp

    def close(self) -> None:
        return


def config() -> BoardConnectionConfig:
    return BoardConnectionConfig(host="board-a", user="user", password="user", port=22)


def test_jobs_are_newest_first() -> None:
    ssh = FakeSsh(
        [
            "100.0\t/outputs/job-old/reconstructions\n"
            "300.0\t/outputs/job-new/reconstructions\n"
        ]
    )
    client = BoardSftpClient(config(), ssh_factory=lambda _: ssh)

    jobs = client.list_jobs("/outputs")

    assert [job.name for job in jobs] == ["job-new", "job-old"]
    assert jobs[0].path == "/outputs/job-new/reconstructions"


def test_cache_key_includes_host_and_job(tmp_path: Path) -> None:
    cache = ImageCache(tmp_path)

    first = cache.path_for("board-a", "/a/job", "/a/job/x.png")
    second = cache.path_for("board-a", "/b/job", "/b/job/x.png")

    assert first != second
    assert first.name == "x.png"


def test_atomic_download_promotes_completed_file(tmp_path: Path) -> None:
    sftp = FakeSftp()
    sftp.files["/remote/x.png"] = b"complete-image"
    ssh = FakeSsh([], sftp)
    client = BoardSftpClient(config(), ssh_factory=lambda _: ssh)
    cache = ImageCache(tmp_path)
    target = cache.path_for("board-a", "/job", "/remote/x.png")

    result = cache.download_atomic(client, "/remote/x.png", target)

    assert result.read_bytes() == b"complete-image"
    assert not target.with_suffix(".png.partial").exists()


def test_aborted_download_removes_partial_file(tmp_path: Path) -> None:
    class AbortingSftp(FakeSftp):
        def get(self, remote: str, local: str, callback=None) -> None:
            Path(local).write_bytes(b"partial")
            raise ResourceAborted("resource hard limit")

    ssh = FakeSsh([], AbortingSftp())
    client = BoardSftpClient(config(), ssh_factory=lambda _: ssh)
    cache = ImageCache(tmp_path)
    target = cache.path_for("board-a", "/job", "/remote/x.png")

    with pytest.raises(ResourceAborted):
        cache.download_atomic(client, "/remote/x.png", target)

    assert not target.exists()
    assert not target.with_suffix(".png.partial").exists()


def test_proc_parsers_report_cpu_and_memory_percent() -> None:
    previous = "cpu  100 0 100 800 0 0 0 0 0 0"
    current = "cpu  150 0 150 900 0 0 0 0 0 0"
    meminfo = "MemTotal: 1000 kB\nMemAvailable: 350 kB\n"

    assert calculate_cpu_percent(previous, current) == pytest.approx(50.0)
    assert parse_meminfo_percent(meminfo) == pytest.approx(65.0)


def test_resource_guard_rejects_download_before_sftp_transfer() -> None:
    ssh = FakeSsh(
        [
            "cpu  100 0 100 800 0 0 0 0 0 0\nMemTotal: 1000 kB\nMemAvailable: 50 kB\n",
            "cpu  150 0 150 900 0 0 0 0 0 0\nMemTotal: 1000 kB\nMemAvailable: 50 kB\n",
        ]
    )
    client = BoardSftpClient(config(), ssh_factory=lambda _: ssh, sleep=lambda _: None)

    with pytest.raises(ResourceAborted):
        client.ensure_resources_available(ResourceGate())
