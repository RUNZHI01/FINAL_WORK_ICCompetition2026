from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import re
from types import ModuleType
from typing import Any
import urllib.error
import urllib.request


JsonDict = dict[str, Any]
DEFAULT_OPERATOR_API_BASE = "http://127.0.0.1:8079"
OPERATOR_API_BASE_ENV = "COCKPIT_NATIVE_OPERATOR_API_BASE"
AIRCRAFT_POSITION_MODE_ENV = "COCKPIT_NATIVE_AIRCRAFT_POSITION_MODE"
OPERATOR_LOCATION_LATITUDE_ENV = "COCKPIT_NATIVE_OPERATOR_LATITUDE"
OPERATOR_LOCATION_LONGITUDE_ENV = "COCKPIT_NATIVE_OPERATOR_LONGITUDE"
OPERATOR_LOCATION_LABEL_ENV = "COCKPIT_NATIVE_OPERATOR_LOCATION_LABEL"
OPERATOR_LOCATION_KIND_ENV = "COCKPIT_NATIVE_OPERATOR_LOCATION_KIND"
FLIGHT_LATITUDE_ENV = "COCKPIT_NATIVE_FLIGHT_LATITUDE"
FLIGHT_LONGITUDE_ENV = "COCKPIT_NATIVE_FLIGHT_LONGITUDE"
FLIGHT_SOURCE_LABEL_ENV = "COCKPIT_NATIVE_FLIGHT_SOURCE_LABEL"
FLIGHT_SOURCE_KIND_ENV = "COCKPIT_NATIVE_FLIGHT_SOURCE_KIND"


def _degradation_tone(status: JsonDict | None) -> str:
    if status is None:
        return "neutral"
    mode = str(status.get("current_mode") or "FULL_FRAME")
    if mode == "ALERT_ONLY":
        return "warning"
    if mode == "ROI_ONLY":
        return "degraded"
    return "online"


def _degradation_summary_text(status: JsonDict | None) -> str:
    if status is None:
        return "退化引擎未接入。"
    mode = str(status.get("current_mode") or "FULL_FRAME")
    strategy = str(status.get("payload_strategy") or "full_latent")
    transitions = int(status.get("mode_transitions") or 0)
    if bool(status.get("is_link_lost")):
        return f"链路丢失，当前模式 {mode}（仅告警），已发生 {transitions} 次模式切换。"
    return f"当前模式 {mode}，发送策略 {strategy}，已发生 {transitions} 次模式切换。"


@dataclass(frozen=True)
class RepoContractPaths:
    project_root: Path
    demo_data_path: Path
    archive_root: Path


@dataclass(frozen=True)
class NativeContractBundle:
    snapshot_path: Path
    snapshot: JsonDict
    aircraft_position: JsonDict
    weak_network: JsonDict
    ui_state: JsonDict

    def as_dict(self) -> JsonDict:
        return {
            "snapshot_path": str(self.snapshot_path),
            "snapshot": self.snapshot,
            "aircraft_position": self.aircraft_position,
            "weak_network": self.weak_network,
            "ui_state": self.ui_state,
        }


