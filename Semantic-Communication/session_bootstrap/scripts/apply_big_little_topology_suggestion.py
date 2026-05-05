#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a big.LITTLE topology suggestion JSON to an env file by updating "
            "BIG_LITTLE_BIG_CORES and BIG_LITTLE_LITTLE_CORES."
        )
    )
    parser.add_argument("--env", required=True, help="Target env file to update.")
    parser.add_argument("--suggestion", required=True, help="Topology suggestion JSON path.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output env path. Defaults to updating --env in place.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the updated env text to stdout without writing files.",
    )
    return parser.parse_args()


def load_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload

    raise ValueError(f"could not parse suggestion JSON from {path}")


def load_suggestion(path: Path) -> tuple[str, str]:
    payload = load_payload(path)
    suggestion = payload.get("suggestion") if isinstance(payload, dict) else None
    if not isinstance(suggestion, dict):
        raise ValueError(f"missing suggestion object in {path}")
    big = str(suggestion.get("big_cores_env") or "").strip()
    little = str(suggestion.get("little_cores_env") or "").strip()
    if not big or not little:
        raise ValueError(f"suggestion JSON does not contain both big/little core env values: {path}")
    return big, little


def replace_or_append_env_key(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + replacement + "\n"


def main() -> int:
    args = parse_args()
    env_path = resolve_path(args.env)
    suggestion_path = resolve_path(args.suggestion)
    output_path = resolve_path(args.output) if args.output else env_path

    if not env_path.is_file():
        raise SystemExit(f"ERROR: env file not found: {env_path}")
    if not suggestion_path.is_file():
        raise SystemExit(f"ERROR: suggestion file not found: {suggestion_path}")

    big, little = load_suggestion(suggestion_path)
    text = env_path.read_text(encoding="utf-8")
    text = replace_or_append_env_key(text, "BIG_LITTLE_BIG_CORES", big)
    text = replace_or_append_env_key(text, "BIG_LITTLE_LITTLE_CORES", little)

    if args.dry_run:
        sys.stdout.write(text)
        return 0

    output_path.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "env": str(output_path),
                "big_cores": big,
                "little_cores": little,
                "source_suggestion": str(suggestion_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
