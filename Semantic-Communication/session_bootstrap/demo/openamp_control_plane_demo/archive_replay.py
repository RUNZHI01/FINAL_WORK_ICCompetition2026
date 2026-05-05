from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from event_spine import MODE_BOUNDARY_NOTE, EventStateStore, sanitize_json


DEFAULT_ARCHIVE_RECENT_LIMIT = 25
ARCHIVE_SUMMARY_RECENT_LIMIT = 1
ARCHIVE_REPLAY_EVENT_LIMIT = 200

_ONLINE_EVENT_TYPES = {
    "ARCHIVE_SNAPSHOT_WRITTEN",
    "FRAME_RECON_READY",
    "HEARTBEAT_OK",
    "JOB_ADMITTED",
    "JOB_DONE",
    "JOB_STARTED",
    "LINK_PROFILE_CHANGED",
    "SAFE_STOP_CLEARED",
}
_DEGRADED_EVENT_TYPES = {
    "HEARTBEAT_LOST",
    "JOB_REJECTED",
    "SAFE_STOP_TRIGGERED",
}


class ArchiveSessionNotFoundError(FileNotFoundError):
    pass


def resolve_archive_root(archive_root: str | Path | None) -> Path | None:
    if archive_root is None:
        return None
    return Path(archive_root).resolve()


