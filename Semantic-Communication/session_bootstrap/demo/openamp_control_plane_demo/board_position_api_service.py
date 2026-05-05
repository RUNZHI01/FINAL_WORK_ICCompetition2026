from __future__ import annotations

import argparse
import json
import os
import select
import socket
import termios
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.request import Request, urlopen


ENV_PREFIX = "BOARD_POSITION_API_"
AIRCRAFT_ENV_PREFIX = "AIRCRAFT_POSITION_"
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_BIND_PORT = 9000
DEFAULT_GPSD_HOST = "127.0.0.1"
DEFAULT_GPSD_PORT = 2947
DEFAULT_SOURCE_ORDER = ("gpsd", "nmea")
DEFAULT_SAMPLE_TIMEOUT_SEC = 2.0
DEFAULT_NMEA_BAUDRATE = 9600
DEFAULT_NMEA_DEVICE_CANDIDATES = (
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
    "/dev/ttyACM0",
    "/dev/ttyACM1",
    "/dev/ttyAMA0",
    "/dev/ttyAMA1",
    "/dev/ttyAMA2",
    "/dev/ttyAMA3",
    "/dev/ttyS0",
    "/dev/ttyS1",
    "/dev/ttyS2",
    "/dev/ttyS3",
)
DEFAULT_HTTP_TIMEOUT_SEC = 3.0
HTTP_FIELD_PATH_CANDIDATES: dict[str, tuple[str, ...]] = {
    "latitude": ("position.latitude", "latitude", "lat", "content.point.y"),
    "longitude": ("position.longitude", "longitude", "lon", "lng", "content.point.x"),
    "altitude_m": ("kinematics.altitude_m", "altitude_m", "altitude"),
    "ground_speed_kph": ("kinematics.ground_speed_kph", "ground_speed_kph", "ground_speed", "speed_kph", "speed"),
    "heading_deg": ("kinematics.heading_deg", "heading_deg", "heading", "track"),
    "vertical_speed_mps": ("kinematics.vertical_speed_mps", "vertical_speed_mps", "vertical_speed", "climb"),
    "fix_type": ("fix.type", "fix_type"),
    "confidence_m": ("fix.confidence_m", "confidence_m", "eph"),
    "satellites": ("fix.satellites", "satellites", "uSat"),
    "captured_at": ("sample.captured_at", "captured_at", "timestamp", "time"),
    "sequence": ("sample.sequence", "sequence"),
}


def _termios_baudrate_constant(baudrate: int) -> int | None:
    attr_name = f"B{int(baudrate)}"
    return getattr(termios, attr_name, None)


def _console_device_candidates() -> tuple[str, ...]:
    cmdline_path = Path("/proc/cmdline")
    try:
        raw_text = cmdline_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ()
    devices: list[str] = []
    for token in raw_text.split():
        if not token.startswith("console="):
            continue
        value = token.split("=", 1)[1].split(",", 1)[0].strip()
        if not value:
            continue
        devices.append(value if value.startswith("/dev/") else f"/dev/{value}")
    return tuple(dict.fromkeys(devices))


def _device_in_use_by_other_process(path: Path) -> bool:
    current_pid = os.getpid()
    parent_pid = os.getppid()
    target = str(path)
    proc_root = Path("/proc")
    try:
        proc_entries = list(proc_root.iterdir())
    except OSError:
        return False
    for proc_entry in proc_entries:
        if not proc_entry.name.isdigit():
            continue
        try:
            pid = int(proc_entry.name)
        except ValueError:
            continue
        if pid in {current_pid, parent_pid}:
            continue
        fd_dir = proc_entry / "fd"
        try:
            fd_entries = list(fd_dir.iterdir())
        except OSError:
            continue
        for fd_entry in fd_entries:
            try:
                linked_path = os.readlink(fd_entry)
            except OSError:
                continue
            if linked_path == target:
                return True
    return False


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _env_text(name: str) -> str:
    return str(os.environ.get(name, "") or "").strip()


def _env_text_any(*names: str) -> str:
    for name in names:
        value = _env_text(name)
        if value:
            return value
    return ""


