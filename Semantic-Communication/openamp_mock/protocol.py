from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
import json
from typing import Any, Mapping
import zlib

MAGIC = 0x53434F4D
VERSION = 1
# The design doc targets <256B binary control frames. The mock uses JSON-like
# dict payloads for readability, so it allows a slightly larger envelope.
MAX_PAYLOAD_LEN = 512

FORMAL_TRUSTED_CURRENT_SHA = (
    "6f236b07f9b0bf981b6762ddb72449e23332d2d92c76b38acdcadc1d9b536dc1"
)
FORMAL_BASELINE_PAYLOAD_MS = 1846.9
FORMAL_CURRENT_PAYLOAD_MS = 130.219
FORMAL_BASELINE_E2E_MS = 1850.0
FORMAL_CURRENT_E2E_MS = 230.339


class ServiceMode(IntEnum):
    """Inner mode state machine: service level inside RUNNING state.

    Governs how the data plane handles incoming payloads:
    - FULL_FRAME:  complete latent → TVM fixed-shape reconstruction
    - ROI_ONLY:    ROI-cropped latent → MNN dynamic-shape reconstruction
    - ALERT_ONLY:  alert metadata only → no inference, direct display
    """
    FULL_FRAME = 0
    ROI_ONLY = 1
    ALERT_ONLY = 2


class MessageType(IntEnum):
    JOB_REQ = 0x01
    JOB_ACK = 0x02
    HEARTBEAT = 0x03
    HEARTBEAT_ACK = 0x04
    JOB_DONE = 0x05
    FAULT_REPORT = 0x06
    SAFE_STOP = 0x07
    STATUS_REQ = 0x08
    STATUS_RESP = 0x09
    RESET_REQ = 0x0A
    RESET_ACK = 0x0B
    SIGNED_ADMISSION_BEGIN = 0x0C
    SIGNED_ADMISSION_CHUNK = 0x0D
    SIGNED_ADMISSION_SIGNATURE = 0x0E
    SIGNED_ADMISSION_COMMIT = 0x0F
    SIGNED_ADMISSION_ACK = 0x10
    ENCRYPTED_CTRL = 0x20
    # --- task-level degradation messages ---
    LINK_HEALTH = 0x60          # linux → guard: link quality report
    MODE_DIRECTIVE = 0x61       # guard → linux: allowed service mode
    MODE_ACK = 0x62             # linux → guard: mode switch confirmed


class Decision(IntEnum):
    DENY = 0
    ALLOW = 1


class FaultCode(IntEnum):
    NONE = 0
    ARTIFACT_SHA_MISMATCH = 1
    INPUT_CONTRACT_INVALID = 2
    HEARTBEAT_TIMEOUT = 3
    CONTROL_CRC_ERROR = 4
    OUTPUT_INCOMPLETE = 5
    DEADLINE_EXCEEDED = 6
    UNSUPPORTED_VERSION = 7
    DUPLICATE_JOB_ID = 8
    ILLEGAL_PARAM_RANGE = 9
    MANUAL_SAFE_STOP = 10
    MANIFEST_NOT_STAGED = 11
    MANIFEST_DIGEST_MISMATCH = 12
    MANIFEST_PARSE_ERROR = 13
    SIGNATURE_INVALID = 14
    KEY_SLOT_UNKNOWN = 15
    MANIFEST_CONTRACT_MISMATCH = 16
    # --- task-level degradation fault codes ---
    LINK_DEGRADED = 17          # informational: link quality below threshold
    LINK_LOST = 18              # critical: RX lost lock, triggers SAFE_STOP


class OrchestratorState(str, Enum):
    IDLE = "IDLE"
    PRECHECK = "PRECHECK"
    REQUESTING = "REQUESTING"
    ALLOWED = "ALLOWED"
    RUNNING = "RUNNING"
    FINALIZING = "FINALIZING"
    DONE = "DONE"
    DENIED = "DENIED"
    SAFE_STOPPED = "SAFE_STOPPED"
    FAILED = "FAILED"


class GuardState(str, Enum):
    BOOT = "BOOT"
    READY = "READY"
    JOB_ACTIVE = "JOB_ACTIVE"
    WAIT_DONE = "WAIT_DONE"
    DENY_PENDING = "DENY_PENDING"
    FAULT_LATCHED = "FAULT_LATCHED"


@dataclass(frozen=True)
class JobSpec:
    job_id: int
    expected_sha256: str
    input_shape: tuple[int, int, int, int] = (1, 32, 32, 32)
    input_dtype: int = 1
    snr_db_x100: int = 1000
    payload_crc32: int = 0
    deadline_ms: int = 500
    expected_outputs: int = 1
    flags: str = "payload"
    result_crc32: int = 0
    artifact_sha_actual: str | None = None

    @property
    def artifact_sha(self) -> str:
        return self.artifact_sha_actual or self.expected_sha256


@dataclass(frozen=True)
class MessageHeader:
    magic: int
    version: int
    msg_type: int
    seq: int
    job_id: int
    payload_len: int
    header_crc32: int


@dataclass(frozen=True)
class ControlMessage:
    header: MessageHeader
    payload: dict[str, Any]

    @property
    def msg_type(self) -> MessageType:
        return MessageType(self.header.msg_type)


def _normalize_payload(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_size(payload: Mapping[str, Any]) -> int:
    return len(_normalize_payload(payload))


def compute_header_crc(
    *,
    magic: int,
    version: int,
    msg_type: int,
    seq: int,
    job_id: int,
    payload_len: int,
) -> int:
    raw = f"{magic}:{version}:{msg_type}:{seq}:{job_id}:{payload_len}".encode("utf-8")
    return zlib.crc32(raw) & 0xFFFFFFFF


def build_message(
    *,
    msg_type: MessageType,
    seq: int,
    job_id: int,
    payload: Mapping[str, Any],
    version: int = VERSION,
    force_bad_crc: bool = False,
) -> ControlMessage:
    body = dict(payload)
    payload_len = payload_size(body)
    header_crc32 = compute_header_crc(
        magic=MAGIC,
        version=version,
        msg_type=int(msg_type),
        seq=seq,
        job_id=job_id,
        payload_len=payload_len,
    )
    if force_bad_crc:
        header_crc32 = (header_crc32 + 1) & 0xFFFFFFFF
    header = MessageHeader(
        magic=MAGIC,
        version=version,
        msg_type=int(msg_type),
        seq=seq,
        job_id=job_id,
        payload_len=payload_len,
        header_crc32=header_crc32,
    )
    return ControlMessage(header=header, payload=body)


def validate_header(header: MessageHeader) -> bool:
    if header.magic != MAGIC:
        return False
    if header.payload_len > MAX_PAYLOAD_LEN:
        return False
    expected = compute_header_crc(
        magic=header.magic,
        version=header.version,
        msg_type=header.msg_type,
        seq=header.seq,
        job_id=header.job_id,
        payload_len=header.payload_len,
    )
    return expected == header.header_crc32


def msg_name(msg_type: int | MessageType) -> str:
    return MessageType(int(msg_type)).name


def fault_tag(code: int | FaultCode) -> str:
    value = int(code)
    if value == 0:
        return "F000"
    return f"F{value:03d}"


def fault_name(code: int | FaultCode) -> str:
    enum_value = FaultCode(int(code))
    if enum_value is FaultCode.NONE:
        return "NONE"
    return enum_value.name