def list_archive_sessions(
    archive_root: str | Path | None,
    *,
    current_session_id: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    root = resolve_archive_root(archive_root)
    if root is None:
        return {
            "status": "ok",
            "archive_root": "",
            "current_session_id": current_session_id,
            "session_count": 0,
            "sessions": [],
        }
    if not root.exists():
        return {
            "status": "ok",
            "archive_root": str(root),
            "current_session_id": current_session_id,
            "session_count": 0,
            "sessions": [],
        }

    summaries: list[dict[str, Any]] = []
    for session_dir in sorted((item for item in root.iterdir() if item.is_dir()), reverse=True):
        session_payload = _load_archive_session_payload(session_dir, recent_limit=ARCHIVE_SUMMARY_RECENT_LIMIT)
        summary = {
            **session_payload["summary"],
            "is_current_session": session_payload["summary"]["session_id"] == current_session_id,
        }
        summaries.append(summary)

    summaries.sort(
        key=lambda item: (
            str(item.get("last_event_at") or ""),
            str(item.get("last_snapshot_at") or ""),
            str(item.get("started_at") or ""),
            str(item.get("session_id") or ""),
        ),
        reverse=True,
    )
    bounded = summaries[: max(1, limit)]
    return {
        "status": "ok",
        "archive_root": str(root),
        "current_session_id": current_session_id,
        "session_count": len(summaries),
        "sessions": sanitize_json(bounded),
    }


def load_archive_session(
    archive_root: str | Path | None,
    *,
    session_id: str,
    recent_limit: int = DEFAULT_ARCHIVE_RECENT_LIMIT,
) -> dict[str, Any]:
    root = resolve_archive_root(archive_root)
    if root is None:
        raise ArchiveSessionNotFoundError("archive root is disabled")
    if not session_id:
        raise ArchiveSessionNotFoundError("missing session_id")

    session_dir = root / session_id
    if not session_dir.is_dir():
        raise ArchiveSessionNotFoundError(f"archive session not found: {session_id}")

    return _load_archive_session_payload(session_dir, recent_limit=recent_limit)


def _load_archive_session_payload(session_dir: Path, *, recent_limit: int) -> dict[str, Any]:
    recent_limit = max(1, min(ARCHIVE_REPLAY_EVENT_LIMIT, recent_limit))
    errors: list[str] = []
    paths = _session_paths(session_dir)
    snapshot_payload = _load_snapshot_payload(paths["state_snapshot_json"], errors)
    events = _load_event_stream(paths["events_jsonl"], errors)
    aggregate = _replay_archive_events(
        session_id=session_dir.name,
        snapshot_payload=snapshot_payload,
        snapshot_path=paths["state_snapshot_json"],
        events=events,
        recent_limit=recent_limit,
    )

    archive_aggregate = aggregate.get("archive", {}) if isinstance(aggregate.get("archive"), dict) else {}
    aggregate["archive"] = {
        **archive_aggregate,
        "enabled": True,
        "status": "ready" if not errors else "error",
        "last_error": errors[-1] if errors else "",
        "root": str(session_dir.parent),
        "session_dir": str(paths["session_dir"]),
        "events_jsonl": str(paths["events_jsonl"]),
        "state_snapshot_json": str(paths["state_snapshot_json"]),
    }
    mode_boundary_note = (
        str(snapshot_payload.get("mode_boundary_note") or "")
        or str(aggregate.get("mode_boundary_note") or "")
        or MODE_BOUNDARY_NOTE
    )
    last_job_id = ""
    jobs = aggregate.get("jobs")
    if isinstance(jobs, dict):
        last_job_id = str(jobs.get("last_job_id") or "")

    summary = {
        "session_id": session_dir.name,
        "started_at": str(aggregate.get("started_at") or ""),
        "event_count": int(aggregate.get("event_count") or 0),
        "last_event_at": str(aggregate.get("last_event_at") or ""),
        "last_event_type": str(aggregate.get("last_event_type") or ""),
        "last_job_id": last_job_id,
        "last_snapshot_at": str(aggregate["archive"].get("last_snapshot_at") or ""),
        "last_snapshot_reason": str(aggregate["archive"].get("last_snapshot_reason") or ""),
        "mode_boundary_note": mode_boundary_note,
        "has_events": paths["events_jsonl"].is_file(),
        "has_snapshot": paths["state_snapshot_json"].is_file(),
        "paths": {
            "session_dir": str(paths["session_dir"]),
            "events_jsonl": str(paths["events_jsonl"]),
            "state_snapshot_json": str(paths["state_snapshot_json"]),
        },
        "read_error_count": len(errors),
    }
    snapshot_recent_events = snapshot_payload.get("recent_events") if isinstance(snapshot_payload.get("recent_events"), list) else []
    raw_recent_events = events[-recent_limit:] if events else snapshot_recent_events[-recent_limit:]
    recent_events = sanitize_json(list(reversed(raw_recent_events)))
    timeline = [_build_timeline_event(event) for event in recent_events]
    snapshot = {
        "exists": bool(snapshot_payload),
        "generated_at": str(snapshot_payload.get("generated_at") or ""),
        "reason": str(snapshot_payload.get("reason") or ""),
        "mode_boundary_note": str(snapshot_payload.get("mode_boundary_note") or ""),
        "path": str(paths["state_snapshot_json"]),
        "extra": sanitize_json(snapshot_payload.get("extra") or {}),
        "recent_event_count": len(snapshot_payload.get("recent_events") or []) if isinstance(snapshot_payload, dict) else 0,
    }
    return {
        "status": "ok",
        "archive_root": str(session_dir.parent),
        "session_id": session_dir.name,
        "mode_boundary_note": mode_boundary_note,
        "summary": sanitize_json(summary),
        "aggregate": sanitize_json(aggregate),
        "snapshot": snapshot,
        "recent_events": recent_events,
        "timeline": timeline,
        "paths": sanitize_json(summary["paths"]),
        "read_errors": sanitize_json(errors),
    }


def _session_paths(session_dir: Path) -> dict[str, Path]:
    return {
        "session_dir": session_dir.resolve(),
        "events_jsonl": (session_dir / "events.jsonl").resolve(),
        "state_snapshot_json": (session_dir / "state_snapshot.json").resolve(),
    }


def _load_snapshot_payload(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"state_snapshot.json: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("state_snapshot.json: expected object payload")
        return {}
    return payload


def _load_event_stream(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    errors.append(f"events.jsonl:{line_number}: {exc.msg}")
                    continue
                if not isinstance(payload, dict):
                    errors.append(f"events.jsonl:{line_number}: expected object payload")
                    continue
                events.append(payload)
    except OSError as exc:
        errors.append(f"events.jsonl: {exc}")
    return events


def _replay_archive_events(
    *,
    session_id: str,
    snapshot_payload: dict[str, Any],
    snapshot_path: Path,
    events: list[dict[str, Any]],
    recent_limit: int,
) -> dict[str, Any]:
    snapshot_aggregate = snapshot_payload.get("aggregate") if isinstance(snapshot_payload.get("aggregate"), dict) else {}
    started_at = str(snapshot_aggregate.get("started_at") or "")
    if not started_at and events:
        started_at = str(events[0].get("timestamp") or "")
    if not started_at:
        started_at = str(snapshot_payload.get("generated_at") or "")

    if events:
        store = EventStateStore(
            session_id=session_id,
            started_at=started_at,
            recent_limit=max(64, recent_limit),
        )
        for event in events:
            store.apply(event)
        aggregate = store.snapshot()
    elif snapshot_aggregate:
        aggregate = sanitize_json(snapshot_aggregate)
        aggregate["session_id"] = str(aggregate.get("session_id") or session_id)
        aggregate["started_at"] = str(aggregate.get("started_at") or started_at)
    else:
        aggregate = EventStateStore(
            session_id=session_id,
            started_at=started_at,
            recent_limit=max(64, recent_limit),
        ).snapshot()
    archive = aggregate.get("archive") if isinstance(aggregate.get("archive"), dict) else {}
    if snapshot_payload:
        archive = {
            **archive,
            "last_snapshot_at": str(archive.get("last_snapshot_at") or snapshot_payload.get("generated_at") or ""),
            "last_snapshot_reason": str(archive.get("last_snapshot_reason") or snapshot_payload.get("reason") or ""),
            "last_snapshot_path": str(archive.get("last_snapshot_path") or snapshot_path),
        }
    aggregate["archive"] = archive
    aggregate["mode_boundary_note"] = (
        str(snapshot_payload.get("mode_boundary_note") or "")
        or str(aggregate.get("mode_boundary_note") or "")
        or MODE_BOUNDARY_NOTE
    )
    return aggregate


def _build_timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("type") or "")
    plane = str(event.get("plane") or "") or "event"
    tone = _timeline_tone(event_type, plane)
    return {
        "event_id": str(event.get("event_id") or ""),
        "sequence": event.get("sequence"),
        "timestamp": str(event.get("timestamp") or ""),
        "type": event_type,
        "title": event_type,
        "summary": str(event.get("message") or ""),
        "lane": plane,
        "tone": tone,
        "job_id": str(event.get("job_id") or ""),
        "source": str(event.get("source") or ""),
        "mode_scope": str(event.get("mode_scope") or ""),
    }


def _timeline_tone(event_type: str, plane: str) -> str:
    if event_type in _ONLINE_EVENT_TYPES:
        return "online"
    if event_type in _DEGRADED_EVENT_TYPES:
        return "degraded"
    if plane == "archive":
        return "neutral"
    return "neutral"
