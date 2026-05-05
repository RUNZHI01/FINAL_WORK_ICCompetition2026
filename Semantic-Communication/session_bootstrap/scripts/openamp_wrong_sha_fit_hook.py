#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = PROJECT_ROOT / "session_bootstrap/scripts/openamp_rpmsg_bridge.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase-router hook for the board-side wrong-SHA FIT run. "
            "It forwards wrapper hook stdin to openamp_rpmsg_bridge.py and stores "
            "each phase under its own output subdirectory."
        )
    )
    parser.add_argument(
        "--output-root",
        required=True,
        help="Root directory for per-phase bridge artifacts.",
    )
    parser.add_argument(
        "--rpmsg-ctrl",
        default="/dev/rpmsg_ctrl0",
        help="RPMsg control node passed through to the bridge.",
    )
    parser.add_argument(
        "--rpmsg-dev",
        default="/dev/rpmsg0",
        help="RPMsg endpoint device passed through to the bridge.",
    )
    parser.add_argument(
        "--response-timeout-sec",
        type=float,
        default=2.0,
        help="Bridge response timeout.",
    )
    parser.add_argument(
        "--settle-timeout-sec",
        type=float,
        default=0.05,
        help="Bridge settle timeout.",
    )
    parser.add_argument(
        "--max-rx-bytes",
        type=int,
        default=4096,
        help="Bridge max receive bytes.",
    )
    return parser.parse_args()


def resolve_output_root(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def detect_phase(raw_event: str) -> str:
    phase = os.environ.get("OPENAMP_PHASE", "").strip()
    if phase:
        return phase.upper()
    try:
        payload = json.loads(raw_event)
    except json.JSONDecodeError:
        return "UNKNOWN"
    if isinstance(payload, dict):
        event_phase = str(payload.get("phase", "")).strip()
        if event_phase:
            return event_phase.upper()
    return "UNKNOWN"


def phase_slug(phase: str) -> str:
    return phase.strip().lower().replace("/", "_").replace(" ", "_") or "unknown"


def main() -> int:
    args = parse_args()
    raw_event = sys.stdin.read()
    phase = detect_phase(raw_event)
    output_root = resolve_output_root(args.output_root)
    phase_output_dir = output_root / phase_slug(phase)
    phase_output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(BRIDGE_PATH),
        "--hook-stdin",
        "--rpmsg-ctrl",
        args.rpmsg_ctrl,
        "--rpmsg-dev",
        args.rpmsg_dev,
        "--output-dir",
        str(phase_output_dir),
        "--response-timeout-sec",
        str(args.response_timeout_sec),
        "--settle-timeout-sec",
        str(args.settle_timeout_sec),
        "--max-rx-bytes",
        str(args.max_rx_bytes),
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        input=raw_event,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
