from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cryptography
import matplotlib
import numpy
import oqs
import PIL
import pytest
import rich
import textual


def _get_enabled(getter_names):
    for getter_name in getter_names:
        getter = getattr(oqs, getter_name, None)
        if getter is not None:
            return getter()

    raise RuntimeError(f"liboqs-python is missing API: {getter_names!r}")


def check_python_deps() -> None:
    enabled_kems = _get_enabled(("get_enabled_kem_mechanisms", "get_enabled_KEM_mechanisms"))
    enabled_sigs = _get_enabled(("get_enabled_sig_mechanisms", "get_enabled_SIG_mechanisms"))

    assert "ML-KEM-768" in enabled_kems
    assert "ML-DSA-65" in enabled_sigs


def check_electron_artifacts(project_root: Path) -> None:
    for tool in ("node", "npm", "tailscale", "tailscaled"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"missing executable: {tool}")

    cockpit_dir = project_root / "Semantic-Communication" / "cockpit_desktop"
    required_paths = (
        cockpit_dir / "node_modules" / ".bin" / "electron",
        cockpit_dir / "out" / "main" / "index.js",
        cockpit_dir / "out" / "preload" / "index.mjs",
        cockpit_dir / "out" / "renderer" / "index.html",
    )
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"missing Electron build artifacts: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-only", action="store_true")
    parser.add_argument("--project-root", default="/workspace")
    args = parser.parse_args()

    check_python_deps()
    if not args.python_only:
        check_electron_artifacts(Path(args.project_root))

    print("deps-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
