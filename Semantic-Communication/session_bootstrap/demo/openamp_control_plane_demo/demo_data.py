from __future__ import annotations

import base64
from functools import lru_cache
import json
import math
import re
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = PROJECT_ROOT.parent
WORKSPACE_ROOT = PROJECT_ROOT.parents[2] if len(PROJECT_ROOT.parents) > 2 else REPO_ROOT
REPORTS_ROOT = PROJECT_ROOT / "session_bootstrap" / "reports"
PACKAGE_ROOT = REPORTS_ROOT / "openamp_control_plane_evidence_package_20260315"
SCRIPTS_ROOT = PROJECT_ROOT / "session_bootstrap" / "scripts"
LATEST_LIVE_DUALPATH_REPORT = REPORTS_ROOT / "openamp_demo_live_dualpath_status_20260317.md"
PYTORCH_REFERENCE_ROOT = (
    PROJECT_ROOT / "session_bootstrap" / "tmp" / "quality_metrics_inputs_20260312" / "reference"
)
PYTORCH_REFERENCE_MANIFEST = PYTORCH_REFERENCE_ROOT / "pytorch_reference_manifest.json"
DEMO_SAMPLES_ROOT = Path(__file__).resolve().parent / "static" / "demo_samples"
USRP_ORIGINAL_IMAGE_DIR_CANDIDATES = (
    REPO_ROOT / "host_pic_to_latent" / "airfield300",
    REPO_ROOT / "host_pic_to_latent" / "airfield",
    WORKSPACE_ROOT / "原始图像",
)

FAULT_CODE_NAMES = {
    0: "NONE",
    1: "ARTIFACT_SHA_MISMATCH",
    3: "HEARTBEAT_TIMEOUT",
    9: "ILLEGAL_PARAM_RANGE",
    10: "MANUAL_SAFE_STOP",
}

GUARD_STATE_NAMES = {
    0: "BOOT",
    1: "READY",
    2: "JOB_ACTIVE",
    3: "WAIT_DONE",
    4: "DENY_PENDING",
    5: "FAULT_LATCHED",
}

DISPLAY_GUARD_STATE_NAMES = {
    "BOOT": "启动中 BOOT",
    "READY": "就绪 READY",
    "JOB_ACTIVE": "任务执行中 JOB_ACTIVE",
    "WAIT_DONE": "等待完成 WAIT_DONE",
    "DENY_PENDING": "拒绝待确认 DENY_PENDING",
    "FAULT_LATCHED": "故障锁存 FAULT_LATCHED",
}

DISPLAY_FAULT_CODE_NAMES = {
    "NONE": "无故障 NONE",
    "ARTIFACT_SHA_MISMATCH": "工件 SHA 不匹配 ARTIFACT_SHA_MISMATCH",
    "HEARTBEAT_TIMEOUT": "心跳超时 HEARTBEAT_TIMEOUT",
    "ILLEGAL_PARAM_RANGE": "参数范围非法 ILLEGAL_PARAM_RANGE",
    "MANUAL_SAFE_STOP": "人工安全停止 MANUAL_SAFE_STOP",
}

FIT_SCENARIO_LABELS = {
    "wrong expected_sha256 JOB_REQ on real board path": "真机路径下发送错误 expected_sha256 的 JOB_REQ",
    "illegal expected_outputs JOB_REQ on real board path": "真机路径下发送非法 expected_outputs 的 JOB_REQ",
    "heartbeat timeout / watchdog semantics on real board path": "真机路径下验证 heartbeat timeout / watchdog 语义",
    "heartbeat timeout / watchdog semantics on real board path after watchdog fix": (
        "部署 watchdog 修复后，在真机路径下复验 heartbeat timeout / watchdog 语义"
    ),
}

FIT_RISK_LABELS = {
    "unknown artifact execution risk": "未知工件被放行执行的风险",
    "input contract / param range violation": "输入契约或参数范围违规风险",
    "runaway active job due to missing heartbeat timeout watchdog": "缺少 heartbeat timeout watchdog 导致任务失控持续运行的风险",
}

FIT_CONCLUSION_LABELS = {
    (
        "After deploying the lazy watchdog firmware fix, a follow-up STATUS_REQ after 5s with no "
        "heartbeat now exposes HEARTBEAT_TIMEOUT(F003) and returns the board to READY."
    ): "部署 watchdog 修复固件后，停发 heartbeat 5 秒再发 STATUS_REQ，板卡会返回 READY，并显式暴露 HEARTBEAT_TIMEOUT(F003)。",
    (
        "Current live firmware does not auto-trigger HEARTBEAT_TIMEOUT / SAFE_STOP after the tested "
        "5s no-heartbeat window; manual SAFE_STOP was required to return the board to READY."
    ): "旧 live firmware 在停发 heartbeat 5 秒后不会自动触发 HEARTBEAT_TIMEOUT / SAFE_STOP，必须手动 SAFE_STOP 才能回到 READY。",
}

FIT_EVIDENCE_LABELS = {
    "fit_report": "FIT 报告",
    "coverage_matrix": "覆盖矩阵",
    "remote_probe": "远程探板结果",
    "wrapper_summary": "wrapper 摘要",
    "job_req_bridge_summary": "JOB_REQ bridge 摘要",
    "post_status_snapshot": "事后状态快照",
    "final_status_snapshot": "最终状态快照",
}

INLINE_LINK_LABELS = {
    "summary": "摘要",
    "probe": "原始探板",
    "probe log": "探针日志",
    "history summary": "历史摘要",
    "fit": "FIT 报告",
}

PRERECORDED_SAMPLE_FIXTURES = (
    {
        "sample_id": "places365-208",
        "label": "样例 208",
        "title": "Places365 预置样例 208",
        "note": "使用仓库内已归档的参考图、current 重建图和 PyTorch 参考基线图，适合现场稳定演示。",
        "relative_path": "Places365_val_00000208_recon.png",
        "original_path": DEMO_SAMPLES_ROOT / "places365_208_current.png",
        "current_path": DEMO_SAMPLES_ROOT / "places365_208_current.png",
        "baseline_path": DEMO_SAMPLES_ROOT / "places365_208_baseline.png",
    },
)
QUALITY_CURRENT_REPORT = REPORTS_ROOT / "quality_metrics_20260312_pytorch_vs_tvm_current.json"
QUALITY_BASELINE_REPORT = REPORTS_ROOT / "quality_metrics_20260312_pytorch_vs_tvm_baseline.json"
DEFAULT_DEMO_DEADLINE_MS = 300000
DEFAULT_DEMO_EXPECTED_OUTPUTS = 300
DEFAULT_DEMO_JOB_FLAGS = "reconstruction"
LINK_PROFILE_PRESETS = (
    {
        "profile_id": "normal",
        "label": "正常链路",
        "tone": "online",
        "summary": "不额外施加弱网扰动，保留现场当前控制面 / 数据面实况。",
        "operator_goal": "默认演示口径，适合讲解控制面与数据面正常联动。",
        "future_binding": {
            "netem": "delay 20ms 2ms loss 0.1%",
            "physical": "直连或无附加衰减",
        },
        "simulated_metrics": {
            "rtt_ms": 20,
            "jitter_ms": 2,
            "loss_pct": 0.1,
            "outage": "无",
        },
        "evidence_binding": {
            "mode": "live_anchor",
            "label": "8115 live 锚点",
            "note": "正常链路默认回到 8115 live 300 / 300 与最新探板锚点，不伪造新的弱网对照。",
        },
    },
    {
        "profile_id": "jitter",
        "label": "抖动",
        "tone": "degraded",
        "summary": "保留链路连通，但放大时延抖动，便于讲解控制与回传的不稳定观感。",
        "operator_goal": "演示弱网抖动下的操作员观察位。",
        "future_binding": {
            "netem": "delay 120ms 60ms distribution normal",
            "physical": "通道模拟仪抖动档位",
        },
        "simulated_metrics": {
            "rtt_ms": 120,
            "jitter_ms": 60,
            "loss_pct": 1.0,
            "outage": "无",
        },
        "evidence_binding": {
            "mode": "repo_compare",
            "scenario_id": "snr12_real_compare",
            "label": "SNR 12 真机对照",
            "note": "把抖动导演位绑定到仓库内已有的 SNR 12 真机 compare 结果，展示真实导出参数而不是静态文案。",
        },
    },
    {
        "profile_id": "lossy",
        "label": "高丢包",
        "tone": "degraded",
        "summary": "强调丢包场景，适合为后续 tc/netem loss / reorder 绑定预留导演位。",
        "operator_goal": "突出回传质量下降与重试讨论。",
        "future_binding": {
            "netem": "loss 12% 25% reorder 3% 50%",
            "physical": "可调衰减或差链路交换口",
        },
        "simulated_metrics": {
            "rtt_ms": 150,
            "jitter_ms": 35,
            "loss_pct": 12.0,
            "outage": "无",
        },
        "evidence_binding": {
            "mode": "repo_compare",
            "scenario_id": "snr10_real_compare",
            "label": "SNR 10 真机对照",
            "note": "把高丢包导演位绑定到仓库内已有的 SNR 10 真机 compare 结果，展示真实导出参数而不是静态文案。",
        },
    },
    {
        "profile_id": "flaky",
        "label": "间歇断连",
        "tone": "offline",
        "summary": "预演短时断连 / 恢复的导演台口径，但当前不伪造 live 读数。",
        "operator_goal": "为未来物理断链或 netem 丢包脉冲控制做 UI 预案。",
        "future_binding": {
            "netem": "loss 35% 60% gemodel + scheduled qdisc toggle",
            "physical": "射频衰减器或交换机端口脉冲断续",
        },
        "simulated_metrics": {
            "rtt_ms": 300,
            "jitter_ms": 120,
            "loss_pct": 35.0,
            "outage": "5s on / 3s off",
        },
        "evidence_binding": {
            "mode": "staged_only",
            "label": "导演位预案",
            "note": "当前仓库没有与间歇断连一一对应的真机 compare 结论；保留导演位，不伪造弱网参数输出。",
        },
    },
    {
        "profile_id": "recover",
        "label": "恢复",
        "tone": "online",
        "summary": "撤销弱网预案，面向 future backend 执行 clear qdisc / 恢复物理链路。",
        "operator_goal": "快速回到 nominal 演示口径。",
        "future_binding": {
            "netem": "tc qdisc del dev <iface> root",
            "physical": "切回直连或旁路档位",
        },
        "simulated_metrics": {
            "rtt_ms": 25,
            "jitter_ms": 3,
            "loss_pct": 0.0,
            "outage": "清除弱网预案",
        },
        "evidence_binding": {
            "mode": "repo_compare",
            "scenario_id": "snr10_bestcurrent",
            "label": "SNR 10 bestcurrent",
            "note": "恢复位默认对齐到仓库内最新 bestcurrent SNR 10 compare，展示收口后的推荐参数与吞吐结论。",
        },
    },
)

