from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, MutableMapping, Sequence
import urllib.error
import urllib.request

from .adapter import DemoRepoAdapter
from .availability import is_pyside6_available


def _env_int(name: str) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return 0
    try:
        return max(0, int(raw_value))
    except ValueError:
        return 0


def _resolve_safe_area_insets(overrides: Mapping[str, int] | None = None) -> dict[str, int]:
    resolved = {
        "left": _env_int("COCKPIT_NATIVE_SAFE_AREA_LEFT"),
        "top": _env_int("COCKPIT_NATIVE_SAFE_AREA_TOP"),
        "right": _env_int("COCKPIT_NATIVE_SAFE_AREA_RIGHT"),
        "bottom": _env_int("COCKPIT_NATIVE_SAFE_AREA_BOTTOM"),
    }
    if overrides is None:
        return resolved

    for key in resolved:
        raw_amount = overrides.get(key, resolved[key])
        resolved[key] = max(0, int(raw_amount))
    return resolved


SOFTWARE_RENDER_ENV_VARS = {
    "QT_QUICK_BACKEND": "software",
    "QSG_RHI_BACKEND": "software",
    "QT_OPENGL": "software",
}

OFFSCREEN_CAPTURE_ENV_VARS = {
    "QT_QPA_PLATFORM": "offscreen",
}

MAP_BACKEND_ENV = "COCKPIT_NATIVE_MAP_BACKEND"
MAP_PROVIDER_ENV = "COCKPIT_NATIVE_MAP_PROVIDER"
MAP_TILE_MODE_ENV = "COCKPIT_NATIVE_MAP_TILE_MODE"
MAP_TILE_ROOT_ENV = "COCKPIT_NATIVE_MAP_TILE_ROOT"
MAP_TILE_FORMAT_ENV = "COCKPIT_NATIVE_MAP_TILE_FORMAT"
WORLD_MAP_BACKDROP_ENV = "COCKPIT_NATIVE_WORLD_MAP_BACKDROP"
VALID_MAP_BACKENDS = {"auto", "canvas", "svg", "qtlocation"}
VALID_MAP_PROVIDERS = {"auto", "osm"}
VALID_MAP_TILE_MODES = {"auto", "online", "local_arcgis_cache"}
FONT_FILE_SUFFIXES = {".ttf", ".otf", ".ttc"}
DEFAULT_WORLD_MAP_BACKDROP_RELATIVE_PATH = Path("cockpit_native") / "qml" / "assets" / "world-map-backdrop.svg"
DEFAULT_THEME_PALETTE = {
    "sceneTop": "#07131d",
    "sceneMid": "#0c1d2d",
    "sceneBottom": "#08131d",
    "haloCool": "#1f5f95",
    "haloWarm": "#4d5f84",
    "shellExterior": "#0b1620",
    "shellInterior": "#142331",
    "surfaceRaised": "#132434",
    "surfaceQuiet": "#0d1822",
    "surfaceGlass": "#1a3144",
    "borderSubtle": "#274257",
    "borderStrong": "#5fa0ce",
    "accentIce": "#87ddff",
    "accentGold": "#d9a15a",
    "accentMint": "#46d7a0",
    "accentRose": "#ff728b",
    "textStrong": "#f1f7fb",
    "textPrimary": "#d1deea",
    "textSecondary": "#91a8bb",
    "textMuted": "#5f7384",
    "dataLine": "#153043",
    "dataLineStrong": "#244b63",
    "panelHighlight": "#1d4d6f",
    "panelGlowSoft": "#63c5f2",
    "canopyTop": "#163247",
    "canopyBottom": "#0b141c",
    "accentBlue": "#78b8e0",
    "shellDockTop": "#173146",
    "shellDockMid": "#132433",
    "shellDockBottom": "#0d1822",
}


@dataclass
class QtCockpitRuntime:
    app: Any
    engine: Any
    root_window: Any
    bridge: Any | None = None


