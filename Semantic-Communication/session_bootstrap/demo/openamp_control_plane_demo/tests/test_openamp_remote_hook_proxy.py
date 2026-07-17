from __future__ import annotations

import base64
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from openamp_remote_hook_proxy import (  # noqa: E402
    SSH_HELPER,
    build_bridge_bundle_base64,
    build_remote_command,
    build_remote_sequence_command,
    main,
    normalize_args,
    parse_sequence_output,
    resolve_bash_executable,
    sequence_events,
)


class OpenampRemoteHookProxyTest(unittest.TestCase):
    def test_normalize_args_strips_windows_line_endings_from_device_paths(self) -> None:
        args = SimpleNamespace(
            host=" demo-board\r\n",
            user="demo-user",
            password="demo-pass",
            port="22",
            remote_project_root="",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0\r",
            rpmsg_dev="/dev/rpmsg0\r",
        )

        normalized = normalize_args(args)

        self.assertEqual(normalized.host, "demo-board")
        self.assertEqual(normalized.rpmsg_ctrl, "/dev/rpmsg_ctrl0")
        self.assertEqual(normalized.rpmsg_dev, "/dev/rpmsg0")

    def test_build_bridge_bundle_contains_bridge_runtime_files(self) -> None:
        bundle = base64.b64decode(build_bridge_bundle_base64())
        with gzip.GzipFile(fileobj=io.BytesIO(bundle), mode="rb") as gzip_file:
            with tarfile.open(fileobj=gzip_file, mode="r:") as archive:
                names = sorted(member.name for member in archive.getmembers())
                self.assertEqual(
                    names,
                    [
                        "openamp_mock/__init__.py",
                        "openamp_mock/protocol.py",
                        "session_bootstrap/scripts/openamp_rpmsg_bridge.py",
                    ],
                )
                bridge_source = archive.extractfile("session_bootstrap/scripts/openamp_rpmsg_bridge.py")
                protocol_source = archive.extractfile("openamp_mock/protocol.py")
                assert bridge_source is not None
                assert protocol_source is not None
                bridge_text = bridge_source.read().decode("utf-8")
                protocol_text = protocol_source.read().decode("utf-8")

        self.assertIn("def parse_args()", bridge_text)
        self.assertIn("class MessageType(IntEnum):", protocol_text)

    def test_build_remote_command_stages_bundle_without_remote_repo_lookup(self) -> None:
        args = SimpleNamespace(
            remote_project_root="",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0",
            rpmsg_dev="/dev/rpmsg0",
        )

        raw_event = '{"phase":"JOB_REQ","payload":{"job_id":123}}'
        hook_event_b64 = base64.b64encode(raw_event.encode("utf-8")).decode("ascii")
        command = build_remote_command(args, phase="JOB_REQ", job_id=123, hook_event_b64=hook_event_b64)

        self.assertIn('STAGE_ROOT="$(mktemp -d /tmp/openamp_demo_bridge.XXXXXX)"', command)
        self.assertIn("REMOTE_PROJECT_ROOT=''", command)
        self.assertIn(f"HOOK_EVENT_B64={hook_event_b64}", command)
        self.assertIn('STAGE_ROOT="$STAGE_ROOT" PYTHONDONTWRITEBYTECODE=1 python3 - <<\'PY\'', command)
        self.assertIn('bundle = base64.b64decode(', command)
        self.assertIn('HOOK_INPUT_FILE="$STAGE_ROOT/hook_event.json"', command)
        self.assertIn('IFS= read -r SUDO_PASSWORD || SUDO_PASSWORD=""', command)
        self.assertIn('HOOK_INPUT_FILE="$HOOK_INPUT_FILE" HOOK_EVENT_B64="$HOOK_EVENT_B64" python3 - <<\'PY\'', command)
        self.assertIn('base64.b64decode(os.environ.get("HOOK_EVENT_B64", ""))', command)
        self.assertIn("run_bridge()", command)
        self.assertIn("run_bridge_with_sudo()", command)
        self.assertIn("""printf '%s\\n' "$SUDO_PASSWORD" | sudo -S -p '' env PYTHONDONTWRITEBYTECODE=1 OPENAMP_PHASE="$PHASE" PYTHONPATH="$BRIDGE_PYTHONPATH" bash -lc 'python3 "$1" --hook-stdin --rpmsg-ctrl "$2" --rpmsg-dev "$3" --output-dir "$4" < "$5"'""", command)
        self.assertIn("could not launch the board-side bridge under sudo", command)
        self.assertIn('BRIDGE_SCRIPT="${REMOTE_BRIDGE_SCRIPT:-$STAGE_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py}"', command)
        self.assertIn('PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$BRIDGE_PYTHONPATH${PYTHONPATH:+:$PYTHONPATH}" OPENAMP_PHASE="$PHASE" python3 "$BRIDGE_SCRIPT"', command)
        self.assertIn("OUTPUT_DIR=/tmp/openamp_demo_hook/123/job_req", command)
        self.assertNotIn("remote_project_root_missing", command)
        self.assertNotIn('cd "$PROJECT_ROOT"', command)
        self.assertNotIn("sudo -n true >/dev/null 2>&1", command)

    def test_build_remote_command_prefers_existing_remote_project_root_when_present(self) -> None:
        args = SimpleNamespace(
            remote_project_root="/tmp/openamp_wrong_sha_fit/project",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0",
            rpmsg_dev="/dev/rpmsg0",
        )

        command = build_remote_command(args, phase="HEARTBEAT", job_id=4242)

        self.assertIn("REMOTE_PROJECT_ROOT=/tmp/openamp_wrong_sha_fit/project", command)
        self.assertIn('[[ -f "$REMOTE_PROJECT_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py" ]]', command)
        self.assertIn('REMOTE_BRIDGE_SCRIPT="$REMOTE_PROJECT_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py"', command)
        self.assertIn('REMOTE_BRIDGE_PYTHONPATH="$REMOTE_PROJECT_ROOT"', command)
        self.assertIn('BRIDGE_SCRIPT="${REMOTE_BRIDGE_SCRIPT:-$STAGE_ROOT/session_bootstrap/scripts/openamp_rpmsg_bridge.py}"', command)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", command)

    def test_sequence_command_reuses_one_ssh_and_one_outer_sudo(self) -> None:
        args = SimpleNamespace(
            remote_project_root="/tmp/openamp_fit/project",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0",
            rpmsg_dev="/dev/rpmsg0",
        )
        events = sequence_events(
            {
                "events": [
                    {"phase": "STATUS_REQ", "payload": {"job_id": 7}},
                    {"phase": "JOB_REQ", "payload": {"job_id": 7}},
                    {"phase": "STATUS_REQ", "payload": {"job_id": 7}, "delay_before_sec": 5},
                ]
            }
        )

        command = build_remote_sequence_command(args, events)

        self.assertEqual(command.count("sudo -S -p '' env SUDO_PASSWORD="), 1)
        self.assertIn("__OPENAMP_SEQUENCE_START__", command)
        self.assertIn("__OPENAMP_SEQUENCE_END__", command)
        self.assertIn("sleep 5.000", command)
        self.assertEqual(command.count("openamp_rpmsg_bridge.py"), 9)

    def test_sequence_output_prefers_bridge_summary_over_permission_tail(self) -> None:
        events = [
            {"phase": "JOB_REQ", "payload": {"job_id": 7}},
            {"phase": "STATUS_REQ", "payload": {"job_id": 7}},
        ]
        job_summary = {"phase": "JOB_REQ", "decision": "DENY", "source": "firmware_job_ack"}
        sudo_tail = {
            "phase": "JOB_REQ",
            "source": "openamp_demo_remote_hook_proxy",
            "transport_status": "permission_gate",
            "note": "JOB_REQ could not launch the board-side bridge under sudo: expected denial",
        }
        status_summary = {"phase": "STATUS_REQ", "protocol_semantics": "implemented"}
        raw = "\n".join(
            [
                "__OPENAMP_SEQUENCE_START__:0:JOB_REQ",
                json.dumps(job_summary),
                json.dumps(sudo_tail),
                "__OPENAMP_SEQUENCE_END__:0:JOB_REQ:2",
                "__OPENAMP_SEQUENCE_START__:1:STATUS_REQ",
                json.dumps(status_summary),
                "__OPENAMP_SEQUENCE_END__:1:STATUS_REQ:0",
            ]
        )

        results = parse_sequence_output(raw, events)

        self.assertEqual(results[0]["response"], job_summary)
        self.assertEqual(results[0]["returncode"], 2)
        self.assertEqual(results[1]["response"], status_summary)

    def test_main_passes_password_and_remote_script_on_stdin_to_avoid_long_windows_argv(self) -> None:
        args = SimpleNamespace(
            host="demo-board",
            user="demo-user",
            password="demo-pass",
            port="2202",
            remote_project_root="",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0",
            rpmsg_dev="/dev/rpmsg0",
        )
        raw_event = '{"phase":"JOB_REQ","payload":{"job_id":7}}'

        with (
            patch("openamp_remote_hook_proxy.parse_args", return_value=args),
            patch(
                "openamp_remote_hook_proxy.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["bash"],
                    returncode=0,
                    stdout='{"decision":"ALLOW"}\n',
                    stderr="",
                ),
            ) as run,
            patch("sys.stdin", io.StringIO(raw_event)),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            rc = main()

        self.assertEqual(rc, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[:2], [resolve_bash_executable(), str(SSH_HELPER)])
        self.assertEqual(command[-3:-1], ["bash", "-lc"])
        self.assertIn('cat >"$WRAPPER_SCRIPT"', command[-1])
        self.assertNotIn("HOOK_EVENT_B64=", command[-1])
        self.assertLess(max(len(part) for part in command), 1024)
        remote_input = run.call_args.kwargs["input"]
        self.assertIsInstance(remote_input, bytes)
        self.assertTrue(remote_input.startswith(b"demo-pass\n"))
        self.assertNotIn(b"\r\n", remote_input)
        remote_command = remote_input.decode("utf-8").split("\n", 1)[1]
        hook_event_b64 = base64.b64encode(raw_event.encode("utf-8")).decode("ascii")
        self.assertIn(f"HOOK_EVENT_B64={hook_event_b64}", remote_command)
        self.assertNotIn("text", run.call_args.kwargs)
        self.assertNotIn("encoding", run.call_args.kwargs)
        self.assertNotIn("errors", run.call_args.kwargs)
        self.assertEqual(stdout.getvalue(), '{"decision":"ALLOW"}\n')
        self.assertEqual(stderr.getvalue(), "")

    def test_main_suppresses_synthetic_permission_gate_tail_when_bridge_summary_exists(self) -> None:
        args = SimpleNamespace(
            host="demo-board",
            user="demo-user",
            password="demo-pass",
            port="2202",
            remote_project_root="",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0",
            rpmsg_dev="/dev/rpmsg0",
        )
        raw_event = '{"phase":"JOB_DONE","payload":{"job_id":7,"result_code":0}}'
        bridge_summary = json.dumps(
            {
                "phase": "JOB_DONE",
                "source": "firmware_job_done_status",
                "transport_status": "job_done_status_received",
                "protocol_semantics": "implemented",
                "note": "Received STATUS_RESP after JOB_DONE.",
            },
            ensure_ascii=False,
        )
        proxy_tail = json.dumps(
            {
                "phase": "JOB_DONE",
                "source": "openamp_demo_remote_hook_proxy",
                "transport_status": "permission_gate",
                "protocol_semantics": "not_attempted",
                "note": "JOB_DONE could not launch the board-side bridge under sudo: sudo returned a non-zero exit status.",
                "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                "rpmsg_dev": "/dev/rpmsg0",
            },
            ensure_ascii=False,
        )

        with (
            patch("openamp_remote_hook_proxy.parse_args", return_value=args),
            patch(
                "openamp_remote_hook_proxy.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["bash"],
                    returncode=1,
                    stdout=f"BASH=/usr/bin/bash\n{bridge_summary}\n{proxy_tail}\n",
                    stderr="cleanup warning\n",
                ),
            ),
            patch("sys.stdin", io.StringIO(raw_event)),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            rc = main()

        self.assertEqual(rc, 0)
        self.assertIn(bridge_summary, stdout.getvalue())
        self.assertNotIn(proxy_tail, stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "cleanup warning\n")

    def test_main_keeps_permission_gate_when_no_bridge_summary_precedes_it(self) -> None:
        args = SimpleNamespace(
            host="demo-board",
            user="demo-user",
            password="demo-pass",
            port="2202",
            remote_project_root="",
            remote_jscc_dir="",
            remote_output_root="/tmp/openamp_demo_hook",
            rpmsg_ctrl="/dev/rpmsg_ctrl0",
            rpmsg_dev="/dev/rpmsg0",
        )
        raw_event = '{"phase":"JOB_DONE","payload":{"job_id":7,"result_code":0}}'
        proxy_tail = json.dumps(
            {
                "phase": "JOB_DONE",
                "source": "openamp_demo_remote_hook_proxy",
                "transport_status": "permission_gate",
                "protocol_semantics": "not_attempted",
                "note": "JOB_DONE could not launch the board-side bridge under sudo: sudo returned a non-zero exit status.",
                "rpmsg_ctrl": "/dev/rpmsg_ctrl0",
                "rpmsg_dev": "/dev/rpmsg0",
            },
            ensure_ascii=False,
        )

        with (
            patch("openamp_remote_hook_proxy.parse_args", return_value=args),
            patch(
                "openamp_remote_hook_proxy.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["bash"],
                    returncode=1,
                    stdout=proxy_tail + "\n",
                    stderr="sudo: a password is required\n",
                ),
            ),
            patch("sys.stdin", io.StringIO(raw_event)),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            rc = main()

        self.assertEqual(rc, 1)
        self.assertEqual(stdout.getvalue(), proxy_tail + "\n")
        self.assertEqual(stderr.getvalue(), "sudo: a password is required\n")


if __name__ == "__main__":
    unittest.main()
