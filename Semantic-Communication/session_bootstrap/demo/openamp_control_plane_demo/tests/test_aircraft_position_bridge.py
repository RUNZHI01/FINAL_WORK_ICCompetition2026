from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

import aircraft_position_bridge as bridge  # noqa: E402


class FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class AircraftPositionBridgeTest(unittest.TestCase):
    def test_normalize_aircraft_position_payload_accepts_demo_contract_shape(self) -> None:
        payload = bridge.normalize_aircraft_position_payload(
            {
                "position": {"latitude": 31.205, "longitude": 121.551},
                "kinematics": {"heading_deg": 145.0, "ground_speed_kph": 275.5, "altitude_m": 3201.2},
                "fix": {"type": "RTK", "confidence_m": 2.1, "satellites": 19},
                "sample": {
                    "captured_at": "2026-04-11T03:20:00+0800",
                    "sequence": 12,
                },
            },
            source_label="Board GPS live feed",
            producer_id="board-gps-daemon",
        )

        self.assertEqual(payload["source_kind"], "upper_computer_gps")
        self.assertEqual(payload["source_status"], "live")
        self.assertEqual(payload["source_label"], "Board GPS live feed")
        self.assertAlmostEqual(payload["position"]["latitude"], 31.205)
        self.assertAlmostEqual(payload["position"]["longitude"], 121.551)
        self.assertAlmostEqual(payload["kinematics"]["ground_speed_kph"], 275.5)
        self.assertEqual(payload["fix"]["type"], "RTK")
        self.assertEqual(payload["sample"]["sequence"], 12)
        self.assertEqual(payload["sample"]["producer_id"], "board-gps-daemon")

    def test_normalize_aircraft_position_payload_supports_aliases_and_scaling(self) -> None:
        payload = bridge.normalize_aircraft_position_payload(
            {
                "lat": 30.572815,
                "lon": 104.066801,
                "speed": 20.0,
                "altitude": 1820.0,
                "vertical_speed": 1.4,
                "heading": 78.0,
                "satellites": 11,
            },
            ground_speed_scale=3.6,
        )

        self.assertAlmostEqual(payload["position"]["latitude"], 30.572815)
        self.assertAlmostEqual(payload["position"]["longitude"], 104.066801)
        self.assertAlmostEqual(payload["kinematics"]["ground_speed_kph"], 72.0)
        self.assertAlmostEqual(payload["kinematics"]["altitude_m"], 1820.0)
        self.assertAlmostEqual(payload["kinematics"]["vertical_speed_mps"], 1.4)
        self.assertAlmostEqual(payload["kinematics"]["heading_deg"], 78.0)
        self.assertEqual(payload["fix"]["satellites"], 11)

    def test_run_bridge_once_fetches_upstream_and_posts_normalized_payload(self) -> None:
        captured: dict[str, object] = {}
        config = bridge.BridgeConfig(
            upstream_url="http://board.local:9000/gps",
            upstream_candidates=("http://board.local:9000/gps",),
            backend_base_url="http://127.0.0.1:8079",
            interval_sec=1.0,
            timeout_sec=2.0,
            upstream_headers={"Authorization": "Bearer demo"},
            backend_headers={"X-Demo": "1"},
            source_label="Board GPS API live feed",
            source_note="board feed",
            producer_id="board-gps-api-bridge",
            transport="board_http_post",
            aircraft_id="FT-AIR-01",
            mission_call_sign="M9-DEMO",
            ground_speed_scale=3.6,
            altitude_scale=1.0,
            vertical_speed_scale=1.0,
            path_overrides={
                "latitude": "gps.latitude_deg",
                "longitude": "gps.longitude_deg",
                "altitude_m": None,
                "ground_speed_kph": "gps.speed_mps",
                "heading_deg": "gps.heading_deg",
                "vertical_speed_mps": None,
                "fix_type": None,
                "confidence_m": None,
                "satellites": None,
                "captured_at": "meta.captured_at",
                "sequence": "meta.sequence",
            },
        )

        def fake_urlopen(request, timeout: float):
            del timeout
            if request.full_url == "http://board.local:9000/gps":
                self.assertEqual(request.headers["Authorization"], "Bearer demo")
                return FakeHTTPResponse(
                    {
                        "gps": {
                            "latitude_deg": 31.205,
                            "longitude_deg": 121.551,
                            "speed_mps": 20.0,
                            "heading_deg": 145.0,
                        },
                        "meta": {
                            "captured_at": "2026-04-11T03:25:00+0800",
                            "sequence": 42,
                        },
                    }
                )
            captured["url"] = request.full_url
            captured["headers"] = dict(request.headers.items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeHTTPResponse({"status": "ok", "source_status": "live"})

        with patch("aircraft_position_bridge.urlopen", side_effect=fake_urlopen):
            normalized_payload, backend_response = bridge.run_bridge_once(config)

        self.assertEqual(captured["url"], "http://127.0.0.1:8079/api/aircraft-position")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(captured["headers"]["X-demo"], "1")
        self.assertAlmostEqual(captured["body"]["position"]["latitude"], 31.205)
        self.assertAlmostEqual(captured["body"]["position"]["longitude"], 121.551)
        self.assertAlmostEqual(captured["body"]["kinematics"]["ground_speed_kph"], 72.0)
        self.assertEqual(captured["body"]["sample"]["sequence"], 42)
        self.assertEqual(captured["body"]["sample"]["upstream_url"], "http://board.local:9000/gps")
        self.assertEqual(normalized_payload["aircraft_id"], "FT-AIR-01")
        self.assertEqual(backend_response["status"], "ok")

    def test_run_bridge_once_auto_discovers_first_usable_upstream_candidate(self) -> None:
        captured: dict[str, object] = {}
        config = bridge.BridgeConfig(
            upstream_url="",
            upstream_candidates=(
                "http://127.0.0.1:9000/gps",
                "http://127.0.0.1:9527/api/v1/position",
            ),
            backend_base_url="http://127.0.0.1:8079",
            interval_sec=1.0,
            timeout_sec=2.0,
            upstream_headers={},
            backend_headers={},
            source_label="Board GPS API live feed",
            source_note="board feed",
            producer_id="board-gps-api-bridge",
            transport="board_http_post",
            aircraft_id=None,
            mission_call_sign=None,
            ground_speed_scale=1.0,
            altitude_scale=1.0,
            vertical_speed_scale=1.0,
            path_overrides={field_name: None for field_name in bridge.FIELD_PATH_CANDIDATES},
        )

        def fake_urlopen(request, timeout: float):
            del timeout
            if request.full_url == "http://127.0.0.1:9000/gps":
                raise bridge.URLError("connection refused")
            if request.full_url == "http://127.0.0.1:9527/api/v1/position":
                return FakeHTTPResponse({"position": {"latitude": 31.205, "longitude": 121.551}})
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeHTTPResponse({"status": "ok"})

        with patch("aircraft_position_bridge.urlopen", side_effect=fake_urlopen):
            normalized_payload, backend_response = bridge.run_bridge_once(config)

        self.assertEqual(captured["url"], "http://127.0.0.1:8079/api/aircraft-position")
        self.assertEqual(captured["body"]["sample"]["upstream_url"], "http://127.0.0.1:9527/api/v1/position")
        self.assertAlmostEqual(normalized_payload["position"]["latitude"], 31.205)
        self.assertEqual(backend_response["status"], "ok")

    def test_config_from_args_accepts_environment_defaults(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "http://board.local:9000/gps",
                "AIRCRAFT_POSITION_BACKEND_BASE_URL": "http://demo-host:8079",
                "AIRCRAFT_POSITION_INTERVAL_SEC": "2.5",
                "AIRCRAFT_POSITION_TIMEOUT_SEC": "4.5",
                "AIRCRAFT_POSITION_UPSTREAM_HEADERS_JSON": json.dumps({"Authorization": "Bearer env-token"}),
                "AIRCRAFT_POSITION_BACKEND_HEADERS_JSON": json.dumps({"X-Demo": "env"}),
                "AIRCRAFT_POSITION_SOURCE_LABEL": "Env GPS",
                "AIRCRAFT_POSITION_AIRCRAFT_ID": "FT-ENV-01",
                "AIRCRAFT_POSITION_MISSION_CALL_SIGN": "MISSION-ENV",
                "AIRCRAFT_POSITION_GROUND_SPEED_SCALE": "3.6",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "gps.lat",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "gps.lon",
            },
            clear=False,
        ):
            args = bridge.build_arg_parser().parse_args([])
            config = bridge._config_from_args(args)

        self.assertEqual(config.upstream_url, "http://board.local:9000/gps")
        self.assertEqual(config.upstream_candidates, ("http://board.local:9000/gps",))
        self.assertEqual(config.backend_base_url, "http://demo-host:8079")
        self.assertAlmostEqual(config.interval_sec, 2.5)
        self.assertAlmostEqual(config.timeout_sec, 4.5)
        self.assertEqual(config.upstream_headers["Authorization"], "Bearer env-token")
        self.assertEqual(config.backend_headers["X-Demo"], "env")
        self.assertEqual(config.source_label, "Env GPS")
        self.assertEqual(config.aircraft_id, "FT-ENV-01")
        self.assertEqual(config.mission_call_sign, "MISSION-ENV")
        self.assertAlmostEqual(config.ground_speed_scale, 3.6)
        self.assertEqual(config.path_overrides["latitude"], "gps.lat")
        self.assertEqual(config.path_overrides["longitude"], "gps.lon")

    def test_build_config_from_env_values_uses_conservative_default_interval(self) -> None:
        config = bridge.build_config_from_env_values(
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "http://board.local:9000/gps",
            }
        )

        self.assertEqual(config.upstream_url, "http://board.local:9000/gps")
        self.assertAlmostEqual(config.interval_sec, 30.0)

    def test_config_from_args_uses_candidate_list_when_explicit_upstream_missing(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AIRCRAFT_POSITION_UPSTREAM_CANDIDATES_JSON": json.dumps(
                    ["http://127.0.0.1:9000/gps", "http://127.0.0.1:9527/api/v1/position"]
                ),
                "AIRCRAFT_POSITION_BACKEND_BASE_URL": "http://demo-host:8079",
            },
            clear=False,
        ):
            args = bridge.build_arg_parser().parse_args([])
            config = bridge._config_from_args(args)

        self.assertEqual(config.upstream_url, "")
        self.assertEqual(
            config.upstream_candidates,
            ("http://127.0.0.1:9000/gps", "http://127.0.0.1:9527/api/v1/position"),
        )

    def test_build_config_from_env_values_supports_baidu_ip_location_shape(self) -> None:
        config = bridge.build_config_from_env_values(
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "AIRCRAFT_POSITION_SOURCE_LABEL": "百度IP定位",
                "AIRCRAFT_POSITION_SOURCE_NOTE": "本机公网出口定位",
                "AIRCRAFT_POSITION_PRODUCER_ID": "baidu-ip-location-bridge",
                "AIRCRAFT_POSITION_TRANSPORT": "baidu_http_get",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
            }
        )

        self.assertEqual(
            config.upstream_url,
            "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
        )
        self.assertEqual(config.path_overrides["latitude"], "content.point.y")
        self.assertEqual(config.path_overrides["longitude"], "content.point.x")
        self.assertEqual(config.source_label, "百度IP定位")

    def test_fetch_normalized_payload_supports_baidu_ip_location_shape(self) -> None:
        config = bridge.build_config_from_env_values(
            {
                "AIRCRAFT_POSITION_UPSTREAM_URL": "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
                "AIRCRAFT_POSITION_LATITUDE_PATH": "content.point.y",
                "AIRCRAFT_POSITION_LONGITUDE_PATH": "content.point.x",
                "AIRCRAFT_POSITION_SOURCE_LABEL": "百度IP定位",
            }
        )

        def fake_urlopen(request, timeout: float):
            del timeout
            self.assertEqual(
                request.full_url,
                "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
            )
            return FakeHTTPResponse(
                {
                    "status": 0,
                    "content": {
                        "point": {
                            "x": "113.39046499907265",
                            "y": "22.943853029625654",
                        }
                    },
                }
            )

        with patch("aircraft_position_bridge.urlopen", side_effect=fake_urlopen):
            payload = bridge.fetch_normalized_payload(config)

        self.assertAlmostEqual(payload["position"]["latitude"], 22.943853)
        self.assertAlmostEqual(payload["position"]["longitude"], 113.390465)
        self.assertEqual(payload["source_label"], "百度IP定位")
        self.assertEqual(
            payload["sample"]["upstream_url"],
            "https://api.map.baidu.com/location/ip?coor=bd09ll&output=json&ak=demo",
        )


if __name__ == "__main__":
    unittest.main()
