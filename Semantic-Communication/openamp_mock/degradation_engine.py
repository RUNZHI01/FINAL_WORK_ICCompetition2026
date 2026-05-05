from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .link_health import LinkHealthReport
from .protocol import ServiceMode


@dataclass
class ModeTransition:
    """One degradation-mode transition on the upper computer."""

    timestamp_ms: int
    from_mode: str
    to_mode: str
    reason: str


class DegradationEngine:
    """Upper-computer-only degradation policy engine.

    Consumes link-health windows and decides which payload strategy should be
    sent next. This class is intentionally side-effect free.
    """

    DEGRADE_THRESHOLD: int = 3
    UPGRADE_THRESHOLD: int = 5
    BURST_LOSS_EMERGENCY: int = 10
    SNR_ROI_THRESHOLD: int = 500
    PER_ROI_THRESHOLD: int = 50
    PER_ALERT_THRESHOLD: int = 200

    def __init__(self) -> None:
        self.current_mode: ServiceMode = ServiceMode.FULL_FRAME
        self.mode_log: list[ModeTransition] = []
        self._degrade_window_count: int = 0
        self._upgrade_window_count: int = 0
        self._link_lost: bool = False

    @property
    def is_link_lost(self) -> bool:
        return self._link_lost

    @property
    def payload_strategy(self) -> str:
        if self.current_mode == ServiceMode.FULL_FRAME:
            return "full_latent"
        if self.current_mode == ServiceMode.ROI_ONLY:
            return "roi_latent"
        return "alert_metadata"

    def update(self, report: LinkHealthReport) -> ServiceMode:
        now_ms = report.timestamp_ms or int(time.time() * 1000)

        if not report.rx_locked:
            self._link_lost = True
            self._degrade_window_count = 0
            self._upgrade_window_count = 0
            self._set_mode(ServiceMode.ALERT_ONLY, "link lost (rx_locked=false)", now_ms)
            return self.current_mode

        self._link_lost = False
        target = self._compute_target_mode(report)

        if report.burst_loss_max >= self.BURST_LOSS_EMERGENCY:
            self._degrade_window_count = 0
            self._upgrade_window_count = 0
            self._set_mode(ServiceMode.ALERT_ONLY, "burst loss emergency", now_ms)
            return self.current_mode

        if target.value > self.current_mode.value:
            self._degrade_window_count += 1
            self._upgrade_window_count = 0
            if self._degrade_window_count >= self.DEGRADE_THRESHOLD:
                self._set_mode(target, "sustained degradation", now_ms)
                self._degrade_window_count = 0
        elif target.value < self.current_mode.value:
            self._upgrade_window_count += 1
            self._degrade_window_count = 0
            if self._upgrade_window_count >= self.UPGRADE_THRESHOLD:
                self._set_mode(target, "sustained recovery", now_ms)
                self._upgrade_window_count = 0
        else:
            self._degrade_window_count = 0
            self._upgrade_window_count = 0

        return self.current_mode

    def reset(self) -> None:
        self.current_mode = ServiceMode.FULL_FRAME
        self.mode_log.clear()
        self._degrade_window_count = 0
        self._upgrade_window_count = 0
        self._link_lost = False

    def snapshot(self) -> dict[str, Any]:
        last_transition = None
        if self.mode_log:
            latest = self.mode_log[-1]
            last_transition = {
                "from_mode": latest.from_mode,
                "to_mode": latest.to_mode,
                "reason": latest.reason,
                "timestamp_ms": latest.timestamp_ms,
            }

        return {
            "current_mode": self.current_mode.name,
            "current_mode_value": int(self.current_mode),
            "payload_strategy": self.payload_strategy,
            "is_link_lost": self._link_lost,
            "degrade_window_count": self._degrade_window_count,
            "upgrade_window_count": self._upgrade_window_count,
            "mode_transitions": len(self.mode_log),
            "last_transition": last_transition,
        }

    def _compute_target_mode(self, report: LinkHealthReport) -> ServiceMode:
        if report.per_x1000 > self.PER_ALERT_THRESHOLD:
            return ServiceMode.ALERT_ONLY
        if report.per_x1000 > self.PER_ROI_THRESHOLD or report.snr_est_db_x100 < self.SNR_ROI_THRESHOLD:
            return ServiceMode.ROI_ONLY
        return ServiceMode.FULL_FRAME

    def _set_mode(self, mode: ServiceMode, reason: str, now_ms: int) -> None:
        previous = self.current_mode
        if previous is mode:
            return
        self.current_mode = mode
        self.mode_log.append(
            ModeTransition(
                timestamp_ms=now_ms,
                from_mode=previous.name,
                to_mode=mode.name,
                reason=reason,
            )
        )
