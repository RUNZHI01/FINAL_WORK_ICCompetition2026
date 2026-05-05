from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .qt_app import capture_native_cockpit


DEFAULT_CAPTURE_RELATIVE_PATH = Path("cockpit_native") / "runtime" / "captures" / "cockpit_native_latest.png"


def default_capture_output_path(project_root: Path | None = None) -> Path:
    resolved_root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    return resolved_root / DEFAULT_CAPTURE_RELATIVE_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render the native cockpit through the repo-backed offscreen/software path and save a PNG.",
    )
    parser.add_argument(
        "--output",
        default=str(default_capture_output_path()),
        help="Output image path. Defaults to cockpit_native/runtime/captures/cockpit_native_latest.png",
    )
    parser.add_argument("--page", type=int, default=None, help="Page index to capture.")
    parser.add_argument("--width", type=int, default=None, help="Window width.")
    parser.add_argument("--height", type=int, default=None, help="Window height.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        saved_path = capture_native_cockpit(
            output_path=Path(args.output),
            page_index=args.page,
            window_width=args.width,
            window_height=args.height,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(saved_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