def _optional_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def normalize_map_backend(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip().lower()
    return candidate if candidate in VALID_MAP_BACKENDS else "auto"


def normalize_map_provider(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip().lower()
    return candidate if candidate in VALID_MAP_PROVIDERS else "auto"


def normalize_map_tile_mode(raw_value: str | None) -> str:
    candidate = str(raw_value or "").strip().lower()
    return candidate if candidate in VALID_MAP_TILE_MODES else "auto"


def resolve_map_tile_mode(raw_value: str | None, *, tile_root: str | None = None) -> str:
    normalized = normalize_map_tile_mode(raw_value)
    if normalized != "auto":
        return normalized
    return "local_arcgis_cache" if str(tile_root or "").strip() else "online"


def available_qtlocation_providers() -> list[str]:
    if not _optional_module_available("PySide6.QtLocation"):
        return []

    try:
        from PySide6.QtLocation import QGeoServiceProvider

        providers = [str(name) for name in QGeoServiceProvider.availableServiceProviders()]
    except Exception:
        return []
    return sorted(provider for provider in providers if provider)


def resolve_qtlocation_plugin_name(
    raw_value: str | None,
    *,
    available_providers: Sequence[str] | None = None,
) -> str:
    providers_source = available_qtlocation_providers() if available_providers is None else available_providers
    providers = [str(provider) for provider in providers_source if provider]
    preferred = normalize_map_provider(raw_value)
    if preferred != "auto" and preferred in providers:
        return preferred
    if "osm" in providers:
        return "osm"
    return providers[0] if providers else ""


def resolve_optional_repo_path(raw_value: str | None, *, project_root: Path | None = None) -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return ""

    resolved_root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    resolved_path = Path(candidate)
    if not resolved_path.is_absolute():
        resolved_path = resolved_root / resolved_path
    return resolved_path.resolve().as_uri()


def resolve_default_world_map_backdrop(project_root: Path | None = None) -> str:
    resolved_root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    backdrop_path = resolved_root / DEFAULT_WORLD_MAP_BACKDROP_RELATIVE_PATH
    if not backdrop_path.is_file():
        return ""
    return backdrop_path.resolve().as_uri()


def resolve_world_map_backdrop_source(raw_value: str | None, *, project_root: Path | None = None) -> str:
    explicit_source = resolve_optional_repo_path(raw_value, project_root=project_root)
    if explicit_source:
        return explicit_source
    return resolve_default_world_map_backdrop(project_root)


def build_launch_options(
    project_root: Path | None = None,
    *,
    software_render: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    resolved_env = os.environ if env is None else env
    package_root = Path(__file__).resolve().parent
    qtlocation_providers = available_qtlocation_providers()
    map_tile_root = resolve_optional_repo_path(
        resolved_env.get(MAP_TILE_ROOT_ENV),
        project_root=project_root,
    )
    map_tile_format = str(resolved_env.get(MAP_TILE_FORMAT_ENV, "png") or "png").strip().lower() or "png"
    return {
        "softwareRender": bool(software_render),
        "mapBackend": normalize_map_backend(resolved_env.get(MAP_BACKEND_ENV)),
        "mapProvider": normalize_map_provider(resolved_env.get(MAP_PROVIDER_ENV)),
        "mapTileMode": resolve_map_tile_mode(
            resolved_env.get(MAP_TILE_MODE_ENV),
            tile_root=map_tile_root,
        ),
        "mapTileRoot": map_tile_root,
        "mapTileFormat": map_tile_format,
        "qtLocationAvailable": _optional_module_available("PySide6.QtLocation"),
        "qtPositioningAvailable": _optional_module_available("PySide6.QtPositioning"),
        "qtSvgAvailable": _optional_module_available("PySide6.QtSvg"),
        "qtLocationStageAvailable": (package_root / "qml" / "components" / "WorldMapStageQtLocation.qml").is_file(),
        "qtLocationProviders": qtlocation_providers,
        "qtLocationPluginName": resolve_qtlocation_plugin_name(
            resolved_env.get(MAP_PROVIDER_ENV),
            available_providers=qtlocation_providers,
        ),
        "worldMapBackdropSource": resolve_world_map_backdrop_source(
            resolved_env.get(WORLD_MAP_BACKDROP_ENV),
            project_root=project_root,
        ),
    }


def resolve_repo_runtime_cache_root(project_root: Path | None = None) -> str:
    resolved_root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    cache_root = resolved_root / "cockpit_native" / "runtime" / "xdg_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    return str(cache_root)


def apply_repo_runtime_env(
    target: MutableMapping[str, str] | None = None,
    *,
    project_root: Path | None = None,
) -> MutableMapping[str, str]:
    resolved = os.environ if target is None else target
    resolved.setdefault("XDG_CACHE_HOME", resolve_repo_runtime_cache_root(project_root))
    resolved.setdefault("QML_XHR_ALLOW_FILE_READ", "1")
    return resolved


def register_project_fonts(package_root: Path) -> list[str]:
    font_root = package_root / "fonts"
    if not font_root.is_dir():
        return []

    try:
        from PySide6.QtGui import QFontDatabase
    except Exception:
        return []

    registered_families: list[str] = []
    for font_path in sorted(font_root.iterdir()):
        if not font_path.is_file() or font_path.suffix.lower() not in FONT_FILE_SUFFIXES:
            continue
        try:
            font_id = QFontDatabase.addApplicationFont(str(font_path))
        except Exception:
            continue
        if font_id < 0:
            continue
        try:
            registered_families.extend(str(name) for name in QFontDatabase.applicationFontFamilies(font_id) if name)
        except Exception:
            continue
    return sorted(set(registered_families))


def resolve_font_family(preferred_families: Sequence[str], *, available_families: Sequence[str], fallback_family: str) -> str:
    available_lookup = {str(family).casefold(): str(family) for family in available_families if family}
    for family in preferred_families:
        resolved = available_lookup.get(str(family).casefold())
        if resolved:
            return resolved
    return fallback_family


def build_runtime_font_plan(package_root: Path, app: Any) -> dict[str, object]:
    try:
        from PySide6.QtGui import QFontDatabase
    except Exception:
        default_family = str(app.font().family()) if hasattr(app, "font") else "Sans Serif"
        return {
            "registeredFontFamilies": [],
            "displayFontFamily": default_family,
            "uiFontFamily": default_family,
            "monoFontFamily": "Monospace",
        }

    registered_families = register_project_fonts(package_root)
    available_families = [str(name) for name in QFontDatabase().families()]
    default_family = str(app.font().family()) if hasattr(app, "font") else "Sans Serif"
    return {
        "registeredFontFamilies": registered_families,
        "displayFontFamily": resolve_font_family(
            ["Source Han Sans SC", "Noto Sans CJK SC", "Ubuntu Sans", "Ubuntu", "DejaVu Sans"],
            available_families=available_families,
            fallback_family=default_family,
        ),
        "uiFontFamily": resolve_font_family(
            ["Source Han Sans SC", "Noto Sans CJK SC", "Ubuntu Sans", "Ubuntu", "DejaVu Sans"],
            available_families=available_families,
            fallback_family=default_family,
        ),
        "monoFontFamily": resolve_font_family(
            ["Ubuntu Sans Mono", "JetBrains Mono", "Ubuntu Mono", "DejaVu Sans Mono"],
            available_families=available_families,
            fallback_family="Monospace",
        ),
    }


def build_runtime_theme_plan() -> dict[str, object]:
    return {
        "themeProfile": "native_cockpit_runtime_v2",
        "themePalette": dict(DEFAULT_THEME_PALETTE),
    }


def apply_software_renderer_env(target: MutableMapping[str, str] | None = None) -> MutableMapping[str, str]:
    resolved = os.environ if target is None else target
    for key, value in SOFTWARE_RENDER_ENV_VARS.items():
        resolved.setdefault(key, value)
    return resolved


def apply_offscreen_capture_env(target: MutableMapping[str, str] | None = None) -> MutableMapping[str, str]:
    resolved = apply_software_renderer_env(target)
    for key, value in OFFSCREEN_CAPTURE_ENV_VARS.items():
        resolved.setdefault(key, value)
    return resolved


def _configure_renderer(software_render: bool) -> None:
    if not software_render:
        return
    apply_software_renderer_env()


def _create_cockpit_runtime(
    project_root: Path | None = None,
    *,
    software_render: bool = False,
    safe_area_insets: Mapping[str, int] | None = None,
    degradation_engine: object | None = None,
    argv: Sequence[str] | None = None,
) -> QtCockpitRuntime:
    if not is_pyside6_available():
        raise RuntimeError("PySide6 is not available in this environment.")

    software_render = software_render or os.environ.get("COCKPIT_NATIVE_SOFTWARE_FALLBACK_ACTIVE") == "1"
    _configure_renderer(software_render)
    apply_repo_runtime_env(project_root=project_root)

    from PySide6.QtCore import QCoreApplication, QObject, Property, Qt, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

    if software_render and hasattr(Qt, "AA_UseSoftwareOpenGL"):
        QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    if software_render and hasattr(QQuickWindow, "setGraphicsApi"):
        QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Software)

    adapter = DemoRepoAdapter(project_root=project_root)

    class CockpitBridge(QObject):
        stateChanged = Signal()
        actionStateChanged = Signal()

        def __init__(
            self,
            repo_adapter: DemoRepoAdapter,
            publish_state_json: Callable[[str], None],
            *,
            degradation_engine: object | None = None,
        ) -> None:
            super().__init__()
            self._adapter = repo_adapter
            self._publish_state_json = publish_state_json
            self._degradation_engine = degradation_engine
            self._state: dict[str, object] = {}
            self._action_state: dict[str, object] = {
                "busy": False,
                "active_action_id": "",
                "last_action": {},
                "history": [],
            }
            self._refresh_state()

        @Property("QVariant", notify=stateChanged)
        def state(self) -> dict[str, object]:
            return self._state

        @Property(str, notify=stateChanged)
        def stateJson(self) -> str:
            return json.dumps(self._state, ensure_ascii=False)

        @Property("QVariant", notify=actionStateChanged)
        def actionState(self) -> dict[str, object]:
            return self._action_state

        @Property(str, notify=actionStateChanged)
        def actionStateJson(self) -> str:
            return json.dumps(self._action_state, ensure_ascii=False)

        def _refresh_state(self) -> None:
            degradation_status = None
            snapshot_fn = getattr(self._degradation_engine, "snapshot", None)
            if callable(snapshot_fn):
                degradation_status = snapshot_fn()
            self._state = self._adapter.load_contract_bundle(degradation_status=degradation_status).ui_state
            self._publish_state_json(json.dumps(self._state, ensure_ascii=False))

        def _set_action_state(self, payload: dict[str, object]) -> None:
            self._action_state = payload
            self.actionStateChanged.emit()

        def _record_action(
            self,
            summary: dict[str, object],
            *,
            busy: bool = False,
            active_action_id: str = "",
        ) -> None:
            previous_history = self._action_state.get("history")
            history = [summary]
            if isinstance(previous_history, list):
                history.extend(item for item in previous_history if isinstance(item, dict))
            self._set_action_state(
                {
                    "busy": bool(busy),
                    "active_action_id": active_action_id if busy else "",
                    "last_action": summary,
                    "history": history[:8],
                }
            )

        def _action_stamp(self) -> str:
            return datetime.now().strftime("%H:%M:%S")

        def _detail_lines_from_payload(self, payload: Mapping[str, object]) -> list[str]:
            lines: list[str] = []

            def add_line(value: object, *, prefix: str = "") -> None:
                text = str(value or "").strip()
                if text:
                    lines.append(prefix + text)

            add_line(payload.get("request_state"), prefix="state: ")
            add_line(payload.get("execution_mode"), prefix="mode: ")
            add_line(payload.get("source_label"), prefix="source: ")
            add_line(payload.get("variant"), prefix="variant: ")
            add_line(payload.get("job_id"), prefix="job: ")
            add_line(payload.get("guard_state"), prefix="guard: ")
            add_line(payload.get("last_fault_code"), prefix="fault: ")
            add_line(payload.get("status_lamp"), prefix="lamp: ")

            if not lines:
                timings = payload.get("timings")
                if isinstance(timings, Mapping):
                    add_line(timings.get("total_ms"), prefix="total_ms: ")

            return lines[:6]

        def _log_lines_from_payload(self, payload: Mapping[str, object]) -> list[str]:
            raw_logs = payload.get("log_entries")
            if not isinstance(raw_logs, list):
                return []
            lines = [str(item or "").strip() for item in raw_logs if str(item or "").strip()]
            return lines[-4:]

        def _tone_from_payload(self, payload: Mapping[str, object]) -> str:
            lamp = str(payload.get("status_lamp") or "").strip().lower()
            status = str(payload.get("status") or payload.get("request_state") or "").strip().lower()
            if lamp == "red":
                return "danger"
            if lamp == "yellow":
                return "warning"
            if any(marker in status for marker in ("error", "failed", "timeout")):
                return "danger"
            if any(marker in status for marker in ("reject", "denied", "warning", "limited")):
                return "warning"
            if any(marker in status for marker in ("running", "queued", "submitted")):
                return "neutral"
            return "online"

        def _summarize_action(
            self,
            *,
            action_id: str,
            label: str,
            payload: Mapping[str, object],
            status_code: int,
        ) -> dict[str, object]:
            headline = str(payload.get("message") or payload.get("status") or label).strip() or label
            detail = str(payload.get("limitation") or payload.get("note") or "").strip()
            return {
                "action_id": action_id,
                "label": label,
                "timestamp": self._action_stamp(),
                "tone": self._tone_from_payload(payload),
                "status_code": status_code,
                "headline": headline,
                "detail": detail,
                "detail_lines": self._detail_lines_from_payload(payload),
                "log_lines": self._log_lines_from_payload(payload),
            }

        def _invoke_operator_api(
            self,
            *,
            action_id: str,
            api_path: str,
            method: str,
        ) -> tuple[int, dict[str, object]]:
            normalized_method = (method or "POST").strip().upper() or "POST"
            resolved_api_path = str(api_path or "").strip()
            if not resolved_api_path:
                raise RuntimeError("动作缺少 API 路径，无法下发。")
            base = self._adapter.operator_api_base()
            url = resolved_api_path if "://" in resolved_api_path else base + resolved_api_path
            body: dict[str, object] = {}
            if action_id == "current_online_rebuild":
                body = {"image_index": 0, "mode": "current"}
            elif action_id == "baseline_live_check":
                body = {"image_index": 0}

            data = None
            headers = {"Accept": "application/json"}
            if normalized_method != "GET":
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                headers["Content-Type"] = "application/json"

            request = urllib.request.Request(url, data=data, headers=headers, method=normalized_method)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(request, timeout=18.0) as response:
                    status_code = int(response.getcode())
                    raw_body = response.read()
            except urllib.error.HTTPError as exc:
                raw_body = exc.read()
                status_code = int(exc.code)
            except urllib.error.URLError as exc:
                raise RuntimeError(f"无法连接 operator server：{exc.reason}") from exc

            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"operator server 返回了无法解析的响应：HTTP {status_code}") from exc
            if not isinstance(payload, dict):
                raise RuntimeError(f"operator server 返回了非对象响应：HTTP {status_code}")
            return status_code, dict(payload)

        @Slot()
        def reload(self) -> None:
            self._refresh_state()
            self.stateChanged.emit()

        @Slot(str, str, str, str)
        def invokeAction(self, action_id: str, api_path: str, method: str, label: str) -> None:
            resolved_action_id = str(action_id or "").strip()
            resolved_label = str(label or resolved_action_id or "动作").strip()
            if not resolved_action_id:
                self._record_action(
                    {
                        "action_id": "",
                        "label": resolved_label,
                        "timestamp": self._action_stamp(),
                        "tone": "danger",
                        "headline": "缺少动作标识，无法执行。",
                        "detail": "",
                        "detail_lines": [],
                        "log_lines": [],
                        "status_code": 0,
                    }
                )
                return

            self._record_action(
                {
                    "action_id": resolved_action_id,
                    "label": resolved_label,
                    "timestamp": self._action_stamp(),
                    "tone": "neutral",
                    "headline": "正在执行 " + resolved_label,
                    "detail": "请求已下发，等待 operator server 返回。",
                    "detail_lines": [],
                    "log_lines": [],
                    "status_code": 0,
                },
                busy=True,
                active_action_id=resolved_action_id,
            )

            try:
                if resolved_action_id == "reload_contracts":
                    self._refresh_state()
                    self.stateChanged.emit()
                    summary = {
                        "action_id": resolved_action_id,
                        "label": resolved_label,
                        "timestamp": self._action_stamp(),
                        "tone": "online",
                        "headline": "仓库合同已重新载入。",
                        "detail": "当前 UI 状态已按最新 repo-backed snapshot 刷新。",
                        "detail_lines": [],
                        "log_lines": [],
                        "status_code": 200,
                    }
                else:
                    status_code, payload = self._invoke_operator_api(
                        action_id=resolved_action_id,
                        api_path=api_path,
                        method=method,
                    )
                    self._refresh_state()
                    self.stateChanged.emit()
                    summary = self._summarize_action(
                        action_id=resolved_action_id,
                        label=resolved_label,
                        payload=payload,
                        status_code=status_code,
                    )
                self._record_action(summary)
            except Exception as exc:
                self._record_action(
                    {
                        "action_id": resolved_action_id,
                        "label": resolved_label,
                        "timestamp": self._action_stamp(),
                        "tone": "danger",
                        "headline": resolved_label + " 执行失败。",
                        "detail": str(exc),
                        "detail_lines": [],
                        "log_lines": [],
                        "status_code": 0,
                    }
                )

    app_argv = [str(item) for item in (list(argv) if argv is not None else sys.argv[:1])]
    if not app_argv:
        app_argv = ["cockpit_native"]

    app = QGuiApplication(app_argv)
    app.setApplicationName("Feiteng Native Cockpit")
    app.setOrganizationName("CICC0903540")
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("cockpitUiStateJson", "{}")
    package_root = Path(__file__).resolve().parent
    launch_options = build_launch_options(project_root=project_root, software_render=software_render)
    launch_options.update(build_runtime_font_plan(package_root, app))
    launch_options.update(build_runtime_theme_plan())

    def publish_state_json(state_json: str) -> None:
        engine.rootContext().setContextProperty("cockpitUiStateJson", state_json)

    bridge = CockpitBridge(adapter, publish_state_json, degradation_engine=degradation_engine)
    primary_screen = app.primaryScreen()
    screen_metrics = {"width": 2560, "height": 1440, "devicePixelRatio": 1.0}
    if primary_screen is not None:
        available = primary_screen.availableGeometry()
        screen_metrics = {
            "width": int(available.width()),
            "height": int(available.height()),
            "devicePixelRatio": float(primary_screen.devicePixelRatio()),
        }
    engine.rootContext().setContextProperty("cockpitBridge", bridge)
    engine.rootContext().setContextProperty("cockpitBridgeAvailable", True)
    engine.rootContext().setContextProperty("safeAreaInsets", _resolve_safe_area_insets(safe_area_insets))
    engine.rootContext().setContextProperty("screenMetrics", screen_metrics)
    engine.rootContext().setContextProperty("launchOptions", launch_options)

    qml_path = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(str(qml_path))
    if not engine.rootObjects():
        raise RuntimeError(f"Unable to load QML scene: {qml_path}")
    # Keep a strong reference to the bridge on the app/runtime so Qt does not
    # drop the Python QObject after this function returns.
    app._cockpit_bridge = bridge  # type: ignore[attr-defined]
    return QtCockpitRuntime(app=app, engine=engine, root_window=engine.rootObjects()[0], bridge=bridge)


def launch_native_cockpit(
    project_root: Path | None = None,
    *,
    software_render: bool = False,
    safe_area_insets: Mapping[str, int] | None = None,
    degradation_engine: object | None = None,
) -> int:
    runtime = _create_cockpit_runtime(
        project_root=project_root,
        software_render=software_render,
        safe_area_insets=safe_area_insets,
        degradation_engine=degradation_engine,
        argv=sys.argv[:1],
    )
    return runtime.app.exec()


def capture_native_cockpit(
    output_path: Path,
    project_root: Path | None = None,
    *,
    settle_ms: int = 500,
    safe_area_insets: Mapping[str, int] | None = None,
    page_index: int | None = None,
    window_width: int | None = None,
    window_height: int | None = None,
) -> Path:
    apply_offscreen_capture_env()

    runtime = _create_cockpit_runtime(
        project_root=project_root,
        software_render=True,
        safe_area_insets=safe_area_insets,
        argv=["cockpit_native.capture"],
    )
    from PySide6.QtCore import QTimer

    resolved_output = output_path.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    if page_index is not None and hasattr(runtime.root_window, "setProperty"):
        runtime.root_window.setProperty("currentPage", max(0, int(page_index)))
    if window_width and hasattr(runtime.root_window, "setWidth"):
        runtime.root_window.setWidth(max(760, int(window_width)))
    if window_height and hasattr(runtime.root_window, "setHeight"):
        runtime.root_window.setHeight(max(600, int(window_height)))
    runtime.root_window.show()

    failure: list[RuntimeError] = []

    def write_capture() -> None:
        image = runtime.root_window.grabWindow()
        if image.isNull():
            failure.append(RuntimeError("Offscreen cockpit capture produced an empty frame."))
        elif not image.save(str(resolved_output)):
            failure.append(RuntimeError(f"Unable to save cockpit capture to {resolved_output}"))
        runtime.app.quit()

    QTimer.singleShot(max(0, int(settle_ms)), write_capture)
    runtime.app.exec()
    if failure:
        raise failure[0]
    return resolved_output
