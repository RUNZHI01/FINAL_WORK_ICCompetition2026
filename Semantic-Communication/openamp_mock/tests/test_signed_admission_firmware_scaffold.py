from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
import unittest

from openamp_mock.protocol import FaultCode, MessageType


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCH_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "patches"
    / "phytium_openamp_for_linux_signed_admission_scaffold_release_v1.4.0_2026-03-16.patch"
)
PATCH_NOTE_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "patches"
    / "phytium_openamp_for_linux_signed_admission_scaffold_release_v1.4.0_2026-03-16.md"
)
TRANSPORT_DOC_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "runbooks"
    / "openamp_signed_admission_transport_v1_2026-03-16.md"
)
SIGNED_MANIFEST_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_signed_manifest.py"
)


def load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


signed_manifest = load_module("openamp_signed_manifest_test_scaffold", SIGNED_MANIFEST_PATH)


def parse_patch_define(text: str, name: str) -> int:
    pattern = re.compile(rf"^[+ ]#define\s+{re.escape(name)}\s+([0-9A-Fa-fxXuU]+)", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise AssertionError(f"missing {name} in patch artifact")
    return int(match.group(1).rstrip("Uu"), 0)


def doc_has_message_row(text: str, name: str, value: int) -> bool:
    row = f"| `{name}` | `0x{value:04X}` |"
    return row in text


def doc_has_status_row(text: str, name: str, value: int) -> bool:
    row = f"| `{name}` | `{value}` |"
    return row in text


class SignedAdmissionFirmwareScaffoldTest(unittest.TestCase):
    def test_patch_constants_match_tooling_and_protocol_enums(self) -> None:
        patch_text = PATCH_PATH.read_text(encoding="utf-8")

        message_define_names = {
            "SC_MSG_SIGNED_ADMISSION_BEGIN": "SIGNED_ADMISSION_BEGIN",
            "SC_MSG_SIGNED_ADMISSION_CHUNK": "SIGNED_ADMISSION_CHUNK",
            "SC_MSG_SIGNED_ADMISSION_SIGNATURE": "SIGNED_ADMISSION_SIGNATURE",
            "SC_MSG_SIGNED_ADMISSION_COMMIT": "SIGNED_ADMISSION_COMMIT",
            "SC_MSG_SIGNED_ADMISSION_ACK": "SIGNED_ADMISSION_ACK",
        }
        for define_name, message_name in message_define_names.items():
            value = parse_patch_define(patch_text, define_name)
            self.assertEqual(value, signed_manifest.SIGNED_ADMISSION_MSG_TYPES[message_name])
            self.assertEqual(value, int(getattr(MessageType, message_name)))

        stage_define_names = {
            "SC_SIGNED_STAGE_BEGIN": "BEGIN",
            "SC_SIGNED_STAGE_CHUNK": "CHUNK",
            "SC_SIGNED_STAGE_SIGNATURE": "SIGNATURE",
            "SC_SIGNED_STAGE_COMMIT": "COMMIT",
        }
        for define_name, stage_name in stage_define_names.items():
            self.assertEqual(
                parse_patch_define(patch_text, define_name),
                signed_manifest.SIGNED_ADMISSION_STAGE_CODES[stage_name],
            )

        ack_define_names = {
            "SC_SIGNED_ACK_ACCEPTED": "ACCEPTED",
            "SC_SIGNED_ACK_DUPLICATE": "DUPLICATE",
            "SC_SIGNED_ACK_OUT_OF_RANGE": "OUT_OF_RANGE",
            "SC_SIGNED_ACK_CRC_ERROR": "CRC_ERROR",
            "SC_SIGNED_ACK_TOO_LARGE": "TOO_LARGE",
            "SC_SIGNED_ACK_READY": "READY",
        }
        for define_name, status_name in ack_define_names.items():
            self.assertEqual(
                parse_patch_define(patch_text, define_name),
                signed_manifest.SIGNED_ADMISSION_ACK_STATUS[status_name],
            )

        fault_define_names = {
            "SC_FAULT_MANIFEST_NOT_STAGED": FaultCode.MANIFEST_NOT_STAGED,
            "SC_FAULT_MANIFEST_DIGEST_MISMATCH": FaultCode.MANIFEST_DIGEST_MISMATCH,
            "SC_FAULT_MANIFEST_PARSE_ERROR": FaultCode.MANIFEST_PARSE_ERROR,
            "SC_FAULT_SIGNATURE_INVALID": FaultCode.SIGNATURE_INVALID,
            "SC_FAULT_KEY_SLOT_UNKNOWN": FaultCode.KEY_SLOT_UNKNOWN,
            "SC_FAULT_MANIFEST_CONTRACT_MISMATCH": FaultCode.MANIFEST_CONTRACT_MISMATCH,
        }
        for define_name, fault_code in fault_define_names.items():
            self.assertEqual(parse_patch_define(patch_text, define_name), int(fault_code))

        self.assertEqual(parse_patch_define(patch_text, "SC_ADMISSION_TYPE_SIGNED_MANIFEST_V1"), 1)
        self.assertEqual(parse_patch_define(patch_text, "SC_SIGALG_ECDSA_P256_SHA256_DER"), 1)
        self.assertEqual(parse_patch_define(patch_text, "SC_SIGNED_MANIFEST_MAX_LEN"), 1536)
        self.assertEqual(parse_patch_define(patch_text, "SC_SIGNED_SIGNATURE_MAX_LEN"), 96)
        self.assertEqual(
            parse_patch_define(patch_text, "SC_SIGNED_MANIFEST_CHUNK_MAX"),
            signed_manifest.SIGNED_ADMISSION_CHUNK_DATA_MAX,
        )
        self.assertEqual(parse_patch_define(patch_text, "SC_SIGNED_MANIFEST_MAX_CHUNK_COUNT"), 10)

    def test_patch_scaffold_wires_handlers_and_keeps_legacy_job_req_path(self) -> None:
        patch_text = PATCH_PATH.read_text(encoding="utf-8")

        for helper_name in (
            "sc_ctrl_clear_signed_stage",
            "sc_ctrl_lookup_public_key_slot",
            "sc_ctrl_send_signed_admission_ack",
            "sc_ctrl_handle_signed_admission_begin",
            "sc_ctrl_handle_signed_admission_chunk",
            "sc_ctrl_handle_signed_admission_signature",
            "sc_ctrl_handle_signed_admission_commit",
            "sc_ctrl_parse_manifest_contract",
            "sc_ctrl_verify_signed_manifest_for_job_req",
        ):
            self.assertIn(helper_name, patch_text)

        for switch_case in (
            "case SC_MSG_SIGNED_ADMISSION_BEGIN:",
            "case SC_MSG_SIGNED_ADMISSION_CHUNK:",
            "case SC_MSG_SIGNED_ADMISSION_SIGNATURE:",
            "case SC_MSG_SIGNED_ADMISSION_COMMIT:",
        ):
            self.assertIn(switch_case, patch_text)

        self.assertIn("signed_path_requested = sc_ctrl_is_signed_stage_for_job(request_header->job_id);", patch_text)
        self.assertIn("sc_ctrl_verify_signed_manifest_for_job_req(request_header, &request);", patch_text)
        self.assertIn("sc_ctrl_is_trusted_artifact_sha(request.expected_sha256, &matched_artifact)", patch_text)
        self.assertIn("TODO(next): replace this deny-by-default stub", patch_text)
        self.assertIn("TODO(next): implement strict field extraction", patch_text)
        self.assertGreaterEqual(patch_text.count("sc_ctrl_clear_signed_stage();"), 5)

    def test_patch_note_and_transport_doc_match_scaffold_contract(self) -> None:
        note_text = PATCH_NOTE_PATH.read_text(encoding="utf-8")
        doc_text = TRANSPORT_DOC_PATH.read_text(encoding="utf-8")

        self.assertIn("Board firmware does not support signed admission yet.", note_text)
        self.assertIn("Legacy `JOB_REQ` SHA allowlist behavior remains intact", note_text)
        self.assertIn("deny-by-default stub", note_text)
        self.assertIn("Exact next firmware coding step:", note_text)
        self.assertIn("openamp_signed_manifest.fixture.transport.json", note_text)

        for message_name, value in signed_manifest.SIGNED_ADMISSION_MSG_TYPES.items():
            self.assertTrue(doc_has_message_row(doc_text, message_name, value))
        for status_name, value in signed_manifest.SIGNED_ADMISSION_ACK_STATUS.items():
            self.assertTrue(doc_has_status_row(doc_text, status_name, value))

        self.assertIn("`manifest_max_len = 1536`", doc_text)
        self.assertIn("`signature_max_len = 96`", doc_text)
        self.assertIn("`chunk_data_max = 160`", doc_text)
        self.assertIn("`max_chunk_count = 10`", doc_text)


if __name__ == "__main__":
    unittest.main()
