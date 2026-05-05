from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Sequence

from .adapter import DemoRepoAdapter
from .availability import availability_report, is_pyside6_available
from .qt_app import apply_software_renderer_env, launch_native_cockpit


COCKPIT_NATIVE_CHILD_ENV = "COCKPIT_NATIVE_LAUNCH_CHILD"
COCKPIT_NATIVE_SOFTWARE_FALLBACK_ENV = "COCKPIT_NATIVE_SOFTWARE_FALLBACK_ACTIVE"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native Qt/QML cockpit prototype for the current repo-backed demo.")
    parser.add_argument(
        "--smoke-import-check",
        action="store_true",
        help="Load the adapter layer and emit a JSON health summary without requiring PySide6.",
    )
    parser.add_argument(
        "--dump-ui-state",
        action="store_true",
        help="Print the normalized UI state as JSON and exit.",
    )
    parser.add_argument(
        "--software-render",
        action="store_true",
        help="Force Qt Quick software rendering for safer launch on fragile GPU/driver stacks.",
    )
    parser.add_argument(
        "--safe-area-insets",
        metavar="LEFT,TOP,RIGHT,BOTTOM",
        help="Optional logical safe-area insets in pixels for native/mobile shells.",
    )
    return parser


def parse_safe_area_insets(raw_value: str | None) -> dict[str, int] | None:
    if raw_value is None:
        return None

    values = [part.strip() for part in raw_value.split(",")]
    if len(values) != 4:
        raise ValueError("safe-area insets must be provided as LEFT,TOP,RIGHT,BOTTOM")

    parsed: dict[str, int] = {}
    for key, item in zip(("left", "top", "right", "bottom"), values):
        try:
            amount = int(item)
        except ValueError as exc:
            raise ValueError(f"safe-area inset `{item}` is not an integer") from exc
        if amount < 0:
            raise ValueError("safe-area insets must be zero or positive")
        parsed[key] = amount
    return parsed


def build_child_command(argv: Sequence[str], *, software_render: bool) -> list[str]:
    forwarded = [arg for arg in argv if arg != "--software-render"]
    return [
        sys.executable,
        "-m",
        "cockpit_native",
        *(["--software-render"] if software_render else []),
        *forwarded,
    ]


def build_child_env(*, software_render: bool) -> dict[str, str]:
    env = os.environ.copy()
    env[COCKPIT_NATIVE_CHILD_ENV] = "1"
    if software_render:
        env[COCKPIT_NATIVE_SOFTWARE_FALLBACK_ENV] = "1"
        apply_software_renderer_env(env)
    else:
        env.pop(COCKPIT_NATIVE_SOFTWARE_FALLBACK_ENV, None)
    return env


def run_child_launch(argv: Sequence[str], *, software_render: bool) -> int:
    result = subprocess.run(
        build_child_command(argv, software_render=software_render),
        check=False,
        env=build_child_env(software_render=software_render),
    )
    return int(result.returncode)


def supervise_native_launch(argv: Sequence[str], *, software_render: bool) -> int:
    initial_rc = run_child_launch(argv, software_render=software_render)
    if initial_rc == 0 or software_render:
        return initial_rc

    print(
        "Native Qt launch failed or exited early. Retrying once with software renderer.",
        file=sys.stderr,
    )
    return run_child_launch(argv, software_render=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    adapter = DemoRepoAdapter()
    try:
        safe_area_insets = parse_safe_area_insets(args.safe_area_insets)
    except ValueError as exc:
        parser.error(str(exc))

    if args.smoke_import_check:
        bundle = adapter.load_contract_bundle()
        report = availability_report()
        report.update(
            {
                "snapshot_path": str(bundle.snapshot_path),
                "session_id": str((bundle.snapshot.get("aggregate") or {}).get("session_id") or ""),
                "aircraft_contract": str(bundle.aircraft_position.get("contract_version") or ""),
                "recommended_scenario_id": str(bundle.weak_network.get("recommended_scenario_id") or ""),
                "layout_strategy": str((bundle.ui_state.get("meta") or {}).get("layout_strategy") or ""),
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.dump_ui_state:
        print(json.dumps(adapter.load_contract_bundle().ui_state, ensure_ascii=False, indent=2))
        return 0

    if not is_pyside6_available():
        print(
            "PySide6 is not installed. Run `python3 -m cockpit_native --smoke-import-check` "
            "or install PySide6 to launch the QML shell.",
            file=sys.stderr,
        )
        return 2

    launch_argv = list(argv if argv is not None else sys.argv[1:])
    if os.environ.get(COCKPIT_NATIVE_CHILD_ENV) != "1":
        return supervise_native_launch(launch_argv, software_render=args.software_render)

    try:
        return launch_native_cockpit(
            software_render=args.software_render,
            safe_area_insets=safe_area_insets,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
