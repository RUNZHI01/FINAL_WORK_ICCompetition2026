from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import openamp_control_wrapper  # noqa: E402
import openamp_signed_manifest  # noqa: E402


def generate_keypair(temp_dir: Path) -> tuple[Path, Path]:
    private_key = temp_dir / "demo-signing.pem"
    public_key = temp_dir / "demo-signing.pub.pem"
    subprocess.run(
        [
            "openssl",
            "genpkey",
            "-algorithm",
            "EC",
            "-pkeyopt",
            "ec_paramgen_curve:P-256",
            "-out",
            str(private_key),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "openssl",
            "pkey",
            "-in",
            str(private_key),
            "-pubout",
            "-out",
            str(public_key),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return private_key, public_key


def build_signed_bundle(temp_dir: Path, *, variant: str) -> tuple[Path, Path]:
    artifact_path = temp_dir / f"{variant}_optimized_model.so"
    artifact_path.write_bytes(f"demo-signed-{variant}".encode("utf-8"))
    private_key, public_key = generate_keypair(temp_dir)
    bundle = openamp_signed_manifest.build_signed_manifest_bundle(
        artifact_path=artifact_path,
        variant=variant,
        key_id=f"demo-wrapper-{variant}-20260316",
        publisher_channel="openamp-demo",
        deadline_ms=60000,
        expected_outputs=1,
        job_flags="smoke",
        private_key=private_key,
    )
    bundle_path = temp_dir / f"{variant}.bundle.json"
    openamp_signed_manifest.write_json(bundle_path, bundle)
    return bundle_path, public_key


class OpenAMPControlWrapperTest(unittest.TestCase):
    def assert_signed_wrapper_trace(self, *, variant: str) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_dir = temp_dir / "wrapper"
            bundle_path, public_key = build_signed_bundle(temp_dir, variant=variant)
            bundle = openamp_signed_manifest.load_signed_manifest_bundle(bundle_path)
            transport_plan = openamp_signed_manifest.build_signed_admission_transport_plan(
                bundle,
                job_id=2026,
                key_slot=openamp_control_wrapper.SIGNED_ADMISSION_KEY_SLOT,
                seq_start=1,
            )
            args = openamp_control_wrapper.argparse.Namespace(
                runner_cmd="echo runner",
                output_dir=str(output_dir),
                job_id=2026,
                variant=variant,
                expected_sha256="",
                trusted_artifact_label="",
                trusted_artifacts_file=str(openamp_control_wrapper.DEFAULT_TRUSTED_ARTIFACTS_PATH),
                deadline_ms=300000,
                expected_outputs=300,
                job_flags="reconstruction",
                heartbeat_interval_sec=5.0,
                runner_timeout_sec=0.0,
                transport="hook",
                control_hook_cmd="echo hook",
                control_hook_timeout_sec=5.0,
                dry_run=True,
                admission_mode="signed_manifest_v1",
                signed_manifest_file=str(bundle_path),
                signed_manifest_public_key=str(public_key),
            )
            real_subprocess_run = subprocess.run

            def fake_hook_run(command, **kwargs):  # type: ignore[no-untyped-def]
                if kwargs.get("input") is None:
                    return real_subprocess_run(command, **kwargs)
                event = json.loads(kwargs["input"])
                phase = event["phase"]
                if phase == "STATUS_REQ":
                    response = {
                        "phase": phase,
                        "transport_status": "status_resp_received",
                        "protocol_semantics": "implemented",
                    }
                elif phase.startswith("SIGNED_ADMISSION_"):
                    response = {
                        "phase": phase,
                        "acknowledged": True,
                        "transport_status": "signed_admission_ack_received",
                        "protocol_semantics": "implemented",
                    }
                else:
                    response = {
                        "phase": phase,
                        "decision": "ALLOW",
                        "fault_code": 0,
                        "fault_name": "NONE",
                        "guard_state": 2,
                        "guard_state_name": "JOB_ACTIVE",
                        "transport_status": "job_ack_received",
                        "protocol_semantics": "implemented",
                    }
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout=json.dumps(response, ensure_ascii=False) + "\n",
                    stderr="",
                )

            stdout = io.StringIO()
            with (
                patch("openamp_control_wrapper.parse_args", return_value=args),
                patch(
                    "openamp_control_wrapper.resolve_expected_sha256",
                    return_value=("", None, "unset"),
                ),
                patch("openamp_control_wrapper.subprocess.run", side_effect=fake_hook_run),
                contextlib.redirect_stdout(stdout),
            ):
                result = openamp_control_wrapper.main()

            trace_events = [
                json.loads(line)
                for line in (output_dir / "control_trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            summary = json.loads(stdout.getvalue().strip())

        self.assertEqual(result, 0)
        self.assertEqual(
            [event["phase"] for event in trace_events],
            ["STATUS_REQ", *[frame["phase"] for frame in transport_plan["frames"]], "JOB_ACK"],
        )
        signed_events = [event for event in trace_events if event["phase"].startswith("SIGNED_ADMISSION_")]
        self.assertTrue(all(event["payload"].get("tx_frame_hex") for event in signed_events))
        self.assertTrue(all(event["payload"].get("signed_admission_frame") for event in signed_events))
        self.assertEqual(trace_events[-2]["payload"]["signed_admission_frame"]["phase"], "JOB_REQ")
        self.assertEqual(summary["result"], "dry_run_only")
        self.assertEqual(len(summary["signed_admission_responses"]), len(signed_events))

    def test_emit_event_records_hook_timeout_instead_of_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "control_trace.jsonl"
            timeout_error = subprocess.TimeoutExpired(
                cmd=["bash", "-lc", "echo hook"],
                timeout=7.5,
                output="",
            )
            timeout_error.stderr = "hook timed out\n"

            with patch(
                "openamp_control_wrapper.subprocess.run",
                side_effect=timeout_error,
            ):
                result = openamp_control_wrapper.emit_event(
                    trace_path=trace_path,
                    phase="HEARTBEAT",
                    payload={"job_id": 101},
                    transport="hook",
                    hook_cmd="echo hook",
                    hook_timeout_sec=7.5,
                )
            event = json.loads(trace_path.read_text(encoding="utf-8").strip())

        self.assertIsNone(result["returncode"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["timeout_sec"], 7.5)
        self.assertEqual(result["stderr"], "hook timed out\n")
        self.assertEqual(
            result["response"],
            {
                "phase": "HEARTBEAT",
                "source": "openamp_control_wrapper",
                "transport_status": "hook_timeout",
                "protocol_semantics": "not_verified",
                "note": "HEARTBEAT control hook timed out after 7.5s.",
            },
        )
        self.assertTrue(event["hook_result"]["timed_out"])

    def test_emit_event_records_hook_exception_instead_of_dropping_phase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "control_trace.jsonl"

            with patch(
                "openamp_control_wrapper.subprocess.run",
                side_effect=RuntimeError("hook proxy crashed"),
            ):
                result = openamp_control_wrapper.emit_event(
                    trace_path=trace_path,
                    phase="JOB_DONE",
                    payload={"job_id": 2026, "result_code": 0},
                    transport="hook",
                    hook_cmd="echo hook",
                    hook_timeout_sec=5.0,
                )
            event = json.loads(trace_path.read_text(encoding="utf-8").strip())

        self.assertEqual(result["returncode"], -1)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["response"]["phase"], "JOB_DONE")
        self.assertEqual(result["response"]["transport_status"], "hook_error")
        self.assertIn("hook proxy crashed", result["response"]["note"])
        self.assertEqual(event["phase"], "JOB_DONE")
        self.assertEqual(event["hook_result"]["response"]["transport_status"], "hook_error")

    def test_main_keeps_duplicate_job_id_denial_visible_without_retrying(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            args = openamp_control_wrapper.argparse.Namespace(
                runner_cmd="echo runner",
                output_dir=str(output_dir),
                job_id=101,
                variant="current_reconstruction",
                expected_sha256="",
                trusted_artifact_label="",
                trusted_artifacts_file=str(output_dir / "trusted.json"),
                deadline_ms=300000,
                expected_outputs=300,
                job_flags="reconstruction",
                heartbeat_interval_sec=5.0,
                runner_timeout_sec=0.0,
                transport="hook",
                control_hook_cmd="echo hook",
                control_hook_timeout_sec=5.0,
                dry_run=False,
                admission_mode="legacy_sha",
                signed_manifest_file="",
                signed_manifest_public_key="",
            )
            emit_calls: list[tuple[str, int]] = []

            def fake_emit_event(*, trace_path, phase, payload, transport, hook_cmd, hook_timeout_sec):  # type: ignore[no-untyped-def]
                emit_calls.append((phase, int(payload.get("job_id", 0) or 0)))
                if phase == "STATUS_REQ":
                    return {
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                        }
                    }
                if phase == "JOB_REQ" and payload["job_id"] == 101:
                    return {
                        "response": {
                            "phase": "JOB_REQ",
                            "decision": "DENY",
                            "fault_name": "DUPLICATE_JOB_ID",
                            "guard_state_name": "JOB_ACTIVE",
                            "transport_status": "job_ack_received",
                            "protocol_semantics": "implemented",
                            "note": "Received a decodable JOB_ACK frame from firmware.",
                        }
                    }
                return {}

            stdout = io.StringIO()
            with (
                patch("openamp_control_wrapper.parse_args", return_value=args),
                patch(
                    "openamp_control_wrapper.resolve_expected_sha256",
                    return_value=("a" * 64, None, "--expected-sha256"),
                ),
                patch("openamp_control_wrapper.emit_event", side_effect=fake_emit_event),
                contextlib.redirect_stdout(stdout),
            ):
                result = openamp_control_wrapper.main()
            manifest = json.loads((output_dir / "job_manifest.json").read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue().strip())

        self.assertEqual(result, 2)
        self.assertEqual(
            emit_calls,
            [
                ("STATUS_REQ", 101),
                ("JOB_REQ", 101),
                ("JOB_ACK", 101),
            ],
        )
        self.assertEqual(manifest["job_id"], 101)
        self.assertNotIn("requested_job_id", manifest)
        self.assertNotIn("retry_count", manifest)
        self.assertNotIn("retry_reason", manifest)
        self.assertEqual(summary["job_id"], 101)
        self.assertEqual(summary["result"], "denied_by_control_hook")

    def test_main_aborts_after_failed_status_req_without_sending_job_req(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            args = openamp_control_wrapper.argparse.Namespace(
                runner_cmd="echo runner",
                output_dir=str(output_dir),
                job_id=202,
                variant="current_reconstruction",
                expected_sha256="",
                trusted_artifact_label="",
                trusted_artifacts_file=str(output_dir / "trusted.json"),
                deadline_ms=300000,
                expected_outputs=300,
                job_flags="reconstruction",
                heartbeat_interval_sec=5.0,
                runner_timeout_sec=0.0,
                transport="hook",
                control_hook_cmd="echo hook",
                control_hook_timeout_sec=5.0,
                dry_run=False,
                admission_mode="legacy_sha",
                signed_manifest_file="",
                signed_manifest_public_key="",
            )
            emit_calls: list[str] = []

            def fake_emit_event(*, trace_path, phase, payload, transport, hook_cmd, hook_timeout_sec):  # type: ignore[no-untyped-def]
                emit_calls.append(phase)
                if phase == "STATUS_REQ":
                    return {
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "tx_ok_rx_timeout",
                            "protocol_semantics": "not_verified",
                            "note": (
                                "write to /dev/rpmsg0 succeeded but no response arrived before timeout. "
                                "Do not claim STATUS_RESP semantics from this result."
                            ),
                        }
                    }
                self.fail(f"unexpected phase {phase}")

            stdout = io.StringIO()
            with (
                patch("openamp_control_wrapper.parse_args", return_value=args),
                patch(
                    "openamp_control_wrapper.resolve_expected_sha256",
                    return_value=("a" * 64, None, "--expected-sha256"),
                ),
                patch("openamp_control_wrapper.emit_event", side_effect=fake_emit_event),
                contextlib.redirect_stdout(stdout),
            ):
                result = openamp_control_wrapper.main()
            summary = json.loads(stdout.getvalue().strip())

        self.assertEqual(result, 2)
        self.assertEqual(emit_calls, ["STATUS_REQ"])
        self.assertEqual(summary["result"], "denied_by_control_hook")
        self.assertEqual(summary["blocked_phase"], "STATUS_REQ")
        self.assertEqual(summary["job_req_response"], {})

    def test_main_aborts_after_failed_signed_admission_phase_without_job_req(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_dir = temp_dir / "wrapper"
            bundle_path, public_key = build_signed_bundle(temp_dir, variant="baseline")
            args = openamp_control_wrapper.argparse.Namespace(
                runner_cmd="echo runner",
                output_dir=str(output_dir),
                job_id=303,
                variant="baseline",
                expected_sha256="",
                trusted_artifact_label="",
                trusted_artifacts_file=str(openamp_control_wrapper.DEFAULT_TRUSTED_ARTIFACTS_PATH),
                deadline_ms=300000,
                expected_outputs=300,
                job_flags="reconstruction",
                heartbeat_interval_sec=5.0,
                runner_timeout_sec=0.0,
                transport="hook",
                control_hook_cmd="echo hook",
                control_hook_timeout_sec=5.0,
                dry_run=True,
                admission_mode="signed_manifest_v1",
                signed_manifest_file=str(bundle_path),
                signed_manifest_public_key=str(public_key),
            )
            emit_calls: list[str] = []

            def fake_emit_event(*, trace_path, phase, payload, transport, hook_cmd, hook_timeout_sec):  # type: ignore[no-untyped-def]
                emit_calls.append(phase)
                if phase == "STATUS_REQ":
                    return {
                        "response": {
                            "phase": "STATUS_REQ",
                            "transport_status": "status_resp_received",
                            "protocol_semantics": "implemented",
                        }
                    }
                if phase == "SIGNED_ADMISSION_BEGIN":
                    return {
                        "response": {
                            "phase": "SIGNED_ADMISSION_BEGIN",
                            "acknowledged": False,
                            "transport_status": "tx_ok_rx_timeout",
                            "protocol_semantics": "not_verified",
                        }
                    }
                self.fail(f"unexpected phase {phase}")

            stdout = io.StringIO()
            with (
                patch("openamp_control_wrapper.parse_args", return_value=args),
                patch(
                    "openamp_control_wrapper.resolve_expected_sha256",
                    return_value=("", None, "unset"),
                ),
                patch("openamp_control_wrapper.emit_event", side_effect=fake_emit_event),
                contextlib.redirect_stdout(stdout),
            ):
                result = openamp_control_wrapper.main()
            summary = json.loads(stdout.getvalue().strip())

        self.assertEqual(result, 2)
        self.assertEqual(emit_calls, ["STATUS_REQ", "SIGNED_ADMISSION_BEGIN"])
        self.assertEqual(summary["result"], "denied_by_control_hook")
        self.assertEqual(summary["blocked_phase"], "SIGNED_ADMISSION_BEGIN")
        self.assertEqual(summary["job_req_response"], {})
        self.assertEqual(len(summary["signed_admission_responses"]), 1)

    def test_main_signed_current_mode_emits_sideband_phases_before_job_req(self) -> None:
        self.assert_signed_wrapper_trace(variant="current")

    def test_main_signed_baseline_mode_emits_sideband_phases_before_job_req(self) -> None:
        self.assert_signed_wrapper_trace(variant="baseline")


if __name__ == "__main__":
    unittest.main()
