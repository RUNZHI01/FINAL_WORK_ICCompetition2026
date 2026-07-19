from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = PROJECT_ROOT / "demo.ps1"
DEMO_SCRIPT_DIR = PROJECT_ROOT / "scripts" / "demo"


def test_demo_entrypoint_dispatches_supported_actions() -> None:
    text = DEMO_SCRIPT.read_text(encoding="utf-8-sig")

    assert '[ValidateSet("start", "init", "check", "help")]' in text
    assert '[string]$Action = "start"' in text
    assert '"scripts\\demo\\start.ps1"' in text
    assert '"scripts\\demo\\init.ps1"' in text
    for action in ('"start"', '"init"', '"check"', '"help"'):
        assert action in text


def test_demo_entrypoint_keeps_public_connection_defaults() -> None:
    text = DEMO_SCRIPT.read_text(encoding="utf-8-sig")

    assert '[string]$BoardHost = "100.121.87.73"' in text
    assert '[string]$BoardUser = "user"' in text
    assert "[int]$BoardPort = 22" in text
    assert '[string]$BoardPassword = ""' in text


def test_start_requires_explicit_initialization_instead_of_installing() -> None:
    text = (DEMO_SCRIPT_DIR / "start.ps1").read_text(encoding="utf-8-sig")

    assert ".\\demo.ps1 init" in text
    assert "npm ci" not in text
    assert "pip install" not in text


def test_init_uses_fast_npm_flags_and_never_contacts_board() -> None:
    text = (DEMO_SCRIPT_DIR / "init.ps1").read_text(encoding="utf-8-sig")
    lower = text.lower()

    for value in ('"--prefer-offline"', '"--no-audit"', '"--no-fund"'):
        assert value in text
    assert text.count("Start-Job") >= 2
    assert "Wait-SetupJob" in text
    for forbidden in ("remote_host", "boardhost", "sshpass", "/api/session/board-access"):
        assert forbidden not in lower


def test_removed_public_entrypoints_are_absent() -> None:
    assert not (PROJECT_ROOT / "init.ps1").exists()
    cockpit_dir = PROJECT_ROOT / "Semantic-Communication" / "cockpit_desktop"
    assert not (cockpit_dir / "start-demo.ps1").exists()
    assert not (cockpit_dir / "start-demo-config.ps1").exists()


def test_help_and_startup_guide_publish_temporary_remote_environment() -> None:
    entrypoint = DEMO_SCRIPT.read_text(encoding="utf-8-sig")
    guide = (DEMO_SCRIPT_DIR / "STARTUP.md").read_text(encoding="utf-8")

    for name in ("REMOTE_HOST", "REMOTE_USER"):
        assert name in entrypoint
        assert name in guide
    assert "Remove-Item Env:REMOTE_HOST" in guide
    assert "Remove-Item Env:REMOTE_USER" in guide
