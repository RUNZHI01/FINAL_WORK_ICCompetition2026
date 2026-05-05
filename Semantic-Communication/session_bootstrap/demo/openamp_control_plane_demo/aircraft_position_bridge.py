from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_SOURCE_LABEL = "Board GPS API live feed"
DEFAULT_SOURCE_NOTE = (
    "Board-side positioning API is currently driving the demo aircraft-position contract."
)
DEFAULT_PRODUCER_ID = "board-gps-api-bridge"
DEFAULT_TRANSPORT = "board_http_post"
DEFAULT_UPSTREAM_CANDIDATE_PORTS = (9000, 9527, 8080)
DEFAULT_UPSTREAM_CANDIDATE_PATHS = (
    "/gps",
    "/position",
    "/location",
    "/api/gps",
    "/api/position",
    "/api/location",
    "/api/v1/gps",
    "/api/v1/position",
    "/api/v1/location",
)
DEFAULT_UPSTREAM_CANDIDATES = tuple(
    f"http://127.0.0.1:{port}{path}"
    for port in DEFAULT_UPSTREAM_CANDIDATE_PORTS
    for path in DEFAULT_UPSTREAM_CANDIDATE_PATHS
)

FIELD_PATH_CANDIDATES: dict[str, tuple[str, ...]] = {
    "latitude": ("position.latitude", "latitude", "lat"),
    "longitude": ("position.longitude", "longitude", "lon", "lng"),
    "altitude_m": ("kinematics.altitude_m", "altitude_m", "altitude"),
    "ground_speed_kph": (
        "kinematics.ground_speed_kph",
        "ground_speed_kph",
        "ground_speed",
        "speed_kph",
        "speed",
    ),
    "heading_deg": ("kinematics.heading_deg", "heading_deg", "heading"),
    "vertical_speed_mps": ("kinematics.vertical_speed_mps", "vertical_speed_mps", "vertical_speed"),
    "fix_type": ("fix.type", "fix_type"),
    "confidence_m": ("fix.confidence_m", "confidence_m"),
    "satellites": ("fix.satellites", "satellites"),
    "captured_at": ("sample.captured_at", "captured_at", "timestamp"),
    "sequence": ("sample.sequence", "sequence"),
}

