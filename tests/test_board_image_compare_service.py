from __future__ import annotations

import json
import threading
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from scripts.board_image_compare.core import GateDecision, ResourceSnapshot
from scripts.board_image_compare.remote import RemoteJob
from scripts.board_image_compare.service import (
    ComparisonConfig,
    ComparisonServiceState,
    create_http_server,
)


class FakeRemote:
    def __init__(self, reconstruction: Path) -> None:
        self.reconstruction = reconstruction
        self.download_calls: list[str] = []
        self.closed = False

    def list_jobs(self, remote_root: str):
        return [
            RemoteJob("new", "job-new", f"{remote_root}/job-new/reconstructions", 300.0),
            RemoteJob("old", "job-old", f"{remote_root}/job-old/reconstructions", 100.0),
        ]

    def list_job_images(self, job_path: str):
        return [PurePosixPath(f"{job_path}/00000000_recon.png")]

    def ensure_resources_available(self, gate):
        snapshot = ResourceSnapshot(cpu_percent=10.0, memory_percent=20.0)
        return snapshot, GateDecision("allow", "test")

    def download(self, remote_path: str, local_path: Path, callback=None) -> None:
        self.download_calls.append(remote_path)
        local_path.write_bytes(self.reconstruction.read_bytes())
        if callback:
            callback(local_path.stat().st_size, local_path.stat().st_size)

    def close(self) -> None:
        self.closed = True


def write_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (8, 8), color).save(path)


def configured_state(tmp_path: Path) -> tuple[ComparisonServiceState, FakeRemote]:
    originals = tmp_path / "originals"
    originals.mkdir()
    write_image(originals / "frame_0000.png", (12, 30, 60))
    reconstruction = tmp_path / "reconstruction.png"
    write_image(reconstruction, (12, 30, 60))
    remote = FakeRemote(reconstruction)
    state = ComparisonServiceState(
        cache_root=tmp_path / "cache",
        remote_factory=lambda _config: remote,
    )
    state.configure(
        ComparisonConfig(
            board_host="board-a",
            board_user="user",
            board_password="user",
            board_port=22,
            original_dir=originals,
            remote_root="/outputs",
        )
    )
    return state, remote


def test_listing_and_selecting_job_do_not_download(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)

    jobs = state.list_jobs()
    detail = state.job_detail("new")

    assert [job["name"] for job in jobs] == ["job-new", "job-old"]
    assert detail["pair_count"] == 1
    assert remote.download_calls == []
    state.close()


def test_pull_downloads_requested_image_and_reuses_cache(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    state.list_jobs()
    state.job_detail("new")

    first = state.pull("new", 0)
    second = state.pull("new", 0)

    assert first["cached"] is False
    assert second["cached"] is True
    assert len(remote.download_calls) == 1
    state.close()


def test_quality_assistance_defaults_to_disabled(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)

    assert state.public_state()["quality_assistance"] is False
    state.close()


def test_http_uncached_reconstruction_returns_404_without_download(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    state.list_jobs()
    state.job_detail("new")
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/image/reconstruction?job_id=new&index=0"

    try:
        try:
            urlopen(url, timeout=2)
            raise AssertionError("uncached reconstruction unexpectedly returned 200")
        except HTTPError as error:
            assert error.code == 404
        assert remote.download_calls == []
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_http_page_exposes_two_previews_and_quality_switch(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        body = urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=2).read().decode()
        assert 'id="original-preview"' in body
        assert 'id="reconstruction-preview"' in body
        assert 'id="quality-assistance"' in body
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_config_endpoint_does_not_return_password(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        response = urlopen(f"http://127.0.0.1:{server.server_port}/api/config", timeout=2)
        payload = json.loads(response.read())
        assert payload["board_host"] == "board-a"
        assert "password" not in json.dumps(payload).lower()
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_http_pull_serializes_infinite_psnr_as_valid_json(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    state.list_jobs()
    state.job_detail("new")
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request = Request(
        f"http://127.0.0.1:{server.server_port}/api/pull",
        data=json.dumps({"job_id": "new", "index": 0}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        payload = json.loads(urlopen(request, timeout=2).read())
        assert payload["quality"]["psnr_db"] == "Infinity"
    finally:
        server.shutdown()
        server.server_close()
        state.close()
