#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = PROJECT_ROOT / "session_bootstrap" / "demo" / "openamp_control_plane_demo"
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from board_access import (  # noqa: E402
    HOST_KEYS,
    INFERENCE_SHARED_REQUIRED_KEYS,
    INFERENCE_VARIANT_REQUIRED_KEYS,
    PORT_KEYS,
    USER_KEYS,
    build_board_access_config,
    build_demo_default_board_access,
    first_non_empty,
    load_env_path,
    repo_relative,
    resolve_existing_env,
    resolve_local_path,
)
from inference_runner import (  # noqa: E402
    configured_admission_mode,
    demo_variant_label,
    expected_sha_for_variant,
    missing_control_plane_fields,
)


EXIT_READY = 0
EXIT_BLOCKED = 2
EXIT_ERROR = 1
VARIANTS = ("current", "baseline")
READINESS_PASSWORD_ENV_VAR = "OPENAMP_DEMO_READINESS_PASSWORD"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check OpenAMP demo session readiness.")
    parser.add_argument(
        "--probe-env",
        default="",
        help="Optional SSH probe env file, aligned with run_openamp_demo.sh --probe-env.",
    )
    parser.add_argument("--host", default="", help="Optional session host override.")
    parser.add_argument("--user", default="", help="Optional session user override.")
    parser.add_argument("--password", default="", help="Optional runtime password override.")
    parser.add_argument("--port", default="", help="Optional session SSH port override.")
    parser.add_argument("--env-file", default="", help="Optional inference env file override.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. json is the default for machine-readable checks.",
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_explicit_path(raw_path: str, label: str) -> None:
    value = str(raw_path or "").strip()
    if not value:
        return
    if resolve_existing_env(value) is not None:
        return
    raise ValueError(f"{label} 不存在: {repo_relative(resolve_local_path(value))}")


def key_presence(values: dict[str, str], keys: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for key in keys:
        if str(values.get(key) or "").strip():
            present.append(str(key))
        else:
            missing.append(str(key))
    return {"present_keys": present, "missing_keys": missing}


def field_presence(values: dict[str, str]) -> dict[str, Any]:
    field_checks = {
        "host": bool(first_non_empty(values, HOST_KEYS)),
        "user": bool(first_non_empty(values, USER_KEYS)),
        "port": bool(first_non_empty(values, PORT_KEYS)),
    }
    present_fields = [field for field, present in field_checks.items() if present]
    missing_fields = [field for field, present in field_checks.items() if not present]
    return {
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "ready_without_password": not missing_fields,
    }


def build_probe_env_report(access: Any) -> dict[str, Any]:
    values: dict[str, str] = {}
    source_path = access.preloaded_ssh_env_file
    if source_path is not None and source_path.exists():
        values = load_env_path(source_path)
    report = field_presence(values)
    report.update(
        {
            "source_file": repo_relative(source_path) if source_path else "",
            "note": "Repo-side password字段不会从 probe env 预载；live probe 仍需要运行时 password。",
        }
    )
    return report


def build_variant_report(access: Any, variant: str) -> dict[str, Any]:
    effective_env = access.build_env()
    shared_presence = key_presence(effective_env, INFERENCE_SHARED_REQUIRED_KEYS)
    variant_keys = INFERENCE_VARIANT_REQUIRED_KEYS.get(variant, ())
    variant_presence = key_presence(effective_env, variant_keys)
    env_missing = access.missing_inference_fields(variant)
    control_missing = missing_control_plane_fields(access, variant)
    ready = not env_missing and not control_missing
    return {
        "label": demo_variant_label(variant),
        "ready": ready,
        "missing_env_fields": env_missing,
        "shared_required_keys": shared_presence,
        "variant_required_keys": variant_presence,
        "control_plane": {
            "admission_mode": configured_admission_mode(effective_env, variant=variant),
            "expected_sha_present": bool(expected_sha_for_variant(access, variant)),
            "missing_fields": control_missing,
        },
    }


def build_blockers(session_public: dict[str, Any], variants: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    missing_connection = list(session_public.get("missing_connection_fields") or [])
    if missing_connection:
        blockers.append(
            {
                "scope": "session",
                "kind": "missing_connection_fields",
                "fields": missing_connection,
                "message": f"缺少会话字段: {', '.join(missing_connection)}。",
            }
        )
    for variant, payload in variants.items():
        missing_env = list(payload.get("missing_env_fields") or [])
        if missing_env:
            blockers.append(
                {
                    "scope": f"{variant}_inference",
                    "kind": "missing_inference_env_fields",
                    "fields": missing_env,
                    "message": f"{payload['label']} live 缺少字段: {', '.join(missing_env)}。",
                }
            )
        missing_control = list(payload.get("control_plane", {}).get("missing_fields") or [])
        if missing_control:
            blockers.append(
                {
                    "scope": f"{variant}_control_plane",
                    "kind": "missing_control_plane_fields",
                    "fields": missing_control,
                    "message": f"{payload['label']} control-plane 缺少字段: {', '.join(missing_control)}。",
                }
            )
    return blockers


def build_mode(access: Any, variants: dict[str, dict[str, Any]]) -> dict[str, Any]:
    current_ready = bool(variants["current"]["ready"])
    baseline_ready = bool(variants["baseline"]["ready"])
    probe_ready = bool(access.probe_ready)
    docs_first_only = not probe_ready

    if probe_ready and current_ready and baseline_ready:
        return {
            "code": "live_probe_and_inference_ready",
            "label": "可继续 live probe / inference",
            "status": "ready",
            "docs_first_only": False,
            "summary": "会话、probe 与 Current/PyTorch live inference 条件都已齐全，可继续真实 demo 会话。",
            "next_action": "可继续在 dashboard 里执行 live probe 与 live inference。",
        }
    if probe_ready and (current_ready or baseline_ready):
        return {
            "code": "live_probe_ready_partial_inference",
            "label": "可继续 live probe，部分 inference 可用",
            "status": "partial",
            "docs_first_only": False,
            "summary": "板侧会话已就绪，至少一个 live inference 变体可继续，但仍有未补齐的 inference 条件。",
            "next_action": "先继续 live probe，并补齐剩余 inference blocker 后再做完整 operator flow。",
        }
    if probe_ready:
        return {
            "code": "live_probe_ready_inference_blocked",
            "label": "可继续 live probe，inference 仍阻塞",
            "status": "partial",
            "docs_first_only": False,
            "summary": "板侧 SSH 会话已齐全，可继续只读 probe，但 live inference 还缺条件。",
            "next_action": "先用 live probe 验证板状态，再补齐 inference env/control-plane blocker。",
        }

    missing_connection = access.missing_connection_fields()
    if access.has_preloaded_defaults and missing_connection == ["password"]:
        return {
            "code": "password_required",
            "label": "待补全密码",
            "status": "blocked",
            "docs_first_only": docs_first_only,
            "summary": "SSH 与推理默认值已预载，但缺少 password；当前仍停留在 docs-first / evidence-led。",
            "next_action": "补齐一次运行时 password 后重跑检查，即可判断能否继续 live probe / inference。",
        }
    if access.configured:
        return {
            "code": "session_incomplete",
            "label": "待补全会话",
            "status": "blocked",
            "docs_first_only": docs_first_only,
            "summary": "当前只填了一部分板侧会话信息，仍不足以继续 live probe。",
            "next_action": "补齐缺失的 host/user/password 后重跑检查。",
        }
    return {
        "code": "docs_first_only",
        "label": "仅 docs-first",
        "status": "blocked",
        "docs_first_only": docs_first_only,
        "summary": "当前没有可用板侧会话，仓库只具备 docs-first / evidence-led 演示条件。",
        "next_action": "先补齐 host/user/password 与 inference env，再重跑 readiness 检查。",
    }


def build_summary_lines(report: dict[str, Any]) -> list[str]:
    overall = report["overall"]
    session = report["session"]
    variants = report["variants"]
    lines = [
        f"mode={overall['mode']['label']}: {overall['mode']['summary']}",
        (
            "session="
            f"host:{session['host'] or '-'} "
            f"user:{session['user'] or '-'} "
            f"port:{session['port']} "
            f"password:{'yes' if session['has_password'] else 'no'} "
            f"env_file:{session['env_file'] or '-'}"
        ),
        (
            "can_continue="
            f"probe:{str(overall['can_continue']['live_probe']).lower()} "
            f"current:{str(overall['can_continue']['live_inference']['current']).lower()} "
            f"baseline:{str(overall['can_continue']['live_inference']['baseline']).lower()}"
        ),
    ]
    if report["blockers"]:
        lines.extend(blocker["message"] for blocker in report["blockers"])
    else:
        lines.append("未发现 readiness blocker。")
    lines.append(f"next_action={overall['mode']['next_action']}")
    return lines


def build_readiness_report(
    *,
    probe_env: str = "",
    host: str = "",
    user: str = "",
    password: str = "",
    port: str = "",
    env_file: str = "",
) -> dict[str, Any]:
    validate_explicit_path(probe_env, "probe env 文件")
    defaults = build_demo_default_board_access(probe_env or None)
    payload = {
        "host": host,
        "user": user,
        "password": password,
        "port": port,
        "env_file": env_file,
    }
    payload = {key: value for key, value in payload.items() if str(value or "").strip()}
    access = build_board_access_config(payload, fallback=defaults) if payload else defaults

    session_public = access.to_public_dict()
    variants = {variant: build_variant_report(access, variant) for variant in VARIANTS}
    mode = build_mode(access, variants)
    blockers = build_blockers(session_public, variants)
    ready_for_live_operator_flow = bool(access.probe_ready and all(variants[name]["ready"] for name in VARIANTS))
    report = {
        "generated_at": now_iso(),
        "inputs": {
            "probe_env": probe_env,
            "host_override": bool(host),
            "user_override": bool(user),
            "password_override": bool(password),
            "port_override": bool(port),
            "env_file_override": bool(env_file),
        },
        "overall": {
            "status": "ready" if ready_for_live_operator_flow else mode["status"],
            "ready_for_live_operator_flow": ready_for_live_operator_flow,
            "docs_first_only": mode["docs_first_only"],
            "can_continue": {
                "live_probe": bool(access.probe_ready),
                "live_inference": {
                    "current": bool(variants["current"]["ready"]),
                    "baseline": bool(variants["baseline"]["ready"]),
                },
            },
            "mode": mode,
            "blocker_count": len(blockers),
        },
        "session": session_public,
        "probe_env": build_probe_env_report(access),
        "inference_env": {
            "source_file": repo_relative(access.env_file) if access.env_file else "",
            "loaded": bool(access.env_file),
            "shared_required_keys": key_presence(access.build_env(), INFERENCE_SHARED_REQUIRED_KEYS),
        },
        "variants": variants,
        "blockers": blockers,
    }
    report["overall"]["summary_lines"] = build_summary_lines(report)
    return report


def exit_code_for_report(report: dict[str, Any]) -> int:
    return EXIT_READY if report["overall"]["ready_for_live_operator_flow"] else EXIT_BLOCKED


def render_text(report: dict[str, Any]) -> str:
    overall = report["overall"]
    session = report["session"]
    probe_env = report["probe_env"]
    inference_env = report["inference_env"]
    variants = report["variants"]
    lines = [
        "OpenAMP Demo Session Readiness",
        f"status: {overall['status']}",
        f"mode: {overall['mode']['label']}",
        f"summary: {overall['mode']['summary']}",
        (
            "session: "
            f"host={session['host'] or '-'} "
            f"user={session['user'] or '-'} "
            f"port={session['port']} "
            f"password={'yes' if session['has_password'] else 'no'} "
            f"env_file={session['env_file'] or '-'}"
        ),
        "missing_connection_fields: " + (", ".join(session["missing_connection_fields"]) or "none"),
        (
            "probe_env: "
            f"source={probe_env['source_file'] or '-'} "
            f"ready_without_password={'yes' if probe_env['ready_without_password'] else 'no'} "
            f"missing={', '.join(probe_env['missing_fields']) or 'none'}"
        ),
        (
            "inference_env: "
            f"source={inference_env['source_file'] or '-'} "
            f"shared_missing={', '.join(inference_env['shared_required_keys']['missing_keys']) or 'none'}"
        ),
    ]
    for variant in VARIANTS:
        payload = variants[variant]
        lines.append(
            f"{variant}: ready={'yes' if payload['ready'] else 'no'} "
            f"missing_env={', '.join(payload['missing_env_fields']) or 'none'} "
            f"missing_control={', '.join(payload['control_plane']['missing_fields']) or 'none'} "
            f"admission={payload['control_plane']['admission_mode']}"
        )
    if report["blockers"]:
        lines.append("blockers:")
        for blocker in report["blockers"]:
            lines.append(f"- {blocker['message']}")
    else:
        lines.append("blockers: none")
    lines.append(f"next_action: {overall['mode']['next_action']}")
    lines.append(
        "exit_code: "
        f"{exit_code_for_report(report)} (0=ready_for_live_operator_flow, 2=blocked_by_readiness)"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    password = args.password or os.environ.get(READINESS_PASSWORD_ENV_VAR, "")
    try:
        report = build_readiness_report(
            probe_env=args.probe_env,
            host=args.host,
            user=args.user,
            password=password,
            port=args.port,
            env_file=args.env_file,
        )
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return EXIT_ERROR

    if args.format == "text":
        sys.stdout.write(render_text(report))
    else:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return exit_code_for_report(report)


if __name__ == "__main__":
    raise SystemExit(main())
