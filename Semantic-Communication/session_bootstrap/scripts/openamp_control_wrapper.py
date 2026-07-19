#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from openamp_trusted_artifacts import (  # noqa: E402
    DEFAULT_TRUSTED_ARTIFACTS_PATH,
    find_trusted_artifact,
    normalize_sha256,
    resolve_trusted_artifacts_path,
)
from openamp_signed_manifest import (  # noqa: E402
    build_signed_admission_transport_plan,
    load_signed_manifest_bundle,
    signed_manifest_summary,
    verify_signed_manifest_bundle,
)

SIGNED_ADMISSION_KEY_SLOT = 1
LINK_HEALTH_PROFILES = {
    "none": None,
    "normal": {
        "snr_est_db_x100": 1200,
        "per_x1000": 1,
        "burst_loss_max": 0,
        "rx_locked": 1,
        "effective_throughput_kbps": 50000,
    },
    "recover": {
        "snr_est_db_x100": 1200,
        "per_x1000": 1,
        "burst_loss_max": 0,
        "rx_locked": 1,
        "effective_throughput_kbps": 50000,
    },
    "jitter": {
        "snr_est_db_x100": 900,
        "per_x1000": 25,
        "burst_loss_max": 2,
        "rx_locked": 1,
        "effective_throughput_kbps": 28000,
    },
    "lossy": {
        "snr_est_db_x100": 400,
        "per_x1000": 120,
        "burst_loss_max": 5,
        "rx_locked": 1,
        "effective_throughput_kbps": 9000,
    },
    "flaky": {
        "snr_est_db_x100": 100,
        "per_x1000": 350,
        "burst_loss_max": 12,
        "rx_locked": 0,
        "effective_throughput_kbps": 0,
    },
}

BASH_ENV_KEYS = ("OPENAMP_BASH", "GIT_BASH", "BASH")


def _is_windows_wsl_bash(path: str) -> bool:
    text = str(path or "").replace("/", "\\").lower()
    return text.endswith("\\windows\\system32\\bash.exe") or "\\appdata\\local\\microsoft\\windowsapps\\bash.exe" in text


