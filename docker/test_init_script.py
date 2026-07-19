from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INIT_SCRIPT = PROJECT_ROOT / "scripts" / "demo" / "init.ps1"
ROOT_README = PROJECT_ROOT / "README.md"
STARTUP_GUIDE = PROJECT_ROOT / "scripts" / "demo" / "STARTUP.md"
DELIVERY_DOCS = (
    ROOT_README,
    PROJECT_ROOT / "docs" / "README.md",
    PROJECT_ROOT / "docs" / "USRP_LINK_BRIEFING.md",
    PROJECT_ROOT / "docs" / "USRP_IQ_RUNTIME.md",
    PROJECT_ROOT / "docker" / "README.md",
    STARTUP_GUIDE,
)


def test_init_script_covers_fresh_windows_checkout() -> None:
    text = INIT_SCRIPT.read_text(encoding="utf-8")

    assert "[switch]$CheckOnly" in text
    assert "[switch]$ForceNodeInstall" in text
    assert '"-m", "venv"' in text
    assert '"ci"' in text
    assert '"--prefer-offline"' in text
    assert '"--no-audit"' in text
    assert '"--no-fund"' in text
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

    assert ".\\demo.ps1 init" in text
    assert ".\\demo.ps1 check" in text
    assert ".\\demo.ps1 start" in text
    assert "scripts/demo/STARTUP.md" in text


def test_tracked_delivery_docs_do_not_reference_removed_entrypoints() -> None:
    forbidden = (
        "docs/runbooks/STARTUP.md",
        "runbooks/STARTUP.md",
        "cockpit_desktop/start-demo.ps1",
        "pwsh -File .\\init.ps1",
    )

    for path in DELIVERY_DOCS:
        text = path.read_text(encoding="utf-8")
        for value in forbidden:
            assert value not in text, f"{path.relative_to(PROJECT_ROOT)} still contains {value}"
