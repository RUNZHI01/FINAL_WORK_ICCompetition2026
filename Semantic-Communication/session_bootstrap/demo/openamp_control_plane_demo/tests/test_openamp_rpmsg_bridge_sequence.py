from __future__ import annotations

import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from openamp_rpmsg_bridge import run_hook_sequence  # noqa: E402


class OpenampRpmsgBridgeSequenceTest(unittest.TestCase):
    def test_sequence_runs_all_phases_in_one_process_and_keeps_returncodes(self) -> None:
        args = SimpleNamespace(output_dir="/tmp/default", phase="STATUS_REQ")
        hook_event = {
            "events": [
                {
                    "phase": "STATUS_REQ",
                    "payload": {"job_id": 7},
                    "delay_before_sec": 0,
                    "output_dir": "/tmp/fit/7/status_req",
                },
                {
                    "phase": "JOB_REQ",
                    "payload": {"job_id": 7},
                    "delay_before_sec": 5,
                    "output_dir": "/tmp/fit/7/job_req",
                },
            ]
        }

        with (
            patch(
                "openamp_rpmsg_bridge.execute_hook_phase",
                side_effect=[({"phase": "STATUS_REQ"}, 0), ({"phase": "JOB_REQ", "decision": "DENY"}, 2)],
            ) as execute,
            patch("openamp_rpmsg_bridge.time.sleep") as sleep,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            rc = run_hook_sequence(args, hook_event)

        self.assertEqual(rc, 0)
        sleep.assert_called_once_with(5.0)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(execute.call_args_list[1].kwargs["phase"], "JOB_REQ")
        self.assertTrue(execute.call_args_list[1].kwargs["output_dir"].as_posix().endswith("/tmp/fit/7/job_req"))
        lines = stdout.getvalue().splitlines()
        self.assertEqual(lines[0], "__OPENAMP_SEQUENCE_START__:0:STATUS_REQ")
        self.assertEqual(json.loads(lines[1]), {"phase": "STATUS_REQ"})
        self.assertEqual(lines[2], "__OPENAMP_SEQUENCE_END__:0:STATUS_REQ:0")
        self.assertEqual(lines[3], "__OPENAMP_SEQUENCE_START__:1:JOB_REQ")
        self.assertEqual(lines[5], "__OPENAMP_SEQUENCE_END__:1:JOB_REQ:2")


if __name__ == "__main__":
    unittest.main()