def _git_bash_candidates_from_exec_path(git_exe: str) -> list[Path]:
    try:
        proc = subprocess.run(
            [git_exe, "--exec-path"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode != 0:
        return []
    raw = proc.stdout.strip()
    if not raw:
        return []
    exec_path = Path(raw).resolve()
    candidates: list[Path] = []
    for root in (exec_path, *exec_path.parents):
        candidates.extend(
            [
                root / "usr" / "bin" / "bash.exe",
                root / "bin" / "bash.exe",
            ]
        )
    return candidates


def resolve_bash_executable() -> str:
    for key in BASH_ENV_KEYS:
        raw = str(os.environ.get(key, "") or "").strip()
        if raw and Path(raw).is_file() and not _is_windows_wsl_bash(raw):
            return raw

    if os.name == "nt":
        git_exe = shutil.which("git")
        if git_exe:
            for candidate in _git_bash_candidates_from_exec_path(git_exe):
                if candidate.is_file():
                    return str(candidate)
            git_root = Path(git_exe).resolve().parents[1]
            for candidate in (
                git_root / "usr" / "bin" / "bash.exe",
                git_root / "bin" / "bash.exe",
            ):
                if candidate.is_file():
                    return str(candidate)
        for raw in (
            r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files\Git\bin\bash.exe",
        ):
            candidate = Path(raw)
            if candidate.is_file():
                return str(candidate)

    bash = shutil.which("bash")
    if bash and not (os.name == "nt" and _is_windows_wsl_bash(bash)):
        return bash
    return "bash"


def terminate_process(process: subprocess.Popen[Any]) -> int:
    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        time.sleep(1.0)
        if process.poll() is None:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        return int(process.wait(timeout=5))
    process.terminate()
    time.sleep(1.0)
    if process.poll() is None:
        process.kill()
    return int(process.wait(timeout=5))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Wrap an existing trusted-artifact runner with control-plane events. "
            "This wrapper never rewrites the inference data path."
        )
    )
    parser.add_argument("--runner-cmd", required=True, help="Existing benchmark or reconstruction command.")
    parser.add_argument("--output-dir", required=True, help="Where manifest/log/control traces should be written.")
    parser.add_argument("--job-id", type=int, default=int(time.time()), help="Control-plane job identifier.")
    parser.add_argument("--variant", default="current", help="Human-readable variant tag.")
    parser.add_argument(
        "--expected-sha256",
        default="",
        help="Trusted artifact SHA. Direct SHA input stays supported for compatibility.",
    )
    parser.add_argument(
        "--trusted-artifact-label",
        default="",
        help="Select a trusted artifact allowlist entry such as baseline or current.",
    )
    parser.add_argument(
        "--trusted-artifacts-file",
        default=str(DEFAULT_TRUSTED_ARTIFACTS_PATH),
        help="JSON allowlist used by --trusted-artifact-label and variant-based resolution.",
    )
    parser.add_argument(
        "--admission-mode",
        choices=("legacy_sha", "signed_manifest_v1"),
        default="legacy_sha",
        help="legacy_sha keeps the current SHA path; signed_manifest_v1 enables the draft signed-manifest flow.",
    )
    parser.add_argument(
        "--signed-manifest-file",
        default="",
        help="Signed manifest bundle JSON used when --admission-mode signed_manifest_v1 is selected.",
    )
    parser.add_argument(
        "--signed-manifest-public-key",
        default="",
        help="Optional PEM public key used to verify --signed-manifest-file locally before emission.",
    )
    parser.add_argument("--deadline-ms", type=int, default=300000, help="Control-plane deadline metadata.")
    parser.add_argument("--expected-outputs", type=int, default=300, help="Expected output count metadata.")
    parser.add_argument("--job-flags", default="reconstruction", help="Payload or reconstruction marker.")
    parser.add_argument(
        "--heartbeat-interval-sec",
        type=float,
        default=5.0,
        help="Heartbeat cadence while the runner is active.",
    )
    parser.add_argument(
        "--runner-timeout-sec",
        type=float,
        default=0.0,
        help="Kill the wrapped runner after this many seconds; 0 disables the timeout.",
    )
    parser.add_argument(
        "--transport",
        choices=("none", "hook"),
        default="none",
        help="none=only emit local traces; hook=invoke an external control hook for each phase.",
    )
    parser.add_argument(
        "--control-hook-cmd",
        default="",
        help=(
            "When --transport hook is used, this shell command is invoked for each control event. "
            "The event JSON is passed on stdin; OPENAMP_PHASE is set in the environment."
        ),
    )
    parser.add_argument(
        "--control-hook-timeout-sec",
        type=float,
        default=5.0,
        help="Timeout for each external hook invocation.",
    )
    parser.add_argument(
        "--link-health-profile",
        default=os.environ.get("OPENAMP_LINK_HEALTH_PROFILE", "none"),
        help=(
            "Optional board-firmware LINK_HEALTH profile. Values: none, normal, jitter, lossy, flaky, recover. "
            "This only emits control-plane telemetry and does not rewrite the inference data path."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit control traces and manifest without executing the wrapped runner.",
    )
    return parser.parse_args()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def resolve_output_dir(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jsonl_append(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as outfile:
        outfile.write(json.dumps(payload, ensure_ascii=False) + "\n")


def parse_response(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def normalize_decision(response: dict[str, Any] | None) -> str | None:
    if not response:
        return None
    if "decision" in response:
        value = response["decision"]
    elif "allow" in response:
        value = "ALLOW" if response["allow"] else "DENY"
    else:
        return None
    if isinstance(value, bool):
        return "ALLOW" if value else "DENY"
    text = str(value).strip().upper()
    if text in {"1", "ALLOW", "ALLOWED", "TRUE"}:
        return "ALLOW"
    if text in {"0", "DENY", "DENIED", "FALSE"}:
        return "DENY"
    return text or None


def hook_response_payload(hook_result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(hook_result, dict):
        return {}
    response = hook_result.get("response")
    return response if isinstance(response, dict) else {}


def status_req_allows_progress(*, transport: str, status_response: dict[str, Any] | None) -> bool:
    if transport != "hook":
        return True
    response = hook_response_payload(status_response)
    return str(response.get("transport_status") or "").strip().lower() == "status_resp_received"


def signed_admission_allows_progress(*, transport: str, hook_result: dict[str, Any] | None) -> bool:
    if transport != "hook":
        return True
    response = hook_response_payload(hook_result)
    return bool(response.get("acknowledged"))


def build_denied_summary(
    *,
    blocked_phase: str,
    status_response: dict[str, Any],
    signed_admission_responses: list[dict[str, Any]],
    job_req_response: dict[str, Any],
    control_job_id: int,
    runner_log_path: Path,
    manifest_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    return {
        "finished_at": now_iso(),
        "job_id": control_job_id,
        "result": "denied_by_control_hook",
        "blocked_phase": blocked_phase,
        "status_response": status_response,
        "signed_admission_responses": signed_admission_responses,
        "job_req_response": job_req_response,
        "runner_exit_code": None,
        "runner_log": str(runner_log_path),
        "manifest_path": str(manifest_path),
        "control_trace_path": str(trace_path),
    }


def build_job_ack_payload(
    *,
    job_id: int,
    transport: str,
    decision: str | None,
    response: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": job_id,
        "decision": "ALLOW" if transport != "hook" else ("ALLOW" if decision == "ALLOW" else "DENY"),
    }
    if isinstance(response, dict):
        for key in (
            "source",
            "fault_code",
            "fault_name",
            "guard_state",
            "guard_state_name",
            "transport_status",
            "protocol_semantics",
            "note",
        ):
            if key in response:
                payload[key] = response[key]
    if transport == "hook" and decision != "ALLOW" and "note" not in payload:
        payload["note"] = "control hook did not return an explicit ALLOW"
    return payload


def build_hook_timeout_response(*, phase: str, timeout_sec: float) -> dict[str, Any]:
    return {
        "phase": phase,
        "source": "openamp_control_wrapper",
        "transport_status": "hook_timeout",
        "protocol_semantics": "not_verified",
        "note": f"{phase} control hook timed out after {timeout_sec:.1f}s.",
    }


def normalize_link_health_profile(raw: str) -> str:
    profile = str(raw or "none").strip().lower()
    return profile if profile in LINK_HEALTH_PROFILES else "none"


def build_link_health_payload(*, job_id: int, profile: str, elapsed_ms: int, window_id: int) -> dict[str, Any] | None:
    metrics = LINK_HEALTH_PROFILES.get(profile)
    if metrics is None:
        return None
    return {
        "job_id": job_id,
        "profile": profile,
        "snr_est_db_x100": metrics["snr_est_db_x100"],
        "per_x1000": metrics["per_x1000"],
        "burst_loss_max": metrics["burst_loss_max"],
        "rx_locked": metrics["rx_locked"],
        "effective_throughput_kbps": metrics["effective_throughput_kbps"],
        "window_id": window_id,
        "timestamp_ms": elapsed_ms & 0xFFFFFFFF,
    }


def mode_ack_payload_from_directive(*, job_id: int, response: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(response, dict):
        return None
    if response.get("transport_status") != "mode_directive_received":
        return None
    applied_mode = response.get("applied_mode_name") or response.get("applied_mode")
    if applied_mode in (None, ""):
        return None
    return {
        "job_id": job_id,
        "applied_mode": applied_mode,
        "ack_status": 0,
    }


def emit_event(
    *,
    trace_path: Path,
    phase: str,
    payload: dict[str, Any],
    transport: str,
    hook_cmd: str,
    hook_timeout_sec: float,
) -> dict[str, Any]:
    event = {
        "at": now_iso(),
        "phase": phase,
        "payload": payload,
    }
    hook_result: dict[str, Any] | None = None
    if transport == "hook":
        env = os.environ.copy()
        env["OPENAMP_PHASE"] = phase
        env["OPENAMP_JOB_ID"] = str(payload.get("job_id", ""))
        hook_started = time.monotonic()
        try:
            result = subprocess.run(
                [resolve_bash_executable(), "-lc", hook_cmd],
                check=False,
                input=json.dumps(event, ensure_ascii=False),
                text=True,
                capture_output=True,
                cwd=PROJECT_ROOT,
                env=env,
                timeout=hook_timeout_sec,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = str(exc.stdout or exc.output or "")
            stderr = str(exc.stderr or "")
            hook_result = {
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr,
                "response": parse_response(stdout) or build_hook_timeout_response(phase=phase, timeout_sec=hook_timeout_sec),
                "timed_out": True,
                "timeout_sec": hook_timeout_sec,
                "duration_ms": int((time.monotonic() - hook_started) * 1000),
            }
        except Exception as exc:
            hook_result = {
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "response": {
                    "phase": phase,
                    "source": "openamp_control_wrapper",
                    "transport_status": "hook_error",
                    "protocol_semantics": "not_verified",
                    "note": f"{phase} control hook raised {exc.__class__.__name__}: {exc}",
                },
                "timed_out": False,
                "timeout_sec": hook_timeout_sec,
                "duration_ms": int((time.monotonic() - hook_started) * 1000),
            }
        else:
            hook_result = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "response": parse_response(result.stdout),
                "timed_out": False,
                "timeout_sec": hook_timeout_sec,
                "duration_ms": int((time.monotonic() - hook_started) * 1000),
            }
        event["hook_result"] = hook_result
    jsonl_append(trace_path, event)
    return hook_result or {}


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    process.kill()
    process.wait(timeout=5)


def build_manifest(
    args: argparse.Namespace,
    output_dir: Path,
    expected_sha256: str,
    *,
    variant: str,
    deadline_ms: int,
    expected_outputs: int,
    job_flags: str,
    signed_admission: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "created_at": now_iso(),
        "job_id": args.job_id,
        "variant": variant,
        "job_flags": job_flags,
        "runner_cmd": args.runner_cmd,
        "runner_cmd_shell_quoted": shlex.join([resolve_bash_executable(), "-lc", args.runner_cmd]),
        "expected_sha256": expected_sha256,
        "expected_outputs": expected_outputs,
        "deadline_ms": deadline_ms,
        "heartbeat_interval_sec": args.heartbeat_interval_sec,
        "runner_timeout_sec": args.runner_timeout_sec,
        "transport": args.transport,
        "control_hook_cmd": args.control_hook_cmd,
        "dry_run": args.dry_run,
        "link_health_profile": normalize_link_health_profile(args.link_health_profile),
        "admission_mode": "signed_manifest_v1" if signed_admission is not None else "legacy_sha",
        "output_dir": str(output_dir),
        "boundary_note": "control plane only; the wrapped runner remains the existing inference data path",
        "protocol_status": "draft_only" if signed_admission is not None else "current",
    }


def build_status_req_payload(
    *,
    job_id: int,
    variant: str,
    expected_sha256: str,
    job_flags: str,
    trusted_artifact: dict[str, Any] | None,
    signed_admission: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "job_id": job_id,
        "variant": variant,
        "expected_sha256": expected_sha256,
        "job_flags": job_flags,
    }
    if trusted_artifact is not None:
        payload["trusted_artifact_label"] = trusted_artifact["label"]
    if signed_admission is not None:
        payload["admission_mode"] = signed_admission["admission_mode"]
        payload["signed_manifest"] = build_signed_manifest_hook_payload(signed_admission)
    return payload


def build_job_req_payload(
    *,
    job_id: int,
    expected_sha256: str,
    deadline_ms: int,
    expected_outputs: int,
    job_flags: str,
    runner_cmd: str,
    trusted_artifact: dict[str, Any] | None,
    signed_admission: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "job_id": job_id,
        "expected_sha256": expected_sha256,
        "deadline_ms": deadline_ms,
        "expected_outputs": expected_outputs,
        "job_flags": job_flags,
        "runner_cmd": runner_cmd,
    }
    if trusted_artifact is not None:
        payload["trusted_artifact_label"] = trusted_artifact["label"]
    if signed_admission is not None:
        payload["admission_mode"] = signed_admission["admission_mode"]
        payload["signed_manifest"] = build_signed_manifest_hook_payload(signed_admission)
    return payload


def build_signed_manifest_hook_payload(signed_admission: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_schema": signed_admission["bundle_schema"],
        "bundle_version": signed_admission["bundle_version"],
        "manifest_schema": signed_admission["manifest_schema"],
        "manifest_version": signed_admission["manifest_version"],
        "manifest_sha256": signed_admission["manifest_sha256"],
        "artifact_sha256": signed_admission["artifact_sha256"],
        "artifact_size_bytes": signed_admission["artifact_size_bytes"],
        "signature_algorithm": signed_admission["signature_algorithm"],
        "key_id": signed_admission["key_id"],
        "protocol_status": signed_admission["protocol_status"],
    }


def build_signed_admission_frame_payload(
    *,
    job_id: int,
    signed_admission: dict[str, Any],
    frame: dict[str, Any],
    trusted_artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "job_id": job_id,
        "admission_mode": signed_admission["admission_mode"],
        "signed_manifest": build_signed_manifest_hook_payload(signed_admission),
        "tx_frame_hex": str(frame["frame_hex"]),
        "signed_admission_frame": {
            "phase": str(frame["phase"]),
            "seq": int(frame["seq"]),
            "msg_type": int(frame["msg_type"]),
            "payload_len": int(frame["payload_len"]),
            "payload": dict(frame["payload"]),
        },
    }
    if trusted_artifact is not None:
        payload["trusted_artifact_label"] = trusted_artifact["label"]
    return payload


def build_signed_admission_plan(
    *,
    job_id: int,
    signed_admission: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if signed_admission is None:
        return None
    bundle_path = Path(str(signed_admission["bundle_path"]))
    bundle = load_signed_manifest_bundle(bundle_path)
    return build_signed_admission_transport_plan(
        bundle,
        job_id=job_id,
        key_slot=SIGNED_ADMISSION_KEY_SLOT,
        seq_start=1,
    )


def resolve_expected_sha256(args: argparse.Namespace) -> tuple[str, dict[str, Any] | None, str]:
    raw_expected_sha256 = ""
    if args.expected_sha256:
        raw_expected_sha256 = normalize_sha256(args.expected_sha256, field_name="--expected-sha256")

    artifacts_file = resolve_trusted_artifacts_path(args.trusted_artifacts_file)
    explicit_label = str(args.trusted_artifact_label or "").strip().lower()
    env_label = str(os.environ.get("OPENAMP_TRUSTED_ARTIFACT_LABEL") or "").strip().lower()
    variant_label = str(args.variant or "").strip().lower()

    label_candidates: list[tuple[str, str]] = []
    if explicit_label:
        label_candidates.append(("--trusted-artifact-label", explicit_label))
    elif not raw_expected_sha256 and env_label:
        label_candidates.append(("OPENAMP_TRUSTED_ARTIFACT_LABEL", env_label))
    elif not raw_expected_sha256 and variant_label:
        label_candidates.append(("--variant", variant_label))

    for source_name, label in label_candidates:
        try:
            trusted_artifact = find_trusted_artifact(label, raw=artifacts_file)
        except LookupError:
            if source_name == "--variant":
                continue
            raise SystemExit(f"ERROR: trusted artifact label {label!r} was not found or is disabled.")
        if raw_expected_sha256 and raw_expected_sha256 != trusted_artifact.sha256:
            raise SystemExit(
                "ERROR: --expected-sha256 does not match the selected trusted artifact "
                f"{trusted_artifact.label!r}."
            )
        return trusted_artifact.sha256, trusted_artifact.to_json(), source_name

    if raw_expected_sha256:
        return raw_expected_sha256, None, "--expected-sha256"

    env_expected_sha256 = str(os.environ.get("INFERENCE_CURRENT_EXPECTED_SHA256") or "").strip()
    if env_expected_sha256:
        return normalize_sha256(env_expected_sha256, field_name="INFERENCE_CURRENT_EXPECTED_SHA256"), None, (
            "INFERENCE_CURRENT_EXPECTED_SHA256"
        )

    return "", None, "unset"


def resolve_admission_context(args: argparse.Namespace) -> tuple[str, dict[str, Any] | None, str, dict[str, Any] | None]:
    expected_sha256, trusted_artifact, expected_sha256_source = resolve_expected_sha256(args)
    admission_mode = str(getattr(args, "admission_mode", "legacy_sha") or "legacy_sha").strip().lower()
    if admission_mode == "legacy_sha":
        return expected_sha256, trusted_artifact, expected_sha256_source, None
    if admission_mode != "signed_manifest_v1":
        raise SystemExit(f"ERROR: unsupported --admission-mode value {admission_mode!r}.")

    signed_manifest_file = str(getattr(args, "signed_manifest_file", "") or "").strip()
    if not signed_manifest_file:
        raise SystemExit("ERROR: --signed-manifest-file is required when --admission-mode signed_manifest_v1 is used.")

    bundle_path = Path(signed_manifest_file)
    if not bundle_path.is_absolute():
        bundle_path = PROJECT_ROOT / bundle_path
    bundle = load_signed_manifest_bundle(bundle_path)
    artifact_verification_path: Path | None = None
    artifact_path = Path(str(bundle["manifest"]["artifact"]["path"]))
    if not artifact_path.is_absolute():
        artifact_path = PROJECT_ROOT / artifact_path
    if artifact_path.exists():
        artifact_verification_path = artifact_path

    public_key = str(getattr(args, "signed_manifest_public_key", "") or "").strip()
    if public_key:
        verify_kwargs: dict[str, Any] = {}
        if artifact_verification_path is not None:
            verify_kwargs["artifact_path"] = artifact_verification_path
        summary = verify_signed_manifest_bundle(bundle, public_key=public_key, **verify_kwargs)
        summary["bundle_path"] = str(bundle_path)
    else:
        summary = signed_manifest_summary(
            bundle,
            bundle_path=bundle_path,
            verified=False,
            artifact_match=None,
            verification_public_key=None,
        )

    manifest_expected_sha256 = str(bundle["manifest"]["artifact"]["sha256"])
    if expected_sha256 and expected_sha256 != manifest_expected_sha256:
        raise SystemExit("ERROR: --expected-sha256 / trusted-artifact resolution does not match --signed-manifest-file.")

    return manifest_expected_sha256, trusted_artifact, "--signed-manifest-file", summary


def get_effective_variant(args: argparse.Namespace, signed_admission: dict[str, Any] | None) -> str:
    if signed_admission is not None:
        return str(signed_admission["variant"])
    return str(args.variant)


def get_effective_deadline_ms(args: argparse.Namespace, signed_admission: dict[str, Any] | None) -> int:
    if signed_admission is not None:
        return int(signed_admission["deadline_ms"])
    return int(args.deadline_ms)


def get_effective_expected_outputs(args: argparse.Namespace, signed_admission: dict[str, Any] | None) -> int:
    if signed_admission is not None:
        return int(signed_admission["expected_outputs"])
    return int(args.expected_outputs)


def get_effective_job_flags(args: argparse.Namespace, signed_admission: dict[str, Any] | None) -> str:
    if signed_admission is not None:
        return str(signed_admission["job_flags"])
    return str(args.job_flags)


def build_job_done_payload(
    *,
    job_id: int,
    elapsed_ms: int,
    return_code: int | None,
    timed_out: bool,
    expected_outputs: int,
) -> dict[str, Any]:
    succeeded = (return_code or 0) == 0 and not timed_out
    return {
        "job_id": job_id,
        "elapsed_ms": elapsed_ms,
        "result_code": 0 if succeeded else 1,
        "output_count": expected_outputs if succeeded else 0,
        "runner_exit_code": return_code,
        "timed_out": timed_out,
    }


def main() -> int:
    args = parse_args()
    if args.transport == "hook" and not args.control_hook_cmd:
        raise SystemExit("ERROR: --control-hook-cmd is required when --transport hook is used.")
    if args.heartbeat_interval_sec <= 0:
        raise SystemExit("ERROR: --heartbeat-interval-sec must be > 0.")
    if args.control_hook_timeout_sec <= 0:
        raise SystemExit("ERROR: --control-hook-timeout-sec must be > 0.")
    if args.deadline_ms <= 0:
        raise SystemExit("ERROR: --deadline-ms must be > 0.")
    args.link_health_profile = normalize_link_health_profile(getattr(args, "link_health_profile", "none"))

    output_dir = resolve_output_dir(args.output_dir)
    trace_path = output_dir / "control_trace.jsonl"
    summary_path = output_dir / "wrapper_summary.json"
    manifest_path = output_dir / "job_manifest.json"
    runner_log_path = output_dir / "runner.log"

    expected_sha256, trusted_artifact, expected_sha256_source, signed_admission = resolve_admission_context(args)
    variant = get_effective_variant(args, signed_admission)
    deadline_ms = get_effective_deadline_ms(args, signed_admission)
    expected_outputs = get_effective_expected_outputs(args, signed_admission)
    job_flags = get_effective_job_flags(args, signed_admission)

    manifest = build_manifest(
        args,
        output_dir,
        expected_sha256,
        variant=variant,
        deadline_ms=deadline_ms,
        expected_outputs=expected_outputs,
        job_flags=job_flags,
        signed_admission=signed_admission,
    )
    manifest["expected_sha256_source"] = expected_sha256_source
    manifest["trusted_artifacts_file"] = str(resolve_trusted_artifacts_path(args.trusted_artifacts_file))
    if trusted_artifact is not None:
        manifest["trusted_artifact"] = trusted_artifact
    if signed_admission is not None:
        manifest["signed_manifest"] = signed_admission
    json_dump(manifest_path, manifest)

    control_job_id = args.job_id
    signed_admission_plan = build_signed_admission_plan(
        job_id=control_job_id,
        signed_admission=signed_admission,
    )
    status_req_payload = build_status_req_payload(
        job_id=control_job_id,
        variant=variant,
        expected_sha256=expected_sha256,
        job_flags=job_flags,
        trusted_artifact=trusted_artifact,
        signed_admission=signed_admission,
    )
    status_response = emit_event(
        trace_path=trace_path,
        phase="STATUS_REQ",
        payload=status_req_payload,
        transport=args.transport,
        hook_cmd=args.control_hook_cmd,
        hook_timeout_sec=args.control_hook_timeout_sec,
    )
    if not status_req_allows_progress(transport=args.transport, status_response=status_response):
        summary = build_denied_summary(
            blocked_phase="STATUS_REQ",
            status_response=status_response,
            signed_admission_responses=[],
            job_req_response={},
            control_job_id=control_job_id,
            runner_log_path=runner_log_path,
            manifest_path=manifest_path,
            trace_path=trace_path,
        )
        json_dump(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 2

    signed_admission_responses: list[dict[str, Any]] = []
    final_job_req_transport_frame: dict[str, Any] | None = None
    if signed_admission_plan is not None:
        frames = list(signed_admission_plan.get("frames", []))
        if not frames:
            raise SystemExit("ERROR: signed admission transport plan did not emit any frames.")
        for frame in frames:
            phase = str(frame.get("phase") or "").strip().upper()
            if phase == "JOB_REQ":
                final_job_req_transport_frame = frame
                continue
            signed_response = emit_event(
                trace_path=trace_path,
                phase=phase,
                payload=build_signed_admission_frame_payload(
                    job_id=control_job_id,
                    signed_admission=signed_admission,
                    frame=frame,
                    trusted_artifact=trusted_artifact,
                ),
                transport=args.transport,
                hook_cmd=args.control_hook_cmd,
                hook_timeout_sec=args.control_hook_timeout_sec,
            )
            signed_admission_responses.append(signed_response)
            if not signed_admission_allows_progress(transport=args.transport, hook_result=signed_response):
                summary = build_denied_summary(
                    blocked_phase=phase,
                    status_response=status_response,
                    signed_admission_responses=signed_admission_responses,
                    job_req_response={},
                    control_job_id=control_job_id,
                    runner_log_path=runner_log_path,
                    manifest_path=manifest_path,
                    trace_path=trace_path,
                )
                json_dump(summary_path, summary)
                print(json.dumps(summary, ensure_ascii=False))
                return 2

    job_req_payload = build_job_req_payload(
        job_id=control_job_id,
        expected_sha256=expected_sha256,
        deadline_ms=deadline_ms,
        expected_outputs=expected_outputs,
        job_flags=job_flags,
        runner_cmd=args.runner_cmd,
        trusted_artifact=trusted_artifact,
        signed_admission=signed_admission,
    )
    if final_job_req_transport_frame is not None:
        job_req_payload["tx_frame_hex"] = str(final_job_req_transport_frame["frame_hex"])
        job_req_payload["signed_admission_frame"] = {
            "phase": str(final_job_req_transport_frame["phase"]),
            "seq": int(final_job_req_transport_frame["seq"]),
            "msg_type": int(final_job_req_transport_frame["msg_type"]),
            "payload_len": int(final_job_req_transport_frame["payload_len"]),
            "payload": dict(final_job_req_transport_frame["payload"]),
        }
    job_req_response = emit_event(
        trace_path=trace_path,
        phase="JOB_REQ",
        payload=job_req_payload,
        transport=args.transport,
        hook_cmd=args.control_hook_cmd,
        hook_timeout_sec=args.control_hook_timeout_sec,
    )
    hook_response = job_req_response.get("response") if job_req_response else None
    decision = normalize_decision(hook_response)
    job_ack_payload = build_job_ack_payload(
        job_id=control_job_id,
        transport=args.transport,
        decision=decision,
        response=hook_response,
    )

    if args.transport == "hook" and decision != "ALLOW":
        summary = build_denied_summary(
            blocked_phase="JOB_REQ",
            status_response=status_response,
            signed_admission_responses=signed_admission_responses,
            job_req_response=job_req_response,
            control_job_id=control_job_id,
            runner_log_path=runner_log_path,
            manifest_path=manifest_path,
            trace_path=trace_path,
        )
        json_dump(summary_path, summary)
        emit_event(
            trace_path=trace_path,
            phase="JOB_ACK",
            payload=job_ack_payload,
            transport="none",
            hook_cmd="",
            hook_timeout_sec=args.control_hook_timeout_sec,
        )
        print(json.dumps(summary, ensure_ascii=False))
        return 2

    emit_event(
        trace_path=trace_path,
        phase="JOB_ACK",
        payload=job_ack_payload,
        transport="none",
        hook_cmd="",
        hook_timeout_sec=args.control_hook_timeout_sec,
    )

    if args.dry_run:
        summary = {
            "finished_at": now_iso(),
            "job_id": control_job_id,
            "result": "dry_run_only",
            "status_response": status_response,
            "signed_admission_responses": signed_admission_responses,
            "job_req_response": job_req_response,
            "runner_exit_code": None,
            "runner_log": str(runner_log_path),
            "manifest_path": str(manifest_path),
            "control_trace_path": str(trace_path),
        }
        json_dump(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    start_time = time.monotonic()
    return_code = None
    timed_out = False

    with runner_log_path.open("w", encoding="utf-8") as logfile:
        logfile.write(f"[{now_iso()}] openamp wrapper start\n")
        logfile.write(f"runner_cmd={args.runner_cmd}\n")
        logfile.flush()
        process = subprocess.Popen(
            [resolve_bash_executable(), "-lc", args.runner_cmd],
            cwd=PROJECT_ROOT,
            stdout=logfile,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )
        try:
            last_heartbeat = start_time
            link_health_window_id = 0
            while True:
                return_code = process.poll()
                elapsed = time.monotonic() - start_time
                if return_code is not None:
                    break
                if args.runner_timeout_sec > 0 and elapsed > args.runner_timeout_sec:
                    timed_out = True
                    return_code = terminate_process(process)
                    break
                if time.monotonic() - last_heartbeat >= args.heartbeat_interval_sec:
                    emit_event(
                        trace_path=trace_path,
                        phase="HEARTBEAT",
                        payload={
                            "job_id": control_job_id,
                            "elapsed_ms": int(elapsed * 1000),
                            "runtime_state": "RUNNING",
                        },
                        transport=args.transport,
                        hook_cmd=args.control_hook_cmd,
                        hook_timeout_sec=args.control_hook_timeout_sec,
                    )
                    link_health_payload = build_link_health_payload(
                        job_id=control_job_id,
                        profile=args.link_health_profile,
                        elapsed_ms=int(elapsed * 1000),
                        window_id=link_health_window_id,
                    )
                    if link_health_payload is not None:
                        link_result = emit_event(
                            trace_path=trace_path,
                            phase="LINK_HEALTH",
                            payload=link_health_payload,
                            transport=args.transport,
                            hook_cmd=args.control_hook_cmd,
                            hook_timeout_sec=args.control_hook_timeout_sec,
                        )
                        link_health_window_id += 1
                        mode_ack_payload = mode_ack_payload_from_directive(
                            job_id=control_job_id,
                            response=hook_response_payload(link_result),
                        )
                        if mode_ack_payload is not None:
                            emit_event(
                                trace_path=trace_path,
                                phase="MODE_ACK",
                                payload=mode_ack_payload,
                                transport=args.transport,
                                hook_cmd=args.control_hook_cmd,
                                hook_timeout_sec=args.control_hook_timeout_sec,
                            )
                    last_heartbeat = time.monotonic()
                time.sleep(0.2)
        except KeyboardInterrupt:
            timed_out = True
            terminate_process(process)
            return_code = process.returncode
            emit_event(
                trace_path=trace_path,
                phase="SAFE_STOP",
                payload={"job_id": control_job_id, "reason": "keyboard_interrupt"},
                transport=args.transport,
                hook_cmd=args.control_hook_cmd,
                hook_timeout_sec=args.control_hook_timeout_sec,
            )
            raise

    finished_at = now_iso()
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    if timed_out:
        emit_event(
            trace_path=trace_path,
            phase="SAFE_STOP",
            payload={"job_id": control_job_id, "reason": "runner_timeout", "elapsed_ms": elapsed_ms},
            transport=args.transport,
            hook_cmd=args.control_hook_cmd,
            hook_timeout_sec=args.control_hook_timeout_sec,
        )

    emit_event(
        trace_path=trace_path,
        phase="JOB_DONE",
        payload=build_job_done_payload(
            job_id=control_job_id,
            elapsed_ms=elapsed_ms,
            return_code=return_code,
            timed_out=timed_out,
            expected_outputs=expected_outputs,
        ),
        transport=args.transport,
        hook_cmd=args.control_hook_cmd,
        hook_timeout_sec=args.control_hook_timeout_sec,
    )

    summary = {
        "finished_at": finished_at,
        "job_id": control_job_id,
        "result": "timeout" if timed_out else ("success" if (return_code or 0) == 0 else "runner_failed"),
        "status_response": status_response,
        "signed_admission_responses": signed_admission_responses,
        "job_req_response": job_req_response,
        "runner_exit_code": return_code,
        "runner_log": str(runner_log_path),
        "manifest_path": str(manifest_path),
        "control_trace_path": str(trace_path),
        "summary_path": str(summary_path),
    }
    json_dump(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 124 if timed_out else (return_code or 0)


if __name__ == "__main__":
    raise SystemExit(main())
