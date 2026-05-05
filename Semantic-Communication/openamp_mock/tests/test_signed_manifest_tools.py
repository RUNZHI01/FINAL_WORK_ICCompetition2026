from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIGNED_MANIFEST_PATH = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_signed_manifest.py"
WRAPPER_PATH = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_control_wrapper.py"
TRUSTED_ARTIFACTS_PATH = PROJECT_ROOT / "session_bootstrap" / "scripts" / "openamp_trusted_artifacts.py"
FIXTURE_ARTIFACT_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "examples" / "openamp_signed_manifest.fixture.artifact.so"
)
FIXTURE_MANIFEST_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "examples" / "openamp_signed_manifest.fixture.manifest.json"
)
FIXTURE_BUNDLE_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "examples" / "openamp_signed_manifest.fixture.bundle.json"
)
FIXTURE_PUBLIC_KEY_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "examples" / "openamp_signed_manifest.fixture.public.pem"
)
FIXTURE_TRANSPORT_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "examples" / "openamp_signed_manifest.fixture.transport.json"
)
FIXTURE_FIRMWARE_CONTRACT_PATH = (
    PROJECT_ROOT / "session_bootstrap" / "examples" / "openamp_signed_manifest.fixture.firmware_contract.json"
)


def load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


signed_manifest = load_module("openamp_signed_manifest_test", SIGNED_MANIFEST_PATH)
trusted_artifacts = load_module("openamp_trusted_artifacts_test_signed", TRUSTED_ARTIFACTS_PATH)
wrapper = load_module("openamp_control_wrapper_test_signed", WRAPPER_PATH)


