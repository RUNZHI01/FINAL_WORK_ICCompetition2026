from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCH_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "patches"
    / "phytium_openamp_for_linux_signed_admission_impl_boundary_release_v1.4.0_2026-03-16.patch"
)
PATCH_NOTE_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "patches"
    / "phytium_openamp_for_linux_signed_admission_impl_boundary_release_v1.4.0_2026-03-16.md"
)
FIRMWARE_CONTRACT_PATH = (
    PROJECT_ROOT
    / "session_bootstrap"
    / "examples"
    / "openamp_signed_manifest.fixture.firmware_contract.json"
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


def parse_patch_define(text: str, name: str) -> int:
    pattern = re.compile(rf"^[+ ]#define\s+{re.escape(name)}\s+([0-9A-Fa-fxXuU]+)", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise AssertionError(f"missing {name} in patch artifact")
    return int(match.group(1).rstrip("Uu"), 0)


signed_manifest = load_module("openamp_signed_manifest_impl_boundary_test", SIGNED_MANIFEST_PATH)


class SignedAdmissionFirmwareImplBoundaryTest(unittest.TestCase):
    def test_firmware_contract_fixture_matches_protocol_constants(self) -> None:
        patch_text = PATCH_PATH.read_text(encoding="utf-8")
        firmware_contract = json.loads(FIRMWARE_CONTRACT_PATH.read_text(encoding="utf-8"))

        self.assertEqual(firmware_contract["schema"], signed_manifest.FIRMWARE_CONTRACT_SCHEMA)
        self.assertEqual(firmware_contract["message_types"], signed_manifest.SIGNED_ADMISSION_MSG_TYPES)
        self.assertEqual(firmware_contract["stage_codes"], signed_manifest.SIGNED_ADMISSION_STAGE_CODES)
        self.assertEqual(firmware_contract["ack_status_codes"], signed_manifest.SIGNED_ADMISSION_ACK_STATUS)
        self.assertEqual(firmware_contract["signature_algorithm_wire"], signed_manifest.SIGNED_ADMISSION_SIGNATURE_ALGORITHM)
        self.assertEqual(firmware_contract["admission_type_wire"], signed_manifest.SIGNED_ADMISSION_TYPE)

        self.assertEqual(parse_patch_define(patch_text, "SC_PUBLIC_KEY_UNCOMPRESSED_LEN"), 65)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_SCHEMA_ID_MAX_LEN"), 32)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_ARTIFACT_PATH_MAX_LEN"), 160)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_ARTIFACT_FORMAT_MAX_LEN"), 48)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_VARIANT_MAX_LEN"), 32)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_KEY_ID_MAX_LEN"), 32)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_CHANNEL_MAX_LEN"), 32)
        self.assertEqual(parse_patch_define(patch_text, "SC_MANIFEST_INPUT_DTYPE_MAX_LEN"), 16)

    def test_patch_embeds_fixture_public_key_and_parser_boundary(self) -> None:
        patch_text = PATCH_PATH.read_text(encoding="utf-8")
        firmware_contract = json.loads(FIRMWARE_CONTRACT_PATH.read_text(encoding="utf-8"))

        for line in firmware_contract["public_key_slot"]["c_initializer_lines"]:
            self.assertIn(line, patch_text)
        self.assertIn(firmware_contract["public_key_slot"]["key_id"], patch_text)
        self.assertIn(firmware_contract["public_key_slot"]["channel"], patch_text)

        for symbol in (
            "ScEcdsaP256VerifyRequest",
            '"openamp_artifact_manifest/v1"',
            "sc_ctrl_verify_manifest_signature(slot,",
            "sc_signed_stage.manifest_sha256",
        ):
            self.assertIn(symbol, patch_text)

        for helper_name in firmware_contract["parser_strategy"]["required_helpers"]:
            self.assertIn(helper_name, patch_text)
        for marker in firmware_contract["parser_strategy"]["parse_call_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["parser_strategy"]["strict_field_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["parser_strategy"]["optional_field_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["parser_strategy"]["slot_binding_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["include_guard_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["required_symbols"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["sha256_wrapper"]["validation_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["sha256_wrapper"]["call_sequence"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["sha256_wrapper"]["implementation_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["verify_wrapper"]["validation_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["verify_wrapper"]["context_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["verify_wrapper"]["cleanup_sequence"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["verify_wrapper"]["implementation_markers"]:
            self.assertIn(marker, patch_text)
        for marker in firmware_contract["crypto_boundary"]["mbedtls_call_sequence"]:
            self.assertIn(marker, patch_text)

        self.assertNotIn("+            /* TODO(next): replace placeholder bytes", patch_text)
        self.assertNotIn("+    /* TODO(next): implement strict field extraction", patch_text)
        self.assertNotIn("standalone SDK drop-in", patch_text)
        self.assertNotIn("+     * TODO(next): replace this deny-by-default stub", patch_text)
        self.assertNotIn("mbedtls_ecdsa_from_keypair", patch_text)

    def test_patch_note_keeps_non_admitting_status_explicit(self) -> None:
        note_text = PATCH_NOTE_PATH.read_text(encoding="utf-8")

        self.assertIn("Board firmware does not support signed admission yet.", note_text)
        self.assertIn("deny-by-default", note_text)
        self.assertIn("openamp_signed_manifest.fixture.firmware_contract.json", note_text)
        self.assertIn("SC_CTRL_USE_MBEDTLS", note_text)
        self.assertIn("sc_ctrl_crypto_sha256(...)", note_text)
        self.assertIn("sc_ctrl_crypto_verify_ecdsa_p256_sha256_der(...)", note_text)
        self.assertIn("artifact.size_bytes", note_text)
        self.assertIn("provenance.source_repo", note_text)
        self.assertIn("mbedtls_sha256_ret", note_text)
        self.assertIn("publisher.key_id / publisher.channel", note_text)
        self.assertIn("mbedtls_ecp_check_pubkey", note_text)
        self.assertIn("Legacy `JOB_REQ` SHA allowlist behavior remains intact", note_text)


if __name__ == "__main__":
    unittest.main()
