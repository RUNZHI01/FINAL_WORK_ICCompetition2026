from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "session_bootstrap"
    / "scripts"
    / "check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy.py"
)

spec = importlib.util.spec_from_file_location(
    "check_fused_variance4_add13_tir_sqrt4_scheduled_reference_vs_working_copy",
    SCRIPT_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FakeCompareHelper:
    def __init__(self) -> None:
        self.report = None

    def require_file(self, path: Path, label: str) -> Path:
        del label
        return Path(path).resolve()

    def load_ir_module(self, module_path: Path, *, operator_name: str):
        return {"module_path": str(module_path), "operator_name": operator_name}

    def make_inputs(self, seed: int, *, input_specs):
        return {"seed": seed, "input_specs": list(input_specs)}

    def build_runtime(self, ir_module, target: str):
        return {"ir_module": ir_module, "target": target}

    def run_module(
        self,
        runtime_module,
        *,
        function_name: str,
        input_specs,
        output_shape,
        inputs,
    ):
        del runtime_module, function_name, input_specs, output_shape, inputs
        return "FAKE_OUTPUT"

    def build_report(
        self,
        *,
        operator_name: str,
        reference_tir: Path,
        candidate_tir: Path,
        target: str,
        seed: int,
        input_specs,
        output_shape,
        reference_output,
        candidate_output,
    ):
        del reference_output, candidate_output
        self.report = {
            "operator": operator_name,
            "reference_tir": str(reference_tir),
            "candidate_tir": str(candidate_tir),
            "target": target,
            "seed": seed,
            "input_shapes": {
                name: list(shape) for name, shape in input_specs
            },
            "output_shape": list(output_shape),
            "exact_equal": True,
            "allclose_atol1e-5_rtol1e-5": True,
        }
        return dict(self.report)

    def maybe_write_json(self, payload, output_json: Path | None) -> None:
        if output_json is None:
            return
        output_json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


class CheckFusedVariance4Add13TirSqrt4ScheduledReferenceVsWorkingCopyTest(
    unittest.TestCase
):
    def test_parse_args_defaults_to_the_v6_candidate(self) -> None:
        args = module.parse_args([])
        self.assertEqual(
            args.candidate_tir.name,
            "fused_variance4_add13_tir_sqrt4_scheduled_form_candidate_v6_working_copy_tir.py",
        )

    def test_main_builds_a_variance4_specific_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            reference_tir = temp_dir / "reference.py"
            candidate_tir = temp_dir / "candidate.py"
            output_json = temp_dir / "report.json"
            reference_tir.write_text("# reference\n", encoding="utf-8")
            candidate_tir.write_text("# candidate\n", encoding="utf-8")
            fake_helper = FakeCompareHelper()

            stdout = io.StringIO()
            with (
                mock.patch.object(module, "_compare_helper", return_value=fake_helper),
                contextlib.redirect_stdout(stdout),
            ):
                rc = module.main(
                    [
                        "--reference-tir",
                        str(reference_tir),
                        "--candidate-tir",
                        str(candidate_tir),
                        "--seed",
                        "123",
                        "--output-json",
                        str(output_json),
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(stdout.getvalue())
            written = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["operator"], module.OPERATOR_NAME)
            self.assertEqual(payload["seed"], 123)
            self.assertEqual(payload["input_shapes"], {"lv335": [1, 12, 256, 256]})
            self.assertEqual(payload["output_shape"], [1, 12, 1, 1])
            self.assertTrue(payload["exact_equal"])
            self.assertTrue(payload["allclose_atol1e-5_rtol1e-5"])
            self.assertEqual(payload["candidate_tir"], written["candidate_tir"])


if __name__ == "__main__":
    unittest.main()