def _env_float(name: str, default: float) -> float:
    raw = _env_text(name)
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = _env_text(name)
    if not raw:
        return default
    return int(raw)


def _parse_csv(raw_value: str) -> tuple[str, ...]:
    values = [part.strip() for part in str(raw_value or "").replace("\n", ",").split(",")]
    return tuple(value for value in values if value)


def _parse_json_dict(raw_value: str) -> dict[str, str]:
    value = str(raw_value or "").strip()
    if not value:
        return {}
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return {str(key): str(val) for key, val in payload.items() if str(key).strip() and val not in (None, "")}


def _clamp_heading(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value % 360.0, 3)


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_nmea_coordinate(raw_value: str, direction: str) -> float | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        numeric = float(value)
    except ValueError:
        return None
    degrees = int(numeric / 100.0)
    minutes = numeric - (degrees * 100.0)
    decimal = degrees + (minutes / 60.0)
    if direction.upper() in {"S", "W"}:
        decimal = -decimal
    return round(decimal, 6)


def parse_nmea_sentence(line: str) -> dict[str, Any] | None:
    stripped = str(line or "").strip()
    if not stripped.startswith("$") or "*" not in stripped:
        return None
    sentence = stripped[1:].split("*", 1)[0]
    parts = sentence.split(",")
    if not parts:
        return None
    sentence_type = parts[0].upper()
    if sentence_type.endswith("GGA") and len(parts) >= 10:
        latitude = _parse_nmea_coordinate(parts[2], parts[3])
        longitude = _parse_nmea_coordinate(parts[4], parts[5])
        if latitude is None or longitude is None:
            return None
        return {
            "latitude": latitude,
            "longitude": longitude,
            "altitude_m": _parse_float(parts[9]),
            "satellites": _parse_int(parts[7]),
            "fix_quality": _parse_int(parts[6]),
            "source_kind": "nmea_gga",
        }
    if sentence_type.endswith("RMC") and len(parts) >= 9:
        if str(parts[2] or "").upper() != "A":
            return None
        latitude = _parse_nmea_coordinate(parts[3], parts[4])
        longitude = _parse_nmea_coordinate(parts[5], parts[6])
        if latitude is None or longitude is None:
            return None
        speed_knots = _parse_float(parts[7])
        track_deg = _parse_float(parts[8])
        return {
            "latitude": latitude,
            "longitude": longitude,
            "ground_speed_kph": round(speed_knots * 1.852, 3) if speed_knots is not None else None,
            "heading_deg": _clamp_heading(track_deg),
            "source_kind": "nmea_rmc",
        }
    return None


