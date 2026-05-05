"""Link health reporting and simulation for task-level degradation.

This module defines the link_health interface between the USRP RX side and
the Phytium guard control plane.  During development, LinkHealthSimulator
produces synthetic reports so that guard + orchestrator testing does not
depend on real USRP hardware.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class LinkHealthReport:
    """One link-health measurement window from the USRP RX side.

    This is the *only* interface contract between the USRP friend's code
    and the Phytium guard.  The USRP RX writes these as JSON at a fixed
    cadence (recommended 500 ms), and the guard polls them.

    Fields:
        snr_est_db_x100:  estimated SNR × 100  (e.g. 1050 → 10.5 dB)
        per_x1000:        packet error rate × 1000  (e.g. 45 → 4.5%)
        burst_loss_max:   max consecutive lost packets in this window
        rx_locked:        whether USRP RX is still locked
        effective_throughput_kbps:  usable throughput in kbps
        window_id:        monotonically increasing window counter
        timestamp_ms:     wall-clock timestamp in ms
    """
    snr_est_db_x100: int
    per_x1000: int
    burst_loss_max: int
    rx_locked: bool
    effective_throughput_kbps: int
    window_id: int
    timestamp_ms: int


# ---------------------------------------------------------------------------
# Simulator – generate synthetic link_health reports for dev / FIT testing
# ---------------------------------------------------------------------------

# Pre-defined link profiles
PROFILE_NORMAL = LinkHealthReport(
    snr_est_db_x100=1500, per_x1000=0, burst_loss_max=0,
    rx_locked=True, effective_throughput_kbps=256,
    window_id=0, timestamp_ms=0,
)
PROFILE_DEGRADED = LinkHealthReport(
    snr_est_db_x100=350, per_x1000=80, burst_loss_max=2,
    rx_locked=True, effective_throughput_kbps=64,
    window_id=0, timestamp_ms=0,
)
PROFILE_SEVERE = LinkHealthReport(
    snr_est_db_x100=100, per_x1000=250, burst_loss_max=5,
    rx_locked=True, effective_throughput_kbps=16,
    window_id=0, timestamp_ms=0,
)
PROFILE_BURST_LOSS = LinkHealthReport(
    snr_est_db_x100=300, per_x1000=150, burst_loss_max=15,
    rx_locked=True, effective_throughput_kbps=32,
    window_id=0, timestamp_ms=0,
)
PROFILE_LOST = LinkHealthReport(
    snr_est_db_x100=0, per_x1000=1000, burst_loss_max=0,
    rx_locked=False, effective_throughput_kbps=0,
    window_id=0, timestamp_ms=0,
)


def _stamp(profile: LinkHealthReport, window_id: int, timestamp_ms: int) -> LinkHealthReport:
    """Return a copy of *profile* with window_id and timestamp_ms updated."""
    return LinkHealthReport(
        snr_est_db_x100=profile.snr_est_db_x100,
        per_x1000=profile.per_x1000,
        burst_loss_max=profile.burst_loss_max,
        rx_locked=profile.rx_locked,
        effective_throughput_kbps=profile.effective_throughput_kbps,
        window_id=window_id,
        timestamp_ms=timestamp_ms,
    )


class LinkHealthSimulator:
    """Generate synthetic LinkHealthReport sequences for dev and FIT testing.

    Usage::

        sim = LinkHealthSimulator()
        reports = sim.progressive_degradation(steps=10)
        for r in reports:
            guard.handle_link_health(r, ...)
    """

    def __init__(self, window_interval_ms: int = 500) -> None:
        self.window_interval_ms = window_interval_ms
        self._window_id = 0
        self._now_ms = 0

    def _next(self, profile: LinkHealthReport) -> LinkHealthReport:
        self._window_id += 1
        self._now_ms += self.window_interval_ms
        return _stamp(profile, self._window_id, self._now_ms)

    def normal(self) -> LinkHealthReport:
        """One normal-quality window."""
        return self._next(PROFILE_NORMAL)

    def degraded(self) -> LinkHealthReport:
        """One degraded-quality window (triggers ROI after hysteresis)."""
        return self._next(PROFILE_DEGRADED)

    def severe(self) -> LinkHealthReport:
        """One severely-degraded window (triggers ALERT after hysteresis)."""
        return self._next(PROFILE_SEVERE)

    def burst_loss(self) -> LinkHealthReport:
        """One window with burst loss >= emergency threshold."""
        return self._next(PROFILE_BURST_LOSS)

    def lost(self) -> LinkHealthReport:
        """One window with rx_locked=False (triggers SAFE_STOP)."""
        return self._next(PROFILE_LOST)

    # ------------------------------------------------------------------
    # Composite scenarios (used by FIT tests)
    # ------------------------------------------------------------------

    def progressive_degradation(self, steps: int = 10) -> list[LinkHealthReport]:
        """Simulate link going from normal → degraded → severe → lost."""
        result: list[LinkHealthReport] = []
        per_phase = max(1, steps // 4)
        for _ in range(per_phase):
            result.append(self.normal())
        for _ in range(per_phase):
            result.append(self.degraded())
        for _ in range(per_phase):
            result.append(self.severe())
        for _ in range(steps - 3 * per_phase):
            result.append(self.lost())
        return result

    def degrade_then_recover(self, degrade_windows: int = 4,
                              recover_windows: int = 6) -> list[LinkHealthReport]:
        """Degrade to ROI, hold, then recover to FULL (tests hysteresis)."""
        result: list[LinkHealthReport] = []
        for _ in range(degrade_windows):
            result.append(self.degraded())
        for _ in range(recover_windows):
            result.append(self.normal())
        return result

    def burst_loss_spike(self, normal_before: int = 2,
                          normal_after: int = 3) -> list[LinkHealthReport]:
        """Normal → single burst loss spike → normal (tests emergency path)."""
        result: list[LinkHealthReport] = []
        for _ in range(normal_before):
            result.append(self.normal())
        result.append(self.burst_loss())
        for _ in range(normal_after):
            result.append(self.normal())
        return result


# ---------------------------------------------------------------------------
# File-based poll interface (for real USRP integration)
# ---------------------------------------------------------------------------
DEFAULT_LINK_HEALTH_PATH = Path("/tmp/usrp_link_health.json")


def read_link_health(path: Path = DEFAULT_LINK_HEALTH_PATH) -> LinkHealthReport | None:
    """Poll the link_health JSON file written by the USRP RX side."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LinkHealthReport(**data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None


def write_link_health(report: LinkHealthReport,
                      path: Path = DEFAULT_LINK_HEALTH_PATH) -> None:
    """Write a link_health JSON (used by simulator or USRP RX)."""
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
