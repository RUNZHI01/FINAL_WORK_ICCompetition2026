#!/usr/bin/env python3
"""Prepare staging-safe env files for handwritten fused_conv2d_transpose1_add9 work.

This helper keeps the handwritten validation path narrow and repeatable:
- start from the checked-in trusted env snapshot template
- redirect current artifact reads to a handwritten staging archive
- pin the expected SHA for the handwritten candidate
- never touch trusted current defaults
"""

from __future__ import annotations

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_ENV = (
    PROJECT_ROOT
    / "session_bootstrap/reports/"
    / "profiling_runtime_joint_top6_staging_artifact_reprobe_20260331_0010/"
    / "trusted_env_snapshot.env"
)
DEFAULT_OUTPUT_ENV = (
    PROJECT_ROOT
    / "session_bootstrap/tmp/"
    / "handwritten_fused_conv2d_transpose1_add9_profile.env"
)
DEFAULT_STAGING_ARCHIVE = "/home/user/Downloads/jscc-test/jscc_staging_handwritten"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a staging-safe profile env for the handwritten "
            "fused_conv2d_transpose1_add9 candidate."
        )
    )
    parser.add_argument(
        "--base-env",
        default=str(DEFAULT_BASE_ENV),
        help="Base env snapshot used as the template.",
    )
    parser.add_argument(
        "--output-env",
        default=str(DEFAULT_OUTPUT_ENV),
        help="Output env path.",
    )
    parser.add_argument(
        "--staging-archive",
        default=DEFAULT_STAGING_ARCHIVE,
        help="Remote staging archive that will host the handwritten candidate.",
    )
    parser.add_argument(
        "--expected-sha256",
        required=True,
        help="Expected SHA256 for the handwritten candidate artifact.",
    )
    parser.add_argument(
        "--stage-root",
        default="/home/user/Downloads/jscc-test/jscc_staging_handwritten/infer_outputs",
        help="Optional stage root for output dirs used by run_remote_current_real_reconstruction.sh",
    )
    return parser.parse_args()


def validate_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SystemExit(f"expected 64 hex sha256, got: {value}")
    return normalized


def main() -> None:
    args = parse_args()
    base_env = Path(args.base_env).expanduser().resolve()
    output_env = Path(args.output_env).expanduser().resolve()
    if not base_env.is_file():
        raise SystemExit(f"base env not found: {base_env}")

    expected_sha = validate_sha256(args.expected_sha256)
    archive = args.staging_archive.rstrip("/")
    artifact = f"{archive}/tvm_tune_logs/optimized_model.so"

    text = base_env.read_text(encoding="utf-8")
    additions = [
        "",
        f"INFERENCE_CURRENT_ARCHIVE={archive}",
        f"REMOTE_CURRENT_ARTIFACT={artifact}",
        f"INFERENCE_CURRENT_EXPECTED_SHA256={expected_sha}",
        f"REMOTE_CURRENT_ARTIFACT_STAGE_DIR={args.stage_root.rstrip('/')}",
    ]

    output_env.parent.mkdir(parents=True, exist_ok=True)
    output_env.write_text(text + "\n".join(additions) + "\n", encoding="utf-8")

    print(f"output_env={output_env}")
    print(f"staging_archive={archive}")
    print(f"artifact={artifact}")
    print(f"expected_sha256={expected_sha}")


if __name__ == "__main__":
    main()
