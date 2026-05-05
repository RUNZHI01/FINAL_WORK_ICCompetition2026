from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from event_spine import CONTROL_MODE_SCOPE, DemoEventSpine  # noqa: E402


class DemoEventSpineTest(unittest.TestCase):
    def test_link_profile_change_updates_store_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            spine = DemoEventSpine(temp_dir, session_id="demo-session")

            event = spine.publish(
                "LINK_PROFILE_CHANGED",
                source="operator",
                plane="control",
                mode_scope=CONTROL_MODE_SCOPE,
                message="Link director switched to jitter profile.",
                data={"profile_id": "jitter", "profile_label": "抖动"},
            )
            snapshot_path = spine.write_snapshot(reason="link_profile_changed")
            summary = spine.summary(limit=8)

            self.assertEqual(event["type"], "LINK_PROFILE_CHANGED")
            self.assertEqual(summary["aggregate"]["link_profile"]["selected_profile_id"], "jitter")
            self.assertEqual(summary["aggregate"]["link_profile"]["selected_profile_label"], "抖动")
            self.assertTrue(summary["aggregate"]["archive"]["enabled"])
            self.assertTrue(Path(snapshot_path).is_file())

            events_path = Path(summary["aggregate"]["archive"]["events_jsonl"])
            self.assertTrue(events_path.is_file())
            event_types = [
                json.loads(line)["type"]
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertIn("LINK_PROFILE_CHANGED", event_types)
            self.assertIn("ARCHIVE_SNAPSHOT_WRITTEN", event_types)

    def test_job_rejection_updates_recent_events_and_counters(self) -> None:
        spine = DemoEventSpine(None, session_id="demo-session")

        spine.publish(
            "JOB_SUBMITTED",
            source="inference",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message="Operator requested a current live launch.",
            data={"variant": "current", "image_index": 0},
        )
        spine.publish(
            "JOB_REJECTED",
            source="inference",
            plane="control",
            mode_scope=CONTROL_MODE_SCOPE,
            message="Launch rejected because the board session is incomplete.",
            data={"variant": "current", "status_category": "config_error"},
        )
        summary = spine.summary(limit=4)

        self.assertEqual(summary["aggregate"]["jobs"]["submitted_count"], 1)
        self.assertEqual(summary["aggregate"]["jobs"]["rejected_count"], 1)
        self.assertEqual(summary["aggregate"]["event_counters"]["JOB_SUBMITTED"], 1)
        self.assertEqual(summary["aggregate"]["event_counters"]["JOB_REJECTED"], 1)
        self.assertEqual(
            [item["type"] for item in summary["recent_events"][:2]],
            ["JOB_REJECTED", "JOB_SUBMITTED"],
        )


if __name__ == "__main__":
    unittest.main()