def _merge_sample(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in incoming.items():
        if value in (None, ""):
            continue
        merged[key] = value
    return merged


def _extract_path(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _field_value(upstream_payload: dict[str, Any], *, field_name: str, override_path: str | None) -> Any:
    if override_path:
        return _extract_path(upstream_payload, override_path)
    for path in HTTP_FIELD_PATH_CANDIDATES[field_name]:
        value = _extract_path(upstream_payload, path)
        if value not in (None, ""):
            return value
    return None


def _apply_scale(value: float | None, scale: float) -> float | None:
    if value is None:
        return None
    return value * scale


def _tail_lines(path: Path, *, limit: int = 50) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-limit:]


def read_nmea_sample(
    *,
    explicit_device: str,
    baudrate: int,
    timeout_sec: float,
) -> dict[str, Any]:
    candidate_paths = (explicit_device,) if explicit_device else DEFAULT_NMEA_DEVICE_CANDIDATES
    console_devices = set() if explicit_device else set(_console_device_candidates())
    overall_deadline = time.monotonic() + max(timeout_sec, 0.2)
    last_error = "nmea source unavailable"
    for raw_path in candidate_paths:
        remaining_budget = overall_deadline - time.monotonic()
        if remaining_budget <= 0:
            break
        path = Path(raw_path).expanduser()
        if not path.exists():
            last_error = f"{path} not found"
            continue
        if not explicit_device and str(path) in console_devices:
            last_error = f"{path} skipped because it is configured as the system console"
            continue
        if not explicit_device and _device_in_use_by_other_process(path):
            last_error = f"{path} is already opened by another process"
            continue
        try:
            if path.is_file():
                sample: dict[str, Any] = {}
                for line in _tail_lines(path):
                    parsed = parse_nmea_sentence(line)
                    if parsed:
                        sample = _merge_sample(sample, parsed)
                if sample.get("latitude") is None or sample.get("longitude") is None:
                    last_error = f"{path} does not contain a valid NMEA fix"
                    continue
                sample["source"] = f"nmea:{path}"
                return sample

            fd = os.open(str(path), os.O_RDONLY | os.O_NONBLOCK)
            try:
                attrs = termios.tcgetattr(fd)
                baud_attr = _termios_baudrate_constant(baudrate)
                attrs[0] = termios.IGNPAR
                attrs[1] = 0
                attrs[2] &= ~(getattr(termios, "PARENB", 0) | getattr(termios, "CSTOPB", 0) | termios.CSIZE)
                attrs[2] |= termios.CS8 | termios.CREAD | termios.CLOCAL
                attrs[3] = 0
                if baud_attr is not None:
                    try:
                        termios.cfsetispeed(attrs, baud_attr)
                        termios.cfsetospeed(attrs, baud_attr)
                    except AttributeError:
                        attrs[4] = baud_attr
                        attrs[5] = baud_attr
                attrs[6][termios.VMIN] = 0
                attrs[6][termios.VTIME] = 0
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
            except termios.error:
                pass

            buffer = b""
            deadline = time.monotonic() + max(min(remaining_budget, timeout_sec), 0.2)
            sample = {}
            try:
                while time.monotonic() < deadline:
                    readable, _, _ = select.select([fd], [], [], 0.2)
                    if not readable:
                        continue
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        continue
                    buffer += chunk
                    while b"\n" in buffer:
                        raw_line, buffer = buffer.split(b"\n", 1)
                        parsed = parse_nmea_sentence(raw_line.decode("utf-8", errors="ignore"))
                        if parsed:
                            sample = _merge_sample(sample, parsed)
                            if sample.get("latitude") is not None and sample.get("longitude") is not None:
                                sample["source"] = f"nmea:{path}"
                                return sample
            finally:
                os.close(fd)
            last_error = f"{path} did not produce a valid NMEA fix before timeout"
        except OSError as exc:
            last_error = f"{path}: {exc}"
            continue
    raise RuntimeError(last_error)


def query_gpsd_sample(*, host: str, port: int, timeout_sec: float) -> dict[str, Any]:
    with socket.create_connection((host, port), timeout=max(timeout_sec, 0.2)) as sock:
        sock.settimeout(max(timeout_sec, 0.2))
        sock.sendall(b'?WATCH={"enable":true,"json":true};\n')
        deadline = time.monotonic() + max(timeout_sec, 0.2)
        buffer = b""
        sky_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            chunk = sock.recv(4096)
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                raw_line, buffer = buffer.split(b"\n", 1)
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                klass = str(payload.get("class") or "").upper()
                if klass == "SKY":
                    sky_payload = payload
                    continue
                if klass != "TPV":
                    continue
                latitude = _parse_float(payload.get("lat"))
                longitude = _parse_float(payload.get("lon"))
                if latitude is None or longitude is None:
                    continue
                sample = {
                    "latitude": round(latitude, 6),
                    "longitude": round(longitude, 6),
                    "altitude_m": _parse_float(payload.get("alt")),
                    "ground_speed_kph": (
                        round(float(payload["speed"]) * 3.6, 3)
                        if _parse_float(payload.get("speed")) is not None
                        else None
                    ),
                    "heading_deg": _clamp_heading(_parse_float(payload.get("track"))),
                    "vertical_speed_mps": _parse_float(payload.get("climb")),
                    "confidence_m": _parse_float(payload.get("eph")),
                    "satellites": _parse_int(sky_payload.get("uSat")) or _parse_int(payload.get("satellites")),
                    "fix_type": str(payload.get("mode") or "").strip() or None,
                    "captured_at": str(payload.get("time") or "").strip() or None,
                    "source": f"gpsd:{host}:{port}",
                }
                return sample
    raise RuntimeError(f"gpsd {host}:{port} did not return a valid fix before timeout")


def query_http_sample(
    *,
    upstream_url: str,
    upstream_headers: dict[str, str],
    timeout_sec: float,
    path_overrides: dict[str, str | None],
    ground_speed_scale: float,
    altitude_scale: float,
    vertical_speed_scale: float,
) -> dict[str, Any]:
    if not str(upstream_url or "").strip():
        raise RuntimeError("http upstream not configured")

    request = Request(str(upstream_url).strip(), headers=dict(upstream_headers or {}))
    with urlopen(request, timeout=max(timeout_sec, 0.2)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("http upstream did not return a JSON object")

    latitude = _parse_float(_field_value(payload, field_name="latitude", override_path=path_overrides.get("latitude")))
    longitude = _parse_float(
        _field_value(payload, field_name="longitude", override_path=path_overrides.get("longitude"))
    )
    if latitude is None or longitude is None:
        raise RuntimeError("http upstream did not provide latitude/longitude")

    return {
        "source": f"http:{upstream_url}",
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "altitude_m": (
            round(_apply_scale(
                _parse_float(_field_value(payload, field_name="altitude_m", override_path=path_overrides.get("altitude_m"))),
                altitude_scale,
            ), 3)
            if _field_value(payload, field_name="altitude_m", override_path=path_overrides.get("altitude_m")) not in (None, "")
            else None
        ),
        "ground_speed_kph": (
            round(_apply_scale(
                _parse_float(
                    _field_value(payload, field_name="ground_speed_kph", override_path=path_overrides.get("ground_speed_kph"))
                ),
                ground_speed_scale,
            ), 3)
            if _field_value(payload, field_name="ground_speed_kph", override_path=path_overrides.get("ground_speed_kph")) not in (None, "")
            else None
        ),
        "heading_deg": _clamp_heading(
            _parse_float(_field_value(payload, field_name="heading_deg", override_path=path_overrides.get("heading_deg")))
        ),
        "vertical_speed_mps": (
            round(_apply_scale(
                _parse_float(
                    _field_value(
                        payload,
                        field_name="vertical_speed_mps",
                        override_path=path_overrides.get("vertical_speed_mps"),
                    )
                ),
                vertical_speed_scale,
            ), 3)
            if _field_value(payload, field_name="vertical_speed_mps", override_path=path_overrides.get("vertical_speed_mps")) not in (None, "")
            else None
        ),
        "confidence_m": _parse_float(
            _field_value(payload, field_name="confidence_m", override_path=path_overrides.get("confidence_m"))
        ),
        "satellites": _parse_int(
            _field_value(payload, field_name="satellites", override_path=path_overrides.get("satellites"))
        ),
        "fix_type": _field_value(payload, field_name="fix_type", override_path=path_overrides.get("fix_type")),
        "captured_at": (
            str(_field_value(payload, field_name="captured_at", override_path=path_overrides.get("captured_at"))).strip()
            if _field_value(payload, field_name="captured_at", override_path=path_overrides.get("captured_at")) not in (None, "")
            else None
        ),
        "sequence": _parse_int(
            _field_value(payload, field_name="sequence", override_path=path_overrides.get("sequence"))
        ),
    }


@dataclass
class ServiceConfig:
    bind_host: str
    bind_port: int
    gpsd_host: str
    gpsd_port: int
    source_order: tuple[str, ...]
    sample_timeout_sec: float
    nmea_device: str
    nmea_baudrate: int
    http_upstream_url: str
    http_headers: dict[str, str]
    http_timeout_sec: float
    path_overrides: dict[str, str | None]
    ground_speed_scale: float
    altitude_scale: float
    vertical_speed_scale: float


def collect_position_sample(config: ServiceConfig) -> dict[str, Any]:
    errors: list[str] = []
    for source_name in config.source_order:
        if source_name == "http":
            try:
                sample = query_http_sample(
                    upstream_url=config.http_upstream_url,
                    upstream_headers=config.http_headers,
                    timeout_sec=config.http_timeout_sec,
                    path_overrides=config.path_overrides,
                    ground_speed_scale=config.ground_speed_scale,
                    altitude_scale=config.altitude_scale,
                    vertical_speed_scale=config.vertical_speed_scale,
                )
                sample["source_kind"] = "http"
                return sample
            except Exception as exc:
                errors.append(f"http:{exc}")
                continue
        if source_name == "gpsd":
            try:
                sample = query_gpsd_sample(
                    host=config.gpsd_host,
                    port=config.gpsd_port,
                    timeout_sec=config.sample_timeout_sec,
                )
                sample["source_kind"] = "gpsd"
                return sample
            except Exception as exc:
                errors.append(f"gpsd:{exc}")
                continue
        if source_name == "nmea":
            try:
                sample = read_nmea_sample(
                    explicit_device=config.nmea_device,
                    baudrate=config.nmea_baudrate,
                    timeout_sec=config.sample_timeout_sec,
                )
                sample["source_kind"] = "nmea"
                return sample
            except Exception as exc:
                errors.append(f"nmea:{exc}")
                continue
    raise RuntimeError("; ".join(errors) or "no position source available")


class PositionServiceState:
    def __init__(self, config: ServiceConfig) -> None:
        self._config = config
        self._lock = Lock()
        self._sequence = 0
        self._last_payload: dict[str, Any] | None = None
        self._last_error: str = ""

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self._last_payload is None:
                return {
                    "status": "starting",
                    "source_order": list(self._config.source_order),
                    "last_error": self._last_error or None,
                    "sample": None,
                }
            return {
                "status": "ok",
                "source_order": list(self._config.source_order),
                "last_error": self._last_error or None,
                "sample": dict(self._last_payload),
            }

    def collect(self) -> dict[str, Any]:
        payload = collect_position_sample(self._config)
        with self._lock:
            self._sequence += 1
            sample = {
                "source": payload.get("source"),
                "source_kind": payload.get("source_kind"),
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "altitude_m": payload.get("altitude_m"),
                "ground_speed_kph": payload.get("ground_speed_kph"),
                "heading_deg": payload.get("heading_deg"),
                "vertical_speed_mps": payload.get("vertical_speed_mps"),
                "confidence_m": payload.get("confidence_m"),
                "satellites": payload.get("satellites"),
                "fix_type": payload.get("fix_type"),
                "captured_at": payload.get("captured_at") or now_iso(),
                "sequence": self._sequence,
                "status": "live",
            }
            self._last_payload = sample
            self._last_error = ""
            return dict(sample)

    def record_error(self, message: str) -> None:
        with self._lock:
            self._last_error = str(message or "").strip()


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class PositionRequestHandler(BaseHTTPRequestHandler):
    server: "PositionHTTPServer"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            payload = self.server.app_state.snapshot()
            self._respond(HTTPStatus.OK, payload)
            return
        if self.path == "/api/v1/position":
            try:
                payload = self.server.app_state.collect()
            except Exception as exc:
                message = str(exc or "position source unavailable")
                self.server.app_state.record_error(message)
                self._respond(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "status": "error",
                        "error": message,
                        "source_order": list(self.server.app_state._config.source_order),
                    },
                )
                return
            self._respond(HTTPStatus.OK, payload)
            return
        self._respond(HTTPStatus.NOT_FOUND, {"status": "error", "error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        del format, args

    def _respond(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class PositionHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], app_state: PositionServiceState):
        super().__init__(server_address, PositionRequestHandler)
        self.app_state = app_state


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expose a board-local positioning API for the OpenAMP demo.")
    parser.add_argument("--host", default=_env_text(f"{ENV_PREFIX}BIND_HOST") or DEFAULT_BIND_HOST)
    parser.add_argument("--port", type=int, default=_env_int(f"{ENV_PREFIX}PORT", DEFAULT_BIND_PORT))
    parser.add_argument("--gpsd-host", default=_env_text(f"{ENV_PREFIX}GPSD_HOST") or DEFAULT_GPSD_HOST)
    parser.add_argument("--gpsd-port", type=int, default=_env_int(f"{ENV_PREFIX}GPSD_PORT", DEFAULT_GPSD_PORT))
    parser.add_argument(
        "--source-order",
        default=_env_text(f"{ENV_PREFIX}SOURCE_ORDER") or ",".join(DEFAULT_SOURCE_ORDER),
        help="Comma-separated source order, e.g. http,gpsd,nmea",
    )
    parser.add_argument(
        "--sample-timeout-sec",
        type=float,
        default=_env_float(f"{ENV_PREFIX}SAMPLE_TIMEOUT_SEC", DEFAULT_SAMPLE_TIMEOUT_SEC),
    )
    parser.add_argument("--nmea-device", default=_env_text(f"{ENV_PREFIX}NMEA_DEVICE"))
    parser.add_argument("--nmea-baudrate", type=int, default=_env_int(f"{ENV_PREFIX}NMEA_BAUDRATE", DEFAULT_NMEA_BAUDRATE))
    parser.add_argument(
        "--http-upstream-url",
        default=_env_text_any(f"{ENV_PREFIX}HTTP_UPSTREAM_URL", f"{AIRCRAFT_ENV_PREFIX}UPSTREAM_URL"),
    )
    parser.add_argument(
        "--http-headers-json",
        default=_env_text_any(f"{ENV_PREFIX}HTTP_HEADERS_JSON", f"{AIRCRAFT_ENV_PREFIX}UPSTREAM_HEADERS_JSON"),
    )
    parser.add_argument(
        "--http-timeout-sec",
        type=float,
        default=float(
            _env_text_any(f"{ENV_PREFIX}HTTP_TIMEOUT_SEC", f"{AIRCRAFT_ENV_PREFIX}TIMEOUT_SEC")
            or DEFAULT_HTTP_TIMEOUT_SEC
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    path_overrides = {
        field_name: (
            _env_text_any(
                f"{ENV_PREFIX}HTTP_{field_name.upper()}_PATH",
                f"{AIRCRAFT_ENV_PREFIX}{field_name.upper()}_PATH",
            )
            or None
        )
        for field_name in HTTP_FIELD_PATH_CANDIDATES
    }
    config = ServiceConfig(
        bind_host=str(args.host or DEFAULT_BIND_HOST).strip() or DEFAULT_BIND_HOST,
        bind_port=int(args.port),
        gpsd_host=str(args.gpsd_host or DEFAULT_GPSD_HOST).strip() or DEFAULT_GPSD_HOST,
        gpsd_port=int(args.gpsd_port),
        source_order=_parse_csv(args.source_order) or DEFAULT_SOURCE_ORDER,
        sample_timeout_sec=max(float(args.sample_timeout_sec), 0.2),
        nmea_device=str(args.nmea_device or "").strip(),
        nmea_baudrate=max(int(args.nmea_baudrate), 1200),
        http_upstream_url=str(args.http_upstream_url or "").strip(),
        http_headers=_parse_json_dict(args.http_headers_json),
        http_timeout_sec=max(float(args.http_timeout_sec), 0.2),
        path_overrides=path_overrides,
        ground_speed_scale=float(
            _env_text_any(f"{ENV_PREFIX}HTTP_GROUND_SPEED_SCALE", f"{AIRCRAFT_ENV_PREFIX}GROUND_SPEED_SCALE") or "1.0"
        ),
        altitude_scale=float(
            _env_text_any(f"{ENV_PREFIX}HTTP_ALTITUDE_SCALE", f"{AIRCRAFT_ENV_PREFIX}ALTITUDE_SCALE") or "1.0"
        ),
        vertical_speed_scale=float(
            _env_text_any(f"{ENV_PREFIX}HTTP_VERTICAL_SPEED_SCALE", f"{AIRCRAFT_ENV_PREFIX}VERTICAL_SPEED_SCALE")
            or "1.0"
        ),
    )
    app_state = PositionServiceState(config)
    httpd = PositionHTTPServer((config.bind_host, config.bind_port), app_state)
    print(
        f"[board-position-api] listening on http://{config.bind_host}:{config.bind_port} "
        f"source_order={','.join(config.source_order)}",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
