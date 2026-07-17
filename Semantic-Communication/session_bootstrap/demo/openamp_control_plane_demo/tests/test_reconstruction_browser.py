from __future__ import annotations

from pathlib import Path
import subprocess
import sys


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from reconstruction_browser import ReconstructionBrowserConfig, ReconstructionBrowserManager


class FakeProcess:
    def __init__(self) -> None:
        self.running = True
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self.running else 0

    def terminate(self) -> None:
        self.terminated = True
        self.running = False

    def wait(self, timeout=None) -> int:
        return 0

    def kill(self) -> None:
        self.killed = True
        self.running = False


def config(tmp_path: Path) -> ReconstructionBrowserConfig:
    originals = tmp_path / "originals"
    originals.mkdir(exist_ok=True)
    return ReconstructionBrowserConfig(
        board_host="board-a",
        board_user="user",
        board_password="user",
        board_port=22,
        original_dir=originals,
        sources=(
            {
                "id": "prerecorded-tvm",
                "label": "Prerecorded TVM",
                "remote_root": "/prerecorded/tvm",
                "include_prefixes": [],
                "exclude_prefixes": ["pytorch_reference_reconstruction_"],
            },
            {
                "id": "usrp-iq-direct",
                "label": "USRP IQ direct",
                "remote_root": "/usrp/iq-direct/tvm",
                "include_prefixes": [],
                "exclude_prefixes": [],
            },
        ),
        default_source="usrp-iq-direct",
        manifest_root=tmp_path / "manifests",
    )


def test_open_reuses_healthy_process_and_reconfigures(tmp_path: Path) -> None:
    process = FakeProcess()
    process_calls: list[list[str]] = []
    configured_payloads: list[dict] = []
    healthy = False

    def process_factory(command: list[str]):
        nonlocal healthy
        process_calls.append(command)
        healthy = True
        return process

    def http_json(method: str, url: str, payload=None, timeout=1.0):
        if url.endswith("/api/health"):
            if not healthy:
                raise OSError("not started")
            return {"status": "ok"}
        configured_payloads.append(payload)
        return {"status": "ok"}

    manager = ReconstructionBrowserManager(
        script_path=tmp_path / "server.py",
        cache_root=tmp_path / "cache",
        process_factory=process_factory,
        http_json=http_json,
        sleep=lambda _: None,
    )

    assert manager.open(config(tmp_path)) == "http://127.0.0.1:8786/"
    assert manager.open(config(tmp_path)) == "http://127.0.0.1:8786/"
    assert len(process_calls) == 1
    assert len(configured_payloads) == 2
    assert configured_payloads[0]["board_password"] == "user"
    assert configured_payloads[0]["sources"] == list(config(tmp_path).sources)
    assert configured_payloads[0]["default_source"] == "usrp-iq-direct"
    assert "remote_root" not in configured_payloads[0]


def test_open_starts_comparison_service_as_module(tmp_path: Path) -> None:
    process = FakeProcess()
    process_calls: list[list[str]] = []
    healthy = False

    def process_factory(command: list[str]):
        nonlocal healthy
        process_calls.append(command)
        healthy = True
        return process

    def http_json(method: str, url: str, payload=None, timeout=1.0):
        if url.endswith("/api/health"):
            if not healthy:
                raise OSError("not started")
            return {"status": "ok"}
        return {"status": "ok"}

    manager = ReconstructionBrowserManager(
        script_path=tmp_path / "scripts" / "board_image_compare_server.py",
        cache_root=tmp_path / "cache",
        process_factory=process_factory,
        http_json=http_json,
        sleep=lambda _: None,
    )

    manager.open(config(tmp_path))

    assert process_calls[0][1:3] == ["-m", "scripts.board_image_compare_server"]


def test_comparison_service_module_entrypoint_imports() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import scripts.board_image_compare_server"],
        cwd=DEMO_ROOT.parents[3],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_comparison_service_direct_entrypoint_imports() -> None:
    repo_root = DEMO_ROOT.parents[3]
    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "board_image_compare_server.py"), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_close_terminates_owned_process(tmp_path: Path) -> None:
    process = FakeProcess()
    manager = ReconstructionBrowserManager(
        script_path=tmp_path / "server.py",
        cache_root=tmp_path / "cache",
        process_factory=lambda _command: process,
        http_json=lambda *_args, **_kwargs: {"status": "ok"},
        sleep=lambda _: None,
    )
    manager._process = process

    manager.close()

    assert process.terminated is True
