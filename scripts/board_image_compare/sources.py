"""Source definitions and conservative historical USRP migration planning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


@dataclass(frozen=True)
class ReconstructionSource:
    id: str
    label: str
    remote_root: str
    include_prefixes: tuple[str, ...] = ()
    exclude_prefixes: tuple[str, ...] = ()

    def accepts(self, job_name: str) -> bool:
        name = job_name.casefold()
        included = not self.include_prefixes or any(
            name.startswith(prefix.casefold()) for prefix in self.include_prefixes
        )
        excluded = any(name.startswith(prefix.casefold()) for prefix in self.exclude_prefixes)
        return included and not excluded


def default_reconstruction_sources(usrp_root: str) -> dict[str, ReconstructionSource]:
    prerecorded_root = "/home/user/Downloads/jscc-test/jscc"
    usrp_root_path = PurePosixPath(usrp_root)
    return {
        "prerecorded-pytorch": ReconstructionSource(
            "prerecorded-pytorch",
            "预录 PyTorch",
            f"{prerecorded_root}/infer_outputs",
            include_prefixes=("pytorch_reference_reconstruction_",),
        ),
        "prerecorded-tvm": ReconstructionSource(
            "prerecorded-tvm",
            "预录 TVM",
            f"{prerecorded_root}/infer_outputs",
            exclude_prefixes=("pytorch_reference_reconstruction_",),
        ),
        "prerecorded-mnn": ReconstructionSource(
            "prerecorded-mnn",
            "预录 MNN",
            f"{prerecorded_root}/mnn_benchmark_outputs",
        ),
        "usrp-qpsk": ReconstructionSource(
            "usrp-qpsk",
            "USRP QPSK",
            str(usrp_root_path / "qpsk" / "tvm"),
        ),
        "usrp-iq-direct": ReconstructionSource(
            "usrp-iq-direct",
            "USRP IQ直传",
            str(usrp_root_path / "iq-direct" / "tvm"),
        ),
    }


def _has_nonempty_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _contains_key_with_value(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        if any(key in keys and _has_nonempty_value(candidate) for key, candidate in value.items()):
            return True
        return any(_contains_key_with_value(candidate, keys) for candidate in value.values())
    if isinstance(value, list):
        return any(_contains_key_with_value(candidate, keys) for candidate in value)
    return False


def classify_usrp_summary(payload: dict[str, Any]) -> str | None:
    """Classify a summary only when it contains unambiguous link evidence."""
    if not isinstance(payload, dict):
        return None

    phy = str(payload.get("phy") or "").strip().casefold()
    if phy == "analog-latent-iq":
        return "usrp-iq-direct"
    if _contains_key_with_value(payload, {"remote_received_latent_npz", "remote_received_latent_npz_files"}):
        return "usrp-iq-direct"

    if any(
        _has_nonempty_value(payload.get(key))
        for key in ("max_arq_rounds", "chunk_bytes", "cpp_sync_mode")
    ):
        return "usrp-qpsk"
    return None


_USRP_JOB_RE = re.compile(r"^openamp3_usrp_(?P<token>.+)_current$")


def extract_usrp_token(job_name: str) -> str | None:
    match = _USRP_JOB_RE.fullmatch(str(job_name).strip())
    return match.group("token") if match else None


def _base_usrp_job(job_name: str) -> str:
    token = extract_usrp_token(job_name)
    if token is None:
        return job_name
    base_token = re.sub(r"_(?:recovery|retry)$", "", token, flags=re.IGNORECASE)
    return f"openamp3_usrp_{base_token}_current"


def _summary_candidates(job_name: str, run_root: Path, legacy_root: Path) -> list[Path]:
    token = extract_usrp_token(job_name)
    exact_names = [job_name]
    base_names = [_base_usrp_job(job_name)]
    if token is not None:
        base_token = re.sub(r"_(?:recovery|retry)$", "", token, flags=re.IGNORECASE)
        exact_names.append(f"cockpit_usrp_usrp-{token}")
        base_names.append(f"cockpit_usrp_usrp-{base_token}")
    candidates: list[Path] = []
    for names in (exact_names, base_names):
        for root in (run_root, legacy_root):
            for name in names:
                candidate = root / name
                if candidate not in candidates:
                    candidates.append(candidate)
    return candidates


def _path_key(value: str | Path) -> str:
    return str(value).replace("\\", "/").rstrip("/").casefold()


def _planned_destination(output_root: Path, layout_name: str, job_name: str) -> str:
    return str(output_root / layout_name / "tvm" / job_name)


def _destination_keys(destination: str) -> set[str]:
    keys = {_path_key(destination)}
    keys.add(_path_key(PurePosixPath(destination)))
    return keys


def _existing_destination_keys(existing_destinations: Iterable[str | Path]) -> set[str]:
    keys: set[str] = set()
    for destination in existing_destinations:
        keys.update(_destination_keys(str(destination)))
    return keys


def _read_summary(candidates: Iterable[Path]) -> tuple[Path | None, dict[str, Any] | None]:
    for candidate in candidates:
        summary_path = candidate / "batch_spool_summary.json"
        if not summary_path.is_file():
            continue
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            return candidate, payload
    return None, None


def plan_usrp_migration(
    job_names: Iterable[str],
    run_root: str | Path,
    legacy_root: str | Path,
    output_root: str | Path,
    *,
    existing_destinations: Iterable[str | Path] = (),
) -> list[dict[str, str | None]]:
    """Return auditable migration decisions without copying or overwriting data."""
    run_path = Path(run_root)
    legacy_path = Path(legacy_root)
    output_path = Path(output_root)
    existing_keys = _existing_destination_keys(existing_destinations)
    decisions: list[dict[str, str | None]] = []

    for job_name in job_names:
        name = str(job_name)
        source_path, payload = _read_summary(_summary_candidates(name, run_path, legacy_path))
        source = str(source_path or run_path / name)
        mode = classify_usrp_summary(payload) if payload is not None else None
        destination = None
        if mode is not None:
            layout_name = "iq-direct" if mode == "usrp-iq-direct" else "qpsk"
            planned_destination = _planned_destination(output_path, layout_name, name)
            if _destination_keys(planned_destination) & existing_keys:
                reason = "destination already exists"
            else:
                destination = planned_destination
                reason = "classified from batch_spool_summary.json"
        elif payload is None:
            reason = "batch_spool_summary.json not found"
        else:
            reason = "batch_spool_summary.json has no classifiable link evidence"
        decisions.append(
            {
                "source": source,
                "destination": destination,
                "mode": mode,
                "reason": reason,
            }
        )
    return decisions
