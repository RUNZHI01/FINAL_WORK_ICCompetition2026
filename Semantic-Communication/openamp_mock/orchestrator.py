from __future__ import annotations

from typing import Any

from .protocol import (
    Decision,
    FaultCode,
    JobSpec,
    MessageType,
    OrchestratorState,
    ServiceMode,
    build_message,
    fault_name,
    fault_tag,
)
from .transport import MockTransport


class Orchestrator:
    def __init__(self) -> None:
        self.state = OrchestratorState.IDLE
        self.state_log: list[dict[str, Any]] = []
        self.fault_log: list[dict[str, Any]] = []
        self.ctrl_events: list[dict[str, Any]] = []
        self.current_job: JobSpec | None = None
        self.last_ack: dict[str, Any] | None = None
        self.last_status: dict[str, Any] | None = None
        self.safe_stop_payload: dict[str, Any] | None = None
        self._tx_seq = 0

        # --- inner mode state machine tracking ---
        self.current_service_mode = ServiceMode.FULL_FRAME
        self.mode_history: list[dict[str, Any]] = []

        self._transition(OrchestratorState.IDLE, "orchestrator initialized", 0)

    def submit_job(
        self,
        job: JobSpec,
        now_ms: int,
        transport: MockTransport,
        *,
        force_bad_crc: bool = False,
        force_version: int | None = None,
    ) -> None:
        self.current_job = job
        self._transition(OrchestratorState.PRECHECK, "local manifest precheck complete", now_ms)
        self._transition(OrchestratorState.REQUESTING, "JOB_REQ dispatched", now_ms)
        payload = {
            "expected_sha256": job.expected_sha256,
            "input_shape_n": job.input_shape[0],
            "input_shape_c": job.input_shape[1],
            "input_shape_h": job.input_shape[2],
            "input_shape_w": job.input_shape[3],
            "input_dtype": job.input_dtype,
            "snr_db_x100": job.snr_db_x100,
            "payload_crc32": job.payload_crc32,
            "deadline_ms": job.deadline_ms,
            "expected_outputs": job.expected_outputs,
            "flags": job.flags,
        }
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.JOB_REQ,
            job_id=job.job_id,
            payload=payload,
            force_bad_crc=force_bad_crc,
            version=force_version,
        )

    def send_heartbeat(
        self,
        *,
        now_ms: int,
        transport: MockTransport,
        elapsed_ms: int,
        completed_outputs: int,
        progress_x100: int,
        runtime_state: str = "RUNNING",
    ) -> None:
        if self.current_job is None:
            raise RuntimeError("no active job")
        if self.state is OrchestratorState.ALLOWED:
            self._transition(OrchestratorState.RUNNING, "first heartbeat after allow", now_ms)
        payload = {
            "runtime_state": runtime_state,
            "elapsed_ms": elapsed_ms,
            "completed_outputs": completed_outputs,
            "progress_x100": progress_x100,
        }
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.HEARTBEAT,
            job_id=self.current_job.job_id,
            payload=payload,
        )

    def finish_job(
        self,
        *,
        now_ms: int,
        transport: MockTransport,
        success: bool,
        output_count: int,
    ) -> None:
        if self.current_job is None:
            raise RuntimeError("no active job")
        if self.state is OrchestratorState.RUNNING:
            self._transition(OrchestratorState.FINALIZING, "JOB_DONE dispatched", now_ms)
        payload = {
            "result_code": 0 if success else 1,
            "output_count": output_count,
            "result_crc32": self.current_job.result_crc32,
            "reserved": 0,
        }
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.JOB_DONE,
            job_id=self.current_job.job_id,
            payload=payload,
        )
        if success and self.state is OrchestratorState.FINALIZING:
            self._transition(OrchestratorState.DONE, "job finished successfully", now_ms)
        elif not success and self.state not in (OrchestratorState.SAFE_STOPPED, OrchestratorState.DENIED):
            self._transition(OrchestratorState.FAILED, "job finished with failure", now_ms)

    def request_status(self, now_ms: int, transport: MockTransport) -> None:
        job_id = self.current_job.job_id if self.current_job is not None else 0
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.STATUS_REQ,
            job_id=job_id,
            payload={},
        )

    def send_reset(self, now_ms: int, transport: MockTransport) -> None:
        job_id = self.current_job.job_id if self.current_job is not None else 0
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.RESET_REQ,
            job_id=job_id,
            payload={},
        )

    def handle(self, message, now_ms: int) -> None:
        msg_type = MessageType(message.header.msg_type)
        self.ctrl_events.append(
            {
                "at_ms": now_ms,
                "msg_type": msg_type.name,
                "job_id": message.header.job_id,
                "payload": dict(message.payload),
            }
        )
        if msg_type is MessageType.JOB_ACK:
            self.last_ack = dict(message.payload)
            if int(message.payload["decision"]) == int(Decision.ALLOW):
                self._transition(OrchestratorState.ALLOWED, "received JOB_ACK ALLOW", now_ms)
                return
            fault_code = FaultCode(int(message.payload["fault_code"]))
            self._record_fault(fault_code, "received JOB_ACK DENY", now_ms)
            self._transition(OrchestratorState.DENIED, "received JOB_ACK DENY", now_ms)
            return
        if msg_type is MessageType.SAFE_STOP:
            fault_code = FaultCode(int(message.payload["fault_code"]))
            self.safe_stop_payload = dict(message.payload)
            self._record_fault(fault_code, "received SAFE_STOP", now_ms)
            self._transition(OrchestratorState.SAFE_STOPPED, "received SAFE_STOP", now_ms)
            return
        if msg_type is MessageType.FAULT_REPORT:
            fault_code = FaultCode(int(message.payload["fault_code"]))
            self._record_fault(fault_code, "received FAULT_REPORT", now_ms)
            return
        if msg_type is MessageType.STATUS_RESP:
            self.last_status = dict(message.payload)
            return
        if msg_type is MessageType.MODE_DIRECTIVE:
            self._handle_mode_directive(message, now_ms)
            return
        if msg_type is MessageType.RESET_ACK:
            self.last_status = dict(message.payload)
            if self.state in (
                OrchestratorState.DENIED,
                OrchestratorState.SAFE_STOPPED,
                OrchestratorState.FAILED,
                OrchestratorState.DONE,
            ):
                self._transition(OrchestratorState.IDLE, "guard reset acknowledged", now_ms)

    def _send(
        self,
        *,
        transport: MockTransport,
        now_ms: int,
        msg_type: MessageType,
        job_id: int,
        payload: dict[str, Any],
        force_bad_crc: bool = False,
        version: int | None = None,
    ) -> None:
        self._tx_seq += 1
        message = build_message(
            msg_type=msg_type,
            seq=self._tx_seq,
            job_id=job_id,
            payload=payload,
            force_bad_crc=force_bad_crc,
            version=version if version is not None else 1,
        )
        transport.send_from_linux(message, now_ms)

    def _transition(self, new_state: OrchestratorState, reason: str, now_ms: int) -> None:
        old_state = self.state
        if old_state is new_state and self.state_log:
            return
        self.state = new_state
        self.state_log.append(
            {
                "at_ms": now_ms,
                "component": "orchestrator",
                "from_state": old_state.value if hasattr(old_state, "value") else str(old_state),
                "to_state": new_state.value,
                "reason": reason,
            }
        )

    def _record_fault(self, fault_code: FaultCode, reason: str, now_ms: int) -> None:
        self.fault_log.append(
            {
                "at_ms": now_ms,
                "fault_tag": fault_tag(fault_code),
                "fault_name": fault_name(fault_code),
                "reason": reason,
                "orchestrator_state": self.state.value,
            }
        )

    # ------------------------------------------------------------------
    # Inner mode state machine: receive MODE_DIRECTIVE from guard
    # ------------------------------------------------------------------

    def _handle_mode_directive(
        self, message, now_ms: int,
    ) -> None:
        """Process a MODE_DIRECTIVE from the guard."""
        new_mode = ServiceMode(int(message.payload["allowed_mode"]))
        old_mode = self.current_service_mode
        self.current_service_mode = new_mode
        self.mode_history.append({
            "at_ms": now_ms,
            "from_mode": old_mode.name,
            "to_mode": new_mode.name,
            "reason": message.payload.get("reason", ""),
            "job_id": message.header.job_id,
        })

    @property
    def payload_strategy(self) -> str:
        """Return data-plane payload strategy based on current service mode.

        - ``"full_latent"``: complete latent → TVM fixed-shape path
        - ``"roi_latent"``:  ROI-cropped latent → MNN dynamic-shape path
        - ``"alert_metadata"``: metadata only → no inference
        """
        if self.current_service_mode == ServiceMode.FULL_FRAME:
            return "full_latent"
        if self.current_service_mode == ServiceMode.ROI_ONLY:
            return "roi_latent"
        return "alert_metadata"