WEAK_NETWORK_COMPARE_FIXTURES = (
    {
        "scenario_id": "snr12_real_compare",
        "label": "SNR 12 真机对照",
        "tone": "degraded",
        "recommended": False,
        "operator_note": "较温和的弱网档位，保持 300 / 300，同时给出 serial vs pipeline 的真实吞吐差。",
        "report_json": REPORTS_ROOT / "big_little_compare_20260318_053619.json",
        "report_md": REPORTS_ROOT / "big_little_compare_20260318_053619.md",
    },
    {
        "scenario_id": "snr10_real_compare",
        "label": "SNR 10 真机对照",
        "tone": "degraded",
        "recommended": False,
        "operator_note": "更重的弱网档位，直接展示 SNR=10 时的真实 compare 导出参数与吞吐差。",
        "report_json": REPORTS_ROOT / "big_little_compare_20260318_095615.json",
        "report_md": REPORTS_ROOT / "big_little_compare_20260318_095615.md",
    },
    {
        "scenario_id": "snr10_bestcurrent",
        "label": "SNR 10 bestcurrent",
        "tone": "online",
        "recommended": True,
        "operator_note": "当前最适合放到答辩台上的 SNR 10 收口档位，pipeline 与队列参数已经稳定。",
        "report_json": REPORTS_ROOT / "big_little_compare_20260318_123300.json",
        "report_md": REPORTS_ROOT / "big_little_compare_20260318_123300.md",
    },
)

