from __future__ import annotations

import errno
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from openamp_mock.protocol import Decision, FaultCode, FORMAL_TRUSTED_CURRENT_SHA, MessageType


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_rpmsg_bridge.py"
BRIDGE_SPEC = importlib.util.spec_from_file_location("openamp_rpmsg_bridge", BRIDGE_PATH)
if BRIDGE_SPEC is None or BRIDGE_SPEC.loader is None:
    raise RuntimeError(f"failed to load bridge module from {BRIDGE_PATH}")
bridge = importlib.util.module_from_spec(BRIDGE_SPEC)
BRIDGE_SPEC.loader.exec_module(bridge)


class OpenAmpRpmsgBridgeTest(unittest.TestCase):
    def test_open_transport_fd_falls_back_when_nonblocking_open_is_rejected(self) -> None:
        rpmsg_dev = Path("/dev/rpmsg0")

        with (
            mock.patch.object(
                bridge.os,
                "open",
                side_effect=[OSError(errno.EINVAL, "invalid open flags"), 9],
            ) as open_mock,
            mock.patch.object(bridge.os, "set_blocking") as set_blocking_mock,
        ):
            fd = bridge.open_transport_fd(rpmsg_dev)

        self.assertEqual(fd, 9)
        self.assertEqual(
            open_mock.call_args_list,
            [
                mock.call(rpmsg_dev, bridge.os.O_RDWR | bridge.os.O_NONBLOCK),
                mock.call(rpmsg_dev, bridge.os.O_RDWR),
            ],
        )
        set_blocking_mock.assert_called_once_with(9, False)

    def test_write_all_tries_direct_write_before_waiting_for_writable(self) -> None:
        with (
            mock.patch.object(bridge.os, "write", return_value=4) as mock_write,
            mock.patch.object(bridge.select, "select") as mock_select,
        ):
            written = bridge.write_all(7, b"ping", timeout_sec=0.1)

        self.assertEqual(written, 4)
        self.assertEqual(mock_write.call_count, 1)
        mock_select.assert_not_called()

    def test_write_all_retries_after_retryable_nonblocking_write_error(self) -> None:
        attempts = 0

        def fake_write(fd: int, payload: bytes | memoryview) -> int:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise BlockingIOError(errno.EAGAIN, "rpmsg busy")
            return len(payload)

        with (
            mock.patch.object(bridge.os, "write", side_effect=fake_write) as mock_write,
            mock.patch.object(bridge.select, "select", return_value=([], [7], [])) as mock_select,
        ):
            written = bridge.write_all(7, b"payload", timeout_sec=0.1)

        self.assertEqual(written, len(b"payload"))
        self.assertEqual(mock_write.call_count, 2)
        self.assertEqual(mock_select.call_count, 1)

    def test_build_job_req_payload_encodes_binary_wire_shape(self) -> None:
        payload = bridge.build_job_req_payload_from_hook(
            {
                "phase": "JOB_REQ",
                "payload": {
                    "job_id": 42,
                    "expected_sha256": FORMAL_TRUSTED_CURRENT_SHA,
                    "deadline_ms": 300000,
                    "expected_outputs": 300,
                    "job_flags": "reconstruction",
                },
            }
        )

        parsed = bridge.parse_job_req_payload(payload)
        self.assertTrue(parsed["parsed"])
        self.assertEqual(parsed["expected_sha256_hex"], FORMAL_TRUSTED_CURRENT_SHA)
        self.assertEqual(parsed["deadline_ms"], 300000)
        self.assertEqual(parsed["expected_outputs"], 300)
        self.assertEqual(parsed["flags"], 2)
        self.assertEqual(parsed["flag_name"], "reconstruction")

    def test_build_job_req_payload_maps_unknown_flag_to_zero(self) -> None:
        payload = bridge.build_job_req_payload_from_hook(
            {
                "phase": "JOB_REQ",
                "payload": {
                    "job_id": 99,
                    "expected_sha256": FORMAL_TRUSTED_CURRENT_SHA,
                    "deadline_ms": 1,
                    "expected_outputs": 1,
                    "job_flags": "future_flag",
                },
            }
        )

        parsed = bridge.parse_job_req_payload(payload)
        self.assertTrue(parsed["parsed"])
        self.assertEqual(parsed["flags"], 0)
        self.assertEqual(parsed["flag_name"], "unknown_0x0")

    def test_run_signed_admission_probe_accepts_firmware_ack(self) -> None:
        manifest_sha256 = "ab" * 32
        tx_frame = bridge.build_frame(
            msg_type=MessageType.SIGNED_ADMISSION_BEGIN,
            seq=3,
            job_id=7301,
            payload=bridge.SIGNED_ADMISSION_BEGIN_STRUCT.pack(
                1,
                1,
                1,
                bytes.fromhex(manifest_sha256),
                808,
                71,
                160,
            ),
        )
        rx_frame = bridge.build_frame(
            msg_type=MessageType.SIGNED_ADMISSION_ACK,
            seq=3,
            job_id=7301,
            payload=bridge.SIGNED_ADMISSION_ACK_STRUCT.pack(
                bytes.fromhex(manifest_sha256),
                1,
                0,
                0,
                808,
            ),
        )
        args = bridge.argparse.Namespace(
            rpmsg_ctrl="/dev/null",
            rpmsg_dev="/dev/null",
            require_devices=False,
            response_timeout_sec=2.0,
            settle_timeout_sec=0.05,
            max_rx_bytes=4096,
            drain_before_send=True,
            seq=1,
            hook_stdin=True,
            job_id=0,
        )
        hook_event = {
            "phase": "SIGNED_ADMISSION_BEGIN",
            "payload": {
                "job_id": 7301,
                "tx_frame_hex": tx_frame.hex(),
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir_raw:
            output_dir = Path(temp_dir_raw)
            with mock.patch.object(
                bridge,
                "transact",
                return_value={
                    "drained_bytes": b"",
                    "written_bytes": len(tx_frame),
                    "rx_bytes": rx_frame,
                    "rx_timeout": False,
                },
            ):
                summary = bridge.run_signed_admission_probe(
                    args=args,
                    output_dir=output_dir,
                    phase="SIGNED_ADMISSION_BEGIN",
                    hook_event=hook_event,
                )

        self.assertTrue(summary["acknowledged"])
        self.assertEqual(summary["source"], "firmware_signed_admission_ack")
        self.assertEqual(summary["transport_status"], "signed_admission_ack_received")
        self.assertEqual(summary["ack_status_name"], "ACCEPTED")
        self.assertEqual(summary["stage_name"], "BEGIN")
        self.assertEqual(summary["seq"], 3)
        self.assertEqual(summary["tx_frame"]["msg_name"], "SIGNED_ADMISSION_BEGIN")

    def test_run_job_probe_prefers_exact_tx_frame_from_hook(self) -> None:
        tx_frame = bridge.build_frame(
            msg_type=MessageType.JOB_REQ,
            seq=7,
            job_id=99,
            payload=bridge.JOB_REQ_STRUCT.pack(
                bytes.fromhex(FORMAL_TRUSTED_CURRENT_SHA),
                60000,
                1,
                3,
            ),
        )
        rx_frame = bridge.build_frame(
            msg_type=MessageType.JOB_ACK,
            seq=7,
            job_id=99,
            payload=bridge.JOB_ACK_STRUCT.pack(int(Decision.ALLOW), int(FaultCode.NONE), 2),
        )
        args = bridge.argparse.Namespace(
            rpmsg_ctrl="/dev/null",
            rpmsg_dev="/dev/null",
            require_devices=False,
            response_timeout_sec=2.0,
            settle_timeout_sec=0.05,
            max_rx_bytes=4096,
            drain_before_send=True,
            seq=1,
            hook_stdin=True,
            job_id=0,
        )
        hook_event = {
            "phase": "JOB_REQ",
            "payload": {
                "job_id": 99,
                "tx_frame_hex": tx_frame.hex(),
                "expected_sha256": "0" * 64,
                "deadline_ms": 1,
                "expected_outputs": 1,
                "job_flags": "payload",
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir_raw:
            output_dir = Path(temp_dir_raw)
            with mock.patch.object(
                bridge,
                "transact",
                return_value={
                    "drained_bytes": b"",
                    "written_bytes": len(tx_frame),
                    "rx_bytes": rx_frame,
                    "rx_timeout": False,
                },
            ) as transact_mock:
                summary = bridge.run_job_probe(
                    args=args,
                    output_dir=output_dir,
                    phase="JOB_REQ",
                    hook_event=hook_event,
                )

        self.assertEqual(transact_mock.call_args.kwargs["tx_bytes"], tx_frame)
        self.assertEqual(summary["decision"], "ALLOW")
        self.assertEqual(summary["seq"], 7)
        self.assertEqual(summary["tx_frame"]["job_req"]["expected_sha256_hex"], FORMAL_TRUSTED_CURRENT_SHA)

    def test_build_heartbeat_payload_defaults_missing_progress_fields(self) -> None:
        payload = bridge.build_heartbeat_payload_from_hook(
            {
                "phase": "HEARTBEAT",
                "payload": {
                    "job_id": 42,
                    "elapsed_ms": 1500,
                    "runtime_state": "RUNNING",
                },
            }
        )

        parsed = bridge.parse_heartbeat_payload(payload)
        self.assertTrue(parsed["parsed"])
        self.assertEqual(parsed["runtime_state_name"], "RUNNING")
        self.assertEqual(parsed["elapsed_ms"], 1500)
        self.assertEqual(parsed["completed_outputs"], 0)
        self.assertEqual(parsed["progress_x100"], 0)

    def test_build_safe_stop_payload_is_empty_wire_body(self) -> None:
        payload = bridge.build_safe_stop_payload_from_hook(
            {
                "phase": "SAFE_STOP",
                "payload": {
                    "job_id": 42,
                    "reason": "runner_timeout",
                },
            }
        )

        self.assertEqual(payload, b"")

    def test_build_job_done_payload_defaults_optional_fields(self) -> None:
        payload = bridge.build_job_done_payload_from_hook(
            {
                "phase": "JOB_DONE",
                "payload": {
                    "job_id": 42,
                    "elapsed_ms": 1500,
                    "result_code": 0,
                    "runner_exit_code": 0,
                    "timed_out": False,
                },
            }
        )

        parsed = bridge.parse_job_done_payload(payload)
        self.assertTrue(parsed["parsed"])
        self.assertEqual(parsed["result_code"], 0)
        self.assertEqual(parsed["output_count"], 0)
        self.assertEqual(parsed["result_crc32"], 0)
        self.assertEqual(parsed["reserved"], 0)
        self.assertTrue(parsed["reported_success"])

    def test_parse_job_ack_frame_and_classify_echo(self) -> None:
        ack_frame = bridge.build_frame(
            msg_type=MessageType.JOB_ACK,
            seq=7,
            job_id=1234,
            payload=bridge.JOB_ACK_STRUCT.pack(int(Decision.ALLOW), int(FaultCode.NONE), 2),
        )
        parsed = bridge.parse_frame(ack_frame)
        self.assertTrue(parsed["job_ack"]["parsed"])
        self.assertEqual(parsed["job_ack"]["decision_name"], "ALLOW")
        self.assertEqual(parsed["job_ack"]["guard_state_name"], "JOB_ACTIVE")

        req_frame = bridge.build_frame(
            msg_type=MessageType.JOB_REQ,
            seq=8,
            job_id=1234,
            payload=bridge.build_job_req_payload_from_hook(
                {
                    "phase": "JOB_REQ",
                    "payload": {
                        "job_id": 1234,
                        "expected_sha256": FORMAL_TRUSTED_CURRENT_SHA,
                        "deadline_ms": 500,
                        "expected_outputs": 1,
                        "job_flags": "smoke",
                    },
                }
            ),
        )
        summary = bridge.classify_job_probe(
            phase="JOB_REQ",
            tx_bytes=req_frame,
            rx_bytes=req_frame,
            rx_timeout=False,
        )
        self.assertEqual(summary["decision"], "DENY")
        self.assertEqual(summary["source"], "linux_bridge_transport_guard")
        self.assertEqual(summary["transport_status"], "transport_echo_only")

    def test_parse_heartbeat_ack_frame_and_classify_success(self) -> None:
        ack_frame = bridge.build_frame(
            msg_type=MessageType.HEARTBEAT_ACK,
            seq=9,
            job_id=1234,
            payload=bridge.HEARTBEAT_ACK_STRUCT.pack(2, 1),
        )
        parsed = bridge.parse_frame(ack_frame)
        self.assertTrue(parsed["heartbeat_ack"]["parsed"])
        self.assertEqual(parsed["heartbeat_ack"]["guard_state_name"], "JOB_ACTIVE")
        self.assertTrue(parsed["heartbeat_ack"]["acknowledged"])

        heartbeat_frame = bridge.build_frame(
            msg_type=MessageType.HEARTBEAT,
            seq=9,
            job_id=1234,
            payload=bridge.build_heartbeat_payload_from_hook(
                {
                    "phase": "HEARTBEAT",
                    "payload": {
                        "job_id": 1234,
                        "runtime_state": "RUNNING",
                        "elapsed_ms": 500,
                        "completed_outputs": 0,
                        "progress_x100": 0,
                    },
                }
            ),
        )
        summary = bridge.classify_heartbeat_probe(
            phase="HEARTBEAT",
            tx_bytes=heartbeat_frame,
            rx_bytes=ack_frame,
            rx_timeout=False,
        )
        self.assertTrue(summary["acknowledged"])
        self.assertEqual(summary["source"], "firmware_heartbeat_ack")
        self.assertEqual(summary["transport_status"], "heartbeat_ack_received")

    def test_classify_heartbeat_probe_negative_ack(self) -> None:
        heartbeat_frame = bridge.build_frame(
            msg_type=MessageType.HEARTBEAT,
            seq=10,
            job_id=5678,
            payload=bridge.build_heartbeat_payload_from_hook(
                {
                    "phase": "HEARTBEAT",
                    "payload": {
                        "job_id": 5678,
                        "runtime_state": "RUNNING",
                        "elapsed_ms": 750,
                    },
                }
            ),
        )
        ack_frame = bridge.build_frame(
            msg_type=MessageType.HEARTBEAT_ACK,
            seq=10,
            job_id=5678,
            payload=bridge.HEARTBEAT_ACK_STRUCT.pack(1, 0),
        )
        summary = bridge.classify_heartbeat_probe(
            phase="HEARTBEAT",
            tx_bytes=heartbeat_frame,
            rx_bytes=ack_frame,
            rx_timeout=False,
        )
        self.assertFalse(summary["acknowledged"])
        self.assertEqual(summary["guard_state_name"], "READY")
        self.assertEqual(summary["transport_status"], "heartbeat_ack_received_negative")

    def test_classify_job_done_probe_success_via_status_resp(self) -> None:
        job_done_frame = bridge.build_frame(
            msg_type=MessageType.JOB_DONE,
            seq=11,
            job_id=777,
            payload=bridge.build_job_done_payload_from_hook(
                {
                    "phase": "JOB_DONE",
                    "payload": {
                        "job_id": 777,
                        "result_code": 0,
                        "runner_exit_code": 0,
                        "timed_out": False,
                    },
                }
            ),
        )
        status_frame = bridge.build_frame(
            msg_type=MessageType.STATUS_RESP,
            seq=11,
            job_id=777,
            payload=bridge.STATUS_RESP_STRUCT.pack(
                1,
                0,
                int(FaultCode.NONE),
                0,
                0,
                0,
            ),
        )

        summary = bridge.classify_job_done_probe(
            phase="JOB_DONE",
            tx_bytes=job_done_frame,
            rx_bytes=status_frame,
            rx_timeout=False,
        )

        self.assertTrue(summary["acknowledged"])
        self.assertTrue(summary["reported_success"])
        self.assertEqual(summary["guard_state_name"], "READY")
        self.assertEqual(summary["last_fault_name"], "NONE")
        self.assertEqual(summary["transport_status"], "job_done_status_received")
        self.assertEqual(summary["source"], "firmware_job_done_status")

    def test_classify_job_done_probe_failed_result_via_status_resp(self) -> None:
        job_done_frame = bridge.build_frame(
            msg_type=MessageType.JOB_DONE,
            seq=12,
            job_id=778,
            payload=bridge.build_job_done_payload_from_hook(
                {
                    "phase": "JOB_DONE",
                    "payload": {
                        "job_id": 778,
                        "result_code": 1,
                        "runner_exit_code": 3,
                        "timed_out": False,
                    },
                }
            ),
        )
        status_frame = bridge.build_frame(
            msg_type=MessageType.STATUS_RESP,
            seq=12,
            job_id=778,
            payload=bridge.STATUS_RESP_STRUCT.pack(
                1,
                0,
                int(FaultCode.OUTPUT_INCOMPLETE),
                0,
                0,
                1,
            ),
        )

        summary = bridge.classify_job_done_probe(
            phase="JOB_DONE",
            tx_bytes=job_done_frame,
            rx_bytes=status_frame,
            rx_timeout=False,
        )

        self.assertTrue(summary["acknowledged"])
        self.assertFalse(summary["reported_success"])
        self.assertEqual(summary["last_fault_name"], "OUTPUT_INCOMPLETE")
        self.assertEqual(summary["transport_status"], "job_done_status_received")
        self.assertEqual(summary["source"], "firmware_job_done_status")

    def test_classify_safe_stop_probe_success_via_status_resp(self) -> None:
        safe_stop_frame = bridge.build_frame(
            msg_type=MessageType.SAFE_STOP,
            seq=11,
            job_id=777,
            payload=bridge.build_safe_stop_payload_from_hook(
                {
                    "phase": "SAFE_STOP",
                    "payload": {
                        "job_id": 777,
                        "reason": "runner_timeout",
                    },
                }
            ),
        )
        status_frame = bridge.build_frame(
            msg_type=MessageType.STATUS_RESP,
            seq=11,
            job_id=777,
            payload=bridge.STATUS_RESP_STRUCT.pack(
                1,
                0,
                int(FaultCode.MANUAL_SAFE_STOP),
                0,
                0,
                3,
            ),
        )

        summary = bridge.classify_safe_stop_probe(
            phase="SAFE_STOP",
            tx_bytes=safe_stop_frame,
            rx_bytes=status_frame,
            rx_timeout=False,
        )

        self.assertTrue(summary["acknowledged"])
        self.assertEqual(summary["guard_state_name"], "READY")
        self.assertEqual(summary["last_fault_name"], "MANUAL_SAFE_STOP")
        self.assertEqual(summary["transport_status"], "safe_stop_status_received")
        self.assertEqual(summary["source"], "firmware_safe_stop_status")

    def test_classify_safe_stop_probe_reports_negative_status_result(self) -> None:
        safe_stop_frame = bridge.build_frame(
            msg_type=MessageType.SAFE_STOP,
            seq=12,
            job_id=778,
            payload=bridge.build_safe_stop_payload_from_hook(
                {
                    "phase": "SAFE_STOP",
                    "payload": {
                        "job_id": 778,
                        "reason": "keyboard_interrupt",
                    },
                }
            ),
        )
        status_frame = bridge.build_frame(
            msg_type=MessageType.STATUS_RESP,
            seq=12,
            job_id=778,
            payload=bridge.STATUS_RESP_STRUCT.pack(
                2,
                778,
                int(FaultCode.NONE),
                1,
                0,
                1,
            ),
        )

        summary = bridge.classify_safe_stop_probe(
            phase="SAFE_STOP",
            tx_bytes=safe_stop_frame,
            rx_bytes=status_frame,
            rx_timeout=False,
        )

        self.assertFalse(summary["acknowledged"])
        self.assertEqual(summary["guard_state_name"], "JOB_ACTIVE")
        self.assertEqual(summary["active_job_id"], 778)
        self.assertEqual(summary["transport_status"], "safe_stop_status_received_not_applied")
        self.assertEqual(summary["source"], "firmware_safe_stop_status")


if __name__ == "__main__":
    unittest.main()
