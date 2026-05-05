#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = PROJECT_ROOT / "session_bootstrap" / "demo" / "openamp_control_plane_demo"
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from board_probe import run_live_probe, write_probe_output  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a read-only OpenAMP board status probe over SSH.")
    parser.add_argument("--env", default="", help="Optional env file passed to connect_phytium_pi.sh.")
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=30.0,
        help="SSH probe timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        default="session_bootstrap/reports/openamp_demo_live_probe_latest.json",
        help="Where to write the probe JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_live_probe(env_file=args.env or None, timeout_sec=args.timeout_sec)
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    write_probe_output(payload, output_path)
    print(output_path)
    print(payload.get("summary", ""))
    return 0 if payload.get("reachable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
