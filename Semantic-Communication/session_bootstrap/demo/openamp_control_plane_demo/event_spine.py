from __future__ import annotations

from collections import deque
from datetime import datetime
import json
from pathlib import Path
from threading import Lock
from typing import Any, Callable


CONTROL_MODE_SCOPE = "3-core Linux + RTOS demo mode / OpenAMP control-only path"
DATA_MODE_SCOPE = "4-core Linux performance mode / reconstruction evidence path"
ARCHIVE_MODE_SCOPE = "demo archive / local event evidence"
MODE_BOUNDARY_NOTE = (
    "4-core Linux performance mode only covers performance and reconstruction evidence; "
    "3-core Linux + RTOS demo mode only covers OpenAMP admission, heartbeat, and SAFE_STOP."
)
EVENT_TYPES = (
    "LINK_PROFILE_CHANGED",
    "JOB_SUBMITTED",
    "JOB_ADMITTED",
    "JOB_REJECTED",
    "JOB_STARTED",
    "JOB_DONE",
    "HEARTBEAT_OK",
    "HEARTBEAT_LOST",
    "SAFE_STOP_TRIGGERED",
    "SAFE_STOP_CLEARED",
    "FRAME_RECON_READY",
    "ARCHIVE_SNAPSHOT_WRITTEN",
    "COORD_FORWARDED",
    "MODE_ALERT_ACTIVE",
    "MODE_ROI_ACTIVE",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_session_id() -> str:
    return datetime.now().astimezone().strftime("session_%Y%m%d_%H%M%S")


def sanitize_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def default_event_archive_root() -> Path:
    return Path(__file__).resolve().parent / "runtime" / "event_archives"


class InProcessEventBus:
    def __init__(self) -> None:
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []

    def subscribe(self, handler: Callable[[dict[str, Any]], None]) -> None:
        self._subscribers.append(handler)

    def publish(self, event: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for handler in list(self._subscribers):
            try:
                handler(event)
            except Exception as exc:  # pragma: no cover - defensive fail-open path
                errors.append(str(exc))
        return errors


class JsonlEventArchive:
    def __init__(self, archive_root: str | Path | None, session_id: str) -> None:
        self._enabled = archive_root is not None
        self._root = Path(archive_root).resolve() if archive_root is not None else None
        self._session_id = session_id
        self._session_dir = self._root / session_id if self._root is not None else None
        self._events_path = self._session_dir / "events.jsonl" if self._session_dir is not None else None
        self._state_snapshot_path = (
            self._session_dir / "state_snapshot.json" if self._session_dir is not None else None
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def append(self, event: dict[str, Any]) -> None:
        if not self._enabled or self._events_path is None:
            return
        self._events_path.parent.mkdir(parents=True, exist_ok=True)
        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def write_state_snapshot(self, payload: dict[str, Any]) -> Path | None:
        if not self._enabled or self._state_snapshot_path is None:
            return None
        self._state_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self._state_snapshot_path

    def describe(self, *, last_error: str = "") -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "status": "error" if last_error else ("ready" if self._enabled else "disabled"),
            "last_error": last_error,
            "session_id": self._session_id,
            "root": str(self._root) if self._root is not None else "",
            "session_dir": str(self._session_dir) if self._session_dir is not None else "",
            "events_jsonl": str(self._events_path) if self._events_path is not None else "",
            "state_snapshot_json": str(self._state_snapshot_path) if self._state_snapshot_path is not None else "",
        }


class EventStateStore:
    def __init__(self, *, session_id: str, started_at: str, recent_limit: int) -> None:
        self._recent_limit = max(1, recent_limit)
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=self._recent_limit)
        self._jobs: dict[str, dict[str, Any]] = {}
        self._aggregate: dict[str, Any] = {
            "session_id": session_id,
            "started_at": started_at,
            "mode_boundary_note": MODE_BOUNDARY_NOTE,
            "event_count": 0,
            "last_event_at": "",
            "last_event_type": "",
            "event_counters": {event_type: 0 for event_type in EVENT_TYPES},
            "link_profile": {
                "selected_profile_id": "normal",
                "selected_profile_label": "正常链路",
                "last_changed_at": "",
            },
            "heartbeat": {
                "status": "unknown",
                "last_ok_at": "",
                "last_lost_at": "",
                "last_job_id": "",
            },
            "safe_stop": {
                "active": False,
                "last_triggered_at": "",
                "last_cleared_at": "",
                "reason": "",
                "last_job_id": "",
            },
            "frames": {
                "ready_count": 0,
                "last_ready_at": "",
                "last_job_id": "",
            },
            "jobs": {
                "submitted_count": 0,
                "admitted_count": 0,
                "rejected_count": 0,
                "preview_submitted_count": 0,
                "preview_admitted_count": 0,
                "preview_rejected_count": 0,
                "started_count": 0,
                "done_count": 0,
                "active_job_id": "",
                "last_job_id": "",
                "by_id": self._jobs,
            },
            "archive": {
                "last_snapshot_at": "",
                "last_snapshot_reason": "",
                "last_snapshot_path": "",
            },
        }

    def apply(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "")
        timestamp = str(event.get("timestamp") or "")
        job_id = str(event.get("job_id") or "")
        message = str(event.get("message") or "")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        preview_only = bool(data.get("preview_only"))

        self._recent_events.append(sanitize_json(event))
        self._aggregate["event_count"] += 1
        self._aggregate["last_event_at"] = timestamp
        self._aggregate["last_event_type"] = event_type
        counters = self._aggregate.get("event_counters")
        if isinstance(counters, dict):
            counters[event_type] = int(counters.get(event_type, 0)) + 1

        job_record: dict[str, Any] | None = None
        if job_id:
            job_record = self._jobs.setdefault(
                job_id,
                {
                    "job_id": job_id,
                    "variant": "",
                    "status": "seen",
                    "last_event_type": "",
                    "last_updated_at": "",
                    "message": "",
                },
            )
            variant = str(data.get("variant") or "")
            if variant:
                job_record["variant"] = variant
            job_record["last_event_type"] = event_type
            job_record["last_updated_at"] = timestamp
            job_record["message"] = message
            self._aggregate["jobs"]["last_job_id"] = job_id

        if event_type == "LINK_PROFILE_CHANGED":
            self._aggregate["link_profile"] = {
                "selected_profile_id": str(data.get("profile_id") or ""),
                "selected_profile_label": str(data.get("profile_label") or ""),
                "last_changed_at": timestamp,
            }
            return

        if event_type == "JOB_SUBMITTED":
            if preview_only:
                self._aggregate["jobs"]["preview_submitted_count"] += 1
                if job_record is not None:
                    job_record["status"] = "preview_submitted"
            else:
                self._aggregate["jobs"]["submitted_count"] += 1
            return

        if event_type == "JOB_ADMITTED":
            if preview_only:
                self._aggregate["jobs"]["preview_admitted_count"] += 1
                if job_record is not None:
                    job_record["status"] = "preview_admitted"
            else:
                self._aggregate["jobs"]["admitted_count"] += 1
                if job_record is not None:
                    job_record["status"] = "admitted"
            return

        if event_type == "JOB_REJECTED":
            if preview_only:
                self._aggregate["jobs"]["preview_rejected_count"] += 1
                if job_record is not None:
                    job_record["status"] = "preview_rejected"
            else:
                self._aggregate["jobs"]["rejected_count"] += 1
                if job_record is not None:
                    job_record["status"] = "rejected"
            return

        if event_type == "JOB_STARTED":
            self._aggregate["jobs"]["started_count"] += 1
            self._aggregate["jobs"]["active_job_id"] = job_id
            if job_record is not None:
                job_record["status"] = "running"
            return

        if event_type == "JOB_DONE":
            self._aggregate["jobs"]["done_count"] += 1
            if self._aggregate["jobs"]["active_job_id"] == job_id:
                self._aggregate["jobs"]["active_job_id"] = ""
            if job_record is not None:
                job_record["status"] = "done"
            return

        if event_type == "HEARTBEAT_OK":
            self._aggregate["heartbeat"] = {
                "status": "ok",
                "last_ok_at": timestamp,
                "last_lost_at": self._aggregate["heartbeat"]["last_lost_at"],
                "last_job_id": job_id,
            }
            return

        if event_type == "HEARTBEAT_LOST":
            self._aggregate["heartbeat"] = {
                "status": "lost",
                "last_ok_at": self._aggregate["heartbeat"]["last_ok_at"],
                "last_lost_at": timestamp,
                "last_job_id": job_id,
            }
            return

        if event_type == "SAFE_STOP_TRIGGERED":
            self._aggregate["safe_stop"] = {
                "active": True,
                "last_triggered_at": timestamp,
                "last_cleared_at": self._aggregate["safe_stop"]["last_cleared_at"],
                "reason": str(data.get("reason") or ""),
                "last_job_id": job_id,
            }
            return

        if event_type == "SAFE_STOP_CLEARED":
            self._aggregate["safe_stop"] = {
                "active": False,
                "last_triggered_at": self._aggregate["safe_stop"]["last_triggered_at"],
                "last_cleared_at": timestamp,
                "reason": str(data.get("reason") or ""),
                "last_job_id": job_id,
            }
            return

        if event_type == "FRAME_RECON_READY":
            self._aggregate["frames"]["ready_count"] += 1
            self._aggregate["frames"]["last_ready_at"] = timestamp
            self._aggregate["frames"]["last_job_id"] = job_id
            return

        if event_type == "ARCHIVE_SNAPSHOT_WRITTEN":
            self._aggregate["archive"] = {
                "last_snapshot_at": timestamp,
                "last_snapshot_reason": str(data.get("reason") or ""),
                "last_snapshot_path": str(data.get("path") or ""),
            }

    def snapshot(self) -> dict[str, Any]:
        return sanitize_json(self._aggregate)

    def recent_events(self, limit: int) -> list[dict[str, Any]]:
        window = list(self._recent_events)[-max(1, limit) :]
        return sanitize_json(list(reversed(window)))


class DemoEventSpine:
    def __init__(
        self,
        archive_root: str | Path | None = None,
        *,
        session_id: str | None = None,
        recent_limit: int = 64,
    ) -> None:
        self._lock = Lock()
        self._session_id = session_id or build_session_id()
        self._started_at = now_iso()
        self._next_sequence = 0
        self._last_error = ""
        self._bus = InProcessEventBus()
        self._store = EventStateStore(
            session_id=self._session_id,
            started_at=self._started_at,
            recent_limit=recent_limit,
        )
        self._archive = JsonlEventArchive(archive_root, self._session_id)
        self._bus.subscribe(self._store.apply)
        self._bus.subscribe(self._archive.append)

    @property
    def session_id(self) -> str:
        return self._session_id

    def publish(
        self,
        event_type: str,
        *,
        job_id: str = "",
        source: str,
        plane: str,
        mode_scope: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {event_type}")

        with self._lock:
            self._next_sequence += 1
            event = {
                "event_id": f"{self._session_id}:{self._next_sequence:06d}",
                "sequence": self._next_sequence,
                "session_id": self._session_id,
                "timestamp": now_iso(),
                "type": event_type,
                "job_id": str(job_id or ""),
                "source": source,
                "plane": plane,
                "mode_scope": mode_scope,
                "message": message,
                "data": sanitize_json(data or {}),
            }
            errors = self._bus.publish(event)
            self._last_error = errors[-1] if errors else ""
            return sanitize_json(event)

    def write_snapshot(
        self,
        *,
        reason: str,
        job_id: str = "",
        extra: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "generated_at": now_iso(),
            "session_id": self._session_id,
            "reason": reason,
            "mode_boundary_note": MODE_BOUNDARY_NOTE,
            "aggregate": self._store.snapshot(),
            "recent_events": self._store.recent_events(16),
            "extra": sanitize_json(extra or {}),
        }
        try:
            written_path = self._archive.write_state_snapshot(payload)
        except Exception as exc:  # pragma: no cover - defensive fail-open path
            self._last_error = str(exc)
            return ""
        if written_path is None:
            return ""
        self.publish(
            "ARCHIVE_SNAPSHOT_WRITTEN",
            job_id=job_id,
            source="archive",
            plane="archive",
            mode_scope=ARCHIVE_MODE_SCOPE,
            message=f"Event spine snapshot written ({reason}).",
            data={"reason": reason, "path": str(written_path)},
        )
        return str(written_path)

    def summary(self, *, limit: int = 25) -> dict[str, Any]:
        aggregate = self._store.snapshot()
        aggregate["archive"] = {
            **aggregate.get("archive", {}),
            **self._archive.describe(last_error=self._last_error),
        }
        return {
            "status": "ok",
            "session_id": self._session_id,
            "started_at": self._started_at,
            "mode_boundary_note": MODE_BOUNDARY_NOTE,
            "event_types": list(EVENT_TYPES),
            "aggregate": aggregate,
            "recent_events": self._store.recent_events(limit),
        }