ENV_PREFIX = "AIRCRAFT_POSITION_"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def _first_present(payload: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value = _extract_path(payload, path)
        if value not in (None, ""):
            return value
    return None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _apply_scale(value: float | None, scale: float) -> float | None:
    if value is None:
        return None
    return value * scale


def _compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", {}, [])}


def _field_value(
    upstream_payload: dict[str, Any],
    *,
    field_name: str,
    override_path: str | None,
) -> Any:
    if override_path:
        return _extract_path(upstream_payload, override_path)
    return _first_present(upstream_payload, *FIELD_PATH_CANDIDATES[field_name])


def normalize_aircraft_position_payload(
    upstream_payload: dict[str, Any],
    *,
    source_label: str = DEFAULT_SOURCE_LABEL,
    source_note: str = DEFAULT_SOURCE_NOTE,
    producer_id: str = DEFAULT_PRODUCER_ID,
    transport: str = DEFAULT_TRANSPORT,
    aircraft_id: str | None = None,
    mission_call_sign: str | None = None,
    path_overrides: dict[str, str | None] | None = None,
    ground_speed_scale: float = 1.0,
    altitude_scale: float = 1.0,
    vertical_speed_scale: float = 1.0,
) -> dict[str, Any]:
    overrides = dict(path_overrides or {})

    latitude = _coerce_float(
        _field_value(upstream_payload, field_name="latitude", override_path=overrides.get("latitude"))
    )
    longitude = _coerce_float(
        _field_value(upstream_payload, field_name="longitude", override_path=overrides.get("longitude"))
    )
    if latitude is None or longitude is None:
        raise ValueError("upstream payload does not provide latitude/longitude")

    altitude_m = _apply_scale(
        _coerce_float(_field_value(upstream_payload, field_name="altitude_m", override_path=overrides.get("altitude_m"))),
        altitude_scale,
    )
    ground_speed_kph = _apply_scale(
        _coerce_float(
            _field_value(upstream_payload, field_name="ground_speed_kph", override_path=overrides.get("ground_speed_kph"))
        ),
        ground_speed_scale,
    )
    heading_deg = _coerce_float(
        _field_value(upstream_payload, field_name="heading_deg", override_path=overrides.get("heading_deg"))
    )
    vertical_speed_mps = _apply_scale(
        _coerce_float(
            _field_value(
                upstream_payload,
                field_name="vertical_speed_mps",
                override_path=overrides.get("vertical_speed_mps"),
            )
        ),
        vertical_speed_scale,
    )
    confidence_m = _coerce_float(
        _field_value(upstream_payload, field_name="confidence_m", override_path=overrides.get("confidence_m"))
    )
    satellites = _coerce_int(
        _field_value(upstream_payload, field_name="satellites", override_path=overrides.get("satellites"))
    )
    fix_type = _field_value(upstream_payload, field_name="fix_type", override_path=overrides.get("fix_type"))
    captured_at = _field_value(
        upstream_payload,
        field_name="captured_at",
        override_path=overrides.get("captured_at"),
    )
    sequence = _coerce_int(
        _field_value(upstream_payload, field_name="sequence", override_path=overrides.get("sequence"))
    )

    sample = _compact_dict(
        {
            "captured_at": str(captured_at).strip() if captured_at not in (None, "") else now_iso(),
            "sequence": sequence,
            "transport": transport,
            "producer_id": producer_id,
        }
    )
    payload = _compact_dict(
        {
            "source_kind": "upper_computer_gps",
            "source_status": "live",
            "source_label": source_label,
            "source_note": source_note,
            "aircraft_id": aircraft_id,
            "mission_call_sign": mission_call_sign,
            "position": {
                "latitude": round(latitude, 6),
                "longitude": round(longitude, 6),
            },
            "kinematics": _compact_dict(
                {
                    "altitude_m": round(altitude_m, 3) if altitude_m is not None else None,
                    "ground_speed_kph": round(ground_speed_kph, 3) if ground_speed_kph is not None else None,
                    "heading_deg": round(heading_deg, 3) if heading_deg is not None else None,
                    "vertical_speed_mps": round(vertical_speed_mps, 3) if vertical_speed_mps is not None else None,
                }
            ),
            "fix": _compact_dict(
                {
                    "type": str(fix_type).strip() if fix_type not in (None, "") else None,
                    "confidence_m": round(confidence_m, 3) if confidence_m is not None else None,
                    "satellites": satellites,
                }
            ),
            "sample": sample,
        }
    )
    return payload


def _parse_json_response(response_body: bytes) -> dict[str, Any] | None:
    text = response_body.decode("utf-8").strip()
    if not text:
        return None
    return json.loads(text)


def fetch_upstream_json(
    upstream_url: str,
    *,
    timeout_sec: float,
    upstream_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request = Request(upstream_url, headers=dict(upstream_headers or {}))
    with urlopen(request, timeout=timeout_sec) as response:
        payload = _parse_json_response(response.read())
    if not isinstance(payload, dict):
        raise ValueError("upstream API did not return a JSON object")
    return payload


def post_aircraft_position(
    backend_base_url: str,
    payload: dict[str, Any],
    *,
    timeout_sec: float,
    backend_headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    base = backend_base_url.rstrip("/")
    request = Request(
        f"{base}/api/aircraft-position",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **dict(backend_headers or {}),
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_sec) as response:
        return _parse_json_response(response.read())


@dataclass
class BridgeConfig:
    upstream_url: str
    upstream_candidates: tuple[str, ...]
    backend_base_url: str
    interval_sec: float
    timeout_sec: float
    upstream_headers: dict[str, str]
    backend_headers: dict[str, str]
    source_label: str
    source_note: str
    producer_id: str
    transport: str
    aircraft_id: str | None
    mission_call_sign: str | None
    ground_speed_scale: float
    altitude_scale: float
    vertical_speed_scale: float
    path_overrides: dict[str, str | None]


def _parse_upstream_candidates(raw_value: str) -> tuple[str, ...]:
    value = str(raw_value or "").strip()
    if not value:
        return ()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        payload = None

    candidates: list[str] = []
    if isinstance(payload, str):
        candidates.append(payload)
    elif isinstance(payload, list):
        candidates.extend(str(item or "").strip() for item in payload)
    else:
        candidates.extend(part.strip() for part in value.replace("\n", ",").split(","))

    deduped: list[str] = []
    seen: set[str] = set()
    for raw_candidate in candidates:
        candidate = str(raw_candidate or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return tuple(deduped)


def _candidate_urls(explicit_upstream_url: str, raw_candidate_config: str = "") -> tuple[str, ...]:
    if explicit_upstream_url:
        return (explicit_upstream_url,)
    env_candidates = _parse_upstream_candidates(raw_candidate_config)
    if env_candidates:
        return env_candidates
    return tuple(DEFAULT_UPSTREAM_CANDIDATES)


def resolve_upstream_source(
    config: BridgeConfig,
) -> tuple[str, dict[str, Any]]:
    attempted: list[dict[str, Any]] = []
    for candidate_url in _candidate_urls(config.upstream_url) if not config.upstream_candidates else config.upstream_candidates:
        try:
            upstream_payload = fetch_upstream_json(
                candidate_url,
                timeout_sec=config.timeout_sec,
                upstream_headers=config.upstream_headers,
            )
            normalize_aircraft_position_payload(
                upstream_payload,
                source_label=config.source_label,
                source_note=config.source_note,
                producer_id=config.producer_id,
                transport=config.transport,
                aircraft_id=config.aircraft_id,
                mission_call_sign=config.mission_call_sign,
                path_overrides=config.path_overrides,
                ground_speed_scale=config.ground_speed_scale,
                altitude_scale=config.altitude_scale,
                vertical_speed_scale=config.vertical_speed_scale,
            )
            return candidate_url, upstream_payload
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            attempted.append({"url": candidate_url, "error": str(exc)})
            continue
    attempted_urls = ", ".join(item["url"] for item in attempted) or "<none>"
    raise ValueError(f"no usable upstream positioning API found; attempted: {attempted_urls}")


def fetch_normalized_payload(config: BridgeConfig) -> dict[str, Any]:
    resolved_upstream_url, upstream_payload = resolve_upstream_source(config)
    normalized_payload = normalize_aircraft_position_payload(
        upstream_payload,
        source_label=config.source_label,
        source_note=config.source_note,
        producer_id=config.producer_id,
        transport=config.transport,
        aircraft_id=config.aircraft_id,
        mission_call_sign=config.mission_call_sign,
        path_overrides=config.path_overrides,
        ground_speed_scale=config.ground_speed_scale,
        altitude_scale=config.altitude_scale,
        vertical_speed_scale=config.vertical_speed_scale,
    )
    normalized_payload.setdefault("sample", {})
    normalized_payload["sample"]["upstream_url"] = resolved_upstream_url
    return normalized_payload


def run_bridge_once(config: BridgeConfig) -> tuple[dict[str, Any], dict[str, Any] | None]:
    normalized_payload = fetch_normalized_payload(config)
    backend_response = post_aircraft_position(
        config.backend_base_url,
        normalized_payload,
        timeout_sec=config.timeout_sec,
        backend_headers=config.backend_headers,
    )
    return normalized_payload, backend_response


def _parse_header_items(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw in values:
        name, sep, value = raw.partition(":")
        if not sep:
            raise ValueError(f"invalid header format: {raw!r}")
        header_name = name.strip()
        header_value = value.strip()
        if not header_name or not header_value:
            raise ValueError(f"invalid header format: {raw!r}")
        headers[header_name] = header_value
    return headers


def _env_text(name: str) -> str:
    return str(os.environ.get(name, "") or "").strip()


def _env_float(name: str, default: float) -> float:
    raw_value = _env_text(name)
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"invalid float environment value for {name}: {raw_value!r}") from exc


def _parse_header_json(raw_value: str) -> dict[str, str]:
    value = str(raw_value or "").strip()
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("header JSON must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("header JSON must be an object")
    headers: dict[str, str] = {}
    for key, item in payload.items():
        header_name = str(key or "").strip()
        header_value = str(item or "").strip()
        if not header_name or not header_value:
            continue
        headers[header_name] = header_value
    return headers


def _mapping_text(mapping: Mapping[str, Any], key: str) -> str:
    return str(mapping.get(key, "") or "").strip()


def build_config_from_env_values(
    env_values: Mapping[str, Any],
    *,
    backend_base_url_default: str = "http://127.0.0.1:8079",
) -> BridgeConfig:
    upstream_url = _mapping_text(env_values, f"{ENV_PREFIX}UPSTREAM_URL")
    raw_candidate_config = _mapping_text(env_values, f"{ENV_PREFIX}UPSTREAM_CANDIDATES_JSON")
    upstream_candidates = _candidate_urls(upstream_url, raw_candidate_config)
    if not upstream_candidates:
        raise ValueError(
            "missing upstream URL; set AIRCRAFT_POSITION_UPSTREAM_URL or AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON"
        )
    return BridgeConfig(
        upstream_url=upstream_url,
        upstream_candidates=upstream_candidates,
        backend_base_url=_mapping_text(env_values, f"{ENV_PREFIX}BACKEND_BASE_URL") or backend_base_url_default,
        interval_sec=max(float(_mapping_text(env_values, f"{ENV_PREFIX}INTERVAL_SEC") or "30.0"), 0.1),
        timeout_sec=max(float(_mapping_text(env_values, f"{ENV_PREFIX}TIMEOUT_SEC") or "3.0"), 0.1),
        upstream_headers=_parse_header_json(_mapping_text(env_values, f"{ENV_PREFIX}UPSTREAM_HEADERS_JSON")),
        backend_headers=_parse_header_json(_mapping_text(env_values, f"{ENV_PREFIX}BACKEND_HEADERS_JSON")),
        source_label=_mapping_text(env_values, f"{ENV_PREFIX}SOURCE_LABEL") or DEFAULT_SOURCE_LABEL,
        source_note=_mapping_text(env_values, f"{ENV_PREFIX}SOURCE_NOTE") or DEFAULT_SOURCE_NOTE,
        producer_id=_mapping_text(env_values, f"{ENV_PREFIX}PRODUCER_ID") or DEFAULT_PRODUCER_ID,
        transport=_mapping_text(env_values, f"{ENV_PREFIX}TRANSPORT") or DEFAULT_TRANSPORT,
        aircraft_id=_mapping_text(env_values, f"{ENV_PREFIX}AIRCRAFT_ID") or None,
        mission_call_sign=_mapping_text(env_values, f"{ENV_PREFIX}MISSION_CALL_SIGN") or None,
        ground_speed_scale=float(_mapping_text(env_values, f"{ENV_PREFIX}GROUND_SPEED_SCALE") or "1.0"),
        altitude_scale=float(_mapping_text(env_values, f"{ENV_PREFIX}ALTITUDE_SCALE") or "1.0"),
        vertical_speed_scale=float(_mapping_text(env_values, f"{ENV_PREFIX}VERTICAL_SPEED_SCALE") or "1.0"),
        path_overrides={
            field_name: _mapping_text(env_values, f"{ENV_PREFIX}{field_name.upper()}_PATH") or None
            for field_name in FIELD_PATH_CANDIDATES
        },
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll a real positioning API and push normalized samples into /api/aircraft-position.",
    )
    parser.add_argument(
        "--upstream-url",
        default="",
        help="Real positioning API URL exposed on the board. Falls back to AIRCRAFT_POSITION_UPSTREAM_URL.",
    )
    parser.add_argument(
        "--backend-base-url",
        default="",
        help="Demo backend base URL. Falls back to AIRCRAFT_POSITION_BACKEND_BASE_URL.",
    )
    parser.add_argument("--interval-sec", type=float, default=None, help="Polling interval for daemon mode.")
    parser.add_argument("--timeout-sec", type=float, default=None, help="HTTP timeout for both upstream and backend.")
    parser.add_argument("--once", action="store_true", help="Fetch and forward one sample, then exit.")
    parser.add_argument(
        "--upstream-header",
        action="append",
        default=[],
        help="Extra upstream HTTP header in 'Name: value' format. Can be repeated.",
    )
    parser.add_argument(
        "--backend-header",
        action="append",
        default=[],
        help="Extra backend HTTP header in 'Name: value' format. Can be repeated.",
    )
    parser.add_argument("--source-label", default="")
    parser.add_argument("--source-note", default="")
    parser.add_argument("--producer-id", default="")
    parser.add_argument("--transport", default="")
    parser.add_argument("--aircraft-id", default="")
    parser.add_argument("--mission-call-sign", default="")
    parser.add_argument("--ground-speed-scale", type=float, default=None)
    parser.add_argument("--altitude-scale", type=float, default=None)
    parser.add_argument("--vertical-speed-scale", type=float, default=None)
    for field_name in FIELD_PATH_CANDIDATES:
        parser.add_argument(
            f"--{field_name.replace('_', '-')}-path",
            default="",
            help=f"Optional dotted path override for {field_name}.",
        )
    return parser


def _config_from_args(args: argparse.Namespace) -> BridgeConfig:
    upstream_url = str(args.upstream_url or "").strip() or _env_text(f"{ENV_PREFIX}UPSTREAM_URL")
    raw_candidate_config = _env_text(f"{ENV_PREFIX}UPSTREAM_CANDIDATES_JSON")
    upstream_candidates = _candidate_urls(upstream_url, raw_candidate_config)
    if not upstream_candidates:
        raise ValueError(
            "missing upstream URL; set --upstream-url / AIRCRAFT_POSITION_UPSTREAM_URL "
            "or AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON"
        )
    backend_base_url = (
        str(args.backend_base_url or "").strip()
        or _env_text(f"{ENV_PREFIX}BACKEND_BASE_URL")
        or "http://127.0.0.1:8079"
    )
    upstream_headers = _parse_header_json(_env_text(f"{ENV_PREFIX}UPSTREAM_HEADERS_JSON"))
    upstream_headers.update(_parse_header_items(list(args.upstream_header)))
    backend_headers = _parse_header_json(_env_text(f"{ENV_PREFIX}BACKEND_HEADERS_JSON"))
    backend_headers.update(_parse_header_items(list(args.backend_header)))
    return BridgeConfig(
        upstream_url=upstream_url,
        upstream_candidates=upstream_candidates,
        backend_base_url=backend_base_url,
        interval_sec=max(
            float(args.interval_sec) if args.interval_sec is not None else _env_float(f"{ENV_PREFIX}INTERVAL_SEC", 30.0),
            0.1,
        ),
        timeout_sec=max(
            float(args.timeout_sec) if args.timeout_sec is not None else _env_float(f"{ENV_PREFIX}TIMEOUT_SEC", 3.0),
            0.1,
        ),
        upstream_headers=upstream_headers,
        backend_headers=backend_headers,
        source_label=str(args.source_label or "").strip() or _env_text(f"{ENV_PREFIX}SOURCE_LABEL") or DEFAULT_SOURCE_LABEL,
        source_note=str(args.source_note or "").strip() or _env_text(f"{ENV_PREFIX}SOURCE_NOTE") or DEFAULT_SOURCE_NOTE,
        producer_id=str(args.producer_id or "").strip() or _env_text(f"{ENV_PREFIX}PRODUCER_ID") or DEFAULT_PRODUCER_ID,
        transport=str(args.transport or "").strip() or _env_text(f"{ENV_PREFIX}TRANSPORT") or DEFAULT_TRANSPORT,
        aircraft_id=str(args.aircraft_id).strip() or _env_text(f"{ENV_PREFIX}AIRCRAFT_ID") or None,
        mission_call_sign=str(args.mission_call_sign).strip() or _env_text(f"{ENV_PREFIX}MISSION_CALL_SIGN") or None,
        ground_speed_scale=(
            float(args.ground_speed_scale)
            if args.ground_speed_scale is not None
            else _env_float(f"{ENV_PREFIX}GROUND_SPEED_SCALE", 1.0)
        ),
        altitude_scale=(
            float(args.altitude_scale)
            if args.altitude_scale is not None
            else _env_float(f"{ENV_PREFIX}ALTITUDE_SCALE", 1.0)
        ),
        vertical_speed_scale=(
            float(args.vertical_speed_scale)
            if args.vertical_speed_scale is not None
            else _env_float(f"{ENV_PREFIX}VERTICAL_SPEED_SCALE", 1.0)
        ),
        path_overrides={
            field_name: (
                str(getattr(args, f"{field_name}_path")).strip()
                or _env_text(f"{ENV_PREFIX}{field_name.upper()}_PATH")
                or None
            )
            for field_name in FIELD_PATH_CANDIDATES
        },
    )


def _print_success(normalized_payload: dict[str, Any], backend_response: dict[str, Any] | None) -> None:
    latitude = normalized_payload["position"]["latitude"]
    longitude = normalized_payload["position"]["longitude"]
    source_label = normalized_payload.get("source_label", DEFAULT_SOURCE_LABEL)
    backend_status = ""
    if isinstance(backend_response, dict):
        backend_status = str(backend_response.get("source_status") or backend_response.get("status") or "").strip()
    print(
        f"[aircraft-position-bridge] pushed lat={latitude:.6f} lon={longitude:.6f} "
        f"source={source_label!r} backend_status={backend_status or 'ok'}",
        flush=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        config = _config_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))

    while True:
        try:
            normalized_payload, backend_response = run_bridge_once(config)
            _print_success(normalized_payload, backend_response)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            print(f"[aircraft-position-bridge] error: {exc}", file=sys.stderr, flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(config.interval_sec)


if __name__ == "__main__":
    raise SystemExit(main())