DEFAULT_AIRCRAFT_POSITION = {
    "aircraft_id": "FT-AIR-01",
    "mission_call_sign": "M9-DEMO",
    "source_kind": "backend_stub",
    "source_status": "stub",
    "source_label": "上位机位置（stub）",
    "source_note": "真实上位机定位缺席时，demo backend 继续通过同一 aircraft-position contract 提供 stub telemetry。",
    "latitude": 30.572815,
    "longitude": 104.066801,
    "altitude_m": 1820.0,
    "ground_speed_kph": 248.0,
    "heading_deg": 78.0,
    "vertical_speed_mps": 1.4,
    "fix_type": "3D",
    "confidence_m": 6.5,
    "satellites": 11,
    "sample_sequence": 0,
    "sample_transport": "backend_http_post",
    "sample_producer_id": "upper-computer-gps-daemon",
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_heading_deg(value: Any, default: float = 0.0) -> float:
    heading = coerce_float(value, default) % 360.0
    return round(heading, 1)


def build_aircraft_track(latitude: float, longitude: float, heading_deg: float) -> list[dict[str, Any]]:
    heading = math.radians((heading_deg + 180.0) % 360.0)
    track: list[dict[str, Any]] = []
    for index in range(5, -1, -1):
        distance = 0.052 * index
        lat_offset = math.cos(heading) * distance * 0.48
        lon_offset = math.sin(heading) * distance
        track.append(
            {
                "latitude": round(latitude + lat_offset, 6),
                "longitude": round(longitude + lon_offset, 6),
                "age_sec": index * 6,
            }
        )
    return track


def build_aircraft_position_snapshot(feed: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(feed or {})
    position_payload = payload.get("position") if isinstance(payload.get("position"), dict) else {}
    kinematics_payload = payload.get("kinematics") if isinstance(payload.get("kinematics"), dict) else {}
    fix_payload = payload.get("fix") if isinstance(payload.get("fix"), dict) else {}
    sample_payload = payload.get("sample") if isinstance(payload.get("sample"), dict) else {}

    latitude = coerce_float(
        position_payload.get("latitude", payload.get("latitude")),
        DEFAULT_AIRCRAFT_POSITION["latitude"],
    )
    longitude = coerce_float(
        position_payload.get("longitude", payload.get("longitude")),
        DEFAULT_AIRCRAFT_POSITION["longitude"],
    )
    altitude_m = coerce_float(
        kinematics_payload.get("altitude_m", payload.get("altitude_m")),
        DEFAULT_AIRCRAFT_POSITION["altitude_m"],
    )
    ground_speed_kph = coerce_float(
        kinematics_payload.get("ground_speed_kph", payload.get("ground_speed_kph")),
        DEFAULT_AIRCRAFT_POSITION["ground_speed_kph"],
    )
    vertical_speed_mps = coerce_float(
        kinematics_payload.get("vertical_speed_mps", payload.get("vertical_speed_mps")),
        DEFAULT_AIRCRAFT_POSITION["vertical_speed_mps"],
    )
    heading_deg = normalize_heading_deg(
        kinematics_payload.get("heading_deg", payload.get("heading_deg")),
        default=DEFAULT_AIRCRAFT_POSITION["heading_deg"],
    )
    confidence_m = coerce_float(
        fix_payload.get("confidence_m", payload.get("confidence_m")),
        DEFAULT_AIRCRAFT_POSITION["confidence_m"],
    )
    satellites = coerce_int(
        fix_payload.get("satellites", payload.get("satellites")),
        DEFAULT_AIRCRAFT_POSITION["satellites"],
    )
    source_status = str(
        payload.get("source_status") or payload.get("feed_status") or DEFAULT_AIRCRAFT_POSITION["source_status"]
    ).strip().lower()
    source_kind = str(payload.get("source_kind") or DEFAULT_AIRCRAFT_POSITION["source_kind"]).strip() or "backend_stub"
    source_label = str(payload.get("source_label") or DEFAULT_AIRCRAFT_POSITION["source_label"]).strip() or "上位机位置（stub）"
    source_note = str(payload.get("source_note") or DEFAULT_AIRCRAFT_POSITION["source_note"]).strip()
    fix_type = str(payload.get("fix_type") or fix_payload.get("type") or DEFAULT_AIRCRAFT_POSITION["fix_type"]).strip() or "3D"
    captured_at = str(sample_payload.get("captured_at") or payload.get("captured_at") or payload.get("updated_at") or now_iso())
    sample_sequence = coerce_int(
        sample_payload.get("sequence", payload.get("sequence")),
        DEFAULT_AIRCRAFT_POSITION["sample_sequence"],
    )
    sample_transport = str(
        sample_payload.get("transport")
        or payload.get("transport")
        or DEFAULT_AIRCRAFT_POSITION["sample_transport"]
    ).strip() or "backend_http_post"
    sample_producer_id = str(
        sample_payload.get("producer_id")
        or payload.get("producer_id")
        or DEFAULT_AIRCRAFT_POSITION["sample_producer_id"]
    ).strip() or "upper-computer-gps-daemon"
    primary_feed_active = source_kind == "upper_computer_gps" and source_status not in {"stub", "fallback", "absent"}
    contract_summary = (
        "Upper-computer GPS is primary; cockpit telemetry is read from the demo backend contract."
        if primary_feed_active
        else "Upper-computer GPS feed is absent; cockpit telemetry is currently served by the backend stub contract."
    )
    active_contract_label = "上位机位置" if primary_feed_active else "上位机位置（stub）"

    return {
        "contract_version": "aircraft_position.v1",
        "source_api_path": "/api/aircraft-position",
        "source_kind": source_kind,
        "source_status": source_status,
        "source_label": source_label,
        "source_note": source_note,
        "ownership_note": "Aircraft position authority sits in the upper-computer/backend contract; the cockpit only mirrors backend telemetry.",
        "fallback_note": (
            "真实上位机 feed 缺席时，页面继续读取 backend stub contract；"
            "真实 feed 接入后仍走同一 API。"
        ),
        "integration_note": "Recommended producer: upper-computer GPS daemon POSTs samples to /api/aircraft-position.",
        "aircraft_id": str(payload.get("aircraft_id") or DEFAULT_AIRCRAFT_POSITION["aircraft_id"]),
        "mission_call_sign": str(payload.get("mission_call_sign") or DEFAULT_AIRCRAFT_POSITION["mission_call_sign"]),
        "updated_at": str(payload.get("updated_at") or now_iso()),
        "sample": {
            "captured_at": captured_at,
            "sequence": sample_sequence,
            "transport": sample_transport,
            "producer_id": sample_producer_id,
        },
        "feed_contract": {
            "authority": "demo_backend",
            "consumer": "cockpit_shell",
            "api_path": "/api/aircraft-position",
            "summary": contract_summary,
            "primary_source": {
                "source_kind": "upper_computer_gps",
                "label": "Upper Computer GPS",
                "producer_id": sample_producer_id,
                "transport": sample_transport,
                "active": primary_feed_active,
            },
            "fallback_source": {
                "source_kind": "backend_stub",
                "label": "Backend Stub Contract",
                "active": not primary_feed_active,
                "activation_note": "Only active while the upper-computer feed is absent.",
            },
            "active_source_kind": source_kind if primary_feed_active else "backend_stub",
            "active_source_label": active_contract_label,
        },
        "position": {
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
        },
        "kinematics": {
            "altitude_m": round(altitude_m, 1),
            "ground_speed_kph": round(ground_speed_kph, 1),
            "heading_deg": heading_deg,
            "vertical_speed_mps": round(vertical_speed_mps, 2),
        },
        "fix": {
            "type": fix_type,
            "confidence_m": round(confidence_m, 1),
            "satellites": satellites,
        },
        "track": build_aircraft_track(latitude, longitude, heading_deg),
    }


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_repo_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
        path.relative_to(PROJECT_ROOT)
        return path

    path = path.resolve()
    try:
        path.relative_to(PROJECT_ROOT)
        return path
    except ValueError:
        # Absolute path from another machine: try to map a repo-internal suffix
        # back under the current PROJECT_ROOT, but keep rejecting unrelated paths.
        for index in range(1, len(path.parts)):
            rebased = PROJECT_ROOT.joinpath(*path.parts[index:])
            if rebased.exists():
                return rebased
        raise ValueError(f"path is outside repo: {path}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


@lru_cache(maxsize=None)
def image_data_uri(path_value: str) -> str:
    path = Path(path_value)
    suffix = path.suffix.lower()
    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    if not path.exists():
        # Use a 1x1 transparent PNG when assets are absent on another machine.
        placeholder_png = base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        ).decode("ascii")
        return f"data:image/png;base64,{placeholder_png}"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _image_number(path: Path, fallback: int) -> int:
    match = re.search(r"(\d+)$", path.stem)
    if not match:
        return fallback
    try:
        return int(match.group(1))
    except ValueError:
        return fallback


def _collect_original_images(image_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.jpg", "*.jpeg", "*.png"):
        files.extend(path for path in image_dir.glob(pattern) if path.is_file())
    files.sort(key=lambda path: path.name)
    return files


def _image_gallery_entry(path: Path, ordinal: int) -> dict[str, Any]:
    return {
        "index": ordinal,
        "number": _image_number(path, ordinal),
        "filename": path.name,
        "path": repo_relative(path),
    }


def build_original_gallery_snapshot(mode: str, *, count: int = 1) -> dict[str, Any]:
    normalized_mode = "usrp" if str(mode or "").strip().lower() == "usrp" else "prerecorded"
    requested_count = max(1, int(count or 1))
    if normalized_mode == "usrp":
        for image_dir in USRP_ORIGINAL_IMAGE_DIR_CANDIDATES:
            images = _collect_original_images(image_dir)
            if not images:
                continue
            selected = images[:requested_count]
            first = selected[0]
            last = selected[-1]
            return {
                "mode": "usrp",
                "label": "USRP 原始图像",
                "source_dir": repo_relative(image_dir),
                "requested_count": requested_count,
                "count": len(selected),
                "range": {
                    "start": _image_number(first, 1),
                    "end": _image_number(last, len(selected)),
                    "label": f"{first.stem}-{last.stem}",
                },
                "preview_image_path": repo_relative(first),
                "preview_image_b64": image_data_uri(str(first)),
                "images": [_image_gallery_entry(path, index + 1) for index, path in enumerate(selected)],
            }

    fixture = PRERECORDED_SAMPLE_FIXTURES[0]
    original_path = fixture["original_path"]
    return {
        "mode": normalized_mode,
        "label": "预录样例原图",
        "source_dir": repo_relative(original_path.parent),
        "requested_count": requested_count,
        "count": 1,
        "range": {"start": 1, "end": 1, "label": original_path.stem},
        "preview_image_path": repo_relative(original_path),
        "preview_image_b64": image_data_uri(str(original_path)),
        "images": [_image_gallery_entry(original_path, 1)],
    }


@lru_cache(maxsize=2)
def quality_metrics_by_relative_path(report_path_value: str) -> dict[str, dict[str, Any]]:
    payload = read_json(Path(report_path_value))
    return {
        item["relative_path"]: item
        for item in payload.get("per_image", [])
        if isinstance(item, dict) and item.get("relative_path")
    }


@lru_cache(maxsize=1)
def pytorch_reference_manifest() -> dict[str, Any]:
    if PYTORCH_REFERENCE_MANIFEST.exists():
        return read_json(PYTORCH_REFERENCE_MANIFEST)
    return {
        "status": "missing",
        "completed_at": "",
        "started_at": "",
        "output_count": 0,
        "records": [],
        "timing": {
            "total_ms": 0.0,
            "mean_ms": 0.0,
        },
        "generator_ckpt_sha256": "",
        "origin_ckpt_sha256": "",
        "device": "",
        "snr": 0.0,
        "manifest_path": repo_relative(PYTORCH_REFERENCE_MANIFEST),
        "note": "PyTorch 参考 manifest 缺失；当前主 demo 已降级为空基线展示。",
    }


@lru_cache(maxsize=1)
def pytorch_reference_records_by_relative_path() -> dict[str, dict[str, Any]]:
    payload = pytorch_reference_manifest()
    records: dict[str, dict[str, Any]] = {}
    for item in payload.get("records", []):
        if not isinstance(item, dict):
            continue
        file_name = Path(str(item.get("output_path") or "")).name
        if not file_name:
            base_name = str(item.get("base_name") or "").strip()
            if not base_name:
                continue
            file_name = f"{base_name}_recon.png"
        records[file_name] = item
    return records


def build_pytorch_reference_baseline_snapshot() -> dict[str, Any]:
    payload = pytorch_reference_manifest()
    output_count = int(payload.get("output_count") or len(payload.get("records", [])) or 0)
    timing = payload.get("timing") if isinstance(payload.get("timing"), dict) else {}
    total_ms = float(timing.get("total_ms") or 0.0)
    mean_ms = float(timing.get("mean_ms") or (total_ms / output_count if output_count else 0.0))
    return {
        "label": "PyTorch 参考基线",
        "completed_at": str(payload.get("completed_at") or payload.get("started_at") or ""),
        "output_count": output_count,
        "mean_ms": round(mean_ms, 3),
        "total_ms": round(total_ms, 3),
        "manifest_path": repo_relative(PYTORCH_REFERENCE_MANIFEST),
        "reconstructions_dir": repo_relative(PYTORCH_REFERENCE_ROOT / "reconstructions"),
        "generator_ckpt_sha256": str(payload.get("generator_ckpt_sha256") or ""),
        "origin_ckpt_sha256": str(payload.get("origin_ckpt_sha256") or ""),
        "device": str(payload.get("device") or ""),
        "snr": float(payload.get("snr") or 0.0),
    }


def build_link_director_catalog() -> dict[str, Any]:
    return {
        "title": "弱网导演台 / Link Director",
        "summary": (
            "导演台预设只改变操作员可见的链路预案与后续绑定目标；本 pass 不执行 tc/netem，也不伪造板卡 live 读数。"
        ),
        "backend_status": "ui_scaffold_only",
        "plane_split_note": (
            "控制面探板、SAFE_STOP 与 guard_state 继续显示真实 live/evidence；"
            "导演台预设主要面向未来数据面链路和物理弱网控制绑定。"
        ),
        "profiles": list(LINK_PROFILE_PRESETS),
    }


@lru_cache(maxsize=1)
def build_job_manifest_contract_snapshot() -> dict[str, Any]:
    payload_report = parse_markdown_key_values(REPORTS_ROOT / "inference_compare_currentsafe_chunk4_refresh_20260313_1758.md")
    e2e_report = parse_markdown_key_values(
        REPORTS_ROOT / "inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md"
    )
    reference = pytorch_reference_manifest()
    first_record = reference.get("records", [{}])[0] if reference.get("records") else {}
    latent_shape = first_record.get("latent_shape") if isinstance(first_record, dict) else None
    output_shape = first_record.get("output_shape") if isinstance(first_record, dict) else None
    return {
        "title": "任务票 / Job Manifest Gate",
        "summary": (
            "把 operator ticket 映射到既有 launch 参数和 admission 证据上，不改现有 JOB_REQ / signed-manifest 协议。"
        ),
        "protocol_boundary_note": (
            "当前 live wrapper 继续沿用 job_id、expected_sha256、expected_outputs、deadline_ms、job_flags；"
            "input_shape / output_shape 在本页作为操作员上下文展示，不宣称本 pass 已扩展 wire schema。"
        ),
        "defaults": {
            "deadline_ms": DEFAULT_DEMO_DEADLINE_MS,
            "expected_outputs": DEFAULT_DEMO_EXPECTED_OUTPUTS,
            "job_flags": DEFAULT_DEMO_JOB_FLAGS,
            "input_shape": str(payload_report.get("input_shape") or "1,32,32,32"),
            "shape_buckets": str(payload_report.get("shape_buckets") or ""),
            "input_dtype": str(payload_report.get("input_dtype") or "float32"),
            "output_shape": str(e2e_report.get("current_output_shape") or output_shape or "[1, 3, 256, 256]"),
            "output_dtype": str(e2e_report.get("current_output_dtype") or "float32"),
            "latent_shape": latent_shape or [1, 32, 32, 32],
            "reference_output_shape": output_shape or [1, 3, 256, 256],
        },
        "evidence": [
            link_entry(
                REPORTS_ROOT / "inference_compare_currentsafe_chunk4_refresh_20260313_1758.md",
                "Current payload 报告",
            ),
            link_entry(
                REPORTS_ROOT / "inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md",
                "Current 端到端报告",
            ),
            link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考 manifest"),
        ],
    }


def clean_markdown_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1]
    return value


def normalize_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")


def to_float(value: Any) -> float:
    return float(str(value).replace(",", "").replace("%", "").replace("x", ""))


def improvement_pct(baseline_ms: float, current_ms: float) -> float:
    if baseline_ms <= 0:
        return 0.0
    return round(((baseline_ms - current_ms) / baseline_ms) * 100, 2)


def short_sha(value: str) -> str:
    return value[:12] if value else ""


def display_guard_state(value: int | str | None) -> str:
    raw = format_guard_state(value)
    return DISPLAY_GUARD_STATE_NAMES.get(raw, raw)


def display_fault_code(value: int | str | None) -> str:
    raw = format_fault_code(value)
    return DISPLAY_FAULT_CODE_NAMES.get(raw, raw)


def localize_fit_scenario(value: str) -> str:
    return FIT_SCENARIO_LABELS.get(value, value)


def localize_fit_risk(value: str) -> str:
    return FIT_RISK_LABELS.get(value, value)


def localize_fit_conclusion(value: str) -> str:
    return FIT_CONCLUSION_LABELS.get(value, value)


def localize_fit_evidence_label(value: str) -> str:
    return FIT_EVIDENCE_LABELS.get(value, value.replace("_", " "))


def localize_inline_link_label(value: str) -> str:
    return INLINE_LINK_LABELS.get(value, value)


def localize_live_probe_summary(summary: str, loaded_from_cache: bool) -> str:
    if summary:
        message = f"当前板卡可达。探板摘要：{summary}"
    else:
        message = "当前板卡可达，已拿到最新只读 SSH 探板结果。"
    if loaded_from_cache:
        message += " 该结果来自上一次成功探板的保存记录。"
    return message


def localize_coverage_item(value: str) -> str:
    mapping = {
        "wrapper-backed board smoke": "wrapper 板级冒烟",
        "wrong-SHA denial": "错误 SHA 拒绝",
        "input contract violation denial": "输入契约违规拒绝",
        "heartbeat timeout / watchdog on old live firmware": "旧固件心跳超时 / watchdog",
        "heartbeat timeout / watchdog after fix": "修复后心跳超时 / watchdog",
    }
    return mapping.get(value, value)


def localize_mapped_id(value: str) -> str:
    mapping = {
        "bring-up gate": "bring-up 门禁",
        "manual stop milestone": "手动停止里程碑",
    }
    return mapping.get(value, value)


def format_guard_state(value: int | str | None) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        return value
    return GUARD_STATE_NAMES.get(value, f"UNKNOWN_{value}")


def format_fault_code(value: int | str | None) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        return value
    return FAULT_CODE_NAMES.get(value, f"UNKNOWN_{value}")


def parse_markdown_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in read_text(path).splitlines():
        match = re.match(r"^- ([^:]+):\s*(.+?)\s*$", line)
        if not match:
            continue
        values[normalize_key(match.group(1))] = clean_markdown_value(match.group(2))
    return values


def markdown_heading(path: Path) -> str:
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return repo_relative(path)


def parse_links(cell: str, base_dir: Path) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for label, target in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", cell):
        localized_label = localize_inline_link_label(label)
        if target.startswith("http://") or target.startswith("https://"):
            links.append({"label": localized_label, "path": target, "external": True})
            continue
        resolved = (base_dir / target).resolve()
        links.append({"label": localized_label, "path": repo_relative(resolved), "external": False})
    return links


def parse_markdown_table(text: str, heading: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    table_lines: list[str] = []
    collecting = False
    for line in lines:
        if line.strip() == heading:
            collecting = True
            continue
        if not collecting:
            continue
        if line.startswith("|"):
            table_lines.append(line.rstrip())
            continue
        if table_lines:
            break
    if len(table_lines) < 3:
        return []

    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def link_entry(path: Path | str, label: str, note: str | None = None) -> dict[str, Any]:
    if isinstance(path, Path):
        value = repo_relative(path)
    else:
        value = path
    entry = {"label": label, "path": value}
    if note:
        entry["note"] = note
    return entry


def load_fit_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    evidence = payload.get("evidence_bundle", {})
    links = []
    for key in (
        "fit_report",
        "coverage_matrix",
        "remote_probe",
        "wrapper_summary",
        "job_req_bridge_summary",
        "post_status_snapshot",
        "final_status_snapshot",
    ):
        raw = evidence.get(key)
        if not raw:
            continue
        try:
            links.append(link_entry(resolve_repo_path(raw), localize_fit_evidence_label(key)))
        except ValueError:
            continue
    return {
        "fit_id": payload["fit_id"],
        "status": payload["status"],
        "scenario": localize_fit_scenario(payload["scenario"]),
        "risk_item": localize_fit_risk(payload["risk_item"]),
        "trusted_current_sha": payload.get("trusted_current_sha", ""),
        "live_firmware_sha256": payload.get("live_firmware_sha256", ""),
        "generated_at": payload["generated_at"],
        "board_access": payload.get("board_access", {}),
        "observed_result": payload.get("observed_result", {}),
        "conclusion": localize_fit_conclusion(payload.get("conclusion", "")),
        "evidence": links,
        "run_id": payload["run_id"],
    }


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def unwrap_big_little_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("pipeline")
    if isinstance(nested, dict):
        return nested
    return payload


def timing_summary(source: dict[str, Any], key: str) -> dict[str, float]:
    raw = source.get(key) if isinstance(source, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {
        "count": safe_int(raw.get("count")),
        "mean_ms": round(safe_float(raw.get("mean_ms")), 3),
        "median_ms": round(safe_float(raw.get("median_ms")), 3),
        "max_ms": round(safe_float(raw.get("max_ms")), 3),
    }


def stage_timing_card(stage_id: str, label: str, summary: dict[str, float], *, tone: str) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "label": label,
        "tone": tone,
        "count": summary.get("count", 0),
        "mean_ms": summary.get("mean_ms", 0.0),
        "median_ms": summary.get("median_ms", 0.0),
        "max_ms": summary.get("max_ms", 0.0),
    }


def build_weak_network_compare_scenario(meta: dict[str, Any]) -> dict[str, Any]:
    payload = read_json(meta["report_json"])
    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
    serial = unwrap_big_little_payload(payload.get("serial"))
    pipeline = unwrap_big_little_payload(payload.get("pipeline"))

    processed_count = safe_int(
        comparison.get("pipeline_processed_count")
        or pipeline.get("processed_count")
        or serial.get("processed_count")
        or pipeline.get("output_count")
        or serial.get("output_count")
    )
    serial_total_wall_ms = safe_float(comparison.get("serial_total_wall_ms"))
    pipeline_total_wall_ms = safe_float(comparison.get("pipeline_total_wall_ms") or pipeline.get("total_wall_ms"))
    serial_images_per_sec = safe_float(comparison.get("serial_images_per_sec"))
    pipeline_images_per_sec = safe_float(comparison.get("pipeline_images_per_sec") or pipeline.get("images_per_sec"))
    serial_ms_per_image = round(serial_total_wall_ms / processed_count, 3) if processed_count else 0.0
    pipeline_ms_per_image = round(pipeline_total_wall_ms / processed_count, 3) if processed_count else 0.0
    throughput_uplift_pct = safe_float(comparison.get("throughput_uplift_pct"))
    wall_delta_ms = round(max(serial_total_wall_ms - pipeline_total_wall_ms, 0.0), 3)
    saved_seconds_per_batch = round(wall_delta_ms / 1000.0, 3)
    saved_ms_per_image = round(max(serial_ms_per_image - pipeline_ms_per_image, 0.0), 3)

    load_summary = timing_summary(pipeline, "preload_load_summary")
    awgn_summary = timing_summary(pipeline, "preload_awgn_summary")
    infer_summary = {
        "count": safe_int(pipeline.get("run_count")),
        "mean_ms": round(safe_float(pipeline.get("run_mean_ms")), 3),
        "median_ms": round(safe_float(pipeline.get("run_median_ms")), 3),
        "max_ms": round(safe_float(pipeline.get("run_max_ms")), 3),
    }
    save_summary = timing_summary(pipeline, "save_summary")
    stage_timings = [
        stage_timing_card("preload", "载荷预取", load_summary, tone="neutral"),
        stage_timing_card("awgn", "AWGN 注噪", awgn_summary, tone="degraded"),
        stage_timing_card("infer", "板端推理", infer_summary, tone="online"),
        stage_timing_card("save", "结果落盘", save_summary, tone="warning"),
    ]

    snr_db = round(
        safe_float(pipeline.get("snr") or serial.get("snr")),
        3,
    )
    batch_size = safe_int(pipeline.get("batch_size") or serial.get("batch_size"))
    queue_depth = {
        "input": safe_int(pipeline.get("input_queue_size")),
        "output": safe_int(pipeline.get("output_queue_size")),
    }
    topology = {
        "big_cores": list(pipeline.get("big_cores") or []),
        "little_cores": list(pipeline.get("little_cores") or []),
        "backend": str(pipeline.get("backend") or ""),
        "runtime": str(pipeline.get("tvm_version") or ""),
    }

    return {
        "scenario_id": str(meta["scenario_id"]),
        "label": str(meta["label"]),
        "tone": str(meta["tone"]),
        "recommended": bool(meta.get("recommended")),
        "operator_note": str(meta.get("operator_note") or ""),
        "summary": (
            f"SNR {snr_db:.0f} 真机 compare：pipeline {pipeline_images_per_sec:.3f} img/s，"
            f"对 serial {serial_images_per_sec:.3f} img/s 提升 {throughput_uplift_pct:.3f}%。"
        ),
        "processed_count": processed_count,
        "channel": {
            "snr_db": snr_db,
            "batch_size": batch_size,
            "max_inputs": safe_int(pipeline.get("max_inputs") or serial.get("max_inputs")),
            "artifact_sha256": str(pipeline.get("artifact_sha256") or serial.get("artifact_sha256") or ""),
        },
        "comparison": {
            "serial_total_wall_ms": round(serial_total_wall_ms, 3),
            "pipeline_total_wall_ms": round(pipeline_total_wall_ms, 3),
            "serial_images_per_sec": round(serial_images_per_sec, 3),
            "pipeline_images_per_sec": round(pipeline_images_per_sec, 3),
            "throughput_uplift_pct": round(throughput_uplift_pct, 3),
            "serial_ms_per_image": serial_ms_per_image,
            "pipeline_ms_per_image": pipeline_ms_per_image,
            "saved_seconds_per_batch": saved_seconds_per_batch,
            "saved_ms_per_image": saved_ms_per_image,
        },
        "stage_timings": stage_timings,
        "topology": {
            **topology,
            "input_queue_size": queue_depth["input"],
            "output_queue_size": queue_depth["output"],
        },
        "commands": {
            "serial": str(payload.get("serial_command") or ""),
            "pipeline": str(payload.get("pipeline_command") or ""),
        },
        "evidence": [
            link_entry(meta["report_md"], "弱网对照报告"),
            link_entry(meta["report_json"], "弱网对照 JSON"),
        ],
    }


def build_weak_network_live_anchor() -> dict[str, Any]:
    latest = build_latest_live_status_snapshot()
    probe_payload: dict[str, Any] = {}
    probe_path = REPORTS_ROOT / "openamp_demo_live_probe_latest.json"
    if probe_path.is_file():
        probe_payload = read_json(probe_path)
    return {
        "label": "8115 live 锚点",
        "tone": "online",
        "valid_instance": str(latest.get("valid_instance") or ""),
        "current_completed": str((latest.get("current") or {}).get("completed") or ""),
        "baseline_completed": str((latest.get("baseline") or {}).get("completed") or ""),
        "board_status": str((latest.get("board") or {}).get("value") or ""),
        "probe_requested_at": str(probe_payload.get("requested_at") or ""),
        "probe_summary": str(probe_payload.get("summary") or (latest.get("board") or {}).get("note") or ""),
        "links": [latest.get("report"), latest.get("probe")],
    }


@lru_cache(maxsize=1)
def build_weak_network_snapshot() -> dict[str, Any]:
    scenarios = [build_weak_network_compare_scenario(meta) for meta in WEAK_NETWORK_COMPARE_FIXTURES]
    recommended = next((item for item in scenarios if item.get("recommended")), scenarios[0] if scenarios else {})
    return {
        "title": "弱网对照 / Weak-Net Console",
        "summary": (
            "这里展示的是仓库内既有 SNR compare 工具链导出的真实对照参数与吞吐结果，"
            "不把 Link Director 包装成 tc/netem 或物理弱网控制。"
        ),
        "truth_note": (
            "Link Director 仍是 ui_scaffold_only；真实弱网指标来自已归档的 compare 报告与最新 live 锚点。"
        ),
        "recommended_scenario_id": str(recommended.get("scenario_id") or ""),
        "live_anchor": build_weak_network_live_anchor(),
        "scenarios": scenarios,
    }


def synthesize_fit_readout(summary: dict[str, Any]) -> str:
    fit_id = summary["fit_id"]
    observed = summary.get("observed_result", {})
    if fit_id == "FIT-01":
        return (
            f"判定={observed.get('decision', 'UNKNOWN')}；"
            f"故障={display_fault_code(observed.get('fault_name', 'UNKNOWN'))}；"
            f"守护状态保持 {display_guard_state(observed.get('guard_final', 'UNKNOWN'))}。"
        )
    if fit_id == "FIT-02":
        return (
            f"判定={observed.get('decision', 'UNKNOWN')}；"
            f"故障={display_fault_code(observed.get('fault_name', 'UNKNOWN'))}；"
            f"wrapper 结果={observed.get('wrapper_result', 'UNKNOWN')}。"
        )
    timeout_status = observed.get("timeout_status") or observed.get("status_after_5s_without_heartbeat") or {}
    return (
        f"停发 heartbeat 5 秒后，状态={display_guard_state(timeout_status.get('guard_state'))}；"
        f"故障={display_fault_code(timeout_status.get('last_fault_code'))}；"
        f"active_job_id={timeout_status.get('active_job_id', 'NA')}。"
    )


def live_probe_loaded_from_cache(live_probe: dict[str, Any] | None) -> bool:
    return bool(live_probe and live_probe.get("_loaded_from_cache"))


def build_mode_snapshot(live_probe: dict[str, Any] | None) -> dict[str, Any]:
    materials = parse_markdown_key_values(PACKAGE_ROOT / "demo_materials_index.md")
    has_live = bool(live_probe and live_probe.get("reachable"))
    if has_live:
        effective_label = "在线读数可用"
        effective_tone = "live"
        if live_probe_loaded_from_cache(live_probe):
            summary = (
                "界面已从保存的成功探板记录恢复最近一次只读 SSH 结果；若需最新板卡状态，可手动再次读取。"
            )
        else:
            summary = (
                "界面已拿到新的只读 SSH 探板结果；整体仍以证据包为主，只额外展示当前板卡状态，不改变控制流。"
            )
    else:
        effective_label = "仅展示证据"
        effective_tone = "fallback"
        summary = (
            "当前没有新的在线探板结果，界面展示仓库内证据包和最近一次已验证的控制面状态。"
        )
    return {
        "default_mode": materials.get("default_mode", "offline-first, evidence-led"),
        "live_policy": materials.get("live_policy", ""),
        "effective_label": effective_label,
        "effective_tone": effective_tone,
        "summary": summary,
    }


def build_board_snapshot(live_probe: dict[str, Any] | None) -> dict[str, Any]:
    fit03_pass = load_fit_summary(
        REPORTS_ROOT / "openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410" / "fit_summary.json"
    )
    fit03_fail = load_fit_summary(
        REPORTS_ROOT / "openamp_heartbeat_timeout_fit_20260315_015841" / "fit_summary.json"
    )
    wrapper_summary = read_json(REPORTS_ROOT / "openamp_wrapper_hook_board_smoke_20260314_005.wrapper_summary.json")
    job_done_probe = read_json(REPORTS_ROOT / "openamp_job_done_real_probe_20260315_001.json")

    timeout_status = fit03_pass["observed_result"]["timeout_status"]
    evidence_status = {
        "label": "板级证据已确认",
        "summary": (
            "真机已通过 JOB_DONE 清理路径和修复后的 FIT-03 超时路径完成验证。现有证据表明：板卡无需重启即可回到 READY。"
        ),
        "confirmed_at": fit03_pass["generated_at"],
        "trusted_current_sha": fit03_pass["trusted_current_sha"],
        "final_live_firmware_sha256": fit03_pass["live_firmware_sha256"],
        "transport": job_done_probe["transport"],
        "wrapper_board_smoke": {
            "result": wrapper_summary["result"],
            "source": wrapper_summary["job_req_response"]["source"],
            "runner_exit_code": wrapper_summary["runner_exit_code"],
        },
        "timeout_ready_state": {
            "guard_state": format_guard_state(timeout_status["guard_state"]),
            "active_job_id": timeout_status["active_job_id"],
            "last_fault": format_fault_code(timeout_status["last_fault_code"]),
            "total_fault_count": timeout_status["total_fault_count"],
        },
        "job_done_ready_state": {
            "guard_state": format_guard_state(job_done_probe["status_after_job_done"]["guard_state"]),
            "active_job_id": job_done_probe["status_after_job_done"]["active_job_id"],
            "last_fault": format_fault_code(job_done_probe["status_after_job_done"]["last_fault_code"]),
        },
        "evidence": [
            link_entry(REPORTS_ROOT / "openamp_phase5_job_done_success_2026-03-15.md", "JOB_DONE 摘要"),
            link_entry(REPORTS_ROOT / "openamp_phase5_fit03_watchdog_success_2026-03-15.md", "FIT-03 修复后摘要"),
            link_entry(REPORTS_ROOT / "openamp_job_done_real_probe_20260315_001.json", "JOB_DONE 原始探板"),
            link_entry(
                REPORTS_ROOT / "openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410" / "remote_probe.json",
                "FIT-03 修复后远程探板",
            ),
        ],
        "history_note": fit03_fail["conclusion"],
    }

    if live_probe and live_probe.get("reachable"):
        loaded_from_cache = live_probe_loaded_from_cache(live_probe)
        summary = localize_live_probe_summary(str(live_probe.get("summary", "")), loaded_from_cache)
        current = {
            "label": "保存的只读 SSH 探板" if loaded_from_cache else "最新只读 SSH 探板",
            "summary": summary,
            "reachable": True,
            "requested_at": live_probe.get("requested_at", ""),
            "details": live_probe.get("details", {}),
            "evidence": [link_entry(REPORTS_ROOT / "openamp_demo_live_probe_latest.json", "在线探板 JSON")],
        }
    else:
        reason = live_probe.get("error", "") if live_probe else ""
        summary = "当前未拿到新的在线探板结果，界面将继续展示最近一次已验证的证据。"
        if reason:
            summary = f"{summary} 原因：{reason}"
        current = {
            "label": "暂无在线探板",
            "summary": summary,
            "reachable": False,
            "requested_at": live_probe.get("requested_at", "") if live_probe else "",
            "details": live_probe.get("details", {}) if live_probe else {},
            "evidence": [],
        }

    return {
        "evidence_status": evidence_status,
        "current_status": current,
    }


def build_milestones_snapshot() -> list[dict[str, Any]]:
    coverage_text = read_text(PACKAGE_ROOT / "coverage_matrix.md")
    rows = parse_markdown_table(coverage_text, "## Test Coverage")
    milestones = [
        {
            "stage": "P0",
            "coverage_item": "冷启动 / remoteproc / RPMsg 演示门禁",
            "mapped_id": "bring-up 门禁",
            "status": "PASS",
            "key_proof_point": (
                "基于 release_v1.4.0 派生的固件已先打通板卡启动、remoteproc 和 RPMsg 演示门禁，然后才继续收集更细的控制面里程碑证据。"
            ),
            "evidence": [
                link_entry(
                    REPORTS_ROOT / "openamp_phase5_release_v1.4.0_cold_boot_and_demo_success_2026-03-14.md",
                    "冷启动摘要",
                )
            ],
        }
    ]
    for row in rows:
        if row.get("Stage") != "P0":
            continue
        milestones.append(
            {
                "stage": row["Stage"],
                "coverage_item": localize_coverage_item(row["Coverage Item"].strip("`")),
                "mapped_id": localize_mapped_id(row["Mapped ID"].strip("`")),
                "status": row["Status"],
                "key_proof_point": row["Key Proof Point"],
                "evidence": parse_links(row["Evidence"], PACKAGE_ROOT),
            }
        )
    return milestones


def build_fit_snapshot() -> list[dict[str, Any]]:
    fit01 = load_fit_summary(REPORTS_ROOT / "openamp_wrong_sha_fit_20260315_012403" / "fit_summary.json")
    fit02 = load_fit_summary(REPORTS_ROOT / "openamp_input_contract_fit_20260315_014542" / "fit_summary.json")
    fit03_fail = load_fit_summary(REPORTS_ROOT / "openamp_heartbeat_timeout_fit_20260315_015841" / "fit_summary.json")
    fit03_pass = load_fit_summary(
        REPORTS_ROOT / "openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410" / "fit_summary.json"
    )
    fit03_pass["history"] = {
        "label": "修复前历史",
        "status": fit03_fail["status"],
        "summary": fit03_fail["conclusion"],
        "evidence": fit03_fail["evidence"],
        "generated_at": fit03_fail["generated_at"],
    }
    fits = [fit01, fit02, fit03_pass]
    for fit in fits:
        fit["readout"] = synthesize_fit_readout(fit)
    return fits


def build_performance_snapshot() -> dict[str, Any]:
    payload = parse_markdown_key_values(REPORTS_ROOT / "inference_compare_currentsafe_chunk4_refresh_20260313_1758.md")
    end_to_end = parse_markdown_key_values(
        REPORTS_ROOT / "inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md"
    )
    speedup = parse_markdown_key_values(REPORTS_ROOT / "current_scheme_b_compare_20260311_195303.md")
    artifact_sha = payload["current_expected_sha256_configured"]
    reference_baseline = build_pytorch_reference_baseline_snapshot()
    reference_mean_ms = reference_baseline["mean_ms"]
    payload_current_ms = to_float(payload["current_run_median_ms"])
    end_to_end_current_ms = to_float(end_to_end["current_run_median_ms"])

    return {
        "artifact_sha": artifact_sha,
        "positioning_note": (
            "第三幕默认基线已切到 2026-03-12 归档的 PyTorch reference manifest。第二、三幕展示的是飞腾侧语义视觉回传数据面结果；"
            "OpenAMP wrapper 只负责控制面准入、状态控制和安全收口，不替代现有推理数据通路。"
            "headline 性能统一引用 4-core Linux performance mode；本场 OpenAMP live 明确属于 3-core Linux + RTOS demo mode。"
        ),
        "metrics": [
            {
                "label": "Current payload vs PyTorch 参考均值",
                "current": f"{payload['current_run_median_ms']} ms",
                "baseline": f"PyTorch 参考 {reference_mean_ms:.3f} ms/image",
                "improvement": f"{improvement_pct(reference_mean_ms, payload_current_ms):.2f}%",
                "links": [
                    link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考 manifest"),
                    link_entry(
                        REPORTS_ROOT / "inference_compare_currentsafe_chunk4_refresh_20260313_1758.md",
                        "Current payload 报告",
                    ),
                ],
                "delta_ms": round(payload_current_ms - reference_mean_ms, 3),
            },
            {
                "label": "Current 端到端 vs PyTorch 参考均值",
                "current": f"{end_to_end['current_run_median_ms']} ms/image",
                "baseline": f"PyTorch 参考 {reference_mean_ms:.3f} ms/image",
                "improvement": f"{improvement_pct(reference_mean_ms, end_to_end_current_ms):.2f}%",
                "links": [
                    link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考 manifest"),
                    link_entry(
                        REPORTS_ROOT / "inference_real_reconstruction_compare_currentsafe_chunk4_refresh_20260313_1758.md",
                        "Current 端到端报告",
                    ),
                ],
                "delta_ms": round(end_to_end_current_ms - reference_mean_ms, 3),
            },
            {
                "label": "增量调优加速比",
                "current": speedup["incremental_speedup_vs_rebuild_only"],
                "baseline": "仅重编译 current",
                "improvement": speedup["incremental_improvement_vs_rebuild_only"],
                "links": [
                    link_entry(
                        REPORTS_ROOT / "current_scheme_b_compare_20260311_195303.md",
                        "current-only 加速报告",
                    )
                ],
                "delta_ms": speedup["incremental_vs_rebuild_only_delta"],
            },
        ],
        "micro_summary": {
            "payload_current_ms": payload_current_ms,
            "payload_baseline_ms": reference_mean_ms,
            "payload_improvement_pct": improvement_pct(reference_mean_ms, payload_current_ms),
            "end_to_end_current_ms": end_to_end_current_ms,
            "end_to_end_baseline_ms": reference_mean_ms,
            "end_to_end_improvement_pct": improvement_pct(reference_mean_ms, end_to_end_current_ms),
            "incremental_speedup_x": to_float(speedup["incremental_speedup_vs_rebuild_only"]),
        },
        "reference_baseline": reference_baseline,
    }


def speedup_x(baseline_ms: float, current_ms: float) -> float:
    if current_ms <= 0:
        return 0.0
    return round(baseline_ms / current_ms, 1)


def build_comparison_snapshot() -> dict[str, Any]:
    performance = build_performance_snapshot()
    micro = performance["micro_summary"]
    return {
        "baseline_source": performance["reference_baseline"],
        "payload": {
            "label": "Current payload vs PyTorch 参考均值",
            "baseline_label": "PyTorch 参考单图均值",
            "current_label": "Current payload 中位数",
            "baseline_ms": micro["payload_baseline_ms"],
            "current_ms": micro["payload_current_ms"],
            "improvement_pct": micro["payload_improvement_pct"],
            "speedup_x": speedup_x(micro["payload_baseline_ms"], micro["payload_current_ms"]),
            "callout": (
                f"基线来自 2026-03-12 归档 PyTorch reference manifest："
                f"{micro['payload_baseline_ms']:.3f} → {micro['payload_current_ms']:.3f} ms"
            ),
        },
        "end_to_end": {
            "label": "Current 端到端 vs PyTorch 参考均值",
            "baseline_label": "PyTorch 参考单图均值",
            "current_label": "Current 端到端中位数",
            "baseline_ms": micro["end_to_end_baseline_ms"],
            "current_ms": micro["end_to_end_current_ms"],
            "improvement_pct": micro["end_to_end_improvement_pct"],
            "speedup_x": speedup_x(micro["end_to_end_baseline_ms"], micro["end_to_end_current_ms"]),
            "callout": (
                f"Current 正式端到端口径对比 PyTorch 参考："
                f"{micro['end_to_end_baseline_ms']:.3f} → {micro['end_to_end_current_ms']:.3f} ms/image"
            ),
        },
        "trusted_current_sha": performance["artifact_sha"],
    }


def build_inference_sample_catalog() -> list[dict[str, Any]]:
    current_quality = quality_metrics_by_relative_path(str(QUALITY_CURRENT_REPORT))
    baseline_quality = quality_metrics_by_relative_path(str(QUALITY_BASELINE_REPORT))
    catalog: list[dict[str, Any]] = []
    for index, fixture in enumerate(PRERECORDED_SAMPLE_FIXTURES):
        current_entry = current_quality.get(fixture["relative_path"], {})
        baseline_entry = baseline_quality.get(fixture["relative_path"], {})
        catalog.append(
            {
                "index": index,
                "sample_id": fixture["sample_id"],
                "label": fixture["label"],
                "title": fixture["title"],
                "note": fixture["note"],
                "quality_preview": {
                    "current_psnr_db": current_entry.get("psnr_db"),
                    "current_ssim": current_entry.get("ssim"),
                    "baseline_psnr_db": baseline_entry.get("psnr_db"),
                    "baseline_ssim": baseline_entry.get("ssim"),
                },
            }
        )
    return catalog


def build_compare_viewer_sample(image_index: int) -> dict[str, Any]:
    current_payload = build_prerecorded_inference_result(image_index, "current")
    baseline_payload = build_prerecorded_inference_result(image_index, "baseline")
    return {
        "index": image_index,
        "sample": dict(current_payload["sample"]),
        "reference": {
            "label": "参考原图",
            "image_path": current_payload["image_sources"]["original_path"],
        },
        "current": {
            "label": "Current reconstruction",
            "source_label": "Current 归档重建图",
            "execution_mode": current_payload["execution_mode"],
            "image_b64": current_payload["reconstructed_image_b64"],
            "image_path": current_payload["image_sources"]["reconstructed_path"],
            "quality": dict(current_payload["quality"]),
            "fallback_note": (
                "若当前没有匹配本样例的最新 Current 结果，左侧继续显示仓库内已有的 current reconstruction archive。"
            ),
        },
        "baseline": {
            "label": "PyTorch reference",
            "source_label": "PyTorch 参考 archive",
            "execution_mode": baseline_payload["execution_mode"],
            "image_b64": baseline_payload["reconstructed_image_b64"],
            "image_path": baseline_payload["image_sources"]["reconstructed_path"],
            "quality": dict(baseline_payload["quality"]),
            "fallback_note": (
                "若当前没有匹配本样例的基线结果，右侧固定显示 2026-03-12 归档的 PyTorch reference reconstruction。"
            ),
        },
    }


def build_compare_viewer_snapshot() -> dict[str, Any]:
    return {
        "title": "重建结果对照",
        "mode_note": "先提供并排 compare viewer，不宣称已实现交互式 slider。",
        "fallback_note": (
            "compare viewer 优先沿用当前页面内已拿到的同样例 current / baseline 结果；"
            "页面刷新后若系统状态保留最近一次已完成结果，也会继续优先显示；"
            "若没有匹配结果，则明确回退到仓库内已有的 archive/reference 图像。"
        ),
        "samples": [build_compare_viewer_sample(index) for index, _ in enumerate(PRERECORDED_SAMPLE_FIXTURES)],
    }


def build_prerecorded_inference_result(image_index: int, variant: str) -> dict[str, Any]:
    variant_key = variant.lower()
    if image_index < 0 or image_index >= len(PRERECORDED_SAMPLE_FIXTURES):
        raise IndexError("invalid image_index")
    fixture = PRERECORDED_SAMPLE_FIXTURES[image_index]
    comparison = build_comparison_snapshot()
    current_quality = quality_metrics_by_relative_path(str(QUALITY_CURRENT_REPORT))
    baseline_quality = quality_metrics_by_relative_path(str(QUALITY_BASELINE_REPORT))
    reference_baseline = build_pytorch_reference_baseline_snapshot()
    reference_record = pytorch_reference_records_by_relative_path().get(fixture["relative_path"], {})
    quality_entry = (
        current_quality.get(fixture["relative_path"], {})
        if variant_key == "current"
        else baseline_quality.get(fixture["relative_path"], {})
    )
    original_path = fixture["original_path"]
    reconstructed_path = fixture["current_path"] if variant_key == "current" else fixture["baseline_path"]

    total_ms = (
        comparison["end_to_end"]["current_ms"]
        if variant_key == "current"
        else float(reference_record.get("elapsed_ms") or reference_baseline["mean_ms"])
    )
    payload_ms = (
        comparison["payload"]["current_ms"]
        if variant_key == "current"
        else float(reference_record.get("elapsed_ms") or reference_baseline["mean_ms"])
    )
    prep_ms = round(max(total_ms - payload_ms, 0.0), 3)

    stage_timings = [
        {
            "label": "前段准备 / 链路",
            "value_ms": prep_ms,
            "emphasis": "host",
        },
        {
            "label": "板端 payload / 解码",
            "value_ms": payload_ms,
            "emphasis": "board",
        },
        {
            "label": "总计",
            "value_ms": total_ms,
            "emphasis": "total",
        },
    ]

    return {
        "status": "success",
        "execution_mode": "prerecorded" if variant_key == "current" else "reference",
        "source_label": "预录结果" if variant_key == "current" else "PyTorch 参考基线",
        "message": (
            "当前展示使用已校验的预录图像与正式速度报告，可稳定支撑答辩演示。"
            if variant_key == "current"
            else "第三幕基线固定使用 2026-03-12 归档的 PyTorch reference manifest，不再尝试 Baseline TVM live。"
        ),
        "variant": variant_key,
        "image_index": image_index,
        "sample": {
            "sample_id": fixture["sample_id"],
            "label": fixture["label"],
            "title": fixture["title"],
            "note": fixture["note"],
        },
        "image_sources": {
            "original_path": repo_relative(original_path),
            "reconstructed_path": repo_relative(reconstructed_path),
        },
        "original_image_b64": image_data_uri(str(original_path)),
        "reconstructed_image_b64": image_data_uri(str(reconstructed_path)),
        "timings": {
            "payload_ms": round(payload_ms, 3),
            "prepare_ms": prep_ms,
            "total_ms": round(total_ms, 3),
            "stages": stage_timings,
        },
        "quality": {
            "psnr_db": quality_entry.get("psnr_db"),
            "ssim": quality_entry.get("ssim"),
        },
        "artifact_sha": (
            comparison["trusted_current_sha"]
            if variant_key == "current"
            else reference_baseline["generator_ckpt_sha256"] or "pytorch-reference"
        ),
        "evidence": [
            (
                link_entry(QUALITY_CURRENT_REPORT, "质量报告")
                if variant_key == "current"
                else link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考 manifest")
            ),
            link_entry(
                fixture["current_path"] if variant_key == "current" else fixture["baseline_path"],
                "重建图像",
            ),
        ],
    }


def build_fault_catalog() -> list[dict[str, Any]]:
    fit_map = {fit["fit_id"]: fit for fit in build_fit_snapshot()}
    return [
        {
            "fault_type": "wrong_sha",
            "title": "错误 SHA 注入",
            "fit_id": "FIT-01",
            "summary": fit_map["FIT-01"]["scenario"],
        },
        {
            "fault_type": "illegal_param",
            "title": "非法参数注入",
            "fit_id": "FIT-02",
            "summary": fit_map["FIT-02"]["scenario"],
        },
        {
            "fault_type": "heartbeat_timeout",
            "title": "心跳超时注入",
            "fit_id": "FIT-03",
            "summary": fit_map["FIT-03"]["scenario"],
        },
    ]


def build_fault_replay(fault_type: str) -> dict[str, Any]:
    if fault_type == "wrong_sha":
        fit_summary = load_fit_summary(REPORTS_ROOT / "openamp_wrong_sha_fit_20260315_012403" / "fit_summary.json")
        return {
            "status": "injected",
            "execution_mode": "replay",
            "fault_type": fault_type,
            "fit_id": "FIT-01",
            "source_label": "FIT-01 回放模式",
            "message": "未进入真机注入链路，当前播放已校验的 FIT-01 日志序列。",
            "board_response": {
                "decision": "DENY",
                "fault_code": "ARTIFACT_SHA_MISMATCH",
                "guard_state": "READY",
            },
            "guard_state": "READY",
            "last_fault_code": "ARTIFACT_SHA_MISMATCH",
            "status_lamp": "red",
            "log_entries": [
                "[01:24:34] ▶ RPMsg STATUS_REQ，guard=READY",
                "[01:24:34] ▶ 发送 JOB_REQ，expected_sha=...dc0",
                "[01:24:34] ◀ JOB_ACK: DENY，fault=ARTIFACT_SHA_MISMATCH",
                "[01:24:35] ◀ STATUS_RESP: READY，last_fault=ARTIFACT_SHA_MISMATCH",
            ],
            "fit_summary": fit_summary,
        }
    if fault_type == "illegal_param":
        fit_summary = load_fit_summary(REPORTS_ROOT / "openamp_input_contract_fit_20260315_014542" / "fit_summary.json")
        return {
            "status": "injected",
            "execution_mode": "replay",
            "fault_type": fault_type,
            "fit_id": "FIT-02",
            "source_label": "FIT-02 回放模式",
            "message": "未进入真机注入链路，当前播放已校验的 FIT-02 日志序列。",
            "board_response": {
                "decision": "DENY",
                "fault_code": "ILLEGAL_PARAM_RANGE",
                "guard_state": "READY",
            },
            "guard_state": "READY",
            "last_fault_code": "ILLEGAL_PARAM_RANGE",
            "status_lamp": "red",
            "log_entries": [
                "[01:47:41] ▶ RPMsg STATUS_REQ，guard=READY",
                "[01:47:41] ▶ 发送 JOB_REQ，expected_outputs=2",
                "[01:47:41] ◀ JOB_ACK: DENY，fault=ILLEGAL_PARAM_RANGE",
                "[01:47:42] ◀ STATUS_RESP: READY，last_fault=ILLEGAL_PARAM_RANGE",
            ],
            "fit_summary": fit_summary,
        }
    fit_summary = load_fit_summary(REPORTS_ROOT / "openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410" / "fit_summary.json")
    return {
        "status": "injected",
        "execution_mode": "replay",
        "fault_type": fault_type,
        "fit_id": "FIT-03",
        "source_label": "FIT-03 回放模式",
        "message": "未进入真机注入链路，当前播放已校验的 FIT-03 watchdog 修复后日志。",
        "board_response": {
            "decision": "ALLOW",
            "fault_code": "HEARTBEAT_TIMEOUT",
            "guard_state": "READY",
        },
        "guard_state": "READY",
        "last_fault_code": "HEARTBEAT_TIMEOUT",
        "status_lamp": "red",
        "log_entries": [
            "[02:36:17] ▶ STATUS_REQ，guard=READY",
            "[02:36:17] ▶ JOB_REQ -> JOB_ACK(ALLOW)",
            "[02:36:17] ▶ HEARTBEAT -> HEARTBEAT_ACK(ok=1)",
            "[02:36:22] ◀ STATUS_RESP: READY，last_fault=HEARTBEAT_TIMEOUT",
            "[02:36:22] ▶ SAFE_STOP 清理完成，guard 保持 READY",
        ],
        "fit_summary": fit_summary,
    }


def build_recover_replay(last_fault_code: str | None = None) -> dict[str, Any]:
    retained_fault_code = format_fault_code(last_fault_code or "MANUAL_SAFE_STOP")
    return {
        "status": "recovered",
        "execution_mode": "replay",
        "source_label": "SAFE_STOP 收口回放",
        "message": "未进入真机 SAFE_STOP 收口链路，当前展示 READY 保留最近 fault code 的正式证据。",
        "board_response": {
            "decision": "ACK",
            "fault_code": retained_fault_code,
            "guard_state": "READY",
        },
        "guard_state": "READY",
        "last_fault_code": retained_fault_code,
        "status_lamp": "green" if retained_fault_code == "NONE" else "yellow",
        "log_entries": [
            "[02:36:22] ▶ SAFE_STOP 收口，guard 保持 READY",
            f"[02:36:22] ◀ STATUS_RESP: READY，last_fault={retained_fault_code}",
        ],
    }


def build_guided_demo_snapshot() -> dict[str, Any]:
    return {
        "sample_catalog": build_inference_sample_catalog(),
        "comparison": build_comparison_snapshot(),
        "compare_viewer": build_compare_viewer_snapshot(),
        "fault_catalog": build_fault_catalog(),
    }


def build_latest_live_status_snapshot() -> dict[str, Any]:
    reference_baseline = build_pytorch_reference_baseline_snapshot()
    return {
        "title": "最新可用 demo 结论",
        "report_date": "2026-03-17",
        "as_of": "2026-03-17 current live / 2026-03-12 reference baseline",
        "status_label": "Current live 数据面 + PyTorch 参考基线",
        "headline": "Current live 300 / 300；第三幕默认基线切到 PyTorch reference archive",
        "hero_summary": (
            "当前答辩 demo 把 Current live 用作飞腾侧语义视觉回传数据面的在线路径；"
            "第三幕默认基线固定使用 2026-03-12 归档的 PyTorch 参考结果。"
            "2026-03-17 的 dual-path live 结论继续作为历史证据保留。"
        ),
        "summary": (
            "Current 路径继续保留 live 300 / 300 演示。第三幕默认展示 2026-03-12 归档的 "
            "PyTorch reference manifest 与 300 张重建结果；不把 2026-03-17 的 baseline live 历史结论"
            "直接当成本场默认 operator flow。"
        ),
        "valid_instance": "8115",
        "current": {
            "label": "Current live",
            "completed": "300 / 300",
            "note": "最近 live reconstruction 已在 8115 板端成功完成。",
        },
        "baseline": {
            "label": "PyTorch 参考基线",
            "completed": f"{reference_baseline['output_count']} / {reference_baseline['output_count']} (archive)",
            "note": "来源于 2026-03-12 归档 manifest，不触发 baseline TVM live。",
        },
        "board": {
            "label": "板卡在线状态",
            "value": "reachable / remoteproc0=running",
            "note": "/dev/rpmsg0 与 /dev/rpmsg_ctrl0 仍可见，可继续演示。",
        },
        "facts": [
            "8115 是当前唯一该用的 demo 实例。",
            "Current 路径最近一次 live reconstruction 已完成真实 300 / 300。",
            "第三幕默认基线固定改用 2026-03-12 归档的 PyTorch reference 300 / 300。",
            "第二、三幕的数据面展示与 OpenAMP 控制面状态分开表述。",
            "headline performance 统一引用 4-core Linux performance mode；本场 OpenAMP live 属于 3-core Linux + RTOS demo mode。",
        ],
        "boundary_note": (
            "OpenAMP 当前负责 control plane / safety；Current reconstruction 继续走既有数据通路。"
            "headline performance 统一引用 4-core Linux performance mode，本场 live demo 明确属于 "
            "3-core Linux + RTOS demo mode。"
        ),
        "report": link_entry(LATEST_LIVE_DUALPATH_REPORT, "2026-03-17 current live 状态报告"),
        "probe": link_entry(REPORTS_ROOT / "openamp_demo_live_probe_latest.json", "最新在线探板 JSON"),
        "links": [
            link_entry(LATEST_LIVE_DUALPATH_REPORT, "2026-03-17 current live 状态报告"),
            link_entry(REPORTS_ROOT / "openamp_demo_live_probe_latest.json", "最新在线探板 JSON"),
            link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考 manifest"),
        ],
    }


def build_mission_snapshot() -> dict[str, Any]:
    reference_baseline = build_pytorch_reference_baseline_snapshot()
    link_director = build_link_director_catalog()
    job_manifest_gate = build_job_manifest_contract_snapshot()
    archive_timeline = [
        {
            "timestamp": "2026-03-17",
            "lane": "mission",
            "title": "Current live 300 / 300 已归档",
            "summary": "Current 路径的 300 张图 live reconstruction 仍是当前答辩 demo 的有效在线证据。",
            "tone": "online",
            "links": [
                link_entry(LATEST_LIVE_DUALPATH_REPORT, "2026-03-17 current live 状态报告"),
                link_entry(REPORTS_ROOT / "openamp_demo_live_probe_latest.json", "最新在线探板 JSON"),
            ],
        },
        {
            "timestamp": "2026-03-15",
            "lane": "safety",
            "title": "FIT-03 watchdog 修复后 READY 收口",
            "summary": "停发 heartbeat 5 秒后显式暴露 HEARTBEAT_TIMEOUT，并回到 READY。",
            "tone": "warning",
            "links": [
                link_entry(REPORTS_ROOT / "openamp_phase5_fit03_watchdog_success_2026-03-15.md", "FIT-03 修复后摘要"),
                link_entry(
                    REPORTS_ROOT / "openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410" / "remote_probe.json",
                    "FIT-03 修复后远程探板",
                ),
            ],
        },
        {
            "timestamp": "2026-03-15",
            "lane": "device",
            "title": "JOB_DONE 清理路径已确认",
            "summary": "现有板级证据表明：板卡无需重启即可通过 JOB_DONE / SAFE_STOP 回到 READY。",
            "tone": "online",
            "links": [
                link_entry(REPORTS_ROOT / "openamp_phase5_job_done_success_2026-03-15.md", "JOB_DONE 摘要"),
                link_entry(REPORTS_ROOT / "openamp_job_done_real_probe_20260315_001.json", "JOB_DONE 原始探板"),
            ],
        },
        {
            "timestamp": str(reference_baseline["completed_at"] or "")[:10] or "2026-03-12",
            "lane": "reference",
            "title": "PyTorch 参考基线 300 / 300 归档",
            "summary": "第三幕默认基线固定引用归档的 PyTorch reference manifest，不重新走 baseline TVM live。",
            "tone": "neutral",
            "links": [link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考 manifest")],
        },
    ]
    return {
        "title": "任务态势总览",
        "summary": (
            "把 OpenAMP 控制面、语义视觉回传数据面、SAFE_STOP 安全收口和正式性能口径放到同一页，但继续如实分开表述。"
        ),
        "control_plane_note": "OpenAMP / RPMsg 当前只负责 control plane、状态门禁和 SAFE_STOP。",
        "data_plane_note": "Current 与 PyTorch reconstruction 继续走既有数据面，不改后端协议。",
        "mode_split_note": (
            "headline performance 引用 4-core Linux performance mode；本场 live operator flow 明确属于 3-core Linux + RTOS demo mode。"
        ),
        "batch_target": int(reference_baseline["output_count"] or 300),
        "link_director": link_director,
        "job_manifest_gate": job_manifest_gate,
        "archive_timeline": archive_timeline,
    }


def build_operator_snapshot() -> dict[str, Any]:
    return {
        "launch_commands": [
            "bash ./session_bootstrap/scripts/run_openamp_demo.sh",
            (
                "bash ./session_bootstrap/scripts/run_openamp_demo.sh "
                "--port 8090 --probe-env ./session_bootstrap/config/phytium_pi_login.env"
            ),
            (
                "python3 ./session_bootstrap/scripts/probe_openamp_board_status.py "
                "--env ./session_bootstrap/config/phytium_pi_login.env"
            ),
        ],
        "host_side": {
            "summary": (
                "主机侧读取仓库内已保存的控制面证据包、原始 JSON 探板和性能报告；界面把 OpenAMP 控制面与语义回传数据面分开展示，"
                "不额外生成新的业务结论。"
            ),
            "items": [
                link_entry(PACKAGE_ROOT / "summary_report.md", "控制面总报告"),
                link_entry(PACKAGE_ROOT / "coverage_matrix.md", "覆盖矩阵"),
                link_entry(SCRIPTS_ROOT / "openamp_control_wrapper.py", "控制 wrapper"),
                link_entry(SCRIPTS_ROOT / "openamp_rpmsg_bridge.py", "RPMsg bridge"),
            ],
        },
        "slave_side": {
            "summary": (
                "板端 / OpenAMP 侧依赖此前已在真机报告中验证的 live firmware 和 Linux RPMsg 传输。可选在线探板只读取主机名、remoteproc 状态、RPMsg 设备和固件 SHA。"
            ),
            "items": [
                link_entry(REPORTS_ROOT / "openamp_phase5_fit03_watchdog_success_2026-03-15.md", "FIT-03 修复后摘要"),
                link_entry(
                    REPORTS_ROOT / "openamp_heartbeat_timeout_fit_watchdogfix_20260315_023410" / "remote_probe.json",
                    "FIT-03 修复后远程探板",
                ),
                link_entry(SCRIPTS_ROOT / "connect_phytium_pi.sh", "SSH 连接脚本"),
                link_entry(SCRIPTS_ROOT / "probe_openamp_board_status.py", "只读板卡探板"),
            ],
        },
        "entrypoints": [
            link_entry(SCRIPTS_ROOT / "run_openamp_demo.sh", "演示启动脚本"),
            link_entry(SCRIPTS_ROOT / "probe_openamp_board_status.py", "板卡探板 CLI"),
            link_entry(PROJECT_ROOT / "session_bootstrap" / "demo" / "openamp_control_plane_demo" / "README.md", "演示 README"),
        ],
    }


def build_docs_snapshot() -> list[dict[str, Any]]:
    return [
        link_entry(PROJECT_ROOT / "README.md", "项目 README"),
        link_entry(PROJECT_ROOT / "docker" / "README.md", "Docker 复现说明"),
        link_entry(PROJECT_ROOT / "board_deps" / "README.md", "板端依赖说明"),
        link_entry(PACKAGE_ROOT / "summary_report.md", "OpenAMP 控制面总报告"),
        link_entry(PACKAGE_ROOT / "coverage_matrix.md", "OpenAMP 覆盖矩阵"),
        link_entry(PYTORCH_REFERENCE_MANIFEST, "PyTorch 参考基线 manifest"),
    ]


def build_snapshot(
    live_probe: dict[str, Any] | None = None,
    aircraft_position: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = parse_markdown_key_values(PACKAGE_ROOT / "summary_report.md")
    coverage = parse_markdown_key_values(PACKAGE_ROOT / "coverage_matrix.md")
    fits = build_fit_snapshot()
    performance = build_performance_snapshot()

    total_p0 = len(build_milestones_snapshot())
    total_fit_final_pass = sum(1 for fit in fits if fit["status"] == "PASS")

    return {
        "generated_at": now_iso(),
        "project": {
            "name": "飞腾多核弱网安全语义视觉回传系统",
            "focus": "演示层：OpenAMP 控制面与语义回传数据面联动看板",
            "package_id": summary["package_id"],
            "final_verdict": summary["final_verdict"],
            "trusted_current_sha": coverage["trusted_current_sha"],
            "final_live_firmware_sha": coverage["final_live_firmware_sha"],
        },
        "mode": build_mode_snapshot(live_probe),
        "board": build_board_snapshot(live_probe),
        "stats": {
            "p0_milestones_verified": total_p0,
            "fit_final_pass_count": total_fit_final_pass,
            "payload_current_ms": performance["micro_summary"]["payload_current_ms"],
            "end_to_end_current_ms": performance["micro_summary"]["end_to_end_current_ms"],
        },
        "aircraft_position": build_aircraft_position_snapshot(aircraft_position),
        "latest_live_status": build_latest_live_status_snapshot(),
        "weak_network": build_weak_network_snapshot(),
        "milestones": build_milestones_snapshot(),
        "fits": fits,
        "performance": performance,
        "guided_demo": build_guided_demo_snapshot(),
        "mission": build_mission_snapshot(),
        "operator": build_operator_snapshot(),
        "docs": build_docs_snapshot(),
    }
