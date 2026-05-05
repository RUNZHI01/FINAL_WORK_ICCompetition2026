from __future__ import annotations

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPO_ROOT
    / "session_bootstrap"
    / "board_snapshots"
    / "phytium_pi_20260418_jobdone_v14_live"
    / "home/user/phytium-dev/release_v1.4.0-jobdone-v14/example/system/amp/openamp_for_linux/src/slaver_00_example.c"
)


class BoardSnapshotDualProtocolSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_legacy_message_ids_remain_unchanged(self) -> None:
        expected = {
            "SC_MSG_JOB_REQ": "0x0001U",
            "SC_MSG_JOB_ACK": "0x0002U",
            "SC_MSG_HEARTBEAT": "0x0003U",
            "SC_MSG_HEARTBEAT_ACK": "0x0004U",
            "SC_MSG_JOB_DONE": "0x0005U",
            "SC_MSG_SAFE_STOP": "0x0007U",
            "SC_MSG_STATUS_REQ": "0x0008U",
            "SC_MSG_STATUS_RESP": "0x0009U",
            "SC_MSG_SIGNED_ADMISSION_BEGIN": "0x000CU",
            "SC_MSG_SIGNED_ADMISSION_CHUNK": "0x000DU",
            "SC_MSG_SIGNED_ADMISSION_SIGNATURE": "0x000EU",
            "SC_MSG_SIGNED_ADMISSION_COMMIT": "0x000FU",
            "SC_MSG_SIGNED_ADMISSION_ACK": "0x0010U",
        }
        for name, value in expected.items():
            self.assertRegex(self.source, rf"#define\s+{name}\s+{re.escape(value)}")

    def test_status_resp_contract_remains_six_u32_fields(self) -> None:
        self.assertRegex(
            self.source,
            (
                r"typedef struct\s*\{\s*"
                r"uint32_t guard_state;\s*"
                r"uint32_t active_job_id;\s*"
                r"uint32_t last_fault_code;\s*"
                r"uint32_t heartbeat_ok;\s*"
                r"uint32_t sticky_fault;\s*"
                r"uint32_t total_fault_count;\s*"
                r"\}\s*ScStatusResp;"
            ),
        )

    def test_dual_protocol_extension_is_declared_in_source(self) -> None:
        expected = {
            "SC_MSG_LINK_HEALTH": "0x0060U",
            "SC_MSG_MODE_DIRECTIVE": "0x0061U",
            "SC_MSG_MODE_ACK": "0x0062U",
            "SC_FAULT_LINK_DEGRADED": "17U",
            "SC_FAULT_LINK_LOST": "18U",
            "SC_SERVICE_MODE_FULL_FRAME": "0U",
            "SC_SERVICE_MODE_ROI_ONLY": "1U",
            "SC_SERVICE_MODE_ALERT_ONLY": "2U",
        }
        for name, value in expected.items():
            self.assertRegex(self.source, rf"#define\s+{name}\s+{re.escape(value)}")

    def test_dual_protocol_handlers_are_wired_into_dispatch(self) -> None:
        self.assertIn("static int sc_ctrl_handle_link_health(", self.source)
        self.assertIn("static int sc_ctrl_handle_mode_ack(", self.source)
        self.assertIn("case SC_MSG_LINK_HEALTH:", self.source)
        self.assertIn("case SC_MSG_MODE_ACK:", self.source)
        self.assertIn("response.header.msg_type = SC_MSG_MODE_DIRECTIVE;", self.source)

    def test_link_lost_path_uses_safe_stop_semantics(self) -> None:
        self.assertRegex(
            self.source,
            (
                r"if\s*\(request\.rx_locked == 0U\)\s*\{\s*"
                r"sc_ctrl_note_fault\(SC_FAULT_LINK_LOST\);\s*"
                r"sc_ctrl_clear_active_job\(\);\s*"
                r"sc_ctrl_clear_signed_stage\(\);\s*"
                r"ret = sc_ctrl_send_status_resp\(ept, src, request_header\);\s*"
            ),
        )

    def test_snapshot_tracks_mean4_v7_trusted_sha_and_key_slot(self) -> None:
        self.assertIn(
            "0xbf, 0x25, 0x5c, 0xd4, 0xbb, 0x29, 0x40, 0x8b,",
            self.source,
        )
        self.assertIn('"mean4-v7-dev-20260420"', self.source)
        self.assertIn('"openamp-demo-current"', self.source)


if __name__ == "__main__":
    unittest.main()
