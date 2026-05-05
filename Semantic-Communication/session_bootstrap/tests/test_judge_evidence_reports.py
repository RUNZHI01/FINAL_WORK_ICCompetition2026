from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = PROJECT_DIR / "session_bootstrap/scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_quality_matrix_report import build_row
from build_snr_robustness_report import parse_summary_md
from judge_evidence_utils import build_line_chart_svg, load_json, parse_markdown_key_values


class JudgeEvidenceReportTests(unittest.TestCase):
    def test_parse_snr_summary_md_fixture(self) -> None:
        path = PROJECT_DIR / "session_bootstrap/reports/snr_sweep_2026-03-01.md"
        points, sources = parse_summary_md(path)

        self.assertEqual(len(points), 4)
        self.assertEqual([int(point["snr"]) for point in points], [8, 10, 12, 14])
        self.assertTrue(any("full_rpc_armv8_phytium_snr12.md" in item for item in sources))
        regression = next(point for point in points if int(point["snr"]) == 12)
        self.assertEqual(regression["improvement_pct"], -44.35)

    def test_quality_row_reads_real_fixture(self) -> None:
        path = PROJECT_DIR / "session_bootstrap/reports/quality_metrics_20260312_pytorch_vs_tvm_current.json"
        payload = load_json(path)
        row = build_row(path, payload)

        self.assertEqual(row["comparison_label"], "pytorch_vs_tvm_current")
        self.assertEqual(row["compared_image_count"], 300)
        self.assertAlmostEqual(row["psnr"]["aggregate_mean"], 35.6942, places=4)
        self.assertAlmostEqual(row["ssim"]["aggregate_mean"], 0.972836, places=6)

    def test_markdown_key_values_and_svg_builder(self) -> None:
        payload = parse_markdown_key_values("- foo: 1\n- bar: baz\n")
        self.assertEqual(payload, {"foo": "1", "bar": "baz"})

        svg = build_line_chart_svg(
            title="Test",
            x_label="x",
            y_label="y",
            series=[{"name": "a", "color": "#2563eb", "points": [(1, 2), (2, 3)]}],
        )
        self.assertIn("<svg", svg)
        self.assertIn("Test", svg)


if __name__ == "__main__":
    unittest.main()
