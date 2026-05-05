from __future__ import annotations

import importlib.util
from typing import Any


def has_optional_dependency(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def is_pyside6_available() -> bool:
    return has_optional_dependency("PySide6")


def availability_report() -> dict[str, Any]:
    available = is_pyside6_available()
    return {
        "dependency": "PySide6",
        "available": available,
        "status": "ready" if available else "missing",
        "smoke_check_hint": "bash ./session_bootstrap/scripts/run_cockpit_native.sh --smoke-import-check",
        "launch_hint": "bash ./session_bootstrap/scripts/run_cockpit_native.sh",
    }
