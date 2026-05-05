from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRUSTED_ARTIFACTS_PATH = PROJECT_ROOT / "session_bootstrap" / "config" / "openamp_trusted_artifacts.json"
HEX_DIGITS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class TrustedArtifact:
    label: str
    sha256: str
    enabled: bool
    source: str = ""
    note: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "sha256": self.sha256,
            "enabled": self.enabled,
            "source": self.source,
            "note": self.note,
        }


def resolve_trusted_artifacts_path(raw: str | Path | None = None) -> Path:
    if raw is None or raw == "":
        return DEFAULT_TRUSTED_ARTIFACTS_PATH
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def normalize_sha256(raw: Any, *, field_name: str = "sha256") -> str:
    text = str(raw or "").strip().lower()
    if len(text) != 64 or any(char not in HEX_DIGITS for char in text):
        raise ValueError(f"{field_name} must be a 64-character lowercase or uppercase SHA-256 hex string")
    return text


def load_trusted_artifacts(raw: str | Path | None = None) -> list[TrustedArtifact]:
    config_path = resolve_trusted_artifacts_path(raw)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError(f"{config_path} is missing an entries list")

    artifacts: list[TrustedArtifact] = []
    seen_labels: set[str] = set()
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"{config_path} entries[{index}] must be an object")
        label = str(raw_entry.get("label") or "").strip().lower()
        if not label:
            raise ValueError(f"{config_path} entries[{index}] is missing label")
        if label in seen_labels:
            raise ValueError(f"{config_path} contains duplicate label {label!r}")
        seen_labels.add(label)
        artifacts.append(
            TrustedArtifact(
                label=label,
                sha256=normalize_sha256(raw_entry.get("sha256"), field_name=f"entries[{index}].sha256"),
                enabled=bool(raw_entry.get("enabled", False)),
                source=str(raw_entry.get("source") or "").strip(),
                note=str(raw_entry.get("note") or "").strip(),
            )
        )
    return artifacts


def find_trusted_artifact(
    label: str,
    *,
    raw: str | Path | None = None,
    require_enabled: bool = True,
) -> TrustedArtifact:
    normalized_label = str(label or "").strip().lower()
    if not normalized_label:
        raise LookupError("trusted artifact label is empty")
    for artifact in load_trusted_artifacts(raw):
        if artifact.label != normalized_label:
            continue
        if require_enabled and not artifact.enabled:
            raise LookupError(f"trusted artifact {normalized_label!r} is disabled")
        return artifact
    raise LookupError(f"trusted artifact {normalized_label!r} was not found")
