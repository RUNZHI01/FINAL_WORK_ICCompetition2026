from __future__ import annotations

from typing import Any

from .link_health import LinkHealthReport
from .protocol import (
    Decision,
    FaultCode,
    GuardState,
    MessageType,
    ServiceMode,
    VERSION,
    build_message,
    fault_name,
    fault_tag,
    validate_header,
)
from .transport import MockTransport


class SafetyGuard:
    def __init__(self, trusted_sha256: str, heartbeat_timeout_ms: int = 250) -> None:
        self.trusted_sha256 = trusted_sha256
        self.heartbeat_timeout_ms = heartbeat_timeout_ms
        self.state = GuardState.BOOT
        self.state_log: list[dict[str, Any]] = []
        self.fault_log: list[dict[str, Any]] = []
        self.last_fault_code = FaultCode.NONE
        self.total_fault_count = 0
        self.sticky_fault = False
        self.active_job_id = 0
        self.expected_outputs = 0
        self.last_heartbeat_ms: int | None = None
        self.deadline_at_ms: int | None = None
        self.seen_job_ids: set[int] = set()
        self._tx_seq = 0

        # --- inner mode state machine (task-level degradation) ---
        self.allowed_mode = ServiceMode.FULL_FRAME
        self.current_mode = ServiceMode.FULL_FRAME
        self.mode_log: list[dict[str, Any]] = []
        self._degrade_window_count = 0
        self._upgrade_window_count = 0
        # hysteresis: 3 consecutive degraded windows to step down,
        #             5 consecutive good windows to step back up
        self.DEGRADE_THRESHOLD = 3
        self.UPGRADE_THRESHOLD = 5
        self.BURST_LOSS_EMERGENCY = 10  # bypass hysteresis on burst loss
        # mode decision thresholds
        self.SNR_ROI_THRESHOLD = 500       # SNR < 5 dB → ROI
        self.PER_ROI_THRESHOLD = 50        # PER > 5%   → ROI
        self.PER_ALERT_THRESHOLD = 200     # PER > 20%  → ALERT

        self._transition(GuardState.READY, "boot completed", 0)

    def handle(self, message, now_ms: int, transport: MockTransport) -> None:
        if not validate_header(message.header):
            self._handle_crc_fault(message, now_ms, transport)
            return
        if message.header.version != VERSION:
            self._deny(FaultCode.UNSUPPORTED_VERSION, message.header.job_id, "unsupported protocol version", now_ms, transport)
            return
        msg_type = MessageType(message.header.msg_type)
        if msg_type is MessageType.JOB_REQ:
            self._handle_job_req(message, now_ms, transport)
            return
        if msg_type is MessageType.HEARTBEAT:
            self._handle_heartbeat(message, now_ms)
            return
        if msg_type is MessageType.JOB_DONE:
            self._handle_job_done(message, now_ms, transport)
            return
        if msg_type is MessageType.STATUS_REQ:
            self._send_status(message.header.job_id, now_ms, transport)
            return
        if msg_type is MessageType.RESET_REQ:
            self._handle_reset(message.header.job_id, now_ms, transport)
            return
        if msg_type is MessageType.LINK_HEALTH:
            self._handle_link_health_msg(message, now_ms, transport)
            return
        if msg_type is MessageType.MODE_ACK:
            return  # acknowledged; no action needed on guard side

    def check_timeouts(self, now_ms: int, transport: MockTransport) -> None:
        if self.state is not GuardState.JOB_ACTIVE:
            return
        if self.last_heartbeat_ms is not None and now_ms - self.last_heartbeat_ms > self.heartbeat_timeout_ms:
            self._trigger_safe_stop(
                fault_code=FaultCode.HEARTBEAT_TIMEOUT,
                reason="heartbeat watchdog expired",
                now_ms=now_ms,
                transport=transport,
            )
            return
        if self.deadline_at_ms is not None and now_ms > self.deadline_at_ms:
            self._trigger_safe_stop(
                fault_code=FaultCode.DEADLINE_EXCEEDED,
                reason="deadline exceeded",
                now_ms=now_ms,
                transport=transport,
            )

    def _handle_job_req(self, message, now_ms: int, transport: MockTransport) -> None:
        if self.state is GuardState.FAULT_LATCHED:
            self._deny(FaultCode.MANUAL_SAFE_STOP, message.header.job_id, "guard fault latched", now_ms, transport)
            return
        if message.header.job_id in self.seen_job_ids or message.header.job_id == self.active_job_id:
            self._deny(FaultCode.DUPLICATE_JOB_ID, message.header.job_id, "duplicate job id", now_ms, transport)
            return
        expected_sha = str(message.payload.get("expected_sha256", ""))
        if expected_sha != self.trusted_sha256:
            self._deny(FaultCode.ARTIFACT_SHA_MISMATCH, message.header.job_id, "artifact sha mismatch", now_ms, transport)
            return
        input_fault = self._validate_input_contract(message.payload)
        if input_fault is not None:
            self._deny(input_fault, message.header.job_id, "input contract invalid", now_ms, transport)
            return
        self.seen_job_ids.add(message.header.job_id)
        self.active_job_id = message.header.job_id
        self.expected_outputs = int(message.payload["expected_outputs"])
        self.last_heartbeat_ms = now_ms
        self.deadline_at_ms = now_ms + int(message.payload["deadline_ms"])
        self._transition(GuardState.JOB_ACTIVE, "job request accepted", now_ms)
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.JOB_ACK,
            job_id=message.header.job_id,
            payload={
                "decision": int(Decision.ALLOW),
                "fault_code": int(FaultCode.NONE),
                "guard_state": self.state.value,
            },
        )

    def _validate_input_contract(self, payload: dict[str, Any]) -> FaultCode | None:
        if int(payload.get("input_shape_n", 0)) != 1:
            return FaultCode.INPUT_CONTRACT_INVALID
        if int(payload.get("input_dtype", 0)) != 1:
            return FaultCode.INPUT_CONTRACT_INVALID
        for key in ("input_shape_c", "input_shape_h", "input_shape_w"):
            if int(payload.get(key, 0)) <= 0:
                return FaultCode.INPUT_CONTRACT_INVALID
        snr_db_x100 = int(payload.get("snr_db_x100", -1))
        expected_outputs = int(payload.get("expected_outputs", 0))
        if snr_db_x100 < 0 or snr_db_x100 > 3000:
            return FaultCode.ILLEGAL_PARAM_RANGE
        if expected_outputs not in (1, 300):
            return FaultCode.ILLEGAL_PARAM_RANGE
        return None

    def _handle_heartbeat(self, message, now_ms: int) -> None:
        if self.state is not GuardState.JOB_ACTIVE:
            return
        if message.header.job_id != self.active_job_id:
            return
        self.last_heartbeat_ms = now_ms

    def _handle_job_done(self, message, now_ms: int, transport: MockTransport) -> None:
        if message.header.job_id != self.active_job_id and self.active_job_id != 0:
            return
        if self.state is GuardState.FAULT_LATCHED:
            return
        result_code = int(message.payload.get("result_code", 1))
        output_count = int(message.payload.get("output_count", 0))
        if result_code != 0 or output_count != self.expected_outputs:
            self._record_fault(
                fault_code=FaultCode.OUTPUT_INCOMPLETE,
                job_id=message.header.job_id,
                reason="job done reported failure or output mismatch",
                action="FAILED",
                now_ms=now_ms,
            )
            self._transition(GuardState.FAULT_LATCHED, "job failed during finalization", now_ms)
            self.sticky_fault = True
            self._send(
                transport=transport,
                now_ms=now_ms,
                msg_type=MessageType.FAULT_REPORT,
                job_id=message.header.job_id,
                payload={
                    "fault_code": int(FaultCode.OUTPUT_INCOMPLETE),
                    "fault_arg0": output_count,
                    "fault_arg1": self.expected_outputs,
                    "guard_state": self.state.value,
                },
            )
            return
        self._clear_active_job()
        self._transition(GuardState.READY, "job completed and finalized", now_ms)

    def _handle_reset(self, job_id: int, now_ms: int, transport: MockTransport) -> None:
        self._clear_active_job()
        self.sticky_fault = False
        self._transition(GuardState.READY, "manual reset acknowledged", now_ms)
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.RESET_ACK,
            job_id=job_id,
            payload={
                "guard_state": self.state.value,
                "last_fault_code": int(self.last_fault_code),
                "sticky_fault": int(self.sticky_fault),
            },
        )

    def _send_status(self, job_id: int, now_ms: int, transport: MockTransport) -> None:
        guard_state = self.state.value
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.STATUS_RESP,
            job_id=job_id,
            payload={
                "guard_state": guard_state,
                "active_job_id": self.active_job_id,
                "last_fault_code": int(self.last_fault_code),
                "heartbeat_ok": int(self.state is GuardState.JOB_ACTIVE),
                "sticky_fault": int(self.sticky_fault),
                "total_fault_count": self.total_fault_count,
            },
        )
        if self.state is GuardState.DENY_PENDING:
            self._transition(GuardState.READY, "deny status consumed", now_ms)

    def _handle_crc_fault(self, message, now_ms: int, transport: MockTransport) -> None:
        if self.state is GuardState.JOB_ACTIVE:
            self._trigger_safe_stop(FaultCode.CONTROL_CRC_ERROR, "control frame crc error", now_ms, transport)
            return
        self._record_fault(
            fault_code=FaultCode.CONTROL_CRC_ERROR,
            job_id=message.header.job_id,
            reason="control frame crc error",
            action="FAULT_LATCHED",
            now_ms=now_ms,
        )
        self.sticky_fault = True
        self._transition(GuardState.FAULT_LATCHED, "control frame crc error", now_ms)
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.FAULT_REPORT,
            job_id=message.header.job_id,
            payload={
                "fault_code": int(FaultCode.CONTROL_CRC_ERROR),
                "fault_arg0": message.header.seq,
                "fault_arg1": 0,
                "guard_state": self.state.value,
            },
        )

    def _deny(
        self,
        fault_code: FaultCode,
        job_id: int,
        reason: str,
        now_ms: int,
        transport: MockTransport,
    ) -> None:
        self._record_fault(fault_code, job_id, reason, "DENY", now_ms)
        self._transition(GuardState.DENY_PENDING, reason, now_ms)
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.JOB_ACK,
            job_id=job_id,
            payload={
                "decision": int(Decision.DENY),
                "fault_code": int(fault_code),
                "guard_state": self.state.value,
            },
        )

    def _trigger_safe_stop(
        self,
        fault_code: FaultCode,
        reason: str,
        now_ms: int,
        transport: MockTransport,
    ) -> None:
        self._record_fault(fault_code, self.active_job_id, reason, "SAFE_STOP", now_ms)
        self.sticky_fault = True
        self._transition(GuardState.FAULT_LATCHED, reason, now_ms)
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.SAFE_STOP,
            job_id=self.active_job_id,
            payload={
                "fault_code": int(fault_code),
                "guard_state": self.state.value,
            },
        )

    def _send(
        self,
        *,
        transport: MockTransport,
        now_ms: int,
        msg_type: MessageType,
        job_id: int,
        payload: dict[str, Any],
    ) -> None:
        self._tx_seq += 1
        message = build_message(
            msg_type=msg_type,
            seq=self._tx_seq,
            job_id=job_id,
            payload=payload,
        )
        transport.send_from_guard(message, now_ms)

    def _record_fault(
        self,
        fault_code: FaultCode,
        job_id: int,
        reason: str,
        action: str,
        now_ms: int,
    ) -> None:
        self.last_fault_code = fault_code
        self.total_fault_count += 1
        self.fault_log.append(
            {
                "at_ms": now_ms,
                "job_id": job_id,
                "fault_tag": fault_tag(fault_code),
                "fault_name": fault_name(fault_code),
                "reason": reason,
                "action": action,
                "guard_state": self.state.value,
            }
        )

    def _transition(self, new_state: GuardState, reason: str, now_ms: int) -> None:
        old_state = self.state
        if old_state is new_state and self.state_log:
            return
        self.state = new_state
        self.state_log.append(
            {
                "at_ms": now_ms,
                "component": "safety_guard",
                "from_state": old_state.value if hasattr(old_state, "value") else str(old_state),
                "to_state": new_state.value,
                "reason": reason,
                "active_job_id": self.active_job_id,
                "last_fault_code": fault_tag(self.last_fault_code),
            }
        )

    def _clear_active_job(self) -> None:
        self.active_job_id = 0
        self.expected_outputs = 0
        self.last_heartbeat_ms = None
        self.deadline_at_ms = None
        # reset inner mode machine on job boundary
        self.allowed_mode = ServiceMode.FULL_FRAME
        self.current_mode = ServiceMode.FULL_FRAME
        self._degrade_window_count = 0
        self._upgrade_window_count = 0

    # ------------------------------------------------------------------
    # Inner mode state machine: task-level degradation
    # ------------------------------------------------------------------

    def handle_link_health(
        self,
        report: LinkHealthReport,
        now_ms: int,
        transport: MockTransport,
    ) -> None:
        """Consume a link_health report and update the inner service mode.

        The outer safety FSM is untouched.  Mode directives are only
        emitted while the guard is in JOB_ACTIVE state.
        """
        if self.state is not GuardState.JOB_ACTIVE:
            return

        # 1. Link lost → immediate SAFE_STOP (reuses existing path)
        if not report.rx_locked:
            self._trigger_safe_stop(
                FaultCode.LINK_LOST,
                "link lost (rx_locked=false)",
                now_ms,
                transport,
            )
            return

        # 2. Compute target mode from measurements
        target = self._compute_target_mode(report)

        # 3. Burst-loss emergency: bypass hysteresis, jump to ALERT_ONLY
        if report.burst_loss_max >= self.BURST_LOSS_EMERGENCY:
            if self.current_mode != ServiceMode.ALERT_ONLY:
                self._set_service_mode(
                    ServiceMode.ALERT_ONLY, "burst loss emergency",
                    now_ms, transport,
                )
                self._degrade_window_count = 0
                self._upgrade_window_count = 0
                return

        # 4. Hysteresis: asymmetric thresholds (degrade=3, upgrade=5)
        if target.value > self.current_mode.value:
            # wants to degrade
            self._degrade_window_count += 1
            self._upgrade_window_count = 0
            if self._degrade_window_count >= self.DEGRADE_THRESHOLD:
                self._set_service_mode(
                    target, "sustained degradation", now_ms, transport,
                )
                self._degrade_window_count = 0
        elif target.value < self.current_mode.value:
            # wants to upgrade
            self._upgrade_window_count += 1
            self._degrade_window_count = 0
            if self._upgrade_window_count >= self.UPGRADE_THRESHOLD:
                self._set_service_mode(
                    target, "sustained recovery", now_ms, transport,
                )
                self._upgrade_window_count = 0
        else:
            self._degrade_window_count = 0
            self._upgrade_window_count = 0

    def _handle_link_health_msg(
        self, message, now_ms: int, transport: MockTransport,
    ) -> None:
        """Unwrap a LINK_HEALTH control message into handle_link_health."""
        report = LinkHealthReport(
            snr_est_db_x100=int(message.payload.get("snr_est_db_x100", 0)),
            per_x1000=int(message.payload.get("per_x1000", 0)),
            burst_loss_max=int(message.payload.get("burst_loss_max", 0)),
            rx_locked=bool(message.payload.get("rx_locked", True)),
            effective_throughput_kbps=int(message.payload.get("effective_throughput_kbps", 0)),
            window_id=int(message.payload.get("window_id", 0)),
            timestamp_ms=int(message.payload.get("timestamp_ms", now_ms)),
        )
        self.handle_link_health(report, now_ms, transport)

    def _compute_target_mode(self, report: LinkHealthReport) -> ServiceMode:
        """Determine desired service mode from link measurements."""
        if report.per_x1000 > self.PER_ALERT_THRESHOLD:
            return ServiceMode.ALERT_ONLY
        if (report.per_x1000 > self.PER_ROI_THRESHOLD
                or report.snr_est_db_x100 < self.SNR_ROI_THRESHOLD):
            return ServiceMode.ROI_ONLY
        return ServiceMode.FULL_FRAME

    def _set_service_mode(
        self,
        mode: ServiceMode,
        reason: str,
        now_ms: int,
        transport: MockTransport,
    ) -> None:
        """Commit a service-mode transition and emit MODE_DIRECTIVE."""
        old = self.current_mode
        if old is mode:
            return
        self.current_mode = mode
        self.allowed_mode = mode
        self.mode_log.append({
            "at_ms": now_ms,
            "from_mode": old.name,
            "to_mode": mode.name,
            "reason": reason,
            "job_id": self.active_job_id,
        })
        self._send(
            transport=transport,
            now_ms=now_ms,
            msg_type=MessageType.MODE_DIRECTIVE,
            job_id=self.active_job_id,
            payload={
                "allowed_mode": int(mode),
                "mode_name": mode.name,
                "reason": reason,
            },
        )
