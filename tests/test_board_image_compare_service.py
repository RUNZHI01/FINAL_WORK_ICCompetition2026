from __future__ import annotations

import json
import threading
import time
from pathlib import Path, PurePosixPath
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image
import pytest

from scripts.board_image_compare.core import GateDecision, ResourceSnapshot
from scripts.board_image_compare.remote import RemoteJob
from scripts.board_image_compare.sources import ReconstructionSource
from scripts.board_image_compare.service import (
    ComparisonConfig,
    ComparisonServiceState,
    create_http_server,
)


class FakeRemote:
    def __init__(self, reconstruction: Path) -> None:
        self.reconstruction = reconstruction
        self.download_calls: list[str] = []
        self.listed_roots: list[str] = []
        self.resource_checks = 0
        self.closed = False

    def list_jobs(self, remote_root: str):
        self.listed_roots.append(remote_root)
        return [
            RemoteJob("new", "job-new", f"{remote_root}/job-new/reconstructions", 300.0),
            RemoteJob("old", "job-old", f"{remote_root}/job-old/reconstructions", 100.0),
        ]

    def list_job_images(self, job_path: str):
        return [PurePosixPath(f"{job_path}/00000000_recon.png")]

    def ensure_resources_available(self, gate):
        self.resource_checks += 1
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