class SignedManifestToolsTest(unittest.TestCase):
    def generate_keypair(self, temp_dir: Path) -> tuple[Path, Path]:
        private_key = temp_dir / "signing.pem"
        public_key = temp_dir / "signing.pub.pem"
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

    def test_build_manifest_records_artifact_sha_and_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_build_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            artifact_path.write_bytes(b"openamp-signed-manifest-test")

            manifest = signed_manifest.build_manifest(
                artifact_path=artifact_path,
                variant="current",
                key_id="dev-local-20260316",
                publisher_channel="openamp-dev",
                deadline_ms=12345,
                expected_outputs=300,
                job_flags="reconstruction",
            )

        self.assertEqual(
            manifest["artifact"]["sha256"],
            hashlib.sha256(b"openamp-signed-manifest-test").hexdigest(),
        )
        self.assertEqual(manifest["artifact"]["size_bytes"], len(b"openamp-signed-manifest-test"))
        self.assertEqual(manifest["job"]["deadline_ms"], 12345)
        self.assertEqual(manifest["job"]["expected_outputs"], 300)
        self.assertEqual(manifest["job"]["job_flags"], "reconstruction")
        self.assertEqual(manifest["publisher"]["key_id"], "dev-local-20260316")

    def test_sign_and_verify_round_trip_with_openssl(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_roundtrip_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            artifact_path.write_bytes(b"round-trip-artifact")
            private_key, public_key = self.generate_keypair(temp_dir)

            bundle = signed_manifest.build_signed_manifest_bundle(
                artifact_path=artifact_path,
                variant="current",
                key_id="dev-local-20260316",
                publisher_channel="openamp-dev",
                deadline_ms=300000,
                expected_outputs=300,
                job_flags="reconstruction",
                private_key=private_key,
            )

            summary = signed_manifest.verify_signed_manifest_bundle(
                bundle,
                public_key=public_key,
                artifact_path=artifact_path,
            )

        self.assertTrue(summary["verified_locally"])
        self.assertTrue(summary["artifact_match"])
        self.assertEqual(summary["signature_algorithm"], "ecdsa-p256-sha256")
        self.assertEqual(summary["key_id"], "dev-local-20260316")
        self.assertEqual(summary["variant"], "current")

    def test_bundle_command_builds_and_signs_in_one_step(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_bundle_cmd_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            artifact_path.write_bytes(b"bundle-command-artifact")
            private_key, public_key = self.generate_keypair(temp_dir)
            output_path = temp_dir / "signed_bundle.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SIGNED_MANIFEST_PATH),
                    "bundle",
                    "--artifact",
                    str(artifact_path),
                    "--private-key",
                    str(private_key),
                    "--output",
                    str(output_path),
                    "--variant",
                    "current",
                    "--key-id",
                    "dev-local-20260316",
                    "--publisher-channel",
                    "openamp-dev",
                    "--deadline-ms",
                    "60000",
                    "--expected-outputs",
                    "300",
                    "--job-flags",
                    "reconstruction",
                    "--created-at",
                    "2026-03-16T16:00:00+0800",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            summary = json.loads(result.stdout)
            bundle = signed_manifest.load_signed_manifest_bundle(output_path)
            verify_summary = signed_manifest.verify_signed_manifest_bundle(
                bundle,
                public_key=public_key,
                artifact_path=artifact_path,
            )

        self.assertEqual(summary["command"], "bundle")
        self.assertEqual(summary["output"], str(output_path))
        self.assertEqual(summary["manifest_sha256"], bundle["manifest_sha256"])
        self.assertEqual(bundle["manifest"]["provenance"]["created_at"], "2026-03-16T16:00:00+0800")
        self.assertTrue(verify_summary["verified_locally"])
        self.assertTrue(verify_summary["artifact_match"])

    def test_verify_rejects_tampered_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_tamper_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            artifact_path.write_bytes(b"tamper-artifact")
            private_key, public_key = self.generate_keypair(temp_dir)

            bundle = signed_manifest.build_signed_manifest_bundle(
                artifact_path=artifact_path,
                variant="current",
                key_id="dev-local-20260316",
                publisher_channel="openamp-dev",
                deadline_ms=300000,
                expected_outputs=300,
                job_flags="reconstruction",
                private_key=private_key,
            )
            bundle["manifest"]["job"]["deadline_ms"] = 300001

            with self.assertRaises(ValueError) as raised:
                signed_manifest.verify_signed_manifest_bundle(
                    bundle,
                    public_key=public_key,
                    artifact_path=artifact_path,
                )

        self.assertIn("manifest_sha256", str(raised.exception))

    def test_wrapper_signed_manifest_mode_uses_manifest_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_wrapper_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            artifact_path.write_bytes(b"wrapper-artifact")
            private_key, public_key = self.generate_keypair(temp_dir)
            bundle = signed_manifest.build_signed_manifest_bundle(
                artifact_path=artifact_path,
                variant="current",
                key_id="dev-local-20260316",
                publisher_channel="openamp-dev",
                deadline_ms=42000,
                expected_outputs=300,
                job_flags="reconstruction",
                private_key=private_key,
            )
            bundle_path = temp_dir / "signed_bundle.json"
            signed_manifest.write_json(bundle_path, bundle)

            args = SimpleNamespace(
                expected_sha256="",
                trusted_artifact_label="",
                trusted_artifacts_file=str(trusted_artifacts.DEFAULT_TRUSTED_ARTIFACTS_PATH),
                variant="legacy-placeholder",
                admission_mode="signed_manifest_v1",
                signed_manifest_file=str(bundle_path),
                signed_manifest_public_key=str(public_key),
            )

            expected_sha256, trusted_artifact, source, signed_admission = wrapper.resolve_admission_context(args)
            payload = wrapper.build_job_req_payload(
                job_id=7,
                expected_sha256=expected_sha256,
                deadline_ms=int(signed_admission["deadline_ms"]),
                expected_outputs=int(signed_admission["expected_outputs"]),
                job_flags=str(signed_admission["job_flags"]),
                runner_cmd="echo noop",
                trusted_artifact=trusted_artifact,
                signed_admission=signed_admission,
            )

        self.assertEqual(source, "--signed-manifest-file")
        self.assertIsNone(trusted_artifact)
        self.assertIsNotNone(signed_admission)
        assert signed_admission is not None
        self.assertTrue(signed_admission["verified_locally"])
        self.assertTrue(signed_admission["artifact_match"])
        self.assertEqual(expected_sha256, bundle["manifest"]["artifact"]["sha256"])
        self.assertEqual(signed_admission["variant"], "current")
        self.assertEqual(signed_admission["deadline_ms"], 42000)
        self.assertEqual(payload["signed_manifest"]["manifest_sha256"], bundle["manifest_sha256"])
        self.assertEqual(payload["signed_manifest"]["key_id"], "dev-local-20260316")

    def test_transport_plan_keeps_existing_job_req_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_transport_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            artifact_path = temp_dir / "optimized_model.so"
            artifact_path.write_bytes(b"transport-plan-artifact")
            private_key, _ = self.generate_keypair(temp_dir)

            bundle = signed_manifest.build_signed_manifest_bundle(
                artifact_path=artifact_path,
                variant="current",
                key_id="dev-local-20260316",
                publisher_channel="openamp-dev",
                deadline_ms=60000,
                expected_outputs=300,
                job_flags="reconstruction",
                private_key=private_key,
                created_at="2026-03-16T16:10:00+0800",
            )
            plan = signed_manifest.build_signed_admission_transport_plan(
                bundle,
                job_id=7301,
                key_slot=1,
                chunk_size=160,
                seq_start=1,
            )

        self.assertEqual(plan["schema"], "openamp_signed_admission_transport_plan/v1")
        self.assertEqual(plan["frames"][0]["phase"], "SIGNED_ADMISSION_BEGIN")
        self.assertEqual(plan["frames"][-1]["phase"], "JOB_REQ")
        self.assertEqual(plan["expected_job_req_payload_len"], 44)
        self.assertEqual(plan["frames"][-1]["payload_len"], 44)
        self.assertEqual(plan["frames"][-1]["payload"]["job_flags"], "reconstruction")
        self.assertEqual(plan["frames"][-1]["payload"]["flags"], 2)
        chunk_frames = [frame for frame in plan["frames"] if frame["phase"] == "SIGNED_ADMISSION_CHUNK"]
        self.assertGreaterEqual(len(chunk_frames), 1)
        self.assertTrue(all(frame["payload"]["chunk_len"] <= 160 for frame in chunk_frames))

    def test_public_key_extraction_matches_committed_fixture_bytes(self) -> None:
        public_key_bytes = signed_manifest.extract_p256_public_key_uncompressed(FIXTURE_PUBLIC_KEY_PATH)

        self.assertEqual(len(public_key_bytes), 65)
        self.assertEqual(public_key_bytes[:1], b"\x04")
        self.assertEqual(
            public_key_bytes.hex(),
            (
                "04aaef2bc7f2dd9af211bd3bc4f3bad1bcaeb7e25baacc0100e13ec51c12bdae"
                "62da2b87f3a1659721602600025d08f77d3a6a23b295316b917d2ebb081d15d305"
            ),
        )

    def test_firmware_contract_command_emits_expected_fixture_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="signed_manifest_fw_contract_") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            output_path = temp_dir / "firmware_contract.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SIGNED_MANIFEST_PATH),
                    "firmware-contract",
                    "--signed-manifest",
                    str(FIXTURE_BUNDLE_PATH),
                    "--public-key",
                    str(FIXTURE_PUBLIC_KEY_PATH),
                    "--key-slot",
                    "1",
                    "--output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            summary = json.loads(result.stdout)
            artifact = signed_manifest.load_json(output_path)

        self.assertEqual(summary["command"], "firmware-contract")
        self.assertEqual(summary["schema"], signed_manifest.FIRMWARE_CONTRACT_SCHEMA)
        self.assertEqual(summary["key_slot"], 1)
        self.assertEqual(artifact["public_key_slot"]["slot_id"], 1)
        self.assertIn('"openamp-fixture"', artifact["public_key_slot"]["c_initializer"])
        self.assertEqual(
            artifact["manifest_contract"]["artifact_sha256"],
            "09af47ee1b0e2a7d3cad3add031f36811926e1fe34cfd58fa98d70eba9526b91",
        )
        self.assertEqual(artifact["manifest_contract"]["artifact_size_bytes"], 119)
        self.assertEqual(
            artifact["manifest_contract"]["artifact_path"],
            "session_bootstrap/examples/openamp_signed_manifest.fixture.artifact.so",
        )
        self.assertEqual(artifact["manifest_contract"]["job_flags_wire"], 2)
        self.assertEqual(artifact["manifest_contract"]["input_shape"], [1, 32, 32, 32])
        self.assertEqual(artifact["manifest_contract"]["input_dtype"], "float32")
        self.assertEqual(
            artifact["manifest_contract"]["provenance_source_git_commit"],
            "execution-batch-fixture",
        )
        self.assertIn("firmware-side admission bring-up", artifact["manifest_contract"]["provenance_note"])
        field_paths = {entry["json_path"] for entry in artifact["manifest_contract"]["field_plan"]}
        self.assertIn("artifact.path", field_paths)
        self.assertIn("input_contract.shape", field_paths)
        self.assertIn("provenance.source_repo", field_paths)
        self.assertIn("provenance.note", field_paths)
        self.assertEqual(
            artifact["parser_strategy"]["slot_binding_markers"],
            [
                "strcmp(contract.publisher_key_id, slot->key_id)",
                "strcmp(contract.publisher_channel, slot->channel)",
            ],
        )
        self.assertIn("sc_ctrl_json_find_optional_string_field", artifact["parser_strategy"]["required_helpers"])
        self.assertIn("out_contract->artifact_path", artifact["parser_strategy"]["strict_field_markers"])
        self.assertIn(
            "sc_ctrl_json_find_optional_string_field(provenance_object.begin,",
            artifact["parser_strategy"]["optional_field_markers"],
        )
        self.assertEqual(artifact["crypto_boundary"]["enable_macro"], "SC_CTRL_USE_MBEDTLS")
        self.assertIn("mbedtls_sha256_ret", artifact["crypto_boundary"]["required_symbols"])
        self.assertIn("mbedtls_ecdsa_read_signature", artifact["crypto_boundary"]["required_symbols"])
        self.assertIn("#if defined(SC_CTRL_USE_MBEDTLS)", artifact["crypto_boundary"]["include_guard_markers"])
        self.assertIn(
            "mbedtls_ecp_check_pubkey(&ecdsa.grp, &ecdsa.Q)",
            artifact["crypto_boundary"]["mbedtls_call_sequence"],
        )
        self.assertIn(
            "sdk_status = mbedtls_sha256_ret(input, input_len, out_digest, 0);",
            artifact["crypto_boundary"]["sha256_wrapper"]["implementation_markers"],
        )
        self.assertNotIn("mbedtls_ecdsa_from_keypair", json.dumps(artifact["crypto_boundary"]))

    def test_committed_fixture_bundle_and_transport_plan_match_tool_output(self) -> None:
        manifest = signed_manifest.load_json(FIXTURE_MANIFEST_PATH)
        bundle = signed_manifest.load_signed_manifest_bundle(FIXTURE_BUNDLE_PATH)
        verify_summary = signed_manifest.verify_signed_manifest_bundle(
            bundle,
            public_key=FIXTURE_PUBLIC_KEY_PATH,
            artifact_path=FIXTURE_ARTIFACT_PATH,
        )
        fixture_transport = signed_manifest.load_json(FIXTURE_TRANSPORT_PATH)
        fixture_firmware_contract = signed_manifest.load_json(FIXTURE_FIRMWARE_CONTRACT_PATH)
        rebuilt_transport = signed_manifest.build_signed_admission_transport_plan(
            bundle,
            job_id=7301,
            key_slot=1,
            chunk_size=160,
            seq_start=1,
        )
        rebuilt_firmware_contract = signed_manifest.build_firmware_contract_artifact(
            bundle,
            public_key=FIXTURE_PUBLIC_KEY_PATH,
            key_slot=1,
        )

        self.assertEqual(manifest, bundle["manifest"])
        self.assertTrue(verify_summary["verified_locally"])
        self.assertTrue(verify_summary["artifact_match"])
        self.assertEqual(fixture_transport, rebuilt_transport)
        self.assertEqual(fixture_firmware_contract, rebuilt_firmware_contract)


if __name__ == "__main__":
    unittest.main()
