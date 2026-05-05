from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


DEMO_ROOT = Path(__file__).resolve().parents[1]
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

import board_position_api_service as service  # noqa: E402


class FakeSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.sent: list[bytes] = []

    def settimeout(self, timeout: float) -> None:
        del timeout

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, size: int) -> bytes:
        del size
        if self._chunks:
            return self._chunks.pop(0)
        return b""

    def __enter__(self) -> "FakeSocket":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class BoardPositionApiServiceTest(unittest.TestCase):
    def test_default_nmea_candidates_cover_extended_uart_range(self) -> None:
        self.assertIn("/dev/ttyAMA2", service.DEFAULT_NMEA_DEVICE_CANDIDATES)
        self.assertIn("/dev/ttyAMA3", service.DEFAULT_NMEA_DEVICE_CANDIDATES)
        self.assertIn("/dev/ttyS2", service.DEFAULT_NMEA_DEVICE_CANDIDATES)
        self.assertIn("/dev/ttyS3", service.DEFAULT_NMEA_DEVICE_CANDIDATES)

    def test_console_device_candidates_reads_proc_cmdline(self) -> None:
        with patch(
            "board_position_api_service.Path.read_text",
            return_value="console=ttyAMA1,115200 root=/dev/mmcblk0p1 console=ttyS0,9600",
        ):
            devices = service._console_device_candidates()

        self.assertEqual(devices, ("/dev/ttyAMA1", "/dev/ttyS0"))

    def test_parse_nmea_sentence_supports_gga_and_rmc(self) -> None:
        gga = service.parse_nmea_sentence("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47")
        rmc = service.parse_nmea_sentence("$GPRMC,123519,A,4807.038,N,01131.000,E,10.5,84.4,230394,,*1F")

        self.assertAlmostEqual(gga["latitude"], 48.1173, places=4)
        self.assertAlmostEqual(gga["longitude"], 11.516667, places=4)
        self.assertAlmostEqual(gga["altitude_m"], 545.4, places=1)
        self.assertEqual(gga["satellites"], 8)
        self.assertAlmostEqual(rmc["ground_speed_kph"], 19.446, places=3)
        self.assertAlmostEqual(rmc["heading_deg"], 84.4, places=1)

    def test_query_gpsd_sample_reads_tpv_fix(self) -> None:
        payload = (
            json.dumps({"class": "SKY", "uSat": 11}).encode("utf-8")
            + b"\n"
            + json.dumps(
                {
                    "class": "TPV",
                    "lat": 31.205,
                    "lon": 121.551,
                    "alt": 3201.2,
                    "speed": 20.0,
                    "track": 145.0,
                    "climb": 1.4,
                    "eph": 2.1,
                    "mode": 3,
                    "time": "2026-04-11T05:30:00Z",
                }
            ).encode("utf-8")
            + b"\n"
        )
        fake_socket = FakeSocket([payload])

        with patch("board_position_api_service.socket.create_connection", return_value=fake_socket):
            sample = service.query_gpsd_sample(host="127.0.0.1", port=2947, timeout_sec=1.0)

        self.assertEqual(fake_socket.sent[0], b'?WATCH={"enable":true,"json":true};\n')
        self.assertAlmostEqual(sample["latitude"], 31.205)
        self.assertAlmostEqual(sample["longitude"], 121.551)
        self.assertAlmostEqual(sample["ground_speed_kph"], 72.0)
        self.assertEqual(sample["satellites"], 11)
        self.assertEqual(sample["source"], "gpsd:127.0.0.1:2947")

    def test_collect_position_sample_falls_back_to_nmea(self) -> None:
        config = service.ServiceConfig(
            bind_host="127.0.0.1",
            bind_port=9000,
            gpsd_host="127.0.0.1",
            gpsd_port=2947,
            source_order=("gpsd", "nmea"),
            sample_timeout_sec=1.0,
            nmea_device="/tmp/demo.nmea",
            nmea_baudrate=9600,
            http_upstream_url="",
            http_headers={},
            http_timeout_sec=1.0,
            path_overrides={},
            ground_speed_scale=1.0,
            altitude_scale=1.0,
            vertical_speed_scale=1.0,
        )

        with (
            patch("board_position_api_service.query_gpsd_sample", side_effect=RuntimeError("gpsd down")),
            patch(
                "board_position_api_service.read_nmea_sample",
                return_value={
                    "latitude": 30.572815,
                    "longitude": 104.066801,
                    "ground_speed_kph": 248.0,
                    "source": "nmea:/tmp/demo.nmea",
                },
            ),
        ):
            sample = service.collect_position_sample(config)

        self.assertEqual(sample["source_kind"], "nmea")
        self.assertEqual(sample["source"], "nmea:/tmp/demo.nmea")
        self.assertAlmostEqual(sample["latitude"], 30.572815)

    def test_collect_position_sample_supports_http_upstream(self) -> None:
        config = service.ServiceConfig(
            bind_host="127.0.0.1",
            bind_port=9000,
            gpsd_host="127.0.0.1",
            gpsd_port=2947,
            source_order=("http", "gpsd", "nmea"),
            sample_timeout_sec=1.0,
            nmea_device="",
            nmea_baudrate=9600,
            http_upstream_url="https://api.map.baidu.com/location/ip?ak=demo",
            http_headers={},
            http_timeout_sec=1.0,
            path_overrides={
                "latitude": "content.point.y",
                "longitude": "content.point.x",
            },
            ground_speed_scale=1.0,
            altitude_scale=1.0,
            vertical_speed_scale=1.0,
        )

        with patch(
            "board_position_api_service.query_http_sample",
            return_value={
                "latitude": 22.943853,
                "longitude": 113.390465,
                "source": "http:https://api.map.baidu.com/location/ip?ak=demo",
            },
        ):
            sample = service.collect_position_sample(config)

        self.assertEqual(sample["source_kind"], "http")
        self.assertAlmostEqual(sample["latitude"], 22.943853)
        self.assertIn("api.map.baidu.com", sample["source"])

    def test_read_nmea_sample_configures_baudrate_for_tty_devices(self) -> None:
        attrs = [0, 0, 0, 0, 0, 0, [0] * 32]
        monotonic_values = iter([0.0, 0.0, 0.0, 0.3])

        with tempfile.NamedTemporaryFile() as handle:
            with (
                patch("board_position_api_service.Path.is_file", return_value=False),
                patch("board_position_api_service.os.open", return_value=7),
                patch("board_position_api_service.os.close", return_value=None),
                patch("board_position_api_service.termios.tcgetattr", return_value=attrs),
                patch("board_position_api_service.termios.tcsetattr") as tcsetattr,
                patch("board_position_api_service.select.select", return_value=([], [], [])),
                patch("board_position_api_service.time.monotonic", side_effect=lambda: next(monotonic_values)),
            ):
                with self.assertRaises(RuntimeError):
                    service.read_nmea_sample(explicit_device=handle.name, baudrate=9600, timeout_sec=0.2)

        configured_attrs = tcsetattr.call_args.args[2]
        self.assertEqual(configured_attrs[4], service.termios.B9600)
        self.assertEqual(configured_attrs[5], service.termios.B9600)

    def test_read_nmea_sample_skips_console_and_busy_default_candidates(self) -> None:
        existing_paths = {
            "/dev/ttyAMA1": True,
            "/dev/ttyAMA2": True,
            "/dev/demo.nmea": True,
        }

        def fake_exists(path_self: Path) -> bool:
            return existing_paths.get(str(path_self), False)

        with (
            patch("board_position_api_service.DEFAULT_NMEA_DEVICE_CANDIDATES", ("/dev/ttyAMA1", "/dev/ttyAMA2", "/dev/demo.nmea")),
            patch("board_position_api_service._console_device_candidates", return_value=("/dev/ttyAMA1",)),
            patch("board_position_api_service._device_in_use_by_other_process", side_effect=lambda path: str(path) == "/dev/ttyAMA2"),
            patch("board_position_api_service.Path.exists", autospec=True, side_effect=fake_exists),
            patch("board_position_api_service.Path.is_file", return_value=True),
            patch(
                "board_position_api_service._tail_lines",
                return_value=["$GPRMC,123519,A,4807.038,N,01131.000,E,10.5,84.4,230394,,*1F"],
            ),
        ):
            sample = service.read_nmea_sample(explicit_device="", baudrate=9600, timeout_sec=0.2)

        self.assertEqual(sample["source"], "nmea:/dev/demo.nmea")

    def test_read_nmea_sample_uses_total_timeout_budget_across_candidates(self) -> None:
        attrs = [0, 0, 0, 0, 0, 0, [0] * 32]
        monotonic_values = iter([0.0, 0.0, 0.0, 0.3, 0.3])

        with (
            patch("board_position_api_service.DEFAULT_NMEA_DEVICE_CANDIDATES", ("/dev/ttyAMA2", "/dev/ttyS0")),
            patch("board_position_api_service._console_device_candidates", return_value=()),
            patch("board_position_api_service._device_in_use_by_other_process", return_value=False),
            patch("board_position_api_service.Path.exists", return_value=True),
            patch("board_position_api_service.Path.is_file", return_value=False),
            patch("board_position_api_service.os.open", return_value=7) as open_mock,
            patch("board_position_api_service.os.close", return_value=None),
            patch("board_position_api_service.termios.tcgetattr", return_value=attrs),
            patch("board_position_api_service.termios.tcsetattr"),
            patch("board_position_api_service.time.monotonic", side_effect=lambda: next(monotonic_values)),
        ):
            with self.assertRaises(RuntimeError):
                service.read_nmea_sample(explicit_device="", baudrate=9600, timeout_sec=0.2)

        self.assertEqual(open_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