def configured_state(
    tmp_path: Path,
    *,
    with_pytorch: bool = False,
    manifest_root: Path | None = None,
) -> tuple[ComparisonServiceState, FakeRemote]:
    originals = tmp_path / "originals"
    originals.mkdir()
    write_image(originals / "frame_0000.png", (12, 30, 60))
    reconstruction = tmp_path / "reconstruction.png"
    write_image(reconstruction, (12, 30, 60))
    remote = FakeRemote(reconstruction)
    pytorch_manifest = None
    if with_pytorch:
        pytorch_output = tmp_path / "pytorch_0000.png"
        write_image(pytorch_output, (22, 40, 70))
        pytorch_manifest = tmp_path / "pytorch_reference_manifest.json"
        pytorch_manifest.write_text(
            json.dumps(
                {
                    "records": [
                        {
                            "source_name": "frame_0000.png",
                            "output_path": str(pytorch_output),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
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
            sources=(
                ReconstructionSource("prerecorded-mnn", "Prerecorded MNN", "/prerecorded/mnn"),
                ReconstructionSource("usrp-qpsk", "USRP QPSK", "/usrp/qpsk/tvm"),
                ReconstructionSource("usrp-iq-direct", "USRP IQ direct", "/usrp/iq-direct/tvm"),
            ),
            default_source="usrp-iq-direct",
            manifest_root=manifest_root,
            pytorch_manifest=pytorch_manifest,
        )
    )
    return state, remote


def configured_http_state(tmp_path: Path):
    state, _ = configured_state(tmp_path)
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return state, server


def fetch_page_assets(configured_http):
    state, server = configured_http
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        body = urlopen(f"{base_url}/", timeout=2).read().decode()
        script = urlopen(f"{base_url}/app.js", timeout=2).read().decode()
        return body, script
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_listing_and_selecting_job_do_not_download(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)

    jobs = state.list_jobs("usrp-iq-direct")
    detail = state.job_detail("new")

    assert [job["name"] for job in jobs] == ["job-new", "job-old"]
    assert detail["pair_count"] == 1
    assert remote.download_calls == []
    state.close()


def test_jobs_are_scoped_to_requested_source(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)

    jobs = state.list_jobs("usrp-iq-direct")

    assert remote.listed_roots == ["/usrp/iq-direct/tvm"]
    assert [job["name"] for job in jobs] == ["job-new", "job-old"]
    state.close()


def test_unknown_source_is_rejected(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)

    with pytest.raises(ValueError, match="unknown reconstruction source"):
        state.list_jobs("not-a-source")
    state.close()


def test_missing_source_root_returns_empty_list(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    remote.list_jobs = Mock(side_effect=FileNotFoundError("missing"))

    assert state.list_jobs("prerecorded-mnn") == []
    state.close()


def test_switching_sources_clears_stale_job_selection(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    state.list_jobs("usrp-iq-direct")
    state.job_detail("new")
    remote.list_jobs = Mock(side_effect=FileNotFoundError("missing"))

    state.list_jobs("prerecorded-mnn")

    with pytest.raises(KeyError, match="unknown job"):
        state.job_detail("new")
    state.close()


def test_stale_source_listing_cannot_restore_old_jobs(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    state.configure(
        ComparisonConfig(
            board_host="board-a",
            board_user="user",
            board_password="user",
            board_port=22,
            original_dir=tmp_path / "originals",
            sources=(
                ReconstructionSource("source-a", "Source A", "/source-a"),
                ReconstructionSource("source-b", "Source B", "/source-b"),
            ),
            default_source="source-a",
        )
    )
    a_started = threading.Event()
    release_a = threading.Event()

    def list_jobs(remote_root: str):
        if remote_root == "/source-a":
            a_started.set()
            assert release_a.wait(timeout=2)
            return [RemoteJob("a", "job-a", "/source-a/job-a/reconstructions", 1.0)]
        return [RemoteJob("b", "job-b", "/source-b/job-b/reconstructions", 2.0)]

    remote.list_jobs = list_jobs
    thread = threading.Thread(target=lambda: state.list_jobs("source-a"))
    thread.start()
    assert a_started.wait(timeout=2)

    assert [job["id"] for job in state.list_jobs("source-b")] == ["b"]
    release_a.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
    with pytest.raises(KeyError, match="unknown job"):
        state.job_detail("a")
    assert state.job_detail("b")["job"]["id"] == "b"
    state.close()


def test_pull_downloads_requested_image_and_reuses_cache(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    state.list_jobs("usrp-iq-direct")
    state.job_detail("new")

    first = state.pull("new", 0)
    second = state.pull("new", 0)

    assert first["cached"] is False
    assert second["cached"] is True
    assert len(remote.download_calls) == 1
    assert remote.resource_checks == 2
    state.close()


def test_pull_does_not_prefetch_adjacent_images(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    write_image(state._config.original_dir / "frame_0001.png", (20, 40, 80))
    remote.list_job_images = lambda job_path: [
        PurePosixPath(f"{job_path}/00000000_recon.png"),
        PurePosixPath(f"{job_path}/00000001_recon.png"),
    ]
    state.list_jobs("usrp-iq-direct")
    state.job_detail("new")

    state.pull("new", 0)
    for _ in range(20):
        if len(remote.download_calls) > 1:
            break
        time.sleep(0.05)
    state.close()

    assert remote.download_calls == [
        "/usrp/iq-direct/tvm/job-new/reconstructions/00000000_recon.png"
    ]


def test_quality_assistance_defaults_to_disabled(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)

    assert state.public_state()["quality_assistance"] is False
    state.close()


def test_pytorch_reference_mode_uses_manifest_mapping(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path, with_pytorch=True)
    state.list_jobs("usrp-iq-direct")
    state.job_detail("new")

    path = state.reference_path("new", 0, "pytorch")

    assert path.name == "pytorch_0000.png"
    state.close()


def test_historical_usrp_job_uses_nested_round_manifest_for_original_and_quality(tmp_path: Path) -> None:
    manifest_root = tmp_path / "runs"
    image_dir = manifest_root / "cockpit_usrp_usrp-123" / "round_0001" / "image_0"
    image_dir.mkdir(parents=True)
    (image_dir / "manifest.json").write_text(
        json.dumps({"source_info": {"source_meta": {"original_filename": "zeta.png"}}}),
        encoding="utf-8",
    )
    state, remote = configured_state(tmp_path, manifest_root=manifest_root)
    write_image(state._config.original_dir / "zeta.png", (12, 30, 60))
    write_image(state._config.original_dir / "frame_0000.png", (80, 20, 40))
    remote.list_jobs = lambda remote_root: [
        RemoteJob("historical", "openamp3_usrp_123_current", f"{remote_root}/historic/reconstructions", 300.0)
    ]

    state.list_jobs("usrp-iq-direct")
    detail = state.job_detail("historical")
    result = state.pull("historical", 0)

    assert detail["pairs"][0]["original_name"] == "zeta.png"
    assert detail["pairs"][0]["original_available"] is True
    assert result["quality"]["psnr_db"] == "Infinity"
    state.close()


def test_historical_usrp_job_keeps_direct_image_manifest_support(tmp_path: Path) -> None:
    manifest_root = tmp_path / "runs"
    image_dir = manifest_root / "cockpit_usrp_usrp-123" / "image_0"
    image_dir.mkdir(parents=True)
    (image_dir / "manifest.json").write_text(
        json.dumps({"source_info": {"source_meta": {"original_filename": "zeta.png"}}}),
        encoding="utf-8",
    )
    state, remote = configured_state(tmp_path, manifest_root=manifest_root)
    write_image(state._config.original_dir / "zeta.png", (12, 30, 60))
    remote.list_jobs = lambda remote_root: [
        RemoteJob("historical", "openamp3_usrp_123_current", f"{remote_root}/historic/reconstructions", 300.0)
    ]

    state.list_jobs("usrp-iq-direct")

    assert state.job_detail("historical")["pairs"][0]["original_name"] == "zeta.png"
    state.close()


def test_qpsk_job_uses_prepared_input_manifest_for_original_and_quality(tmp_path: Path) -> None:
    manifest_root = tmp_path / "runs"
    run_dir = manifest_root / "cockpit_usrp_usrp-123" / "prepared_usrp_inputs"
    run_dir.mkdir(parents=True)
    (run_dir / "usrp_input_manifest.json").write_text(
        json.dumps(
            {
                "files": [
                    {
                        "original_filename": "zeta",
                        "source_image_rel": "zeta.png",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    state, remote = configured_state(tmp_path, manifest_root=manifest_root)
    write_image(state._config.original_dir / "zeta.png", (12, 30, 60))
    write_image(state._config.original_dir / "frame_0000.png", (80, 20, 40))
    remote.list_jobs = lambda remote_root: [
        RemoteJob("qpsk", "openamp3_usrp_123_current", f"{remote_root}/openamp3_usrp_123_current", 300.0)
    ]

    state.list_jobs("usrp-qpsk")
    detail = state.job_detail("qpsk")
    result = state.pull("qpsk", 0, "original")

    assert detail["pairs"][0]["original_name"] == "zeta.png"
    assert detail["pairs"][0]["original_available"] is True
    assert result["quality"]["psnr_db"] == "Infinity"
    assert result["quality"]["ssim"] == 1.0
    state.close()


def test_prerecorded_job_never_uses_usrp_run_manifest(tmp_path: Path) -> None:
    manifest_root = tmp_path / "runs"
    image_dir = manifest_root / "cockpit_usrp_usrp-123" / "image_0"
    image_dir.mkdir(parents=True)
    (image_dir / "manifest.json").write_text(
        json.dumps({"source_info": {"source_meta": {"original_filename": "zeta.png"}}}),
        encoding="utf-8",
    )
    state, _ = configured_state(tmp_path, manifest_root=manifest_root)
    write_image(state._config.original_dir / "zeta.png", (80, 20, 40))

    state.list_jobs("prerecorded-mnn")

    assert state.job_detail("new")["pairs"][0]["original_name"] == "frame_0000.png"
    state.close()


def test_unmatched_usrp_job_never_uses_another_runs_manifest(tmp_path: Path) -> None:
    manifest_root = tmp_path / "runs"
    image_dir = manifest_root / "cockpit_usrp_usrp-123" / "image_0"
    image_dir.mkdir(parents=True)
    (image_dir / "manifest.json").write_text(
        json.dumps({"source_info": {"source_meta": {"original_filename": "zeta.png"}}}),
        encoding="utf-8",
    )
    state, remote = configured_state(tmp_path, manifest_root=manifest_root)
    write_image(state._config.original_dir / "zeta.png", (80, 20, 40))
    remote.list_jobs = lambda remote_root: [
        RemoteJob("unmatched", "openamp3_usrp_999_current", f"{remote_root}/unmatched/reconstructions", 300.0)
    ]

    state.list_jobs("usrp-iq-direct")

    assert state.job_detail("unmatched")["pairs"][0]["original_name"] == "frame_0000.png"
    state.close()


def test_missing_pytorch_reference_does_not_fall_back(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    state.list_jobs("usrp-iq-direct")
    state.job_detail("new")

    try:
        state.reference_path("new", 0, "pytorch")
        raise AssertionError("missing PyTorch reference unexpectedly fell back")
    except FileNotFoundError as error:
        assert "PyTorch" in str(error)
    finally:
        state.close()


def test_quality_cache_is_isolated_by_reference_mode(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path, with_pytorch=True)
    state.list_jobs("usrp-iq-direct")
    state.job_detail("new")

    original = state.pull("new", 0, reference_mode="original")
    pytorch = state.pull("new", 0, reference_mode="pytorch")

    assert original["quality"]["psnr_db"] == "Infinity"
    assert pytorch["quality"]["psnr_db"] != "Infinity"
    assert "new:0:original" in state.public_state()["quality"]
    assert "new:0:pytorch" in state.public_state()["quality"]
    state.close()


def test_http_uncached_reconstruction_returns_404_without_download(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    state.list_jobs("usrp-iq-direct")
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
        assert 'data-reference-mode="original"' in body
        assert 'data-reference-mode="pytorch"' in body
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_http_page_exposes_reconstruction_source_selector(tmp_path: Path) -> None:
    body, script = fetch_page_assets(configured_http_state(tmp_path))

    assert 'id="reconstruction-source"' in body
    assert "sourceSelect.addEventListener('change'" in script
    assert "/api/jobs?source=" in script


def test_http_page_ignores_job_details_from_previous_source(tmp_path: Path) -> None:
    _, script = fetch_page_assets(configured_http_state(tmp_path))

    detail_request = script.index("const detail = await requestJson(`/api/job?id=${encodeURIComponent(jobId)}`)")
    stale_guard = script.index("if (!isCurrentJobRequest(sourceEpoch, sourceId, jobId)) return", detail_request)
    detail_assignment = script.index("state.detail = detail", detail_request)
    assert stale_guard < detail_assignment


def test_http_page_invalidates_stale_source_job_and_pull_requests(tmp_path: Path) -> None:
    _, script = fetch_page_assets(configured_http_state(tmp_path))

    assert "sourceEpoch: 0" in script
    assert "state.sourceEpoch += 1" in script
    assert "state.quality = {}" in script
    assert "function isCurrentSourceRequest(sourceEpoch, sourceId)" in script
    assert "function isCurrentJobRequest(sourceEpoch, sourceId, jobId)" in script
    assert "function isCurrentPullRequest(request)" in script
    assert "if (!isCurrentSourceRequest(sourceEpoch, sourceId)) return" in script
    assert "if (!isCurrentJobRequest(sourceEpoch, sourceId, jobId)) return" in script
    assert "if (!isCurrentPullRequest(request)) return" in script
    assert "sourceEpoch: state.sourceEpoch" in script
    assert "sourceId: state.sourceId" in script
    assert "jobId: currentJobId()" in script
    assert "index: state.index" in script
    assert "referenceMode: state.referenceMode" in script
    assert "pair === currentPair()" in script
    assert "state.quality[`${jobId}:${index}:${referenceMode}`] = payload.quality" in script


def test_http_page_ignores_stale_poll_state_responses(tmp_path: Path) -> None:
    _, script = fetch_page_assets(configured_http_state(tmp_path))

    poll_start = script.index("async function pollState()")
    state_request = script.index("const payload = await requestJson('/api/state')", poll_start)
    source_epoch = script.index("const sourceEpoch = state.sourceEpoch", poll_start)
    source_id = script.index("const sourceId = state.sourceId", poll_start)
    success_guard = script.index("if (!sourceReady || !isCurrentSourceRequest(sourceEpoch, sourceId)) return", state_request)
    quality_update = script.index("state.quality = payload.quality || {}", state_request)
    error_guard = script.index("if (!sourceReady || !isCurrentSourceRequest(sourceEpoch, sourceId)) return", success_guard + 1)
    status_update = script.index("elements.serviceStatus.textContent", error_guard)

    assert source_epoch < state_request
    assert source_id < state_request
    assert success_guard < quality_update
    assert error_guard < status_update


def test_http_page_requires_source_ready_before_applying_poll_state(tmp_path: Path) -> None:
    _, script = fetch_page_assets(configured_http_state(tmp_path))

    reset_start = script.index("function resetSelectedJob()")
    poll_start = script.index("async function pollState()")
    jobs_start = script.index("async function loadJobs()")
    source_guard = script.index("if (!isCurrentSourceRequest(sourceEpoch, sourceId)) return", jobs_start)
    jobs_apply = script.index("state.jobs = payload.jobs", jobs_start)
    state_request = script.index("const payload = await requestJson('/api/state')", poll_start)
    ready_capture = script.index("const sourceReady = state.sourceReady", poll_start)
    success_guard = script.index("if (!sourceReady || !isCurrentSourceRequest(sourceEpoch, sourceId)) return", state_request)
    quality_update = script.index("state.quality = payload.quality || {}", state_request)
    error_guard = script.index("if (!sourceReady || !isCurrentSourceRequest(sourceEpoch, sourceId)) return", success_guard + 1)
    status_update = script.index("elements.serviceStatus.textContent", error_guard)

    assert "sourceReady: false" in script
    assert "state.sourceReady = false" in script[reset_start:poll_start]
    assert source_guard < script.index("state.sourceReady = true", jobs_start) < jobs_apply
    assert ready_capture < state_request
    assert success_guard < quality_update
    assert error_guard < status_update


def test_http_page_renders_current_image_quality_metrics(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        body = urlopen(f"{base_url}/", timeout=2).read().decode()
        script = urlopen(f"{base_url}/app.js", timeout=2).read().decode()
        styles = urlopen(f"{base_url}/styles.css", timeout=2).read().decode()
        assert 'id="quality-psnr"' in body
        assert 'id="quality-ssim"' in body
        assert "qualityPsnr" in script
        assert "psnr.toFixed(2)" in script
        assert "ssim.toFixed(4)" in script
        assert ".image-stage { position: relative; overflow: hidden;" in styles
        assert ".image-stage img { position: absolute; inset: 0;" in styles
        mobile_styles = styles[styles.index("@media (max-width: 900px)"):]
        assert ".job-controls #reconstruction-source { width: 100%; }" in mobile_styles
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


def test_http_config_parses_sources_and_exposes_public_source_fields(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request = Request(
        f"http://127.0.0.1:{server.server_port}/api/config",
        data=json.dumps(
            {
                "board_host": "board-a",
                "board_user": "user",
                "board_password": "secret",
                "board_port": 22,
                "original_dir": str(tmp_path / "originals"),
                "sources": [
                    {
                        "id": "usrp-iq-direct",
                        "label": "USRP IQ direct",
                        "remote_root": "/usrp/iq-direct/tvm",
                        "include_prefixes": [],
                        "exclude_prefixes": [],
                    }
                ],
                "default_source": "usrp-iq-direct",
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        payload = json.loads(urlopen(request, timeout=2).read())
        assert payload["sources"] == [
            {"id": "usrp-iq-direct", "label": "USRP IQ direct", "remote_root": "/usrp/iq-direct/tvm"}
        ]
        assert payload["default_source"] == "usrp-iq-direct"
        assert "password" not in json.dumps(payload).lower()
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_http_config_rejects_blank_source_id(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request = Request(
        f"http://127.0.0.1:{server.server_port}/api/config",
        data=json.dumps(
            {
                "board_host": "board-a",
                "board_user": "user",
                "board_port": 22,
                "original_dir": str(tmp_path / "originals"),
                "sources": [{"id": "", "label": "Blank", "remote_root": "/blank"}],
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with pytest.raises(HTTPError) as error:
            urlopen(request, timeout=2)
        assert error.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_http_jobs_reject_unknown_source_and_return_empty_for_missing_root(tmp_path: Path) -> None:
    state, remote = configured_state(tmp_path)
    remote.list_jobs = Mock(side_effect=FileNotFoundError("missing"))
    server = create_http_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{server.server_port}/api/jobs?source=unknown", timeout=2)
        assert error.value.code == 400
        payload = json.loads(
            urlopen(f"http://127.0.0.1:{server.server_port}/api/jobs?source=prerecorded-mnn", timeout=2).read()
        )
        assert payload == {"jobs": []}
    finally:
        server.shutdown()
        server.server_close()
        state.close()


def test_http_pull_serializes_infinite_psnr_as_valid_json(tmp_path: Path) -> None:
    state, _ = configured_state(tmp_path)
    state.list_jobs("usrp-iq-direct")
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
