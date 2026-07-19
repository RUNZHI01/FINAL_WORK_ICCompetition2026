from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = PROJECT_ROOT / "init.ps1"
ROOT_README = PROJECT_ROOT / "README.md"


def test_init_script_covers_fresh_windows_checkout() -> None:
    text = INIT_SCRIPT.read_text(encoding="utf-8")

    assert "[switch]$CheckOnly" in text
    assert "[switch]$ForceNodeInstall" in text
    assert '"-m", "venv"' in text
    assert '"ci"' in text
    assert "iccomp-usrp-tx:latest" in text
    assert "docker/check_deps.py" in text
    assert "torch" in text
    assert "places365-latents.tar.gz" in text
    assert "--strip-components=1" in text
    assert '& $Py.Source -3 -c "import sys; print(sys.executable)"' in text


def test_init_script_does_not_contact_board() -> None:
    text = INIT_SCRIPT.read_text(encoding="utf-8").lower()

    for forbidden in ("remote_host", "boardhost", "sshpass", "/api/session/board-access"):
        assert forbidden not in text


def test_root_readme_is_the_delivery_entrypoint() -> None:
    text = ROOT_README.read_text(encoding="utf-8")

    assert ".\\init.ps1" in text
    assert ".\\Semantic-Communication\\cockpit_desktop\\start-demo.ps1" in text
    assert "docs/runbooks/STARTUP.md" in text
