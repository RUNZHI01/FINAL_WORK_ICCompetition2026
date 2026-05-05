from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD_SCRIPT = PROJECT_ROOT / "session_bootstrap" / "scripts" / "run_remote_tvm_inference_payload.sh"


def parse_last_json(stdout: str) -> dict[str, object]:
    for raw in reversed(stdout.splitlines()):
        line = raw.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise AssertionError(f"no JSON payload found in output:\n{stdout}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_executable(path: Path, content: str) -> None:
    write_text(path, content)
    path.chmod(0o755)


class RunRemoteTvmInferencePayloadTest(unittest.TestCase):
    def test_ssh_mode_supports_composite_remote_tvm_python(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            fake_bin = temp_dir / "bin"
            fake_bin.mkdir()
            archive_dir = temp_dir / "archive"
            archive_dir.mkdir()
            trace_path = temp_dir / "remote_command.txt"

            fake_ssh = fake_bin / "ssh"
            write_executable(
                fake_ssh,
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    set -eu
                    eval "remote_command=\\${$#}"
                    printf '%s\n' "$remote_command" >"$FAKE_SSH_TRACE"
                    exec bash -lc "$remote_command"
                    """
                ),
            )

            fake_python = temp_dir / "fake_python.sh"
            write_executable(
                fake_python,
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    set -eu

                    if [ "${FAKE_REMOTE_MARKER:-}" != "expected" ]; then
                      echo "missing composite marker" >&2
                      exit 23
                    fi
                    if [ "${1:-}" != "-" ]; then
                      echo "expected stdin payload marker as first arg" >&2
                      exit 24
                    fi

                    archive_dir="${2:-}"
                    variant="${3:-}"
                    cat >/dev/null

                    python3 - "$archive_dir" "$variant" <<'PY'
                    import json
                    import sys

                    print(
                        json.dumps(
                            {
                                "status": "ok",
                                "archive": sys.argv[1],
                                "variant": sys.argv[2],
                            },
                            ensure_ascii=False,
                        )
                    )
                    PY
                    """
                ),
            )

            composite_python = f"env FAKE_REMOTE_MARKER=expected {fake_python}"
            env = os.environ.copy()
            env.update(
                {
                    "FAKE_SSH_TRACE": str(trace_path),
                    "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                    "REMOTE_MODE": "ssh",
                    "REMOTE_HOST": "demo-host",
                    "REMOTE_USER": "demo-user",
                    "REMOTE_PASS": "demo-pass",
                    "REMOTE_TVM_PYTHON": composite_python,
                    "REMOTE_TVM_JSCC_BASE_DIR": str(archive_dir),
                    "SSH_WITH_PASSWORD_DISABLE_CONTROLMASTER": "1",
                    "TUNE_INPUT_SHAPE": "1,1,1,1",
                    "TUNE_INPUT_DTYPE": "float32",
                }
            )

            result = subprocess.run(
                ["bash", str(PAYLOAD_SCRIPT), "--variant", "current"],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = parse_last_json(result.stdout)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["archive"], str(archive_dir))
            self.assertEqual(payload["variant"], "current")

            remote_command = trace_path.read_text(encoding="utf-8").strip()
            self.assertIn(composite_python, remote_command)
            self.assertNotIn(f"'{composite_python}'", remote_command)


if __name__ == "__main__":
    unittest.main()