class DemoRepoAdapter:
    def __init__(self, project_root: Path | None = None) -> None:
        resolved_root = (project_root or Path(__file__).resolve().parent.parent).resolve()
        self.paths = RepoContractPaths(
            project_root=resolved_root,
            demo_data_path=resolved_root / "session_bootstrap" / "demo" / "openamp_control_plane_demo" / "demo_data.py",
            archive_root=resolved_root
            / "session_bootstrap"
            / "demo"
            / "openamp_control_plane_demo"
            / "runtime"
            / "event_archives",
        )
        self._validate_sources()

    def _validate_sources(self) -> None:
        if not self.paths.demo_data_path.is_file():
            raise FileNotFoundError(f"Missing demo data source: {self.paths.demo_data_path}")
        if not self.paths.archive_root.is_dir():
            raise FileNotFoundError(f"Missing event archive root: {self.paths.archive_root}")

    def _report_path(self, relative: str) -> Path:
        return self.paths.project_root / relative

    @lru_cache(maxsize=1)
    def _demo_data_module(self) -> ModuleType:
        module_name = "_cockpit_native_demo_data"
        spec = importlib.util.spec_from_file_location(module_name, self.paths.demo_data_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load demo data module from {self.paths.demo_data_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def latest_snapshot_path(self) -> Path:
        candidates = sorted(self.paths.archive_root.glob("session_*/state_snapshot.json"))
        if not candidates:
            raise FileNotFoundError(f"No archive snapshots found under {self.paths.archive_root}")
        return max(candidates, key=lambda path: (path.parent.name, path.stat().st_mtime_ns))

    def load_snapshot(self) -> tuple[Path, JsonDict]:
        snapshot_path = self.latest_snapshot_path()
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        return snapshot_path, payload

    def load_aircraft_position_contract(self) -> JsonDict:
        aircraft_position = self._load_aircraft_position_source()
        return self._apply_aircraft_position_override(aircraft_position)

    def _aircraft_position_mode(self) -> str:
        candidate = str(os.environ.get(AIRCRAFT_POSITION_MODE_ENV, "") or "").strip().lower()
        return candidate if candidate in {"auto", "live", "repo"} else "auto"

    def _operator_api_base(self) -> str:
        candidate = str(os.environ.get(OPERATOR_API_BASE_ENV, "") or "").strip()
        if not candidate:
            return DEFAULT_OPERATOR_API_BASE
        if "://" not in candidate:
            candidate = "http://" + candidate
        return candidate.rstrip("/")

    def operator_api_base(self) -> str:
        return self._operator_api_base()

    def _load_live_aircraft_position_contract(self) -> JsonDict | None:
        request = urllib.request.Request(
            self._operator_api_base() + "/api/aircraft-position",
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=1.2) as response:
                body = response.read()
        except (urllib.error.URLError, TimeoutError, ValueError):
            return None
        if not body:
            return None
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return dict(payload) if isinstance(payload, dict) else None

    def _load_repo_aircraft_position_contract(self) -> JsonDict:
        demo_data = self._demo_data_module()
        return dict(demo_data.build_aircraft_position_snapshot())

    def _load_aircraft_position_source(self) -> JsonDict:
        mode = self._aircraft_position_mode()
        if mode != "repo":
            live_payload = self._load_live_aircraft_position_contract()
            if live_payload is not None:
                return live_payload
        return self._load_repo_aircraft_position_contract()

    def load_weak_network_contract(self) -> JsonDict:
        demo_data = self._demo_data_module()
        return dict(demo_data.build_weak_network_snapshot())

    def load_contract_bundle(self, degradation_status: JsonDict | None = None) -> NativeContractBundle:
        snapshot_path, snapshot = self.load_snapshot()
        aircraft_position = self.load_aircraft_position_contract()
        weak_network = self.load_weak_network_contract()
        ui_state = self._build_ui_state(
            snapshot_path=snapshot_path,
            snapshot=snapshot,
            aircraft_position=aircraft_position,
            weak_network=weak_network,
            degradation_status=degradation_status,
        )
        return NativeContractBundle(
            snapshot_path=snapshot_path,
            snapshot=snapshot,
            aircraft_position=aircraft_position,
            weak_network=weak_network,
            ui_state=ui_state,
        )

    def _parse_markdown_key_values(self, path: Path) -> JsonDict:
        if not path.is_file():
            return {}
        pairs: JsonDict = {}
        pattern = re.compile(r"^\s*-\s*([A-Za-z0-9_]+):\s*(.+?)\s*$")
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if not match:
                continue
            key, value = match.groups()
            pairs[key] = value
        return pairs

    def _float_value(self, value: object) -> float | None:
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _build_demo_story(self) -> JsonDict:
        performance_report = self._report_path(
            "session_bootstrap/reports/inference_compare_baseline_vs_currentsafe_rerun_20260311_114828.md"
        )
        parsed = self._parse_markdown_key_values(performance_report)
        baseline_ms = self._float_value(parsed.get("baseline_run_median_ms"))
        current_ms = self._float_value(parsed.get("current_run_median_ms"))
        improvement_pct = self._float_value(parsed.get("improvement_pct"))
        delta_ms = self._float_value(parsed.get("delta_run_median_ms"))

        if baseline_ms is None:
            baseline_ms = 1844.1
        if current_ms is None:
            current_ms = 153.778
        if improvement_pct is None:
            improvement_pct = 91.66
        if delta_ms is None:
            delta_ms = current_ms - baseline_ms

        headline = {
            "baseline_ms": round(baseline_ms, 3),
            "current_ms": round(current_ms, 3),
            "improvement_pct": round(improvement_pct, 2),
            "delta_ms": round(delta_ms, 3),
            "speedup_x": round(baseline_ms / current_ms, 1) if current_ms > 0 else 0.0,
            "label": "Current trusted payload",
            "summary": f"{baseline_ms:.1f} ms -> {current_ms:.3f} ms，Current 相比 baseline 提升 {improvement_pct:.2f}%。",
            "callout": "当前可信结论是 Current 已明显快于 baseline，这一页应直接拿来做演示 headline。",
            "report_path": str(performance_report.relative_to(self.paths.project_root)),
        }

        return {
            "performance_headline": headline,
            "flow": [
                {
                    "step_id": "demo_current",
                    "title": "先打 Current 在线重建",
                    "detail": headline["summary"],
                    "action_id": "current_online_rebuild",
                    "tone": "online",
                },
                {
                    "step_id": "demo_reload",
                    "title": "再讲合同刷新",
                    "detail": "说明座舱不是 mock，点击后会重新读取当前 repo 快照和合同。",
                    "action_id": "reload_contracts",
                    "tone": "neutral",
                },
                {
                    "step_id": "demo_probe",
                    "title": "最后做板卡探测",
                    "detail": "把 live 限制、探测结果和 SAFE_STOP 收口都放在执行页解释。",
                    "action_id": "probe_live_board",
                    "tone": "warning",
                },
            ],
        }

    def _env_float(self, name: str) -> float | None:
        raw_value = str(os.environ.get(name, "") or "").strip()
        if not raw_value:
            return None
        try:
            return float(raw_value)
        except ValueError:
            return None

    def _first_env_float(self, *names: str) -> float | None:
        for name in names:
            resolved = self._env_float(name)
            if resolved is not None:
                return resolved
        return None

    def _env_text(self, name: str) -> str:
        return str(os.environ.get(name, "") or "").strip()

    def _first_env_text(self, *names: str) -> str:
        for name in names:
            resolved = self._env_text(name)
            if resolved:
                return resolved
        return ""

    def _apply_aircraft_position_override(self, aircraft_position: JsonDict) -> JsonDict:
        latitude = self._first_env_float(OPERATOR_LOCATION_LATITUDE_ENV, FLIGHT_LATITUDE_ENV)
        longitude = self._first_env_float(OPERATOR_LOCATION_LONGITUDE_ENV, FLIGHT_LONGITUDE_ENV)
        source_label = self._first_env_text(OPERATOR_LOCATION_LABEL_ENV, FLIGHT_SOURCE_LABEL_ENV)
        source_kind = self._first_env_text(OPERATOR_LOCATION_KIND_ENV, FLIGHT_SOURCE_KIND_ENV)

        if latitude is None and longitude is None and not source_label and not source_kind:
            return aircraft_position

        demo_data = self._demo_data_module()
        payload = json.loads(json.dumps(aircraft_position, ensure_ascii=False))
        position = dict(payload.get("position") or {})
        if latitude is not None:
            position["latitude"] = latitude
        if longitude is not None:
            position["longitude"] = longitude
        payload["position"] = position
        payload["source_label"] = source_label or str(payload.get("source_label") or "Configured operator location")
        payload["source_kind"] = source_kind or "cockpit_config_override"
        payload["source_status"] = "configured"
        payload["source_note"] = (
            "Cockpit-native 当前坐标来自 operator location 环境变量配置，不伪装成 live GPS。"
        )
        return dict(demo_data.build_aircraft_position_snapshot(payload))

    def _build_position_source(self, aircraft_position: JsonDict) -> JsonDict:
        feed_contract = aircraft_position.get("feed_contract") if isinstance(aircraft_position.get("feed_contract"), dict) else {}
        position = aircraft_position.get("position") if isinstance(aircraft_position.get("position"), dict) else {}
        latitude = position.get("latitude")
        longitude = position.get("longitude")
        source_kind = str(aircraft_position.get("source_kind") or feed_contract.get("active_source_kind") or "backend_stub")
        source_status = str(aircraft_position.get("source_status") or "unknown")
        configured_override = source_kind == "cockpit_config_override" or source_status == "configured"
        api_path = str(aircraft_position.get("source_api_path") or feed_contract.get("api_path") or "/api/aircraft-position")
        active_label = str(
            aircraft_position.get("source_label")
            if configured_override
            else (feed_contract.get("active_source_label") or aircraft_position.get("source_label") or "Backend Stub Contract")
        )
        if configured_override:
            configured_by = (
                "env override: "
                f"{OPERATOR_LOCATION_LATITUDE_ENV} / {OPERATOR_LOCATION_LONGITUDE_ENV} / {OPERATOR_LOCATION_LABEL_ENV}"
            )
            summary = "当前位置来自 cockpit_native operator location 配置，不是实时上位机 GPS。"
        elif source_kind == "upper_computer_gps":
            configured_by = f"upper-computer GPS -> {api_path}"
            summary = "真实位置应由上位机 GPS 通过既有 aircraft-position contract 推送。"
        else:
            configured_by = "repo contract: aircraft_position.v1 default sample"
            summary = (
                "仓库当前没有 live aircraft feed；页面明确使用 repo-backed stub telemetry 默认样例坐标。"
            )
        coordinate_text = "--"
        if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
            coordinate_text = f"{float(latitude):.6f}°, {float(longitude):.6f}°"
        return {
            "label": active_label,
            "kind": source_kind,
            "status": source_status,
            "configured_by": configured_by,
            "api_path": api_path,
            "coordinate_text": coordinate_text,
            "summary": summary,
            "override_hint": (
                f"可通过 {OPERATOR_LOCATION_LATITUDE_ENV} / {OPERATOR_LOCATION_LONGITUDE_ENV} / "
                f"{OPERATOR_LOCATION_LABEL_ENV} 覆盖；旧变量 {FLIGHT_LATITUDE_ENV} / "
                f"{FLIGHT_LONGITUDE_ENV} / {FLIGHT_SOURCE_LABEL_ENV} 仍兼容，"
                f"或继续沿用 {api_path}。"
            ),
        }

    def _build_ui_state(
        self,
        *,
        snapshot_path: Path,
        snapshot: JsonDict,
        aircraft_position: JsonDict,
        weak_network: JsonDict,
        degradation_status: JsonDict | None = None,
    ) -> JsonDict:
        aggregate = snapshot.get("aggregate") if isinstance(snapshot.get("aggregate"), dict) else {}
        jobs = aggregate.get("jobs") if isinstance(aggregate.get("jobs"), dict) else {}
        heartbeat = aggregate.get("heartbeat") if isinstance(aggregate.get("heartbeat"), dict) else {}
        link_profile = aggregate.get("link_profile") if isinstance(aggregate.get("link_profile"), dict) else {}
        aircraft_track = aircraft_position.get("track") if isinstance(aircraft_position.get("track"), list) else []
        weak_network_scenarios = weak_network.get("scenarios") if isinstance(weak_network.get("scenarios"), list) else []
        live_anchor = weak_network.get("live_anchor") if isinstance(weak_network.get("live_anchor"), dict) else {}
        recent_events = snapshot.get("recent_events") if isinstance(snapshot.get("recent_events"), list) else []
        operator_snapshot = snapshot.get("operator") if isinstance(snapshot.get("operator"), dict) else {}
        demo_story = self._build_demo_story()
        operator_launch_commands = [
            str(command) for command in operator_snapshot.get("launch_commands", []) if str(command).strip()
        ]
        operator_launch_command = operator_launch_commands[0] if operator_launch_commands else "bash ./session_bootstrap/scripts/run_openamp_demo.sh"
        last_event = recent_events[0] if recent_events else {}
        position_source = self._build_position_source(aircraft_position)

        left_panel = {
            "title": "系统 / 板态",
            "summary": "当前 OpenAMP 演示证据状态的只读归一化视图。",
            "rows": [
                {"label": "会话", "value": str(aggregate.get("session_id") or "unknown"), "tone": "neutral"},
                {"label": "最近事件", "value": str(aggregate.get("last_event_type") or "unknown"), "tone": "online"},
                {"label": "事件时间", "value": str(aggregate.get("last_event_at") or ""), "tone": "neutral"},
                {
                    "label": "作业统计",
                    "value": (
                        f"已提交 {int(jobs.get('submitted_count') or 0)} / "
                        f"拒绝 {int(jobs.get('rejected_count') or 0)} / "
                        f"完成 {int(jobs.get('done_count') or 0)}"
                    ),
                    "tone": "warning" if int(jobs.get("rejected_count") or 0) else "online",
                },
                {
                    "label": "心跳",
                    "value": str(heartbeat.get("status") or "unknown"),
                    "tone": "online" if str(heartbeat.get("status") or "").lower() == "ok" else "warning",
                },
                {
                    "label": "链路档位",
                    "value": str(link_profile.get("selected_profile_label") or "正常链路"),
                    "tone": "neutral",
                },
                {
                    "label": "退化模式",
                    "value": (
                        str(degradation_status.get("current_mode") or "FULL_FRAME")
                        if degradation_status is not None
                        else "未接入"
                    ),
                    "tone": _degradation_tone(degradation_status),
                },
                {
                    "label": "快照原因",
                    "value": str(snapshot.get("reason") or "unknown"),
                    "tone": "warning",
                },
            ],
            "truth_note": str(snapshot.get("mode_boundary_note") or aggregate.get("mode_boundary_note") or ""),
            "snapshot_path": str(snapshot_path.relative_to(self.paths.project_root)),
        }

        center_panel = {
            "title": "航迹 / 飞机合同",
            "mission_call_sign": str(aircraft_position.get("mission_call_sign") or "M9-DEMO"),
            "aircraft_id": str(aircraft_position.get("aircraft_id") or "FT-AIR-01"),
            "source_label": str(aircraft_position.get("source_label") or ""),
            "source_status": str(aircraft_position.get("source_status") or ""),
            "source_api_path": str(aircraft_position.get("source_api_path") or ""),
            "ownership_note": str(aircraft_position.get("ownership_note") or ""),
            "fallback_note": str(aircraft_position.get("fallback_note") or ""),
            "sample": dict(aircraft_position.get("sample") or {}),
            "feed_contract": dict(aircraft_position.get("feed_contract") or {}),
            "position": dict(aircraft_position.get("position") or {}),
            "position_source": position_source,
            "kinematics": dict(aircraft_position.get("kinematics") or {}),
            "fix": dict(aircraft_position.get("fix") or {}),
            "track": aircraft_track,
            "control_summary": {
                "link_profile": str(link_profile.get("selected_profile_label") or "正常链路"),
                "last_job_id": str(jobs.get("last_job_id") or ""),
                "last_event_message": str(last_event.get("message") or ""),
            },
        }

        right_panel = {
            "title": "弱网对照 / Weak-Network",
            "summary": str(weak_network.get("summary") or ""),
            "truth_note": str(weak_network.get("truth_note") or ""),
            "recommended_scenario_id": str(weak_network.get("recommended_scenario_id") or ""),
            "live_anchor": live_anchor,
            "scenarios": weak_network_scenarios,
        }

        bottom_actions = {
            "title": "操作条 / Action Strip",
            "demo_story": demo_story,
            "actions": [
                {
                    "action_id": "current_online_rebuild",
                    "label": "Current 在线重建",
                    "tone": "online",
                    "enabled": False,
                    "interactive": True,
                    "api_path": "/api/run-inference",
                    "method": "POST",
                    "cta_label": "触发 Current",
                    "note": "尝试调用本机 OpenAMP demo server 的 Current live 重建入口。",
                    "limitation": (
                        f"需要本机 operator server 在线（默认 {DEFAULT_OPERATOR_API_BASE}），"
                        "且该服务内已有会话/板卡凭据。"
                    ),
                    "runtime_state": "待接线",
                },
                {
                    "action_id": "reload_contracts",
                    "label": "重载 cockpit 合同",
                    "tone": "online",
                    "enabled": True,
                    "interactive": True,
                    "cta_label": "立即重载",
                    "note": "重新读取仓库快照与合同构建器。",
                    "runtime_state": "本地可用",
                },
                {
                    "action_id": "probe_live_board",
                    "label": "探测板卡状态",
                    "tone": "neutral",
                    "enabled": False,
                    "interactive": True,
                    "api_path": "/api/probe-board",
                    "method": "POST",
                    "cta_label": "执行探测",
                    "note": "调用 repo 现有只读板卡探测 API，刷新 remoteproc / RPMsg / firmware 状态。",
                    "limitation": "若 operator server 未启动或尚未录入会话凭据，会返回明确限制说明。",
                    "runtime_state": "待接线",
                },
                {
                    "action_id": "recover_safe_stop",
                    "label": "SAFE_STOP 收口",
                    "tone": "warning",
                    "enabled": False,
                    "interactive": True,
                    "api_path": "/api/recover",
                    "method": "POST",
                    "cta_label": "执行收口",
                    "note": "通过 operator server 触发 SAFE_STOP 恢复链路；若 live 不通则返回回放/限制说明。",
                    "limitation": "这不是本地假动作，只有 OpenAMP demo server 在线时才会真正下发恢复。",
                    "runtime_state": "待接线",
                },
                {
                    "action_id": "baseline_live_check",
                    "label": "Baseline 对照刷新",
                    "tone": "neutral",
                    "enabled": False,
                    "interactive": True,
                    "api_path": "/api/run-baseline",
                    "method": "POST",
                    "cta_label": "刷新对照",
                    "note": "调用 baseline 对照入口；若 live baseline 不可用，server 会明确回退到归档/受限状态。",
                    "limitation": "baseline 侧仍受 repo 既有 live/demo 模式约束，不在 native shell 内伪造结果。",
                    "runtime_state": "待接线",
                },
                {
                    "action_id": "show_snapshot_path",
                    "label": "快照路径",
                    "tone": "neutral",
                    "enabled": False,
                    "interactive": False,
                    "note": str(snapshot_path.relative_to(self.paths.project_root)),
                    "runtime_state": "只读",
                },
                {
                    "action_id": "degradation_status",
                    "label": "退化保底状态",
                    "tone": _degradation_tone(degradation_status),
                    "enabled": False,
                    "interactive": False,
                    "note": _degradation_summary_text(degradation_status),
                    "runtime_state": "只读",
                },
            ],
            "footer_note": (
                "Native cockpit 默认入口是 `bash ./session_bootstrap/scripts/run_cockpit_native.sh`；"
                f"live operator API 默认由 `{operator_launch_command}` 提供。"
                "若 operator server 未启动，动作卡仍可点击，但会返回明确的受限状态。"
            ),
            "operator_api_base": DEFAULT_OPERATOR_API_BASE,
            "operator_launch_command": operator_launch_command,
        }

        return {
            "meta": {
                "title": "飞腾原生座舱 / Feiteng Native Cockpit",
                "subtitle": "Qt/QML 原生壳体继续读取仓库现有 TVM/OpenAMP 演示合同，不假设固定分辨率。",
                "project_root": str(self.paths.project_root),
                "snapshot_path": str(snapshot_path),
                "layout_strategy": "adaptive_zones",
                "design_direction": "resolution-independent logical zones with scalable type, spacing, and safe-area padding",
                "launch_hint": "bash ./session_bootstrap/scripts/run_cockpit_native.sh",
                "demo_story": demo_story,
            },
            "zones": {
                "left_status_panel": left_panel,
                "center_tactical_view": center_panel,
                "right_weak_network_panel": right_panel,
                "bottom_action_strip": bottom_actions,
            },
        }
