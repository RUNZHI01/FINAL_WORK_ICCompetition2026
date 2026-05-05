#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping
import zlib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEX_DIGITS = frozenset("0123456789abcdef")
MANIFEST_SCHEMA = "openamp_artifact_manifest/v1"
SIGNED_BUNDLE_SCHEMA = "openamp_signed_manifest_bundle/v1"
BUNDLE_VERSION = 1
SIGNATURE_ALGORITHM = "ecdsa-p256-sha256"
SIGNED_ADMISSION_TRANSPORT_SCHEMA = "openamp_signed_admission_transport_plan/v1"
FIRMWARE_CONTRACT_SCHEMA = "openamp_signed_admission_firmware_contract/v1"
CTRL_MAGIC = 0x53434F4D
CTRL_VERSION = 1
CTRL_HEADER_STRUCT = struct.Struct("<IHHIIII")
SIGNED_ADMISSION_TYPE = 1
SIGNED_ADMISSION_SIGNATURE_ALGORITHM = 1
SIGNED_ADMISSION_CHUNK_DATA_MAX = 160
P256_PUBLIC_KEY_UNCOMPRESSED_LEN = 65
JOB_FLAG_NAME_TO_WIRE = {
    "payload": 1,
    "reconstruction": 2,
    "smoke": 3,
}
SIGNED_ADMISSION_MSG_TYPES = {
    "SIGNED_ADMISSION_BEGIN": 0x000C,
    "SIGNED_ADMISSION_CHUNK": 0x000D,
    "SIGNED_ADMISSION_SIGNATURE": 0x000E,
    "SIGNED_ADMISSION_COMMIT": 0x000F,
    "SIGNED_ADMISSION_ACK": 0x0010,
}
SIGNED_ADMISSION_STAGE_CODES = {
    "BEGIN": 1,
    "CHUNK": 2,
    "SIGNATURE": 3,
    "COMMIT": 4,
}
SIGNED_ADMISSION_ACK_STATUS = {
    "ACCEPTED": 0,
    "DUPLICATE": 1,
    "OUT_OF_RANGE": 2,
    "CRC_ERROR": 3,
    "TOO_LARGE": 4,
    "READY": 5,
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def resolve_path(raw: str | Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def normalize_sha256(raw: Any, *, field_name: str) -> str:
    text = str(raw or "").strip().lower()
    if len(text) != 64 or any(char not in HEX_DIGITS for char in text):
        raise ValueError(f"{field_name} must be a 64-character SHA-256 hex string.")
    return text


def require_dict(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    return raw


def require_text(raw: Any, *, field_name: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def require_u32(raw: Any, *, field_name: str, allow_zero: bool = False) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{field_name} must be an integer.") from err
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    if not allow_zero and value == 0:
        raise ValueError(f"{field_name} must be > 0.")
    if value > 0xFFFFFFFF:
        raise ValueError(f"{field_name} must fit in u32.")
    return value


def compute_file_sha256(path: str | Path) -> str:
    resolved = resolve_path(path)
    digest = hashlib.sha256()
    with resolved.open("rb") as infile:
        while True:
            chunk = infile.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def canonicalize_manifest(manifest: Mapping[str, Any]) -> bytes:
    validate_manifest(manifest)
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def manifest_sha256_hex(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonicalize_manifest(manifest)).hexdigest()


def compute_crc32(payload: bytes) -> int:
    return zlib.crc32(payload) & 0xFFFFFFFF


def compute_control_header_crc(
    *,
    magic: int,
    version: int,
    msg_type: int,
    seq: int,
    job_id: int,
    payload_len: int,
) -> int:
    header_without_crc = struct.pack(
        "<IHHIII",
        magic,
        version,
        msg_type,
        seq,
        job_id,
        payload_len,
    )
    return compute_crc32(header_without_crc)


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    schema = require_text(manifest.get("schema"), field_name="manifest.schema")
    if schema != MANIFEST_SCHEMA:
        raise ValueError(f"manifest.schema must equal {MANIFEST_SCHEMA!r}.")

    version = require_u32(manifest.get("manifest_version"), field_name="manifest.manifest_version")
    if version != 1:
        raise ValueError("manifest.manifest_version must equal 1.")

    artifact = require_dict(manifest.get("artifact"), field_name="manifest.artifact")
    normalize_sha256(artifact.get("sha256"), field_name="manifest.artifact.sha256")
    require_u32(artifact.get("size_bytes"), field_name="manifest.artifact.size_bytes", allow_zero=True)
    require_text(artifact.get("path"), field_name="manifest.artifact.path")
    require_text(artifact.get("format"), field_name="manifest.artifact.format")
    require_text(artifact.get("variant"), field_name="manifest.artifact.variant")

    job = require_dict(manifest.get("job"), field_name="manifest.job")
    require_u32(job.get("deadline_ms"), field_name="manifest.job.deadline_ms")
    require_u32(job.get("expected_outputs"), field_name="manifest.job.expected_outputs")
    require_text(job.get("job_flags"), field_name="manifest.job.job_flags")

    input_contract = require_dict(manifest.get("input_contract"), field_name="manifest.input_contract")
    shape = input_contract.get("shape")
    if not isinstance(shape, list) or len(shape) != 4:
        raise ValueError("manifest.input_contract.shape must be a 4-element list.")
    for index, raw_dim in enumerate(shape):
        require_u32(raw_dim, field_name=f"manifest.input_contract.shape[{index}]")
    require_text(input_contract.get("dtype"), field_name="manifest.input_contract.dtype")

    publisher = require_dict(manifest.get("publisher"), field_name="manifest.publisher")
    require_text(publisher.get("key_id"), field_name="manifest.publisher.key_id")
    require_text(publisher.get("channel"), field_name="manifest.publisher.channel")

    provenance = require_dict(manifest.get("provenance"), field_name="manifest.provenance")
    require_text(provenance.get("created_at"), field_name="manifest.provenance.created_at")
    require_text(provenance.get("builder"), field_name="manifest.provenance.builder")
    require_text(provenance.get("source_repo"), field_name="manifest.provenance.source_repo")


def build_manifest(
    *,
    artifact_path: str | Path,
    variant: str,
    key_id: str,
    publisher_channel: str,
    deadline_ms: int,
    expected_outputs: int,
    job_flags: str,
    artifact_format: str = "tvm-module-shared-object",
    input_shape: tuple[int, int, int, int] = (1, 32, 32, 32),
    input_dtype: str = "float32",
    source_git_commit: str = "",
    note: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    resolved_artifact = resolve_path(artifact_path)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "manifest_version": 1,
        "artifact": {
            "path": str(artifact_path),
            "sha256": compute_file_sha256(resolved_artifact),
            "size_bytes": resolved_artifact.stat().st_size,
            "format": artifact_format,
            "variant": require_text(variant, field_name="variant"),
        },
        "job": {
            "deadline_ms": require_u32(deadline_ms, field_name="deadline_ms"),
            "expected_outputs": require_u32(expected_outputs, field_name="expected_outputs"),
            "job_flags": require_text(job_flags, field_name="job_flags"),
        },
        "input_contract": {
            "shape": [
                require_u32(input_shape[0], field_name="input_shape[0]"),
                require_u32(input_shape[1], field_name="input_shape[1]"),
                require_u32(input_shape[2], field_name="input_shape[2]"),
                require_u32(input_shape[3], field_name="input_shape[3]"),
            ],
            "dtype": require_text(input_dtype, field_name="input_dtype"),
        },
        "publisher": {
            "key_id": require_text(key_id, field_name="key_id"),
            "channel": require_text(publisher_channel, field_name="publisher_channel"),
        },
        "provenance": {
            "created_at": created_at or now_iso(),
            "builder": "session_bootstrap/scripts/openamp_signed_manifest.py",
            "source_repo": "tvm_metaschedule_execution_project",
        },
    }
    if source_git_commit:
        manifest["provenance"]["source_git_commit"] = str(source_git_commit).strip()
    if note:
        manifest["provenance"]["note"] = str(note).strip()
    validate_manifest(manifest)
    return manifest


def _run_openssl(command: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        command,
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or f"openssl exited with {result.returncode}"
        raise ValueError(detail)
    return result


def _sign_bytes_with_openssl(payload: bytes, *, private_key: str | Path, openssl_bin: str) -> bytes:
    private_key_path = resolve_path(private_key)
    with tempfile.TemporaryDirectory(prefix="openamp_sign_") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        payload_path = temp_dir / "manifest.bin"
        signature_path = temp_dir / "manifest.sig"
        payload_path.write_bytes(payload)
        _run_openssl(
            [
                openssl_bin,
                "dgst",
                "-sha256",
                "-sign",
                str(private_key_path),
                "-out",
                str(signature_path),
                str(payload_path),
            ]
        )
        return signature_path.read_bytes()


def _verify_bytes_with_openssl(
    payload: bytes,
    *,
    signature: bytes,
    public_key: str | Path,
    openssl_bin: str,
) -> None:
    public_key_path = resolve_path(public_key)
    with tempfile.TemporaryDirectory(prefix="openamp_verify_") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        payload_path = temp_dir / "manifest.bin"
        signature_path = temp_dir / "manifest.sig"
        payload_path.write_bytes(payload)
        signature_path.write_bytes(signature)
        _run_openssl(
            [
                openssl_bin,
                "dgst",
                "-sha256",
                "-verify",
                str(public_key_path),
                "-signature",
                str(signature_path),
                str(payload_path),
            ]
        )


def sign_manifest(
    manifest: Mapping[str, Any],
    *,
    private_key: str | Path,
    key_id: str | None = None,
    openssl_bin: str = "openssl",
) -> dict[str, Any]:
    validate_manifest(manifest)
    canonical = canonicalize_manifest(manifest)
    manifest_sha256 = hashlib.sha256(canonical).hexdigest()
    selected_key_id = require_text(
        key_id if key_id is not None else manifest["publisher"]["key_id"],
        field_name="key_id",
    )
    if selected_key_id != str(manifest["publisher"]["key_id"]).strip():
        raise ValueError("key_id must match manifest.publisher.key_id.")
    signature_bytes = _sign_bytes_with_openssl(canonical, private_key=private_key, openssl_bin=openssl_bin)
    return {
        "schema": SIGNED_BUNDLE_SCHEMA,
        "bundle_version": BUNDLE_VERSION,
        "manifest_sha256": manifest_sha256,
        "manifest": dict(manifest),
        "signature": {
            "algorithm": SIGNATURE_ALGORITHM,
            "key_id": selected_key_id,
            "encoding": "base64",
            "value": base64.b64encode(signature_bytes).decode("ascii"),
        },
    }


def validate_signed_manifest_bundle(bundle: Mapping[str, Any]) -> None:
    schema = require_text(bundle.get("schema"), field_name="bundle.schema")
    if schema != SIGNED_BUNDLE_SCHEMA:
        raise ValueError(f"bundle.schema must equal {SIGNED_BUNDLE_SCHEMA!r}.")

    version = require_u32(bundle.get("bundle_version"), field_name="bundle.bundle_version")
    if version != BUNDLE_VERSION:
        raise ValueError(f"bundle.bundle_version must equal {BUNDLE_VERSION}.")

    manifest = require_dict(bundle.get("manifest"), field_name="bundle.manifest")
    validate_manifest(manifest)

    declared_manifest_sha = normalize_sha256(bundle.get("manifest_sha256"), field_name="bundle.manifest_sha256")
    actual_manifest_sha = manifest_sha256_hex(manifest)
    if declared_manifest_sha != actual_manifest_sha:
        raise ValueError("bundle.manifest_sha256 does not match the canonical manifest digest.")

    signature = require_dict(bundle.get("signature"), field_name="bundle.signature")
    algorithm = require_text(signature.get("algorithm"), field_name="bundle.signature.algorithm").lower()
    if algorithm != SIGNATURE_ALGORITHM:
        raise ValueError(f"bundle.signature.algorithm must equal {SIGNATURE_ALGORITHM!r}.")
    require_text(signature.get("key_id"), field_name="bundle.signature.key_id")
    encoding = require_text(signature.get("encoding"), field_name="bundle.signature.encoding").lower()
    if encoding != "base64":
        raise ValueError("bundle.signature.encoding must equal 'base64'.")
    require_text(signature.get("value"), field_name="bundle.signature.value")


def parse_job_flags_to_wire(job_flags: str) -> int:
    key = require_text(job_flags, field_name="job_flags").strip().lower()
    try:
        return JOB_FLAG_NAME_TO_WIRE[key]
    except KeyError as err:
        allowed = ", ".join(sorted(JOB_FLAG_NAME_TO_WIRE))
        raise ValueError(f"job_flags must map to a known wire value ({allowed}).") from err


def decode_signature_bytes(bundle: Mapping[str, Any]) -> bytes:
    signature = require_dict(bundle.get("signature"), field_name="bundle.signature")
    return base64.b64decode(str(signature["value"]).encode("ascii"), validate=True)


def _format_c_byte_initializer(payload: bytes, *, values_per_line: int = 8) -> list[str]:
    lines: list[str] = []
    for offset in range(0, len(payload), values_per_line):
        chunk = payload[offset:offset + values_per_line]
        rendered = ", ".join(f"0x{value:02X}U" for value in chunk)
        if offset + len(chunk) < len(payload):
            rendered += ","
        lines.append(rendered)
    return lines


def extract_p256_public_key_uncompressed(
    public_key: str | Path,
    *,
    openssl_bin: str = "openssl",
) -> bytes:
    result = _run_openssl(
        [
            openssl_bin,
            "ec",
            "-pubin",
            "-in",
            str(resolve_path(public_key)),
            "-text",
            "-noout",
        ]
    )
    output = result.stdout.decode("utf-8", errors="replace")
    if "ASN1 OID: prime256v1" not in output:
        raise ValueError("public key must be an EC P-256 public key (prime256v1).")

    collecting = False
    octets: list[int] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line == "pub:":
            collecting = True
            continue
        if collecting and line.startswith("ASN1 OID:"):
            break
        if not collecting:
            continue
        octets.extend(int(token, 16) for token in re.findall(r"[0-9A-Fa-f]{2}", line))

    key_bytes = bytes(octets)
    if len(key_bytes) != P256_PUBLIC_KEY_UNCOMPRESSED_LEN or key_bytes[:1] != b"\x04":
        raise ValueError("public key must decode to a 65-byte uncompressed SEC1 point.")
    return key_bytes


def build_control_frame(*, msg_type: int, seq: int, job_id: int, payload: bytes) -> bytes:
    header_crc32 = compute_control_header_crc(
        magic=CTRL_MAGIC,
        version=CTRL_VERSION,
        msg_type=msg_type,
        seq=seq,
        job_id=job_id,
        payload_len=len(payload),
    )
    header = CTRL_HEADER_STRUCT.pack(
        CTRL_MAGIC,
        CTRL_VERSION,
        msg_type,
        seq,
        job_id,
        len(payload),
        header_crc32,
    )
    return header + payload


def chunk_bytes(payload: bytes, *, chunk_size: int) -> list[tuple[int, bytes]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")
    chunks: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(payload):
        chunk = payload[offset:offset + chunk_size]
        chunks.append((offset, chunk))
        offset += len(chunk)
    return chunks


def load_signed_manifest_bundle(path: str | Path) -> dict[str, Any]:
    bundle = load_json(path)
    validate_signed_manifest_bundle(bundle)
    return bundle


def signed_manifest_summary(
    bundle: Mapping[str, Any],
    *,
    bundle_path: str | Path | None = None,
    verified: bool,
    artifact_match: bool | None,
    verification_public_key: str | None = None,
) -> dict[str, Any]:
    manifest = require_dict(bundle.get("manifest"), field_name="bundle.manifest")
    signature = require_dict(bundle.get("signature"), field_name="bundle.signature")
    artifact = require_dict(manifest.get("artifact"), field_name="manifest.artifact")
    job = require_dict(manifest.get("job"), field_name="manifest.job")
    return {
        "admission_mode": "signed_manifest_v1",
        "bundle_schema": str(bundle["schema"]),
        "bundle_version": int(bundle["bundle_version"]),
        "manifest_schema": str(manifest["schema"]),
        "manifest_version": int(manifest["manifest_version"]),
        "manifest_sha256": str(bundle["manifest_sha256"]),
        "artifact_sha256": str(artifact["sha256"]),
        "artifact_path": str(artifact["path"]),
        "artifact_size_bytes": int(artifact["size_bytes"]),
        "variant": str(artifact["variant"]),
        "deadline_ms": int(job["deadline_ms"]),
        "expected_outputs": int(job["expected_outputs"]),
        "job_flags": str(job["job_flags"]),
        "signature_algorithm": str(signature["algorithm"]),
        "key_id": str(signature["key_id"]),
        "verified_locally": bool(verified),
        "artifact_match": artifact_match,
        "bundle_path": str(bundle_path) if bundle_path is not None else None,
        "verification_public_key": verification_public_key,
        "protocol_status": "draft_only",
    }


def verify_signed_manifest_bundle(
    bundle: Mapping[str, Any],
    *,
    public_key: str | Path,
    artifact_path: str | Path | None = None,
    openssl_bin: str = "openssl",
) -> dict[str, Any]:
    validate_signed_manifest_bundle(bundle)
    manifest = require_dict(bundle.get("manifest"), field_name="bundle.manifest")
    signature = require_dict(bundle.get("signature"), field_name="bundle.signature")
    signature_bytes = base64.b64decode(str(signature["value"]).encode("ascii"), validate=True)
    canonical = canonicalize_manifest(manifest)
    _verify_bytes_with_openssl(
        canonical,
        signature=signature_bytes,
        public_key=public_key,
        openssl_bin=openssl_bin,
    )
    artifact_match: bool | None = None
    if artifact_path is not None:
        artifact_sha = compute_file_sha256(artifact_path)
        artifact_match = artifact_sha == str(manifest["artifact"]["sha256"])
        if not artifact_match:
            raise ValueError("artifact_path sha256 does not match manifest.artifact.sha256.")
    return signed_manifest_summary(
        bundle,
        bundle_path=None,
        verified=True,
        artifact_match=artifact_match,
        verification_public_key=str(resolve_path(public_key)),
    )


def build_signed_manifest_bundle(
    *,
    artifact_path: str | Path,
    variant: str,
    key_id: str,
    publisher_channel: str,
    deadline_ms: int,
    expected_outputs: int,
    job_flags: str,
    private_key: str | Path,
    artifact_format: str = "tvm-module-shared-object",
    input_shape: tuple[int, int, int, int] = (1, 32, 32, 32),
    input_dtype: str = "float32",
    source_git_commit: str = "",
    note: str = "",
    created_at: str | None = None,
    openssl_bin: str = "openssl",
) -> dict[str, Any]:
    manifest = build_manifest(
        artifact_path=artifact_path,
        variant=variant,
        key_id=key_id,
        publisher_channel=publisher_channel,
        deadline_ms=deadline_ms,
        expected_outputs=expected_outputs,
        job_flags=job_flags,
        artifact_format=artifact_format,
        input_shape=input_shape,
        input_dtype=input_dtype,
        source_git_commit=source_git_commit,
        note=note,
        created_at=created_at,
    )
    return sign_manifest(
        manifest,
        private_key=private_key,
        key_id=key_id,
        openssl_bin=openssl_bin,
    )


def build_signed_admission_transport_plan(
    bundle: Mapping[str, Any],
    *,
    job_id: int,
    key_slot: int,
    chunk_size: int = SIGNED_ADMISSION_CHUNK_DATA_MAX,
    seq_start: int = 1,
) -> dict[str, Any]:
    validate_signed_manifest_bundle(bundle)
    manifest = require_dict(bundle.get("manifest"), field_name="bundle.manifest")
    artifact = require_dict(manifest.get("artifact"), field_name="manifest.artifact")
    job = require_dict(manifest.get("job"), field_name="manifest.job")
    if key_slot < 0 or key_slot > 0xFF:
        raise ValueError("key_slot must fit in u8.")
    if seq_start <= 0 or seq_start > 0xFFFFFFFF:
        raise ValueError("seq_start must fit in u32 and be > 0.")
    if chunk_size <= 0 or chunk_size > SIGNED_ADMISSION_CHUNK_DATA_MAX:
        raise ValueError(
            f"chunk_size must be > 0 and <= {SIGNED_ADMISSION_CHUNK_DATA_MAX} bytes."
        )

    canonical_manifest = canonicalize_manifest(manifest)
    manifest_sha256 = normalize_sha256(bundle.get("manifest_sha256"), field_name="bundle.manifest_sha256")
    signature_bytes = decode_signature_bytes(bundle)
    signature_crc32 = compute_crc32(signature_bytes)
    manifest_crc32 = compute_crc32(canonical_manifest)
    expected_sha256 = normalize_sha256(artifact.get("sha256"), field_name="manifest.artifact.sha256")
    deadline_ms = require_u32(job.get("deadline_ms"), field_name="manifest.job.deadline_ms")
    expected_outputs = require_u32(job.get("expected_outputs"), field_name="manifest.job.expected_outputs")
    flags_wire = parse_job_flags_to_wire(str(job.get("job_flags")))

    seq = seq_start
    frames: list[dict[str, Any]] = []

    begin_payload = struct.pack(
        "<BBH32sIII",
        SIGNED_ADMISSION_TYPE,
        key_slot,
        SIGNED_ADMISSION_SIGNATURE_ALGORITHM,
        bytes.fromhex(manifest_sha256),
        len(canonical_manifest),
        len(signature_bytes),
        chunk_size,
    )
    begin_frame = build_control_frame(
        msg_type=SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_BEGIN"],
        seq=seq,
        job_id=job_id,
        payload=begin_payload,
    )
    frames.append(
        {
            "phase": "SIGNED_ADMISSION_BEGIN",
            "seq": seq,
            "job_id": job_id,
            "msg_type": SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_BEGIN"],
            "payload_len": len(begin_payload),
            "payload_hex": begin_payload.hex(),
            "frame_hex": begin_frame.hex(),
            "payload": {
                "admission_type": SIGNED_ADMISSION_TYPE,
                "key_slot": key_slot,
                "signature_algorithm": SIGNED_ADMISSION_SIGNATURE_ALGORITHM,
                "manifest_sha256": manifest_sha256,
                "manifest_len": len(canonical_manifest),
                "signature_len": len(signature_bytes),
                "chunk_size": chunk_size,
            },
        }
    )
    seq += 1

    manifest_chunks: list[dict[str, Any]] = []
    for offset, chunk in chunk_bytes(canonical_manifest, chunk_size=chunk_size):
        chunk_crc32 = compute_crc32(chunk)
        chunk_payload = (
            bytes.fromhex(manifest_sha256)
            + struct.pack("<III", offset, len(chunk), chunk_crc32)
            + chunk
        )
        chunk_frame = build_control_frame(
            msg_type=SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_CHUNK"],
            seq=seq,
            job_id=job_id,
            payload=chunk_payload,
        )
        manifest_chunks.append(
            {
                "phase": "SIGNED_ADMISSION_CHUNK",
                "seq": seq,
                "job_id": job_id,
                "msg_type": SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_CHUNK"],
                "payload_len": len(chunk_payload),
                "payload_hex": chunk_payload.hex(),
                "frame_hex": chunk_frame.hex(),
                "payload": {
                    "manifest_sha256": manifest_sha256,
                    "offset": offset,
                    "chunk_len": len(chunk),
                    "chunk_crc32": chunk_crc32,
                    "chunk_data_hex": chunk.hex(),
                },
            }
        )
        seq += 1
    frames.extend(manifest_chunks)

    signature_payload = (
        bytes.fromhex(manifest_sha256)
        + struct.pack("<II", len(signature_bytes), signature_crc32)
        + signature_bytes
    )
    signature_frame = build_control_frame(
        msg_type=SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_SIGNATURE"],
        seq=seq,
        job_id=job_id,
        payload=signature_payload,
    )
    frames.append(
        {
            "phase": "SIGNED_ADMISSION_SIGNATURE",
            "seq": seq,
            "job_id": job_id,
            "msg_type": SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_SIGNATURE"],
            "payload_len": len(signature_payload),
            "payload_hex": signature_payload.hex(),
            "frame_hex": signature_frame.hex(),
            "payload": {
                "manifest_sha256": manifest_sha256,
                "signature_len": len(signature_bytes),
                "signature_crc32": signature_crc32,
                "signature_hex": signature_bytes.hex(),
            },
        }
    )
    seq += 1

    commit_payload = (
        bytes.fromhex(manifest_sha256)
        + struct.pack(
            "<IIII",
            manifest_crc32,
            signature_crc32,
            len(canonical_manifest),
            len(signature_bytes),
        )
    )
    commit_frame = build_control_frame(
        msg_type=SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_COMMIT"],
        seq=seq,
        job_id=job_id,
        payload=commit_payload,
    )
    frames.append(
        {
            "phase": "SIGNED_ADMISSION_COMMIT",
            "seq": seq,
            "job_id": job_id,
            "msg_type": SIGNED_ADMISSION_MSG_TYPES["SIGNED_ADMISSION_COMMIT"],
            "payload_len": len(commit_payload),
            "payload_hex": commit_payload.hex(),
            "frame_hex": commit_frame.hex(),
            "payload": {
                "manifest_sha256": manifest_sha256,
                "manifest_crc32": manifest_crc32,
                "signature_crc32": signature_crc32,
                "manifest_len": len(canonical_manifest),
                "signature_len": len(signature_bytes),
            },
        }
    )
    seq += 1

    job_req_payload = struct.pack(
        "<32sIII",
        bytes.fromhex(expected_sha256),
        deadline_ms,
        expected_outputs,
        flags_wire,
    )
    job_req_frame = build_control_frame(
        msg_type=0x0001,
        seq=seq,
        job_id=job_id,
        payload=job_req_payload,
    )
    frames.append(
        {
            "phase": "JOB_REQ",
            "seq": seq,
            "job_id": job_id,
            "msg_type": 0x0001,
            "payload_len": len(job_req_payload),
            "payload_hex": job_req_payload.hex(),
            "frame_hex": job_req_frame.hex(),
            "payload": {
                "expected_sha256": expected_sha256,
                "deadline_ms": deadline_ms,
                "expected_outputs": expected_outputs,
                "flags": flags_wire,
                "job_flags": str(job["job_flags"]),
            },
        }
    )

    return {
        "schema": SIGNED_ADMISSION_TRANSPORT_SCHEMA,
        "transport_version": 1,
        "job_id": job_id,
        "key_slot": key_slot,
        "chunk_size": chunk_size,
        "bundle_schema": str(bundle["schema"]),
        "manifest_sha256": manifest_sha256,
        "artifact_sha256": expected_sha256,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_algorithm_wire": SIGNED_ADMISSION_SIGNATURE_ALGORITHM,
        "admission_type": "signed_manifest_v1",
        "message_types": dict(SIGNED_ADMISSION_MSG_TYPES),
        "stage_codes": dict(SIGNED_ADMISSION_STAGE_CODES),
        "ack_status_codes": dict(SIGNED_ADMISSION_ACK_STATUS),
        "manifest_len": len(canonical_manifest),
        "signature_len": len(signature_bytes),
        "manifest_crc32": manifest_crc32,
        "signature_crc32": signature_crc32,
        "expected_job_req_payload_len": len(job_req_payload),
        "frames": frames,
    }


def build_firmware_contract_artifact(
    bundle: Mapping[str, Any],
    *,
    public_key: str | Path,
    key_slot: int,
    openssl_bin: str = "openssl",
) -> dict[str, Any]:
    validate_signed_manifest_bundle(bundle)
    manifest = require_dict(bundle.get("manifest"), field_name="bundle.manifest")
    artifact = require_dict(manifest.get("artifact"), field_name="manifest.artifact")
    job = require_dict(manifest.get("job"), field_name="manifest.job")
    input_contract = require_dict(manifest.get("input_contract"), field_name="manifest.input_contract")
    publisher = require_dict(manifest.get("publisher"), field_name="manifest.publisher")
    provenance = require_dict(manifest.get("provenance"), field_name="manifest.provenance")
    if key_slot < 0 or key_slot > 0xFF:
        raise ValueError("key_slot must fit in u8.")

    canonical_manifest = canonicalize_manifest(manifest)
    signature_bytes = decode_signature_bytes(bundle)
    public_key_bytes = extract_p256_public_key_uncompressed(public_key, openssl_bin=openssl_bin)
    job_flags_text = require_text(job.get("job_flags"), field_name="manifest.job.job_flags")
    job_flags_wire = parse_job_flags_to_wire(job_flags_text)
    manifest_sha256 = normalize_sha256(bundle.get("manifest_sha256"), field_name="bundle.manifest_sha256")
    input_shape = input_contract.get("shape")
    if not isinstance(input_shape, list) or len(input_shape) != 4:
        raise ValueError("manifest.input_contract.shape must be a 4-element list.")

    public_key_slot_entry = "\n".join(
        [
            "{",
            f"    {key_slot}U,",
            f"    \"{require_text(publisher.get('key_id'), field_name='manifest.publisher.key_id')}\",",
            f"    \"{require_text(publisher.get('channel'), field_name='manifest.publisher.channel')}\",",
            "    {",
            *[f"        {line}" for line in _format_c_byte_initializer(public_key_bytes)],
            "    },",
            "}",
        ]
    )
    field_plan = [
        {
            "json_path": "schema",
            "c_field": "schema_id",
            "c_type": "char[32]",
            "parser": "json_string_exact",
            "required": True,
            "max_len": 32,
            "expected": MANIFEST_SCHEMA,
        },
        {
            "json_path": "manifest_version",
            "c_field": "manifest_version",
            "c_type": "uint32_t",
            "parser": "json_u32_exact",
            "required": True,
            "expected": 1,
        },
        {
            "json_path": "artifact.sha256",
            "c_field": "artifact_sha256",
            "c_type": "uint8_t[32]",
            "parser": "json_sha256_hex",
            "required": True,
        },
        {
            "json_path": "artifact.size_bytes",
            "c_field": "artifact_size_bytes",
            "c_type": "uint32_t",
            "parser": "json_u32",
            "required": True,
            "allow_zero": True,
        },
        {
            "json_path": "artifact.path",
            "c_field": "artifact_path",
            "c_type": "char[160]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 160,
        },
        {
            "json_path": "artifact.format",
            "c_field": "artifact_format",
            "c_type": "char[48]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 48,
        },
        {
            "json_path": "artifact.variant",
            "c_field": "artifact_variant",
            "c_type": "char[32]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 32,
        },
        {
            "json_path": "job.deadline_ms",
            "c_field": "deadline_ms",
            "c_type": "uint32_t",
            "parser": "json_u32",
            "required": True,
        },
        {
            "json_path": "job.expected_outputs",
            "c_field": "expected_outputs",
            "c_type": "uint32_t",
            "parser": "json_u32",
            "required": True,
        },
        {
            "json_path": "job.job_flags",
            "c_field": "flags",
            "c_type": "uint32_t",
            "parser": "json_string_enum",
            "required": True,
            "enum_map": dict(JOB_FLAG_NAME_TO_WIRE),
        },
        {
            "json_path": "input_contract.shape",
            "c_field": "input_shape",
            "c_type": "uint32_t[4]",
            "parser": "json_u32_array4",
            "required": True,
        },
        {
            "json_path": "input_contract.dtype",
            "c_field": "input_dtype",
            "c_type": "char[16]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 16,
        },
        {
            "json_path": "publisher.key_id",
            "c_field": "publisher_key_id",
            "c_type": "char[32]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 32,
        },
        {
            "json_path": "publisher.channel",
            "c_field": "publisher_channel",
            "c_type": "char[32]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 32,
        },
        {
            "json_path": "provenance.created_at",
            "c_field": "provenance_created_at",
            "c_type": "char[40]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 40,
        },
        {
            "json_path": "provenance.builder",
            "c_field": "provenance_builder",
            "c_type": "char[64]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 64,
        },
        {
            "json_path": "provenance.source_repo",
            "c_field": "provenance_source_repo",
            "c_type": "char[64]",
            "parser": "json_string_copy",
            "required": True,
            "max_len": 64,
        },
        {
            "json_path": "provenance.source_git_commit",
            "c_field": "provenance_source_git_commit",
            "c_type": "char[64]",
            "parser": "json_string_optional",
            "required": False,
            "max_len": 64,
        },
        {
            "json_path": "provenance.note",
            "c_field": "provenance_note",
            "c_type": "char[128]",
            "parser": "json_string_optional",
            "required": False,
            "max_len": 128,
        },
    ]

    return {
        "schema": FIRMWARE_CONTRACT_SCHEMA,
        "contract_version": 1,
        "bundle_schema": str(bundle["schema"]),
        "manifest_schema": str(manifest["schema"]),
        "manifest_sha256": manifest_sha256,
        "manifest_len": len(canonical_manifest),
        "manifest_crc32": compute_crc32(canonical_manifest),
        "signature_len": len(signature_bytes),
        "signature_crc32": compute_crc32(signature_bytes),
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature_algorithm_wire": SIGNED_ADMISSION_SIGNATURE_ALGORITHM,
        "admission_type_wire": SIGNED_ADMISSION_TYPE,
        "message_types": dict(SIGNED_ADMISSION_MSG_TYPES),
        "stage_codes": dict(SIGNED_ADMISSION_STAGE_CODES),
        "ack_status_codes": dict(SIGNED_ADMISSION_ACK_STATUS),
        "public_key_slot": {
            "slot_id": key_slot,
            "key_id": str(publisher["key_id"]),
            "channel": str(publisher["channel"]),
            "curve": "prime256v1",
            "format": "uncompressed-sec1",
            "byte_len": len(public_key_bytes),
            "bytes_hex": public_key_bytes.hex(),
            "c_type": "ScPublicKeySlot",
            "c_initializer_lines": _format_c_byte_initializer(public_key_bytes),
            "c_initializer": public_key_slot_entry,
        },
        "manifest_contract": {
            "struct_name": "ScManifestContract",
            "schema": str(manifest["schema"]),
            "manifest_version": int(manifest["manifest_version"]),
            "artifact_sha256": str(artifact["sha256"]),
            "artifact_size_bytes": int(artifact["size_bytes"]),
            "artifact_path": str(artifact["path"]),
            "artifact_format": str(artifact["format"]),
            "artifact_variant": str(artifact["variant"]),
            "deadline_ms": int(job["deadline_ms"]),
            "expected_outputs": int(job["expected_outputs"]),
            "job_flags_text": job_flags_text,
            "job_flags_wire": job_flags_wire,
            "input_shape": [int(require_u32(dim, field_name=f"manifest.input_contract.shape[{index}]")) for index, dim in enumerate(input_shape)],
            "input_dtype": str(input_contract["dtype"]),
            "publisher_key_id": str(publisher["key_id"]),
            "publisher_channel": str(publisher["channel"]),
            "provenance_created_at": str(provenance["created_at"]),
            "provenance_builder": str(provenance["builder"]),
            "provenance_source_repo": str(provenance["source_repo"]),
            "provenance_source_git_commit": str(provenance.get("source_git_commit", "")),
            "provenance_note": str(provenance.get("note", "")),
            "field_plan": field_plan,
        },
        "parser_strategy": {
            "entrypoint": "sc_ctrl_parse_manifest_contract",
            "required_helpers": [
                "sc_ctrl_json_expect_string_field",
                "sc_ctrl_json_expect_u32_field",
                "sc_ctrl_json_find_object",
                "sc_ctrl_json_find_string_field",
                "sc_ctrl_json_find_optional_string_field",
                "sc_ctrl_json_find_u32_field",
                "sc_ctrl_json_find_u32_array4_field",
                "sc_ctrl_parse_manifest_artifact_contract",
                "sc_ctrl_parse_manifest_job_contract",
                "sc_ctrl_parse_manifest_input_contract",
                "sc_ctrl_parse_manifest_publisher_contract",
                "sc_ctrl_parse_manifest_provenance_contract",
                "sc_ctrl_parse_sha256_hex",
                "sc_ctrl_manifest_flag_from_string",
            ],
            "parse_call_markers": [
                "sc_ctrl_json_expect_string_field(manifest_bytes,",
                "sc_ctrl_json_expect_u32_field(manifest_bytes,",
                "sc_ctrl_parse_manifest_artifact_contract(manifest_bytes,",
                "sc_ctrl_parse_manifest_job_contract(manifest_bytes,",
                "sc_ctrl_parse_manifest_input_contract(manifest_bytes,",
                "sc_ctrl_parse_manifest_publisher_contract(manifest_bytes,",
                "sc_ctrl_parse_manifest_provenance_contract(manifest_bytes,",
            ],
            "strict_field_markers": [
                "out_contract->artifact_size_bytes",
                "out_contract->artifact_path",
                "out_contract->artifact_format",
                "out_contract->artifact_variant",
                "out_contract->input_shape",
                "out_contract->input_dtype",
                "out_contract->provenance_created_at",
                "out_contract->provenance_builder",
                "out_contract->provenance_source_repo",
            ],
            "optional_field_markers": [
                "sc_ctrl_json_find_optional_string_field(provenance_object.begin,",
                "out_contract->provenance_source_git_commit",
                "out_contract->provenance_note",
            ],
            "slot_binding_markers": [
                "strcmp(contract.publisher_key_id, slot->key_id)",
                "strcmp(contract.publisher_channel, slot->channel)",
            ],
            "assumptions": [
                "manifest bytes are the exact canonical UTF-8 bytes staged over SIGNED_ADMISSION_CHUNK",
                "parser is narrow and only accepts the committed openamp_artifact_manifest/v1 schema",
                "string fields reject escape sequences to keep the firmware parser small and deterministic",
                "artifact.path / artifact.format / artifact.variant / input_contract / provenance fields are still parsed even though JOB_REQ only mirrors a subset",
            ],
        },
        "crypto_boundary": {
            "backend": "standalone-sdk-mbedtls-boundary",
            "hash_algorithm": "sha256",
            "digest_len": 32,
            "public_key_format": "uncompressed-sec1",
            "signature_format": "asn1-der",
            "request_struct_name": "ScEcdsaP256VerifyRequest",
            "enable_macro": "SC_CTRL_USE_MBEDTLS",
            "include_guard_markers": [
                "#if defined(SC_CTRL_USE_MBEDTLS)",
                "#include <mbedtls/ecdsa.h>",
                "#include <mbedtls/ecp.h>",
                "#include <mbedtls/sha256.h>",
                "#endif",
            ],
            "required_symbols": [
                "mbedtls_sha256_ret",
                "mbedtls_ecdsa_init",
                "mbedtls_ecp_group_load",
                "mbedtls_ecp_point_read_binary",
                "mbedtls_ecp_check_pubkey",
                "mbedtls_ecdsa_read_signature",
                "mbedtls_ecdsa_free",
            ],
            "sha256_wrapper": {
                "name": "sc_ctrl_crypto_sha256",
                "prototype": (
                    "static int sc_ctrl_crypto_sha256(const uint8_t *input, "
                    "uint32_t input_len, uint8_t out_digest[32])"
                ),
                "validation_markers": [
                    "input == NULL",
                    "input_len == 0U",
                    "out_digest == NULL",
                ],
                "call_sequence": [
                    "mbedtls_sha256_ret(input, input_len, out_digest, 0)",
                ],
                "implementation_markers": [
                    "#if defined(SC_CTRL_USE_MBEDTLS)",
                    "sdk_status = mbedtls_sha256_ret(input, input_len, out_digest, 0);",
                    "return (sdk_status == 0);",
                    "#else",
                    "return 0;",
                    "#endif",
                ],
            },
            "verify_wrapper": {
                "name": "sc_ctrl_crypto_verify_ecdsa_p256_sha256_der",
                "prototype": (
                    "static int sc_ctrl_crypto_verify_ecdsa_p256_sha256_der("
                    "const ScEcdsaP256VerifyRequest *request)"
                ),
                "validation_markers": [
                    "request->manifest_bytes == NULL",
                    "request->manifest_len == 0U",
                    "request->signature_der == NULL",
                    "request->signature_len == 0U",
                    "request->signature_len > SC_SIGNED_SIGNATURE_MAX_LEN",
                    "request->public_key_uncompressed == NULL",
                    "request->public_key_len != SC_PUBLIC_KEY_UNCOMPRESSED_LEN",
                ],
                "context_markers": [
                    "mbedtls_ecdsa_context ecdsa",
                    "int sdk_status = -1",
                ],
                "cleanup_sequence": [
                    "mbedtls_ecdsa_free(&ecdsa)",
                ],
                "implementation_markers": [
                    "#if defined(SC_CTRL_USE_MBEDTLS)",
                    "mbedtls_ecdsa_context ecdsa;",
                    "mbedtls_ecdsa_init(&ecdsa);",
                    "sdk_status = mbedtls_ecp_group_load(&ecdsa.grp, MBEDTLS_ECP_DP_SECP256R1);",
                    "sdk_status = mbedtls_ecp_point_read_binary(&ecdsa.grp,",
                    "sdk_status = mbedtls_ecp_check_pubkey(&ecdsa.grp, &ecdsa.Q);",
                    "sdk_status = mbedtls_ecdsa_read_signature(&ecdsa,",
                    "mbedtls_ecdsa_free(&ecdsa);",
                    "return (sdk_status == 0);",
                    "#else",
                    "return 0;",
                    "#endif",
                ],
            },
            "sdk_headers": [
                "mbedtls/ecdsa.h",
                "mbedtls/ecp.h",
                "mbedtls/sha256.h",
            ],
            "mbedtls_call_sequence": [
                "mbedtls_ecdsa_init(&ecdsa)",
                "mbedtls_ecp_group_load(&ecdsa.grp, MBEDTLS_ECP_DP_SECP256R1)",
                "mbedtls_ecp_point_read_binary(&ecdsa.grp,",
                "mbedtls_ecp_check_pubkey(&ecdsa.grp, &ecdsa.Q)",
                "mbedtls_ecdsa_read_signature(&ecdsa,",
            ],
            "integration_checklist": [
                "define SC_CTRL_USE_MBEDTLS only after the openamp_for_linux example resolves the mbedTLS headers",
                "link the standalone-SDK archive set that resolves every symbol in required_symbols",
                "keep SC_CTRL_USE_MBEDTLS undefined until that link step is complete so signed admission remains deny-by-default",
            ],
        },
    }


def parse_shape(raw: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in str(raw).split(",")]
    if len(parts) != 4:
        raise ValueError("--input-shape must have exactly four comma-separated dimensions.")
    return tuple(require_u32(part, field_name=f"input_shape[{index}]") for index, part in enumerate(parts))  # type: ignore[return-value]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create, sign, and verify signed OpenAMP artifact manifests. "
            "The host keeps the private key; firmware stores only public keys."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build an unsigned artifact manifest JSON file.")
    build_parser.add_argument("--artifact", required=True, help="Artifact path used for sha256 and size metadata.")
    build_parser.add_argument("--output", required=True, help="Manifest JSON output path.")
    build_parser.add_argument("--variant", required=True, help="Variant label such as current or baseline.")
    build_parser.add_argument("--key-id", required=True, help="Publisher key identifier stored in the manifest.")
    build_parser.add_argument("--publisher-channel", required=True, help="Publishing channel or environment label.")
    build_parser.add_argument("--deadline-ms", type=int, default=300000)
    build_parser.add_argument("--expected-outputs", type=int, default=300)
    build_parser.add_argument("--job-flags", default="reconstruction")
    build_parser.add_argument("--artifact-format", default="tvm-module-shared-object")
    build_parser.add_argument("--input-shape", default="1,32,32,32")
    build_parser.add_argument("--input-dtype", default="float32")
    build_parser.add_argument("--source-git-commit", default="")
    build_parser.add_argument("--note", default="")
    build_parser.add_argument("--created-at", default="")

    bundle_parser = subparsers.add_parser(
        "bundle",
        help="Build and sign a manifest bundle from an artifact path in one command.",
    )
    bundle_parser.add_argument("--artifact", required=True, help="Artifact path used for sha256 and size metadata.")
    bundle_parser.add_argument("--private-key", required=True, help="PEM private key used for signing.")
    bundle_parser.add_argument("--output", required=True, help="Signed bundle JSON output path.")
    bundle_parser.add_argument("--variant", required=True, help="Variant label such as current or baseline.")
    bundle_parser.add_argument("--key-id", required=True, help="Publisher key identifier stored in the manifest.")
    bundle_parser.add_argument("--publisher-channel", required=True, help="Publishing channel or environment label.")
    bundle_parser.add_argument("--deadline-ms", type=int, default=300000)
    bundle_parser.add_argument("--expected-outputs", type=int, default=300)
    bundle_parser.add_argument("--job-flags", default="reconstruction")
    bundle_parser.add_argument("--artifact-format", default="tvm-module-shared-object")
    bundle_parser.add_argument("--input-shape", default="1,32,32,32")
    bundle_parser.add_argument("--input-dtype", default="float32")
    bundle_parser.add_argument("--source-git-commit", default="")
    bundle_parser.add_argument("--note", default="")
    bundle_parser.add_argument("--created-at", default="")
    bundle_parser.add_argument("--openssl-bin", default="openssl")

    sign_parser = subparsers.add_parser("sign", help="Sign an existing manifest JSON file and emit a bundle.")
    sign_parser.add_argument("--manifest", required=True, help="Input unsigned manifest JSON.")
    sign_parser.add_argument("--private-key", required=True, help="PEM private key used for signing.")
    sign_parser.add_argument("--output", required=True, help="Signed bundle JSON output path.")
    sign_parser.add_argument("--key-id", default="", help="Optional explicit key_id. Defaults to manifest.publisher.key_id.")
    sign_parser.add_argument("--openssl-bin", default="openssl")

    verify_parser = subparsers.add_parser("verify", help="Verify a signed bundle with a public key.")
    verify_parser.add_argument("--signed-manifest", required=True, help="Signed bundle JSON path.")
    verify_parser.add_argument("--public-key", required=True, help="PEM public key used for verification.")
    verify_parser.add_argument("--artifact", default="", help="Optional artifact path to match against the manifest sha256.")
    verify_parser.add_argument("--openssl-bin", default="openssl")

    transport_parser = subparsers.add_parser(
        "transport-plan",
        help="Emit the draft signed-admission sideband transport plan that precedes the existing JOB_REQ.",
    )
    transport_parser.add_argument("--signed-manifest", required=True, help="Signed bundle JSON path.")
    transport_parser.add_argument("--job-id", required=True, type=int, help="Control-plane job identifier.")
    transport_parser.add_argument("--key-slot", required=True, type=int, help="Firmware public-key slot index.")
    transport_parser.add_argument("--output", required=True, help="JSON output path for the transport plan.")
    transport_parser.add_argument("--chunk-size", type=int, default=SIGNED_ADMISSION_CHUNK_DATA_MAX)
    transport_parser.add_argument("--seq-start", type=int, default=1)

    firmware_parser = subparsers.add_parser(
        "firmware-contract",
        help="Emit the exact firmware-facing manifest contract, public key slot, and crypto boundary fixture.",
    )
    firmware_parser.add_argument("--signed-manifest", required=True, help="Signed bundle JSON path.")
    firmware_parser.add_argument("--public-key", required=True, help="PEM public key used for firmware slot generation.")
    firmware_parser.add_argument("--key-slot", required=True, type=int, help="Firmware public-key slot index.")
    firmware_parser.add_argument("--output", required=True, help="JSON output path for the firmware contract artifact.")
    firmware_parser.add_argument("--openssl-bin", default="openssl")

    return parser.parse_args()


def command_build(args: argparse.Namespace) -> dict[str, Any]:
    manifest = build_manifest(
        artifact_path=args.artifact,
        variant=args.variant,
        key_id=args.key_id,
        publisher_channel=args.publisher_channel,
        deadline_ms=args.deadline_ms,
        expected_outputs=args.expected_outputs,
        job_flags=args.job_flags,
        artifact_format=args.artifact_format,
        input_shape=parse_shape(args.input_shape),
        input_dtype=args.input_dtype,
        source_git_commit=args.source_git_commit,
        note=args.note,
        created_at=args.created_at or None,
    )
    output_path = resolve_path(args.output)
    write_json(output_path, manifest)
    return {
        "command": "build",
        "output": str(output_path),
        "manifest_sha256": manifest_sha256_hex(manifest),
        "artifact_sha256": manifest["artifact"]["sha256"],
    }


def command_bundle(args: argparse.Namespace) -> dict[str, Any]:
    bundle = build_signed_manifest_bundle(
        artifact_path=args.artifact,
        variant=args.variant,
        key_id=args.key_id,
        publisher_channel=args.publisher_channel,
        deadline_ms=args.deadline_ms,
        expected_outputs=args.expected_outputs,
        job_flags=args.job_flags,
        private_key=args.private_key,
        artifact_format=args.artifact_format,
        input_shape=parse_shape(args.input_shape),
        input_dtype=args.input_dtype,
        source_git_commit=args.source_git_commit,
        note=args.note,
        created_at=args.created_at or None,
        openssl_bin=args.openssl_bin,
    )
    output_path = resolve_path(args.output)
    write_json(output_path, bundle)
    return {
        "command": "bundle",
        "output": str(output_path),
        "manifest_sha256": bundle["manifest_sha256"],
        "artifact_sha256": bundle["manifest"]["artifact"]["sha256"],
        "key_id": bundle["signature"]["key_id"],
        "signature_algorithm": bundle["signature"]["algorithm"],
    }


def command_sign(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_json(args.manifest)
    bundle = sign_manifest(
        manifest,
        private_key=args.private_key,
        key_id=args.key_id or None,
        openssl_bin=args.openssl_bin,
    )
    output_path = resolve_path(args.output)
    write_json(output_path, bundle)
    return {
        "command": "sign",
        "output": str(output_path),
        "manifest_sha256": bundle["manifest_sha256"],
        "key_id": bundle["signature"]["key_id"],
        "signature_algorithm": bundle["signature"]["algorithm"],
    }


def command_verify(args: argparse.Namespace) -> dict[str, Any]:
    bundle_path = resolve_path(args.signed_manifest)
    bundle = load_signed_manifest_bundle(bundle_path)
    summary = verify_signed_manifest_bundle(
        bundle,
        public_key=args.public_key,
        artifact_path=args.artifact or None,
        openssl_bin=args.openssl_bin,
    )
    summary["command"] = "verify"
    summary["bundle_path"] = str(bundle_path)
    return summary


def command_transport_plan(args: argparse.Namespace) -> dict[str, Any]:
    bundle_path = resolve_path(args.signed_manifest)
    bundle = load_signed_manifest_bundle(bundle_path)
    plan = build_signed_admission_transport_plan(
        bundle,
        job_id=require_u32(args.job_id, field_name="--job-id"),
        key_slot=require_u32(args.key_slot, field_name="--key-slot", allow_zero=True),
        chunk_size=require_u32(args.chunk_size, field_name="--chunk-size"),
        seq_start=require_u32(args.seq_start, field_name="--seq-start"),
    )
    output_path = resolve_path(args.output)
    write_json(output_path, plan)
    return {
        "command": "transport-plan",
        "output": str(output_path),
        "schema": plan["schema"],
        "frame_count": len(plan["frames"]),
        "manifest_sha256": plan["manifest_sha256"],
        "job_id": plan["job_id"],
    }


def command_firmware_contract(args: argparse.Namespace) -> dict[str, Any]:
    bundle_path = resolve_path(args.signed_manifest)
    bundle = load_signed_manifest_bundle(bundle_path)
    artifact = build_firmware_contract_artifact(
        bundle,
        public_key=args.public_key,
        key_slot=require_u32(args.key_slot, field_name="--key-slot", allow_zero=True),
        openssl_bin=args.openssl_bin,
    )
    output_path = resolve_path(args.output)
    write_json(output_path, artifact)
    return {
        "command": "firmware-contract",
        "output": str(output_path),
        "schema": artifact["schema"],
        "manifest_sha256": artifact["manifest_sha256"],
        "key_slot": artifact["public_key_slot"]["slot_id"],
    }


def main() -> int:
    args = parse_args()
    if args.command == "build":
        result = command_build(args)
    elif args.command == "bundle":
        result = command_bundle(args)
    elif args.command == "sign":
        result = command_sign(args)
    elif args.command == "verify":
        result = command_verify(args)
    elif args.command == "transport-plan":
        result = command_transport_plan(args)
    elif args.command == "firmware-contract":
        result = command_firmware_contract(args)
    else:
        raise SystemExit(f"unsupported command: {args.command}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
